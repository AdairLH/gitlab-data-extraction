"""
Author: Flavio Córdula
Linkedin: www.linkedin.com/in/cordulaflavio
Date: 2025-02-20
Description: Script to extract issues, milestones, assignees, and participants from GitLab via API and store them in a PostgreSQL database for later reporting in Power BI and Metabase.
GitLab Community Edition: v18.2.1
Python Version: 3.12.3
"""

import gitlab
import psycopg2
import requests

# GitLab configuration
GITLAB_URL = 'GITLAB_URL'
PRIVATE_TOKEN = 'GITLAB_PRIVATE_TOKEN'
PROJECT_IDS = [001, 002, 003]   # List of projects
CREATE_DATE = '2025-05-01'      # Initial date to filter issues

# Database configuration
DB_HOST = 'DB_HOST'
DB_PORT = 'DB_PORT'
DB_NAME = 'DB_NAME'
DB_USER = 'DB_USER'
DB_PASSWORD = 'DB_PASSWORD'

# Header for REST and GraphQL calls
HEADERS = {
    "Authorization": f"Bearer {PRIVATE_TOKEN}",
    "Content-Type": "application/json"
}

# Function to fetch startDate and dueDate via GraphQL
def fetch_start_due_dates(iid):
    query = """
    query ($iid: String!) {
      project(fullPath: "GITLAB_PROJECT_PATH") {
        workItems(iids: [$iid], types: [ISSUE]) {
          nodes {
            widgets(onlyTypes: START_AND_DUE_DATE) {
              ... on WorkItemWidgetStartAndDueDate {
                startDate
                dueDate
              }
            }
          }
        }
      }
    }
    """
    variables = {"iid": str(iid)}

    response = requests.post(
        f"{GITLAB_URL}/api/graphql",
        json={"query": query, "variables": variables},
        headers=HEADERS
    )

    if response.status_code == 200:
        data = response.json()
        nodes = data.get('data', {}).get('project', {}).get('workItems', {}).get('nodes', [])
        if nodes and nodes[0].get('widgets'):
            widget = nodes[0]['widgets'][0]
            return widget.get('startDate'), widget.get('dueDate')
    else:
        print(f"Erro GraphQL IID {iid}: {response.status_code} - {response.text}")

    return None, None

# Get real commenters
def get_real_commenters(issue):
    commenters = {}
    try:
        for note in issue.notes.list(all=True):
            if not getattr(note, 'system', False):
                author = note.author
                commenters[author['id']] = (author['id'], author['username'], author['name'])
    except Exception as e:
        print(f"Error fetching comments for issue {issue.iid}: {e}")
    return list(commenters.values())

# Function to extract process and activity from a PGD label
def extract_pgd_process_activity(labels):
    for label in labels:
        if label.startswith("PGD -") and "***" in label:
            try:
                partes = label.split("-", 1)[1].split("***")
                processo = partes[0].strip()
                atividade = partes[1].strip()
                return processo, atividade
            except:
                return None, None
    return None, None

# GitLab and PostgreSQL connection
def connect_to_gitlab():
    try:
        print("Trying to connect to GitLab...")
        gl = gitlab.Gitlab(GITLAB_URL, private_token=PRIVATE_TOKEN)
        print("Connected to GitLab successfully.")
        return gl
    except Exception as e:
        print(f"Error connecting to GitLab: {e}")
        exit(1)

def connect_to_postgres():
    try:
        print("Trying to connect to PostgreSQL...")
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        print("Connected to PostgreSQL successfully.")
        return conn, cur
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        exit(1)

