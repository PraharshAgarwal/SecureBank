"""
Centralized configuration for SecureBank.
All database credentials and app settings in one place.
"""

import os

# Database Configuration (PostgreSQL — Supabase Cloud, Mumbai ap-south-1)
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'aws-1-ap-south-1.pooler.supabase.com'),
    'user': os.environ.get('DB_USER', 'postgres.zzigmvwzdfcwcpjnvruu'),
    'password': os.environ.get('DB_PASSWORD', 'Prah_securebank'),
    'database': os.environ.get('DB_NAME', 'securebank'),
    'port': int(os.environ.get('DB_PORT', 5432))
}

# Flask secret key — use env var in production, fallback for dev
SECRET_KEY = os.environ.get('SECRET_KEY', 'securebank-dev-secret-key-change-in-production')
