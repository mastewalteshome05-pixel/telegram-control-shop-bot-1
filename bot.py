"""
====================================================================================================
                    🚀 ULTIMATE CONTROL BOT v6.0 🚀
        ከ1000+ ቦቶች ማስተዳደር የሚችል የላቀ ሲስተም
====================================================================================================
"""

import os
import sys
import json
import time
import math
import re
import hashlib
import secrets
import threading
import logging
import csv
import io
import base64
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from functools import wraps
from contextlib import contextmanager
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# Third-party imports
import telebot
from telebot import types, apihelper
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request, render_template_string, send_file, make_response
from flask_cors import CORS
import google.generativeai as genai
from PIL import Image
import requests

# =================================================================================================
#                           CONFIGURATION & ENVIRONMENT
# =================================================================================================

class Config:
    """የሲስተም ውቅር ክፍል"""
    
    # Database
    DATABASE_URL = os.environ.get("DATABASE_URL")
    DATABASE_POOL_MIN = int(os.environ.get("DATABASE_POOL_MIN", "2"))
    DATABASE_POOL_MAX = int(os.environ.get("DATABASE_POOL_MAX", "20"))
    
    # Bot Tokens
    CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")
    SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
    SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
    
    # API Keys
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    
    # Server
    PORT = int(os.environ.get("PORT", "8080"))
    HOST = os.environ.get("HOST", "0.0.0.0")
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    MAX_BOTS = int(os.environ.get("MAX_BOTS", "1000"))
    
    # Security
    SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "7200"))
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION = int(os.environ.get("LOCKOUT_DURATION", "900"))
    
    # Bot Management
    BOT_RESTART_DELAY = int(os.environ.get("BOT_RESTART_DELAY", "5"))
    BOT_HEALTH_CHECK_INTERVAL = int(os.environ.get("BOT_HEALTH_CHECK_INTERVAL", "60"))
    MAX_BOT_RESTARTS = int(os.environ.get("MAX_BOT_RESTARTS", "5"))
    
    # Delivery
    BASE_DELIVERY_FEE = float(os.environ.get("BASE_DELIVERY_FEE", "30"))
    PER_KM_RATE = float(os.environ.get("PER_KM_RATE", "8"))
    
    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("LOG_FILE", "control_bot.log")

# Validate required config
if not Config.DATABASE_URL:
    raise ValueError("❌ DATABASE_URL environment variable is required!")
if not Config.CONTROL_BOT_TOKEN:
    raise ValueError("❌ CONTROL_BOT_TOKEN environment variable is required!")

# =================================================================================================
#                           LOGGING SYSTEM
# =================================================================================================

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ControlBot')

try:
    file_handler = logging.FileHandler(Config.LOG_FILE)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
except Exception as e:
    print(f"⚠️ Could not create log file: {e}")

# =================================================================================================
#                           DATABASE LAYER
# =================================================================================================

db_pool = None
db_pool_lock = threading.Lock()

def init_db_pool():
    global db_pool
    with db_pool_lock:
        if db_pool is None:
            try:
                db_pool = ThreadedConnectionPool(
                    Config.DATABASE_POOL_MIN,
                    Config.DATABASE_POOL_MAX,
                    dsn=Config.DATABASE_URL
                )
                conn = db_pool.getconn()
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                db_pool.putconn(conn)
                logger.info(f"✅ Database pool initialized (min={Config.DATABASE_POOL_MIN}, max={Config.DATABASE_POOL_MAX})")
            except Exception as e:
                logger.error(f"❌ Database pool initialization failed: {e}")
                raise

def get_db_connection():
    global db_pool
    if db_pool is None:
        init_db_pool()
    
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except Exception as e:
        logger.error(f"❌ Failed to get connection: {e}")
        with db_pool_lock:
            try:
                if db_pool:
                    db_pool.closeall()
            except:
                pass
            db_pool = None
            init_db_pool()
        return db_pool.getconn()

def put_db_connection(conn):
    if conn is not None and db_pool is not None:
        try:
            db_pool.putconn(conn)
        except:
            try:
                conn.close()
            except:
                pass

def db_execute(query: str, params: tuple = None, fetch: bool = False):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            if fetch:
                return cur.fetchall()
            conn.commit()
            return cur.rowcount if cur.rowcount > 0 else None
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise
    finally:
        if conn:
            put_db_connection(conn)

def db_execute_dict(query: str, params: tuple = None):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            return cur.fetchall()
    except Exception as e:
        logger.error(f"❌ Database error: {e}")
        raise
    finally:
        if conn:
            put_db_connection(conn)

# =================================================================================================
#                           DATABASE SCHEMA
# =================================================================================================

def init_schema():
    """የውሂብ ጎታ ሰንጠረዦች መፍጠር"""
    
    schema = """
    -- =====================================================
    -- STORES TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS stores (
        id SERIAL PRIMARY KEY,
        token TEXT UNIQUE NOT NULL,
        store_name TEXT NOT NULL,
        admin_id BIGINT,
        username TEXT,
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL,
        telebirr TEXT,
        cbebirr TEXT,
        bank_name TEXT,
        bank_account TEXT,
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
        last_restart TIMESTAMP,
        restart_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- PRODUCTS TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        name_am TEXT NOT NULL,
        name_en TEXT,
        brand TEXT,
        price REAL NOT NULL,
        stock INTEGER DEFAULT 0,
        desc_am TEXT,
        desc_en TEXT,
        image_url TEXT,
        category_id INTEGER,
        is_active INTEGER DEFAULT 1,
        sales_count INTEGER DEFAULT 0,
        rating REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- CATEGORIES TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        name_am TEXT,
        name_en TEXT,
        icon TEXT,
        parent_id INTEGER DEFAULT 0,
        display_order INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- ORDERS TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        customer_id BIGINT NOT NULL,
        customer_phone TEXT,
        customer_name TEXT,
        status_am TEXT DEFAULT 'በመጠባበቅ ላይ',
        status_en TEXT DEFAULT 'Pending',
        status_stage INTEGER DEFAULT 0,
        total_price REAL NOT NULL,
        delivery_fee REAL DEFAULT 0,
        discount REAL DEFAULT 0,
        commission REAL DEFAULT 0,
        payment_method TEXT,
        payment_status TEXT DEFAULT 'pending',
        payment_receipt_url TEXT,
        tracking_number TEXT,
        delivery_address TEXT,
        delivery_lat REAL,
        delivery_lng REAL,
        notes TEXT,
        delivered_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- ORDER ITEMS TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL,
        product_name TEXT,
        qty INTEGER NOT NULL,
        price REAL NOT NULL,
        discount REAL DEFAULT 0,
        total REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- USER LANGUAGES TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS user_langs (
        chat_id BIGINT PRIMARY KEY,
        lang TEXT DEFAULT 'am',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- CUSTOMER INFO TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS customer_info (
        chat_id BIGINT PRIMARY KEY,
        phone TEXT,
        lat REAL,
        lng REAL,
        address TEXT,
        city TEXT,
        subcity TEXT,
        woreda TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- AUDIT LOGS TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        action TEXT NOT NULL,
        details JSONB,
        ip_address TEXT,
        user_agent TEXT,
        success BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- BOT METRICS TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS bot_metrics (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        metric_name TEXT NOT NULL,
        metric_value REAL,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- NOTIFICATIONS TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info',
        link TEXT,
        is_read BOOLEAN DEFAULT FALSE,
        is_sent BOOLEAN DEFAULT FALSE,
        sent_at TIMESTAMP,
        read_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- STORE ANALYTICS TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS store_analytics (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        date DATE NOT NULL,
        visits INTEGER DEFAULT 0,
        views INTEGER DEFAULT 0,
        orders INTEGER DEFAULT 0,
        revenue REAL DEFAULT 0,
        unique_customers INTEGER DEFAULT 0,
        conversion_rate REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- INDEXES
    -- =====================================================
    CREATE INDEX IF NOT EXISTS idx_products_token ON products(token);
    CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
    CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token);
    CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
    CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
    CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status_stage);
    CREATE INDEX IF NOT EXISTS idx_bot_metrics_token ON bot_metrics(token);
    CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
    CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
    CREATE INDEX IF NOT EXISTS idx_store_analytics_token_date ON store_analytics(token, date);

    -- =====================================================
    -- VIEWS
    -- =====================================================
    CREATE OR REPLACE VIEW v_store_performance AS
    SELECT 
        s.id,
        s.store_name,
        s.username,
        COUNT(DISTINCT o.id) as total_orders,
        COALESCE(SUM(o.total_price + o.delivery_fee), 0) as total_revenue,
        COUNT(DISTINCT o.customer_id) as unique_customers,
        AVG(o.total_price) as avg_order_value,
        s.rating,
        s.total_orders as order_count,
        s.total_sales as total_sales,
        s.bot_status
    FROM stores s
    LEFT JOIN orders o ON s.token = o.token AND o.status_stage >= 1
    GROUP BY s.id, s.store_name, s.username, s.rating, s.total_orders, s.total_sales, s.bot_status;

    CREATE OR REPLACE VIEW v_daily_stats AS
    SELECT 
        DATE(created_at) as date,
        COUNT(*) as orders,
        COUNT(DISTINCT customer_id) as customers,
        COALESCE(SUM(total_price + delivery_fee), 0) as revenue,
        COALESCE(AVG(total_price + delivery_fee), 0) as avg_order
    FROM orders
    WHERE status_stage >= 1
    GROUP BY DATE(created_at)
    ORDER BY date DESC;
    """
    
    try:
        db_execute(schema)
        logger.info("✅ Database schema initialized successfully")
    except Exception as e:
        logger.error(f"❌ Schema initialization failed: {e}")
        raise

