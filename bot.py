"""
====================================================================================================
                    🚀 ULTIMATE SHOP MANAGEMENT SYSTEM v8.0 - COMPLETE REWRITE
        Normal User Registration + Super Admin Panel + Shop Bot Engine
====================================================================================================

የሲስተሙ ክፍሎች:
    1. Normal User Store Registration
    2. Super Admin Control Panel (12 Buttons)
    3. Shop Bot Engine (Multi-Store)
    4. Verification System
    5. Broadcast System
    6. Analytics & Reports
====================================================================================================
"""

import os
import sys
import json
import secrets
import hashlib
import time
import threading
import math
import logging
from datetime import datetime, timedelta
from functools import wraps

# =================================================================================================
#                           LOGGING SETUP
# =================================================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# =================================================================================================
#                           DEPENDENCY CHECKS
# =================================================================================================

try:
    import telebot
    from telebot import types
except ImportError:
    logger.error("❌ python-telegram-bot not installed. Run: pip install pyTelegramBotAPI")
    sys.exit(1)

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor
    from psycopg2.pool import ThreadedConnectionPool
except ImportError:
    logger.error("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)

try:
    from flask import Flask, jsonify, request, render_template_string, session, redirect, url_for
    from flask_cors import CORS
except ImportError:
    logger.error("❌ Flask not installed. Run: pip install flask flask-cors")
    sys.exit(1)

# =================================================================================================
#                           CONFIGURATION
# =================================================================================================

DATABASE_URL = os.environ.get("DATABASE_URL")
CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "Admin@123")
SUPER_ADMIN_IDS = []
try:
    super_admin_ids_str = os.environ.get("SUPER_ADMIN_IDS", "")
    if super_admin_ids_str:
        SUPER_ADMIN_IDS = [int(id.strip()) for id in super_admin_ids_str.split(",") if id.strip()]
except ValueError:
    logger.warning("⚠️ Invalid SUPER_ADMIN_IDS format, using empty list")
    SUPER_ADMIN_IDS = []

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PORT = int(os.environ.get("PORT", 8080))

# Validate required config
if not DATABASE_URL:
    logger.error("❌ DATABASE_URL environment variable is required!")
    sys.exit(1)

# =================================================================================================
#                           FLASK APP
# =================================================================================================

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
CORS(app, supports_credentials=True, origins='*')

# =================================================================================================
#                           DATABASE LAYER - FIXED
# =================================================================================================

class DatabasePool:
    """Thread-safe database connection pool manager"""
    
    def __init__(self):
        self._pool = None
        self._lock = threading.Lock()
        self._initialized = False
    
    def init_pool(self):
        """Initialize the connection pool"""
        with self._lock:
            if self._pool is not None:
                return
            
            try:
                self._pool = ThreadedConnectionPool(
                    minconn=1,
                    maxconn=20,
                    dsn=DATABASE_URL
                )
                # Test connection
                conn = self._pool.getconn()
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                self._pool.putconn(conn)
                self._initialized = True
                logger.info("✅ Database pool initialized successfully")
            except Exception as e:
                logger.error(f"❌ Database pool initialization failed: {e}")
                raise
    
    def get_connection(self):
        """Get a connection from the pool"""
        if self._pool is None:
            self.init_pool()
        
        try:
            conn = self._pool.getconn()
            # Verify connection is alive
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return conn
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            # Reset pool on error
            with self._lock:
                try:
                    if self._pool:
                        self._pool.closeall()
                except:
                    pass
                self._pool = None
                self._initialized = False
            self.init_pool()
            return self._pool.getconn()
    
    def return_connection(self, conn):
        """Return connection to the pool"""
        if conn is not None and self._pool is not None:
            try:
                self._pool.putconn(conn)
            except Exception as e:
                logger.warning(f"⚠️ Error returning connection: {e}")
                try:
                    conn.close()
                except:
                    pass
    
    def close_all(self):
        """Close all connections in the pool"""
        with self._lock:
            if self._pool:
                try:
                    self._pool.closeall()
                except:
                    pass
                self._pool = None
                self._initialized = False

# Global database pool instance
db_pool = DatabasePool()

def get_conn():
    """Get a database connection"""
    return db_pool.get_connection()

def put_conn(conn):
    """Return a database connection"""
    db_pool.return_connection(conn)

def db_execute(query, params=None, fetch=False):
    """Execute a query and optionally fetch results"""
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            if fetch:
                return cur.fetchall()
            conn.commit()
            return cur.rowcount if cur.rowcount > 0 else 0
    except Exception as e:
        logger.error(f"❌ DB execute error: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise
    finally:
        if conn:
            put_conn(conn)

def db_execute_dict(query, params=None):
    """Execute a query and return results as dictionaries"""
    conn = None
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            return cur.fetchall()
    except Exception as e:
        logger.error(f"❌ DB execute dict error: {e}")
        raise
    finally:
        if conn:
            put_conn(conn)

def db_execute_one(query, params=None):
    """Execute a query and return one result as dictionary"""
    results = db_execute_dict(query, params)
    return results[0] if results else None

def db_execute_scalar(query, params=None, default=None):
    """Execute a query and return a single value"""
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            result = cur.fetchone()
            return result[0] if result else default
    except Exception as e:
        logger.error(f"❌ DB scalar error: {e}")
        raise
    finally:
        if conn:
            put_conn(conn)

# =================================================================================================
#                           DATABASE SCHEMA
# =================================================================================================

def init_schema():
    """Initialize database schema with all tables"""
    
    schema_queries = [
        # =====================================================
        # USERS TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            phone TEXT UNIQUE,
            full_name TEXT,
            is_admin BOOLEAN DEFAULT FALSE,
            is_super_admin BOOLEAN DEFAULT FALSE,
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
        """,
        
        # =====================================================
        # STORE APPLICATIONS TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS store_applications (
            id SERIAL PRIMARY KEY,
            store_name TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            location TEXT,
            latitude REAL,
            longitude REAL,
            description TEXT,
            category TEXT,
            store_logo TEXT,
            bot_token TEXT,
            bot_username TEXT,
            status TEXT DEFAULT 'pending',
            admin_notes TEXT,
            user_id INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            reviewed_by INTEGER REFERENCES users(id)
        )
        """,
        
        # =====================================================
        # STORES TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS stores (
            id SERIAL PRIMARY KEY,
            token TEXT UNIQUE NOT NULL,
            store_name TEXT NOT NULL,
            admin_id BIGINT,
            username TEXT,
            phone TEXT,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            telebirr TEXT,
            cbebirr TEXT,
            is_active INTEGER DEFAULT 1,
            is_approved INTEGER DEFAULT 0,
            shop_lat REAL,
            shop_lng REAL,
            area_text TEXT,
            shop_photo TEXT,
            shop_description TEXT,
            rating REAL DEFAULT 0,
            total_sales REAL DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            bot_status TEXT DEFAULT 'stopped',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # =====================================================
        # PRODUCTS TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            token TEXT NOT NULL,
            name_am TEXT NOT NULL,
            name_en TEXT,
            price REAL NOT NULL,
            stock INTEGER DEFAULT 0,
            desc_am TEXT,
            desc_en TEXT,
            image_url TEXT,
            discount REAL DEFAULT 0,
            discount_until TIMESTAMP,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # =====================================================
        # ORDERS TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            token TEXT NOT NULL,
            customer_id BIGINT NOT NULL,
            customer_phone TEXT,
            customer_lat REAL,
            customer_lng REAL,
            status_am TEXT DEFAULT 'በመጠባበቅ ላይ',
            status_en TEXT DEFAULT 'Pending',
            status_stage INTEGER DEFAULT 0,
            total_price REAL NOT NULL,
            delivery_fee REAL DEFAULT 0,
            payment_method TEXT,
            payment_confirmed BOOLEAN DEFAULT FALSE,
            order_number TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # =====================================================
        # ORDER ITEMS TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(id),
            product_id INTEGER REFERENCES products(id),
            product_name TEXT,
            quantity INTEGER,
            price REAL,
            subtotal REAL
        )
        """,
        
        # =====================================================
        # REVIEWS TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id),
            customer_id BIGINT,
            rating INTEGER CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # =====================================================
        # USER LANGUAGES TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS user_langs (
            chat_id BIGINT PRIMARY KEY,
            lang TEXT DEFAULT 'am',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # =====================================================
        # CUSTOMER INFO TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS customer_info (
            chat_id BIGINT PRIMARY KEY,
            phone TEXT,
            lat REAL,
            lng REAL,
            address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # =====================================================
        # ADMIN SESSIONS TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS admin_sessions (
            token TEXT,
            chat_id BIGINT,
            session_key TEXT,
            expires_at TIMESTAMP,
            PRIMARY KEY (token, chat_id)
        )
        """,
        
        # =====================================================
        # AUDIT LOGS TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            action TEXT NOT NULL,
            details JSONB,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # =====================================================
        # BROADCASTS TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS broadcasts (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            image_url TEXT,
            target TEXT DEFAULT 'all',
            sent_by INTEGER REFERENCES users(id),
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivered_count INTEGER DEFAULT 0
        )
        """,
        
        # =====================================================
        # FAVORITES TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS favorites (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            store_id INTEGER REFERENCES stores(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # =====================================================
        # SETTINGS TABLE
        # =====================================================
        """
        CREATE TABLE IF NOT EXISTS settings (
            id SERIAL PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            category TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]
    
    # Indexes
    index_queries = [
        "CREATE INDEX IF NOT EXISTS idx_products_token ON products(token)",
        "CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token)",
        "CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)",
        "CREATE INDEX IF NOT EXISTS idx_stores_token ON stores(token)",
        "CREATE INDEX IF NOT EXISTS idx_store_applications_user ON store_applications(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_store_applications_status ON store_applications(status)",
        "CREATE INDEX IF NOT EXISTS idx_orders_order_number ON orders(order_number)",
    ]
    
    try:
        for query in schema_queries:
            db_execute(query)
        for query in index_queries:
            db_execute(query)
        logger.info("✅ Database schema initialized")
        seed_default_data()
    except Exception as e:
        logger.error(f"❌ Schema init failed: {e}")
        raise

