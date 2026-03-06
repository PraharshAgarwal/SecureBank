# SecureBank - Database Management Systems Project (BCSE302L)

A complete web application demonstrating core database concepts including JOIN operations, ACID transactions, stored procedures, indexing, and triggers.

## 🎯 Project Overview

SecureBank is a banking web application designed to showcase various database management concepts required for BCSE302L course evaluation. The application demonstrates:

- **Relational Modeling**: JOIN operations between Customers and Accounts
- **ACID Transactions**: Atomic fund transfers with rollback capability
- **Stored Procedures**: Database-side transaction processing
- **Concurrency Control**: Row-level locking (SELECT ... FOR UPDATE)
- **Indexing**: B+ Tree indexes for fast data retrieval
- **Database Triggers**: Automatic audit logging
- **Normalization**: BCNF compliant database schema

## 📋 Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- pip (Python package manager)

## 🚀 Installation & Setup

### Step 1: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure Database

1. Make sure PostgreSQL is running on your system
2. Update database credentials in `config.py`:
   ```python
   DB_CONFIG = {
       'host': 'localhost',
       'user': 'postgres',  # Change if needed (default PostgreSQL user)
       'password': '',  # Enter your PostgreSQL password
       'database': 'securebank',
       'port': 5432  # Default PostgreSQL port
   }
   ```

### Step 3: Initialize Database

Run the setup script to create the database, tables, stored procedures, and triggers:

```bash
python setup_database.py
```

This script will:
- Create the `securebank` database
- Create all tables (Customers, Accounts, TransactionHistory, AuditLog)
- Insert sample data
- Create stored procedures for fund transfers
- Create triggers for audit logging
- Set up demo user accounts with proper password hashing

### Step 4: Run the Application

```bash
python app.py
```

The application will start on `http://localhost:5001`

## 🔐 Demo Credentials

- **Email**: `john.doe@email.com`
- **Password**: `SecureBank@123`

Additional test accounts:
- `jane.smith@email.com` / `SecureBank@123`
- `bob.wilson@email.com` / `SecureBank@123`

## 📱 Application Pages

### 1. Login Page (`/login`)
- **Purpose**: User authentication
- **Database Feature**: SELECT query with WHERE clause
- **Demonstrates**: Security & Access Control

### 2. Dashboard (`/dashboard`)
- **Purpose**: Display user accounts and balances
- **Database Feature**: INNER JOIN (Customers ↔ Accounts)
- **Demonstrates**: Relational Modeling, JOIN operations
- **Features**:
  - Shows all accounts for logged-in user
  - Account cards with balance display
  - Quick links to transfer and history pages

### 3. Transfer Funds (`/transfer`)
- **Purpose**: Execute fund transfers between accounts
- **Database Feature**: Stored Procedure with ACID transaction
- **Demonstrates**:
  - **Atomicity**: All changes succeed or all rollback
  - **Consistency**: Database remains in valid state
  - **Isolation**: Row-level locking (SELECT ... FOR UPDATE)
  - **Durability**: Committed changes are permanent
- **Features**:
  - Form validation
  - Balance checking
  - Automatic rollback on failure
  - Success/failure feedback

### 4. Transaction History (`/history/<account_id>`)
- **Purpose**: Display transaction history for an account
- **Database Feature**: Indexed queries on timestamp
- **Demonstrates**: B+ Tree Indexing for fast retrieval
- **Features**:
  - Chronological transaction list
  - Color-coded amounts (green for deposits, red for withdrawals)
  - Status indicators
  - Fast query performance using indexed columns

## 🗄️ Database Schema

### Tables

1. **Customers**
   - `customer_id` (PRIMARY KEY)
   - `email` (UNIQUE, INDEXED)
   - `password_hash`
   - `full_name`
   - `created_at`

2. **Accounts**
   - `account_id` (PRIMARY KEY)
   - `customer_id` (FOREIGN KEY → Customers)
   - `account_type`
   - `balance`
   - `created_at`
   - Index on `customer_id` for JOIN operations