# Initialize database
init_db_pool()
init_schema()

# =================================================================================================
#                           AI ENGINE (Gemini)
# =================================================================================================

class AIEngine:
    _model = None
    _vision_model = None
    _initialized = False
    
    @classmethod
    def init(cls):
        if cls._initialized:
            return
        
        if Config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                cls._model = genai.GenerativeModel('gemini-1.5-flash')
                cls._vision_model = genai.GenerativeModel('gemini-1.5-flash')
                cls._initialized = True
                logger.info("✅ Gemini AI initialized")
            except Exception as e:
                logger.error(f"❌ Gemini AI init failed: {e}")
                cls._initialized = False
        else:
            logger.warning("⚠️ GEMINI_API_KEY not set")
            cls._initialized = False
    
    @classmethod
    def is_available(cls) -> bool:
        return cls._initialized and cls._model is not None
    
    @classmethod
    def generate_response(cls, prompt: str, context: str = "") -> Optional[str]:
        if not cls.is_available():
            return None
        try:
            response = cls._model.generate_content(f"{context}\n\n{prompt}")
            return response.text if response else None
        except Exception as e:
            logger.error(f"AI generation error: {e}")
            return None
    
    @classmethod
    def search_products(cls, query: str, products: List[Dict]) -> List[Dict]:
        if not cls.is_available():
            return None
        try:
            product_text = ""
            for p in products[:50]:
                name = p.get('name_am', '')
                price = p.get('price', 0)
                desc = p.get('desc_am', '')
                product_text += f"- ID:{p['id']}, Name:{name}, Price:{price} ETB, Desc:{desc}\n"
            
            prompt = f"""
            Analyze the user's query and find matching products.
            
            Available products:
            {product_text}
            
            User query: {query}
            
            Return ONLY the product IDs that match, separated by commas.
            If no products match, return "NONE".
            """
            
            response = cls._model.generate_content(prompt)
            result = response.text.strip()
            
            if result == "NONE" or not result:
                return []
            
            ids = re.findall(r'\d+', result)
            if not ids:
                return []
            
            placeholders = ','.join(['%s'] * len(ids))
            matched = db_execute_dict(
                f"""
                SELECT p.*, c.name_am as category_am, c.name_en as category_en
                FROM products p
                LEFT JOIN categories c ON p.category_id = c.id
                WHERE p.id IN ({placeholders}) AND p.is_active = 1
                """,
                tuple(ids)
            )
            return matched
        except Exception as e:
            logger.error(f"AI search error: {e}")
            return None
    
    @classmethod
    def verify_payment_receipt(cls, image_data: bytes, expected_amount: float) -> Tuple[bool, str]:
        if not cls.is_available():
            return False, "AI model not configured."
        try:
            img = Image.open(io.BytesIO(image_data))
            
            prompt = f"""
            Analyze this payment receipt image.
            Check:
            1. Is it a valid payment receipt?
            2. Does the amount match or exceed {expected_amount} ETB?
            3. Is the receipt genuine?
            
            Respond:
            status: VALID or INVALID
            amount_found: [number or 0]
            reason: [short explanation]
            """
            
            response = cls._vision_model.generate_content([prompt, img])
            result_text = response.text.strip()
            logger.info(f"AI Receipt Analysis: {result_text}")
            
            is_valid = "status: VALID" in result_text.upper()
            return is_valid, result_text
        except Exception as e:
            logger.error(f"Receipt verification error: {e}")
            return False, f"Error: {str(e)}"

AIEngine.init()

# =================================================================================================
#                           UTILITY FUNCTIONS
# =================================================================================================

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def verify_password(password: str, hashed: str, salt: str) -> bool:
    test_hash, _ = hash_password(password, salt)
    return test_hash == hashed

def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def calculate_delivery_fee(distance_km: float) -> float:
    if distance_km <= 0:
        return 0
    return round(Config.BASE_DELIVERY_FEE + (distance_km * Config.PER_KM_RATE), 2)

def format_currency(amount: float) -> str:
    return f"{amount:,.2f} ETB"

def format_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")

def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except:
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except:
        return default

def sanitize_input(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'[;\'"<>]', '', text)
    return text[:1000]

def get_user_lang(chat_id: int) -> str:
    try:
        result = db_execute("SELECT lang FROM user_langs WHERE chat_id = %s", (chat_id,), fetch=True)
        if result:
            return result[0][0]
    except:
        pass
    return "am"

def set_user_lang(chat_id: int, lang: str):
    try:
        db_execute(
            "INSERT INTO user_langs (chat_id, lang) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang",
            (chat_id, lang)
        )
    except Exception as e:
        logger.error(f"Set user lang error: {e}")

def get_store_info(token: str) -> Optional[Dict]:
    try:
        result = db_execute_dict("""
            SELECT id, store_name, admin_id, username, is_active, is_approved,
                   area_text, shop_description, shop_lat, shop_lng,
                   telebirr, cbebirr, bank_name, bank_account,
                   bot_status, restart_count, total_orders, total_sales
            FROM stores WHERE token = %s
        """, (token,))
        if result:
            return dict(result[0])
        return None
    except Exception as e:
        logger.error(f"Get store info error: {e}")
        return None

def update_bot_status(token: str, status: str):
    try:
        db_execute(
            "UPDATE stores SET bot_status = %s, updated_at = CURRENT_TIMESTAMP WHERE token = %s",
            (status, token)
        )
    except Exception as e:
        logger.error(f"Update bot status error: {e}")

def get_customer_info(chat_id: int) -> Optional[Dict]:
    try:
        result = db_execute_dict(
            "SELECT phone, lat, lng, address, city FROM customer_info WHERE chat_id = %s",
            (chat_id,)
        )
        if result:
            return dict(result[0])
        return None
    except Exception as e:
        logger.error(f"Get customer info error: {e}")
        return None

def save_customer_info(chat_id: int, phone: str = None, lat: float = None, lng: float = None, address: str = None):
    try:
        if phone:
            db_execute(
                "INSERT INTO customer_info (chat_id, phone) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET phone = EXCLUDED.phone",
                (chat_id, phone)
            )
        if lat is not None and lng is not None:
            db_execute(
                "INSERT INTO customer_info (chat_id, lat, lng) VALUES (%s, %s, %s) ON CONFLICT (chat_id) DO UPDATE SET lat = EXCLUDED.lat, lng = EXCLUDED.lng",
                (chat_id, lat, lng)
            )
        if address:
            db_execute(
                "INSERT INTO customer_info (chat_id, address) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET address = EXCLUDED.address",
                (chat_id, address)
            )
    except Exception as e:
        logger.error(f"Save customer info error: {e}")