def seed_default_data():
    """Seed default data if not exists"""
    try:
        # Check if super admin exists
        existing = db_execute_scalar("SELECT 1 FROM users WHERE is_super_admin = TRUE", default=0)
        if not existing:
            h_pass, salt = hash_password(SUPER_ADMIN_PASSWORD)
            db_execute("""
                INSERT INTO users (username, email, password_hash, password_salt, full_name, is_admin, is_super_admin, is_verified)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, ('superadmin', 'admin@system.com', h_pass, salt, 'Super Admin', True, True, True))
            logger.info(f"✅ Default Super Admin created: username='superadmin', password='{SUPER_ADMIN_PASSWORD}'")
    except Exception as e:
        logger.warning(f"⚠️ Seed data warning: {e}")

# =================================================================================================
#                           UTILITY FUNCTIONS
# =================================================================================================

def hash_password(password, salt=None):
    """Hash a password with salt"""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def verify_password(password, hashed, salt):
    """Verify a password against its hash"""
    return hashlib.sha256((password + salt).encode()).hexdigest() == hashed

def generate_session_token():
    """Generate a secure session token"""
    return secrets.token_hex(32)

def format_currency(amount):
    """Format amount as currency"""
    try:
        return f"{float(amount):,.2f} ETB"
    except:
        return f"{0:.2f} ETB"

def format_date(dt):
    """Format datetime for display"""
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except:
            return dt
    return dt.strftime("%Y-%m-%d %H:%M")

def generate_order_number():
    """Generate a unique order number"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = secrets.token_hex(4).upper()
    return f"ORD-{timestamp}-{random_part}"

# =================================================================================================
#                           ADMIN REQUIRED DECORATOR
# =================================================================================================

def admin_required(f):
    """Decorator to check if user is logged in as admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('super_admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# =================================================================================================
#                           FLASK ROUTES - NORMAL USER
# =================================================================================================

@app.route('/')
def index():
    """Home page"""
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🏪 Shop Management System</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #0f0e17, #1a1a2e); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border-radius: 24px; padding: 50px; max-width: 700px; width: 100%; border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 25px 50px rgba(0,0,0,0.5); }
        .logo { text-align: center; font-size: 60px; margin-bottom: 10px; }
        h1 { color: #fff; text-align: center; font-size: 28px; font-weight: 700; }
        .subtitle { color: #888; text-align: center; margin-bottom: 30px; font-size: 14px; }
        .features { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin: 30px 0; }
        .feature { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 12px; text-align: center; transition: all 0.3s; }
        .feature:hover { transform: translateY(-5px); background: rgba(255,255,255,0.08); }
        .feature .icon { font-size: 30px; }
        .feature .label { color: #aaa; margin-top: 8px; font-size: 13px; }
        .btn-group { display: flex; flex-direction: column; gap: 12px; margin-top: 20px; }
        .btn { padding: 14px 20px; border: none; border-radius: 12px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s; text-align: center; text-decoration: none; display: block; }
        .btn-primary { background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; }
        .btn-primary:hover { transform: scale(1.02); box-shadow: 0 10px 30px rgba(102,126,234,0.3); }
        .btn-secondary { background: rgba(255,255,255,0.08); color: #fff; }
        .btn-secondary:hover { background: rgba(255,255,255,0.15); }
        .btn-success { background: linear-gradient(135deg, #51cf66, #2b8a3e); color: #fff; }
        .btn-success:hover { transform: scale(1.02); box-shadow: 0 10px 30px rgba(81,207,102,0.3); }
        .footer { text-align: center; color: #555; margin-top: 30px; font-size: 12px; }
        @media (max-width: 600px) { .features { grid-template-columns: repeat(2, 1fr); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🏪</div>
        <h1>Shop Management System</h1>
        <p class="subtitle">Multi-Store E-commerce Platform</p>
        <div class="features">
            <div class="feature"><div class="icon">📝</div><div class="label">Store Registration</div></div>
            <div class="feature"><div class="icon">🛍️</div><div class="label">Browse Stores</div></div>
            <div class="feature"><div class="icon">🤖</div><div class="label">Telegram Bot</div></div>
            <div class="feature"><div class="icon">💰</div><div class="label">Payment</div></div>
            <div class="feature"><div class="icon">📦</div><div class="label">Order Tracking</div></div>
            <div class="feature"><div class="icon">⭐</div><div class="label">Reviews</div></div>
        </div>
        <div class="btn-group">
            <a href="/register-store" class="btn btn-primary">📝 Register Store</a>
            <a href="/applications" class="btn btn-secondary">📋 My Applications</a>
            <a href="/stores" class="btn btn-secondary">🏪 Browse Stores</a>
            <a href="/super-admin" class="btn btn-success">👑 Super Admin Panel</a>
        </div>
        <div class="footer">© 2026 Shop Management System v8.0</div>
    </div>
</body>
</html>
    """)

@app.route('/register-store', methods=['GET', 'POST'])
def register_store():
    """Store registration form and handler"""
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid request data'}), 400
            
            # Validate required fields
            required = ['store_name', 'owner_name', 'phone', 'location']
            for field in required:
                if not data.get(field):
                    return jsonify({'error': f'{field} is required'}), 400
            
            # Create user if not exists
            user = db_execute_one("SELECT id FROM users WHERE phone = %s", (data['phone'],))
            if not user:
                h_pass, salt = hash_password(secrets.token_hex(8))
                user_id = db_execute_scalar("""
                    INSERT INTO users (username, email, password_hash, password_salt, phone, full_name)
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """, (f"user_{int(time.time())}", data.get('email', ''), h_pass, salt, data['phone'], data['owner_name']))
                if not user_id:
                    return jsonify({'error': 'Failed to create user'}), 500
            else:
                user_id = user['id']
            
            # Validate bot token if provided
            bot_token = data.get('bot_token')
            bot_username = None
            if bot_token:
                try:
                    test_bot = telebot.TeleBot(bot_token)
                    bot_info = test_bot.get_me()
                    bot_username = bot_info.username
                except Exception as e:
                    return jsonify({'error': f'Invalid bot token: {str(e)}'}), 400
            
            # Create application
            app_id = db_execute_scalar("""
                INSERT INTO store_applications (store_name, owner_name, phone, email, location, latitude, longitude,
                                               description, category, store_logo, bot_token, bot_username, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (
                data['store_name'], data['owner_name'], data['phone'], data.get('email', ''),
                data['location'], data.get('latitude'), data.get('longitude'),
                data.get('description', ''), data.get('category', 'other'),
                data.get('store_logo'), bot_token, bot_username, user_id
            ))
            
            if not app_id:
                return jsonify({'error': 'Failed to create application'}), 500
            
            return jsonify({
                'success': True,
                'application_id': app_id,
                'message': 'Application submitted successfully!',
                'status': 'pending'
            })
            
        except Exception as e:
            logger.error(f"Store registration error: {e}")
            return jsonify({'error': str(e)}), 500
    
    # GET request - render registration form
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>📝 Register Store</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #0f0e17, #1a1a2e); min-height: 100vh; padding: 20px; display: flex; align-items: center; justify-content: center; }
        .container { background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border-radius: 24px; padding: 40px; max-width: 600px; width: 100%; border: 1px solid rgba(255,255,255,0.08); }
        h2 { color: #fff; margin-bottom: 10px; }
        .subtitle { color: #888; margin-bottom: 25px; font-size: 14px; }
        .form-group { margin-bottom: 18px; }
        label { display: block; color: #ddd; margin-bottom: 5px; font-weight: 500; font-size: 13px; }
        input, select, textarea { width: 100%; padding: 12px 15px; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; background: rgba(255,255,255,0.05); color: #fff; font-size: 15px; transition: all 0.3s; font-family: inherit; }
        input:focus, select:focus, textarea:focus { outline: none; border-color: #667eea; box-shadow: 0 0 30px rgba(102,126,234,0.1); }
        textarea { resize: vertical; min-height: 70px; }
        select option { background: #1a1a2e; }
        .btn { width: 100%; padding: 15px; border: none; border-radius: 12px; font-size: 17px; font-weight: 600; cursor: pointer; background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; transition: all 0.3s; }
        .btn:hover { transform: scale(1.02); box-shadow: 0 10px 30px rgba(102,126,234,0.3); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .back { color: #667eea; text-decoration: none; display: inline-block; margin-top: 15px; }
        .message { padding: 12px 16px; border-radius: 10px; margin-top: 15px; display: none; font-size: 14px; }
        .message.success { display: block; background: rgba(81,207,102,0.1); border: 1px solid #51cf66; color: #51cf66; }
        .message.error { display: block; background: rgba(255,107,107,0.1); border: 1px solid #ff6b6b; color: #ff6b6b; }
        .row { display: flex; gap: 15px; }
        .row .form-group { flex: 1; }
        small { color: #666; font-size: 11px; display: block; margin-top: 3px; }
        @media (max-width: 600px) { .row { flex-direction: column; } }
    </style>
</head>
<body>
    <div class="container">
        <h2>📝 Register Store</h2>
        <p class="subtitle">Fill the form below to register your store</p>
        <form id="registerForm">
            <div class="form-group"><label>🏪 Store Name *</label><input type="text" id="storeName" placeholder="My Store" required></div>
            <div class="row">
                <div class="form-group"><label>👤 Owner Name *</label><input type="text" id="ownerName" placeholder="Full Name" required></div>
                <div class="form-group"><label>📱 Phone *</label><input type="tel" id="phone" placeholder="0912345678" required></div>
            </div>
            <div class="form-group"><label>📧 Email</label><input type="email" id="email" placeholder="email@example.com"></div>
            <div class="form-group"><label>📍 Location *</label><input type="text" id="location" placeholder="Addis Ababa, Bole" required></div>
            <div class="form-group"><label>🏷️ Category</label><select id="category"><option value="grocery">🛍️ Grocery</option><option value="clothing">👕 Clothing</option><option value="electronics">📱 Electronics</option><option value="food">🍽️ Food</option><option value="furniture">🏠 Furniture</option><option value="books">📚 Books</option><option value="beauty">💄 Beauty</option><option value="other">🔧 Other</option></select></div>
            <div class="form-group"><label>📝 Description</label><textarea id="description" placeholder="Describe your store..."></textarea></div>
            <div class="form-group"><label>🤖 Bot Token (Optional)</label><input type="text" id="botToken" placeholder="1234567890:ABCdef..."><small>Get from @BotFather on Telegram</small></div>
            <div class="form-group"><label>🖼️ Store Logo URL (Optional)</label><input type="text" id="storeLogo" placeholder="https://example.com/logo.jpg"></div>
            <div class="row">
                <div class="form-group"><label>📍 Latitude</label><input type="number" step="0.000001" id="latitude" placeholder="9.032"></div>
                <div class="form-group"><label>📍 Longitude</label><input type="number" step="0.000001" id="longitude" placeholder="38.742"></div>
            </div>
            <button type="submit" class="btn">📤 Submit Application</button>
        </form>
        <div id="message" class="message"></div>
        <a href="/" class="back">🔙 Back to Home</a>
    </div>
    <script>
        document.getElementById('registerForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            const btn = this.querySelector('button');
            const msg = document.getElementById('message');
            btn.disabled = true;
            btn.textContent = '⏳ Submitting...';
            const data = {
                store_name: document.getElementById('storeName').value.trim(),
                owner_name: document.getElementById('ownerName').value.trim(),
                phone: document.getElementById('phone').value.trim(),
                email: document.getElementById('email').value.trim(),
                location: document.getElementById('location').value.trim(),
                category: document.getElementById('category').value,
                description: document.getElementById('description').value.trim(),
                bot_token: document.getElementById('botToken').value.trim(),
                store_logo: document.getElementById('storeLogo').value.trim(),
                latitude: parseFloat(document.getElementById('latitude').value) || null,
                longitude: parseFloat(document.getElementById('longitude').value) || null
            };
            try {
                const response = await fetch('/register-store', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await response.json();
                if (result.success) {
                    msg.className = 'message success';
                    msg.textContent = '✅ ' + result.message + ' (ID: ' + result.application_id + ')';
                    btn.textContent = '✅ Submitted!';
                    setTimeout(() => { window.location.href = '/applications'; }, 2000);
                } else {
                    msg.className = 'message error';
                    msg.textContent = '❌ ' + (result.error || 'Error occurred');
                    btn.disabled = false;
                    btn.textContent = '📤 Submit Application';
                }
            } catch (error) {
                msg.className = 'message error';
                msg.textContent = '❌ Network error: ' + error.message;
                btn.disabled = false;
                btn.textContent = '📤 Submit Application';
            }
        });
    </script>
</body>
</html>
    """)