# Table creation
def create_tables(cur):
    cur.execute('''
        CREATE TABLE IF NOT EXISTS git_lab.Dim_Issues (
            IssuePK TEXT PRIMARY KEY,
            IssueID INTEGER,
            ProjectID INTEGER,
            Title TEXT, Description TEXT, State TEXT,
            CreatedAt TIMESTAMP, StartDate TIMESTAMP,
            DueDate TIMESTAMP, ClosedAt TIMESTAMP, IssueType TEXT
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS git_lab.Dim_Project (
            ProjectID INTEGER PRIMARY KEY,
            ProjectName TEXT, GroupID INTEGER, GroupName TEXT
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS git_lab.Dim_Users (
            UserID INTEGER PRIMARY KEY,
            Username TEXT,
            Name TEXT
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS git_lab.Dim_Milestone (
            MilestoneID INTEGER PRIMARY KEY,
            Title TEXT,
            Description TEXT,
            StartDate TIMESTAMP,
            DueDate TIMESTAMP,
            State TEXT,
            ProjectID INTEGER
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS git_lab.Dim_Labels (
            LabelID SERIAL PRIMARY KEY,
            Name TEXT UNIQUE
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS git_lab.Fact_Issue_Participation (
            FactID SERIAL PRIMARY KEY,
            IssuePK TEXT,
            UserID INTEGER,
            ProjectID INTEGER,
            Role TEXT,
            Processo TEXT,
            Atividade TEXT,
            FOREIGN KEY (IssuePK) REFERENCES git_lab.Dim_Issues (IssuePK),
            FOREIGN KEY (UserID) REFERENCES git_lab.Dim_Users (UserID),
            FOREIGN KEY (ProjectID) REFERENCES git_lab.Dim_Project (ProjectID)
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS git_lab.Fact_Issues (
            FactIssueID SERIAL PRIMARY KEY,
            IssuePK TEXT,
            ProjectID INTEGER,
            MilestoneID INTEGER,
            FOREIGN KEY (IssuePK) REFERENCES git_lab.Dim_Issues (IssuePK),
            FOREIGN KEY (ProjectID) REFERENCES git_lab.Dim_Project (ProjectID),
            FOREIGN KEY (MilestoneID) REFERENCES git_lab.Dim_Milestone (MilestoneID)
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS git_lab.Fact_Issue_Labels (
            LabelFactID SERIAL PRIMARY KEY,
            IssuePK TEXT,
            LabelID INTEGER,
            FOREIGN KEY (IssuePK) REFERENCES git_lab.Dim_Issues (IssuePK),
            FOREIGN KEY (LabelID) REFERENCES git_lab.Dim_Labels (LabelID)
        );
    ''')

# Truncate tables
def truncate_tables(cur):
    cur.execute('TRUNCATE TABLE git_lab.Fact_Issue_Labels, git_lab.Fact_Issue_Participation, git_lab.Fact_Issues, git_lab.Dim_Users, git_lab.Dim_Issues, git_lab.Dim_Project, git_lab.Dim_Milestone, git_lab.Dim_Labels CASCADE')

# Functions to insert data into the corresponding tables
def insert_dim_issues(cur, issue, project_id, start, due):
    issue_pk = f"{project_id}-{issue.iid}" # evitar conflitos de ID de issues entre projetos diferentes
    cur.execute('''
        INSERT INTO git_lab.Dim_Issues (
            IssuePK, IssueID, ProjectID, Title, Description, State,
            CreatedAt, StartDate, DueDate, ClosedAt, IssueType
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (IssuePK) DO NOTHING
    ''', (
        issue_pk, issue.iid, project_id, issue.title, issue.description, issue.state,
        issue.created_at, start, due, issue.closed_at, getattr(issue, 'type', None)
    ))
    return issue_pk 

def insert_dim_project(cur, project):
    gid = project.namespace.get('id')
    gname = project.namespace.get('name')
    cur.execute('''
        INSERT INTO git_lab.Dim_Project VALUES (%s,%s,%s,%s)
        ON CONFLICT (ProjectID) DO NOTHING
    ''', (project.id, project.name, gid, gname))

def insert_dim_user(cur, user_id, username, name):
    cur.execute('''
        INSERT INTO git_lab.Dim_Users VALUES (%s, %s, %s)
        ON CONFLICT (UserID) DO NOTHING
    ''', (user_id, username, name))