# =================================================================================================
#                           FLASK WEB SERVER
# =================================================================================================

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
CORS(app)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ultimate Control Bot</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
            .container { background: white; border-radius: 20px; padding: 40px; max-width: 900px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
            h1 { color: #333; font-size: 2.5em; margin-bottom: 10px; }
            .subtitle { color: #666; margin-bottom: 30px; }
            .status { display: inline-block; padding: 8px 20px; border-radius: 30px; background: #4CAF50; color: white; font-weight: bold; margin-bottom: 20px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 30px 0; }
            .stat-item { background: #f8f8f8; padding: 20px; border-radius: 12px; text-align: center; transition: transform 0.3s; }
            .stat-item:hover { transform: translateY(-5px); }
            .stat-number { font-size: 28px; font-weight: bold; color: #667eea; }
            .stat-label { color: #888; font-size: 14px; margin-top: 5px; }
            .info { background: #e8f4fd; padding: 20px; border-radius: 12px; margin: 20px 0; }
            .info p { color: #666; line-height: 1.6; }
            .footer { text-align: center; color: #999; margin-top: 30px; font-size: 12px; }
            .commands { display: flex; gap: 10px; flex-wrap: wrap; margin: 15px 0; }
            .commands code { background: #f0f0f0; padding: 8px 15px; border-radius: 8px; font-size: 14px; color: #333; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Ultimate Control Bot</h1>
            <p class="subtitle">Manage 1000+ Shop Bots</p>
            <div class="status">🟢 Online</div>
            <div class="stats" id="stats">
                <div class="stat-item">
                    <div class="stat-number" id="total-stores">-</div>
                    <div class="stat-label">Total Stores</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="active-stores">-</div>
                    <div class="stat-label">Active Stores</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="running-bots">-</div>
                    <div class="stat-label">Running Bots</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="pending-stores">-</div>
                    <div class="stat-label">Pending Approval</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="total-orders">-</div>
                    <div class="stat-label">Total Orders</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="total-revenue">-</div>
                    <div class="stat-label">Total Revenue</div>
                </div>
            </div>
            <div class="info">
                <h3>📌 Quick Commands</h3>
                <div class="commands">
                    <code>/start</code>
                    <code>/help</code>
                    <code>/superadmin</code>
                    <code>/panel</code>
                    <code>/analytics</code>
                    <code>/bots</code>
                </div>
            </div>
            <div class="info">
                <h3>🤖 AI Features</h3>
                <p>🔍 Natural Language Search</p>
                <p>📸 AI-Powered Payment Verification</p>
                <p>💬 Smart Chat Assistant</p>
                <p>📊 Bot Performance Monitoring</p>
            </div>
            <div class="footer">
                © 2026 Ultimate Control Bot v6.0 | Powered by Gemini AI | Supports 1000+ Bots
            </div>
        </div>
        <script>
            async function loadStats() {
                try {
                    const response = await fetch('/api/stats');
                    const data = await response.json();
                    document.getElementById('total-stores').textContent = data.total_stores || 0;
                    document.getElementById('active-stores').textContent = data.active_stores || 0;
                    document.getElementById('running-bots').textContent = data.running_bots || 0;
                    document.getElementById('pending-stores').textContent = data.pending_approval || 0;
                    document.getElementById('total-orders').textContent = data.total_orders || 0;
                    document.getElementById('total-revenue').textContent = data.total_revenue ? data.total_revenue.toFixed(2) + ' ETB' : '0 ETB';
                } catch(e) {
                    console.error('Stats error:', e);
                }
            }
            loadStats();
            setInterval(loadStats, 30000);
        </script>
    </body>
    </html>
    """

@app.route('/api/stats')
def api_stats():
    try:
        total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
        pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
        active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
        running = db_execute("SELECT COUNT(*) FROM stores WHERE bot_status = 'running'", fetch=True)[0][0]
        total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
        revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
        
        return jsonify({
            "total_stores": total_stores,
            "pending_approval": pending,
            "active_stores": active,
            "running_bots": running,
            "total_orders": total_orders,
            "total_revenue": float(revenue)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/bots')
def api_bots():
    try:
        bots = db_execute_dict("""
            SELECT id, store_name, username, is_active, is_approved, bot_status, 
                   total_orders, total_sales, created_at
            FROM stores ORDER BY created_at DESC LIMIT 100
        """)
        return jsonify([dict(b) for b in bots])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health')
def api_health():
    try:
        db_execute("SELECT 1", fetch=True)
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "ai_available": AIEngine.is_available(),
            "total_bots": len(running_tokens) if 'running_tokens' in globals() else 0
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

def run_flask():
    app.run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)

threading.Thread(target=run_flask, daemon=True).start()
logger.info(f"✅ Web server running on {Config.HOST}:{Config.PORT}")

# =================================================================================================
#                           BOT MANAGER - 1000+ Bots
# =================================================================================================

running_tokens = set()
running_lock = threading.Lock()
bot_threads = {}
bot_threads_lock = threading.Lock()
bot_restart_tracker = defaultdict(int)
bot_restart_lock = threading.Lock()

class BotManager:
    """ማዕከላዊ የቦት አስተዳደር ክፍል - 1000+ ቦቶችን ይደግፋል"""
    
    _instance = None
    _lock = threading.Lock()
    _executor = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self._executor = ThreadPoolExecutor(max_workers=Config.DATABASE_POOL_MAX * 2)
        self._health_check_thread = None
        self._running = True
        self._start_health_check()
        logger.info("✅ Bot Manager initialized (supports 1000+ bots)")
    
    def _start_health_check(self):
        def health_check_loop():
            while self._running:
                try:
                    self._check_all_bots()
                    time.sleep(Config.BOT_HEALTH_CHECK_INTERVAL)
                except Exception as e:
                    logger.error(f"Health check error: {e}")
                    time.sleep(10)
        
        self._health_check_thread = threading.Thread(target=health_check_loop, daemon=True)
        self._health_check_thread.start()
    
    def _check_all_bots(self):
        try:
            bots = db_execute_dict("""
                SELECT token, store_name, bot_status, is_active, is_approved
                FROM stores 
                WHERE is_approved = 1
            """)
            
            current_running = set(running_tokens)
            should_run = set()
            
            for bot in bots:
                if bot['is_active'] == 1 and bot['is_approved'] == 1:
                    should_run.add(bot['token'])
            
            to_start = should_run - current_running
            for token in to_start:
                logger.info(f"🔄 Auto-restarting bot: {token[:15]}...")
                self.start_bot(token)
            
            to_stop = current_running - should_run
            for token in to_stop:
                logger.info(f"🛑 Stopping bot: {token[:15]}...")
                self.stop_bot(token)
            
            for bot in bots:
                status = 'running' if bot['token'] in running_tokens else 'stopped'
                if bot['bot_status'] != status:
                    update_bot_status(bot['token'], status)
                    
        except Exception as e:
            logger.error(f"Health check error: {e}")
    
    def start_bot(self, token: str) -> bool:
        with running_lock:
            if token in running_tokens:
                return True
        
        try:
            store = get_store_info(token)
            if not store or store.get('is_approved', 0) != 1 or store.get('is_active', 1) != 1:
                logger.warning(f"Cannot start bot {token[:15]}: not approved or inactive")
                return False
            
            with bot_restart_lock:
                if bot_restart_tracker[token] >= Config.MAX_BOT_RESTARTS:
                    logger.warning(f"Bot {token[:15]} has exceeded max restarts")
                    return False
            
            success = self._start_bot_thread(token)
            
            if success:
                with running_lock:
                    running_tokens.add(token)
                update_bot_status(token, 'running')
                with bot_restart_lock:
                    bot_restart_tracker[token] = 0
                logger.info(f"✅ Bot started: {token[:15]}...")
                return True
            else:
                with bot_restart_lock:
                    bot_restart_tracker[token] += 1
                return False
                
        except Exception as e:
            logger.error(f"Failed to start bot {token[:15]}: {e}")
            return False
    
    def _start_bot_thread(self, token: str) -> bool:
        try:
            with bot_threads_lock:
                if token in bot_threads:
                    return True
                
                def run_bot():
                    try:
                        setup_bot_handlers(token)
                    except Exception as e:
                        logger.error(f"Bot {token[:15]} crashed: {e}")
                        time.sleep(Config.BOT_RESTART_DELAY)
                        self.start_bot(token)
                
                thread = threading.Thread(target=run_bot, daemon=True, name=f"Bot_{token[:10]}")
                thread.start()
                bot_threads[token] = thread
                return True
        except Exception as e:
            logger.error(f"Thread start error: {e}")
            return False
    
    def stop_bot(self, token: str) -> bool:
        with running_lock:
            if token not in running_tokens:
                return True
            
            running_tokens.discard(token)
            update_bot_status(token, 'stopped')
            
            with bot_threads_lock:
                if token in bot_threads:
                    del bot_threads[token]
            
            logger.info(f"🛑 Bot stopped: {token[:15]}...")
            return True
    
    def restart_bot(self, token: str) -> bool:
        self.stop_bot(token)
        time.sleep(1)
        return self.start_bot(token)
    
    def get_all_bots(self) -> List[Dict]:
        try:
            return db_execute_dict("""
                SELECT id, store_name, username, is_active, is_approved, 
                       bot_status, total_orders, total_sales, created_at
                FROM stores
                ORDER BY created_at DESC
                LIMIT 1000
            """)
        except Exception as e:
            logger.error(f"Get all bots error: {e}")
            return []
    
    def get_bot_stats(self) -> Dict:
        try:
            total = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
            running = db_execute("SELECT COUNT(*) FROM stores WHERE bot_status = 'running'", fetch=True)[0][0]
            stopped = db_execute("SELECT COUNT(*) FROM stores WHERE bot_status = 'stopped'", fetch=True)[0][0]
            pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
            
            return {
                "total": total,
                "running": running,
                "stopped": stopped,
                "pending": pending
            }
        except Exception as e:
            logger.error(f"Get bot stats error: {e}")
            return {"total": 0, "running": 0, "stopped": 0, "pending": 0}
    
    def shutdown(self):
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=False)
        logger.info("🛑 Bot Manager shutting down")

bot_manager = BotManager()

# =================================================================================================
#                           SHOP BOT ENGINE
# =================================================================================================

def setup_bot_handlers(token: str):
    """የሱቅ ቦት ሃንድለሮች ማዘጋጀት"""
    bot = telebot.TeleBot(token, threaded=False)
    
    try:
        bot.remove_webhook()
    except:
        pass
    
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        chat_id = message.chat.id
        store = get_store_info(token)
        
        if not store:
            bot.send_message(chat_id, "🏪 ይህ ቦት ገና አልተመዘገበም።")
            return
        
        if store.get('is_approved', 0) != 1:
            bot.send_message(chat_id, f"⏳ ሱቅ **{store.get('store_name', '')}** ገና አልጸደቀም።")
            return
        
        if not store.get('is_active', 1):
            bot.send_message(chat_id, "❌ ይህ ሱቅ ንቁ አይደለም።")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data=f"lang_am_{token}"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data=f"lang_en_{token}")
        )
        
        bot.send_message(
            chat_id,
            f"🌐 **{store.get('store_name', '')}**\n\nቋንቋ ይምረጡ:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
    def handle_lang(call):
        _, lang, bot_token = call.data.split("_")
        if bot_token != token:
            return
        
        chat_id = call.message.chat.id
        set_user_lang(chat_id, lang)
        
        bot.delete_message(chat_id, call.message.message_id)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("🛍️ ምርቶች"),
            types.KeyboardButton("🛒 ጋሪ")
        )
        markup.add(
            types.KeyboardButton("🔍 ፍለጋ"),
            types.KeyboardButton("📦 ትዕዛዝ")
        )
        markup.add(
            types.KeyboardButton("📍 መረጃ"),
            types.KeyboardButton("❓ እርዳታ")
        )
        
        bot.send_message(chat_id, "እንኳን ወደ ሱቅ በደህና መጡ! 👋", reply_markup=markup)
    
    @bot.message_handler(func=lambda m: m.text == "🛍️ ምርቶች")
    def handle_products(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name_am, name_en, price, stock, image_url
                    FROM products
                    WHERE token = %s AND stock > 0 AND is_active = 1
                    ORDER BY id LIMIT 20
                """, (token,))
                products = cur.fetchall()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not products:
            bot.send_message(chat_id, "🛍️ ምንም ምርት የለም")
            return
        
        for product in products:
            p_id, name_am, name_en, price, stock, image_url = product
            name = name_am if lang == "am" else name_en
            
            text = f"📦 **{name}**\n💰 {format_currency(price)}\n📌 ✅ ይገኛል"
            
            markup = types.InlineKeyboardMarkup()
            if stock > 0:
                markup.add(types.InlineKeyboardButton("🛒 ወደ ጋሪ ጨምር", callback_data=f"add_{p_id}"))
            
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    @bot.message_handler(func=lambda m: m.text == "🛒 ጋሪ")
    def handle_cart(message):
        chat_id = message.chat.id
        bot.send_message(chat_id, "🛒 ጋሪዎ ባዶ ነው")
    
    @bot.message_handler(func=lambda m: m.text == "🔍 ፍለጋ")
    def handle_search(message):
        chat_id = message.chat.id
        msg = bot.send_message(chat_id, "🔍 የምርት ስም ያስገቡ:")
        bot.register_next_step_handler(msg, lambda m: process_search(m, token, bot))
    
    def process_search(message, token, bot):
        query = message.text.strip()
        chat_id = message.chat.id
        
        if not query:
            bot.send_message(chat_id, "❌ እባክዎ ፍለጋ ቃል ያስገቡ")
            return
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name_am, name_en, price, stock, image_url
                    FROM products
                    WHERE token = %s AND is_active = 1 AND stock > 0
                    AND (name_am ILIKE %s OR name_en ILIKE %s)
                    LIMIT 10
                """, (token, f"%{query}%", f"%{query}%"))
                products = cur.fetchall()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not products:
            bot.send_message(chat_id, f"🔍 '{query}' አልተገኘም")
            return
        
        for p in products:
            name = p.get('name_am', '')
            price = p.get('price', 0)
            image_url = p.get('image_url')
            
            text = f"📦 **{name}**\n💰 {format_currency(price)}"
            
            markup = types.InlineKeyboardMarkup()
            if p.get('stock', 0) > 0:
                markup.add(types.InlineKeyboardButton("🛒 ወደ ጋሪ ጨምር", callback_data=f"add_{p['id']}"))
            
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    @bot.message_handler(func=lambda m: m.text == "📦 ትዕዛዝ")
    def handle_track(message):
        chat_id = message.chat.id
        msg = bot.send_message(chat_id, "🔢 የትዕዛዝ ቁጥር ያስገቡ:")
        bot.register_next_step_handler(msg, lambda m: process_track(m, token, bot))
    
    def process_track(message, token, bot):
        try:
            order_id = int(message.text.strip())
            chat_id = message.chat.id
            
            conn = None
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT status_am, total_price, created_at
                        FROM orders
                        WHERE id = %s AND token = %s
                    """, (order_id, token))
                    order = cur.fetchone()
            finally:
                if conn:
                    put_db_connection(conn)
            
            if not order:
                bot.send_message(chat_id, "❌ ትዕዛዝ አልተገኘም")
                return
            
            status, price, created = order
            text = f"📦 **ትዕዛዝ #{order_id}**\n"
            text += f"📌 ሁኔታ: {status}\n"
            text += f"💵 ድምር: {format_currency(price)}\n"
            text += f"📅 ቀን: {format_date(created)}"
            
            bot.send_message(chat_id, text, parse_mode="Markdown")
        except ValueError:
            bot.send_message(message.chat.id, "❌ የተሳሳተ ቁጥር!")
    
    @bot.message_handler(func=lambda m: m.text == "📍 መረጃ")
    def handle_info(message):
        chat_id = message.chat.id
        store = get_store_info(token)
        
        if not store:
            return
        
        text = f"🏪 **{store.get('store_name', '')}**\n\n"
        if store.get('shop_description'):
            text += f"📝 {store['shop_description']}\n\n"
        if store.get('area_text'):
            text += f"📍 {store['area_text']}\n"
        if store.get('username'):
            text += f"👤 @{store['username']}\n"
        text += f"⭐ {store.get('rating', 0)}/5.0"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
    
    @bot.message_handler(func=lambda m: m.text == "❓ እርዳታ")
    def handle_help(message):
        text = """
❓ **እርዳታ**

🛍️ ምርቶች - የሱቁን ምርቶች ይመልከቱ
🛒 ጋሪ - የእርስዎን ጋሪ ይመልከቱ
🔍 ፍለጋ - ምርቶችን ይፈልጉ
📦 ትዕዛዝ - ትዕዛዝዎን ይከታተሉ
📍 መረጃ - ስለ ሱቁ መረጃ

📞 ለተጨማሪ እርዳታ አስተዳዳሪውን ያነጋግሩ
"""
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    
    @bot.message_handler(func=lambda m: m.text == "🔙 ወደ ኋላ")
    def handle_back(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("🛍️ ምርቶች"),
            types.KeyboardButton("🛒 ጋሪ")
        )
        markup.add(
            types.KeyboardButton("🔍 ፍለጋ"),
            types.KeyboardButton("📦 ትዕዛዝ")
        )
        markup.add(
            types.KeyboardButton("📍 መረጃ"),
            types.KeyboardButton("❓ እርዳታ")
        )
        
        bot.send_message(chat_id, "🔙 ወደ ዋና ሜኑ", reply_markup=markup)
    
    @bot.message_handler(func=lambda m: True)
    def handle_ai(message):
        if not AIEngine.is_available():
            return
        
        chat_id = message.chat.id
        store = get_store_info(token)
        
        if not store:
            return
        
        bot.send_chat_action(chat_id, 'typing')
        context = f"You are an AI assistant for '{store.get('store_name', '')}' store. Respond in Amharic or English."
        response = AIEngine.generate_response(message.text, context)
        
        if response:
            bot.reply_to(message, response[:1000])
    
    def _run_bot():
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                logger.error(f"Bot {token[:15]} polling error: {e}")
                time.sleep(Config.BOT_RESTART_DELAY)
    
    threading.Thread(target=_run_bot, daemon=True).start()

# =================================================================================================
#                           CONTROL BOT - Super Admin
# =================================================================================================

class ControlBot:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.bot = telebot.TeleBot(Config.CONTROL_BOT_TOKEN, threaded=False)
        self.sessions = {}
        self.login_attempts = {}
        self.reg_states = {}
        
        self.sessions_lock = threading.Lock()
        self.login_lock = threading.Lock()
        self.reg_lock = threading.Lock()
        
        try:
            self.bot.remove_webhook()
        except:
            pass
        
        self._register_handlers()
        self._start_polling()
        logger.info("✅ Control Bot initialized")
    
    def _register_handlers(self):
        
        @self.bot.message_handler(commands=['start', 'help'])
        def cmd_start(message):
            chat_id = message.chat.id
            
            text = """
👋 **እንኳን ወደ Ultimate Control Bot በደህና መጡ!**

📌 **አዲስ ሱቅ ለመመዝገብ:**
1️⃣ @BotFather ላይ `/newbot` በማድረግ ቦት ይፍጠሩ
2️⃣ Token ከተቀበሉ '📝 አዲስ ሱቅ መዝግብ' ይጫኑ
3️⃣ 5 ደረጃዎችን ይሙሉ

📌 **ሱቆችዎን ለማየት:** 🏪 ሱቆቼ
📌 **ሁሉንም ሱቆች ለማየት:** `/bots`

👑 **Super Admin ከሆኑ:** `/superadmin`

🤖 **AI Features:**
- 🔍 Natural Language Search
- 📸 AI-Powered Payment Verification
- 💬 Smart Chat Assistant
- 📊 1000+ Bot Management
"""
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add(
                types.KeyboardButton("📝 አዲስ ሱቅ መዝግብ"),
                types.KeyboardButton("🏪 ሱቆቼ")
            )
            markup.add(
                types.KeyboardButton("🔍 ሱቆችን ፈልግ"),
                types.KeyboardButton("❓ እርዳታ")
            )
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        
        @self.bot.message_handler(commands=['superadmin'])
        def cmd_superadmin(message):
            chat_id = message.chat.id
            
            if not Config.SUPER_ADMIN_PASSWORD:
                self.bot.reply_to(message, "❌ SUPER_ADMIN_PASSWORD not set!")
                return
            
            if Config.SUPER_ADMIN_ID != 0 and chat_id != Config.SUPER_ADMIN_ID:
                self.bot.reply_to(message, "❌ መብት የለዎትም!")
                return
            
            with self.login_lock:
                attempt = self.login_attempts.get(chat_id, {"count": 0, "lockout_until": 0})
                if time.time() < attempt["lockout_until"]:
                    remaining = int(attempt["lockout_until"] - time.time())
                    self.bot.reply_to(message, f"🔒 እገዳ ላይ ነዎት! ከ {remaining} ሰከንድ በኋላ ይሞክሩ።")
                    return
            
            msg = self.bot.send_message(
                chat_id,
                "🔐 **የ Super Admin የይለፍ ቃል ያስገቡ:**",
                parse_mode="Markdown"
            )
            self.bot.register_next_step_handler(msg, self._process_super_login)
        
        @self.bot.message_handler(commands=['panel'])
        def cmd_panel(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_dashboard(message)
        
        @self.bot.message_handler(commands=['analytics'])
        def cmd_analytics(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_analytics(message)
        
        @self.bot.message_handler(commands=['bots'])
        def cmd_bots(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_all_bots(message)
        
        @self.bot.message_handler(commands=['broadcast'])
        def cmd_broadcast(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_broadcast_menu(message)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("dash_"))
        def handle_dashboard(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            
            action = call.data.split("_")[1]
            
            if action == "refresh":
                self._show_dashboard(call.message)
                self.bot.answer_callback_query(call.id, "🔄 Refreshed!")
            elif action == "pending":
                self.bot.answer_callback_query(call.id)
                self._show_pending_stores(call.message)
            elif action == "all":
                self.bot.answer_callback_query(call.id)
                self._show_all_bots(call.message)
            elif action == "stats":
                self.bot.answer_callback_query(call.id)
                self._show_analytics(call.message)
            elif action == "broadcast":
                self.bot.answer_callback_query(call.id)
                self._show_broadcast_menu(call.message)
            elif action == "back":
                self.bot.answer_callback_query(call.id)
                try:
                    self.bot.delete_message(chat_id, call.message.message_id)
                except:
                    pass
                self._show_dashboard(call.message)
            elif action == "logout":
                self.bot.answer_callback_query(call.id)
                self._logout(chat_id)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sapprove_"))
        def handle_approve(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            store_id = int(call.data.split("_")[1])
            self._approve_store(chat_id, store_id, call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sreject_"))
        def handle_reject(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            store_id = int(call.data.split("_")[1])
            self._reject_store(chat_id, store_id, call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sblock_"))
        def handle_block(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            store_id = int(call.data.split("_")[1])
            self._block_store(chat_id, store_id, call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sunblock_"))
        def handle_unblock(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            store_id = int(call.data.split("_")[1])
            self._unblock_store(chat_id, store_id, call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("startbot_"))
        def handle_start_bot(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            store_id = int(call.data.split("_")[1])
            self._start_bot(chat_id, store_id, call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("stopbot_"))
        def handle_stop_bot(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            store_id = int(call.data.split("_")[1])
            self._stop_bot(chat_id, store_id, call)
        
        @self.bot.message_handler(func=lambda m: m.text == "📝 አዲስ ሱቅ መዝግብ")
        def handle_register(message):
            self._start_registration(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "🏪 ሱቆቼ")
        def handle_my_stores(message):
            self._show_my_stores(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "🔍 ሱቆችን ፈልግ")
        def handle_search_stores(message):
            chat_id = message.chat.id
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📝 በስም ፈልግ", callback_data="search_name"),
                types.InlineKeyboardButton("📍 በአካባቢ ፈልግ", callback_data="search_location")
            )
            self.bot.send_message(chat_id, "🔍 **ሱቆችን ፈልግ**", reply_markup=markup)
        
        @self.bot.message_handler(func=lambda m: m.text == "❓ እርዳታ")
        def handle_help(message):
            cmd_start(message)
        
        @self.bot.message_handler(content_types=['location'])
        def handle_location(message):
            self._search_by_location(message)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("search_"))
        def handle_search(call):
            chat_id = call.message.chat.id
            
            if call.data == "search_name":
                msg = self.bot.send_message(chat_id, "📝 የሱቅ ስም ያስገቡ:")
                self.bot.register_next_step_handler(msg, self._search_by_name)
            elif call.data == "search_location":
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
                self.bot.send_message(chat_id, "📍 አካባቢ ያጋሩ:", reply_markup=markup)
        
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 1)
        def reg_step_token(message):
            self._process_reg_token(message)
        
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 2)
        def reg_step_name(message):
            self._process_reg_name(message)
        
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 3)
        def reg_step_password(message):
            self._process_reg_password(message)
        
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 4)
        def reg_step_location(message):
            self._process_reg_location(message)
        
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 5)
        def reg_step_description(message):
            self._process_reg_description(message)
    
    def _is_super_admin(self, chat_id: int) -> bool:
        with self.sessions_lock:
            return chat_id in self.sessions and time.time() < self.sessions[chat_id]
    
    def _get_reg_state(self, chat_id: int, key: str = None):
        with self.reg_lock:
            state = self.reg_states.get(chat_id, {})
            if key:
                return state.get(key)
            return state
    
    def _set_reg_state(self, chat_id: int, key: str, value: Any):
        with self.reg_lock:
            if chat_id not in self.reg_states:
                self.reg_states[chat_id] = {}
            self.reg_states[chat_id][key] = value
    
    def _clear_reg_state(self, chat_id: int):
        with self.reg_lock:
            self.reg_states.pop(chat_id, None)
    
    def _get_main_menu(self):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("📝 አዲስ ሱቅ መዝግብ"),
            types.KeyboardButton("🏪 ሱቆቼ")
        )
        markup.add(
            types.KeyboardButton("🔍 ሱቆችን ፈልግ"),
            types.KeyboardButton("❓ እርዳታ")
        )
        return markup
    
    def _get_dashboard_markup(self):
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("⏳ ያልጸደቁ", callback_data="dash_pending"),
            types.InlineKeyboardButton("📊 ስታቲስቲክስ", callback_data="dash_stats")
        )
        markup.add(
            types.InlineKeyboardButton("📢 ማሰራጨት", callback_data="dash_broadcast"),
            types.InlineKeyboardButton("🔄 አዘምን", callback_data="dash_refresh")
        )
        markup.add(types.InlineKeyboardButton("🚪 ውጣ", callback_data="dash_logout"))
        return markup
    
    def _process_super_login(self, message):
        chat_id = message.chat.id
        password = message.text.strip()
        
        if password == Config.SUPER_ADMIN_PASSWORD:
            with self.sessions_lock:
                self.sessions[chat_id] = time.time() + Config.SESSION_TIMEOUT
            with self.login_lock:
                self.login_attempts[chat_id] = {"count": 0, "lockout_until": 0}
            
            self.bot.send_message(
                chat_id,
                "🔓 **እንኳን ወደ Super Admin ፓነል በደህና መጡ!**\n\n🤖 AI-Powered 1000+ Bot Management System",
                parse_mode="Markdown"
            )
            self._show_dashboard(message)
            logger.audit(chat_id, "super_admin_login", {"success": True})
        else:
            with self.login_lock:
                attempt = self.login_attempts.setdefault(chat_id, {"count": 0, "lockout_until": 0})
                attempt["count"] += 1
                
                if attempt["count"] >= Config.MAX_LOGIN_ATTEMPTS:
                    attempt["lockout_until"] = time.time() + Config.LOCKOUT_DURATION
                    self.bot.send_message(
                        chat_id,
                        f"❌ {Config.MAX_LOGIN_ATTEMPTS} ጊዜ ተሳስተዋል። ለ{Config.LOCKOUT_DURATION//60} ደቂቃ ታግደዋል።"
                    )
                else:
                    left = Config.MAX_LOGIN_ATTEMPTS - attempt["count"]
                    self.bot.send_message(
                        chat_id,
                        f"❌ የተሳሳተ የይለፍ ቃል! {left} ሙከራዎች ቀርተውዎታል።"
                    )
    
    def _logout(self, chat_id: int):
        with self.sessions_lock:
            self.sessions.pop(chat_id, None)
        self.bot.send_message(chat_id, "🔒 ከአስተዳደር ወጥተዋል።", reply_markup=self._get_main_menu())
    
    def _show_dashboard(self, message):
        chat_id = message.chat.id
        
        try:
            total = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
            pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
            active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
            running = db_execute("SELECT COUNT(*) FROM stores WHERE bot_status = 'running'", fetch=True)[0][0]
            total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
            revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
            
            text = f"""
🎛 **Super Admin Dashboard**

🏪 Total Stores: **{total}**
⏳ Pending Approval: **{pending}**
🟢 Active Stores: **{active}**
🤖 Running Bots: **{running}**
🧾 Total Orders: **{total_orders}**
💰 Total Revenue: **{format_currency(revenue)}**

🤖 AI Status: {'✅ Active' if AIEngine.is_available() else '❌ Disabled'}

📌 ርምጫ ይምረጡ:
"""
            
            self.bot.send_message(
                chat_id,
                text,
                reply_markup=self._get_dashboard_markup(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _show_pending_stores(self, message):
        chat_id = message.chat.id
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, username, area_text, created_at
                FROM stores WHERE is_approved = 0 AND is_active = 1
                ORDER BY created_at DESC
            """)
            
            if not stores:
                self.bot.send_message(chat_id, "✅ ምንም ያልተጸደቁ ሱቆች የሉም!")
                return
            
            for store in stores:
                text = f"""
🏪 **{store['store_name']}**
🆔 #{store['id']}
👤 @{store['username'] or 'ስም'}
📍 {store['area_text'] or 'አልተዘጋጀም'}
📅 {format_date(store['created_at'])}
"""
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"sapprove_{store['id']}"),
                    types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"sreject_{store['id']}")
                )
                markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
                
                self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Pending stores error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _show_all_bots(self, message):
        chat_id = message.chat.id
        
        try:
            bots = db_execute_dict("""
                SELECT id, store_name, username, is_active, is_approved,
                       bot_status, total_orders, total_sales, created_at
                FROM stores ORDER BY created_at DESC LIMIT 50
            """)
            
            if not bots:
                self.bot.send_message(chat_id, "📜 ምንም ቦት የለም!")
                return
            
            text = "🤖 **ሁሉም ቦቶች**\n\n"
            for bot in bots:
                status = "🟢" if bot['is_active'] else "🔴"
                approved = "✅" if bot['is_approved'] else "⏳"
                bot_status = "▶️" if bot['bot_status'] == 'running' else "⏹️"
                
                text += f"""
{status} {approved} {bot_status} **{bot['store_name']}**
  🆔 #{bot['id']} | 👤 @{bot['username'] or 'ስም'}
  📦 {bot['total_orders'] or 0} ትዕዛዝ | 💰 {format_currency(bot['total_sales'] or 0)}
  📅 {format_date(bot['created_at'])}
"""
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("▶️ ማስነሳት", callback_data="startbot_menu"),
                types.InlineKeyboardButton("⏹️ ማቆም", callback_data="stopbot_menu")
            )
            markup.add(
                types.InlineKeyboardButton("🔴 ማገድ", callback_data="block_menu"),
                types.InlineKeyboardButton("🟢 ማንቃት", callback_data="unblock_menu")
            )
            markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"All bots error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _show_analytics(self, message):
        chat_id = message.chat.id
        
        try:
            stats = bot_manager.get_bot_stats()
            
            total_stores = stats['total']
            pending = stats['pending']
            active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
            running = stats['running']
            total_products = db_execute("SELECT COUNT(*) FROM products", fetch=True)[0][0]
            total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
            revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
            
            top_stores = db_execute_dict("""
                SELECT s.store_name, COUNT(o.id) as orders,
                       COALESCE(SUM(o.total_price + o.delivery_fee), 0) as revenue
                FROM stores s
                LEFT JOIN orders o ON s.token = o.token AND o.status_stage >= 1
                GROUP BY s.id, s.store_name
                ORDER BY revenue DESC LIMIT 5
            """)
            
            text = f"""
📊 **System Analytics**

🤖 **Bot Statistics**
  • Total Bots: {total_stores}
  • Running: {running}
  • Stopped: {stats['stopped']}
  • Pending: {pending}
  • Active: {active}

📦 **Products:** {total_products}
🧾 **Orders:** {total_orders}
💰 **Revenue:** {format_currency(revenue)}

🤖 **AI Status:** {'✅ Active' if AIEngine.is_available() else '❌ Disabled'}

🏆 **Top Stores:**
"""
            for i, store in enumerate(top_stores, 1):
                text += f"  {i}. {store['store_name']} - {store['orders']} orders - {format_currency(store['revenue'])}\n"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Analytics error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _show_broadcast_menu(self, message):
        chat_id = message.chat.id
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📢 ለሱቅ ባለቤቶች", callback_data="broadcast_owners"),
            types.InlineKeyboardButton("👥 ለደንበኞች", callback_data="broadcast_customers"),
            types.InlineKeyboardButton("👤 ለአንድ ተጠቃሚ", callback_data="broadcast_user"),
            types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back")
        )
        
        self.bot.send_message(
            chat_id,
            "📢 **Broadcast Message**\n\nWho do you want to send the message to?",
            reply_markup=markup
        )
    
    def _broadcast_to_all(self, message, target):
        chat_id = message.chat.id
        msg_text = message.text
        
        try:
            if target == "owners":
                users = db_execute_dict("SELECT DISTINCT admin_id FROM stores WHERE admin_id > 0 AND is_approved = 1")
            else:
                users = db_execute_dict("SELECT DISTINCT customer_id FROM orders")
            
            if not users:
                self.bot.reply_to(message, "❌ No users found!")
                return
            
            self.bot.reply_to(message, f"⏳ Sending to {len(users)} users...")
            
            success = 0
            failed = 0
            
            for user in users:
                user_id = user.get('admin_id') or user.get('customer_id')
                if not user_id:
                    continue
                try:
                    self.bot.send_message(
                        user_id,
                        f"📢 **System Broadcast**\n\n{msg_text}"
                    )
                    success += 1
                    time.sleep(0.05)
                except:
                    failed += 1
            
            self.bot.send_message(
                chat_id,
                f"✅ Broadcast complete!\n\n✅ Success: {success}\n❌ Failed: {failed}"
            )
            
            logger.audit(chat_id, "broadcast_sent", {
                "target": target,
                "success": success,
                "failed": failed
            })
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            self.bot.reply_to(message, f"❌ Error: {e}")
    
    def _broadcast_to_user(self, message):
        chat_id = message.chat.id
        
        try:
            user_id = int(message.text.strip())
        except:
            self.bot.reply_to(message, "❌ Invalid user ID!")
            return
        
        msg = self.bot.send_message(chat_id, "📝 Enter the message to send:")
        self.bot.register_next_step_handler(
            msg,
            lambda m: self._send_single_message(m, user_id)
        )
    
    def _send_single_message(self, message, user_id):
        chat_id = message.chat.id
        msg_text = message.text
        
        try:
            self.bot.send_message(
                user_id,
                f"📢 **System Broadcast**\n\n{msg_text}"
            )
            self.bot.reply_to(message, f"✅ Message sent to user {user_id}!")
            logger.audit(chat_id, "single_message_sent", {"user_id": user_id})
        except Exception as e:
            self.bot.reply_to(message, f"❌ Failed to send: {e}")
    
    def _approve_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT token, store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ Store not found!")
                return
            
            store = store[0]
            db_execute("UPDATE stores SET is_approved = 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (store_id,))
            bot_manager.start_bot(store['token'])
            
            try:
                self.bot.send_message(
                    store['admin_id'],
                    f"🎉 **Your store has been approved!**\n\n🏪 {store['store_name']}"
                )
            except:
                pass
            
            if call:
                self.bot.edit_message_text(
                    f"✅ Store #{store_id} approved!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "Approved!")
            
            logger.audit(chat_id, "store_approved", {"store_id": store_id, "store_name": store['store_name']})
        except Exception as e:
            logger.error(f"Approve store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _reject_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ Store not found!")
                return
            
            store = store[0]
            db_execute("DELETE FROM stores WHERE id = %s", (store_id,))
            
            try:
                self.bot.send_message(
                    store['admin_id'],
                    f"❌ Your store **{store['store_name']}** has been rejected."
                )
            except:
                pass
            
            if call:
                self.bot.edit_message_text(
                    f"❌ Store #{store_id} rejected!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "Rejected!")
            
            logger.audit(chat_id, "store_rejected", {"store_id": store_id, "store_name": store['store_name']})
        except Exception as e:
            logger.error(f"Reject store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _block_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT store_name, admin_id, token FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ Store not found!")
                return
            
            store = store[0]
            db_execute("UPDATE stores SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (store_id,))
            bot_manager.stop_bot(store['token'])
            
            try:
                self.bot.send_message(store['admin_id'], f"🔴 Your store **{store['store_name']}** has been blocked.")
            except:
                pass
            
            if call:
                self.bot.edit_message_text(
                    f"🔴 Store #{store_id} blocked!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "Blocked!")
            
            logger.audit(chat_id, "store_blocked", {"store_id": store_id, "store_name": store['store_name']})
        except Exception as e:
            logger.error(f"Block store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _unblock_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT store_name, admin_id, token FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ Store not found!")
                return
            
            store = store[0]
            db_execute("UPDATE stores SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (store_id,))
            bot_manager.start_bot(store['token'])
            
            try:
                self.bot.send_message(store['admin_id'], f"🟢 Your store **{store['store_name']}** has been unblocked.")
            except:
                pass
            
            if call:
                self.bot.edit_message_text(
                    f"🟢 Store #{store_id} unblocked!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "Unblocked!")
            
            logger.audit(chat_id, "store_unblocked", {"store_id": store_id, "store_name": store['store_name']})
        except Exception as e:
            logger.error(f"Unblock store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _start_bot(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT store_name, admin_id, token FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ Store not found!")
                return
            
            store = store[0]
            success = bot_manager.start_bot(store['token'])
            
            if success:
                if call:
                    self.bot.edit_message_text(
                        f"▶️ Bot started!\n🏪 {store['store_name']}",
                        chat_id,
                        call.message.message_id
                    )
                    self.bot.answer_callback_query(call.id, "Started!")
            else:
                if call:
                    self.bot.edit_message_text(
                        f"❌ Failed to start bot!\n🏪 {store['store_name']}",
                        chat_id,
                        call.message.message_id
                    )
                    self.bot.answer_callback_query(call.id, "Failed!")
        except Exception as e:
            logger.error(f"Start bot error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _stop_bot(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT store_name, admin_id, token FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ Store not found!")
                return
            
            store = store[0]
            success = bot_manager.stop_bot(store['token'])
            
            if success:
                if call:
                    self.bot.edit_message_text(
                        f"⏹️ Bot stopped!\n🏪 {store['store_name']}",
                        chat_id,
                        call.message.message_id
                    )
                    self.bot.answer_callback_query(call.id, "Stopped!")
            else:
                if call:
                    self.bot.edit_message_text(
                        f"❌ Failed to stop bot!\n🏪 {store['store_name']}",
                        chat_id,
                        call.message.message_id
                    )
                    self.bot.answer_callback_query(call.id, "Failed!")
        except Exception as e:
            logger.error(f"Stop bot error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _start_registration(self, message):
        chat_id = message.chat.id
        self._clear_reg_state(chat_id)
        self._set_reg_state(chat_id, "step", 1)
        self._set_reg_state(chat_id, "data", {})
        
        msg = self.bot.send_message(
            chat_id,
            "📝 **Step 1/5: Bot Token**\n\nEnter the token you got from @BotFather:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_token)
    
    def _process_reg_token(self, message):
        chat_id = message.chat.id
        token = message.text.strip()
        
        try:
            test_bot = telebot.TeleBot(token)
            bot_info = test_bot.get_me()
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            self.bot.reply_to(message, "❌ Invalid token! Please check and try again.")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["token"] = token
        data["bot_username"] = bot_info.username
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 2)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ Token verified! 👤 @{bot_info.username}\n\n"
            "📝 **Step 2/5: Store Name**\n\nEnter your store name:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_name)
    
    def _process_reg_name(self, message):
        chat_id = message.chat.id
        name = sanitize_input(message.text.strip())
        
        if not name or len(name) < 3:
            self.bot.reply_to(message, "❌ Store name must be at least 3 characters!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["store_name"] = name
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 3)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ Store name: **{name}**\n\n"
            "📝 **Step 3/5: Password**\n\n"
            "Enter a password for store admin (min 8 characters):"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_password)
    
    def _process_reg_password(self, message):
        chat_id = message.chat.id
        password = message.text.strip()
        
        if len(password) < 8:
            self.bot.reply_to(message, "❌ Password must be at least 8 characters!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["password"] = password
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 4)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("📍 Share Location", request_location=True))
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ Password received\n\n"
            "📝 **Step 4/5: Store Location**\n\n"
            "Share your store location or enter city name:",
            reply_markup=markup
        )
        self.bot.register_next_step_handler(msg, self._process_reg_location)
    
    def _process_reg_location(self, message):
        chat_id = message.chat.id
        data = self._get_reg_state(chat_id, "data") or {}
        
        if message.location:
            data["shop_lat"] = message.location.latitude
            data["shop_lng"] = message.location.longitude
            location_text = f"📍 {data['shop_lat']}, {data['shop_lng']}"
        else:
            location_text = sanitize_input(message.text.strip())
            if not location_text:
                self.bot.reply_to(message, "❌ Please enter a location!")
                return
            data["area_text"] = location_text
        
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 5)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ Location: {location_text}\n\n"
            "📝 **Step 5/5: Store Description**\n\n"
            "Enter a short description of your store:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_description)
    
    def _process_reg_description(self, message):
        chat_id = message.chat.id
        description = sanitize_input(message.text.strip())
        
        if not description:
            self.bot.reply_to(message, "❌ Please enter a description!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["shop_description"] = description
        data["username"] = data.get("bot_username", f"shop_{chat_id}")
        
        try:
            existing = db_execute_dict("SELECT 1 FROM stores WHERE token = %s", (data["token"],))
            if existing:
                self.bot.reply_to(message, "❌ This token is already registered!")
                return
            
            h_pass, salt = hash_password(data["password"])
            
            db_execute("""
                INSERT INTO stores (
                    token, store_name, admin_id, username,
                    password_hash, password_salt,
                    is_active, is_approved, shop_lat, shop_lng,
                    area_text, shop_description
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["token"], data["store_name"], chat_id, data["username"],
                h_pass, salt, 1, 0,
                data.get("shop_lat"), data.get("shop_lng"),
                data.get("area_text", ""), data.get("shop_description", "")
            ))
            
            bot_manager.start_bot(data["token"])
            
            if Config.SUPER_ADMIN_ID:
                try:
                    self.bot.send_message(
                        Config.SUPER_ADMIN_ID,
                        f"🔔 **New store pending approval!**\n\n🏪 {data['store_name']}\n👤 @{data['username']}"
                    )
                except:
                    pass
            
            self._clear_reg_state(chat_id)
            
            self.bot.reply_to(
                message,
                f"✅ **Store registered successfully!**\n\n"
                f"🏪 Name: {data['store_name']}\n"
                f"👤 Username: @{data['username']}\n"
                f"📍 Location: {data.get('area_text', 'Saved')}\n"
                f"🔑 Password: `{data['password']}`\n\n"
                f"⏳ Your store is pending approval.",
                reply_markup=self._get_main_menu(),
                parse_mode="Markdown"
            )
            
            logger.audit(chat_id, "store_registered", {
                "store_name": data["store_name"],
                "store_id": data["token"]
            })
        except Exception as e:
            logger.error(f"Registration error: {e}")
            self.bot.reply_to(message, f"❌ Error: {e}")
    
    def _show_my_stores(self, message):
        chat_id = message.chat.id
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, is_active, is_approved, username, area_text, bot_status
                FROM stores WHERE admin_id = %s
                ORDER BY created_at DESC
            """, (chat_id,))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "❌ You haven't registered any stores yet.",
                    reply_markup=self._get_main_menu()
                )
                return
            
            text = "🏪 **Your Stores:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                approved = "✅" if store['is_approved'] else "⏳"
                bot_status = "▶️" if store['bot_status'] == 'running' else "⏹️"
                text += f"""
{status} {approved} {bot_status} **{store['store_name']}**
  👤 @{store['username'] or 'N/A'}
  📍 {store['area_text'] or 'N/A'}
  🆔 #{store['id']}
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu())
        except Exception as e:
            logger.error(f"My stores error: {e}")
            self.bot.reply_to(message, f"❌ Error: {e}")
    
    def _search_by_name(self, message):
        chat_id = message.chat.id
        query = sanitize_input(message.text.strip())
        
        if not query:
            self.bot.reply_to(message, "❌ Please enter a store name!")
            return
        
        try:
            stores = db_execute_dict("""
                SELECT store_name, username, area_text, is_active, is_approved
                FROM stores
                WHERE (store_name ILIKE %s OR username ILIKE %s) AND is_approved = 1
                LIMIT 10
            """, (f"%{query}%", f"%{query}%"))
            
            if not stores:
                self.bot.reply_to(message, "🔍 No stores found.", reply_markup=self._get_main_menu())
                return
            
            text = "🔍 **Search Results:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                text += f"""
{status} **{store['store_name']}**
  👤 @{store['username'] or 'N/A'}
  📍 {store['area_text'] or 'N/A'}
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu())
        except Exception as e:
            logger.error(f"Search error: {e}")
            self.bot.reply_to(message, f"❌ Error: {e}")
    
    def _search_by_location(self, message):
        chat_id = message.chat.id
        
        if not message.location:
            self.bot.reply_to(message, "❌ Please share your location!")
            return
        
        lat = message.location.latitude
        lng = message.location.longitude
        
        try:
            stores = db_execute_dict("""
                SELECT store_name, username, area_text, is_active,
                       (6371 * acos(cos(radians(%s)) * cos(radians(shop_lat)) *
                        cos(radians(shop_lng) - radians(%s)) + sin(radians(%s)) *
                        sin(radians(shop_lat)))) as distance
                FROM stores
                WHERE shop_lat IS NOT NULL AND shop_lng IS NOT NULL AND is_approved = 1
                ORDER BY distance LIMIT 10
            """, (lat, lng, lat))
            
            if not stores:
                self.bot.reply_to(message, "🔍 No stores found nearby.", reply_markup=self._get_main_menu())
                return
            
            text = "📍 **Nearby Stores:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                distance = store.get('distance', 0)
                text += f"""
{status} **{store['store_name']}**
  👤 @{store['username'] or 'N/A'}
  📍 {store['area_text'] or 'N/A'}
  📏 {distance:.1f} km
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu())
        except Exception as e:
            logger.error(f"Location search error: {e}")
            self.bot.reply_to(message, f"❌ Error: {e}")
    
    def _start_polling(self):
        def _poll():
            while True:
                try:
                    self.bot.infinity_polling(skip_pending=True, timeout=30)
                except Exception as e:
                    logger.error(f"Polling error: {e}")
                    time.sleep(5)
        
        threading.Thread(target=_poll, daemon=True).start()

# =================================================================================================
#                           LOAD EXISTING STORES
# =================================================================================================

def load_existing_stores():
    try:
        stores = db_execute_dict("SELECT token FROM stores WHERE is_approved = 1")
        count = 0
        for store in stores:
            if bot_manager.start_bot(store['token']):
                count += 1
        logger.info(f"✅ {count} stores loaded and started")
    except Exception as e:
        logger.error(f"❌ Failed to load stores: {e}")

load_existing_stores()

# =================================================================================================
#                           MAIN ENTRY POINT
# =================================================================================================

if __name__ == "__main__":
    try:
        control_bot = ControlBot()
        logger.info("🚀 Ultimate Control Bot v6.0 is running!")
        logger.info(f"🤖 AI Status: {'✅ Active' if AIEngine.is_available() else '❌ Disabled'}")
        logger.info(f"📊 Web Dashboard: http://{Config.HOST}:{Config.PORT}")
        logger.info(f"📊 Max Bots: {Config.MAX_BOTS}")
        
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        bot_manager.shutdown()
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        while True:
            time.sleep(60)
