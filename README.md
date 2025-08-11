# GitLab Data Extraction

Author: Flavio Ribeiro Córdula [![LinkedIn](https://img.shields.io/badge/LinkedIn--blue?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/cordulaflavio)

---

## 1. Introduction

This project collects and structures GitLab issue tracking data into a dimensional model for analytics.

Its main objective is to extract and model all issues created by IT staff or imported through the integration between OTRS and GitLab — which now automatically receives tickets as issues. This provides a practical and accessible data foundation for STI managers — including department heads and the superintendent — to monitor the volume, distribution, and status of every task or demand submitted by the UFPB academic community.

The second part of this initiative, maintained in a separate project, focuses on creating a private dashboard in Metabase and a public dashboard in Power BI based on the data extracted by this script.

Beyond improving management capabilities, the project fosters internal transparency, enhances resource allocation, and supports the prioritization of critical demands.

## 2. Reach

- Reaches **90+ STI staff members**, including IT technicians and analysts.
- Used by **all IT managers** and the **STI superintendent**.
- Some views are also used by **institutional managers from other departments**.

## 3. Production Timeline

- In production since **February 2025**.

## 4. Technologies Used

* **GitLab Community Edition:** v18.2.1
* **Python:** 3.12.3
* **Key Python libraries:**

  * `gitlab`
  * `psycopg2`
  * `requests` (used for REST and GraphQL API calls)

* Additional Tools:

  * `DBeaver` (used for database modeling, querying, and managing PostgreSQL)

## 5. Project Architecture

The project follows a daily ETL process executed by GitLab, extracting and transforming data from GitLab issues into a dimensional model stored in PostgreSQL.

The entity-relationship diagram below was generated with DBeaver and illustrates the fact and dimension tables created by the script.

The Python source code responsible for data extraction and loading is located in the src/ folder.


