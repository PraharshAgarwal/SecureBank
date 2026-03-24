"""
SecureBank - Flask Web Application
BCSE302L Database Management Systems Project
Demonstrates: JOIN operations, ACID transactions, Stored Functions, Indexing, Triggers
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, Response, jsonify
import psycopg2
from psycopg2 import Error
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from config import DB_CONFIG, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=30)

# Indian Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# DB_CONFIG imported from config.py


def get_db_connection():
    """Create and return database connection"""
    try:
        # Use connection string format to ensure password is properly included
        conn_string = (
            f"host={DB_CONFIG['host']} "
            f"port={DB_CONFIG['port']} "
            f"dbname={DB_CONFIG['database']} "
            f"user={DB_CONFIG['user']} "
            f"password={DB_CONFIG['password']}"
        )
        conn = psycopg2.connect(conn_string)
        return conn
    except Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        print(
            f"Attempted connection to: {DB_CONFIG['host']}:{DB_CONFIG['port']}/"
            f"{DB_CONFIG['database']} as user {DB_CONFIG['user']}"
        )
        return None


def mask_email(email: str):
    """Return a masked version of an email for display (e.g., j***@bank.com)."""
    if not email or '@' not in email:
        return None
    name, domain = email.split('@', 1)
    if len(name) <= 1:
        masked_name = '*'
    else:
        masked_name = name[0] + '***'
    return f"{masked_name}@{domain}"


def login_required(f):
    """Decorator to require login for protected routes.
    Validates that user_id exists in the session AND corresponds
    to a real customer in the database.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))

        # Server-side validation: verify the user still exists in DB
        conn = get_db_connection()
        if not conn:
            session.clear()
            flash('Session error. Please log in again.', 'error')
            return redirect(url_for('login'))

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT customer_id FROM Customers WHERE customer_id = %s",
                (session['user_id'],),
            )
            user = cursor.fetchone()
            cursor.close()
            conn.close()

            if not user:
                session.clear()
                flash('Session expired. Please log in again.', 'error')
                return redirect(url_for('login'))
        except Error:
            session.clear()
            if conn:
                conn.close()
            flash('Session error. Please log in again.', 'error')
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return decorated_function


@app.after_request
def add_no_cache_headers(response):
    """Prevent browsers from caching protected pages.
    Ensures the back-button cannot show stale authenticated content."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/')
def index():
    """Redirect to login page"""
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login Page - Demonstrates: Security & Access (SELECT query)"""
    # Determine returning user info from cookie
    last_email = request.cookies.get('last_email')
    masked_email = mask_email(last_email) if last_email else None
    last_login = None
    last_device = None

    # Fetch last successful login activity for returning user (previous login)
    if last_email:
        conn_activity = get_db_connection()
        if conn_activity:
            try:
                cursor = conn_activity.cursor(cursor_factory=RealDictCursor)
                activity_query = """
                    SELECT la.login_timestamp, la.device_info
                    FROM LoginActivity la
                    JOIN Customers c ON la.customer_id = c.customer_id
                    WHERE c.email = %s
                    ORDER BY la.login_timestamp DESC
                    OFFSET 1 LIMIT 1
                """
                cursor.execute(activity_query, (last_email,))
                activity = cursor.fetchone()
                if activity:
                    ts = activity["login_timestamp"]
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    last_login = ts.astimezone(IST)
                    last_device = activity["device_info"]
            except Error:
                pass
            finally:
                conn_activity.close()

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error. Please try again.', 'error')
            return render_template(
                'login.html',
                masked_email=masked_email,
                last_login=last_login,
                last_device=last_device,
            )
        
        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            # SELECT query for authentication
            query = "SELECT customer_id, email, password_hash, full_name FROM Customers WHERE email = %s"
            cursor.execute(query, (email,))
            user = cursor.fetchone()
            
            if user and user['password_hash'] and check_password_hash(str(user['password_hash']), str(password)):
                # Login successful - record login activity
                device_info = request.headers.get('User-Agent', 'Unknown device')
                ip_address = request.remote_addr

                try:
                    cursor.execute(
                        """
                        INSERT INTO LoginActivity (customer_id, device_info, ip_address)
                        VALUES (%s, %s, %s)
                        """,
                        (user['customer_id'], device_info, ip_address),
                    )
                    conn.commit()
                except Error:
                    conn.rollback()

                session.permanent = True
                session['user_id'] = user['customer_id']
                session['user_name'] = user['full_name']
                session['user_email'] = user['email']

                # Set masked email cookie for future visits
                tab_token = str(uuid.uuid4())
                response = make_response(redirect(url_for('dashboard', tab_token=tab_token)))
                response.set_cookie('last_email', user['email'], max_age=30 * 24 * 60 * 60)
                return response
            else:
                flash('Invalid email or password. Please try again.', 'error')
        except Error as e:
            flash(f'Login error: {str(e)}', 'error')
        finally:
            if conn:
                conn.close()
    
    return render_template(
        'login.html',
        masked_email=masked_email,
        last_login=last_login,
        last_device=last_device,
    )


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Signup Page - Register a new customer account"""
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        if not all([full_name, email, password, confirm_password]):
            flash('All required fields must be filled.', 'error')
            return render_template('signup.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('signup.html')

        # Password strength check
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('signup.html')

        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(not c.isalnum() for c in password)
        if not (has_upper and has_lower and has_digit and has_symbol):
            flash('Password must include uppercase, lowercase, digit, and symbol.', 'error')
            return render_template('signup.html')

        conn = get_db_connection()
        if not conn:
            flash('Database connection error. Please try again.', 'error')
            return render_template('signup.html')

        try:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Check if email already exists
            cursor.execute("SELECT customer_id FROM Customers WHERE email = %s", (email,))
            if cursor.fetchone():
                flash('An account with this email already exists.', 'error')
                cursor.close()
                conn.close()
                return render_template('signup.html')

            # Create customer
            password_hash = generate_password_hash(password)
            cursor.execute(
                """
                INSERT INTO Customers (email, password_hash, full_name, phone)
                VALUES (%s, %s, %s, %s)
                RETURNING customer_id
                """,
                (email, password_hash, full_name, phone or None),
            )
            row = cursor.fetchone()
            customer_id = row['customer_id'] if row else None

            # Auto-create a savings account
            account_number = ''.join(str(random.randint(0, 9)) for _ in range(12))
            ifsc_prefixes = ['SECB0']
            ifsc_code = random.choice(ifsc_prefixes) + f"{random.randint(0, 999999):06d}"
            branches = ['Mumbai Downtown', 'Bangalore MG Road', 'Delhi Connaught Place', 'Chennai Central']
            branch = random.choice(branches)

            cursor.execute(
                """
                INSERT INTO Accounts (customer_id, account_type, account_number, ifsc_code, branch_name, balance)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (customer_id, 'Savings', account_number, ifsc_code, branch, 1000.00),
            )

            conn.commit()

            # Auto-login
            session.permanent = True
            session['user_id'] = customer_id
            session['user_name'] = full_name
            session['user_email'] = email

            flash(f'Account created successfully! Your account number is {account_number}.', 'success')
            cursor.close()
            conn.close()

            tab_token = str(uuid.uuid4())
            response = make_response(redirect(url_for('dashboard', tab_token=tab_token)))
            response.set_cookie('last_email', email, max_age=30 * 24 * 60 * 60)
            return response

        except Error as e:
            if conn:
                conn.rollback()
                conn.close()
            flash(f'Registration error: {str(e)}', 'error')
            return render_template('signup.html')

    return render_template('signup.html')


