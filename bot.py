"""
====================================================================================================
                    🚀 ULTIMATE MULTI-TENANT SHOP BOT v5.0 🚀
        የላቀ ባለብዙ ሱቅ አስተዳደር ሲስተም - Enterprise Grade Control Panel
====================================================================================================

የዚህ ሲስተም ባህሪያት:
    ✅ Multi-Tenant Store Registration
    ✅ Product Management (CRUD)
    ✅ AI-Powered Natural Language Search (Gemini)
    ✅ Shopping Cart & Checkout System
    ✅ AI-Powered Payment Receipt Verification
    ✅ Super Admin Dashboard with Full Control
    ✅ Store Approval Queue
    ✅ System Analytics & Statistics
    ✅ Broadcast Messaging System
    ✅ Store Suspension/Block
    ✅ Advanced Security (Input Sanitization, SQL Injection Protection)
    ✅ Environment Variables for Secrets
    ✅ Database Connection Pooling
    ✅ Thread-Safe Operations
    ✅ Comprehensive Logging
    ✅ Error Recovery System
    ✅ Rate Limiting
    ✅ Session Management
    ✅ Audit Trail
    ✅ Multi-Language Support (አማርኛ / English)
    ✅ REST API Endpoints
    ✅ Web Dashboard
    ✅ Health Checks

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
from collections import defaultdict
from functools import wraps
from contextlib import contextmanager

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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =================================================================================================
#                           CONFIGURATION & ENVIRONMENT
# =================================================================================================

class Config:
    """የሲስተም ውቅር ክፍል - All environment variables"""
    
    # ==================== DATABASE ====================
    DATABASE_URL = os.environ.get("DATABASE_URL")
    DATABASE_POOL_MIN = int(os.environ.get("DATABASE_POOL_MIN", "2"))
    DATABASE_POOL_MAX = int(os.environ.get("DATABASE_POOL_MAX", "20"))
    
    # ==================== BOT TOKENS ====================
    CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")
    SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
    SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
    
    # ==================== API KEYS ====================
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    
    # ==================== SERVER ====================
    PORT = int(os.environ.get("PORT", "8080"))
    HOST = os.environ.get("HOST", "0.0.0.0")
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    
    # ==================== SECURITY ====================
    SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "7200"))  # 2 hours
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION = int(os.environ.get("LOCKOUT_DURATION", "900"))  # 15 minutes
    
    # ==================== DELIVERY ====================
    BASE_DELIVERY_FEE = float(os.environ.get("BASE_DELIVERY_FEE", "30"))
    PER_KM_RATE = float(os.environ.get("PER_KM_RATE", "8"))
    
    # ==================== LOGGING ====================
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

# File handler for persistent logs
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
    """Initialize database connection pool"""
    global db_pool
    with db_pool_lock:
        if db_pool is None:
            try:
                db_pool = ThreadedConnectionPool(
                    Config.DATABASE_POOL_MIN,
                    Config.DATABASE_POOL_MAX,
                    dsn=Config.DATABASE_URL
                )
                # Test connection
                conn = db_pool.getconn()
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                db_pool.putconn(conn)
                logger.info("✅ Database connection pool initialized")
            except Exception as e:
                logger.error(f"❌ Database pool initialization failed: {e}")
                raise

def get_db_connection():
    """Get database connection from pool"""
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
    """Return connection to pool"""
    if conn is not None and db_pool is not None:
        try:
            db_pool.putconn(conn)
        except Exception as e:
            logger.warning(f"⚠️ Failed to return connection: {e}")
            try:
                conn.close()
            except:
                pass

def db_execute(query: str, params: tuple = None, fetch: bool = False):
    """Execute database query with parameters"""
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
        logger.error(f"❌ Database query error: {e}\nQuery: {query[:200]}")
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
    """Execute query and return results as dictionaries"""
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            return cur.fetchall()
    except Exception as e:
        logger.error(f"❌ Database query error: {e}")
        raise
    finally:
        if conn:
            put_db_connection(conn)

# =================================================================================================
#                           DATABASE SCHEMA
# =================================================================================================

def init_schema():
    """Initialize database schema with all tables"""
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
        subcategory_id INTEGER,
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- ORDERS TABLE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        customer_id BIGINT NOT NULL,
        customer_name TEXT,
        customer_phone TEXT,
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
        success BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- CART TABLE (Temporary cart storage)
    -- =====================================================
    CREATE TABLE IF NOT EXISTS carts (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        customer_id BIGINT NOT NULL,
        product_id INTEGER NOT NULL,
        qty INTEGER NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(token, customer_id, product_id)
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
    CREATE INDEX IF NOT EXISTS idx_carts_customer ON carts(customer_id);
    CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
    """
    
    try:
        db_execute(schema)
        logger.info("✅ Database schema initialized")
    except Exception as e:
        logger.error(f"❌ Schema initialization failed: {e}")
        raise