3. **TransactionHistory**
   - `transaction_id` (PRIMARY KEY)
   - `from_account_id` (FOREIGN KEY → Accounts)
   - `to_account_id` (FOREIGN KEY → Accounts)
   - `transaction_type`
   - `amount`
   - `status`
   - `transaction_timestamp` (INDEXED - B+ Tree)
   - Multiple indexes for fast retrieval

4. **AuditLog**
   - `log_id` (PRIMARY KEY)
   - `action_type`
   - `user_id`
   - `account_id`
   - `details`
   - `log_timestamp` (INDEXED)

### Stored Procedures

- **TransferFunds**: Implements ACID transaction with:
  - Row-level locking (SELECT ... FOR UPDATE)
  - Balance validation
  - Automatic rollback on error (via exception handling)
  - Transaction logging

### Triggers

- **audit_transfer_access**: Logs every transfer transaction
- **audit_balance_update**: Logs balance changes

## 📊 Database Concepts Demonstrated

| Page/Feature | Database Concept | SQL Implementation |
|-------------|-----------------|-------------------|
| Login | Security & Access | `SELECT ... WHERE email = ?` |
| Dashboard | Relational Modeling | `INNER JOIN Customers ON Accounts` |
| Transfer | ACID Transaction | `START TRANSACTION`, `COMMIT`, `ROLLBACK` |
| Transfer | Concurrency Control | `SELECT ... FOR UPDATE` (Row locking) |
| Transfer | Stored Function | `CREATE FUNCTION TransferFunds` (PostgreSQL) |
| History | Physical Design | `INDEX idx_timestamp` (B+ Tree) |
| All Pages | Normalization | Schema in BCNF (No redundancy) |
| Triggers | Database Triggers | `CREATE TRIGGER audit_*` |

## 🎨 UI Features

- Modern, clean design with gradient background
- Responsive layout (mobile-friendly)
- Flash messages for user feedback
- Color-coded transaction amounts
- Smooth animations and transitions
- Professional banking interface

## 🔧 Troubleshooting

### Database Connection Error
- Verify PostgreSQL is running: `psql -U postgres`
- Check credentials in `config.py`
- Ensure database exists: `psql -U postgres -l`

### Stored Function Not Found
- Run `setup_database.py` again
- Manually execute `stored_procedures.sql` in PostgreSQL: `psql -U postgres -d securebank -f stored_procedures.sql`

### Password Authentication Fails
- Run `setup_database.py` to update password hashes
- Verify you're using the correct demo credentials

## 📝 Project Structure

```
dbms_project/
├── app.py                 # Flask application (main file)
├── config.py              # Database & app configuration
├── setup_database.py      # Database initialization script
├── database_schema.sql    # Database schema and sample data
├── stored_procedures.sql  # ACID transaction stored function
├── triggers.sql           # Database triggers for audit logging
├── demo_queries.sql       # SQL queries for viva demonstration
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
├── QUICK_START.md         # Quick setup guide
├── templates/             # HTML templates
│   ├── partials/
│   │   └── top_nav.html   # Shared navigation bar
│   ├── login.html
│   ├── signup.html
│   ├── dashboard.html
│   ├── transfer.html
│   ├── history.html
│   └── profile.html
└── static/
    └── css/
        └── style.css      # Stylesheet
```

## 🎓 For Viva/Evaluation

### Key Points to Highlight:

1. **ACID Properties**: Explain how the transfer procedure ensures atomicity, consistency, isolation, and durability
2. **Concurrency Control**: Demonstrate row-level locking prevents race conditions
3. **Indexing**: Show how B+ Tree indexes improve query performance
4. **Normalization**: Explain how the schema is in BCNF
5. **Stored Procedures**: Benefits of server-side transaction processing
6. **Triggers**: Automatic audit logging without application code

### Demo Flow:

1. Login with demo credentials
2. Show dashboard with JOIN query results
3. Execute a transfer (show success)
4. Execute a transfer with insufficient balance (show rollback)
5. View transaction history (show indexed query performance)
6. Check audit log in database (show trigger functionality)

## 📄 License

This project is created for educational purposes (BCSE302L course).

## 👨‍💻 Author

Created for BCSE302L Database Management Systems course project.

---

**Note**: This is a demonstration project. For production use, implement additional security measures, input validation, and error handling.
