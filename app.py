"""
SecureBank - Flask Web Application
BCSE302L Database Management Systems Project
Demonstrates: JOIN operations, ACID transactions, Stored Functions, Indexing, Triggers
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import psycopg2
from psycopg2 import Error
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import random
import uuid
from datetime import datetime, timedelta
from config import DB_CONFIG, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(minutes=30)

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
                    last_login = activity["login_timestamp"]
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
            
            if user and check_password_hash(user['password_hash'], password):
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
            customer_id = cursor.fetchone()['customer_id']

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
            last_login = last_login_data['login_timestamp'].strftime('%d %b %Y at %I:%M %p')
        
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
            
            # Validation
            if not all([from_account_id, to_account_number, amount, beneficiary_name, bank_name, ifsc]):
                flash('All fields are required.', 'error')
                return render_template('transfer.html', accounts=user_accounts, other_accounts=other_accounts)
            
            try:
                amount = float(amount)
                from_account_id = int(from_account_id)
                
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
                    "SELECT * FROM TransferFunds(%s, %s, %s)",
                    (from_account_id, to_account_id, amount)
                )
                result = cursor.fetchone()
                
                # Get output parameters
                status = result[0]  # p_status
                message = result[1]  # p_message
                
                if status == 'Success':
                    conn.commit()  # Commit the transaction
                    flash(message, 'success')
                else:
                    conn.rollback()  # Rollback on failure
                    flash(message, 'error')
                
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


@app.route('/history/<int:account_id>')
@login_required
def history(account_id):
    """
    Transaction History Page - Demonstrates: Indexing (B-tree on timestamp)
    Fast retrieval using indexed timestamp column
    """
    conn = get_db_connection()
    if not conn:
        flash('Database connection error.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        # Verify account belongs to user
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        verify_query = "SELECT customer_id FROM Accounts WHERE account_id = %s"
        cursor.execute(verify_query, (account_id,))
        account = cursor.fetchone()
        
        if not account or account['customer_id'] != session['user_id']:
            flash('Access denied. Account not found.', 'error')
            cursor.close()
            conn.close()
            return redirect(url_for('dashboard'))
        
        # Get account details
        account_query = """
            SELECT account_id, account_type, balance, account_number
            FROM Accounts
            WHERE account_id = %s
        """
        cursor.execute(account_query, (account_id,))
        account_info = cursor.fetchone()
        
        # Get transaction history (uses indexed timestamp for fast retrieval)
        history_query = """
            SELECT 
                transaction_id,
                from_account_id,
                to_account_id,
                transaction_type,
                amount,
                status,
                transaction_timestamp
            FROM TransactionHistory
            WHERE from_account_id = %s OR to_account_id = %s
            ORDER BY transaction_timestamp DESC
            LIMIT 50
        """
        cursor.execute(history_query, (account_id, account_id))
        transactions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('history.html', 
                             account=account_info,
                             transactions=transactions)
    except Error as e:
        flash(f'Error loading history: {str(e)}', 'error')
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

        # Call cursor-based stored function
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
        )
    except Error as e:
        flash(f'Error loading statement: {str(e)}', 'error')
        if conn:
            conn.close()
        return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