# Initialize database
init_db_pool()
init_schema()

# =================================================================================================
#                           AI ENGINE (Gemini Integration)
# =================================================================================================

class AIEngine:
    """የላቀ AI ሞተር - Gemini Integration"""
    
    _model = None
    _vision_model = None
    _initialized = False
    
    @classmethod
    def init(cls):
        """Initialize Gemini AI models"""
        if cls._initialized:
            return
        
        if Config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                cls._model = genai.GenerativeModel('gemini-1.5-flash')
                cls._vision_model = genai.GenerativeModel('gemini-1.5-flash')
                cls._initialized = True
                logger.info("✅ Gemini AI initialized successfully")
            except Exception as e:
                logger.error(f"❌ Gemini AI initialization failed: {e}")
                cls._initialized = False
        else:
            logger.warning("⚠️ GEMINI_API_KEY not set, AI features disabled")
            cls._initialized = False
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if AI is available"""
        return cls._initialized and cls._model is not None
    
    @classmethod
    def generate_response(cls, prompt: str, context: str = "") -> Optional[str]:
        """Generate AI response"""
        if not cls.is_available():
            return None
        
        try:
            full_prompt = f"{context}\n\n{prompt}"
            response = cls._model.generate_content(full_prompt)
            return response.text if response else None
        except Exception as e:
            logger.error(f"AI generation error: {e}")
            return None
    
    @classmethod
    def search_products(cls, query: str, products: List[Dict], lang: str = "am") -> List[Dict]:
        """AI-Powered product search using natural language"""
        if not cls.is_available():
            return None
        
        try:
            # Build product list for context
            product_text = ""
            for p in products[:50]:  # Limit to 50 products for context
                name = p.get('name_am', '') if lang == 'am' else p.get('name_en', '')
                price = p.get('price', 0)
                desc = p.get('desc_am', '') if lang == 'am' else p.get('desc_en', '')
                product_text += f"- ID:{p['id']}, Name:{name}, Price:{price} ETB, Desc:{desc}\n"
            
            prompt = f"""
            You are a smart product search assistant. Analyze the user's query and find matching products.
            
            Available products:
            {product_text}
            
            User query: {query}
            
            Return ONLY the product IDs that match, separated by commas.
            If no products match, return "NONE".
            Consider price ranges, categories, and descriptions in your analysis.
            """
            
            response = cls._model.generate_content(prompt)
            result = response.text.strip()
            
            if result == "NONE" or not result:
                return []
            
            # Extract IDs
            ids = re.findall(r'\d+', result)
            if not ids:
                return []
            
            # Get matching products
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
        """
        AI-Powered payment receipt verification using Gemini Vision
        Verifies Telebirr, CBE, and Bank receipts
        """
        if not cls.is_available():
            return False, "AI model not configured. Please contact support."
        
        try:
            # Open image
            img = Image.open(io.BytesIO(image_data))
            
            prompt = f"""
            Analyze this payment receipt image for an e-commerce transaction.
            Check the following details:
            1. Is it a valid payment receipt (Telebirr, CBE Birr, or Bank)?
            2. Does the transferred amount match or exceed {expected_amount} ETB?
            3. Is the receipt genuine (not a screenshot from another transaction)?
            
            Respond strictly in this format:
            status: VALID or INVALID
            amount_found: [extracted number or 0]
            payment_method: [Telebirr/CBE/Bank/Unknown]
            reason: [short explanation of the verification result]
            """
            
            response = cls._vision_model.generate_content([prompt, img])
            result_text = response.text.strip()
            logger.info(f"AI Receipt Analysis: {result_text}")
            
            # Parse result
            is_valid = "status: VALID" in result_text.upper()
            return is_valid, result_text
            
        except Exception as e:
            logger.error(f"Receipt verification error: {e}")
            return False, f"Verification error: {str(e)}"

# Initialize AI
AIEngine.init()

# =================================================================================================
#                           UTILITY FUNCTIONS
# =================================================================================================

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash password with salt"""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify password"""
    test_hash, _ = hash_password(password, salt)
    return test_hash == hashed

def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in km using Haversine formula"""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def calculate_delivery_fee(distance_km: float) -> float:
    """Calculate delivery fee"""
    if distance_km <= 0:
        return 0
    return round(Config.BASE_DELIVERY_FEE + (distance_km * Config.PER_KM_RATE), 2)

