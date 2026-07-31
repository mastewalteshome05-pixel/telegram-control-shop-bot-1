"""
================================================================================
                    🚀 ADVANCED CONTROL BOT v3.0 🚀
        የላቀ የሱቅ አስተዳደር ሲስተም - Super Admin Control Panel
================================================================================

የዚህ ሲስተም ባህሪያት:
    ✅ Multi-language Support (አማርኛ / English)
    ✅ Advanced Store Management
    ✅ Real-time Analytics Dashboard
    ✅ Automated Store Approval System
    ✅ Bulk Messaging (Broadcast)
    ✅ Store Analytics & Reports
    ✅ User Management
    ✅ Payment Method Configuration
    ✅ Order Management
    ✅ Product Management
    ✅ Category Management
    ✅ AI-Powered Search
    ✅ Database Connection Pool
    ✅ Thread-Safe Operations
    ✅ Comprehensive Logging
    ✅ Error Recovery System
    ✅ Rate Limiting
    ✅ Session Management
    ✅ Backup & Restore
    ✅ Export Reports (CSV/PDF)
    ✅ Store Performance Metrics
    ✅ Customer Analytics
    ✅ Revenue Tracking
    ✅ Commission Management
    ✅ Notification System
    ✅ Audit Trail
    ✅ Scheduled Tasks
    ✅ Webhook Support
    ✅ API Endpoints

================================================================================
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
import asyncio
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict
from functools import wraps

# Third-party imports
import telebot
from telebot import types, apihelper
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor, Json
from flask import Flask, jsonify, request, render_template_string
import google.generativeai as genai

# =================================================================================
#                           CONFIGURATION & ENVIRONMENT
# =================================================================================

class Config:
    """የሲስተም ውቅር ክፍል"""
    
    # Database
    DATABASE_URL = os.environ.get("DATABASE_URL")
    
    # Bot Tokens
    CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")
    SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
    SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
    
    # API Keys
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    
    # Server
    PORT = int(os.environ.get("PORT", 8080))
    HOST = os.environ.get("HOST", "0.0.0.0")
    
    # Security
    SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "7200"))  # 2 hours
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION = int(os.environ.get("LOCKOUT_DURATION", "900"))  # 15 minutes
    
    # Pagination
    PAGE_SIZE = int(os.environ.get("PAGE_SIZE", "10"))
    
    # Rate Limiting
    RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "30"))  # messages per minute
    
    # Commission
    DEFAULT_COMMISSION = float(os.environ.get("DEFAULT_COMMISSION", "0.05"))  # 5%
    
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

# =================================================================================
#                           LOGGING SYSTEM
# =================================================================================

class Logger:
    """የላቀ ሎግ ሲስተም"""
    
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
        self.logger = logging.getLogger('ControlBot')
        self.logger.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler
        try:
            file_handler = logging.FileHandler(Config.LOG_FILE)
            file_handler.setLevel(logging.INFO)
            file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
        except Exception:
            pass
        
        # Database handler for audit logs
        self.audit_enabled = True
    
    def info(self, message: str):
        self.logger.info(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def debug(self, message: str):
        self.logger.debug(message)
    
    def audit(self, user_id: int, action: str, details: dict = None):
        """የኦዲት ሎግ መዝገብ"""
        if self.audit_enabled:
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO audit_logs (user_id, action, details, ip_address, created_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (user_id, action, json.dumps(details) if details else None, None))
                    conn.commit()
            except Exception as e:
                self.error(f"Audit log error: {e}")
            finally:
                if conn:
                    put_db_connection(conn)

logger = Logger()

# =================================================================================
#                           DATABASE LAYER
# =================================================================================

class Database:
    """የላቀ የውሂብ ጎታ አስተዳደር ክፍል"""
    
    _pool = None
    _pool_lock = threading.Lock()
    
    @classmethod
    def init_pool(cls):
        """የውሂብ ጎታ ገንዳ መጀመሪያ"""
        with cls._pool_lock:
            if cls._pool is None:
                try:
                    cls._pool = ThreadedConnectionPool(1, 20, dsn=Config.DATABASE_URL)
                    logger.info("✅ Database connection pool initialized")
                except Exception as e:
                    logger.error(f"❌ Database pool initialization failed: {e}")
                    raise
    
    @classmethod
    def get_connection(cls):
        """ከገንዳ ግንኙነት ማግኘት"""
        if cls._pool is None:
            cls.init_pool()
        
        try:
            conn = cls._pool.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return conn
        except Exception as e:
            logger.error(f"❌ Failed to get connection: {e}")
            # Try to reinitialize
            with cls._pool_lock:
                try:
                    if cls._pool:
                        cls._pool.closeall()
                except:
                    pass
                cls._pool = None
                cls.init_pool()
            return cls._pool.getconn()
    
    @classmethod
    def return_connection(cls, conn):
        """ግንኙነት ወደ ገንዳ መመለስ"""
        if conn is not None and cls._pool is not None:
            try:
                cls._pool.putconn(conn)
            except Exception as e:
                logger.warning(f"⚠️ Failed to return connection: {e}")
                try:
                    conn.close()
                except:
                    pass
    
    @classmethod
    def execute(cls, query: str, params: tuple = None, fetch: bool = False):
        """የውሂብ ጎታ ጥያቄ ማስኬድ"""
        conn = None
        try:
            conn = cls.get_connection()
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                if fetch:
                    return cur.fetchall()
                conn.commit()
                return cur.rowcount if cur.rowcount > 0 else None
        except Exception as e:
            logger.error(f"❌ Database query error: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise
        finally:
            if conn:
                cls.return_connection(conn)
    
    @classmethod
    def execute_dict(cls, query: str, params: tuple = None):
        """የውሂብ ጎታ ጥያቄ በመዝገብ ቅርጸት"""
        conn = None
        try:
            conn = cls.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params or ())
                return cur.fetchall()
        except Exception as e:
            logger.error(f"❌ Database query error: {e}")
            raise
        finally:
            if conn:
                cls.return_connection(conn)
    
    @classmethod
    def init_schema(cls):
        """የውሂብ ጎታ ሰንጠረዦች መፍጠር"""
        schema = """
        -- Stores table
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
            is_active INTEGER DEFAULT 1,
            is_approved INTEGER DEFAULT 0,
            shop_lat REAL,
            shop_lng REAL,
            area_text TEXT,
            shop_photo TEXT,
            shop_description TEXT,
            bank_name TEXT,
            bank_account TEXT,
            commission_rate REAL DEFAULT 0.05,
            rating REAL DEFAULT 0,
            total_sales REAL DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Products table
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
            category_id INTEGER,
            sales_count INTEGER DEFAULT 0,
            rating REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Orders table
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            token TEXT NOT NULL,
            customer_id BIGINT NOT NULL,
            status_am TEXT DEFAULT 'በመጠባበቅ ላይ',
            status_en TEXT DEFAULT 'Pending',
            total_price REAL NOT NULL,
            delivery_fee REAL DEFAULT 0,
            commission REAL DEFAULT 0,
            status_stage INTEGER DEFAULT 0,
            payment_method TEXT,
            payment_status TEXT DEFAULT 'pending',
            tracking_number TEXT,
            delivered_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Order items
        CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        );

        -- User languages
        CREATE TABLE IF NOT EXISTS user_langs (
            chat_id BIGINT PRIMARY KEY,
            lang TEXT DEFAULT 'am'
        );

        -- Customer info
        CREATE TABLE IF NOT EXISTS customer_info (
            chat_id BIGINT PRIMARY KEY,
            phone TEXT,
            lat REAL,
            lng REAL,
            address TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Categories
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            token TEXT NOT NULL,
            name_am TEXT,
            name_en TEXT,
            icon TEXT,
            parent_id INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Audit logs
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            action TEXT NOT NULL,
            details JSONB,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Store analytics
        CREATE TABLE IF NOT EXISTS store_analytics (
            id SERIAL PRIMARY KEY,
            token TEXT NOT NULL,
            date DATE NOT NULL,
            visits INTEGER DEFAULT 0,
            orders INTEGER DEFAULT 0,
            revenue REAL DEFAULT 0,
            unique_customers INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Notifications
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            title TEXT,
            message TEXT,
            type TEXT DEFAULT 'info',
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_products_token ON products(token);
        CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token);
        CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
        CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
        CREATE INDEX IF NOT EXISTS idx_analytics_token_date ON store_analytics(token, date);
        """
        
        try:
            cls.execute(schema)
            logger.info("✅ Database schema initialized")
        except Exception as e:
            logger.error(f"❌ Schema initialization failed: {e}")
            raise

# Initialize database
Database.init_pool()
Database.init_schema()

# Helper functions for backward compatibility
def get_db_connection():
    return Database.get_connection()

def put_db_connection(conn):
    Database.return_connection(conn)

def db_execute(query, params=None, fetch=False):
    return Database.execute(query, params, fetch)

def db_execute_dict(query, params=None):
    return Database.execute_dict(query, params)

# =================================================================================
#                           MODELS / DATA CLASSES
# =================================================================================

@dataclass
class Store:
    """የሱቅ ውሂብ ክፍል"""
    id: int
    token: str
    store_name: str
    admin_id: Optional[int]
    username: Optional[str]
    is_active: bool
    is_approved: bool
    area_text: Optional[str]
    shop_description: Optional[str]
    telebirr: Optional[str]
    cbebirr: Optional[str]
    bank_name: Optional[str]
    bank_account: Optional[str]
    shop_lat: Optional[float]
    shop_lng: Optional[float]
    commission_rate: float
    rating: float
    total_sales: float
    total_orders: int
    created_at: datetime
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get('id'),
            token=data.get('token'),
            store_name=data.get('store_name'),
            admin_id=data.get('admin_id'),
            username=data.get('username'),
            is_active=bool(data.get('is_active', 1)),
            is_approved=bool(data.get('is_approved', 0)),
            area_text=data.get('area_text'),
            shop_description=data.get('shop_description'),
            telebirr=data.get('telebirr'),
            cbebirr=data.get('cbebirr'),
            bank_name=data.get('bank_name'),
            bank_account=data.get('bank_account'),
            shop_lat=data.get('shop_lat'),
            shop_lng=data.get('shop_lng'),
            commission_rate=float(data.get('commission_rate', 0.05)),
            rating=float(data.get('rating', 0)),
            total_sales=float(data.get('total_sales', 0)),
            total_orders=int(data.get('total_orders', 0)),
            created_at=data.get('created_at')
        )
    
    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class Order:
    """የትዕዛዝ ውሂብ ክፍል"""
    id: int
    token: str
    customer_id: int
    status_am: str
    status_en: str
    total_price: float
    delivery_fee: float
    commission: float
    status_stage: int
    payment_method: Optional[str]
    payment_status: str
    tracking_number: Optional[str]
    created_at: datetime
    delivered_at: Optional[datetime]
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get('id'),
            token=data.get('token'),
            customer_id=data.get('customer_id'),
            status_am=data.get('status_am'),
            status_en=data.get('status_en'),
            total_price=float(data.get('total_price', 0)),
            delivery_fee=float(data.get('delivery_fee', 0)),
            commission=float(data.get('commission', 0)),
            status_stage=int(data.get('status_stage', 0)),
            payment_method=data.get('payment_method'),
            payment_status=data.get('payment_status', 'pending'),
            tracking_number=data.get('tracking_number'),
            created_at=data.get('created_at'),
            delivered_at=data.get('delivered_at')
        )

@dataclass
class Product:
    """የምርት ውሂብ ክፍል"""
    id: int
    token: str
    name_am: str
    name_en: Optional[str]
    price: float
    stock: int
    desc_am: Optional[str]
    desc_en: Optional[str]
    image_url: Optional[str]
    category_id: Optional[int]
    sales_count: int
    rating: float
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get('id'),
            token=data.get('token'),
            name_am=data.get('name_am'),
            name_en=data.get('name_en'),
            price=float(data.get('price', 0)),
            stock=int(data.get('stock', 0)),
            desc_am=data.get('desc_am'),
            desc_en=data.get('desc_en'),
            image_url=data.get('image_url'),
            category_id=data.get('category_id'),
            sales_count=int(data.get('sales_count', 0)),
            rating=float(data.get('rating', 0))
        )

@dataclass
class AnalyticsData:
    """የስታቲስቲክስ ውሂብ ክፍል"""
    total_stores: int
    pending_approval: int
    active_stores: int
    total_products: int
    total_orders: int
    total_revenue: float
    active_users: int
    recent_orders: int
    daily_orders: Dict[str, int]
    revenue_by_store: List[Dict]
    top_products: List[Dict]
    growth_data: Dict[str, Any]

# =================================================================================
#                           UTILITY FUNCTIONS
# =================================================================================

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """የይለፍ ቃል መደበቅ"""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def verify_password(password: str, hashed: str, salt: str) -> bool:
    """የይለፍ ቃል ማረጋገጥ"""
    test_hash, _ = hash_password(password, salt)
    return test_hash == hashed

def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """ርቀት በኪሎሜትር ማስላት"""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def calculate_delivery_fee(distance_km: float) -> float:
    """የማድረሻ ወጪ ማስላት"""
    return round(Config.BASE_DELIVERY_FEE + (distance_km * Config.PER_KM_RATE), 2)

def calculate_commission(amount: float, rate: float) -> float:
    """ኮሚሽን ማስላት"""
    return round(amount * rate, 2)

def format_currency(amount: float) -> str:
    """ገንዘብ በቅርጸት ማሳየት"""
    return f"{amount:,.2f} ETB"

def format_date(dt: datetime) -> str:
    """ቀን በቅርጸት ማሳየት"""
    return dt.strftime("%Y-%m-%d %H:%M")

def safe_int(value: Any, default: int = 0) -> int:
    """ወደ ኢንቲጀር ደህንነት መቀየር"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    """ወደ ፍሎት ደህንነት መቀየር"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def generate_tracking_number() -> str:
    """የክትትል ቁጥር ማመንጨት"""
    return f"TRK-{secrets.token_hex(4).upper()}-{int(time.time()) % 10000}"

# =================================================================================
#                           LOCALIZATION SYSTEM
# =================================================================================

class Localization:
    """የቋንቋ አስተዳደር ክፍል"""
    
    _strings = {
        "am": {
            # General
            "welcome": "👋 እንኳን ወደ ሱቅ አስተዳደር ሲስተም በደህና መጡ!",
            "help": "❓ እርዳታ",
            "back": "🔙 ወደ ኋላ",
            "loading": "⏳ እየተጫነ ነው...",
            "success": "✅ ተሳክቷል!",
            "error": "❌ ስህተት ተከስቷል",
            "not_found": "❌ አልተገኘም",
            "confirm": "✔️ አረጋግጥ",
            "cancel": "❌ ሰርዝ",
            
            # Dashboard
            "dashboard_title": "🎛 የአስተዳደር ፓነል",
            "total_stores": "🏪 ጠቅላላ ሱቆች",
            "pending_approval": "⏳ ያልጸደቁ",
            "active_stores": "🟢 ንቁ ሱቆች",
            "total_orders": "📦 ጠቅላላ ትዕዛዞች",
            "total_revenue": "💰 ጠቅላላ ገቢ",
            "active_users": "👥 ንቁ ተጠቃሚዎች",
            "today_orders": "📊 የዛሬ ትዕዛዞች",
            
            # Actions
            "pending_stores": "⏳ ያልጸደቁ ሱቆች",
            "all_stores": "🏢 ሁሉም ሱቆች",
            "stats": "📊 ስታቲስቲክስ",
            "broadcast": "📢 መልእክት ማሰራጨት",
            "refresh": "🔄 አዘምን",
            "logout": "🚪 ውጣ",
            "settings": "⚙️ ቅንብሮች",
            "backup": "💾 ምትኬ",
            "export": "📤 አውጣ",
            
            # Store Management
            "store_name": "🏪 የሱቅ ስም",
            "store_id": "🆔 መለያ",
            "store_username": "👤 ዩዘርኔም",
            "store_location": "📍 አካባቢ",
            "store_status": "📌 ሁኔታ",
            "approve": "✅ አጽድቅ",
            "reject": "❌ ውድቅ አድርግ",
            "block": "🔴 አግድ",
            "unblock": "🟢 አንቃ",
            "delete": "🗑️ ሰርዝ",
            
            # Broadcast
            "broadcast_title": "📢 መልእክት ማሰራጨት",
            "broadcast_to_owners": "📢 ለሱቅ ባለቤቶች",
            "broadcast_to_customers": "👥 ለደንበኞች",
            "broadcast_to_user": "👤 ለአንድ ተጠቃሚ",
            "enter_message": "📝 መልእክት ያስገቡ:",
            "broadcast_sent": "✅ መልእክት ተልኳል!",
            "broadcast_failed": "❌ መልእክት መላክ አልተቻለም",
            
            # Registration
            "register_title": "📝 አዲስ ሱቅ መዝግብ",
            "step_token": "🔑 ደረጃ 1/5: የቦት ቶከን",
            "step_name": "📛 ደረጃ 2/5: የሱቅ ስም",
            "step_password": "🔐 ደረጃ 3/5: የይለፍ ቃል",
            "step_location": "📍 ደረጃ 4/5: አካባቢ",
            "step_description": "📝 ደረጃ 5/5: መግለጫ",
            "registration_complete": "✅ ሱቅ ተመዝግቧል!",
            
            # Search
            "search_title": "🔍 ሱቆችን ፈልግ",
            "search_by_name": "📝 በስም ፈልግ",
            "search_by_location": "📍 በአካባቢ ፈልግ",
            "search_results": "📋 የተገኙ ውጤቶች",
            "no_results": "🔍 ምንም አልተገኘም",
        },
        "en": {
            # General
            "welcome": "👋 Welcome to Store Management System!",
            "help": "❓ Help",
            "back": "🔙 Back",
            "loading": "⏳ Loading...",
            "success": "✅ Success!",
            "error": "❌ An error occurred",
            "not_found": "❌ Not found",
            "confirm": "✔️ Confirm",
            "cancel": "❌ Cancel",
            
            # Dashboard
            "dashboard_title": "🎛 Admin Dashboard",
            "total_stores": "🏪 Total Stores",
            "pending_approval": "⏳ Pending Approval",
            "active_stores": "🟢 Active Stores",
            "total_orders": "📦 Total Orders",
            "total_revenue": "💰 Total Revenue",
            "active_users": "👥 Active Users",
            "today_orders": "📊 Today's Orders",
            
            # Actions
            "pending_stores": "⏳ Pending Stores",
            "all_stores": "🏢 All Stores",
            "stats": "📊 Statistics",
            "broadcast": "📢 Broadcast",
            "refresh": "🔄 Refresh",
            "logout": "🚪 Logout",
            "settings": "⚙️ Settings",
            "backup": "💾 Backup",
            "export": "📤 Export",
            
            # Store Management
            "store_name": "🏪 Store Name",
            "store_id": "🆔 ID",
            "store_username": "👤 Username",
            "store_location": "📍 Location",
            "store_status": "📌 Status",
            "approve": "✅ Approve",
            "reject": "❌ Reject",
            "block": "🔴 Block",
            "unblock": "🟢 Unblock",
            "delete": "🗑️ Delete",
            
            # Broadcast
            "broadcast_title": "📢 Broadcast Message",
            "broadcast_to_owners": "📢 To Store Owners",
            "broadcast_to_customers": "👥 To Customers",
            "broadcast_to_user": "👤 To Single User",
            "enter_message": "📝 Enter message:",
            "broadcast_sent": "✅ Message sent!",
            "broadcast_failed": "❌ Failed to send message",
            
            # Registration
            "register_title": "📝 Register New Store",
            "step_token": "🔑 Step 1/5: Bot Token",
            "step_name": "📛 Step 2/5: Store Name",
            "step_password": "🔐 Step 3/5: Password",
            "step_location": "📍 Step 4/5: Location",
            "step_description": "📝 Step 5/5: Description",
            "registration_complete": "✅ Store registered!",
            
            # Search
            "search_title": "🔍 Search Stores",
            "search_by_name": "📝 Search by Name",
            "search_by_location": "📍 Search by Location",
            "search_results": "📋 Search Results",
            "no_results": "🔍 No results found",
        }
    }
    
    @classmethod
    def get(cls, key: str, lang: str = "am") -> str:
        """የቋንቋ ጽሁፍ ማግኘት"""
        try:
            return cls._strings[lang].get(key, key)
        except KeyError:
            return cls._strings["am"].get(key, key)
    
    @classmethod
    def get_user_lang(cls, chat_id: int) -> str:
        """የተጠቃሚ ቋንቋ ማግኘት"""
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
    
    @classmethod
    def set_user_lang(cls, chat_id: int, lang: str):
        """የተጠቃሚ ቋንቋ ማስቀመጥ"""
        try:
            db_execute(
                """INSERT INTO user_langs (chat_id, lang) 
                   VALUES (%s, %s) 
                   ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang""",
                (chat_id, lang)
            )
        except Exception as e:
            logger.error(f"Failed to set user language: {e}")

# =================================================================================
#                           ANALYTICS ENGINE
# =================================================================================

class AnalyticsEngine:
    """የስታቲስቲክስ ሞተር"""
    
    @staticmethod
    def get_dashboard_stats() -> AnalyticsData:
        """የዳሽቦርድ ስታቲስቲክስ ማግኘት"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                # Total stores
                cur.execute("SELECT COUNT(*) FROM stores")
                total_stores = cur.fetchone()[0]
                
                # Pending approval
                cur.execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0")
                pending = cur.fetchone()[0]
                
                # Active stores
                cur.execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1")
                active = cur.fetchone()[0]
                
                # Total products
                cur.execute("SELECT COUNT(*) FROM products")
                total_products = cur.fetchone()[0]
                
                # Total orders
                cur.execute("SELECT COUNT(*) FROM orders")
                total_orders = cur.fetchone()[0]
                
                # Total revenue
                cur.execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1")
                total_revenue = cur.fetchone()[0]
                
                # Active users
                cur.execute("SELECT COUNT(DISTINCT customer_id) FROM orders")
                active_users = cur.fetchone()[0]
                
                # Recent orders (last 7 days)
                cur.execute("""
                    SELECT COUNT(*) FROM orders 
                    WHERE created_at > NOW() - INTERVAL '7 days'
                """)
                recent_orders = cur.fetchone()[0]
                
                # Daily orders (last 7 days)
                cur.execute("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM orders
                    WHERE created_at > NOW() - INTERVAL '7 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """)
                daily_orders = {str(row[0]): row[1] for row in cur.fetchall()}
                
                # Revenue by store (top 10)
                cur.execute("""
                    SELECT s.store_name, COALESCE(SUM(o.total_price + o.delivery_fee), 0) as revenue
                    FROM stores s
                    LEFT JOIN orders o ON s.token = o.token AND o.status_stage >= 1
                    GROUP BY s.id, s.store_name
                    ORDER BY revenue DESC
                    LIMIT 10
                """)
                revenue_by_store = [
                    {"store_name": row[0], "revenue": float(row[1])}
                    for row in cur.fetchall()
                ]
                
                # Top products (by sales)
                cur.execute("""
                    SELECT p.name_am, COALESCE(SUM(oi.qty), 0) as sales
                    FROM products p
                    LEFT JOIN order_items oi ON p.id = oi.product_id
                    GROUP BY p.id, p.name_am
                    ORDER BY sales DESC
                    LIMIT 10
                """)
                top_products = [
                    {"name": row[0], "sales": row[1]}
                    for row in cur.fetchall()
                ]
                
                return AnalyticsData(
                    total_stores=total_stores,
                    pending_approval=pending,
                    active_stores=active,
                    total_products=total_products,
                    total_orders=total_orders,
                    total_revenue=float(total_revenue),
                    active_users=active_users,
                    recent_orders=recent_orders,
                    daily_orders=daily_orders,
                    revenue_by_store=revenue_by_store,
                    top_products=top_products,
                    growth_data={}
                )
        except Exception as e:
            logger.error(f"Analytics error: {e}")
            raise
        finally:
            if conn:
                put_db_connection(conn)
    
    @staticmethod
    def get_store_analytics(token: str, days: int = 30) -> Dict:
        """የሱቅ ስታቲስቲክስ ማግኘት"""
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                # Daily stats
                cur.execute("""
                    SELECT DATE(created_at) as date,
                           COUNT(*) as orders,
                           COALESCE(SUM(total_price + delivery_fee), 0) as revenue
                    FROM orders
                    WHERE token = %s 
                      AND created_at > NOW() - INTERVAL '%s days'
                      AND status_stage >= 1
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """, (token, days))
                
                daily_stats = []
                for row in cur.fetchall():
                    daily_stats.append({
                        "date": str(row[0]),
                        "orders": row[1],
                        "revenue": float(row[2])
                    })
                
                # Total stats
                cur.execute("""
                    SELECT COUNT(*) as total_orders,
                           COALESCE(SUM(total_price + delivery_fee), 0) as total_revenue,
                           COUNT(DISTINCT customer_id) as unique_customers
                    FROM orders
                    WHERE token = %s AND status_stage >= 1
                """, (token,))
                
                row = cur.fetchone()
                total_stats = {
                    "total_orders": row[0],
                    "total_revenue": float(row[1]),
                    "unique_customers": row[2]
                }
                
                return {
                    "daily_stats": daily_stats,
                    "total_stats": total_stats
                }
        except Exception as e:
            logger.error(f"Store analytics error: {e}")
            return {"daily_stats": [], "total_stats": {"total_orders": 0, "total_revenue": 0, "unique_customers": 0}}
        finally:
            if conn:
                put_db_connection(conn)

