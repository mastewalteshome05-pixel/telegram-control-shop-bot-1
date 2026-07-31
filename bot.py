"""
================================================================================
                    🚀 CONTROL BOT v4.0 - RENDER OPTIMIZED
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
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from collections import defaultdict
from functools import wraps

# Third-party imports
import telebot
from telebot import types, apihelper
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request, make_response, send_file

# Optional imports with fallback
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Redis not available, using memory cache")

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("⚠️ Pandas not available")

try:
    from flask_cors import CORS
    CORS_AVAILABLE = True
except ImportError:
    CORS_AVAILABLE = False
    print("⚠️ Flask-CORS not available")

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False
    print("⚠️ Flask-Limiter not available")

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
    
    # Server
    PORT = int(os.environ.get("PORT", 8080))
    HOST = os.environ.get("HOST", "0.0.0.0")
    
    # Redis (optional)
    REDIS_URL = os.environ.get("REDIS_URL", "")
    
    # Security
    SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "7200"))
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION = int(os.environ.get("LOCKOUT_DURATION", "900"))
    
    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Validate required config
if not Config.DATABASE_URL:
    raise ValueError("❌ DATABASE_URL environment variable is required!")
if not Config.CONTROL_BOT_TOKEN:
    raise ValueError("❌ CONTROL_BOT_TOKEN environment variable is required!")

# =================================================================================
#                           LOGGING SYSTEM
# =================================================================================

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ControlBot')

# =================================================================================
#                           DATABASE LAYER
# =================================================================================

db_pool = None
db_pool_lock = threading.Lock()

def init_db_pool():
    global db_pool
    with db_pool_lock:
        if db_pool is None:
            try:
                db_pool = ThreadedConnectionPool(1, 20, dsn=Config.DATABASE_URL)
                logger.info("✅ Database connection pool initialized")
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
        except Exception as e:
            logger.warning(f"⚠️ Failed to return connection: {e}")
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
        logger.error(f"❌ Database query error: {e}")
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
        logger.error(f"❌ Database query error: {e}")
        raise
    finally:
        if conn:
            put_db_connection(conn)

def init_schema():
    schema = """
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
        total_sales REAL DEFAULT 0,
        total_orders INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        customer_id BIGINT NOT NULL,
        status_am TEXT DEFAULT 'በመጠባበቅ ላይ',
        status_en TEXT DEFAULT 'Pending',
        total_price REAL NOT NULL,
        delivery_fee REAL DEFAULT 0,
        status_stage INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        qty INTEGER NOT NULL,
        price REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS user_langs (
        chat_id BIGINT PRIMARY KEY,
        lang TEXT DEFAULT 'am'
    );

    CREATE TABLE IF NOT EXISTS customer_info (
        chat_id BIGINT PRIMARY KEY,
        phone TEXT,
        lat REAL,
        lng REAL
    );

    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        name_am TEXT,
        name_en TEXT,
        icon TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_products_token ON products(token);
    CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token);
    CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
    """
    
    try:
        db_execute(schema)
        logger.info("✅ Database schema initialized")
    except Exception as e:
        logger.error(f"❌ Schema initialization failed: {e}")
        raise

init_db_pool()
init_schema()

# =================================================================================
#                           CACHE SYSTEM (with fallback)
# =================================================================================

class Cache:
    _instance = None
    _lock = threading.Lock()
    _memory_cache = {}
    _memory_timestamps = {}
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self._redis_client = None
        self._cache_type = 'memory'
        
        if REDIS_AVAILABLE and Config.REDIS_URL:
            try:
                self._redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
                self._redis_client.ping()
                self._cache_type = 'redis'
                logger.info("✅ Redis cache initialized")
            except Exception as e:
                logger.warning(f"⚠️ Redis unavailable, using memory cache: {e}")
                self._cache_type = 'memory'
        else:
            logger.info("ℹ️ Using memory cache")
    
    def get(self, key: str, default: Any = None) -> Any:
        try:
            if self._cache_type == 'redis' and self._redis_client:
                value = self._redis_client.get(key)
                if value is not None:
                    try:
                        return json.loads(value)
                    except:
                        return value
                return default
            
            # Memory cache
            if key in self._memory_cache:
                if time.time() - self._memory_timestamps.get(key, 0) < 300:
                    return self._memory_cache[key]
            return default
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return default
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        try:
            if self._cache_type == 'redis' and self._redis_client:
                data = json.dumps(value) if not isinstance(value, str) else value
                self._redis_client.setex(key, ttl, data)
                return True
            
            self._memory_cache[key] = value
            self._memory_timestamps[key] = time.time()
            return True
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        try:
            if self._cache_type == 'redis' and self._redis_client:
                self._redis_client.delete(key)
            else:
                self._memory_cache.pop(key, None)
                self._memory_timestamps.pop(key, None)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False

cache = Cache()

# =================================================================================
#                           UTILITY FUNCTIONS
# =================================================================================

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def format_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")

def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def format_currency(amount: float) -> str:
    return f"{amount:,.2f} ETB"

def get_user_lang(chat_id: int) -> str:
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
    try:
        db_execute(
            "INSERT INTO user_langs (chat_id, lang) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang",
            (chat_id, lang)
        )
    except Exception as e:
        logger.error(f"Set user lang error: {e}")

# =================================================================================
#                           FLASK WEB SERVER
# =================================================================================

app = Flask(__name__)

# Setup CORS if available
if CORS_AVAILABLE:
    CORS(app)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Control Bot</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
            .container { background: white; border-radius: 20px; padding: 40px; max-width: 700px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
            h1 { color: #333; font-size: 2.5em; margin-bottom: 10px; }
            .subtitle { color: #666; margin-bottom: 30px; }
            .status { display: inline-block; padding: 8px 20px; border-radius: 30px; background: #4CAF50; color: white; font-weight: bold; margin-bottom: 20px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 30px 0; }
            .stat-item { background: #f8f8f8; padding: 20px; border-radius: 12px; text-align: center; }
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
            <h1>🚀 Control Bot</h1>
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
                </div>
            </div>
            
            <div class="info">
                <h3>📊 System Info</h3>
                <p><strong>Version:</strong> 4.0</p>
                <p><strong>Status:</strong> Running</p>
                <p><strong>Cache:</strong> <span id="cache-type">Loading...</span></p>
            </div>
            
            <div class="footer">
                © 2026 Control Bot v4.0 | Powered by AI
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
                    document.getElementById('total-orders').textContent = data.total_orders || 0;
                    document.getElementById('total-revenue').textContent = data.total_revenue ? data.total_revenue.toFixed(2) + ' ETB' : '0 ETB';
                    document.getElementById('cache-type').textContent = data.cache_type || 'memory';
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
        total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
        revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
        
        return jsonify({
            "total_stores": total_stores,
            "pending_approval": pending,
            "active_stores": active,
            "total_orders": total_orders,
            "total_revenue": float(revenue),
            "cache_type": cache._cache_type if hasattr(cache, '_cache_type') else 'memory'
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health')
def api_health():
    try:
        db_execute("SELECT 1", fetch=True)
        return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

def run_flask():
    app.run(host=Config.HOST, port=Config.PORT, debug=False)

threading.Thread(target=run_flask, daemon=True).start()
logger.info(f"✅ Web server running on {Config.HOST}:{Config.PORT}")

# =================================================================================
#                           SHOP BOT ENGINE
# =================================================================================

running_tokens = set()
running_lock = threading.Lock()

def start_shop_bot(token: str) -> bool:
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
            bot.send_message(
                chat_id,
                f"⏳ ሱቅ **{store.get('store_name', '')}** ገና አልጸደቀም።"
            )
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data=f"lang_am_{token}"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data=f"lang_en_{token}")
        )
        
        bot.send_message(
            chat_id,
            f"🌐 **{store.get('store_name', '')}**\n\nቋንቋ ይምረጡ / Select Language:",
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
        markup.add(types.KeyboardButton("❓ እርዳታ"))
        
        bot.send_message(chat_id, "እንኳን ደህና መጡ! 👋", reply_markup=markup)
    
    @bot.message_handler(func=lambda m: m.text == "🛍️ ምርቶች")
    def handle_products(message):
        chat_id = message.chat.id
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name_am, name_en, price, stock, image_url
                    FROM products
                    WHERE token = %s AND stock > 0
                    ORDER BY id
                    LIMIT 10
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
            text = f"📦 **{name_am}**\n💰 {price} ETB\n✅ ይገኛል"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🛒 ወደ ጋሪ ጨምር", callback_data=f"add_{p_id}"),
                types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="back")
            )
            
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    @bot.message_handler(func=lambda m: m.text == "🔍 ፍለጋ")
    def handle_search(message):
        chat_id = message.chat.id
        msg = bot.send_message(chat_id, "🔍 የምርት ስም ያስገቡ:")
        bot.register_next_step_handler(msg, search_product)
    
    def search_product(message):
        query = message.text.strip()
        chat_id = message.chat.id
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT name_am, name_en, price
                    FROM products
                    WHERE token = %s AND (name_am ILIKE %s OR name_en ILIKE %s)
                    LIMIT 10
                """, (token, f"%{query}%", f"%{query}%"))
                products = cur.fetchall()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not products:
            bot.send_message(chat_id, f"🔍 '{query}' አልተገኘም")
            return
        
        text = f"🔍 **'{query}' ውጤቶች:**\n\n"
        for p in products:
            text += f"📦 {p[0]} - {p[2]} ETB\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
    
    @bot.message_handler(func=lambda m: m.text == "📦 ትዕዛዝ")
    def handle_track(message):
        chat_id = message.chat.id
        msg = bot.send_message(chat_id, "🔢 የትዕዛዝ ቁጥር ያስገቡ:")
        bot.register_next_step_handler(msg, track_order)
    
    def track_order(message):
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
            text += f"💵 ድምር: {price} ETB\n"
            text += f"📅 ቀን: {format_date(created)}"
            
            bot.send_message(chat_id, text, parse_mode="Markdown")
        except ValueError:
            bot.send_message(message.chat.id, "❌ የተሳሳተ ቁጥር!")
    
    @bot.message_handler(func=lambda m: m.text == "❓ እርዳታ")
    def handle_help(message):
        text = """
        ❓ **እርዳታ**
        
        🛍️ ምርቶች - የሱቁን ምርቶች ይመልከቱ
        🛒 ጋሪ - የእርስዎን ጋሪ ይመልከቱ
        🔍 ፍለጋ - ምርቶችን ይፈልጉ
        📦 ትዕዛዝ - ትዕዛዝዎን ይከታተሉ
        """
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
    def handle_add(call):
        bot.answer_callback_query(call.id, "✅ ወደ ጋሪ ተጨምሯል!")
    
    @bot.callback_query_handler(func=lambda call: call.data == "back")
    def handle_back(call):
        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    
    @bot.message_handler(func=lambda m: m.text == "🛒 ጋሪ")
    def handle_cart(message):
        bot.send_message(message.chat.id, "🛒 ጋሪዎ ባዶ ነው")
    
    @bot.message_handler(func=lambda m: True)
    def handle_all(message):
        bot.reply_to(message, "🤖 እንዴት ልረዳዎት እችላለሁ?")
    
    def get_store_info(token):
        try:
            result = db_execute_dict(
                "SELECT store_name, admin_id, is_active, is_approved FROM stores WHERE token = %s",
                (token,)
            )
            if result:
                return dict(result[0])
            return None
        except Exception as e:
            logger.error(f"Get store info error: {e}")
            return None
    
    def _run_bot():
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                logger.error(f"Bot polling error: {e}")
                time.sleep(5)
    
    threading.Thread(target=_run_bot, daemon=True).start()

# =================================================================================
#                           CONTROL BOT
# =================================================================================

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
            lang = get_user_lang(chat_id)
            
            text = f"""
👋 እንኳን ወደ ሱቅ ቦት መመዝገቢያ በደህና መጡ!

📌 **አዲስ ሱቅ ለመመዝገብ:**
1️⃣ @BotFather ላይ `/newbot` በማድረግ ቦት ይፍጠሩ
2️⃣ Token ከተቀበሉ '📝 አዲስ ሱቅ መዝግብ' ይጫኑ
3️⃣ 5 ደረጃዎችን ይሙሉ

📌 **ሱቆችዎን ለማየት:** 🏪 ሱቆቼ

👑 **Super Admin ከሆኑ:** `/superadmin`
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
                "🔐 **እባክዎ የ Super Admin የይለፍ ቃል ያስገቡ፦**",
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
                self._show_all_stores(call.message)
            elif action == "stats":
                self.bot.answer_callback_query(call.id)
                self._show_stats(call.message)
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
        
        @self.bot.message_handler(func=lambda m: m.text == "📝 አዲስ ሱቅ መዝግብ")
        def handle_register(message):
            self._start_registration(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "🏪 ሱቆቼ")
        def handle_my_stores(message):
            self._show_my_stores(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "🔍 ሱቆችን ፈልግ")
        def handle_search(message):
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
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("search_"))
        def handle_search_callbacks(call):
            chat_id = call.message.chat.id
            
            if call.data == "search_name":
                msg = self.bot.send_message(chat_id, "📝 የሱቅ ስም ያስገቡ:")
                self.bot.register_next_step_handler(msg, self._search_by_name)
            elif call.data == "search_location":
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
                self.bot.send_message(chat_id, "📍 አካባቢ ያጋሩ:", reply_markup=markup)
        
        @self.bot.message_handler(content_types=['location'])
        def handle_location(message):
            self._search_by_location(message)
        
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
                "🔓 **እንኳን ወደ Super Admin ፓነል በደህና መጡ!**",
                parse_mode="Markdown"
            )
            self._show_dashboard(message)
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
        lang = get_user_lang(chat_id)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("📝 አዲስ ሱቅ መዝግብ"),
            types.KeyboardButton("🏪 ሱቆቼ")
        )
        markup.add(
            types.KeyboardButton("🔍 ሱቆችን ፈልግ"),
            types.KeyboardButton("❓ እርዳታ")
        )
        self.bot.send_message(chat_id, "🔒 ከአስተዳደር ወጥተዋል።", reply_markup=markup)
    
    def _show_dashboard(self, message):
        chat_id = message.chat.id
        
        try:
            total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
            pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
            active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
            total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
            revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
            
            text = f"""
🎛 **Super Admin Dashboard**

🏪 Total Stores: **{total_stores}**
⏳ Pending Approval: **{pending}**
🟢 Active Stores: **{active}**
📦 Total Orders: **{total_orders}**
💰 Total Revenue: **{format_currency(revenue)}**

📌 ርምጫ ይምረጡ:
"""
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("⏳ ያልጸደቁ", callback_data="dash_pending"),
                types.InlineKeyboardButton("🏢 ሁሉም", callback_data="dash_all")
            )
            markup.add(
                types.InlineKeyboardButton("📊 ስታቲስቲክስ", callback_data="dash_stats"),
                types.InlineKeyboardButton("📢 ማሰራጨት", callback_data="dash_broadcast")
            )
            markup.add(
                types.InlineKeyboardButton("🔄 አዘምን", callback_data="dash_refresh"),
                types.InlineKeyboardButton("🚪 ውጣ", callback_data="dash_logout")
            )
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
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
                self.bot.send_message(
                    chat_id,
                    "✅ ምንም ያልተጸደቁ ሱቆች የሉም!",
                    reply_markup=self._get_dashboard_markup()
                )
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
    
    def _show_all_stores(self, message):
        chat_id = message.chat.id
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, username, is_active, is_approved, created_at
                FROM stores ORDER BY created_at DESC LIMIT 20
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
                text += f"""
{status} {approved} **{store['store_name']}**
  🆔 #{store['id']} | 👤 @{store['username'] or 'ስም'}
  📅 {format_date(store['created_at'])}
