"""
Centralized configuration for SecureBank.
All database credentials and app settings in one place.
"""

import os

# Database Configuration (PostgreSQL)
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '1234'),
    'database': os.environ.get('DB_NAME', 'securebank'),
    'port': int(os.environ.get('DB_PORT', 5432))
}

# Flask secret key — use env var in production, fallback for dev
SECRET_KEY = os.environ.get('SECRET_KEY', 'securebank-dev-secret-key-change-in-production')