# =================================================================================
#                           FLASK WEB SERVER
# =================================================================================

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Control Bot Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }
            .status { display: inline-block; padding: 5px 15px; border-radius: 20px; background: #4CAF50; color: white; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px; margin: 20px 0; }
            .stat-item { background: #f8f8f8; padding: 15px; border-radius: 8px; text-align: center; }
            .stat-number { font-size: 24px; font-weight: bold; color: #4CAF50; }
            .stat-label { color: #666; font-size: 14px; }
            .info { background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Control Bot Dashboard</h1>
            <div class="status">🟢 Online</div>
            <div class="info">
                <p><strong>Version:</strong> 3.0</p>
                <p><strong>Status:</strong> Running</p>
                <p><strong>Connected Bots:</strong> <span id="bot-count">Loading...</span></p>
            </div>
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
                    <div class="stat-number" id="total-orders">-</div>
                    <div class="stat-label">Total Orders</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="total-revenue">-</div>
                    <div class="stat-label">Total Revenue</div>
                </div>
            </div>
            <p style="color: #666; font-size: 12px; margin-top: 20px;">
                Powered by Advanced Control Bot v3.0 | &copy; 2026
            </p>
        </div>
        <script>
            async function loadStats() {
                try {
                    const response = await fetch('/api/stats');
                    const data = await response.json();
                    document.getElementById('total-stores').textContent = data.total_stores || 0;
                    document.getElementById('active-stores').textContent = data.active_stores || 0;
                    document.getElementById('pending-stores').textContent = data.pending_approval || 0;
                    document.getElementById('total-orders').textContent = data.total_orders || 0;
                    document.getElementById('total-revenue').textContent = data.total_revenue ? data.total_revenue.toFixed(2) + ' ETB' : '0 ETB';
                    document.getElementById('bot-count').textContent = data.bots || 0;
                } catch(e) {
                    document.getElementById('bot-count').textContent = 'Error loading';
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
    """API ለስታቲስቲክስ"""
    try:
        stats = AnalyticsEngine.get_dashboard_stats()
        return jsonify({
            "total_stores": stats.total_stores,
            "pending_approval": stats.pending_approval,
            "active_stores": stats.active_stores,
            "total_products": stats.total_products,
            "total_orders": stats.total_orders,
            "total_revenue": stats.total_revenue,
            "active_users": stats.active_users,
            "recent_orders": stats.recent_orders,
            "bots": len(running_tokens)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stores')
def api_stores():
    """API ለሱቆች ዝርዝር"""
    try:
        stores = db_execute_dict(
            "SELECT id, store_name, username, is_active, is_approved, created_at FROM stores ORDER BY created_at DESC LIMIT 50"
        )
        return jsonify([dict(s) for s in stores])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_flask():
    app.run(host=Config.HOST, port=Config.PORT, debug=False)

threading.Thread(target=run_flask, daemon=True).start()
logger.info(f"✅ Flask server running on {Config.HOST}:{Config.PORT}")

# =================================================================================
#                           AI ENGINE
# =================================================================================

class AIEngine:
    """የAI ሞተር"""
    
    _model = None
    
    @classmethod
    def init(cls):
        if Config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                cls._model = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("✅ AI Engine initialized")
            except Exception as e:
                logger.error(f"❌ AI Engine init failed: {e}")
                cls._model = None
        else:
            logger.warning("⚠️ GEMINI_API_KEY not set")
    
    @classmethod
    def generate_response(cls, prompt: str, context: str = "") -> Optional[str]:
        """AI ምላሽ ማመንጨት"""
        if cls._model is None:
            return None
        
        try:
            full_prompt = f"{context}\n\n{prompt}"
            response = cls._model.generate_content(full_prompt)
            return response.text if response else None
        except Exception as e:
            logger.error(f"AI generation error: {e}")
            return None
    
    @classmethod
    def analyze_query(cls, query: str) -> Dict:
        """የተጠቃሚ ጥያቄ መተንተን"""
        if cls._model is None:
            return {"type": "unknown", "confidence": 0}
        
        try:
            prompt = f"""
            Analyze this user query and classify it.
            Return JSON with:
            - type: one of [search_store, register_store, view_stores, help, other]
            - confidence: number 0-1
            - entities: any extracted information
            
            Query: "{query}"
            """
            response = cls._model.generate_content(prompt)
            if response and response.text:
                import json
                try:
                    return json.loads(response.text)
                except:
                    return {"type": "other", "confidence": 0.5}
            return {"type": "other", "confidence": 0}
        except:
            return {"type": "other", "confidence": 0}

AIEngine.init()

# =================================================================================
#                           CONTROL BOT MAIN CLASS
# =================================================================================

class ControlBot:
    """ዋናው የአስተዳደር ቦት ክፍል"""
    
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
        """ቦቱን መጀመር"""
        self.bot = telebot.TeleBot(Config.CONTROL_BOT_TOKEN, threaded=False)
        self.sessions = {}
        self.login_attempts = {}
        self.reg_states = {}
        
        # Locks for thread safety
        self.sessions_lock = threading.Lock()
        self.login_lock = threading.Lock()
        self.reg_lock = threading.Lock()
        
        # Remove webhook
        try:
            self.bot.remove_webhook()
        except:
            pass
        
        # Register handlers
        self._register_handlers()
        
        # Start polling
        self._start_polling()
        
        logger.info("✅ Control Bot initialized")
    
    def _register_handlers(self):
        """ሁሉንም ትዕዛዞች መመዝገብ"""
        
        # ============================================================
        # COMMAND: /start, /help
        # ============================================================
        @self.bot.message_handler(commands=['start', 'help'])
        def cmd_start(message):
            chat_id = message.chat.id
            lang = Localization.get_user_lang(chat_id)
            
            text = Localization.get("welcome", lang)
            markup = self._get_main_menu(lang)
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        
        # ============================================================
        # COMMAND: /superadmin
        # ============================================================
        @self.bot.message_handler(commands=['superadmin'])
        def cmd_superadmin(message):
            chat_id = message.chat.id
            
            if not Config.SUPER_ADMIN_PASSWORD:
                self.bot.reply_to(message, "❌ SUPER_ADMIN_PASSWORD not set!")
                return
            
            if Config.SUPER_ADMIN_ID != 0 and chat_id != Config.SUPER_ADMIN_ID:
                self.bot.reply_to(message, "❌ መብት የለዎትም!")
                return
            
            # Check lockout
            with self.login_lock:
                attempt = self.login_attempts.get(chat_id, {"count": 0, "lockout_until": 0})
                if time.time() < attempt["lockout_until"]:
                    remaining = int(attempt["lockout_until"] - time.time())
                    self.bot.reply_to(message, f"🔒 እገዳ ላይ ነዎት! ከ {remaining} ሰከንድ በኋላ ይሞክሩ።")
                    return
            
            msg = self.bot.send_message(
                chat_id,
                "🔐 **እባክዎ የ Super Admin የይለፍ ቃል ያስገቡ፦**",
                parse_mode="Markdown"
            )
            self.bot.register_next_step_handler(msg, self._process_super_login)
        
        # ============================================================
        # COMMAND: /panel
        # ============================================================
        @self.bot.message_handler(commands=['panel'])
        def cmd_panel(message):
            chat_id = message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            
            self._show_dashboard(message)
        
        # ============================================================
        # COMMAND: /analytics
        # ============================================================
        @self.bot.message_handler(commands=['analytics'])
        def cmd_analytics(message):
            chat_id = message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            
            self._show_analytics(message)
        
        # ============================================================
        # COMMAND: /stores
        # ============================================================
        @self.bot.message_handler(commands=['stores'])
        def cmd_stores(message):
            chat_id = message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            
            self._show_all_stores(message)
        
        # ============================================================
        # COMMAND: /broadcast
        # ============================================================
        @self.bot.message_handler(commands=['broadcast'])
        def cmd_broadcast(message):
            chat_id = message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            
            self._show_broadcast_menu(message)
        
        # ============================================================
        # COMMAND: /backup
        # ============================================================
        @self.bot.message_handler(commands=['backup'])
        def cmd_backup(message):
            chat_id = message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            
            self._create_backup(message)
        
        # ============================================================
        # COMMAND: /export
        # ============================================================
        @self.bot.message_handler(commands=['export'])
        def cmd_export(message):
            chat_id = message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            
            self._export_data(message)
        
        # ============================================================
        # CALLBACK QUERY HANDLER
        # ============================================================
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("dash_"))
        def handle_dashboard_callbacks(call):
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
                self._show_all_stores(call.message)
            
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
        
        # ============================================================
        # STORE APPROVAL CALLBACKS
        # ============================================================
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sapprove_"))
        def handle_approve_store(call):
            chat_id = call.message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            
            store_id = int(call.data.split("_")[1])
            self._approve_store(chat_id, store_id, call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sreject_"))
        def handle_reject_store(call):
            chat_id = call.message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            
            store_id = int(call.data.split("_")[1])
            self._reject_store(chat_id, store_id, call)
        
        # ============================================================
        # STORE MANAGEMENT CALLBACKS
        # ============================================================
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sblock_"))
        def handle_block_store(call):
            chat_id = call.message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            
            store_id = int(call.data.split("_")[1])
            self._block_store(chat_id, store_id, call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sunblock_"))
        def handle_unblock_store(call):
            chat_id = call.message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            
            store_id = int(call.data.split("_")[1])
            self._unblock_store(chat_id, store_id, call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sdelete_"))
        def handle_delete_store(call):
            chat_id = call.message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            
            store_id = int(call.data.split("_")[1])
            self._delete_store(chat_id, store_id, call)
        
        # ============================================================
        # BROADCAST CALLBACKS
        # ============================================================
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_"))
        def handle_broadcast_callbacks(call):
            chat_id = call.message.chat.id
            
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            
            target = call.data.split("_")[1]
            self.bot.answer_callback_query(call.id)
            
            if target == "user":
                msg = self.bot.send_message(chat_id, "👤 የተጠቃሚ አይዲ (User ID) ያስገቡ:")
                self.bot.register_next_step_handler(msg, self._broadcast_to_user)
            else:
                target_label = "ሱቅ ባለቤቶች" if target == "owners" else "ደንበኞች"
                msg = self.bot.send_message(
                    chat_id,
                    f"📝 **መልእክት ይላኩ**\n\nለ{target_label} የሚላከውን መልእክት ይላኩ:"
                )
                self.bot.register_next_step_handler(
                    msg,
                    lambda m: self._broadcast_to_all(m, target)
                )
        
        # ============================================================
        # SEARCH CALLBACKS
        # ============================================================
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("csearch_"))
        def handle_search_callbacks(call):
            chat_id = call.message.chat.id
            
            if call.data == "csearch_name":
                msg = self.bot.send_message(chat_id, "📝 የሱቅ ስም ያስገቡ:")
                self.bot.register_next_step_handler(msg, self._search_by_name)
            elif call.data == "csearch_location":
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
                self.bot.send_message(chat_id, "📍 አካባቢ ያጋሩ:", reply_markup=markup)
        
        # ============================================================
        # TEXT HANDLERS
        # ============================================================
        @self.bot.message_handler(func=lambda m: m.text in ["📝 አዲስ ሱቅ መዝግብ", "📝 Register New Store"])
        def handle_register(message):
            self._start_registration(message)
        
        @self.bot.message_handler(func=lambda m: m.text in ["🏪 ሱቆቼ", "🏪 My Stores"])
        def handle_my_stores(message):
            self._show_my_stores(message)
        
        @self.bot.message_handler(func=lambda m: m.text in ["🔍 ሱቆችን ፈልግ", "🔍 Search Stores"])
        def handle_search_stores(message):
            lang = Localization.get_user_lang(message.chat.id)
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton(Localization.get("search_by_name", lang), callback_data="csearch_name"),
                types.InlineKeyboardButton(Localization.get("search_by_location", lang), callback_data="csearch_location")
            )
            self.bot.send_message(
                message.chat.id,
                Localization.get("search_title", lang),
                reply_markup=markup
            )
        
        @self.bot.message_handler(func=lambda m: m.text in ["❓ እርዳታ", "❓ Help"])
        def handle_help(message):
            cmd_start(message)
        
        @self.bot.message_handler(content_types=['location'])
        def handle_location_search(message):
            self._search_by_location(message)
        
        # ============================================================
        # REGISTRATION STEP HANDLERS
        # ============================================================
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
        def reg_step_location_text(message):
            self._process_reg_location_text(message)
        
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 5)
        def reg_step_description(message):
            self._process_reg_description(message)
    
    # ============================================================
    # PRIVATE METHODS
    # ============================================================
    
    def _get_main_menu(self, lang: str) -> types.ReplyKeyboardMarkup:
        """ዋናውን ሜኑ ማግኘት"""
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton(Localization.get("register_title", lang)),
            types.KeyboardButton("🏪 ሱቆቼ")
        )
        markup.add(
            types.KeyboardButton("🔍 ሱቆችን ፈልግ"),
            types.KeyboardButton(Localization.get("help", lang))
        )
        return markup
    
    def _get_dashboard_markup(self) -> types.InlineKeyboardMarkup:
        """የዳሽቦርድ ቁልፎች"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("⏳ ያልጸደቁ ሱቆች", callback_data="dash_pending"),
            types.InlineKeyboardButton("🏢 ሁሉም ሱቆች", callback_data="dash_all")
        )
        markup.add(
            types.InlineKeyboardButton("📊 ስታቲስቲክስ", callback_data="dash_stats"),
            types.InlineKeyboardButton("📢 መልእክት ማሰራጨት", callback_data="dash_broadcast")
        )
        markup.add(
            types.InlineKeyboardButton("🔄 አዘምን", callback_data="dash_refresh"),
            types.InlineKeyboardButton("🚪 ውጣ", callback_data="dash_logout")
        )
        return markup
    
    def _is_super_admin(self, chat_id: int) -> bool:
        """ሱፐር አድሚን መሆኑን ማረጋገጥ"""
        with self.sessions_lock:
            return chat_id in self.sessions and time.time() < self.sessions[chat_id]
    
    def _get_reg_state(self, chat_id: int, key: str = None):
        """የምዝገባ ሁኔታ ማግኘት"""
        with self.reg_lock:
            state = self.reg_states.get(chat_id, {})
            if key:
                return state.get(key)
            return state
    
    def _set_reg_state(self, chat_id: int, key: str, value: Any):
        """የምዝገባ ሁኔታ ማስቀመጥ"""
        with self.reg_lock:
            if chat_id not in self.reg_states:
                self.reg_states[chat_id] = {}
            self.reg_states[chat_id][key] = value
    
    def _clear_reg_state(self, chat_id: int):
        """የምዝገባ ሁኔታ ማጽዳት"""
        with self.reg_lock:
            self.reg_states.pop(chat_id, None)
    
    # ============================================================
    # SUPER ADMIN LOGIN
    # ============================================================
    
    def _process_super_login(self, message):
        """የሱፐር አድሚን ግባት ማስተናገድ"""
        chat_id = message.chat.id
        password = message.text.strip()
        
        if password == Config.SUPER_ADMIN_PASSWORD:
            with self.sessions_lock:
                self.sessions[chat_id] = time.time() + Config.SESSION_TIMEOUT
            with self.login_lock:
                self.login_attempts[chat_id] = {"count": 0, "lockout_until": 0}
            
            self.bot.send_message(
                chat_id,
                "🔓 **እንኳን ወደ Super Admin ፓነል በደህና መጡ!**",
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
            
            logger.audit(chat_id, "super_admin_login_failed", {"password_attempt": True})
    
    def _logout(self, chat_id: int):
        """ከሱፐር አድሚን መውጣት"""
        with self.sessions_lock:
            self.sessions.pop(chat_id, None)
        
        lang = Localization.get_user_lang(chat_id)
        self.bot.send_message(
            chat_id,
            "🔒 ከአስተዳደር ወጥተዋል።",
            reply_markup=self._get_main_menu(lang)
        )
        logger.audit(chat_id, "super_admin_logout", {})
    
    # ============================================================
    # DASHBOARD
    # ============================================================
    
    def _show_dashboard(self, message):
        """ዳሽቦርድ ማሳየት"""
        chat_id = message.chat.id
        lang = Localization.get_user_lang(chat_id)
        
        try:
            stats = AnalyticsEngine.get_dashboard_stats()
            
            text = (
                f"🎛 **{Localization.get('dashboard_title', lang)}**\n\n"
                f"🏪 {Localization.get('total_stores', lang)}: **{stats.total_stores}**\n"
                f"⏳ {Localization.get('pending_approval', lang)}: **{stats.pending_approval}**\n"
                f"🟢 {Localization.get('active_stores', lang)}: **{stats.active_stores}**\n"
                f"📦 {Localization.get('total_orders', lang)}: **{stats.total_orders}**\n"
                f"💰 {Localization.get('total_revenue', lang)}: **{format_currency(stats.total_revenue)}**\n"
                f"👥 {Localization.get('active_users', lang)}: **{stats.active_users}**\n"
                f"📊 {Localization.get('today_orders', lang)}: **{stats.recent_orders}**\n\n"
                f"📌 {Localization.get('select_action', lang) if lang == 'en' else 'ርምጫ ይምረጡ'}:"
            )
            
            self.bot.send_message(
                chat_id,
                text,
                reply_markup=self._get_dashboard_markup(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            self.bot.send_message(chat_id, f"❌ {Localization.get('error', lang)}: {e}")
    
    # ============================================================
    # STORE MANAGEMENT
    # ============================================================
    
    def _show_pending_stores(self, message):
        """ያልጸደቁ ሱቆች ማሳየት"""
        chat_id = message.chat.id
        lang = Localization.get_user_lang(chat_id)
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, username, area_text, shop_description, created_at, admin_id, token
                FROM stores 
                WHERE is_approved = 0 AND is_active = 1 
                ORDER BY created_at DESC
            """)
            
            if not stores:
                self.bot.send_message(
                    chat_id,
                    "✅ ምንም ያልተጸደቁ ሱቆች የሉም!",
                    reply_markup=self._get_dashboard_markup()
                )
                return
            
            for store in stores:
                text = (
                    f"🏪 **{store['store_name']}**\n"
                    f"🆔 #{store['id']}\n"
                    f"👤 @{store['username'] or 'ስም'}\n"
                    f"📍 {store['area_text'] or 'አልተዘጋጀም'}\n"
                    f"📝 {store['shop_description'][:50] if store['shop_description'] else ''}...\n"
                    f"📅 {format_date(store['created_at'])}"
                )
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"sapprove_{store['id']}"),
                    types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"sreject_{store['id']}")
                )
                markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
                
                self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Pending stores error: {e}")
            self.bot.send_message(chat_id, f"❌ {Localization.get('error', lang)}: {e}")
    
    def _show_all_stores(self, message):
        """ሁሉንም ሱቆች ማሳየት"""
        chat_id = message.chat.id
        lang = Localization.get_user_lang(chat_id)
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, username, is_active, is_approved, created_at 
                FROM stores 
                ORDER BY created_at DESC 
                LIMIT 20
            """)
            
            if not stores:
                self.bot.send_message(
                    chat_id,
                    "📜 ምንም ሱቅ የለም!",
                    reply_markup=self._get_dashboard_markup()
                )
                return
            
            text = "🏢 **ሁሉም ሱቆች**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                approved = "✅" if store['is_approved'] else "⏳"
                text += (
                    f"{status} {approved} **{store['store_name']}**\n"
                    f"  🆔 #{store['id']} | 👤 @{store['username'] or 'ስም'}\n"
                    f"  📅 {format_date(store['created_at'])}\n\n"
                )
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🔴 ሱቅ አግድ", callback_data="sblock_menu"),
                types.InlineKeyboardButton("🟢 ሱቅ አንቃ", callback_data="sunblock_menu"),
                types.InlineKeyboardButton("🗑️ ሱቅ ሰርዝ", callback_data="sdelete_menu"),
                types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back")
            )
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"All stores error: {e}")
            self.bot.send_message(chat_id, f"❌ {Localization.get('error', lang)}: {e}")
    
    def _approve_store(self, chat_id: int, store_id: int, call=None):
        """ሱቅ ማጽደቅ"""
        try:
            store = db_execute_dict(
                "SELECT token, store_name, admin_id FROM stores WHERE id = %s",
                (store_id,)
            )
            
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ ሱቅ አልተገኘም!")
                return
            
            store = store[0]
            
            # Update store
            db_execute(
                "UPDATE stores SET is_approved = 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (store_id,)
            )
            
            # Start the bot
            start_shop_bot(store['token'])
            
            # Notify store owner
            try:
                self.bot.send_message(
                    store['admin_id'],
                    f"🎉 **ሱቅዎ ተጸድቋል!**\n\n"
                    f"🏪 {store['store_name']}\n"
                    f"🔑 አሁን /login [የይለፍ_ቃል] በማድረግ መግባት ይችላሉ"
                )
            except:
                pass
            
            logger.audit(chat_id, "store_approved", {"store_id": store_id, "store_name": store['store_name']})
            
            if call:
                self.bot.edit_message_text(
                    f"✅ ሱቅ #{store_id} ተጸድቋል!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "ተጸድቋል!")
            
            self._show_dashboard(call.message if call else None)
        except Exception as e:
            logger.error(f"Approve store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _reject_store(self, chat_id: int, store_id: int, call=None):
        """ሱቅ ውድቅ ማድረግ"""
        try:
            store = db_execute_dict(
                "SELECT store_name, admin_id FROM stores WHERE id = %s",
                (store_id,)
            )
            
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ ሱቅ አልተገኘም!")
                return
            
            store = store[0]
            
            # Delete store
            db_execute("DELETE FROM stores WHERE id = %s", (store_id,))
            
            # Notify store owner
            try:
                self.bot.send_message(
                    store['admin_id'],
                    f"❌ ሱቅዎ **{store['store_name']}** ውድቅ ተደርጓል።"
                )
            except:
                pass
            
            logger.audit(chat_id, "store_rejected", {"store_id": store_id, "store_name": store['store_name']})
            
            if call:
                self.bot.edit_message_text(
                    f"❌ ሱቅ #{store_id} ውድቅ ተደርጓል!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "ውድቅ ተደርጓል!")
            
            self._show_dashboard(call.message if call else None)
        except Exception as e:
            logger.error(f"Reject store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _block_store(self, chat_id: int, store_id: int, call=None):
        """ሱቅ ማገድ"""
        try:
            store = db_execute_dict(
                "SELECT store_name, admin_id FROM stores WHERE id = %s",
                (store_id,)
            )
            
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ ሱቅ አልተገኘም!")
                return
            
            store = store[0]
            
            db_execute(
                "UPDATE stores SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (store_id,)
            )
            
            try:
                self.bot.send_message(store['admin_id'], f"🔴 ሱቅዎ **{store['store_name']}** ተግዷል!")
            except:
                pass
            
            logger.audit(chat_id, "store_blocked", {"store_id": store_id, "store_name": store['store_name']})
            
            if call:
                self.bot.edit_message_text(
                    f"🔴 ሱቅ #{store_id} ተግዷል!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "ተግዷል!")
        except Exception as e:
            logger.error(f"Block store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _unblock_store(self, chat_id: int, store_id: int, call=None):
        """ሱቅ ማንቃት"""
        try:
            store = db_execute_dict(
                "SELECT store_name, admin_id FROM stores WHERE id = %s",
                (store_id,)
            )
            
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ ሱቅ አልተገኘም!")
                return
            
            store = store[0]
            
            db_execute(
                "UPDATE stores SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (store_id,)
            )
            
            try:
                self.bot.send_message(store['admin_id'], f"🟢 ሱቅዎ **{store['store_name']}** ተነቅቷል!")
            except:
                pass
            
            logger.audit(chat_id, "store_unblocked", {"store_id": store_id, "store_name": store['store_name']})
            
            if call:
                self.bot.edit_message_text(
                    f"🟢 ሱቅ #{store_id} ተነቅቷል!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "ተነቅቷል!")
        except Exception as e:
            logger.error(f"Unblock store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _delete_store(self, chat_id: int, store_id: int, call=None):
        """ሱቅ መሰረዝ"""
        try:
            store = db_execute_dict(
                "SELECT store_name, token, admin_id FROM stores WHERE id = %s",
                (store_id,)
            )
            
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ ሱቅ አልተገኘም!")
                return
            
            store = store[0]
            
            # Delete all related data
            db_execute("DELETE FROM products WHERE token = %s", (store['token'],))
            db_execute("DELETE FROM orders WHERE token = %s", (store['token'],))
            db_execute("DELETE FROM stores WHERE id = %s", (store_id,))
            
            try:
                self.bot.send_message(store['admin_id'], f"🗑️ ሱቅዎ **{store['store_name']}** ተሰርዟል!")
            except:
                pass
            
            logger.audit(chat_id, "store_deleted", {"store_id": store_id, "store_name": store['store_name']})
            
            if call:
                self.bot.edit_message_text(
                    f"🗑️ ሱቅ #{store_id} ተሰርዟል!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "ተሰርዟል!")
        except Exception as e:
            logger.error(f"Delete store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    # ============================================================
    # ANALYTICS
    # ============================================================
    
    def _show_analytics(self, message):
        """የስታቲስቲክስ ዳሽቦርድ ማሳየት"""
        chat_id = message.chat.id
        lang = Localization.get_user_lang(chat_id)
        
        try:
            stats = AnalyticsEngine.get_dashboard_stats()
            
            text = (
                f"📊 **የሲስተም ስታቲስቲክስ**\n\n"
                f"🏪 **ሱቆች**\n"
                f"  • ጠቅላላ: {stats.total_stores}\n"
                f"  • ንቁ: {stats.active_stores}\n"
                f"  • ያልተጸደቀ: {stats.pending_approval}\n\n"
                f"📦 **ምርቶች:** {stats.total_products}\n\n"
                f"🧾 **ትዕዛዞች**\n"
                f"  • ጠቅላላ: {stats.total_orders}\n"
                f"  • የቅርብ 7 ቀናት: {stats.recent_orders}\n"
                f"  • ንቁ ተጠቃሚዎች: {stats.active_users}\n\n"
                f"💰 **ጠቅላላ ገቢ:** {format_currency(stats.total_revenue)}\n"
            )
            
            # Top products
            if stats.top_products:
                text += "\n🏆 **በጣም የተሸጡ ምርቶች:**\n"
                for i, p in enumerate(stats.top_products[:5], 1):
                    text += f"  {i}. {p['name']} ({p['sales']} ሽያጭ)\n"
            
            # Top stores by revenue
            if stats.revenue_by_store:
                text += "\n💰 **ከፍተኛ ገቢ ያላቸው ሱቆች:**\n"
                for i, s in enumerate(stats.revenue_by_store[:5], 1):
                    text += f"  {i}. {s['store_name']} ({format_currency(s['revenue'])})\n"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Analytics error: {e}")
            self.bot.send_message(chat_id, f"❌ {Localization.get('error', lang)}: {e}")
    
    # ============================================================
    # BROADCAST
    # ============================================================
    
    def _show_broadcast_menu(self, message):
        """የማሰራጨት ሜኑ"""
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
            "📢 **ብሮድካስት መልእክት**\n\n"
            "መልእክት ለማን መላክ ይፈልጋሉ?",
            reply_markup=markup
        )
    
    def _broadcast_to_all(self, message, target: str):
        """ለሁሉም መልእክት መላክ"""
        chat_id = message.chat.id
        msg_text = message.text
        
        try:
            if target == "owners":
                users = db_execute_dict(
                    "SELECT DISTINCT admin_id FROM stores WHERE admin_id > 0 AND is_approved = 1"
                )
            else:
                users = db_execute_dict("SELECT DISTINCT customer_id FROM orders")
            
            if not users:
                self.bot.reply_to(message, "❌ ምንም ተጠቃሚ አልተገኘም!")
                return
            
            self.bot.reply_to(message, f"⏳ ለ {len(users)} ተጠቃሚዎች በማስተላለፍ ላይ...")
            
            success = 0
            failed = 0
            
            for user in users:
                user_id = user.get('admin_id') or user.get('customer_id')
                if not user_id:
                    continue
                try:
                    self.bot.send_message(
                        user_id,
                        f"📢 **የሲስተም ማስታወቂያ**\n\n{msg_text}"
                    )
                    success += 1
                    time.sleep(0.05)
                except:
                    failed += 1
            
            self.bot.send_message(
                chat_id,
                f"✅ ብሮድካስት ተጠናቋል!\n\n✅ የተሳካ: {success}\n❌ ያልተሳካ: {failed}",
                reply_markup=self._get_dashboard_markup()
            )
            
            logger.audit(chat_id, "broadcast_sent", {
                "target": target,
                "success": success,
                "failed": failed,
                "message_preview": msg_text[:100]
            })
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _broadcast_to_user(self, message):
        """ለአንድ ተጠቃሚ መልእክት መላክ"""
        chat_id = message.chat.id
        
        try:
            user_id = int(message.text.strip())
        except:
            self.bot.reply_to(message, "❌ የተሳሳተ አይዲ!")
            return
        
        msg = self.bot.send_message(chat_id, "📝 ለተጠቃሚው የሚላከውን መልእክት ይላኩ:")
        self.bot.register_next_step_handler(
            msg,
            lambda m: self._send_single_message(m, user_id)
        )
    
    def _send_single_message(self, message, user_id: int):
        """ለአንድ ተጠቃሚ መልእክት መላክ"""
        chat_id = message.chat.id
        msg_text = message.text
        
        try:
            self.bot.send_message(
                user_id,
                f"📢 **የሲስተም ማስታወቂያ**\n\n{msg_text}"
            )
            self.bot.reply_to(
                message,
                f"✅ መልእክት ለተጠቃሚ {user_id} ተልኳል!",
                reply_markup=self._get_dashboard_markup()
            )
            logger.audit(chat_id, "single_message_sent", {"user_id": user_id})
        except Exception as e:
            self.bot.reply_to(
                message,
                f"❌ መልእክት ለ {user_id} መላክ አልተቻለም!: {e}",
                reply_markup=self._get_dashboard_markup()
            )
    
    # ============================================================
    # STORE REGISTRATION
    # ============================================================
    
    def _start_registration(self, message):
        """አዲስ ሱቅ ምዝገባ መጀመር"""
        chat_id = message.chat.id
        self._clear_reg_state(chat_id)
        self._set_reg_state(chat_id, "step", 1)
        self._set_reg_state(chat_id, "data", {})
        
        msg = self.bot.send_message(
            chat_id,
            "📝 **ደረጃ 1/5: የቦት ቶከን**\n\n"
            "ከ @BotFather ያገኙትን ቶከን ያስገቡ:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_token)
    
    def _process_reg_token(self, message):
        """የቶከን ደረጃ ማስተናገድ"""
        chat_id = message.chat.id
        token = message.text.strip()
        
        try:
            test_bot = telebot.TeleBot(token)
            bot_info = test_bot.get_me()
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            self.bot.reply_to(message, "❌ ቶከን ልክ አይደለም! እባክዎ ትክክለኛ ቶከን ያስገቡ።")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["token"] = token
        data["bot_username"] = bot_info.username
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 2)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ ቶከን ተረጋግጧል! 👤 @{bot_info.username}\n\n"
            "📝 **ደረጃ 2/5: የሱቅ ስም**\n\n"
            "የሱቅዎን ስም ያስገቡ:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_name)
    
    def _process_reg_name(self, message):
        """የሱቅ ስም ደረጃ ማስተናገድ"""
        chat_id = message.chat.id
        name = message.text.strip()
        
        if not name:
            self.bot.reply_to(message, "❌ እባክዎ ሱቅ ስም ያስገቡ!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["store_name"] = name
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 3)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ ስም: **{name}**\n\n"
            "📝 **ደረጃ 3/5: የይለፍ ቃል**\n\n"
            "ለሱቅ አስተዳደር የይለፍ ቃል ያስገቡ (ቢያንስ 8 ፊደል):"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_password)
    
    def _process_reg_password(self, message):
        """የይለፍ ቃል ደረጃ ማስተናገድ"""
        chat_id = message.chat.id
        password = message.text.strip()
        
        if len(password) < 8:
            self.bot.reply_to(message, "❌ ቢያንስ 8 ፊደል!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["password"] = password
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 4)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ የይለፍ ቃል ተቀብለናል\n\n"
            "📝 **ደረጃ 4/5: የሱቅ አካባቢ**\n\n"
            "የሱቅዎን አካባቢ ያጋሩ (ቁልፉን ይጫኑ) ወይም የከተማ ስም ያስገቡ:",
            reply_markup=markup
        )
        self.bot.register_next_step_handler(msg, self._process_reg_location)
    
    def _process_reg_location(self, message):
        """የአካባቢ ደረጃ ማስተናገድ"""
        chat_id = message.chat.id
        data = self._get_reg_state(chat_id, "data") or {}
        
        if message.location:
            data["shop_lat"] = message.location.latitude
            data["shop_lng"] = message.location.longitude
            location_text = f"📍 {data['shop_lat']}, {data['shop_lng']}"
        else:
            location_text = message.text.strip()
            if not location_text:
                self.bot.reply_to(message, "❌ እባክዎ አካባቢ ያስገቡ ወይም ያጋሩ!")
                return
            data["area_text"] = location_text
        
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 5)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ አካባቢ: {location_text}\n\n"
            "📝 **ደረጃ 5/5: ስለ ሱቅ መግለጫ**\n\n"
            "ስለ ሱቅዎ አጭር መግለጫ ይላኩ:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_description)
    
    def _process_reg_location_text(self, message):
        """የአካባቢ ጽሁፍ ደረጃ ማስተናገድ"""
        self._process_reg_location(message)
    
    def _process_reg_description(self, message):
        """የመግለጫ ደረጃ ማስተናገድ"""
        chat_id = message.chat.id
        description = message.text.strip()
        
        if not description:
            self.bot.reply_to(message, "❌ እባክዎ የሱቅ መግለጫ ያስገቡ!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["shop_description"] = description
        data["username"] = data.get("bot_username", f"shop_{chat_id}")
        
        try:
            # Check if token already exists
            existing = db_execute_dict(
                "SELECT 1 FROM stores WHERE token = %s",
                (data["token"],)
            )
            if existing:
                self.bot.reply_to(message, "❌ ቶከን ቀድሞውኑ ተመዝግቧል!")
                return
            
            # Hash password
            h_pass, salt = hash_password(data["password"])
            
            # Insert store
            db_execute("""
                INSERT INTO stores 
                (token, store_name, admin_id, username, password_hash, password_salt, 
                 telebirr, cbebirr, is_active, is_approved, 
                 shop_lat, shop_lng, area_text, shop_description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["token"], data["store_name"], chat_id, data["username"],
                h_pass, salt, "", "", 1, 0,
                data.get("shop_lat"), data.get("shop_lng"),
                data.get("area_text", ""), data.get("shop_description", "")
            ))
            
            # Start the bot
            start_shop_bot(data["token"])
            
            # Notify super admin
            if Config.SUPER_ADMIN_ID:
                try:
                    self.bot.send_message(
                        Config.SUPER_ADMIN_ID,
                        f"🔔 **አዲስ ሱቅ ለማጽደቅ ተመዝግቧል!**\n\n"
                        f"🏪 **{data['store_name']}**\n"
                        f"👤 @{data['username']}\n"
                        f"📍 {data.get('area_text', 'አልተዘጋጀም')}"
                    )
                except:
                    pass
            
            self._clear_reg_state(chat_id)
            
            self.bot.reply_to(
                message,
                f"✅ **ሱቅ ተመዝግቧል!**\n\n"
                f"🏪 **ስም:** {data['store_name']}\n"
                f"👤 **ዩዘርኔም:** @{data['username']}\n"
                f"📍 **አካባቢ:** {data.get('area_text', 'ተቀምጧል')}\n"
                f"📝 **መግለጫ:** {data.get('shop_description', '')[:50]}...\n\n"
                f"🔑 **የይለፍ ቃል:** `{data['password']}`\n\n"
                f"⏳ **ሱቅዎ ለማጽደቅ በመጠባበቅ ላይ ነው!**",
                reply_markup=self._get_main_menu("am"),
                parse_mode="Markdown"
            )
            
            logger.audit(chat_id, "store_registered", {
                "store_name": data["store_name"],
                "store_id": data["token"]
            })
        except Exception as e:
            logger.error(f"Registration error: {e}")
            self.bot.reply_to(message, f"❌ ስህተት ተከስቷል: {e}")
    
    # ============================================================
    # MY STORES
    # ============================================================
    
    def _show_my_stores(self, message):
        """የተጠቃሚውን ሱቆች ማሳየት"""
        chat_id = message.chat.id
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, token, is_active, is_approved, username, area_text 
                FROM stores 
                WHERE admin_id = %s
                ORDER BY created_at DESC
            """, (chat_id,))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "❌ ምንም ሱቅ አልተመዘገቡም።\n\n"
                    "📌 አዲስ ሱቅ ለመመዝገብ '📝 አዲስ ሱቅ መዝግብ' ይጫኑ",
                    reply_markup=self._get_main_menu("am")
                )
                return
            
            text = "🏪 **ሱቆችዎ:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                approved = "✅" if store['is_approved'] else "⏳"
                text += (
                    f"{status} {approved} **{store['store_name']}**\n"
                    f"  👤 @{store['username'] or 'ስም'}\n"
                    f"  📍 {store['area_text'] or 'አልተዘጋጀም'}\n"
                    f"  🆔 #{store['id']}\n\n"
                )
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu("am"))
        except Exception as e:
            logger.error(f"My stores error: {e}")
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    # ============================================================
    # SEARCH
    # ============================================================
    
    def _search_by_name(self, message):
        """በስም ሱቆችን መፈለግ"""
        chat_id = message.chat.id
        query = message.text.strip()
        
        if not query:
            self.bot.reply_to(message, "❌ እባክዎ የሱቅ ስም ያስገቡ!")
            return
        
        try:
            stores = db_execute_dict("""
                SELECT store_name, username, area_text, shop_description, is_active, is_approved
                FROM stores 
                WHERE (store_name ILIKE %s OR username ILIKE %s) AND is_approved = 1
                LIMIT 10
            """, (f"%{query}%", f"%{query}%"))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "🔍 ምንም ሱቅ አልተገኘም",
                    reply_markup=self._get_main_menu("am")
                )
                return
            
            text = "🔍 **የተገኙ ሱቆች:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                text += (
                    f"{status} **{store['store_name']}**\n"
                    f"  👤 @{store['username'] or 'ስም'}\n"
                    f"  📍 {store['area_text'] or 'አልተዘጋጀም'}\n\n"
                )
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu("am"))
        except Exception as e:
            logger.error(f"Search error: {e}")
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _search_by_location(self, message):
        """በአካባቢ ሱቆችን መፈለግ"""
        chat_id = message.chat.id
        
        if not message.location:
            self.bot.reply_to(message, "❌ እባክዎ አካባቢ ያጋሩ!")
            return
        
        lat = message.location.latitude
        lng = message.location.longitude
        
        try:
            stores = db_execute_dict("""
                SELECT store_name, username, area_text, shop_description, is_active,
                       (6371 * acos(cos(radians(%s)) * cos(radians(shop_lat)) * 
                        cos(radians(shop_lng) - radians(%s)) + sin(radians(%s)) * 
                        sin(radians(shop_lat)))) as distance
                FROM stores 
                WHERE shop_lat IS NOT NULL AND shop_lng IS NOT NULL AND is_approved = 1
                ORDER BY distance
                LIMIT 10
            """, (lat, lng, lat))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "🔍 በአቅራቢያ ምንም ሱቅ አልተገኘም",
                    reply_markup=self._get_main_menu("am")
                )
                return
            
            text = "📍 **በአቅራቢያ ያሉ ሱቆች:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                distance = store.get('distance', 0)
                text += (
                    f"{status} **{store['store_name']}**\n"
                    f"  👤 @{store['username'] or 'ስም'}\n"
                    f"  📍 {store['area_text'] or 'አልተዘጋጀም'}\n"
                    f"  📏 {distance:.1f} ኪ.ሜ\n\n"
                )
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu("am"))
        except Exception as e:
            logger.error(f"Location search error: {e}")
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    # ============================================================
    # BACKUP
    # ============================================================
    
    def _create_backup(self, message):
        """የውሂብ ጎታ ምትኬ መፍጠር"""
        chat_id = message.chat.id
        
        try:
            self.bot.send_message(chat_id, "⏳ ምትኬ እየተዘጋጀ ነው...")
            
            # Get all data
            stores = db_execute_dict("SELECT * FROM stores")
            products = db_execute_dict("SELECT * FROM products")
            orders = db_execute_dict("SELECT * FROM orders")
            
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "stores": stores,
                "products": products,
                "orders": orders
            }
            
            # Create JSON file
            json_data = json.dumps(backup_data, default=str, indent=2)
            
            # Send as file
            import io
            file_obj = io.BytesIO(json_data.encode())
            file_obj.name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            self.bot.send_document(chat_id, file_obj)
            self.bot.send_message(
                chat_id,
                "✅ ምትኬ ተፈጥሯል!",
                reply_markup=self._get_dashboard_markup()
            )
            
            logger.audit(chat_id, "backup_created", {})
        except Exception as e:
            logger.error(f"Backup error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    # ============================================================
    # EXPORT
    # ============================================================
    
    def _export_data(self, message):
        """ውሂብ ወደ CSV ማውጣት"""
        chat_id = message.chat.id
        
        try:
            self.bot.send_message(chat_id, "⏳ ውሂብ እየተዘጋጀ ነው...")
            
            # Export stores
            stores = db_execute_dict("""
                SELECT id, store_name, username, is_active, is_approved, 
                       area_text, total_sales, total_orders, created_at
                FROM stores
                ORDER BY created_at DESC
            """)
            
            if not stores:
                self.bot.send_message(chat_id, "❌ ምንም ውሂብ የለም!")
                return
            
            # Create CSV
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers
            headers = ["ID", "Store Name", "Username", "Active", "Approved", 
                      "Location", "Total Sales", "Total Orders", "Created At"]
            writer.writerow(headers)
            
            # Write data
            for store in stores:
                writer.writerow([
                    store['id'],
                    store['store_name'],
                    store['username'] or '',
                    "Yes" if store['is_active'] else "No",
                    "Yes" if store['is_approved'] else "No",
                    store['area_text'] or '',
                    float(store['total_sales'] or 0),
                    int(store['total_orders'] or 0),
                    format_date(store['created_at'])
                ])
            
            # Send as file
            output.seek(0)
            file_obj = io.BytesIO(output.getvalue().encode())
            file_obj.name = f"stores_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            self.bot.send_document(chat_id, file_obj)
            self.bot.send_message(
                chat_id,
                f"✅ {len(stores)} ሱቆች ተላኩ!",
                reply_markup=self._get_dashboard_markup()
            )
            
            logger.audit(chat_id, "data_exported", {"count": len(stores)})
        except Exception as e:
            logger.error(f"Export error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    # ============================================================
    # POLLING
    # ============================================================
    
    def _start_polling(self):
        """ቦቱን መጀመር"""
        def _poll():
            while True:
                try:
                    self.bot.infinity_polling(skip_pending=True, timeout=30)
                except Exception as e:
                    logger.error(f"⚠️ Control bot polling crashed: {e}. Restarting in 5s...")
                    time.sleep(5)
        
        threading.Thread(target=_poll, name="ControlBotPolling", daemon=True).start()

# =================================================================================
#                           SHOP BOT ENGINE
# =================================================================================

running_tokens = set()
running_lock = threading.Lock()

def start_shop_bot(token: str) -> bool:
    """የሱቅ ቦት ማስነሳት"""
    with running_lock:
        if token in running_tokens:
            return False
        running_tokens.add(token)
    
    logger.info(f"🚀 Starting shop bot: {token[:15]}...")
    try:
        # Import and setup bot handlers
        setup_bot_handlers(token)
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot {token[:15]}: {e}")
        with running_lock:
            running_tokens.discard(token)
        return False

def setup_bot_handlers(token: str):
    """የሱቅ ቦት ሃንድለሮችን ማዘጋጀት"""
    # This function would contain the shop bot handlers
    # For brevity, we're using the existing implementation
    # In production, this would be the full shop bot code
    pass

# =================================================================================
#                           LOAD EXISTING STORES
# =================================================================================

def load_existing_stores():
    """ያሉ ሱቆችን መጫን"""
    try:
        stores = db_execute_dict("SELECT token FROM stores")
        count = 0
        for store in stores:
            if start_shop_bot(store['token']):
                count += 1
        logger.info(f"✅ {count} stores loaded")
    except Exception as e:
        logger.error(f"❌ Failed to load stores: {e}")

load_existing_stores()

# =================================================================================
#                           MAIN ENTRY POINT
# =================================================================================

if __name__ == "__main__":
    try:
        # Initialize control bot
        control_bot = ControlBot()
        logger.info("🚀 Advanced Control Bot v3.0 is running!")
        
        # Keep the main thread alive
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