def insert_dim_milestone(cur, milestone, project_id):
    if milestone is None:
        return None
    cur.execute('''
        INSERT INTO git_lab.Dim_Milestone (
            MilestoneID, Title, Description, StartDate, DueDate, State, ProjectID
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (MilestoneID) DO NOTHING
    ''', (
        milestone['id'], milestone.get('title'), milestone.get('description'),
        milestone.get('start_date'), milestone.get('due_date'),
        milestone.get('state'), project_id
    ))
    return milestone['id']

def insert_dim_label(cur, label_name):
    cur.execute('''
        INSERT INTO git_lab.Dim_Labels (Name)
        VALUES (%s)
        ON CONFLICT (Name) DO NOTHING
    ''', (label_name,))
    cur.execute('SELECT LabelID FROM git_lab.Dim_Labels WHERE Name = %s', (label_name,))
    return cur.fetchone()[0]

def insert_fact_participation(cur, issue_pk, user_id, project_id, role, processo=None, atividade=None):
    cur.execute('''
        INSERT INTO git_lab.Fact_Issue_Participation (IssuePK, UserID, ProjectID, Role, Processo, Atividade)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (issue_pk, user_id, project_id, role, processo, atividade))

def insert_fact_issues(cur, issue_pk, project_id, milestone_id):
    cur.execute('''
        INSERT INTO git_lab.Fact_Issues (IssuePK, ProjectID, MilestoneID)
        VALUES (%s, %s, %s)
    ''', (issue_pk, project_id, milestone_id))

def insert_fact_issue_label(cur, issue_pk, label_id):
    cur.execute('''
        INSERT INTO git_lab.Fact_Issue_Labels (IssuePK, LabelID)
        VALUES (%s, %s)
    ''', (issue_pk, label_id))

# ISSUE PROCESSING PER PROJECT
def process_issues(project, cur):
    insert_dim_project(cur, project)
    issues = project.issues.list(created_after=CREATE_DATE, all=True)
    
    for issue in issues:
        start, due = fetch_start_due_dates(issue.iid)
        cur.execute('BEGIN')

        issue_pk = insert_dim_issues(cur, issue, project.id, start, due) # Insere e retorna issue_pk

        # Milestone
        milestone_id = None
        if hasattr(issue, 'milestone') and issue.milestone is not None:
            milestone_id = insert_dim_milestone(cur, issue.milestone, project.id)

        insert_fact_issues(cur, issue_pk, project.id, milestone_id)

        # Labels
        if issue.labels:
            for label in issue.labels:
                label_id = insert_dim_label(cur, label)
                insert_fact_issue_label(cur, issue_pk, label_id)

        processo, atividade = extract_pgd_process_activity(issue.labels if issue.labels else [])

        # Assignee
        if issue.assignee:
            insert_dim_user(cur, issue.assignee['id'], issue.assignee['username'], issue.assignee['name'])
            insert_fact_participation(cur, issue_pk, issue.assignee['id'], project.id, 'Assignee', processo, atividade)

        # Commenters
        commenters = get_real_commenters(issue)
        for uid, uname, name in commenters:
            insert_dim_user(cur, uid, uname, name)
            insert_fact_participation(cur, issue_pk, uid, project.id, 'Commenter', processo, atividade)

        # Creator
        if hasattr(issue, 'author') and issue.author:
            insert_dim_user(cur, issue.author['id'], issue.author['username'], issue.author['name'])
            insert_fact_participation(cur, issue_pk, issue.author['id'], project.id, 'Creator', processo, atividade)

        cur.execute('COMMIT')

# MAIN
def main():
    gl = connect_to_gitlab()
    conn, cur = connect_to_postgres()

    create_tables(cur)
    truncate_tables(cur)

    for idx, pid in enumerate(PROJECT_IDS, start=1):
        project = gl.projects.get(pid)
        print(f"Processing project {idx} of {len(PROJECT_IDS)}")
        print(f"Persisting data for project {idx}: {project.name} | ID: {project.id}")
        process_issues(project, cur)

    conn.commit()
    cur.close()
    conn.close()
    print("Successfully completed.")

if __name__ == '__main__':
    main()