@app.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard Page - Demonstrates: JOIN operation (Customer + Accounts)
    Shows all accounts for the logged-in user
    """
    conn = get_db_connection()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('login'))
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # JOIN query: Customer + Accounts with account numbers
        query = """
            SELECT 
                a.account_id,
                a.account_type,
                a.balance,
                a.account_number,
                a.ifsc_code,
                a.branch_name,
                a.created_at,
                c.full_name,
                c.email
            FROM Accounts a
            INNER JOIN Customers c ON a.customer_id = c.customer_id
            WHERE c.customer_id = %s
            ORDER BY a.account_id
        """
        cursor.execute(query, (session['user_id'],))
        accounts = cursor.fetchall()
        
        # Get last login time
        last_login_query = """
            SELECT login_timestamp, device_info
            FROM LoginActivity
            WHERE customer_id = %s
            ORDER BY login_timestamp DESC
            LIMIT 1
        """
        cursor.execute(last_login_query, (session['user_id'],))
        last_login_data = cursor.fetchone()
        
        last_login = None
        if last_login_data and last_login_data['login_timestamp']:
            ts = last_login_data['login_timestamp']
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            last_login = ts.astimezone(IST).strftime('%d %b %Y at %I:%M %p')
        
        cursor.close()
        conn.close()
        
        return render_template('dashboard.html', 
                             user_name=session['user_name'],
                             accounts=accounts,
                             last_login=last_login)
    except Error as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('login'))


@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    """
    Transfer Funds Page - Demonstrates: ACID Transaction, Stored Function, Concurrency Control
    This is the most important page for demonstrating database concepts
    """
    conn = get_db_connection()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Get user's accounts for dropdown (with account numbers)
        query = """
            SELECT account_id, account_type, balance, account_number, ifsc_code, branch_name
            FROM Accounts
            WHERE customer_id = %s
            ORDER BY account_id
        """
        cursor.execute(query, (session['user_id'],))
        user_accounts = cursor.fetchall()
        
        # Get list of other accounts for reference (to show available accounts to transfer to)
        other_accounts_query = """
            SELECT a.account_id, a.account_number, a.ifsc_code, a.branch_name, c.full_name
            FROM Accounts a
            JOIN Customers c ON a.customer_id = c.customer_id
            WHERE a.customer_id != %s
            ORDER BY c.full_name, a.account_id
        """
        cursor.execute(other_accounts_query, (session['user_id'],))
        other_accounts = cursor.fetchall()
        
        if request.method == 'POST':
            from_account_id = request.form.get('from_account')
            to_account_number = request.form.get('to_account')  # Now expects 12-digit account number
            amount = request.form.get('amount')
            beneficiary_name = request.form.get('beneficiary_name')
            bank_name = request.form.get('bank_name')
            ifsc = request.form.get('ifsc')
            category = request.form.get('category', 'General')
            
            # Validation
            if not all([from_account_id, to_account_number, amount, beneficiary_name, bank_name, ifsc]):
                flash('All fields are required.', 'error')
                return render_template('transfer.html', accounts=user_accounts, other_accounts=other_accounts)
            
            try:
                amount = float(amount or 0)
                from_account_id = int(from_account_id or 0)
                
                if amount <= 0:
                    flash('Amount must be greater than zero.', 'error')
                    return render_template('transfer.html', accounts=user_accounts, other_accounts=other_accounts)
                
                # Look up destination account by account_number
                to_account_query = "SELECT account_id FROM Accounts WHERE account_number = %s"
                cursor.execute(to_account_query, (to_account_number,))
                to_account = cursor.fetchone()
                
                if not to_account:
                    flash(f'Account number {to_account_number} not found. Please check and try again.', 'error')
                    return render_template('transfer.html', accounts=user_accounts, other_accounts=other_accounts)
                
                to_account_id = to_account['account_id']
                
                if from_account_id == to_account_id:
                    flash('Source and destination accounts cannot be the same.', 'error')
                    return render_template('transfer.html', accounts=user_accounts, other_accounts=other_accounts)
                
            except ValueError:
                flash('Invalid input. Please check account number (12 digits) and amount.', 'error')
                return render_template('transfer.html', accounts=user_accounts, other_accounts=other_accounts)
            
            # Call Stored Function for ACID Transaction
            try:
                # Close previous cursor and create new one for stored function
                cursor.close()
                cursor = conn.cursor()
                # Call stored function (PostgreSQL functions return records)
                cursor.execute(
                    "SELECT * FROM TransferFunds(%s, %s, %s, %s)",
                    (from_account_id, to_account_id, amount, category)
                )
                result = cursor.fetchone()
                
                # Get output parameters
                status = result[0] if result else None  # p_status
                message = result[1] if result else None  # p_message
                
                if status == 'Success':
                    conn.commit()  # Commit the transaction
                    flash(str(message or 'Transfer completed'), 'success')
                else:
                    conn.rollback()  # Rollback on failure
                    flash(str(message or 'Transfer failed'), 'error')
                
                cursor.close()
                conn.close()
                
                return redirect(url_for('dashboard'))
                
            except Error as e:
                if conn:
                    conn.rollback()
                    conn.close()
                flash(f'Transfer failed: {str(e)}. Transaction rolled back.', 'error')
                return render_template('transfer.html', accounts=user_accounts, other_accounts=other_accounts)
        
        # Close cursor and connection before returning template
        cursor.close()
        conn.close()
        return render_template('transfer.html', accounts=user_accounts, other_accounts=other_accounts)
        
    except Error as e:
        flash(f'Error: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('dashboard'))



@app.route('/profile')
@login_required
def profile():
    """
    Profile Page - Shows personal info and secure banking details for the logged-in user.
    """
    conn = get_db_connection()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('dashboard'))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch customer record
        cursor.execute(
            """
            SELECT customer_id, full_name, email, phone, created_at
            FROM Customers
            WHERE customer_id = %s
            """,
            (session['user_id'],),
        )
        customer = cursor.fetchone()

        # Fetch all accounts for this customer, including sensitive fields
        cursor.execute(
            """
            SELECT
                account_id,
                account_type,
                account_number,
                ifsc_code,
                branch_name,
                balance,
                created_at
            FROM Accounts
            WHERE customer_id = %s
            ORDER BY account_id
            """,
            (session['user_id'],),
        )
        accounts = cursor.fetchall()

        cursor.close()
        conn.close()

        if not customer:
            flash('Profile not found.', 'error')
            return redirect(url_for('dashboard'))

        primary_account = accounts[0] if accounts else None

        return render_template(
            'profile.html',
            customer=customer,
            accounts=accounts,
            primary_account=primary_account,
        )
    except Error as e:
        flash(f'Error loading profile: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('dashboard'))

@app.route('/statement/<int:account_id>')
@login_required
def statement(account_id):
    """
    Paginated Bank Statement — Demonstrates: Database Cursors
    Calls the GetPaginatedStatement() stored function which uses
    DECLARE CURSOR, OPEN, FETCH, MOVE FORWARD, CLOSE in PL/pgSQL.
    """
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1

    conn = get_db_connection()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('dashboard'))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verify account belongs to user
        cursor.execute(
            "SELECT customer_id FROM Accounts WHERE account_id = %s",
            (account_id,),
        )
        account = cursor.fetchone()
        if not account or account['customer_id'] != session['user_id']:
            flash('Access denied. Account not found.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('dashboard'))

        # Get account details
        cursor.execute(
            """SELECT account_id, account_type, balance, account_number, ifsc_code
               FROM Accounts WHERE account_id = %s""",
            (account_id,),
        )
        account_info = cursor.fetchone()

        # Get available months for this account
        cursor.execute("""
            SELECT DISTINCT
                EXTRACT(YEAR FROM transaction_timestamp)::INT AS yr,
                EXTRACT(MONTH FROM transaction_timestamp)::INT AS mo,
                TO_CHAR(transaction_timestamp, 'Mon YYYY') AS label
            FROM TransactionHistory
            WHERE (from_account_id = %s OR to_account_id = %s)
              AND status = 'Success'
            ORDER BY yr DESC, mo DESC
        """, (account_id, account_id))
        available_months = cursor.fetchall()

        # Get filter params (optional — if not provided, show all)
        filter_year = request.args.get('year', type=int)
        filter_month = request.args.get('month', type=int)

        # Call cursor-based stored function (fetches all, we filter afterward)
        # Use a large page size to get all transactions when filtering
        if filter_year and filter_month:
            # Fetch all transactions for filtering
            cursor.execute(
                "SELECT * FROM GetPaginatedStatement(%s, %s, %s)",
                (account_id, 1, 10000),
            )
            all_transactions = cursor.fetchall()

            # Filter by selected month/year
            filtered = [
                t for t in all_transactions
                if t['transaction_date'] and
                   t['transaction_date'].year == filter_year and
                   t['transaction_date'].month == filter_month
            ]

            # Manual pagination on filtered results
            per_page = 10
            total_records = len(filtered)
            total_pages = max(1, -(-total_records // per_page))  # ceil division
            start = (page - 1) * per_page
            transactions = list(filtered[start:start + per_page])  # type: ignore

            # Re-number rows
            for i, t in enumerate(transactions):
                t['row_num'] = start + i + 1
                t['total_records'] = total_records
                t['total_pages'] = total_pages
        else:
            cursor.execute(
                "SELECT * FROM GetPaginatedStatement(%s, %s, %s)",
                (account_id, page, 10),
            )
            transactions = cursor.fetchall()
            total_records = transactions[0]['total_records'] if transactions else 0
            total_pages = transactions[0]['total_pages'] if transactions else 0

        cursor.close()
        conn.close()

        return render_template(
            'statement.html',
            account=account_info,
            transactions=transactions,
            page=page,
            total_pages=total_pages,
            total_records=total_records,
            available_months=available_months,
            filter_year=filter_year,
            filter_month=filter_month,
        )
    except Error as e:
        flash(f'Error loading statement: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('dashboard'))


@app.route('/analytics')
@login_required
def analytics():
    """Transaction Analytics — Demonstrates: GROUP BY, Aggregate Functions, JOINs"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('dashboard'))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get user's account IDs
        cursor.execute(
            "SELECT account_id FROM Accounts WHERE customer_id = %s",
            (session['user_id'],),
        )
        user_accounts = [r['account_id'] for r in cursor.fetchall()]

        if not user_accounts:
            cursor.close()
            conn.close()
            now = datetime.now()
            return render_template('analytics.html', chart_data=[], credit_chart_data=[], monthly_totals=[], all_time_data=[], available_months=[], available_years=[], summary_year=now.year)

        placeholders = ','.join(['%s'] * len(user_accounts))

        # Get available months from transaction history
        cursor.execute(f"""
            SELECT DISTINCT
                EXTRACT(YEAR FROM transaction_timestamp)::INT AS yr,
                EXTRACT(MONTH FROM transaction_timestamp)::INT AS mo,
                TO_CHAR(transaction_timestamp, 'Mon YYYY') AS label
            FROM TransactionHistory
            WHERE (from_account_id IN ({placeholders}) OR to_account_id IN ({placeholders}))
              AND status = 'Success'
            ORDER BY yr DESC, mo DESC
        """, tuple(user_accounts) * 2)
        available_months = cursor.fetchall()

        # Determine selected month/year from query params
        now = datetime.now()
        sel_year = request.args.get('year', now.year, type=int)
        sel_month = request.args.get('month', now.month, type=int)

        # Category-wise spending (debits only) for selected month
        cursor.execute(f"""
            SELECT
                COALESCE(category, 'General') AS category,
                SUM(amount) AS total,
                COUNT(*) AS txn_count
            FROM TransactionHistory
            WHERE from_account_id IN ({placeholders})
              AND status = 'Success'
              AND EXTRACT(YEAR FROM transaction_timestamp) = %s
              AND EXTRACT(MONTH FROM transaction_timestamp) = %s
            GROUP BY COALESCE(category, 'General')
            ORDER BY total DESC
        """, tuple(user_accounts) + (sel_year, sel_month))
        chart_data = cursor.fetchall()

        # Category-wise credits (incoming) for selected month
        cursor.execute(f"""
            SELECT
                COALESCE(category, 'General') AS category,
                SUM(amount) AS total,
                COUNT(*) AS txn_count
            FROM TransactionHistory
            WHERE to_account_id IN ({placeholders})
              AND status = 'Success'
              AND EXTRACT(YEAR FROM transaction_timestamp) = %s
              AND EXTRACT(MONTH FROM transaction_timestamp) = %s
            GROUP BY COALESCE(category, 'General')
            ORDER BY total DESC
        """, tuple(user_accounts) + (sel_year, sel_month))
        credit_chart_data = cursor.fetchall()

        # Determine selected summary year from query params
        summary_year = request.args.get('summary_year', now.year, type=int)

        # Get available years for monthly summary dropdown
        cursor.execute(f"""
            SELECT DISTINCT EXTRACT(YEAR FROM transaction_timestamp)::INT AS yr
            FROM TransactionHistory
            WHERE (from_account_id IN ({placeholders}) OR to_account_id IN ({placeholders}))
              AND status = 'Success'
            ORDER BY yr DESC
        """, tuple(user_accounts) * 2)
        available_years = [r['yr'] for r in cursor.fetchall()]

        # Monthly totals for selected year
        cursor.execute(f"""
            SELECT
                TO_CHAR(transaction_timestamp, 'Mon YYYY') AS month_label,
                SUM(CASE WHEN from_account_id IN ({placeholders}) THEN amount ELSE 0 END) AS total_debit,
                SUM(CASE WHEN to_account_id IN ({placeholders}) THEN amount ELSE 0 END) AS total_credit
            FROM TransactionHistory
            WHERE (from_account_id IN ({placeholders}) OR to_account_id IN ({placeholders}))
              AND status = 'Success'
              AND EXTRACT(YEAR FROM transaction_timestamp) = %s
            GROUP BY TO_CHAR(transaction_timestamp, 'Mon YYYY'),
                     DATE_TRUNC('month', transaction_timestamp)
            ORDER BY DATE_TRUNC('month', transaction_timestamp) DESC
        """, tuple(user_accounts) * 4 + (summary_year,))
        monthly_totals = cursor.fetchall()

        # All-time category breakdown
        cursor.execute(f"""
            SELECT
                COALESCE(category, 'General') AS category,
                SUM(amount) AS total,
                COUNT(*) AS txn_count
            FROM TransactionHistory
            WHERE (from_account_id IN ({placeholders}) OR to_account_id IN ({placeholders}))
              AND status = 'Success'
            GROUP BY COALESCE(category, 'General')
            ORDER BY total DESC
        """, tuple(user_accounts) * 2)
        all_time_data = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template(
            'analytics.html',
            chart_data=chart_data,
            credit_chart_data=credit_chart_data,
            monthly_totals=monthly_totals,
            all_time_data=all_time_data,
            available_months=available_months,
            available_years=available_years,
            sel_year=sel_year,
            sel_month=sel_month,
            summary_year=summary_year,
        )
    except Error as e:
        flash(f'Error loading analytics: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('dashboard'))


@app.route('/statement/<int:account_id>/pdf')
@login_required
def statement_pdf(account_id):
    """Generate and download a PDF bank statement."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

    conn = get_db_connection()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('statement', account_id=account_id))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verify account belongs to user
        cursor.execute("SELECT customer_id FROM Accounts WHERE account_id = %s", (account_id,))
        acc_check = cursor.fetchone()
        if not acc_check or acc_check['customer_id'] != session['user_id']:
            flash('Access denied.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('dashboard'))

        # Customer info
        cursor.execute(
            "SELECT full_name, email, phone, created_at FROM Customers WHERE customer_id = %s",
            (session['user_id'],),
        )
        customer = cursor.fetchone()

        # Account info
        cursor.execute(
            """SELECT account_id, account_type, balance, account_number, ifsc_code, branch_name
               FROM Accounts WHERE account_id = %s""",
            (account_id,),
        )
        account = cursor.fetchone()

        # All transactions (no pagination for PDF — fetch all)
        cursor.execute(
            "SELECT * FROM GetPaginatedStatement(%s, %s, %s)",
            (account_id, 1, 10000),
        )
        all_transactions = cursor.fetchall()

        # Apply year/month filter if provided
        filter_year = request.args.get('year', type=int)
        filter_month = request.args.get('month', type=int)

        if filter_year and filter_month:
            transactions = [
                t for t in all_transactions
                if t['transaction_date'] and
                   t['transaction_date'].year == filter_year and
                   t['transaction_date'].month == filter_month
            ]
            # Re-number rows
            for i, t in enumerate(transactions):
                t['row_num'] = i + 1
        else:
            transactions = all_transactions

        cursor.close()
        conn.close()

        # Build period label for PDF
        month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December']
        if filter_year and filter_month:
            period_label = f'{month_names[filter_month]} {filter_year}'
        else:
            period_label = None

        # --- Build PDF ---
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=20*mm, rightMargin=20*mm,
            topMargin=15*mm, bottomMargin=15*mm,
        )

        styles = getSampleStyleSheet()
        elements = []

        # Custom styles
        title_style = ParagraphStyle('BankTitle', parent=styles['Title'],
            fontSize=24, textColor=colors.HexColor('#1E293B'), spaceAfter=2,
            alignment=TA_LEFT)
        subtitle_style = ParagraphStyle('BankSub', parent=styles['Normal'],
            fontSize=10, textColor=colors.HexColor('#64748B'), spaceAfter=4)
        heading_style = ParagraphStyle('SectionHead', parent=styles['Heading2'],
            fontSize=11, textColor=colors.HexColor('#1E293B'), spaceBefore=10, spaceAfter=6)
        normal_style = ParagraphStyle('NormalText', parent=styles['Normal'],
            fontSize=9, textColor=colors.HexColor('#334155'), leading=14)
        small_style = ParagraphStyle('SmallText', parent=styles['Normal'],
            fontSize=8, textColor=colors.HexColor('#94A3B8'))

        blue = '#4F46E5'
        dark = '#1E293B'

        # -- Colored Logo Header --
        logo_html = (
            f'<font name="Helvetica-Bold" size="24" color="{blue}">Secure</font>'
            f'<font name="Helvetica-Bold" size="24" color="{dark}">Bank</font>'
        )
        elements.append(Paragraph(logo_html, ParagraphStyle(
            'Logo', parent=styles['Normal'], fontSize=24, leading=28, spaceAfter=2)))
        subtitle_text = 'Account Statement'
        if period_label:
            subtitle_text += f' — {period_label}'
        elements.append(Paragraph(subtitle_text, subtitle_style))
        elements.append(Paragraph(
            f'Generated on {datetime.now().strftime("%d %B %Y, %I:%M %p")}',
            small_style
        ))
        elements.append(Spacer(1, 3*mm))
        elements.append(HRFlowable(width='100%', thickness=1.2,
            color=colors.HexColor(blue)))
        elements.append(Spacer(1, 5*mm))

        # -- Customer & Account Details (formatted cards) --
        cust_name = customer['full_name'] if customer else 'N/A'
        cust_email = customer['email'] if customer else 'N/A'
        cust_phone = customer['phone'] if customer and customer['phone'] else 'N/A'
        member_since = customer['created_at'].strftime('%d %b %Y') if customer and customer['created_at'] else 'N/A'

        acct_num = account['account_number'] if account else 'N/A'
        acct_type = account['account_type'] if account else 'N/A'
        ifsc = account['ifsc_code'] if account else 'N/A'
        branch = (account.get('branch_name', 'N/A') if account else 'N/A') or 'N/A'
        balance = f"Rs. {account['balance']:,.2f}" if account else 'N/A'

        label_s = ParagraphStyle('Lbl', parent=normal_style,
            textColor=colors.HexColor('#94A3B8'), fontSize=7.5,
            spaceBefore=0, spaceAfter=0, leading=10)
        value_s = ParagraphStyle('Val', parent=normal_style,
            fontSize=9, textColor=colors.HexColor('#1E293B'),
            spaceBefore=0, spaceAfter=3, leading=12)

        def info_cell(label, value):
            return [Paragraph(label, label_s), Paragraph(f'<b>{value}</b>', value_s)]

        left_cells = [
            info_cell('CUSTOMER NAME', cust_name),
            info_cell('EMAIL ADDRESS', cust_email),
            info_cell('PHONE NUMBER', cust_phone),
            info_cell('MEMBER SINCE', member_since),
        ]
        right_cells = [
            info_cell('ACCOUNT NUMBER', acct_num),
            info_cell('ACCOUNT TYPE', acct_type),
            info_cell('IFSC CODE', ifsc),
            info_cell('BRANCH', branch),
        ]

        # Build rows: each row has left-label, left-value, spacer, right-label, right-value
        info_rows = []
        for i in range(len(left_cells)):
            info_rows.append([
                left_cells[i][0], left_cells[i][1],
                '', # spacer column
                right_cells[i][0], right_cells[i][1],
            ])
        # Add balance row
        info_rows.append([
            '', '',
            '',
            Paragraph('CURRENT BALANCE', label_s),
            Paragraph(f'<b>{balance}</b>', ParagraphStyle('BalVal', parent=value_s,
                fontSize=11, textColor=colors.HexColor(blue))),
        ])

        half_w = (doc.width - 8*mm) / 2
        info_table = Table(info_rows, colWidths=[half_w*0.35, half_w*0.65, 8*mm, half_w*0.35, half_w*0.65])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            # Left card border
            ('BOX', (0, 0), (1, len(info_rows)-2), 0.5, colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0, 0), (1, len(info_rows)-2), colors.HexColor('#F8FAFC')),
            ('ROUNDEDCORNERS', [4, 4, 4, 4]),
            # Right card border
            ('BOX', (3, 0), (4, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (3, 0), (4, -1), colors.HexColor('#F8FAFC')),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 5*mm))
        elements.append(HRFlowable(width='100%', thickness=0.5,
            color=colors.HexColor('#E2E8F0')))
        elements.append(Spacer(1, 4*mm))

        # -- Transaction Table --
        txn_heading = f'Transaction History  ({len(transactions)} records)'
        if period_label:
            txn_heading = f'Transaction History — {period_label}  ({len(transactions)} records)'
        elements.append(Paragraph(
            txn_heading,
            heading_style,
        ))

        if transactions:
            header = ['#', 'Date', 'Type', 'Counterparty', 'Direction', 'Amount (Rs.)', 'Status']
            table_data = [header]

            for txn in transactions:
                date_str = txn['transaction_date'].strftime('%d %b %Y') if txn['transaction_date'] else '\u2014'
                amt = f"{txn['amount']:,.2f}"
                sign = '\u2212' if txn['direction'] == 'DEBIT' else '+'
                table_data.append([
                    str(txn['row_num']),
                    date_str,
                    txn['transaction_type'] or '\u2014',
                    txn['counterparty'] or '\u2014',
                    txn['direction'] or '\u2014',
                    f"{sign}{amt}",
                    txn['status'] or '\u2014',
                ])

            # Adjusted column widths: #(18) Date(68) Type(58) Counterparty(108) Dir(48) Amount(72) Status(48) = ~420
            page_w = doc.width
            col_widths = [
                page_w * 0.04,   # #
                page_w * 0.14,   # Date
                page_w * 0.12,   # Type
                page_w * 0.28,   # Counterparty (widest)
                page_w * 0.10,   # Direction
                page_w * 0.18,   # Amount
                page_w * 0.14,   # Status
            ]
            t = Table(table_data, colWidths=col_widths, repeatRows=1)

            debit_color = colors.HexColor('#DC2626')
            credit_color = colors.HexColor('#16A34A')
            header_bg = colors.HexColor('#F1F5F9')
            border_color = colors.HexColor('#E2E8F0')
            stripe_color = colors.HexColor('#FAFBFD')

            style_cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), header_bg),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#475569')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 7.5),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),   # # column
                ('ALIGN', (5, 0), (5, -1), 'RIGHT'),     # Amount column
                ('ALIGN', (4, 0), (4, -1), 'CENTER'),    # Direction column
                ('ALIGN', (6, 0), (6, -1), 'CENTER'),    # Status column
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.4, border_color),
                ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#CBD5E1')),
            ]

            # Stripe alternate rows & color amounts
            for i in range(1, len(table_data)):
                if i % 2 == 0:
                    style_cmds.append(('BACKGROUND', (0, i), (-1, i), stripe_color))
                if table_data[i][5].startswith('\u2212'):
                    style_cmds.append(('TEXTCOLOR', (5, i), (5, i), debit_color))
                    style_cmds.append(('FONTNAME', (5, i), (5, i), 'Helvetica-Bold'))
                else:
                    style_cmds.append(('TEXTCOLOR', (5, i), (5, i), credit_color))
                    style_cmds.append(('FONTNAME', (5, i), (5, i), 'Helvetica-Bold'))

            t.setStyle(TableStyle(style_cmds))
            elements.append(t)
        else:
            elements.append(Paragraph('No transactions found.', normal_style))

        # -- Footer --
        elements.append(Spacer(1, 8*mm))
        elements.append(HRFlowable(width='100%', thickness=0.5,
            color=colors.HexColor('#E2E8F0')))
        elements.append(Spacer(1, 2*mm))
        footer_logo = (
            f'<font name="Helvetica-Bold" color="{blue}">Secure</font>'
            f'<font name="Helvetica-Bold" color="{dark}">Bank</font>'
            f'  <font color="#94A3B8">|</font>  '
            f'<font color="#94A3B8">System-generated statement  |  support@securebank.com</font>'
        )
        elements.append(Paragraph(
            footer_logo,
            ParagraphStyle('Footer', parent=small_style, alignment=TA_CENTER, fontSize=7.5),
        ))

        doc.build(elements)
        buffer.seek(0)

        filename = f"SecureBank_Statement_{acct_num}_{datetime.now().strftime('%Y%m%d')}.pdf"

        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )

    except Error as e:
        flash(f'Error generating PDF: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('statement', account_id=account_id))


@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))


# ─────────────────────────────────────────────────────────────────────────────
# JSON API ROUTES  (used by the Android native app)
# ─────────────────────────────────────────────────────────────────────────────

def api_login_required(f):
    """Login decorator for JSON API endpoints — returns 401 JSON instead of redirect."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"status": "error", "message": "Not authenticated"}), 401
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "message": "Database error"}), 500
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT customer_id FROM Customers WHERE customer_id = %s",
                (session['user_id'],),
            )
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            if not user:
                session.clear()
                return jsonify({"status": "error", "message": "Session expired"}), 401
        except Error:
            if conn:
                conn.close()
            return jsonify({"status": "error", "message": "Session error"}), 500
        return f(*args, **kwargs)
    return decorated_function


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.form
    email = data.get('email', '').strip()
    password = data.get('password', '')
    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password are required"}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection error"}), 500
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT customer_id, email, password_hash, full_name FROM Customers WHERE email = %s", (email,))
        user = cursor.fetchone()
        if user and user['password_hash'] and check_password_hash(str(user['password_hash']), str(password)):
            device_info = request.headers.get('User-Agent', 'Android App')
            ip_address = request.remote_addr
            try:
                cursor.execute("INSERT INTO LoginActivity (customer_id, device_info, ip_address) VALUES (%s, %s, %s)", (user['customer_id'], device_info, ip_address))
                conn.commit()
            except Error:
                conn.rollback()
            session.permanent = True
            session['user_id'] = user['customer_id']
            session['user_name'] = user['full_name']
            session['user_email'] = user['email']
            return jsonify({"status": "success", "message": "Login successful", "user_id": user['customer_id'], "user_name": user['full_name'], "user_email": user['email']})
        else:
            return jsonify({"status": "error", "message": "Invalid email or password"}), 401
    except Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.form
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    password = data.get('password', '')
    confirm_password = data.get('confirm_password', '')
    if not all([full_name, email, password, confirm_password]):
        return jsonify({"status": "error", "message": "All required fields must be filled"}), 400
    if password != confirm_password:
        return jsonify({"status": "error", "message": "Passwords do not match"}), 400
    if len(password) < 8:
        return jsonify({"status": "error", "message": "Password must be at least 8 characters"}), 400
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() for c in password)
    if not (has_upper and has_lower and has_digit and has_symbol):
        return jsonify({"status": "error", "message": "Password must include uppercase, lowercase, digit, and symbol"}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection error"}), 500
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT customer_id FROM Customers WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": "An account with this email already exists"}), 409
        password_hash = generate_password_hash(password)
        cursor.execute("INSERT INTO Customers (email, password_hash, full_name, phone) VALUES (%s, %s, %s, %s) RETURNING customer_id", (email, password_hash, full_name, phone or None))
        row = cursor.fetchone()
        customer_id = row['customer_id'] if row else None
        account_number = ''.join(str(random.randint(0, 9)) for _ in range(12))
        ifsc_code = 'SECB0' + f"{random.randint(0, 999999):06d}"
        branches = ['Mumbai Downtown', 'Bangalore MG Road', 'Delhi Connaught Place', 'Chennai Central']
        branch = random.choice(branches)
        cursor.execute("INSERT INTO Accounts (customer_id, account_type, account_number, ifsc_code, branch_name, balance) VALUES (%s, %s, %s, %s, %s, %s)", (customer_id, 'Savings', account_number, ifsc_code, branch, 1000.00))
        conn.commit()
        session.permanent = True
        session['user_id'] = customer_id
        session['user_name'] = full_name
        session['user_email'] = email
        return jsonify({"status": "success", "message": f"Account created! Your account number is {account_number}", "user_id": customer_id, "user_name": full_name, "account_number": account_number}), 201
    except Error as e:
        if conn:
            conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({"status": "success", "message": "Logged out"})


@app.route('/api/dashboard', methods=['GET'])
@api_login_required
def api_dashboard():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database error"}), 500
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT a.account_id, a.account_type, a.balance, a.account_number, a.ifsc_code, a.branch_name, a.created_at, c.full_name, c.email FROM Accounts a INNER JOIN Customers c ON a.customer_id = c.customer_id WHERE c.customer_id = %s ORDER BY a.account_id", (session['user_id'],))
        accounts_raw = cursor.fetchall()
        cursor.execute("SELECT login_timestamp FROM LoginActivity WHERE customer_id = %s ORDER BY login_timestamp DESC LIMIT 1", (session['user_id'],))
        last_login_row = cursor.fetchone()
        last_login = None
        if last_login_row and last_login_row['login_timestamp']:
            ts = last_login_row['login_timestamp']
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            last_login = ts.astimezone(IST).strftime('%d %b %Y at %I:%M %p')
        cursor.close()
        conn.close()
        accounts = [{"account_id": a['account_id'], "account_type": a['account_type'], "balance": float(a['balance']), "account_number": a['account_number'], "ifsc_code": a['ifsc_code'], "branch_name": a['branch_name'], "created_at": str(a['created_at']), "full_name": a['full_name'], "email": a['email']} for a in accounts_raw]
        return jsonify({"status": "success", "user_name": session['user_name'], "last_login": last_login, "accounts": accounts, "total_balance": sum(a['balance'] for a in accounts)})
    except Error as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/profile', methods=['GET'])
@api_login_required
def api_profile():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database error"}), 500
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT customer_id, full_name, email, phone, created_at FROM Customers WHERE customer_id = %s", (session['user_id'],))
        customer_raw = cursor.fetchone()
        cursor.execute("SELECT account_id, account_type, account_number, ifsc_code, branch_name, balance, created_at FROM Accounts WHERE customer_id = %s ORDER BY account_id", (session['user_id'],))
        accounts_raw = cursor.fetchall()
        cursor.close()
        conn.close()
        if not customer_raw:
            return jsonify({"status": "error", "message": "Profile not found"}), 404
        customer = {"customer_id": customer_raw['customer_id'], "full_name": customer_raw['full_name'], "email": customer_raw['email'], "phone": customer_raw['phone'] or '', "created_at": str(customer_raw['created_at'])}
        accounts = [{"account_id": a['account_id'], "account_type": a['account_type'], "account_number": a['account_number'], "ifsc_code": a['ifsc_code'], "branch_name": a['branch_name'], "balance": float(a['balance']), "created_at": str(a['created_at'])} for a in accounts_raw]
        return jsonify({"status": "success", "customer": customer, "accounts": accounts})
    except Error as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/transfer', methods=['GET'])
@api_login_required
def api_transfer_get():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database error"}), 500
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT account_id, account_type, balance, account_number, ifsc_code, branch_name FROM Accounts WHERE customer_id = %s ORDER BY account_id", (session['user_id'],))
        user_accounts_raw = cursor.fetchall()
        cursor.execute("SELECT a.account_id, a.account_number, a.ifsc_code, a.branch_name, c.full_name FROM Accounts a JOIN Customers c ON a.customer_id = c.customer_id WHERE a.customer_id != %s ORDER BY c.full_name", (session['user_id'],))
        other_accounts_raw = cursor.fetchall()
        cursor.close()
        conn.close()
        user_accounts = [{"account_id": a['account_id'], "account_type": a['account_type'], "balance": float(a['balance']), "account_number": a['account_number'], "ifsc_code": a['ifsc_code'], "branch_name": a['branch_name']} for a in user_accounts_raw]
        other_accounts = [{"account_id": a['account_id'], "account_number": a['account_number'], "ifsc_code": a['ifsc_code'], "branch_name": a['branch_name'], "full_name": a['full_name']} for a in other_accounts_raw]
        return jsonify({"status": "success", "user_accounts": user_accounts, "other_accounts": other_accounts})
    except Error as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/transfer', methods=['POST'])
@api_login_required
def api_transfer_post():
    data = request.form
    from_account_id = data.get('from_account')
    to_account_number = data.get('to_account')
    amount_str = data.get('amount')
    beneficiary_name = data.get('beneficiary_name')
    bank_name = data.get('bank_name')
    ifsc = data.get('ifsc')
    category = data.get('category', 'General')
    if not all([from_account_id, to_account_number, amount_str, beneficiary_name, bank_name, ifsc]):
        return jsonify({"status": "error", "message": "All fields are required"}), 400
    try:
        amount = float(amount_str or 0)
        from_account_id = int(from_account_id or 0)
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid amount or account ID"}), 400
    if amount <= 0:
        return jsonify({"status": "error", "message": "Amount must be greater than zero"}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database error"}), 500
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT account_id FROM Accounts WHERE account_number = %s", (to_account_number,))
        to_account = cursor.fetchone()
        if not to_account:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": f"Account number {to_account_number} not found"}), 404
        to_account_id = to_account['account_id']
        if from_account_id == to_account_id:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Source and destination cannot be the same"}), 400
        cursor.close()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM TransferFunds(%s, %s, %s, %s)", (from_account_id, to_account_id, amount, category))
        result = cursor.fetchone()
        status = result[0] if result else None
        message = result[1] if result else None
        if status == 'Success':
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({"status": "success", "message": str(message or 'Transfer completed')})
        else:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": str(message or 'Transfer failed')}), 400
    except Error as e:
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/statement/<int:account_id>', methods=['GET'])
@api_login_required
def api_statement(account_id):
    page = request.args.get('page', 1, type=int)
    if page < 1:
        page = 1
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database error"}), 500
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT customer_id FROM Accounts WHERE account_id = %s", (account_id,))
        acc_check = cursor.fetchone()
        if not acc_check or acc_check['customer_id'] != session['user_id']:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Access denied"}), 403
        cursor.execute("SELECT account_id, account_type, balance, account_number, ifsc_code FROM Accounts WHERE account_id = %s", (account_id,))
        account_raw = cursor.fetchone()
        filter_year = request.args.get('year', type=int)
        filter_month = request.args.get('month', type=int)
        if filter_year and filter_month:
            cursor.execute("SELECT * FROM GetPaginatedStatement(%s, %s, %s)", (account_id, 1, 10000))
            all_txns = cursor.fetchall()
            filtered = [t for t in all_txns if t.get('transaction_date') and t['transaction_date'].year == filter_year and t['transaction_date'].month == filter_month]
            per_page = 10
            total_records = len(filtered)
            total_pages = max(1, -(-total_records // per_page))
            start = (page - 1) * per_page
            txns_raw = filtered[start:start + per_page]
            for i, t in enumerate(txns_raw):
                t['row_num'] = start + i + 1
                t['total_records'] = total_records
                t['total_pages'] = total_pages
        else:
            cursor.execute("SELECT * FROM GetPaginatedStatement(%s, %s, %s)", (account_id, page, 10))
            txns_raw = cursor.fetchall()
        cursor.close()
        conn.close()
        account = {"account_id": account_raw['account_id'], "account_type": account_raw['account_type'], "balance": float(account_raw['balance']), "account_number": account_raw['account_number'], "ifsc_code": account_raw['ifsc_code']} if account_raw else {}
        transactions = []
        total_records = 0
        total_pages = 0
        for t in txns_raw:
            total_records = t.get('total_records', 0)
            total_pages = t.get('total_pages', 0)
            transactions.append({"row_num": t.get('row_num'), "transaction_id": t.get('transaction_id'), "transaction_date": str(t['transaction_date']) if t.get('transaction_date') else None, "transaction_type": t.get('transaction_type'), "counterparty": t.get('counterparty'), "direction": t.get('direction'), "amount": float(t['amount']) if t.get('amount') else 0.0, "status": t.get('status')})
        return jsonify({"status": "success", "account": account, "transactions": transactions, "page": page, "total_pages": total_pages, "total_records": total_records})
    except Error as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/analytics', methods=['GET'])
@api_login_required
def api_analytics():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database error"}), 500
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT account_id FROM Accounts WHERE customer_id = %s", (session['user_id'],))
        user_accounts = [r['account_id'] for r in cursor.fetchall()]
        now = datetime.now()
        sel_year = request.args.get('year', now.year, type=int)
        sel_month = request.args.get('month', now.month, type=int)
        summary_year = request.args.get('summary_year', now.year, type=int)
        if not user_accounts:
            cursor.close()
            conn.close()
            return jsonify({"status": "success", "chart_data": [], "credit_chart_data": [], "monthly_totals": [], "all_time_data": [], "available_months": [], "available_years": [], "sel_year": sel_year, "sel_month": sel_month, "summary_year": summary_year})
        placeholders = ','.join(['%s'] * len(user_accounts))
        cursor.execute(f"SELECT DISTINCT EXTRACT(YEAR FROM transaction_timestamp)::INT AS yr, EXTRACT(MONTH FROM transaction_timestamp)::INT AS mo, TO_CHAR(transaction_timestamp, 'Mon YYYY') AS label FROM TransactionHistory WHERE (from_account_id IN ({placeholders}) OR to_account_id IN ({placeholders})) AND status = 'Success' ORDER BY yr DESC, mo DESC", tuple(user_accounts) * 2)
        available_months = [dict(r) for r in cursor.fetchall()]
        cursor.execute(f"SELECT DISTINCT EXTRACT(YEAR FROM transaction_timestamp)::INT AS yr FROM TransactionHistory WHERE (from_account_id IN ({placeholders}) OR to_account_id IN ({placeholders})) AND status = 'Success' ORDER BY yr DESC", tuple(user_accounts) * 2)
        available_years = [r['yr'] for r in cursor.fetchall()]
        cursor.execute(f"SELECT COALESCE(category, 'General') AS category, SUM(amount) AS total, COUNT(*) AS txn_count FROM TransactionHistory WHERE from_account_id IN ({placeholders}) AND status = 'Success' AND EXTRACT(YEAR FROM transaction_timestamp) = %s AND EXTRACT(MONTH FROM transaction_timestamp) = %s GROUP BY COALESCE(category, 'General') ORDER BY total DESC", tuple(user_accounts) + (sel_year, sel_month))
        chart_data = [{"category": r['category'], "total": float(r['total']), "txn_count": r['txn_count']} for r in cursor.fetchall()]
        cursor.execute(f"SELECT COALESCE(category, 'General') AS category, SUM(amount) AS total, COUNT(*) AS txn_count FROM TransactionHistory WHERE to_account_id IN ({placeholders}) AND status = 'Success' AND EXTRACT(YEAR FROM transaction_timestamp) = %s AND EXTRACT(MONTH FROM transaction_timestamp) = %s GROUP BY COALESCE(category, 'General') ORDER BY total DESC", tuple(user_accounts) + (sel_year, sel_month))
        credit_chart_data = [{"category": r['category'], "total": float(r['total']), "txn_count": r['txn_count']} for r in cursor.fetchall()]
        cursor.execute(f"SELECT TO_CHAR(transaction_timestamp, 'Mon YYYY') AS month_label, SUM(CASE WHEN from_account_id IN ({placeholders}) THEN amount ELSE 0 END) AS total_debit, SUM(CASE WHEN to_account_id IN ({placeholders}) THEN amount ELSE 0 END) AS total_credit FROM TransactionHistory WHERE (from_account_id IN ({placeholders}) OR to_account_id IN ({placeholders})) AND status = 'Success' AND EXTRACT(YEAR FROM transaction_timestamp) = %s GROUP BY TO_CHAR(transaction_timestamp, 'Mon YYYY'), DATE_TRUNC('month', transaction_timestamp) ORDER BY DATE_TRUNC('month', transaction_timestamp) DESC", tuple(user_accounts) * 4 + (summary_year,))
        monthly_totals = [{"month_label": r['month_label'], "total_debit": float(r['total_debit']), "total_credit": float(r['total_credit'])} for r in cursor.fetchall()]
        cursor.execute(f"SELECT COALESCE(category, 'General') AS category, SUM(amount) AS total, COUNT(*) AS txn_count FROM TransactionHistory WHERE (from_account_id IN ({placeholders}) OR to_account_id IN ({placeholders})) AND status = 'Success' GROUP BY COALESCE(category, 'General') ORDER BY total DESC", tuple(user_accounts) * 2)
        all_time_data = [{"category": r['category'], "total": float(r['total']), "txn_count": r['txn_count']} for r in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "chart_data": chart_data, "credit_chart_data": credit_chart_data, "monthly_totals": monthly_totals, "all_time_data": all_time_data, "available_months": available_months, "available_years": available_years, "sel_year": sel_year, "sel_month": sel_month, "summary_year": summary_year})
    except Error as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