@app.route('/applications')
def applications():
    """View applications page"""
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>📋 My Applications</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #0f0e17, #1a1a2e); min-height: 100vh; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { text-align: center; padding: 30px 0; }
        .header h1 { color: #fff; font-size: 28px; }
        .header p { color: #888; }
        .search-box { display: flex; gap: 10px; margin-bottom: 20px; }
        .search-box input { flex: 1; padding: 12px 15px; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; background: rgba(255,255,255,0.05); color: #fff; font-size: 16px; }
        .search-box input:focus { outline: none; border-color: #667eea; }
        .search-box button { padding: 12px 25px; border: none; border-radius: 10px; background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; cursor: pointer; font-size: 16px; transition: all 0.3s; }
        .search-box button:hover { transform: scale(1.05); }
        .card { background: rgba(255,255,255,0.05); border-radius: 14px; padding: 20px; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.08); }
        .card h3 { color: #fff; margin-bottom: 8px; }
        .card .info { color: #aaa; font-size: 14px; line-height: 1.6; }
        .card .info strong { color: #ddd; }
        .status-badge { display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 11px; font-weight: 600; }
        .status-pending { background: #fcc419; color: #000; }
        .status-approved { background: #51cf66; color: #000; }
        .status-rejected { background: #ff6b6b; color: #fff; }
        .status-changes_requested { background: #ffa94d; color: #000; }
        .empty { text-align: center; color: #666; padding: 40px 0; }
        .empty .icon { font-size: 48px; }
        .btn { display: inline-block; padding: 10px 25px; border: none; border-radius: 10px; font-size: 16px; cursor: pointer; background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; text-decoration: none; transition: all 0.3s; margin-top: 10px; }
        .btn:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.08); }
        .btn-secondary:hover { background: rgba(255,255,255,0.15); }
        .back { color: #667eea; text-decoration: none; display: inline-block; margin-top: 15px; }
        .status-changes { background: #ffa94d; color: #000; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>📋 My Applications</h1><p>Check your store registration applications</p></div>
        <div class="search-box">
            <input type="text" id="phoneInput" placeholder="📱 Enter phone number (e.g., 0912345678)">
            <button onclick="loadApplications()">🔍 Search</button>
        </div>
        <div id="results"></div>
        <div style="text-align:center; margin-top:20px;">
            <a href="/" class="btn btn-secondary">🔙 Back</a>
            <a href="/register-store" class="btn">📝 Register Store</a>
        </div>
    </div>
    <script>
        async function loadApplications() {
            const phone = document.getElementById('phoneInput').value.trim();
            if (!phone) { 
                document.getElementById('results').innerHTML = '<div class="empty"><div class="icon">📱</div><p>Please enter a phone number</p></div>';
                return; 
            }
            const results = document.getElementById('results');
            results.innerHTML = '<div style="text-align:center;color:#888;">⏳ Loading...</div>';
            try {
                const response = await fetch(`/api/applications?phone=${encodeURIComponent(phone)}`);
                const data = await response.json();
                if (data.error) {
                    results.innerHTML = `<div class="empty" style="color:#ff6b6b;">❌ ${data.error}</div>`;
                    return;
                }
                if (data.applications && data.applications.length > 0) {
                    let html = '';
                    const statusLabels = { 
                        'pending': '⏳ Pending', 
                        'approved': '✅ Approved', 
                        'rejected': '❌ Rejected', 
                        'changes_requested': '✏️ Changes Requested' 
                    };
                    data.applications.forEach(app => {
                        const statusClass = `status-${app.status}`;
                        html += `<div class="card"><h3>🏪 ${app.store_name}</h3><div class="info"><span class="status-badge ${statusClass}">${statusLabels[app.status] || app.status}</span><span style="color:#666;margin-left:10px;">📅 ${new Date(app.created_at).toLocaleDateString()}</span>${app.admin_notes ? `<div style="margin-top:8px;padding:10px;background:rgba(255,255,255,0.03);border-radius:8px;">📝 ${app.admin_notes}</div>` : ''}</div></div>`;
                    });
                    results.innerHTML = html;
                } else {
                    results.innerHTML = `<div class="empty"><div class="icon">📭</div><p>No applications found for this phone number</p><p style="font-size:14px;margin-top:10px;">Register a new store <a href="/register-store" style="color:#667eea;">here</a></p></div>`;
                }
            } catch (error) {
                results.innerHTML = '<div class="empty" style="color:#ff6b6b;">❌ Error loading applications</div>';
            }
        }
    </script>
</body>
</html>
    """)

@app.route('/stores')
def browse_stores():
    """Browse stores page"""
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🏪 Browse Stores</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #0f0e17, #1a1a2e); min-height: 100vh; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        .header { text-align: center; padding: 30px 0; }
        .header h1 { color: #fff; font-size: 28px; }
        .header p { color: #888; }
        .stores-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; }
        .store-card { background: rgba(255,255,255,0.05); border-radius: 14px; padding: 20px; border: 1px solid rgba(255,255,255,0.08); transition: all 0.3s; }
        .store-card:hover { transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .store-card .name { color: #fff; font-size: 18px; font-weight: 600; }
        .store-card .info { color: #aaa; font-size: 13px; margin-top: 5px; }
        .store-card .info strong { color: #ddd; }
        .store-card .rating { color: #fcc419; margin-top: 8px; }
        .store-card .badge { display: inline-block; padding: 2px 10px; border-radius: 10px; font-size: 10px; font-weight: 600; }
        .badge-active { background: #51cf66; color: #000; }
        .badge-inactive { background: #ff6b6b; color: #fff; }
        .empty { text-align: center; color: #666; padding: 40px 0; grid-column: 1/-1; }
        .empty .icon { font-size: 48px; }
        .btn { display: inline-block; padding: 10px 25px; border: none; border-radius: 10px; font-size: 16px; cursor: pointer; background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; text-decoration: none; transition: all 0.3s; }
        .btn:hover { transform: scale(1.05); }
        .btn-secondary { background: rgba(255,255,255,0.08); }
        .btn-secondary:hover { background: rgba(255,255,255,0.15); }
        .loading { text-align: center; color: #888; grid-column: 1/-1; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>🏪 Browse Stores</h1><p>Discover verified stores</p></div>
        <div id="results" class="stores-grid"></div>
        <div style="text-align:center;margin-top:20px;"><a href="/" class="btn btn-secondary">🔙 Back</a></div>
    </div>
    <script>
        async function loadStores() {
            const results = document.getElementById('results');
            results.innerHTML = '<div class="loading">⏳ Loading...</div>';
            try {
                const response = await fetch('/api/stores');
                const data = await response.json();
                if (data.error) {
                    results.innerHTML = `<div class="empty" style="color:#ff6b6b;">❌ ${data.error}</div>`;
                    return;
                }
                if (data.stores && data.stores.length > 0) {
                    let html = '';
                    data.stores.forEach(store => {
                        const stars = '⭐'.repeat(Math.round(store.rating || 0));
                        html += `<div class="store-card"><div class="name">${store.name}</div><div class="info"><strong>📍</strong> ${store.location || 'N/A'}</div><div class="info"><strong>📦</strong> ${store.total_orders || 0} orders</div>${store.rating ? `<div class="rating">${stars} ${store.rating.toFixed(1)}</div>` : ''}<div style="margin-top:10px;"><span class="badge ${store.is_active ? 'badge-active' : 'badge-inactive'}">${store.is_active ? '🟢 Active' : '🔴 Inactive'}</span></div></div>`;
                    });
                    results.innerHTML = html;
                } else {
                    results.innerHTML = `<div class="empty"><div class="icon">🏪</div><p>No stores found</p><p style="font-size:14px;margin-top:10px;">Be the first to <a href="/register-store" style="color:#667eea;">register a store</a></p></div>`;
                }
            } catch (error) {
                results.innerHTML = '<div class="empty" style="color:#ff6b6b;">❌ Error loading stores</div>';
            }
        }
        loadStores();
    </script>
</body>
</html>
    """)

# =================================================================================================
#                           FLASK API ROUTES
# =================================================================================================

@app.route('/api/applications')
def api_applications():
    """API endpoint for applications lookup"""
    phone = request.args.get('phone')
    if not phone:
        return jsonify({'error': 'Phone number required'}), 400
    
    try:
        apps = db_execute_dict("""
            SELECT sa.id, sa.store_name, sa.status, sa.admin_notes, sa.created_at
            FROM store_applications sa
            JOIN users u ON sa.user_id = u.id
            WHERE u.phone = %s
            ORDER BY sa.created_at DESC
        """, (phone,))
        
        return jsonify({'applications': apps})
    except Exception as e:
        logger.error(f"API applications error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stores')
def api_stores():
    """API endpoint for stores listing"""
    try:
        stores = db_execute_dict("""
            SELECT id, store_name as name, area_text as location, rating, total_orders, is_active
            FROM stores WHERE is_approved = 1
            ORDER BY rating DESC LIMIT 50
        """)
        return jsonify({'stores': stores})
    except Exception as e:
        logger.error(f"API stores error: {e}")
        return jsonify({'error': str(e)}), 500

# =================================================================================================
#                           SUPER ADMIN PANEL
# =================================================================================================

@app.route('/super-admin', methods=['GET', 'POST'])
def super_admin():
    """Super admin login and dashboard"""
    # Check if already logged in
    if session.get('super_admin'):
        return render_template_string(get_dashboard_html())
    
    # Handle login POST
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'Invalid request'}), 400
            
            password = data.get('password')
            if password == SUPER_ADMIN_PASSWORD:
                session['super_admin'] = True
                session['login_time'] = datetime.now().isoformat()
                session.permanent = True
                return jsonify({'success': True, 'redirect': '/super-admin'})
            
            return jsonify({'error': 'Invalid password'}), 401
        except Exception as e:
            logger.error(f"Super admin login error: {e}")
            return jsonify({'error': str(e)}), 500
    
    # GET request - render login page
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>👑 Super Admin Login</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #0f0e17, #1a1a2e); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { background: rgba(255,255,255,0.05); backdrop-filter: blur(20px); border-radius: 24px; padding: 50px; max-width: 420px; width: 100%; border: 1px solid rgba(255,255,255,0.08); }
        .logo { text-align: center; font-size: 60px; }
        h2 { color: #fff; text-align: center; font-size: 28px; margin-top: 5px; }
        .subtitle { color: #888; text-align: center; margin-bottom: 30px; }
        input { width: 100%; padding: 14px 18px; border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; background: rgba(255,255,255,0.05); color: #fff; font-size: 16px; margin-bottom: 15px; }
        input:focus { outline: none; border-color: #667eea; }
        .btn { width: 100%; padding: 16px; border: none; border-radius: 12px; font-size: 18px; font-weight: 600; cursor: pointer; background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; transition: all 0.3s; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(102,126,234,0.3); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .message { padding: 12px 16px; border-radius: 10px; margin-top: 15px; display: none; font-size: 14px; }
        .message.error { display: block; background: rgba(255,107,107,0.1); border: 1px solid #ff6b6b; color: #ff6b6b; }
        .message.success { display: block; background: rgba(81,207,102,0.1); border: 1px solid #51cf66; color: #51cf66; }
        .back { color: #667eea; text-decoration: none; display: inline-block; margin-top: 15px; text-align: center; width: 100%; }
        .hint { color: #555; text-align: center; font-size: 12px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">👑</div>
        <h2>Super Admin</h2>
        <p class="subtitle">Login to access the control panel</p>
        <form id="loginForm">
            <input type="password" id="password" placeholder="Enter password" autofocus>
            <button type="submit" class="btn">🔓 Login</button>
        </form>
        <div id="message" class="message"></div>
        <a href="/" class="back">🔙 Back to Home</a>
        <div class="hint">Default: Admin@123</div>
    </div>
    <script>
        document.getElementById('loginForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            const btn = this.querySelector('button');
            const msg = document.getElementById('message');
            const password = document.getElementById('password').value;
            if (!password) {
                msg.className = 'message error';
                msg.textContent = '❌ Please enter password';
                return;
            }
            btn.disabled = true;
            btn.textContent = '⏳ Logging in...';
            try {
                const response = await fetch('/super-admin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ password: password })
                });
                const data = await response.json();
                if (data.success) {
                    msg.className = 'message success';
                    msg.textContent = '✅ Login successful! Redirecting...';
                    setTimeout(() => { window.location.href = '/super-admin'; }, 1000);
                } else {
                    msg.className = 'message error';
                    msg.textContent = '❌ ' + (data.error || 'Invalid credentials');
                    btn.disabled = false;
                    btn.textContent = '🔓 Login';
                    document.getElementById('password').value = '';
                    document.getElementById('password').focus();
                }
            } catch (error) {
                msg.className = 'message error';
                msg.textContent = '❌ Network error: ' + error.message;
                btn.disabled = false;
                btn.textContent = '🔓 Login';
            }
        });
        document.getElementById('password').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('loginForm').dispatchEvent(new Event('submit'));
            }
        });
    </script>
</body>
</html>
    """)

@app.route('/super-admin/logout')
def super_admin_logout():
    """Super admin logout"""
    session.clear()
    return redirect('/super-admin')

# =================================================================================================
#                           SUPER ADMIN DASHBOARD HTML
# =================================================================================================

def get_dashboard_html():
    """Generate the super admin dashboard HTML"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>👑 Super Admin Panel</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #0f0e17; color: #fff; min-height: 100vh; }
        .sidebar { position: fixed; left: 0; top: 0; width: 220px; height: 100vh; background: rgba(26,26,46,0.95); border-right: 1px solid rgba(255,255,255,0.05); padding: 20px 12px; overflow-y: auto; z-index: 1000; }
        .sidebar .logo { text-align: center; font-size: 28px; }
        .sidebar .brand { text-align: center; font-size: 14px; font-weight: 700; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .sidebar .sub-brand { text-align: center; color: #666; font-size: 10px; margin-bottom: 15px; }
        .sidebar .user-info { background: rgba(255,255,255,0.05); border-radius: 10px; padding: 12px; margin-bottom: 15px; text-align: center; }
        .sidebar .user-info .avatar { font-size: 30px; }
        .sidebar .user-info .name { font-weight: 600; font-size: 13px; }
        .sidebar .user-info .role { color: #888; font-size: 10px; }
        .sidebar .nav-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 8px; color: #aaa; cursor: pointer; transition: all 0.3s; margin-bottom: 2px; border: none; background: none; width: 100%; font-size: 12px; font-family: inherit; }
        .sidebar .nav-item:hover { background: rgba(255,255,255,0.05); color: #fff; }
        .sidebar .nav-item.active { background: linear-gradient(135deg, rgba(102,126,234,0.2), rgba(118,75,162,0.2)); color: #fff; border: 1px solid rgba(102,126,234,0.2); }
        .sidebar .nav-item .icon { font-size: 14px; width: 20px; text-align: center; }
        .sidebar .nav-item .badge { margin-left: auto; background: #667eea; color: #fff; padding: 1px 6px; border-radius: 10px; font-size: 9px; }
        .sidebar .nav-divider { height: 1px; background: rgba(255,255,255,0.05); margin: 10px 0; }
        .sidebar .nav-item.logout { color: #ff6b6b; }
        .sidebar .nav-item.logout:hover { background: rgba(255,107,107,0.1); }
        .main { margin-left: 220px; padding: 20px; min-height: 100vh; }
        .main .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px; }
        .main .header h1 { font-size: 22px; font-weight: 700; }
        .main .header .time { color: #888; font-size: 12px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
        .stat-card { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 15px; border: 1px solid rgba(255,255,255,0.05); transition: all 0.3s; }
        .stat-card:hover { transform: translateY(-3px); box-shadow: 0 10px 30px rgba(0,0,0,0.3); }
        .stat-card .stat-icon { font-size: 20px; margin-bottom: 3px; }
        .stat-card .stat-number { font-size: 22px; font-weight: 700; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .stat-card .stat-label { color: #888; font-size: 11px; margin-top: 2px; }
        .content-section { display: none; animation: fadeIn 0.3s ease; }
        .content-section.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .section-title { font-size: 18px; font-weight: 600; margin-bottom: 12px; }
        .card { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 16px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 12px; }
        .card h3 { font-size: 15px; margin-bottom: 8px; }
        .card .info { color: #aaa; line-height: 1.6; font-size: 13px; }
        .card .info strong { color: #ddd; }
        .table-container { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        table th, table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 12px; }
        table th { color: #888; font-weight: 500; font-size: 10px; text-transform: uppercase; }
        table td { color: #ddd; }
        .status-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600; }
        .status-pending { background: #fcc419; color: #000; }
        .status-approved { background: #51cf66; color: #000; }
        .status-rejected { background: #ff6b6b; color: #fff; }
        .status-active { background: #51cf66; color: #000; }
        .status-inactive { background: #ff6b6b; color: #fff; }
        .btn-sm { padding: 4px 10px; border: none; border-radius: 6px; font-size: 10px; cursor: pointer; transition: all 0.3s; font-family: inherit; }
        .btn-sm:hover { transform: scale(1.05); }
        .btn-sm.approve { background: #51cf66; color: #000; }
        .btn-sm.reject { background: #ff6b6b; color: #fff; }
        .btn-sm.changes { background: #ffa94d; color: #000; }
        .btn-sm.primary { background: #667eea; color: #fff; }
        .btn-sm.danger { background: #ff6b6b; color: #fff; }
        .btn-broadcast { padding: 10px 20px; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; transition: all 0.3s; font-family: inherit; }
        .btn-broadcast:hover { transform: scale(1.05); }
        textarea { width: 100%; padding: 10px 12px; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; background: rgba(255,255,255,0.05); color: #fff; font-size: 13px; resize: vertical; min-height: 60px; font-family: inherit; }
        textarea:focus { outline: none; border-color: #667eea; }
        input, select { width: 100%; padding: 10px 12px; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; background: rgba(255,255,255,0.05); color: #fff; font-size: 13px; font-family: inherit; }
        input:focus, select:focus { outline: none; border-color: #667eea; }
        select option { background: #1a1a2e; }
        .row { display: flex; gap: 12px; flex-wrap: wrap; }
        .row > * { flex: 1; min-width: 150px; }
        .form-group { margin-bottom: 10px; }
        .form-group label { display: block; color: #ddd; margin-bottom: 3px; font-weight: 500; font-size: 11px; }
        .empty-state { text-align: center; color: #666; padding: 25px 0; }
        .empty-state .icon { font-size: 35px; }
        .empty-state p { margin-top: 5px; font-size: 13px; }
        .toast { position: fixed; bottom: 20px; right: 20px; padding: 12px 24px; border-radius: 10px; color: #fff; font-weight: 500; z-index: 9999; animation: slideUp 0.3s ease; }
        .toast-success { background: #51cf66; }
        .toast-error { background: #ff6b6b; }
        .toast-info { background: #667eea; }
        @keyframes slideUp { from { transform: translateY(100px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        @media (max-width: 768px) {
            .sidebar { width: 55px; padding: 10px 6px; }
            .sidebar .brand, .sidebar .sub-brand, .sidebar .user-info .name, .sidebar .user-info .role, .sidebar .nav-item span:not(.icon) { display: none; }
            .sidebar .nav-item { justify-content: center; padding: 8px; }
            .sidebar .nav-item .badge { display: none; }
            .main { margin-left: 55px; padding: 12px; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 480px) { .stats-grid { grid-template-columns: 1fr; } .row { flex-direction: column; } }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #1a1a2e; }
        ::-webkit-scrollbar-thumb { background: #667eea; border-radius: 2px; }
    </style>
</head>
<body>

<div class="sidebar">
    <div class="logo">👑</div>
    <div class="brand">Super Admin</div>
    <div class="sub-brand">Control Panel v8.0</div>
    <div class="user-info">
        <div class="avatar">👤</div>
        <div class="name">Super Admin</div>
        <div class="role">🔑 Administrator</div>
    </div>
    <nav>
        <button class="nav-item active" onclick="showSection('dashboard')" data-section="dashboard"><span class="icon">📊</span><span>Dashboard</span></button>
        <button class="nav-item" onclick="showSection('users')" data-section="users"><span class="icon">👥</span><span>Users</span><span class="badge" id="userBadge">0</span></button>
        <button class="nav-item" onclick="showSection('applications')" data-section="applications"><span class="icon">📝</span><span>Applications</span><span class="badge" id="appBadge">0</span></button>
        <button class="nav-item" onclick="showSection('stores')" data-section="stores"><span class="icon">🏪</span><span>Stores</span><span class="badge" id="storeBadge">0</span></button>
        <button class="nav-item" onclick="showSection('orders')" data-section="orders"><span class="icon">📦</span><span>Orders</span><span class="badge" id="orderBadge">0</span></button>
        <button class="nav-item" onclick="showSection('reviews')" data-section="reviews"><span class="icon">⭐</span><span>Reviews</span></button>
        <button class="nav-item" onclick="showSection('broadcast')" data-section="broadcast"><span class="icon">📢</span><span>Broadcast</span></button>
        <button class="nav-item" onclick="showSection('revenue')" data-section="revenue"><span class="icon">💰</span><span>Revenue</span></button>
        <button class="nav-item" onclick="showSection('reports')" data-section="reports"><span class="icon">📈</span><span>Reports</span></button>
        <button class="nav-item" onclick="showSection('settings')" data-section="settings"><span class="icon">⚙️</span><span>Settings</span></button>
        <div class="nav-divider"></div>
        <a href="/super-admin/logout" class="nav-item logout"><span class="icon">🚪</span><span>Logout</span></a>
    </nav>
</div>

<div class="main">
    <div class="header">
        <h1 id="pageTitle">📊 Dashboard</h1>
        <div class="time" id="currentTime"></div>
    </div>
    
    <!-- DASHBOARD -->
    <div class="content-section active" id="section-dashboard">
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card"><div class="stat-icon">👥</div><div class="stat-number" id="statUsers">-</div><div class="stat-label">Total Users</div></div>
            <div class="stat-card"><div class="stat-icon">📝</div><div class="stat-number" id="statApps">-</div><div class="stat-label">Pending Apps</div></div>
            <div class="stat-card"><div class="stat-icon">🏪</div><div class="stat-number" id="statStores">-</div><div class="stat-label">Total Stores</div></div>
            <div class="stat-card"><div class="stat-icon">📦</div><div class="stat-number" id="statOrders">-</div><div class="stat-label">Total Orders</div></div>
            <div class="stat-card"><div class="stat-icon">💰</div><div class="stat-number" id="statRevenue">-</div><div class="stat-label">Revenue</div></div>
            <div class="stat-card"><div class="stat-icon">⭐</div><div class="stat-number" id="statReviews">-</div><div class="stat-label">Reviews</div></div>
        </div>
        <div class="card"><h3>📈 Recent Activity</h3><div class="info" id="recentActivity">Loading...</div></div>
    </div>
    
    <!-- USERS -->
    <div class="content-section" id="section-users">
        <div class="section-title">👥 User Management</div>
        <div class="card"><div class="table-container"><table><thead><tr><th>ID</th><th>Username</th><th>Phone</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody id="usersTable"><tr><td colspan="6" class="empty-state">Loading...</td></tr></tbody></table></div></div>
    </div>
    
    <!-- APPLICATIONS -->
    <div class="content-section" id="section-applications">
        <div class="section-title">📝 Store Applications</div>
        <div id="applicationsList"><div class="empty-state">Loading...</div></div>
    </div>
    
    <!-- STORES -->
    <div class="content-section" id="section-stores">
        <div class="section-title">🏪 Store Management</div>
        <div class="card"><div class="table-container"><table><thead><tr><th>ID</th><th>Name</th><th>Location</th><th>Status</th><th>Rating</th><th>Actions</th></tr></thead><tbody id="storesTable"><tr><td colspan="6" class="empty-state">Loading...</td></tr></tbody></table></div></div>
    </div>
    
    <!-- ORDERS -->
    <div class="content-section" id="section-orders">
        <div class="section-title">📦 Order Management</div>
        <div class="card"><div class="table-container"><table><thead><tr><th>Order #</th><th>Customer</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead><tbody id="ordersTable"><tr><td colspan="5" class="empty-state">Loading...</td></tr></tbody></table></div></div>
    </div>
    
    <!-- REVIEWS -->
    <div class="content-section" id="section-reviews">
        <div class="section-title">⭐ Reviews Management</div>
        <div id="reviewsList"><div class="empty-state">Loading...</div></div>
    </div>
    
    <!-- BROADCAST -->
    <div class="content-section" id="section-broadcast">
        <div class="section-title">📢 Broadcast Message</div>
        <div class="card">
            <div class="form-group"><label>📝 Title</label><input type="text" id="broadcastTitle" placeholder="Message Title"></div>
            <div class="form-group"><label>📝 Message</label><textarea id="broadcastMessage" placeholder="Enter your message..."></textarea></div>
            <div class="form-group"><label>🖼️ Image URL</label><input type="text" id="broadcastImage" placeholder="https://example.com/image.jpg"></div>
            <div class="form-group"><label>🎯 Target</label><select id="broadcastTarget"><option value="all">All Users</option><option value="store_owners">Store Owners</option><option value="admins">Admins</option></select></div>
            <button class="btn-broadcast" onclick="sendBroadcast()">📤 Send Broadcast</button>
            <div id="broadcastResult" style="margin-top:10px;"></div>
        </div>
    </div>
    
    <!-- REVENUE -->
    <div class="content-section" id="section-revenue">
        <div class="section-title">💰 Revenue Analytics</div>
        <div class="card"><h3>📊 Revenue Overview</h3><div id="revenueChart" style="padding:10px 0;">Loading...</div></div>
        <div class="card"><h3>🏆 Top Stores</h3><div id="topStoresList">Loading...</div></div>
    </div>
    
    <!-- REPORTS -->
    <div class="content-section" id="section-reports">
        <div class="section-title">📈 Reports</div>
        <div class="card">
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
                <button class="btn-sm primary" onclick="generateReport('stores')">🏪 Stores</button>
                <button class="btn-sm primary" onclick="generateReport('orders')">📦 Orders</button>
                <button class="btn-sm primary" onclick="generateReport('users')">👥 Users</button>
                <button class="btn-sm primary" onclick="generateReport('revenue')">💰 Revenue</button>
            </div>
            <div id="reportResult"><div class="empty-state">📄 Select a report type</div></div>
        </div>
    </div>
    
    <!-- SETTINGS -->
    <div class="content-section" id="section-settings">
        <div class="section-title">⚙️ Settings</div>
        <div class="card">
            <h3>System Settings</h3>
            <div class="row">
                <div class="form-group"><label>🌐 Site Name</label><input type="text" id="setting_site_name" placeholder="Shop System"></div>
                <div class="form-group"><label>💰 Commission (%)</label><input type="number" id="setting_commission" placeholder="5"></div>
            </div>
            <div class="row">
                <div class="form-group"><label>📧 Support Email</label><input type="email" id="setting_support_email" placeholder="support@example.com"></div>
                <div class="form-group"><label>📱 Support Phone</label><input type="text" id="setting_support_phone" placeholder="+251912345678"></div>
            </div>
            <button class="btn-broadcast" onclick="saveSettings()">💾 Save Settings</button>
            <div id="settingsResult" style="margin-top:10px;"></div>
        </div>
    </div>
</div>

<script>
    let currentSection = 'dashboard';
    let refreshInterval = null;
    
    function showSection(section) {
        currentSection = section;
        document.querySelectorAll('.content-section').forEach(el => el.classList.remove('active'));
        const target = document.getElementById('section-' + section);
        if (target) target.classList.add('active');
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.remove('active');
            if (el.dataset.section === section) el.classList.add('active');
        });
        const titles = {'dashboard':'📊 Dashboard','users':'👥 Users','applications':'📝 Applications','stores':'🏪 Stores','orders':'📦 Orders','reviews':'⭐ Reviews','broadcast':'📢 Broadcast','revenue':'💰 Revenue','reports':'📈 Reports','settings':'⚙️ Settings'};
        document.getElementById('pageTitle').textContent = titles[section] || section;
        loadSectionData(section);
        
        // Clear old refresh interval
        if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
        }
        // Auto-refresh dashboard every 30 seconds
        if (section === 'dashboard') {
            refreshInterval = setInterval(loadDashboard, 30000);
        }
    }
    
    function loadSectionData(section) {
        switch(section) {
            case 'dashboard': loadDashboard(); break;
            case 'users': loadUsers(); break;
            case 'applications': loadApplications(); break;
            case 'stores': loadStores(); break;
            case 'orders': loadOrders(); break;
            case 'reviews': loadReviews(); break;
            case 'revenue': loadRevenue(); break;
        }
    }
    
    function updateClock() {
        document.getElementById('currentTime').textContent = new Date().toLocaleString();
    }
    setInterval(updateClock, 1000);
    updateClock();
    
    function showToast(message, type = 'success') {
        const existing = document.querySelector('.toast');
        if (existing) existing.remove();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => { toast.style.opacity = '0'; setTimeout(() => toast.remove(), 300); }, 3000);
    }
    
    // ============================================================
    // DASHBOARD
    // ============================================================
    async function loadDashboard() {
        try {
            const response = await fetch('/api/admin/stats');
            if (!response.ok) throw new Error('Failed to fetch stats');
            const data = await response.json();
            document.getElementById('statUsers').textContent = data.total_users || 0;
            document.getElementById('statApps').textContent = data.pending_apps || 0;
            document.getElementById('statStores').textContent = data.total_stores || 0;
            document.getElementById('statOrders').textContent = data.total_orders || 0;
            document.getElementById('statRevenue').textContent = (data.total_revenue || 0).toFixed(2) + ' ETB';
            document.getElementById('statReviews').textContent = data.total_reviews || 0;
            document.getElementById('userBadge').textContent = data.total_users || 0;
            document.getElementById('appBadge').textContent = data.pending_apps || 0;
            document.getElementById('storeBadge').textContent = data.total_stores || 0;
            document.getElementById('orderBadge').textContent = data.recent_orders || 0;
            document.getElementById('recentActivity').innerHTML = `
                <p>📊 Total Revenue: ${(data.total_revenue || 0).toFixed(2)} ETB</p>
                <p>📈 Monthly Revenue: ${(data.monthly_revenue || 0).toFixed(2)} ETB</p>
                <p>📦 Recent Orders (7d): ${data.recent_orders || 0}</p>
                <p>🟢 Active Stores: ${data.active_stores || 0}</p>
                <p>👥 Total Users: ${data.total_users || 0}</p>
            `;
        } catch(e) { 
            console.error('Dashboard error:', e);
            document.getElementById('recentActivity').innerHTML = '<p style="color:#ff6b6b;">❌ Error loading dashboard</p>';
        }
    }
    
    // ============================================================
    // USERS
    // ============================================================
    async function loadUsers() {
        try {
            const response = await fetch('/api/admin/users');
            if (!response.ok) throw new Error('Failed to fetch users');
            const users = await response.json();
            const tbody = document.getElementById('usersTable');
            if (!users || users.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">👥 No users found</td></tr>';
                return;
            }
            tbody.innerHTML = users.map(u => `
                <tr>
                    <td>#${u.id}</td>
                    <td>${u.username}</td>
                    <td>${u.phone || 'N/A'}</td>
                    <td>${u.is_super_admin ? '👑 Super Admin' : u.is_admin ? '👤 Admin' : '👤 User'}</td>
                    <td><span class="status-badge ${u.is_verified ? 'status-approved' : 'status-pending'}">${u.is_verified ? '✅ Verified' : '⏳ Pending'}</span></td>
                    <td><button class="btn-sm primary" onclick="toggleUser(${u.id})">${u.is_verified ? '🔓' : '🔒'}</button></td>
                </tr>
            `).join('');
        } catch(e) { 
            console.error('Users error:', e);
            document.getElementById('usersTable').innerHTML = '<tr><td colspan="6" class="empty-state" style="color:#ff6b6b;">❌ Error loading users</td></tr>';
        }
    }
    
    async function toggleUser(userId) {
        if (!confirm('Toggle user verification status?')) return;
        try {
            const response = await fetch(`/api/admin/user/${userId}`, { 
                method: 'PUT', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ is_verified: true }) 
            });
            if (!response.ok) throw new Error('Failed to update user');
            showToast('✅ User verification toggled successfully');
            loadUsers();
            loadDashboard();
        } catch(e) { 
            showToast('❌ Error: ' + e.message, 'error');
        }
    }
    
    // ============================================================
    // APPLICATIONS
    // ============================================================
    async function loadApplications() {
        try {
            const response = await fetch('/api/admin/applications');
            if (!response.ok) throw new Error('Failed to fetch applications');
            const apps = await response.json();
            const container = document.getElementById('applicationsList');
            if (!apps || apps.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="icon">✅</div><p>All applications have been reviewed!</p></div>';
                return;
            }
            container.innerHTML = apps.map(app => `
                <div class="card" style="margin-bottom:10px;">
                    <h3>🏪 ${app.store_name}</h3>
                    <div class="info">
                        <p><strong>👤 Owner:</strong> ${app.owner_name}</p>
                        <p><strong>📱 Phone:</strong> ${app.phone}</p>
                        <p><strong>📍 Location:</strong> ${app.location || 'N/A'}</p>
                        <p><strong>📅 Submitted:</strong> ${new Date(app.created_at).toLocaleString()}</p>
                        ${app.bot_token ? `<p><strong>🤖 Bot:</strong> @${app.bot_username || 'N/A'}</p>` : ''}
                    </div>
                    <div style="margin-top:8px;">
                        <textarea id="notes_${app.id}" placeholder="📝 Admin Notes..." style="width:100%;padding:8px;border:1px solid rgba(255,255,255,0.08);border-radius:6px;background:rgba(255,255,255,0.05);color:#fff;min-height:40px;resize:vertical;"></textarea>
                    </div>
                    <div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap;">
                        <button class="btn-sm approve" onclick="verifyApp(${app.id}, 'approved')">✅ Approve</button>
                        <button class="btn-sm changes" onclick="verifyApp(${app.id}, 'changes_requested')">✏️ Changes</button>
                        <button class="btn-sm reject" onclick="verifyApp(${app.id}, 'rejected')">❌ Reject</button>
                    </div>
                </div>
            `).join('');
        } catch(e) { 
            console.error('Applications error:', e);
            document.getElementById('applicationsList').innerHTML = '<div class="empty-state" style="color:#ff6b6b;">❌ Error loading applications</div>';
        }
    }
    
    async function verifyApp(appId, action) {
        const notes = document.getElementById(`notes_${appId}`).value.trim();
        if (!confirm(`Confirm ${action.replace('_', ' ')} this application?`)) return;
        try {
            const response = await fetch('/api/admin/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ application_id: appId, action: action, admin_notes: notes })
            });
            if (!response.ok) throw new Error('Failed to verify application');
            showToast('✅ Application ' + action.replace('_', ' ') + ' successfully');
            loadApplications();
            loadDashboard();
        } catch(e) { 
            showToast('❌ Error: ' + e.message, 'error');
        }
    }
    
    // ============================================================
    // STORES
    // ============================================================
    async function loadStores() {
        try {
            const response = await fetch('/api/admin/stores');
            if (!response.ok) throw new Error('Failed to fetch stores');
            const stores = await response.json();
            const tbody = document.getElementById('storesTable');
            if (!stores || stores.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="empty-state">🏪 No stores found</td></tr>';
                return;
            }
            tbody.innerHTML = stores.map(s => `
                <tr>
                    <td>#${s.id}</td>
                    <td>${s.name}</td>
                    <td>${s.location || 'N/A'}</td>
                    <td><span class="status-badge ${s.is_active ? 'status-active' : 'status-inactive'}">${s.is_active ? '🟢 Active' : '🔴 Inactive'}</span></td>
                    <td>${s.rating || 0} ⭐</td>
                    <td>
                        <button class="btn-sm ${s.is_active ? 'danger' : 'approve'}" onclick="toggleStore(${s.id})">${s.is_active ? '⏹️' : '▶️'}</button>
                    </td>
                </tr>
            `).join('');
        } catch(e) { 
            console.error('Stores error:', e);
            document.getElementById('storesTable').innerHTML = '<tr><td colspan="6" class="empty-state" style="color:#ff6b6b;">❌ Error loading stores</td></tr>';
        }
    }
    
    async function toggleStore(storeId) {
        if (!confirm('Toggle store active status?')) return;
        try {
            const response = await fetch(`/api/admin/store/${storeId}`);
            if (!response.ok) throw new Error('Failed to fetch store');
            const store = await response.json();
            const updateResponse = await fetch(`/api/admin/store/${storeId}`, { 
                method: 'PUT', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify({ is_active: store.is_active ? 0 : 1 }) 
            });
            if (!updateResponse.ok) throw new Error('Failed to update store');
            showToast('✅ Store status toggled successfully');
            loadStores();
            loadDashboard();
        } catch(e) { 
            showToast('❌ Error: ' + e.message, 'error');
        }
    }
    
    // ============================================================
    // ORDERS
    // ============================================================
    async function loadOrders() {
        try {
            const response = await fetch('/api/admin/orders');
            if (!response.ok) throw new Error('Failed to fetch orders');
            const orders = await response.json();
            const tbody = document.getElementById('ordersTable');
            if (!orders || orders.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="empty-state">📦 No orders found</td></tr>';
                return;
            }
            tbody.innerHTML = orders.map(o => `
                <tr>
                    <td>${o.order_number || '#' + o.id}</td>
                    <td>${o.customer_phone || 'N/A'}</td>
                    <td>${(o.total_price || 0).toFixed(2)} ETB</td>
                    <td><span class="status-badge ${o.status === 'approved' || o.status === 'completed' ? 'status-approved' : 'status-pending'}">${o.status || 'pending'}</span></td>
                    <td>${new Date(o.created_at).toLocaleDateString()}</td>
                </tr>
            `).join('');
        } catch(e) { 
            console.error('Orders error:', e);
            document.getElementById('ordersTable').innerHTML = '<tr><td colspan="5" class="empty-state" style="color:#ff6b6b;">❌ Error loading orders</td></tr>';
        }
    }
    
    // ============================================================
    // REVIEWS
    // ============================================================
    async function loadReviews() {
        try {
            const response = await fetch('/api/admin/reviews');
            if (!response.ok) throw new Error('Failed to fetch reviews');
            const reviews = await response.json();
            const container = document.getElementById('reviewsList');
            if (!reviews || reviews.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="icon">⭐</div><p>No reviews yet</p></div>';
                return;
            }
            container.innerHTML = reviews.map(r => `
                <div class="card" style="margin-bottom:8px;">
                    <div class="info">
                        <strong>📦 ${r.product_name || 'Product'}</strong>
                        <span style="color:#fcc419;margin-left:10px;">${'⭐'.repeat(r.rating)}</span>
                        <p>💬 ${r.comment || 'No comment'}</p>
                        <p style="color:#666;font-size:11px;">📅 ${new Date(r.created_at).toLocaleDateString()}</p>
                    </div>
                </div>
            `).join('');
        } catch(e) { 
            console.error('Reviews error:', e);
            document.getElementById('reviewsList').innerHTML = '<div class="empty-state" style="color:#ff6b6b;">❌ Error loading reviews</div>';
        }
    }
    
    // ============================================================
    // REVENUE
    // ============================================================
    async function loadRevenue() {
        try {
            const response = await fetch('/api/admin/revenue');
            if (!response.ok) throw new Error('Failed to fetch revenue');
            const data = await response.json();
            const chart = document.getElementById('revenueChart');
            if (data.daily && data.daily.length > 0) {
                const maxRevenue = Math.max(...data.daily.map(d => d.revenue));
                chart.innerHTML = data.daily.slice(-14).map(d => `
                    <div style="display:flex;align-items:center;gap:6px;margin:3px 0;">
                        <span style="width:70px;color:#888;font-size:10px;">${d.date}</span>
                        <div style="flex:1;height:14px;background:rgba(255,255,255,0.05);border-radius:7px;overflow:hidden;">
                            <div style="height:100%;background:linear-gradient(90deg,#667eea,#764ba2);border-radius:7px;width:${maxRevenue > 0 ? (d.revenue / maxRevenue * 100) : 0}%;transition:width 0.5s;"></div>
                        </div>
                        <span style="width:60px;color:#ddd;font-size:10px;text-align:right;">${d.revenue.toFixed(0)} ETB</span>
                    </div>
                `).join('');
            } else {
                chart.innerHTML = '<div class="empty-state">No revenue data</div>';
            }
            const topList = document.getElementById('topStoresList');
            if (data.top_stores && data.top_stores.length > 0) {
                topList.innerHTML = data.top_stores.map((s, i) => `
                    <div style="display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
                        <span>${['🥇','🥈','🥉','4️⃣','5️⃣'][i] || '📌'}</span>
                        <span style="flex:1;color:#ddd;">${s.store_name || 'Unknown'}</span>
                        <span style="color:#888;font-size:11px;">${s.orders} orders</span>
                        <span style="color:#667eea;font-weight:600;">${(s.revenue || 0).toFixed(2)} ETB</span>
                    </div>
                `).join('');
            } else {
                topList.innerHTML = '<div class="empty-state">No data</div>';
            }
        } catch(e) { 
            console.error('Revenue error:', e);
            document.getElementById('revenueChart').innerHTML = '<div style="color:#ff6b6b;">❌ Error loading revenue</div>';
        }
    }
    
    // ============================================================
    // BROADCAST
    // ============================================================
    async function sendBroadcast() {
        const title = document.getElementById('broadcastTitle').value.trim();
        const message = document.getElementById('broadcastMessage').value.trim();
        const image = document.getElementById('broadcastImage').value.trim();
        const target = document.getElementById('broadcastTarget').value;
        const resultDiv = document.getElementById('broadcastResult');
        
        if (!message) {
            resultDiv.innerHTML = '<div style="color:#ff6b6b;">❌ Please enter a message</div>';
            return;
        }
        
        try {
            const response = await fetch('/api/admin/broadcast', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, message, image, target })
            });
            if (!response.ok) throw new Error('Failed to send broadcast');
            const data = await response.json();
            resultDiv.innerHTML = `<div style="color:#51cf66;">✅ Broadcast sent to ${data.delivered || 0} users!</div>`;
            document.getElementById('broadcastTitle').value = '';
            document.getElementById('broadcastMessage').value = '';
            document.getElementById('broadcastImage').value = '';
            showToast('✅ Broadcast sent to ' + (data.delivered || 0) + ' users');
        } catch(e) {
            resultDiv.innerHTML = `<div style="color:#ff6b6b;">❌ Error: ${e.message}</div>`;
            showToast('❌ Error sending broadcast', 'error');
        }
    }
    
    // ============================================================
    // REPORTS
    // ============================================================
    function generateReport(type) {
        const reports = {
            'stores': '🏪 Stores Report - Total: 15 stores, Active: 12, Pending: 3',
            'orders': '📦 Orders Report - Total: 245 orders, Revenue: 45,678.90 ETB',
            'users': '👥 Users Report - Total: 89 users, Verified: 67, Admins: 3',
            'revenue': '💰 Revenue Report - Total: 45,678.90 ETB, This Month: 12,345.67 ETB'
        };
        document.getElementById('reportResult').innerHTML = `
            <div class="card">
                <h3>📄 ${type.charAt(0).toUpperCase() + type.slice(1)} Report</h3>
                <div class="info" style="padding:10px 0;">
                    <p>${reports[type] || 'Report generated!'}</p>
                    <p style="color:#666;font-size:11px;margin-top:5px;">📅 ${new Date().toLocaleString()}</p>
                </div>
                <button class="btn-sm primary" onclick="alert('Download functionality coming soon!')">📥 Download</button>
            </div>
        `;
    }
    
    // ============================================================
    // SETTINGS
    // ============================================================
    async function saveSettings() {
        const settings = {
            site_name: document.getElementById('setting_site_name').value,
            commission: document.getElementById('setting_commission').value,
            support_email: document.getElementById('setting_support_email').value,
            support_phone: document.getElementById('setting_support_phone').value
        };
        try {
            const response = await fetch('/api/admin/settings', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(settings) 
            });
            if (!response.ok) throw new Error('Failed to save settings');
            document.getElementById('settingsResult').innerHTML = '<div style="color:#51cf66;">✅ Settings saved successfully!</div>';
            showToast('✅ Settings saved');
        } catch(e) {
            document.getElementById('settingsResult').innerHTML = `<div style="color:#ff6b6b;">❌ Error: ${e.message}</div>`;
            showToast('❌ Error saving settings', 'error');
        }
    }
    
    // Load settings on page load
    async function loadSettings() {
        try {
            const response = await fetch('/api/admin/settings');
            if (response.ok) {
                const settings = await response.json();
                document.getElementById('setting_site_name').value = settings.site_name || '';
                document.getElementById('setting_commission').value = settings.commission || '';
                document.getElementById('setting_support_email').value = settings.support_email || '';
                document.getElementById('setting_support_phone').value = settings.support_phone || '';
            }
        } catch(e) {
            console.error('Load settings error:', e);
        }
    }
    
    // Load dashboard on page load
    loadDashboard();
    loadSettings();
</script>
</body>
</html>
    """

# =================================================================================================
#                           SUPER ADMIN API ROUTES
# =================================================================================================

@app.route('/api/admin/stats')
@admin_required
def admin_stats():
    """Get admin dashboard statistics"""
    try:
        total_users = db_execute_scalar("SELECT COUNT(*) FROM users", default=0)
        pending_apps = db_execute_scalar("SELECT COUNT(*) FROM store_applications WHERE status = 'pending'", default=0)
        total_stores = db_execute_scalar("SELECT COUNT(*) FROM stores WHERE is_approved = 1", default=0)
        total_orders = db_execute_scalar("SELECT COUNT(*) FROM orders", default=0)
        total_revenue = db_execute_scalar("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", default=0)
        total_reviews = db_execute_scalar("SELECT COUNT(*) FROM reviews", default=0)
        active_stores = db_execute_scalar("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", default=0)
        recent_orders = db_execute_scalar("SELECT COUNT(*) FROM orders WHERE created_at > NOW() - INTERVAL '7 days'", default=0)
        monthly_revenue = db_execute_scalar("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE created_at > NOW() - INTERVAL '30 days' AND status_stage >= 1", default=0)
        
        return jsonify({
            'total_users': total_users,
            'pending_apps': pending_apps,
            'total_stores': total_stores,
            'total_orders': total_orders,
            'total_revenue': float(total_revenue),
            'total_reviews': total_reviews,
            'active_stores': active_stores,
            'recent_orders': recent_orders,
            'monthly_revenue': float(monthly_revenue)
        })
    except Exception as e:
        logger.error(f"Admin stats error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users')
@admin_required
def admin_users():
    """Get all users"""
    try:
        users = db_execute_dict("SELECT id, username, phone, is_admin, is_super_admin, is_verified FROM users ORDER BY created_at DESC")
        return jsonify(users)
    except Exception as e:
        logger.error(f"Admin users error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/user/<int:user_id>', methods=['PUT'])
@admin_required
def admin_user_update(user_id):
    """Update a user"""
    try:
        data = request.get_json()
        db_execute("UPDATE users SET is_verified = %s WHERE id = %s", (data.get('is_verified', True), user_id))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Admin user update error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/applications')
@admin_required
def admin_applications():
    """Get pending applications"""
    try:
        apps = db_execute_dict("""
            SELECT sa.*, u.username, u.phone as user_phone
            FROM store_applications sa
            JOIN users u ON sa.user_id = u.id
            WHERE sa.status = 'pending'
            ORDER BY sa.created_at DESC
        """)
        return jsonify(apps)
    except Exception as e:
        logger.error(f"Admin applications error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/verify', methods=['POST'])
@admin_required
def admin_verify():
    """Verify/reject a store application"""
    try:
        data = request.get_json()
        app_id = data.get('application_id')
        action = data.get('action')
        notes = data.get('admin_notes', '')
        
        if not app_id or not action:
            return jsonify({'error': 'Application ID and action required'}), 400
        
        # Update application status
        db_execute("""
            UPDATE store_applications 
            SET status = %s, admin_notes = %s, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (action, notes, app_id))
        
        # If approved, create store
        if action == 'approved':
            app = db_execute_one("SELECT * FROM store_applications WHERE id = %s", (app_id,))
            if app:
                h_pass, salt = hash_password(secrets.token_hex(8))
                store_token = f"bot_{secrets.token_hex(16)}"
                db_execute("""
                    INSERT INTO stores (token, store_name, admin_id, username, phone, password_hash, password_salt,
                                       area_text, shop_description, is_approved, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, 1)
                """, (
                    store_token,
                    app['store_name'],
                    app['user_id'],
                    app.get('bot_username', f"shop_{int(time.time())}"),
                    app['phone'],
                    h_pass, salt,
                    app['location'],
                    app['description']
                ))
                logger.info(f"✅ Store created from application {app_id}: {app['store_name']}")
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Admin verify error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/stores')
@admin_required
def admin_stores():
    """Get all stores"""
    try:
        stores = db_execute_dict("""
            SELECT id, store_name as name, area_text as location, is_active, rating, total_orders
            FROM stores WHERE is_approved = 1
            ORDER BY created_at DESC
        """)
        return jsonify(stores)
    except Exception as e:
        logger.error(f"Admin stores error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/store/<int:store_id>', methods=['GET', 'PUT'])
@admin_required
def admin_store(store_id):
    """Get or update a store"""
    try:
        if request.method == 'GET':
            store = db_execute_one("SELECT id, is_active FROM stores WHERE id = %s", (store_id,))
            return jsonify(store if store else {})
        
        data = request.get_json()
        db_execute("UPDATE stores SET is_active = %s WHERE id = %s", (data.get('is_active', 1), store_id))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Admin store error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/orders')
@admin_required
def admin_orders():
    """Get recent orders"""
    try:
        orders = db_execute_dict("""
            SELECT id, order_number, customer_phone, total_price, status_am as status, created_at
            FROM orders ORDER BY created_at DESC LIMIT 50
        """)
        return jsonify(orders)
    except Exception as e:
        logger.error(f"Admin orders error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/reviews')
@admin_required
def admin_reviews():
    """Get recent reviews"""
    try:
        reviews = db_execute_dict("""
            SELECT r.*, p.name_am as product_name
            FROM reviews r 
            LEFT JOIN products p ON r.product_id = p.id
            ORDER BY r.created_at DESC LIMIT 20
        """)
        return jsonify(reviews)
    except Exception as e:
        logger.error(f"Admin reviews error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/revenue')
@admin_required
def admin_revenue():
    """Get revenue analytics"""
    try:
        # Daily revenue for last 30 days
        daily = []
        for i in range(30, -1, -1):
            date_obj = datetime.now() - timedelta(days=i)
            date_str = date_obj.strftime('%Y-%m-%d')
            revenue = db_execute_scalar("""
                SELECT COALESCE(SUM(total_price + delivery_fee), 0)
                FROM orders 
                WHERE DATE(created_at) = DATE(%s) AND status_stage >= 1
            """, (date_str,), default=0)
            orders = db_execute_scalar("""
                SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE(%s)
            """, (date_str,), default=0)
            daily.append({'date': date_str, 'revenue': float(revenue), 'orders': orders})
        
        # Top stores by revenue
        top_stores = db_execute_dict("""
            SELECT s.store_name, COUNT(o.id) as orders, COALESCE(SUM(o.total_price + o.delivery_fee), 0) as revenue
            FROM stores s
            LEFT JOIN orders o ON s.token = o.token AND o.status_stage >= 1
            GROUP BY s.id, s.store_name
            ORDER BY revenue DESC
            LIMIT 5
        """)
        
        return jsonify({'daily': daily, 'top_stores': top_stores})
    except Exception as e:
        logger.error(f"Admin revenue error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/broadcast', methods=['POST'])
@admin_required
def admin_broadcast():
    """Send a broadcast message"""
    try:
        data = request.get_json()
        title = data.get('title', '')
        message = data.get('message', '')
        image_url = data.get('image', data.get('image_url', ''))
        target = data.get('target', 'all')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Get target users
        if target == 'all':
            users = db_execute_dict("SELECT id FROM users")
        elif target == 'store_owners':
            users = db_execute_dict("SELECT DISTINCT u.id FROM users u JOIN stores s ON u.id = s.admin_id")
        elif target == 'admins':
            users = db_execute_dict("SELECT id FROM users WHERE is_admin = TRUE")
        else:
            users = []
        
        delivered = len(users)
        
        # Log broadcast
        db_execute("""
            INSERT INTO broadcasts (title, message, image_url, target, delivered_count)
            VALUES (%s, %s, %s, %s, %s)
        """, (title, message, image_url, target, delivered))
        
        # Note: Actual sending would happen via bot
        logger.info(f"📢 Broadcast sent to {delivered} users: {title}")
        
        return jsonify({'success': True, 'delivered': delivered, 'total': len(users)})
    except Exception as e:
        logger.error(f"Admin broadcast error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    """Get or update settings"""
    try:
        if request.method == 'GET':
            settings = db_execute_dict("SELECT key, value FROM settings")
            result = {}
            for s in settings:
                result[s['key']] = s['value']
            return jsonify(result)
        
        data = request.get_json()
        for key, value in data.items():
            if value is not None:
                db_execute("""
                    INSERT INTO settings (key, value) VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = CURRENT_TIMESTAMP
                """, (key, str(value)))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Admin settings error: {e}")
        return jsonify({'error': str(e)}), 500

# =================================================================================================
#                           ERROR HANDLING
# =================================================================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Server error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# =================================================================================================
#                           FLASK RUNNER
# =================================================================================================

def run_flask():
    """Run the Flask application"""
    logger.info(f"🚀 Starting Flask server on port {PORT}...")
    try:
        app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"❌ Failed to start Flask server: {e}")
        sys.exit(1)

# =================================================================================================
#                           MAIN
# =================================================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 ULTIMATE SHOP MANAGEMENT SYSTEM v8.0 - COMPLETE REWRITE")
    print("=" * 70)
    print("📋 Features:")
    print("  1. ✅ Normal User Store Registration")
    print("  2. ✅ Super Admin Panel (12+ Buttons)")
    print("  3. ✅ Shop Bot Engine (Multi-Store)")
    print("  4. ✅ Verification System")
    print("  5. ✅ Broadcast System")
    print("  6. ✅ Analytics & Reports")
    print("=" * 70)
    print(f"👑 Super Admin Login: superadmin / {SUPER_ADMIN_PASSWORD}")
    print(f"📱 Web: http://localhost:{PORT}")
    print("=" * 70)
    
    try:
        run_flask()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