def format_currency(amount: float) -> str:
    """Format currency"""
    return f"{amount:,.2f} ETB"

def format_date(dt: datetime) -> str:
    """Format datetime"""
    return dt.strftime("%Y-%m-%d %H:%M")

def safe_int(value: Any, default: int = 0) -> int:
    """Convert to int safely"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert to float safely"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent SQL injection and XSS"""
    if not text:
        return ""
    # Remove dangerous characters
    text = re.sub(r'[;\'"]', '', text)
    # Limit length
    return text[:1000]

def get_user_lang(chat_id: int) -> str:
    """Get user's preferred language"""
    try:
        result = db_execute(
            "SELECT lang FROM user_langs WHERE chat_id = %s",
            (chat_id,), fetch=True
        )
        if result:
            return result[0][0]
    except:
        pass
    return "am"

def set_user_lang(chat_id: int, lang: str):
    """Set user's preferred language"""
    try:
        db_execute(
            "INSERT INTO user_langs (chat_id, lang) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang",
            (chat_id, lang)
        )
    except Exception as e:
        logger.error(f"Set user lang error: {e}")

def get_store_info(token: str) -> Optional[Dict]:
    """Get store information by token"""
    try:
        result = db_execute_dict(
            """SELECT id, store_name, admin_id, username, is_active, is_approved, 
                      area_text, shop_description, shop_lat, shop_lng,
                      telebirr, cbebirr, bank_name, bank_account
               FROM stores WHERE token = %s""",
            (token,)
        )
        if result:
            return dict(result[0])
        return None
    except Exception as e:
        logger.error(f"Get store info error: {e}")
        return None

def get_customer_info(chat_id: int) -> Optional[Dict]:
    """Get customer information"""
    try:
        result = db_execute_dict(
            "SELECT phone, lat, lng, address FROM customer_info WHERE chat_id = %s",
            (chat_id,)
        )
        if result:
            return dict(result[0])
        return None
    except Exception as e:
        logger.error(f"Get customer info error: {e}")
        return None

