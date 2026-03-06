# SecureBank - Quick Start Guide

## 🚀 Fast Setup (5 minutes)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Database
Edit `config.py` - update PostgreSQL credentials:
```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'postgres',    # Your PostgreSQL username (default)
    'password': 'yourpass', # Your PostgreSQL password
    'database': 'securebank',
    'port': 5432           # Default PostgreSQL port
}
```

### Step 3: Initialize Database
```bash
python setup_database.py
```

### Step 4: Run Application
```bash
python app.py
```

### Step 5: Access Application
Open browser: `http://localhost:5001`

**Login Credentials:**
- Email: `john.doe@email.com`
- Password: `SecureBank@123`

---

## 📋 What Each Page Demonstrates

| Page | URL | Database Concept |
|------|-----|-----------------|
| Login | `/login` | SELECT query, Authentication |
| Dashboard | `/dashboard` | INNER JOIN (Customer ↔ Accounts) |
| Transfer | `/transfer` | ACID Transaction, Stored Procedure, Locking |
| History | `/history/<id>` | Indexed Query (B+ Tree) |

---

## 🎯 For Viva Demonstration

### 1. Show JOIN Operation
- Login and view dashboard
- Explain: "This page uses INNER JOIN to combine Customer and Accounts tables"

### 2. Show ACID Transaction
- Go to Transfer page
- Transfer funds successfully
- Try to transfer more than balance (shows rollback)
- Explain: "This uses a stored procedure with START TRANSACTION, COMMIT, and ROLLBACK"

### 3. Show Concurrency Control
- Explain: "The stored procedure uses SELECT ... FOR UPDATE for row-level locking"
- Show in `stored_procedures.sql` file

### 4. Show Indexing
- View transaction history
- Explain: "The timestamp column has a B+ Tree index for fast retrieval"
- Run: `EXPLAIN SELECT ... FROM TransactionHistory WHERE transaction_timestamp ...`

### 5. Show Triggers
- Execute a transfer
- Run query: `SELECT * FROM AuditLog ORDER BY log_timestamp DESC LIMIT 5`
- Explain: "The trigger automatically logs every transfer"

---

## 🔍 Useful SQL Queries for Demo

See `demo_queries.sql` for ready-to-use queries.

### Quick Checks:
```sql
-- View all accounts
SELECT * FROM Accounts;

-- View transaction history
SELECT * FROM TransactionHistory ORDER BY transaction_timestamp DESC;

-- View audit log (trigger output)
SELECT * FROM AuditLog ORDER BY log_timestamp DESC LIMIT 10;

-- Check stored function definition
SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname = 'transferfunds';

-- Check triggers
SELECT trigger_name, event_object_table, action_timing, event_manipulation
FROM information_schema.triggers WHERE trigger_schema = 'public';
```

---

## ⚠️ Troubleshooting

**Problem**: Database connection error
- **Solution**: Check PostgreSQL is running and credentials are correct

**Problem**: Stored procedure not found
- **Solution**: Run `setup_database.py` again or manually execute `stored_procedures.sql`

**Problem**: Password authentication fails
- **Solution**: Run `setup_database.py` to update password hashes

**Problem**: Port 5000 already in use
- **Solution**: Change port in `app.py`: `app.run(debug=True, port=5001)`

---

## 📁 Project Files

- `app.py` - Main Flask application
- `database_schema.sql` - Database structure
- `stored_procedures.sql` - ACID transaction procedure
- `triggers.sql` - Audit logging triggers
- `setup_database.py` - Database initialization
- `demo_queries.sql` - SQL queries for demonstration
- `templates/` - HTML pages
- `static/css/` - Stylesheet

---

## ✅ Checklist Before Viva

- [ ] Database is set up and running
- [ ] Application starts without errors
- [ ] Can login with demo credentials
- [ ] Dashboard shows accounts (JOIN working)
- [ ] Transfer page works (stored procedure working)
- [ ] Transaction history loads (indexing working)
- [ ] Audit log has entries (triggers working)
- [ ] Ready to explain each database concept

---

**Good luck with your presentation! 🎓**
