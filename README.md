# SecureBank - Full-Stack Banking Platform

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Render-46E3B7?style=for-the-badge&logo=render)](https://securebank-ssp4.onrender.com/)

A complete full-stack banking platform demonstrating advanced database management, secure backend engineering, and mobile integration. It features a responsive web interface, a robust REST API, and a seamlessly connected native Android application.

## 🎯 Project Overview

SecureBank is a comprehensive personal project built to showcase scalable architecture and core database principles. The application ecosystem is powered by a Flask backend and a PostgreSQL database, which serves both a dynamic web frontend and a Java-based native Android app.

The database architecture highlights:
* **Relational Modeling:** Efficient `JOIN` operations across normalized tables (BCNF compliant).
* **ACID Transactions:** Atomic fund transfers with automatic exception handling and rollback capabilities.
* **Stored Procedures:** Database-side transaction processing for enhanced security and speed.
* **Concurrency Control:** Row-level locking (`SELECT ... FOR UPDATE`) to prevent race conditions during concurrent transfers.
* **Indexing:** B+ Tree indexes for rapid data retrieval across large transaction histories.
* **Database Triggers:** Automated, application-independent audit logging for security compliance.
* **Normalization:** BCNF-compliant database schema to eliminate data redundancy.

## 🌐 Live Demo & Deployment

The web application and REST APIs are deployed and hosted live on Render.
* **Access the Web App:** [SecureBank](https://securebank-ssp4.onrender.com/)
* **Demo Credentials:**
    * **Email:** `john.doe@email.com`
    * **Password:** `SecureBank@123`

## 📱 Android Native App (Java)

SecureBank includes a native Android application built with Java. The mobile app connects to the deployed Flask backend via a dedicated set of RESTful JSON APIs, providing a secure, real-time banking experience on the go.

### 📥 Getting the App
* **Download APK:** [Download SecureBank.apk](https://github.com/PraharshAgarwal/SecureBank-App/releases/download/v1.0.0/SecureBankv1.apk)
* **Run via Android Studio:** [Github Repository](https://github.com/PraharshAgarwal/SecureBank-App.git)
    1.  Open the Android project folder in Android Studio.
    2.  Sync the project with Gradle files.
    3.  Locate your API configuration file (e.g., `ApiClient.java` or `Constants.java`) and update the Base URL to point to the live server:

        ```java
        public static final String BASE_URL = "YOUR_RENDER_URL_HERE/api/";
        ```
    5.  Build and run on an emulator or physical Android device.

### 🔋 Mobile Features
* Secure authentication via session-based API endpoints.
* Real-time dashboard with consolidated account balances.
* Native UI for executing ACID-compliant fund transfers.
* Interactive transaction history and dynamic account statements.

### 🔌 REST API Endpoints (Mobile Integration)
The backend exposes the following JSON endpoints specifically for the Android client:
* `POST /api/login` & `POST /api/signup`: Authentication and registration.
* `GET /api/dashboard`: Retrieves the user's accounts and total balance.
* `GET /api/profile`: Fetches detailed customer and linked account information.
* `GET /api/transfer` & `POST /api/transfer`: Validates and executes secure fund transfers.
* `GET /api/statement/<account_id>`: Cursor-based paginated transaction history.
* `GET /api/analytics`: Fetches categorical spending/receiving data for native charts.

## 💻 Web Application Features

1.  **Secure Authentication (`/login`)**: User authentication demonstrating secure `SELECT` queries and hashed password validation using `werkzeug.security`.
2.  **Dashboard (`/dashboard`)**: Displays user accounts and balances using multi-table `INNER JOIN` operations.
3.  **Transfer Funds (`/transfer`)**: Executes atomic fund transfers using a PostgreSQL Stored Procedure, demonstrating strict Isolation (Row-level locking) and Durability.
4.  **Transaction History (`/statement`)**: Displays chronological transactions using B+ Tree indexed queries and PL/pgSQL cursors for highly efficient data pagination.
5.  **Analytics (`/analytics`)**: Transaction breakdowns using `GROUP BY`, aggregate functions, and dynamic charting using Chart.js.

## 🗄️ Database Schema Details

### Core Tables
1.  **Customers:** `customer_id`, `email`, `password_hash`, `full_name`, `phone`, `created_at`.
2.  **Accounts:** `account_id`, `customer_id`, `account_type`, `balance`, `ifsc_code`, `account_number`, `branch_name`.
3.  **TransactionHistory:** `transaction_id`, `from_account_id`, `to_account_id`, `transaction_type`, `amount`, `status`, `transaction_timestamp`.
4.  **AuditLog:** `log_id`, `action_type`, `user_id`, `account_id`, `details`, `log_timestamp`.
5.  **LoginActivity:** Tracks user logins, IP addresses, and device info for security audits.

### Advanced Database Objects
* **Stored Procedures (`TransferFunds`)**: Implements complex business logic directly in the database, ensuring data integrity even if the application layer fails.
* **Triggers**: `audit_transfer_access` and `audit_balance_update` for automated compliance logging.
* **Materialized Views**: Pre-computed monthly aggregates (`mv_monthly_transaction_summary`) for lightning-fast analytics rendering.
* **Cursor Functions**: `GetPaginatedStatement` utilizing PL/pgSQL cursors (`DECLARE`, `OPEN`, `FETCH`, `MOVE`) for fast offset pagination.

## 🚀 Local Installation & Setup

### Prerequisites
* Python 3.8+
* PostgreSQL 12+
* pip (Python package manager)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Database
Update the database credentials in config.py to match your local PostgreSQL setup:

```Python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'postgres',  
    'password': 'your_password',  
    'database': 'securebank',
    'port': 5432  
}
```

### Step 3: Initialize Database
Run the setup script to create the database, tables, stored procedures, and triggers, and to seed the demo users:

```Bash
python setup_database.py
```

### Step 4: Run the Application
```Bash
python app.py
```
The web application and backend REST API will start on http://localhost:5001.


## 🔧 Troubleshooting (Local Setup)
* **Database Connection Error**: Verify PostgreSQL is running (psql -U postgres), check credentials in config.py, and ensure the database exists.
* **Stored Function Not Found**: Run setup_database.py again or manually execute the SQL scripts in PostgreSQL.


## 🛠️ Tech Stack
* **Backend:** Python, Flask, RESTful APIs
* **Database:** PostgreSQL, psycopg2
* **Frontend (Web):** HTML5, CSS3, JavaScript, Chart.js
* **Frontend (Mobile):** Java, Android SDK
* **Security:** Werkzeug Password Hashing, Session Management