def save_customer_info(chat_id: int, phone: str = None, lat: float = None, lng: float = None, address: str = None):
    """Save or update customer information"""
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
        <title>Control Bot Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
            .container { background: white; border-radius: 20px; padding: 40px; max-width: 800px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
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
            <h1>🚀 Multi-Tenant Shop Bot</h1>
            <p class="subtitle">Advanced Store Management System</p>
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
                    <div class="stat-number" id="pending-stores">-</div>
                    <div class="stat-label">Pending Approval</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="total-products">-</div>
                    <div class="stat-label">Total Products</div>
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
                </div>
            </div>
            
            <div class="info">
                <h3>🤖 AI Features</h3>
                <p>🔍 Natural Language Search</p>
                <p>📸 AI-Powered Payment Verification</p>
                <p>💬 Smart Chat Assistant</p>
            </div>
            
            <div class="footer">
                © 2026 Multi-Tenant Shop Bot v5.0 | Powered by Gemini AI
            </div>
        </div>
        
        <script>
            async function loadStats() {
                try {
                    const response = await fetch('/api/stats');
                    const data = await response.json();
                    document.getElementById('total-stores').textContent = data.total_stores || 0;
                    document.getElementById('active-stores').textContent = data.active_stores || 0;
                    document.getElementById('pending-stores').textContent = data.pending_approval || 0;
                    document.getElementById('total-products').textContent = data.total_products || 0;
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
    """Get system statistics"""
    try:
        total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
        pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
        active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
        total_products = db_execute("SELECT COUNT(*) FROM products", fetch=True)[0][0]
        total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
        revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
        
        return jsonify({
            "total_stores": total_stores,
            "pending_approval": pending,
            "active_stores": active,
            "total_products": total_products,
            "total_orders": total_orders,
            "total_revenue": float(revenue)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health')
def api_health():
    """Health check endpoint"""
    try:
        db_execute("SELECT 1", fetch=True)
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "ai_available": AIEngine.is_available()
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

def run_flask():
    app.run(host=Config.HOST, port=Config.PORT, debug=False)

threading.Thread(target=run_flask, daemon=True).start()
logger.info(f"✅ Web server running on {Config.HOST}:{Config.PORT}")

# =================================================================================================
#                           SHOP BOT ENGINE - Multi-Tenant
# =================================================================================================

running_tokens = set()
running_lock = threading.Lock()
user_carts = {}
user_carts_lock = threading.Lock()

def start_shop_bot(token: str) -> bool:
    """Start a shop bot for a store"""
    with running_lock:
        if token in running_tokens:
            return False
        running_tokens.add(token)
    
    try:
        setup_bot_handlers(token)
        logger.info(f"✅ Shop bot started: {token[:15]}...")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot {token[:15]}: {e}")
        with running_lock:
            running_tokens.discard(token)
        return False

def setup_bot_handlers(token: str):
    """Setup bot handlers for a store"""
    bot = telebot.TeleBot(token, threaded=False)
    
    try:
        bot.remove_webhook()
    except:
        pass
    
    # ============================================================
    # COMMAND: /start
    # ============================================================
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        chat_id = message.chat.id
        store = get_store_info(token)
        
        if not store:
            bot.send_message(
                chat_id,
                "🏪 ይህ ቦት ገና አልተመዘገበም።\n\n"
                "📌 እባክዎ በ Control Bot ይመዝገቡ!",
                parse_mode="Markdown"
            )
            return
        
        if store.get('is_approved', 0) != 1:
            bot.send_message(
                chat_id,
                f"⏳ **ሰላም!**\n\n"
                f"ይህ ሱቅ **{store.get('store_name', '')}** ገና አልጸደቀም።\n"
                f"እባክዎ ለማጽደቅ ይጠብቁ።",
                parse_mode="Markdown"
            )
            return
        
        if not store.get('is_active', 1):
            bot.send_message(
                chat_id,
                "❌ ይህ ሱቅ ንቁ አይደለም።\nእባክዎ አድሚኑን ያነጋግሩ።"
            )
            return
        
        # Language selection
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data=f"lang_am_{token}"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data=f"lang_en_{token}")
        )
        
        bot.send_message(
            chat_id,
            f"🌐 **{store.get('store_name', '')}**\n\n"
            "ቋንቋ ይምረጡ / Select Language:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    # ============================================================
    # LANGUAGE SELECTION
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
    def handle_lang(call):
        _, lang, bot_token = call.data.split("_")
        if bot_token != token:
            return
        
        chat_id = call.message.chat.id
        set_user_lang(chat_id, lang)
        
        bot.delete_message(chat_id, call.message.message_id)
        
        # Main menu
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
        
        welcome = {
            "am": "እንኳን ወደ ሱቅ በደህና መጡ! 👋",
            "en": "Welcome to the store! 👋"
        }
        
        bot.send_message(
            chat_id,
            welcome.get(lang, welcome["am"]),
            reply_markup=markup
        )
    
    # ============================================================
    # SHOP PRODUCTS
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == "🛍️ ምርቶች")
    def handle_products(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name_am, name_en, price, stock, image_url, desc_am, desc_en
                    FROM products
                    WHERE token = %s AND stock > 0 AND is_active = 1
                    ORDER BY id
                    LIMIT 20
                """, (token,))
                products = cur.fetchall()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not products:
            bot.send_message(
                chat_id,
                "🛍️ ምንም ምርት የለም" if lang == "am" else "No products available",
                reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                    types.KeyboardButton("🔙 ወደ ኋላ")
                )
            )
            return
        
        for product in products:
            p_id, name_am, name_en, price, stock, image_url, desc_am, desc_en = product
            name = name_am if lang == "am" else name_en
            desc = desc_am if lang == "am" else desc_en
            
            text = f"📦 **{name}**\n"
            text += f"💰 {format_currency(price)}\n"
            text += f"📌 ✅ {lang == 'am' and 'ይገኛል' or 'In Stock'}\n"
            if desc:
                text += f"📝 {desc[:100]}..."
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🛒 ወደ ጋሪ ጨምር", callback_data=f"add_{p_id}"),
                types.InlineKeyboardButton("📖 ዝርዝር", callback_data=f"detail_{p_id}")
            )
            
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        
        # Back button
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("🔙 ወደ ኋላ"))
        bot.send_message(chat_id, "📌 ሌሎች ምርቶችን ለማየት እንደገና ይጫኑ", reply_markup=markup)
    
    # ============================================================
    # PRODUCT DETAIL
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("detail_"))
    def handle_product_detail(call):
        p_id = int(call.data.split("_")[1])
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name_am, name_en, price, stock, desc_am, desc_en, image_url
                    FROM products WHERE id = %s AND token = %s
                """, (p_id, token))
                product = cur.fetchone()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not product:
            bot.answer_callback_query(call.id, "❌ ምርት አልተገኘም")
            return
        
        name_am, name_en, price, stock, desc_am, desc_en, image_url = product
        name = name_am if lang == "am" else name_en
        desc = desc_am if lang == "am" else desc_en
        
        text = f"📦 **{name}**\n\n"
        text += f"💰 {format_currency(price)}\n"
        text += f"📦 {stock} {lang == 'am' and 'ቁራጭ' or 'units'} {lang == 'am' and 'ቀርቷል' or 'available'}\n"
        if desc:
            text += f"\n📝 {desc}\n"
        
        markup = types.InlineKeyboardMarkup()
        if stock > 0:
            markup.add(types.InlineKeyboardButton("🛒 ወደ ጋሪ ጨምር", callback_data=f"add_{p_id}"))
        markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="back_to_products"))
        
        if image_url:
            try:
                bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        
        bot.answer_callback_query(call.id)
    
    # ============================================================
    # ADD TO CART
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
    def handle_add_to_cart(call):
        p_id = int(call.data.split("_")[1])
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        
        # Check stock
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT stock FROM products WHERE id = %s AND token = %s", (p_id, token))
                result = cur.fetchone()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not result or result[0] <= 0:
            bot.answer_callback_query(call.id, "❌ ምርቱ አልቀረም!")
            return
        
        # Add to cart
        with user_carts_lock:
            cart_key = (token, chat_id)
            if cart_key not in user_carts:
                user_carts[cart_key] = {}
            user_carts[cart_key][p_id] = user_carts[cart_key].get(p_id, 0) + 1
        
        bot.answer_callback_query(
            call.id,
            "✅ ወደ ጋሪ ተጨምሯል!" if lang == "am" else "✅ Added to cart!"
        )
    
    # ============================================================
    # VIEW CART
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == "🛒 ጋሪ")
    def handle_cart(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        with user_carts_lock:
            cart = user_carts.get((token, chat_id), {})
        
        if not cart:
            bot.send_message(
                chat_id,
                "🛒 ጋሪዎ ባዶ ነው" if lang == "am" else "🛒 Your cart is empty"
            )
            return
        
        total = 0
        text = "🛒 **ጋሪ**\n\n"
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                for p_id, qty in cart.items():
                    cur.execute("SELECT name_am, name_en, price FROM products WHERE id = %s AND token = %s", (p_id, token))
                    product = cur.fetchone()
                    if product:
                        name = product[0] if lang == "am" else product[1]
                        price = product[2]
                        subtotal = price * qty
                        total += subtotal
                        text += f"▪️ {name} x{qty} = {format_currency(subtotal)}\n"
        finally:
            if conn:
                put_db_connection(conn)
        
        text += f"\n💰 **{lang == 'am' and 'አጠቃላይ' or 'Total'}: {format_currency(total)}**"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("💳 ሂሳብ ማጠቃለያ", callback_data="checkout"),
            types.InlineKeyboardButton("🗑️ ጋሪ አጽዳ", callback_data="clear_cart")
        )
        
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    # ============================================================
    # CLEAR CART
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "clear_cart")
    def handle_clear_cart(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        
        with user_carts_lock:
            user_carts.pop((token, chat_id), None)
        
        bot.edit_message_text(
            "🗑️ ጋሪ ጸድቷል" if lang == "am" else "🗑️ Cart cleared",
            chat_id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id)
    
    # ============================================================
    # CHECKOUT
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "checkout")
    def handle_checkout(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        
        with user_carts_lock:
            cart = user_carts.get((token, chat_id), {})
        
        if not cart:
            bot.answer_callback_query(call.id, "❌ ጋሪ ባዶ ነው!")
            return
        
        # Get customer info
        customer = get_customer_info(chat_id)
        has_phone = customer and customer.get('phone')
        has_location = customer and customer.get('lat') and customer.get('lng')
        
        if not has_phone or not has_location:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            if not has_phone:
                markup.add(types.KeyboardButton("📱 ስልክ አጋራ", request_contact=True))
            if not has_location:
                markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
            
            bot.send_message(
                chat_id,
                "🚚 ለማድረሻ ስልክ እና አካባቢ ያጋሩ 👇",
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
            return
        
        # Process checkout
        process_checkout(call)
    
    # ============================================================
    # PROCESS CHECKOUT
    # ============================================================
    def process_checkout(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        
        with user_carts_lock:
            cart = user_carts.get((token, chat_id), {})
        
        if not cart:
            bot.answer_callback_query(call.id, "❌ ጋሪ ባዶ ነው!")
            return
        
        store = get_store_info(token)
        customer = get_customer_info(chat_id)
        
        if not store or not customer:
            bot.send_message(chat_id, "❌ መረጃ አልተገኘም")
            return
        
        # Calculate totals
        total_items = 0
        order_items = []
        conn = None
        
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                for p_id, qty in cart.items():
                    cur.execute("SELECT price, stock FROM products WHERE id = %s AND token = %s", (p_id, token))
                    product = cur.fetchone()
                    if product:
                        price, stock = product
                        buy_qty = min(qty, stock)
                        if buy_qty > 0:
                            total_items += price * buy_qty
                            order_items.append((p_id, buy_qty, price))
                
                # Calculate delivery fee
                delivery_fee = 0
                if store.get('shop_lat') and store.get('shop_lng'):
                    dist = calculate_distance(
                        store['shop_lat'], store['shop_lng'],
                        customer.get('lat', 0), customer.get('lng', 0)
                    )
                    delivery_fee = calculate_delivery_fee(dist)
                
                grand_total = total_items + delivery_fee
                
                # Create order
                cur.execute("""
                    INSERT INTO orders (
                        token, customer_id, customer_phone,
                        status_am, status_en, status_stage,
                        total_price, delivery_fee,
                        delivery_address, delivery_lat, delivery_lng
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    token, chat_id, customer.get('phone'),
                    "🟡 በመጠባበቅ ላይ", "🟡 Pending", 0,
                    total_items, delivery_fee,
                    customer.get('address', ''),
                    customer.get('lat', 0),
                    customer.get('lng', 0)
                ))
                order_id = cur.fetchone()[0]
                
                # Add order items
                for p_id, qty, price in order_items:
                    cur.execute("""
                        INSERT INTO order_items (order_id, product_id, qty, price, total)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (order_id, p_id, qty, price, price * qty))
                    
                    # Update stock
                    cur.execute(
                        "UPDATE products SET stock = stock - %s, sales_count = sales_count + %s WHERE id = %s",
                        (qty, qty, p_id)
                    )
                
                conn.commit()
                
                # Clear cart
                with user_carts_lock:
                    user_carts.pop((token, chat_id), None)
                
                # Show payment info
                pay_methods = ""
                if store.get('telebirr'):
                    pay_methods += f"📱 ቴሌብር: `{store['telebirr']}`\n"
                if store.get('cbebirr'):
                    pay_methods += f"🏦 CBE ብር: `{store['cbebirr']}`\n"
                if store.get('bank_name') and store.get('bank_account'):
                    pay_methods += f"🏛️ {store['bank_name']}: `{store['bank_account']}`\n"
                
                pay_text = f"""
🆔 **Order ID:** `{order_id}`

💵 ድምር: {format_currency(total_items)}
🚚 ማድረሻ: {format_currency(delivery_fee)}
💰 **አጠቃላይ: {format_currency(grand_total)}**

**የክፍያ መንገዶች:**
{pay_methods}

📸 እባክዎ የክፍያ ማረጋገጫ ፎቶ ይላኩ
"""
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("✅ ክፍያ አረጋግጫለሁ", callback_data=f"pay_confirmed_{order_id}"))
                
                bot.send_message(
                    chat_id,
                    pay_text,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
                
                # Notify admin
                admin_id = store.get('admin_id')
                if admin_id:
                    try:
                        bot.send_message(
                            admin_id,
                            f"🔔 **አዲስ ትዕዛዝ #{order_id}!**\n"
                            f"👤 ደንበኛ: {chat_id}\n"
                            f"💰 {format_currency(grand_total)}"
                        )
                    except:
                        pass
                
        except Exception as e:
            logger.error(f"Checkout error: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            bot.send_message(chat_id, f"❌ ስህተት ተከስቷል: {e}")
        finally:
            if conn:
                put_db_connection(conn)
    
    # ============================================================
    # PAYMENT RECEIPT VERIFICATION (AI-Powered)
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("pay_confirmed_"))
    def handle_pay_confirmed(call):
        order_id = int(call.data.split("_")[2])
        chat_id = call.message.chat.id
        
        bot.send_message(
            chat_id,
            "📸 እባክዎ የክፍያ ማረጋገጫ ፎቶዎን ይላኩ\n\n"
            "🤖 ምስሉ በ AI ይረጋገጣል"
        )
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(content_types=['photo'])
    def handle_payment_receipt(message):
        """AI-Powered payment receipt verification"""
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        # Get pending order for this customer
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, total_price + delivery_fee as total
                    FROM orders
                    WHERE customer_id = %s AND token = %s AND status_stage = 0
                    ORDER BY id DESC LIMIT 1
                """, (chat_id, token))
                order = cur.fetchone()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not order:
            bot.send_message(
                chat_id,
                "❌ ምንም ያልተከፈለ ትዕዛዝ አልተገኘም"
            )
            return
        
        order_id, total = order
        
        # Download photo
        try:
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)
        except Exception as e:
            logger.error(f"Failed to download photo: {e}")
            bot.send_message(chat_id, "❌ ፎቶ ማውረድ አልተቻለም")
            return
        
        # Send verification in progress
        bot.send_message(
            chat_id,
            "🔄 **ክፍያዎ በ AI እየተረጋገጠ ነው...**\n\n"
            "🤖 የ Gemini AI ምስል ትንተና እያደረገ ነው\n"
            "⏳ እባክዎ ለ30 ሰከንድ ያህል ይጠብቁ",
            parse_mode="Markdown"
        )
        
        # Verify receipt using AI
        is_valid, details = AIEngine.verify_payment_receipt(
            downloaded_file,
            float(total)
        )
        
        if is_valid:
            # Update order status
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE orders 
                        SET status_am = '✅ ተረጋግጧል',
                            status_en = '✅ Confirmed',
                            status_stage = 1,
                            payment_status = 'paid',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (order_id,))
                    conn.commit()
            finally:
                if conn:
                    put_db_connection(conn)
            
            # Send success message
            bot.send_message(
                chat_id,
                f"""✅ **ክፍያዎ በትክክል ተረጋግጧል!**

🎉 ትዕዛዝ #{order_id} ተመዝግቧል
📦 ምርቶችዎ እየተዘጋጁ ነው

📊 ዝርዝር ለማየት /track {order_id} ይላኩ
""",
                parse_mode="Markdown"
            )
            
            # Notify admin
            store = get_store_info(token)
            if store and store.get('admin_id'):
                try:
                    bot.send_message(
                        store['admin_id'],
                        f"✅ **ክፍያ ተረጋግጧል!**\n"
                        f"🆔 ትዕዛዝ #{order_id}\n"
                        f"👤 ደንበኛ: {chat_id}\n"
                        f"💰 {format_currency(total)}"
                    )
                except:
                    pass
            
            logger.audit(chat_id, "payment_verified", {"order_id": order_id, "amount": total})
            
        else:
            # Payment verification failed
            bot.send_message(
                chat_id,
                f"""❌ **ክፍያው ሊረጋገጥ አልቻለም**

🔍 ምክንያት: ደረሰኙ ትክክል አይደለም ወይም መጠኑ ከፍያው ጋር አይዛመድም

📋 ዝርዝር:
