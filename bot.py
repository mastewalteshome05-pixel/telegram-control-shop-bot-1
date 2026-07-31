"""
================================================================================
                    🚀 ADVANCED CONTROL BOT v3.0 🚀
        የላቀ የሱቅ አስተዳደር ሲስተም - Super Admin Control Panel
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
from flask import Flask, jsonify

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
    
    # Security
    SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "7200"))
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION = int(os.environ.get("LOCKOUT_DURATION", "900"))
    
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

logger = logging.getLogger('ControlBot')
logger.setLevel(getattr(logging, Config.LOG_LEVEL))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)

try:
    file_handler = logging.FileHandler(Config.LOG_FILE)
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
except Exception:
    pass

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
        commission_rate REAL DEFAULT 0.05,
        rating REAL DEFAULT 0,
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
        rating REAL DEFAULT 0,
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
        commission REAL DEFAULT 0,
        status_stage INTEGER DEFAULT 0,
        payment_method TEXT,
        payment_status TEXT DEFAULT 'pending',
        tracking_number TEXT,
        delivered_at TIMESTAMP,
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
        lng REAL,
        address TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        name_am TEXT,
        name_en TEXT,
        icon TEXT,
        parent_id INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        action TEXT NOT NULL,
        details JSONB,
        ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_products_token ON products(token);
    CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token);
    CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
    CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
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

# =================================================================================
#                           LOCALIZATION
# =================================================================================

STRINGS = {
    "am": {
        "welcome": "👋 እንኳን ወደ ሱቅ አስተዳደር ሲስተም በደህና መጡ!",
        "help": "❓ እርዳታ",
        "back": "🔙 ወደ ኋላ",
        "loading": "⏳ እየተጫነ ነው...",
        "success": "✅ ተሳክቷል!",
        "error": "❌ ስህተት ተከስቷል",
        "not_found": "❌ አልተገኘም",
        "dashboard_title": "🎛 የአስተዳደር ፓነል",
        "total_stores": "🏪 ጠቅላላ ሱቆች",
        "pending_approval": "⏳ ያልጸደቁ",
        "active_stores": "🟢 ንቁ ሱቆች",
        "total_orders": "📦 ጠቅላላ ትዕዛዞች",
        "total_revenue": "💰 ጠቅላላ ገቢ",
        "active_users": "👥 ንቁ ተጠቃሚዎች",
        "register_title": "📝 አዲስ ሱቅ መዝግብ",
        "search_title": "🔍 ሱቆችን ፈልግ",
        "search_by_name": "📝 በስም ፈልግ",
        "search_by_location": "📍 በአካባቢ ፈልግ",
        "no_results": "🔍 ምንም አልተገኘም",
    },
    "en": {
        "welcome": "👋 Welcome to Store Management System!",
        "help": "❓ Help",
        "back": "🔙 Back",
        "loading": "⏳ Loading...",
        "success": "✅ Success!",
        "error": "❌ An error occurred",
        "not_found": "❌ Not found",
        "dashboard_title": "🎛 Admin Dashboard",
        "total_stores": "🏪 Total Stores",
        "pending_approval": "⏳ Pending Approval",
        "active_stores": "🟢 Active Stores",
        "total_orders": "📦 Total Orders",
        "total_revenue": "💰 Total Revenue",
        "active_users": "👥 Active Users",
        "register_title": "📝 Register New Store",
        "search_title": "🔍 Search Stores",
        "search_by_name": "📝 Search by Name",
        "search_by_location": "📍 Search by Location",
        "no_results": "🔍 No results found",
    }
}

def get_string(key: str, lang: str = "am") -> str:
    try:
        return STRINGS[lang].get(key, key)
    except KeyError:
        return STRINGS["am"].get(key, key)

def get_user_lang(chat_id: int) -> str:
    try:
        result = db_execute("SELECT lang FROM user_langs WHERE chat_id = %s", (chat_id,), fetch=True)
        if result:
            return result[0][0]
    except:
        pass
    return "am"

# =================================================================================
#                           FLASK WEB SERVER
# =================================================================================

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Control Bot</title></head>
    <body>
        <h1>🚀 Control Bot is Running!</h1>
        <p>Status: Online</p>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

def run_flask():
    app.run(host=Config.HOST, port=Config.PORT, debug=False)

threading.Thread(target=run_flask, daemon=True).start()
logger.info(f"✅ Flask server running on {Config.HOST}:{Config.PORT}")

# =================================================================================
#                           SHOP BOT ENGINE - FIXED
# =================================================================================

running_tokens = set()
running_lock = threading.Lock()

def setup_bot_handlers(token: str):
    """የሱቅ ቦት ሃንድለሮችን ማዘጋጀት"""
    try:
        bot = telebot.TeleBot(token)
        bot.remove_webhook()
        
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
                    f"⏳ ሱቅ {store.get('store_name', '')} ገና አልጸደቀም።"
                )
                return
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data=f"lang_am_{token}"),
                types.InlineKeyboardButton("English 🇬🇧", callback_data=f"lang_en_{token}")
            )
            bot.send_message(
                chat_id,
                f"🌐 Welcome to {store['store_name']}!\n\nቋንቋ ይምረጡ:",
                reply_markup=markup
            )
        
        @bot.callback_query_handler(func=lambda call: call.data.startswith(f"lang_"))
        def handle_lang(call):
            _, lang, bot_token = call.data.split("_")
            if bot_token != token:
                return
            
            chat_id = call.message.chat.id
            db_execute(
                "INSERT INTO user_langs (chat_id, lang) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang",
                (chat_id, lang)
            )
            
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
            bot.send_message(chat_id, "እንኳን ደህና መጡ!", reply_markup=markup)
        
        @bot.message_handler(func=lambda m: True)
        def handle_all(m):
            bot.reply_to(m, "🤖 እንዴት ልረዳዎት እችላለሁ?")
        
        def _poll():
            while True:
                try:
                    bot.infinity_polling(skip_pending=True, timeout=30)
                except Exception as e:
                    logger.error(f"Bot polling error: {e}")
                    time.sleep(5)
        
        threading.Thread(target=_poll, daemon=True).start()
        logger.info(f"✅ Shop bot started: {token[:15]}...")
        
    except Exception as e:
        logger.error(f"❌ Failed to setup bot {token[:15]}: {e}")
        raise

def get_store_info(token: str):
    try:
        result = db_execute_dict(
            "SELECT store_name, admin_id, username, is_active, is_approved FROM stores WHERE token = %s",
            (token,)
        )
        if result:
            return dict(result[0])
        return None
    except Exception as e:
        logger.error(f"Get store info error: {e}")
        return None

def start_shop_bot(token: str) -> bool:
    with running_lock:
        if token in running_tokens:
            return False
        running_tokens.add(token)
    
    try:
        setup_bot_handlers(token)
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot {token[:15]}: {e}")
        with running_lock:
            running_tokens.discard(token)
        return False

# =================================================================================
#                           CONTROL BOT MAIN CLASS
# =================================================================================

class ControlBot:
    def __init__(self):
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
            text = get_string("welcome", lang)
            markup = self._get_main_menu(lang)
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
            
            msg = self.bot.send_message(chat_id, "🔐 **የ Super Admin የይለፍ ቃል ያስገቡ:**", parse_mode="Markdown")
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
        
        @self.bot.message_handler(func=lambda m: m.text in ["📝 አዲስ ሱቅ መዝግብ", "📝 Register New Store"])
        def handle_register(message):
            self._start_registration(message)
        
        @self.bot.message_handler(func=lambda m: m.text in ["🏪 ሱቆቼ", "🏪 My Stores"])
        def handle_my_stores(message):
            self._show_my_stores(message)
        
        @self.bot.message_handler(func=lambda m: m.text in ["🔍 ሱቆችን ፈልግ", "🔍 Search Stores"])
        def handle_search(message):
            lang = get_user_lang(message.chat.id)
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton(get_string("search_by_name", lang), callback_data="search_name"),
                types.InlineKeyboardButton(get_string("search_by_location", lang), callback_data="search_location")
            )
            self.bot.send_message(message.chat.id, get_string("search_title", lang), reply_markup=markup)
        
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
    
    def _get_main_menu(self, lang: str) -> types.ReplyKeyboardMarkup:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton(get_string("register_title", lang)),
            types.KeyboardButton("🏪 ሱቆቼ")
        )
        markup.add(
            types.KeyboardButton("🔍 ሱቆችን ፈልግ"),
            types.KeyboardButton(get_string("help", lang))
        )
        return markup
    
    def _get_dashboard_markup(self) -> types.InlineKeyboardMarkup:
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
            
            self.bot.send_message(chat_id, "🔓 **እንኳን ወደ Super Admin ፓነል በደህና መጡ!**", parse_mode="Markdown")
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
                    self.bot.send_message(chat_id, f"❌ የተሳሳተ የይለፍ ቃል! {left} ሙከራዎች ቀርተውዎታል።")
    
    def _logout(self, chat_id: int):
        with self.sessions_lock:
            self.sessions.pop(chat_id, None)
        lang = get_user_lang(chat_id)
        self.bot.send_message(chat_id, "🔒 ከአስተዳደር ወጥተዋል።", reply_markup=self._get_main_menu(lang))
    
    def _show_dashboard(self, message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        try:
            # Get stats
            total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
            pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
            active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
            total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
            revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
            
            text = (
                f"🎛 **{get_string('dashboard_title', lang)}**\n\n"
                f"🏪 {get_string('total_stores', lang)}: **{total_stores}**\n"
                f"⏳ {get_string('pending_approval', lang)}: **{pending}**\n"
                f"🟢 {get_string('active_stores', lang)}: **{active}**\n"
                f"📦 {get_string('total_orders', lang)}: **{total_orders}**\n"
                f"💰 {get_string('total_revenue', lang)}: **{revenue:,.2f} ETB**\n\n"
                f"📌 ርምጫ ይምረጡ:"
            )
            
            self.bot.send_message(chat_id, text, reply_markup=self._get_dashboard_markup(), parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            self.bot.send_message(chat_id, f"❌ {get_string('error', lang)}: {e}")
    
    def _show_pending_stores(self, message):
        chat_id = message.chat.id
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, username, area_text, shop_description, created_at
                FROM stores WHERE is_approved = 0 AND is_active = 1 ORDER BY created_at DESC
            """)
            
            if not stores:
                self.bot.send_message(chat_id, "✅ ምንም ያልተጸደቁ ሱቆች የሉም!", reply_markup=self._get_dashboard_markup())
                return
            
            for store in stores:
                text = (
                    f"🏪 **{store['store_name']}**\n"
                    f"🆔 #{store['id']}\n"
                    f"👤 @{store['username'] or 'ስም'}\n"
                    f"📍 {store['area_text'] or 'አልተዘጋጀም'}\n"
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
            self.bot.send_message(chat_id, f"❌ {get_string('error')}: {e}")
    
    def _show_all_stores(self, message):
        chat_id = message.chat.id
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, username, is_active, is_approved, created_at
                FROM stores ORDER BY created_at DESC LIMIT 20
            """)
            
            if not stores:
                self.bot.send_message(chat_id, "📜 ምንም ሱቅ የለም!", reply_markup=self._get_dashboard_markup())
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
                types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back")
            )
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"All stores error: {e}")
            self.bot.send_message(chat_id, f"❌ {get_string('error')}: {e}")
    
    def _show_stats(self, message):
        chat_id = message.chat.id
        
        try:
            total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
            pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
            active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
            total_products = db_execute("SELECT COUNT(*) FROM products", fetch=True)[0][0]
            total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
            revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
            active_users = db_execute("SELECT COUNT(DISTINCT customer_id) FROM orders", fetch=True)[0][0]
            
            text = (
                f"📊 **የሲስተም ስታቲስቲክስ**\n\n"
                f"🏪 **ሱቆች**\n"
                f"  • ጠቅላላ: {total_stores}\n"
                f"  • ንቁ: {active}\n"
                f"  • ያልተጸደቀ: {pending}\n\n"
                f"📦 **ምርቶች:** {total_products}\n\n"
                f"🧾 **ትዕዛዞች**\n"
                f"  • ጠቅላላ: {total_orders}\n"
                f"  • ንቁ ተጠቃሚዎች: {active_users}\n\n"
                f"💰 **ጠቅላላ ገቢ:** {revenue:,.2f} ETB"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Stats error: {e}")
            self.bot.send_message(chat_id, f"❌ {get_string('error')}: {e}")
    
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
    
    def _start_registration(self, message):
        chat_id = message.chat.id
        self._clear_reg_state(chat_id)
        self._set_reg_state(chat_id, "step", 1)
        self._set_reg_state(chat_id, "data", {})
        
        msg = self.bot.send_message(
            chat_id,
            "📝 **ደረጃ 1/5: የቦት ቶከን**\n\nከ @BotFather ያገኙትን ቶከን ያስገቡ:"
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
            "📝 **ደረጃ 2/5: የሱቅ ስም**\n\nየሱቅዎን ስም ያስገቡ:"
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
                INSERT INTO stores (token, store_name, admin_id, username, password_hash, password_salt,
                    telebirr, cbebirr, is_active, is_approved, shop_lat, shop_lng, area_text, shop_description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                reply_markup=self._get_main_menu("am"),
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
                FROM stores WHERE admin_id = %s ORDER BY created_at DESC
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
    
    def _search_by_name(self, message):
        chat_id = message.chat.id
        query = message.text.strip()
        
        if not query:
            self.bot.reply_to(message, "❌ እባክዎ የሱቅ ስም ያስገቡ!")
            return
        
        try:
            stores = db_execute_dict("""
                SELECT store_name, username, area_text, is_active
                FROM stores WHERE (store_name ILIKE %s OR username ILIKE %s) AND is_approved = 1
                LIMIT 10
            """, (f"%{query}%", f"%{query}%"))
            
            if not stores:
                self.bot.reply_to(message, "🔍 ምንም ሱቅ አልተገኘም", reply_markup=self._get_main_menu("am"))
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
                ORDER BY distance LIMIT 10
            """, (lat, lng, lat))
            
            if not stores:
                self.bot.reply_to(message, "🔍 በአቅራቢያ ምንም ሱቅ አልተገኘም", reply_markup=self._get_main_menu("am"))
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
    
    def _approve_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT token, store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ ሱቅ አልተገኘም!")
                return
            
            store = store[0]
            db_execute("UPDATE stores SET is_approved = 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (store_id,))
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
        logger.info("🚀 Advanced Control Bot v3.0 is running!")
        
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        # Don't exit, keep retrying
        while True:
            time.sleep(60)