"""
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"All stores error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _show_stats(self, message):
        chat_id = message.chat.id
        
        try:
            total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
            pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
            active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
            total_products = db_execute("SELECT COUNT(*) FROM products", fetch=True)[0][0]
            total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
            revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
            
            text = f"""
📊 **የሲስተም ስታቲስቲክስ**

🏪 **ሱቆች**
  • ጠቅላላ: {total_stores}
  • ንቁ: {active}
  • ያልተጸደቀ: {pending}

📦 **ምርቶች:** {total_products}

🧾 **ትዕዛዞች**
  • ጠቅላላ: {total_orders}

💰 **ጠቅላላ ገቢ:** {format_currency(revenue)}
"""
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Stats error: {e}")
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
            "📢 **ብሮድካስት መልእክት**\n\nመልእክት ለማን መላክ ይፈልጋሉ?",
            reply_markup=markup
        )
    
    def _broadcast_to_all(self, message, target):
        chat_id = message.chat.id
        msg_text = message.text
        
        try:
            if target == "owners":
                users = db_execute_dict("SELECT DISTINCT admin_id FROM stores WHERE admin_id > 0")
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
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _broadcast_to_user(self, message):
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
    
    def _send_single_message(self, message, user_id):
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
        except Exception as e:
            self.bot.reply_to(
                message,
                f"❌ መልእክት ለ {user_id} መላክ አልተቻለም!: {e}",
                reply_markup=self._get_dashboard_markup()
            )
    
    def _start_registration(self, message):
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
        chat_id = message.chat.id
        token = message.text.strip()
        
        try:
            test_bot = telebot.TeleBot(token)
            bot_info = test_bot.get_me()
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            self.bot.reply_to(message, "❌ ቶከን ልክ አይደለም!")
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
            "የሱቅዎን አካባቢ ያጋሩ ወይም የከተማ ስም ያስገቡ:",
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
            location_text = message.text.strip()
            if not location_text:
                self.bot.reply_to(message, "❌ እባክዎ አካባቢ ያስገቡ!")
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
    
    def _process_reg_description(self, message):
        chat_id = message.chat.id
        description = message.text.strip()
        
        if not description:
            self.bot.reply_to(message, "❌ እባክዎ የሱቅ መግለጫ ያስገቡ!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["shop_description"] = description
        data["username"] = data.get("bot_username", f"shop_{chat_id}")
        
        try:
            existing = db_execute_dict("SELECT 1 FROM stores WHERE token = %s", (data["token"],))
            if existing:
                self.bot.reply_to(message, "❌ ቶከን ቀድሞውኑ ተመዝግቧል!")
                return
            
            h_pass, salt = hash_password(data["password"])
            
            db_execute("""
                INSERT INTO stores (
                    token, store_name, admin_id, username,
                    password_hash, password_salt, telebirr, cbebirr,
                    is_active, is_approved, shop_lat, shop_lng,
                    area_text, shop_description
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["token"], data["store_name"], chat_id, data["username"],
                h_pass, salt, "", "", 1, 0,
                data.get("shop_lat"), data.get("shop_lng"),
                data.get("area_text", ""), data.get("shop_description", "")
            ))
            
            start_shop_bot(data["token"])
            
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
                f"🔑 **የይለፍ ቃል:** `{data['password']}`\n\n"
                f"⏳ **ሱቅዎ ለማጽደቅ በመጠባበቅ ላይ ነው!**",
                reply_markup=self._get_main_menu(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Registration error: {e}")
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _show_my_stores(self, message):
        chat_id = message.chat.id
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, is_active, is_approved, username, area_text
                FROM stores WHERE admin_id = %s
                ORDER BY created_at DESC
            """, (chat_id,))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "❌ ምንም ሱቅ አልተመዘገቡም።\n\n"
                    "📌 አዲስ ሱቅ ለመመዝገብ '📝 አዲስ ሱቅ መዝግብ' ይጫኑ",
                    reply_markup=self._get_main_menu()
                )
                return
            
            text = "🏪 **ሱቆችዎ:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                approved = "✅" if store['is_approved'] else "⏳"
                text += f"""
{status} {approved} **{store['store_name']}**
  👤 @{store['username'] or 'ስም'}
  📍 {store['area_text'] or 'አልተዘጋጀም'}
  🆔 #{store['id']}
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu())
        except Exception as e:
            logger.error(f"My stores error: {e}")
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _search_by_name(self, message):
        chat_id = message.chat.id
        query = message.text.strip()
        
        if not query:
            self.bot.reply_to(message, "❌ እባክዎ የሱቅ ስም ያስገቡ!")
            return
        
        try:
            stores = db_execute_dict("""
                SELECT store_name, username, area_text, is_active
                FROM stores
                WHERE (store_name ILIKE %s OR username ILIKE %s) AND is_approved = 1
                LIMIT 10
            """, (f"%{query}%", f"%{query}%"))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "🔍 ምንም ሱቅ አልተገኘም",
                    reply_markup=self._get_main_menu()
                )
                return
            
            text = "🔍 **የተገኙ ሱቆች:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                text += f"""
{status} **{store['store_name']}**
  👤 @{store['username'] or 'ስም'}
  📍 {store['area_text'] or 'አልተዘጋጀም'}
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu())
        except Exception as e:
            logger.error(f"Search error: {e}")
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _search_by_location(self, message):
        chat_id = message.chat.id
        
        if not message.location:
            self.bot.reply_to(message, "❌ እባክዎ አካባቢ ያጋሩ!")
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
                ORDER BY distance
                LIMIT 10
            """, (lat, lng, lat))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "🔍 በአቅራቢያ ምንም ሱቅ አልተገኘም",
                    reply_markup=self._get_main_menu()
                )
                return
            
            text = "📍 **በአቅራቢያ ያሉ ሱቆች:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                distance = store.get('distance', 0)
                text += f"""
{status} **{store['store_name']}**
  👤 @{store['username'] or 'ስም'}
  📍 {store['area_text'] or 'አልተዘጋጀም'}
  📏 {distance:.1f} ኪ.ሜ
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu())
        except Exception as e:
            logger.error(f"Location search error: {e}")
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _approve_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT token, store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ ሱቅ አልተገኘም!")
                return
            
            store = store[0]
            db_execute("UPDATE stores SET is_approved = 1 WHERE id = %s", (store_id,))
            start_shop_bot(store['token'])
            
            try:
                self.bot.send_message(
                    store['admin_id'],
                    f"🎉 **ሱቅዎ ተጸድቋል!**\n\n🏪 {store['store_name']}\n🔑 አሁን /login በማድረግ መግባት ይችላሉ"
                )
            except:
                pass
            
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
        try:
            store = db_execute_dict("SELECT store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ ሱቅ አልተገኘም!")
                return
            
            store = store[0]
            db_execute("DELETE FROM stores WHERE id = %s", (store_id,))
            
            try:
                self.bot.send_message(store['admin_id'], f"❌ ሱቅዎ **{store['store_name']}** ውድቅ ተደርጓል።")
            except:
                pass
            
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
            types.InlineKeyboardButton("🏢 ሁሉም", callback_data="dash_all")
        )
        markup.add(
            types.InlineKeyboardButton("📊 ስታቲስቲክስ", callback_data="dash_stats"),
            types.InlineKeyboardButton("📢 ማሰራጨት", callback_data="dash_broadcast")
        )
        markup.add(
            types.InlineKeyboardButton("🔄 አዘምን", callback_data="dash_refresh"),
            types.InlineKeyboardButton("🚪 ውጣ", callback_data="dash_logout")
        )
        return markup
    
    def _start_polling(self):
        def _poll():
            while True:
                try:
                    self.bot.infinity_polling(skip_pending=True, timeout=30)
                except Exception as e:
                    logger.error(f"Polling error: {e}")
                    time.sleep(5)
        
        threading.Thread(target=_poll, daemon=True).start()

# =================================================================================
#                           LOAD EXISTING STORES
# =================================================================================

def load_existing_stores():
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
        control_bot = ControlBot()
        logger.info("🚀 Control Bot v4.0 is running!")
        
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        while True:
            time.sleep(60)
