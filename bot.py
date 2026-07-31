import os
import threading
import hashlib
import secrets
import time
import math
import re
import logging
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from flask import Flask, jsonify
import telebot
from telebot import types
import google.generativeai as genai
from datetime import datetime
from typing import Dict, Optional, List, Tuple, Any

# ============================================================
# LOGGING SETUP
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")
CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")
SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
PORT = int(os.environ.get("PORT", 8080))

if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL environment variable is required!")

# ============================================================
# FLASK APP
# ============================================================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "message": "Unified AI Shop Platform is Running!",
        "version": "2.0",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        put_db_connection(conn)
        return jsonify({
            "status": "healthy",
            "bots": len(running_tokens),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

def run_flask():
    app.run(host='0.0.0.0', port=PORT, debug=False)

threading.Thread(target=run_flask, daemon=True).start()
logger.info(f"✅ Flask server running on port {PORT}")

# ============================================================
# DATABASE CONNECTION POOL
# ============================================================
db_pool = None
db_pool_lock = threading.Lock()

def init_db_pool():
    global db_pool
    try:
        db_pool = SimpleConnectionPool(1, 20, dsn=DATABASE_URL)
        logger.info("✅ PostgreSQL Connection Pool initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize connection pool: {e}")
        raise

def get_db_connection():
    global db_pool
    if db_pool is None:
        with db_pool_lock:
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
        conn = db_pool.getconn()
        return conn

def put_db_connection(conn):
    if conn is None:
        return
    try:
        if db_pool is not None:
            db_pool.putconn(conn)
    except Exception as e:
        logger.warning(f"⚠️ Failed to return connection to pool: {e}")
        try:
            conn.close()
        except:
            pass

# ============================================================
# DATABASE INITIALIZATION
# ============================================================
def init_database():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Stores table
            cursor.execute('''CREATE TABLE IF NOT EXISTS stores (
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # Products table
            cursor.execute('''CREATE TABLE IF NOT EXISTS products (
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # Orders table
            cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                token TEXT NOT NULL,
                customer_id BIGINT NOT NULL,
                status_am TEXT DEFAULT 'በመጠባበቅ ላይ',
                status_en TEXT DEFAULT 'Pending',
                total_price REAL NOT NULL,
                delivery_fee REAL DEFAULT 0,
                status_stage INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # User languages table
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_langs (
                chat_id BIGINT PRIMARY KEY,
                lang TEXT DEFAULT 'am'
            )''')

            # Customer info table
            cursor.execute('''CREATE TABLE IF NOT EXISTS customer_info (
                chat_id BIGINT PRIMARY KEY,
                phone TEXT,
                lat REAL,
                lng REAL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # Categories table
            cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                token TEXT NOT NULL,
                name_am TEXT,
                name_en TEXT,
                icon TEXT
            )''')

            # Order items table
            cursor.execute('''CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                qty INTEGER NOT NULL,
                price REAL NOT NULL
            )''')

            # Indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_token ON products(token)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")
            
            conn.commit()
            logger.info("✅ Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    finally:
        put_db_connection(conn)

# ============================================================
# GEMINI AI INITIALIZATION
# ============================================================
ai_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("✅ Gemini AI initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini AI: {e}")
else:
    logger.warning("⚠️ GEMINI_API_KEY not set, AI features disabled.")

# ============================================================
# UTILITY FUNCTIONS
# ============================================================
def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def calculate_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def calculate_delivery_fee(distance_km: float) -> float:
    BASE_DELIVERY_FEE = 30
    PER_KM_RATE = 8
    return round(BASE_DELIVERY_FEE + (distance_km * PER_KM_RATE), 2)

def get_customer_info(chat_id: int) -> Optional[Dict]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT phone, lat, lng FROM customer_info WHERE chat_id=%s", (chat_id,))
            row = cursor.fetchone()
            if row:
                return {"phone": row[0], "lat": row[1], "lng": row[2]}
            return None
    finally:
        put_db_connection(conn)

def save_customer_phone(chat_id: int, phone: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''INSERT INTO customer_info (chat_id, phone) 
                              VALUES (%s, %s) ON CONFLICT (chat_id) 
                              DO UPDATE SET phone = EXCLUDED.phone, updated_at = CURRENT_TIMESTAMP''', 
                           (chat_id, phone))
            conn.commit()
    finally:
        put_db_connection(conn)

def save_customer_location(chat_id: int, lat: float, lng: float):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''INSERT INTO customer_info (chat_id, lat, lng) 
                              VALUES (%s, %s, %s) ON CONFLICT (chat_id) 
                              DO UPDATE SET lat = EXCLUDED.lat, lng = EXCLUDED.lng, updated_at = CURRENT_TIMESTAMP''', 
                           (chat_id, lat, lng))
            conn.commit()
    finally:
        put_db_connection(conn)

def get_store_info(token: str) -> Optional[Dict]:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''SELECT store_name, admin_id, username, telebirr, is_active, is_approved, 
                              password_hash, password_salt, cbebirr, area_text, shop_photo, shop_description,
                              shop_lat, shop_lng, bank_name, bank_account
                              FROM stores WHERE token=%s''', (token,))
            row = cursor.fetchone()
            if row:
                return {
                    "store_name": row[0],
                    "admin_id": row[1],
                    "username": row[2],
                    "telebirr": row[3],
                    "is_active": row[4],
                    "is_approved": row[5],
                    "pass_hash": row[6],
                    "salt": row[7],
                    "cbebirr": row[8],
                    "area_text": row[9],
                    "shop_photo": row[10],
                    "shop_description": row[11],
                    "shop_lat": row[12],
                    "shop_lng": row[13],
                    "bank_name": row[14],
                    "bank_account": row[15]
                }
            return None
    finally:
        put_db_connection(conn)

def get_user_lang(chat_id: int) -> str:
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT lang FROM user_langs WHERE chat_id=%s", (chat_id,))
            row = cursor.fetchone()
            return row[0] if row else "am"
    finally:
        put_db_connection(conn)

def save_user_lang(chat_id: int, lang: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''INSERT INTO user_langs (chat_id, lang) VALUES (%s, %s)
                              ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang''', 
                           (chat_id, lang))
            conn.commit()
    finally:
        put_db_connection(conn)

# ============================================================
# LOCALIZATION
# ============================================================
STRINGS = {
    "am": {
        "welcome": "እንኳን ወደ AI የሽያጭ ረዳት ቦት በደህና መጡ! 👋\n\nእባክዎ ይምረጡ:",
        "shop": "🛍️ ምርቶችን እይ",
        "cart": "🛒 የእኔ ጋሪ",
        "track": "📦 ትዕዛዝ መከታተያ",
        "faq": "❓ መረጃ",
        "search": "🔍 ፍለጋ",
        "back": "🔙 ወደ ኋላ",
        "empty_cart": "🛒 ጋሪዎ በአሁኑ ሰዓት ባዶ ነው።",
        "added_to_cart": "✅ ወደ ጋሪ ተጨምሯል!",
        "total": "አጠቃላይ",
        "price": "ዋጋ",
        "checkout": "💳 ሂሳብ ማጠቃለያ",
        "clear_cart": "🗑️ ጋሪ አጽዳ",
        "enter_order_id": "🔢 እባክዎ የትዕዛዝ ቁጥርዎን ያስገቡ:",
        "order_not_found": "❌ የትዕዛዝ ቁጥሩ አልተገኘም።",
        "invalid_order_id": "❌ የተሳሳተ ቁጥር ገብቷል።",
        "payment_approved": "✅ ክፍያ ተረጋግጧል! 🎉\nትዕዛዝዎ እየተዘጋጀ ነው።",
        "payment_rejected": "❌ ክፍያ አልተረጋገጠም።\nእባክዎ ሱቁን ያነጋግሩ።",
        "receipt_prompt": "📸 እባክዎ የክፍያ ማረጋገጫ ፎቶ ይላኩ።",
        "faq_text": "ℹ️ **ስለ ሱቃችን**\n\n📍 አድራሻ: አዲስ አበባ\n📞 ስልክ: 0911223344\n⏰ የስራ ሰዓት: ሰኞ - ቅዳሜ (8:00 - 18:00)",
        "login_success": "✅ በስኬት ገብተዋል!",
        "login_failed": "❌ የተሳሳተ የይለፍ ቃል",
        "logout_success": "🔒 ከአስተዳደር ወጥተዋል።",
        "no_products": "🛍️ ምንም ምርት የለም።",
        "in_stock": "✅ ይገኛል",
        "out_of_stock": "❌ ተሟጧል",
        "order_stages": ["🟡 በመጠባበቅ ላይ", "✅ ተረጋግጧል", "🚚 በመንገድ ላይ", "📦 ደርሷል"],
        "share_contact": "📱 ስልክ አጋራ",
        "share_location": "📍 አካባቢ አጋራ",
        "choose_language": "🌐 ቋንቋ ይምረጡ / Select Language:"
    },
    "en": {
        "welcome": "Welcome to AI Shop Assistant Bot! 👋\n\nPlease choose:",
        "shop": "🛍️ Shop Products",
        "cart": "🛒 My Cart",
        "track": "📦 Track Order",
        "faq": "❓ FAQ",
        "search": "🔍 Search",
        "back": "🔙 Back",
        "empty_cart": "🛒 Your cart is empty.",
        "added_to_cart": "✅ Added to cart!",
        "total": "Total",
        "price": "Price",
        "checkout": "💳 Checkout",
        "clear_cart": "🗑️ Clear Cart",
        "enter_order_id": "🔢 Please enter your Order ID:",
        "order_not_found": "❌ Order ID not found.",
        "invalid_order_id": "❌ Invalid ID entered.",
        "payment_approved": "✅ Payment approved! 🎉\nYour order is being prepared.",
        "payment_rejected": "❌ Payment rejected.\nPlease contact the store.",
        "receipt_prompt": "📸 Please send payment confirmation photo.",
        "faq_text": "ℹ️ **About Our Store**\n\n📍 Location: Addis Ababa\n📞 Phone: 0911223344\n⏰ Hours: Mon - Sat (8:00 AM - 6:00 PM)",
        "login_success": "✅ Login successful!",
        "login_failed": "❌ Incorrect password.",
        "logout_success": "🔒 Logged out.",
        "no_products": "🛍️ No products available.",
        "in_stock": "✅ In Stock",
        "out_of_stock": "❌ Out of Stock",
        "order_stages": ["🟡 Pending", "✅ Confirmed", "🚚 On the way", "📦 Delivered"],
        "share_contact": "📱 Share Phone",
        "share_location": "📍 Share Location",
        "choose_language": "🌐 Choose Language:"
    }
}

# ============================================================
# GLOBAL STATE (Thread-safe)
# ============================================================
user_carts: Dict[tuple, Dict[int, int]] = {}
user_carts_lock = threading.Lock()

admin_sessions: Dict[tuple, float] = {}
admin_sessions_lock = threading.Lock()

admin_states: Dict[tuple, Dict] = {}
admin_states_lock = threading.Lock()

login_attempts: Dict[tuple, Dict] = {}
login_attempts_lock = threading.Lock()

running_tokens: set = set()
running_tokens_lock = threading.Lock()

# ============================================================
# ADMIN BUTTONS
# ============================================================
ADMIN_BTN = {
    "add_product": "➕ ምርት ጨምር",
    "my_products": "📋 ምርቶቼ",
    "orders": "📬 ትዕዛዞች",
    "payment": "💰 የክፍያ ቅንብር",
    "stats": "📊 ስታትስቲክስ",
    "profile": "🏪 የሱቅ መገለጫ",
    "changepass": "🔑 የይለፍ ቃል ቀይር",
    "logout": "🚪 ውጣ"
}

def get_main_menu(lang: str):
    ln = STRINGS[lang]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton(ln["shop"]),
        types.KeyboardButton(ln["cart"])
    )
    markup.add(
        types.KeyboardButton(ln["search"]),
        types.KeyboardButton(ln["track"])
    )
    markup.add(types.KeyboardButton(ln["faq"]))
    return markup

def get_admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton(ADMIN_BTN["add_product"]),
        types.KeyboardButton(ADMIN_BTN["my_products"])
    )
    markup.add(
        types.KeyboardButton(ADMIN_BTN["orders"]),
        types.KeyboardButton(ADMIN_BTN["payment"])
    )
    markup.add(
        types.KeyboardButton(ADMIN_BTN["stats"]),
        types.KeyboardButton(ADMIN_BTN["profile"])
    )
    markup.add(
        types.KeyboardButton(ADMIN_BTN["changepass"]),
        types.KeyboardButton(ADMIN_BTN["logout"])
    )
    return markup

def get_back_button(lang: str):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main"))
    return markup

# ============================================================
# SHOP BOT ENGINE
# ============================================================
def start_shop_bot(token: str) -> bool:
    with running_tokens_lock:
        if token in running_tokens:
            return False
        running_tokens.add(token)
    
    try:
        setup_bot_handlers(token)
        logger.info(f"✅ Shop bot started: {token[:15]}...")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot {token[:15]}: {e}")
        with running_tokens_lock:
            running_tokens.discard(token)
        return False

def setup_bot_handlers(token: str):
    bot = telebot.TeleBot(token, threaded=False)
    
    try:
        bot.remove_webhook()
    except Exception as e:
        logger.warning(f"⚠️ Webhook removal failed: {e}")
    
    # ============================================================
    # BOT HANDLERS
    # ============================================================
    
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        chat_id = message.chat.id
        store = get_store_info(token)
        
        if not store:
            bot.send_message(
                chat_id,
                "🏪 ይህ ቦት ገና አልተመዘገበም።\n\n"
                "📌 እባክዎ በ Control Bot ይመዝገቡ!\n"
                "📌 ለእርዳታ አድሚኑን ያነጋግሩ"
            )
            return
        
        if store.get("is_approved", 0) != 1:
            bot.send_message(
                chat_id,
                f"⏳ **ሰላም!**\n\n"
                f"ይህ ሱቅ **{store.get('store_name', '')}** ገና አልጸደቀም።\n"
                f"እባክዎ ለማጽደቅ ይጠብቁ።\n\n"
                f"📌 ሱቁ ከጸደቀ በኋላ ማሳወቂያ ይደርስዎታል።",
                parse_mode="Markdown"
            )
            return
        
        if not store.get("is_active", 1):
            bot.send_message(
                chat_id,
                "❌ ይህ ሱቅ ንቁ አይደለም።\n"
                "እባክዎ አድሚኑን ያነጋግሩ።"
            )
            return
        
        # Show language selection
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data=f"setlang_am_{token}"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data=f"setlang_en_{token}")
        )
        
        welcome_text = f"👋 **{store.get('store_name', '')}**\n\n{STRINGS['am']['welcome']}"
        bot.send_message(chat_id, welcome_text, reply_markup=markup, parse_mode="Markdown")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith(f"setlang_"))
    def handle_language_selection(call):
        try:
            _, lang, bot_token = call.data.split("_")
            if bot_token != token:
                bot.answer_callback_query(call.id, "❌ ስህተት!")
                return
            
            chat_id = call.message.chat.id
            save_user_lang(chat_id, lang)
            
            bot.delete_message(chat_id, call.message.message_id)
            bot.send_message(
                chat_id,
                STRINGS[lang]["welcome"],
                reply_markup=get_main_menu(lang)
            )
            bot.answer_callback_query(call.id)
        except Exception as e:
            logger.error(f"Language selection error: {e}")
            bot.answer_callback_query(call.id, "❌ ስህተት ተከስቷል!")
    
    @bot.message_handler(commands=['login'])
    def handle_login(message):
        chat_id = message.chat.id
        store = get_store_info(token)
        
        if not store:
            bot.reply_to(message, "❌ ሱቅ አልተገኘም!")
            return
        
        if store.get("is_approved", 0) != 1:
            bot.reply_to(message, "⏳ ሱቁ ገና አልጸደቀም!")
            return
        
        attempt_key = (token, chat_id)
        with login_attempts_lock:
            if attempt_key not in login_attempts:
                login_attempts[attempt_key] = {"count": 0, "lockout_until": 0}
            attempt = login_attempts[attempt_key]
        
        if time.time() < attempt["lockout_until"]:
            remaining = int(attempt["lockout_until"] - time.time())
            bot.reply_to(message, f"🔒 እገዳ ላይ ነዎት! ከ {remaining} ሰከንድ በኋላ ይሞክሩ።")
            return
        
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ አጠቃቀም: `/login [የይለፍ_ቃል]`")
            return
        
        input_pass = args[1]
        test_hash, _ = hash_password(input_pass, store["salt"])
        
        if test_hash == store["pass_hash"]:
            # Update admin_id
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET admin_id=%s WHERE token=%s", (chat_id, token))
                    conn.commit()
            finally:
                put_db_connection(conn)
            
            with admin_sessions_lock:
                admin_sessions[(token, chat_id)] = time.time() + 7200
            
            with login_attempts_lock:
                login_attempts[attempt_key] = {"count": 0, "lockout_until": 0}
            
            bot.reply_to(
                message,
                f"{STRINGS['am']['login_success']}\n\n"
                "🔑 የ 2 ሰዓት ሴሽን ተጀምሯል።",
                reply_markup=get_admin_menu()
            )
        else:
            with login_attempts_lock:
                attempt["count"] += 1
                if attempt["count"] >= 5:
                    attempt["lockout_until"] = time.time() + 900
                    bot.reply_to(message, "❌ 5 ጊዜ ተሳስተዋል። ለ15 ደቂቃ ታግደዋል።")
                else:
                    left = 5 - attempt["count"]
                    bot.reply_to(message, f"❌ {STRINGS['am']['login_failed']} ({left} ሙከራዎች ቀርተዋል)")
    
    @bot.message_handler(commands=['logout'])
    def handle_logout(message):
        chat_id = message.chat.id
        with admin_sessions_lock:
            admin_sessions.pop((token, chat_id), None)
        lang = get_user_lang(chat_id)
        bot.reply_to(message, STRINGS[lang]["logout_success"], reply_markup=get_main_menu(lang))
    
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["shop"])
    def handle_shop(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id, name_am, name_en, price, stock, desc_am, desc_en, image_url "
                    "FROM products WHERE token=%s AND stock > 0 ORDER BY id",
                    (token,)
                )
                rows = cursor.fetchall()
        finally:
            put_db_connection(conn)
        
        if not rows:
            bot.send_message(chat_id, STRINGS[lang]["no_products"], reply_markup=get_back_button(lang))
            return
        
        for row in rows:
            p_id, name_am, name_en, price, stock, desc_am, desc_en, image_url = row
            name = name_am if lang == "am" else name_en
            desc = desc_am if lang == "am" else desc_en
            
            text = f"📦 **{name}**\n"
            text += f"💰 {STRINGS[lang]['price']}: {price} ETB\n"
            text += f"📌 {STRINGS[lang]['in_stock']}\n"
            if desc:
                text += f"📝 {desc[:100]}..."
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🛒 ወደ ጋሪ ጨምር", callback_data=f"addtocart_{p_id}"),
                types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main")
            )
            
            try:
                if image_url:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                else:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Failed to send product: {e}")
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("addtocart_"))
    def handle_add_to_cart(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        p_id = int(call.data.split("_")[1])
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT stock FROM products WHERE id=%s AND token=%s", (p_id, token))
                row = cursor.fetchone()
                if not row:
                    bot.answer_callback_query(call.id, "❌ ምርት አልተገኘም")
                    return
                stock = row[0] or 0
        finally:
            put_db_connection(conn)
        
        cart_key = (token, chat_id)
        with user_carts_lock:
            if cart_key not in user_carts:
                user_carts[cart_key] = {}
            current_qty = user_carts[cart_key].get(p_id, 0)
            
            if current_qty + 1 > stock:
                bot.answer_callback_query(call.id, "❌ በቂ ክምችት የለም", show_alert=True)
                return
            
            user_carts[cart_key][p_id] = current_qty + 1
        
        bot.answer_callback_query(call.id, STRINGS[lang]["added_to_cart"])
    
    @bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
    def handle_back_to_main(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        bot.send_message(chat_id, "🔙 ወደ ዋና ሜኑ", reply_markup=get_main_menu(lang))
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["cart"])
    def handle_cart(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        cart_key = (token, chat_id)
        
        with user_carts_lock:
            cart = user_carts.get(cart_key, {})
            if not cart:
                bot.send_message(chat_id, STRINGS[lang]["empty_cart"], reply_markup=get_back_button(lang))
                return
            
            total = 0
            text = "🛒 **ጋሪ**\n\n"
            items_to_remove = []
            
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    for p_id, qty in list(cart.items()):
                        cursor.execute("SELECT name_am, name_en, price FROM products WHERE id=%s AND token=%s", (p_id, token))
                        row = cursor.fetchone()
                        if row:
                            name = row[0] if lang == "am" else row[1]
                            price = row[2]
                            subtotal = price * qty
                            total += subtotal
                            text += f"▪️ {name} x{qty} = {subtotal} ETB\n"
                        else:
                            items_to_remove.append(p_id)
                    
                    for p_id in items_to_remove:
                        del cart[p_id]
            finally:
                put_db_connection(conn)
            
            if not cart:
                bot.send_message(chat_id, STRINGS[lang]["empty_cart"], reply_markup=get_back_button(lang))
                return
            
            text += f"\n💵 **{STRINGS[lang]['total']}: {total} ETB**"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(STRINGS[lang]["checkout"], callback_data="checkout"),
                types.InlineKeyboardButton(STRINGS[lang]["clear_cart"], callback_data="clear_cart"),
                types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main")
            )
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    @bot.callback_query_handler(func=lambda call: call.data in ["checkout", "clear_cart"])
    def handle_cart_actions(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        cart_key = (token, chat_id)
        
        if call.data == "clear_cart":
            with user_carts_lock:
                user_carts.pop(cart_key, None)
            bot.edit_message_text("🗑️ ጋሪ ጸድቷል", chat_id, call.message.message_id)
            bot.answer_callback_query(call.id)
            return
        
        # Checkout
        with user_carts_lock:
            cart = user_carts.get(cart_key, {})
            if not cart:
                bot.answer_callback_query(call.id, "❌ ጋሪ ባዶ ነው!")
                return
        
        # Check if customer has phone and location
        cust_info = get_customer_info(chat_id)
        has_phone = cust_info and cust_info.get("phone")
        has_location = cust_info and cust_info.get("lat") and cust_info.get("lng")
        
        if has_phone and has_location:
            process_checkout(chat_id, lang, call)
        else:
            # Request missing info
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            if not has_phone:
                markup.add(types.KeyboardButton(STRINGS[lang]["share_contact"], request_contact=True))
            if not has_location:
                markup.add(types.KeyboardButton(STRINGS[lang]["share_location"], request_location=True))
            
            with admin_states_lock:
                admin_states[(token, chat_id)] = {"state": "pending_checkout", "data": {}}
            
            bot.send_message(
                chat_id,
                "🚚 ለማድረሻ እባክዎ መረጃዎን ያጋሩ 👇",
                reply_markup=markup
            )
            bot.answer_callback_query(call.id)
    
    def process_checkout(chat_id: int, lang: str, call=None):
        cart_key = (token, chat_id)
        
        with user_carts_lock:
            cart = user_carts.get(cart_key, {})
            if not cart:
                if call:
                    bot.answer_callback_query(call.id, "❌ ጋሪ ባዶ ነው!")
                return
        
        store = get_store_info(token)
        if not store:
            bot.send_message(chat_id, "❌ ሱቅ አልተገኘም")
            return
        
        cust_info = get_customer_info(chat_id)
        
        items_total = 0
        order_items = []
        conn = get_db_connection()
        
        try:
            with conn.cursor() as cursor:
                for p_id, qty in list(cart.items()):
                    cursor.execute("SELECT price, stock FROM products WHERE id=%s AND token=%s FOR UPDATE", (p_id, token))
                    row = cursor.fetchone()
                    if not row:
                        continue
                    
                    price, stock = row[0], row[1] or 0
                    buy_qty = min(qty, stock)
                    if buy_qty <= 0:
                        continue
                    
                    items_total += price * buy_qty
                    order_items.append((p_id, buy_qty, price))
                
                if not order_items:
                    conn.rollback()
                    bot.send_message(chat_id, "❌ ምርቶች አልቀሩም")
                    with user_carts_lock:
                        user_carts.pop(cart_key, None)
                    return
                
                delivery_fee = 0
                distance_note = ""
                
                if (store.get("shop_lat") and store.get("shop_lng") and 
                    cust_info and cust_info.get("lat") and cust_info.get("lng")):
                    dist_km = calculate_distance_km(
                        store["shop_lat"], store["shop_lng"],
                        cust_info["lat"], cust_info["lng"]
                    )
                    delivery_fee = calculate_delivery_fee(dist_km)
                    distance_note = f"📍 ርቀት: {dist_km:.1f} ኪ.ሜ\n🚚 ማድረሻ: {delivery_fee} ETB\n"
                
                grand_total = items_total + delivery_fee
                
                # Create order
                cursor.execute('''INSERT INTO orders (token, customer_id, status_am, status_en, total_price, delivery_fee, status_stage)
                                  VALUES (%s, %s, %s, %s, %s, %s, 0) RETURNING id''',
                               (token, chat_id, STRINGS['am']['order_stages'][0], 
                                STRINGS['en']['order_stages'][0], items_total, delivery_fee))
                order_id = cursor.fetchone()[0]
                
                # Add order items and update stock
                for p_id, buy_qty, price in order_items:
                    cursor.execute("INSERT INTO order_items (order_id, product_id, qty, price) VALUES (%s, %s, %s, %s)",
                                   (order_id, p_id, buy_qty, price))
                    cursor.execute("UPDATE products SET stock = stock - %s WHERE id=%s AND token=%s", 
                                   (buy_qty, p_id, token))
                
                conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Checkout error: {e}")
            bot.send_message(chat_id, "❌ ስህተት ተከስቷል! እባክዎ እንደገና ይሞክሩ።")
            return
        finally:
            put_db_connection(conn)
            with user_carts_lock:
                user_carts.pop(cart_key, None)
        
        # Prepare payment info
        pay_methods = ""
        if store.get("telebirr"):
            pay_methods += f"📱 ቴሌብር: `{store.get('telebirr')}`\n"
        if store.get("cbebirr"):
            pay_methods += f"🏦 CBE ብር: `{store.get('cbebirr')}`\n"
        if store.get("bank_name") and store.get("bank_account"):
            pay_methods += f"🏛️ {store.get('bank_name')}: `{store.get('bank_account')}`\n"
        
        pay_text = (
            f"🆔 **Order ID:** `{order_id}`\n\n"
            f"💵 ድምር: {items_total} ETB\n"
            f"{distance_note}"
            f"💰 **አጠቃላይ: {grand_total} ETB**\n\n"
            f"**የክፍያ መንገዶች:**\n{pay_methods}\n\n{STRINGS[lang]['receipt_prompt']}"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main"))
        
        if call:
            try:
                bot.edit_message_text(pay_text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, pay_text, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, pay_text, reply_markup=markup, parse_mode="Markdown")
        
        with admin_states_lock:
            admin_states[(token, chat_id)] = {"state": f"awaiting_receipt_{order_id}", "data": {}}
    
    @bot.message_handler(content_types=['contact'])
    def handle_contact(message):
        chat_id = message.chat.id
        
        if message.contact and message.contact.user_id == message.from_user.id:
            save_customer_phone(chat_id, message.contact.phone_number)
            bot.reply_to(message, "✅ ስልክ ተቀብለናል!")
            
            with admin_states_lock:
                state = admin_states.get((token, chat_id), {}).get("state")
            
            if state == "pending_checkout":
                cust_info = get_customer_info(chat_id)
                if cust_info and cust_info.get("lat") and cust_info.get("lng"):
                    lang = get_user_lang(chat_id)
                    process_checkout(chat_id, lang)
                else:
                    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                    markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
                    bot.send_message(chat_id, "📍 እባክዎ አካባቢ ያጋሩ", reply_markup=markup)
    
    @bot.message_handler(content_types=['location'])
    def handle_location(message):
        chat_id = message.chat.id
        lat, lng = message.location.latitude, message.location.longitude
        save_customer_location(chat_id, lat, lng)
        bot.reply_to(message, "✅ አካባቢ ተቀብለናል!")
        
        with admin_states_lock:
            state = admin_states.get((token, chat_id), {}).get("state")
        
        if state == "pending_checkout":
            cust_info = get_customer_info(chat_id)
            if cust_info and cust_info.get("phone"):
                lang = get_user_lang(chat_id)
                process_checkout(chat_id, lang)
            else:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton("📱 ስልክ አጋራ", request_contact=True))
                bot.send_message(chat_id, "📱 እባክዎ ስልክ ያጋሩ", reply_markup=markup)
    
    @bot.message_handler(content_types=['photo'])
    def handle_photo(message):
        chat_id = message.chat.id
        state_key = (token, chat_id)
        
        with admin_states_lock:
            state_info = admin_states.get(state_key, {"state": "", "data": {}})
            state = state_info["state"]
        
        if state.startswith("awaiting_receipt_"):
            order_id = int(state.split("_")[2])
            store = get_store_info(token)
            admin_id = store.get("admin_id") if store else None
            
            if admin_id:
                cust_info = get_customer_info(chat_id)
                phone = f"\n📞 {cust_info['phone']}" if cust_info and cust_info.get("phone") else ""
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                    types.InlineKeyboardButton("❌ አትቀበል", callback_data=f"rejectorder_{order_id}")
                )
                
                try:
                    bot.send_message(admin_id, f"🔔 **አዲስ ደረሰኝ #{order_id}!**{phone}", reply_markup=markup, parse_mode="Markdown")
                    if cust_info and cust_info.get("lat") and cust_info.get("lng"):
                        bot.send_location(admin_id, cust_info["lat"], cust_info["lng"])
                    bot.forward_message(admin_id, chat_id, message.message_id)
                    
                    conn = get_db_connection()
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("UPDATE orders SET status_am='ክፍያ ተልኳል', status_en='Payment sent' WHERE id=%s AND token=%s", (order_id, token))
                            conn.commit()
                    finally:
                        put_db_connection(conn)
                    
                    bot.reply_to(message, "✅ ደረሰኝ ተልኳል!")
                    with admin_states_lock:
                        admin_states[state_key] = {"state": "", "data": {}}
                except Exception as e:
                    logger.error(f"Failed to forward receipt: {e}")
                    bot.reply_to(message, "❌ ደረሰኝ መላክ አልተቻለም!")
            else:
                bot.reply_to(message, "❌ አድሚን አልተገኘም!")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("approveorder_") or call.data.startswith("rejectorder_"))
    def handle_order_action(call):
        chat_id = call.message.chat.id
        is_approved = call.data.startswith("approveorder_")
        order_id = int(call.data.split("_")[1])
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT customer_id FROM orders WHERE id=%s AND token=%s", (order_id, token))
                row = cursor.fetchone()
                if row:
                    cust_id = row[0]
                    if is_approved:
                        cursor.execute("UPDATE orders SET status_am=%s, status_en=%s, status_stage=1 WHERE id=%s",
                                       (STRINGS['am']['order_stages'][1], STRINGS['en']['order_stages'][1], order_id))
                        conn.commit()
                        lang = get_user_lang(cust_id)
                        bot.send_message(cust_id, STRINGS[lang]["payment_approved"])
                        bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ጸድቋል", chat_id, call.message.message_id)
                    else:
                        cursor.execute("UPDATE orders SET status_am='❌ ውድቅ', status_en='❌ Rejected', status_stage=-1 WHERE id=%s", (order_id,))
                        conn.commit()
                        lang = get_user_lang(cust_id)
                        bot.send_message(cust_id, STRINGS[lang]["payment_rejected"])
                        bot.edit_message_text(f"❌ ትዕዛዝ #{order_id} ውድቅ ተደርጓል", chat_id, call.message.message_id)
        finally:
            put_db_connection(conn)
        
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["track"])
    def handle_track(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        msg = bot.reply_to(message, STRINGS[lang]["enter_order_id"])
        bot.register_next_step_handler(msg, process_track_order)
    
    def process_track_order(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        try:
            order_id = int(message.text.strip())
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT status_am, status_en, total_price, created_at FROM orders WHERE id=%s AND token=%s", (order_id, token))
                    row = cursor.fetchone()
                    if row:
                        status = row[0] if lang == "am" else row[1]
                        price = row[2]
                        created = row[3]
                        text = f"📦 **ትዕዛዝ #{order_id}**\n"
                        text += f"📌 ሁኔታ: {status}\n"
                        text += f"💵 ድምር: {price} ETB\n"
                        text += f"📅 ቀን: {created.strftime('%Y-%m-%d %H:%M')}"
                        bot.reply_to(message, text, reply_markup=get_back_button(lang), parse_mode="Markdown")
                    else:
                        bot.reply_to(message, STRINGS[lang]["order_not_found"], reply_markup=get_back_button(lang))
            finally:
                put_db_connection(conn)
        except ValueError:
            bot.reply_to(message, STRINGS[lang]["invalid_order_id"], reply_markup=get_back_button(lang))
    
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["faq"])
    def handle_faq(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        store = get_store_info(token)
        
        text = STRINGS[lang]["faq_text"]
        if store:
            if store.get("shop_description"):
                text += f"\n\n📝 {store.get('shop_description')}"
            if store.get("area_text"):
                text += f"\n📍 {store.get('area_text')}"
            if store.get("username"):
                text += f"\n👤 @{store.get('username')}"
        
        bot.reply_to(message, text, reply_markup=get_back_button(lang), parse_mode="Markdown")
    
    @bot.message_handler(func=lambda m: m.text in ADMIN_BTN.values())
    def handle_admin_menu(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        # Check admin session
        with admin_sessions_lock:
            is_admin = (token, chat_id) in admin_sessions and time.time() < admin_sessions[(token, chat_id)]
        
        if not is_admin:
            bot.reply_to(message, "❌ ይህ መብት የሚፈቀደው በ `/login` ለገቡ አድሚኖች ብቻ ነው።")
            return
        
        text = message.text
        if text == ADMIN_BTN["add_product"]:
            bot.reply_to(message, "📝 የምርት መረጃ በዚህ ፎርማት ይላኩ:\n`[አማርኛ ስም],[እንግሊዝኛ ስም],[ዋጋ],[ብዛት],[አማርኛ መግለጫ],[እንግሊዝኛ መግለጫ]`", parse_mode="Markdown")
            with admin_states_lock:
                admin_states[(token, chat_id)] = {"state": "waiting_product_details", "data": {}}
        elif text == ADMIN_BTN["my_products"]:
            show_my_products(chat_id, bot, token, lang)
        elif text == ADMIN_BTN["orders"]:
            show_orders(chat_id, bot, token, lang)
        elif text == ADMIN_BTN["payment"]:
            show_payment_settings(chat_id, bot, token, lang)
        elif text == ADMIN_BTN["stats"]:
            show_stats(chat_id, bot, token, lang)
        elif text == ADMIN_BTN["profile"]:
            show_profile(chat_id, bot, token, lang)
        elif text == ADMIN_BTN["changepass"]:
            bot.reply_to(message, "🔑 አዲስ የይለፍ ቃል ይላኩ (ቢያንስ 6 ፊደል):")
            with admin_states_lock:
                admin_states[(token, chat_id)] = {"state": "waiting_new_password", "data": {}}
        elif text == ADMIN_BTN["logout"]:
            with admin_sessions_lock:
                admin_sessions.pop((token, chat_id), None)
            bot.reply_to(message, STRINGS[lang]["logout_success"], reply_markup=get_main_menu(lang))
    
    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "waiting_product_details")
    def handle_product_details(message):
        chat_id = message.chat.id
        state_key = (token, chat_id)
        
        try:
            parts = message.text.split(",")
            if len(parts) < 6:
                bot.reply_to(message, "❌ ሁሉንም 6 መረጃዎች ያስገቡ!")
                return
            
            product_data = {
                "name_am": parts[0].strip(),
                "name_en": parts[1].strip(),
                "price": float(parts[2].strip()),
                "stock": int(parts[3].strip()),
                "desc_am": parts[4].strip(),
                "desc_en": parts[5].strip()
            }
            
            with admin_states_lock:
                admin_states[state_key] = {"state": "waiting_product_photo", "data": product_data}
            
            bot.reply_to(message, "📸 የምርቱን ፎቶ ይላኩ (ወይም 'ስቀር' ይበሉ):")
        except Exception as e:
            logger.error(f"Product details error: {e}")
            bot.reply_to(message, "❌ የተሳሳተ ፎርማት!")
    
    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "waiting_product_photo")
    def handle_product_photo(message):
        chat_id = message.chat.id
        state_key = (token, chat_id)
        
        with admin_states_lock:
            state_info = admin_states.get(state_key, {"state": "", "data": {}})
            product_data = state_info.get("data", {})
        
        if not product_data:
            bot.reply_to(message, "❌ ስህተት!")
            return
        
        photo_id = None
        if message.photo:
            photo_id = message.photo[-1].file_id
        elif message.text and message.text.lower() in ["ስቀር", "none", "skip"]:
            photo_id = ""
        else:
            bot.reply_to(message, "📸 እባክዎ ፎቶ ይላኩ ወይም 'ስቀር' ይበሉ:")
            return
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO products (token, name_am, name_en, price, stock, desc_am, desc_en, image_url)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                               (token, product_data["name_am"], product_data["name_en"], 
                                product_data["price"], product_data["stock"], 
                                product_data["desc_am"], product_data["desc_en"], photo_id or ""))
                conn.commit()
        finally:
            put_db_connection(conn)
        
        bot.reply_to(message, f"🎉 ምርት '{product_data['name_am']}' ተጨምሯል!")
        with admin_states_lock:
            admin_states[state_key] = {"state": "", "data": {}}
    
    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "waiting_new_password")
    def handle_new_password(message):
        chat_id = message.chat.id
        new_pass = message.text.strip()
        
        if len(new_pass) < 6:
            bot.reply_to(message, "❌ ቢያንስ 6 ፊደል!")
            return
        
        h_pass, salt = hash_password(new_pass)
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET password_hash=%s, password_salt=%s WHERE token=%s", (h_pass, salt, token))
                conn.commit()
        finally:
            put_db_connection(conn)
        
        bot.reply_to(message, "✅ የይለፍ ቃል ተቀይሯል!")
        with admin_states_lock:
            admin_states[(token, chat_id)] = {"state": "", "data": {}}
    
    @bot.message_handler(func=lambda message: True)
    def handle_ai_chat(message):
        if ai_model is None:
            return
        
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        store = get_store_info(token)
        
        if not store or not store.get("is_active"):
            return
        
        bot.send_chat_action(chat_id, 'typing')
        
        try:
            context = f"እንደ {store.get('store_name', 'ሱቅ')} ረዳት ምላሽ ስጥ። በ{lang} ምላሽ ስጥ።"
            response = ai_model.generate_content(f"{context}\n\nተጠቃሚ: {message.text}")
            
            if response and response.text:
                bot.reply_to(message, response.text[:1000])
        except Exception as e:
            logger.error(f"AI error: {e}")
            bot.reply_to(message, "🤖 AI በአሁኑ ጊዜ አይገኝም። እባክዎ ቆይተው ይሞክሩ።")
    
    # ============================================================
    # ADMIN HELPER FUNCTIONS
    # ============================================================
    
    def show_my_products(chat_id, bot, token, lang):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name_am, price, stock FROM products WHERE token=%s ORDER BY id", (token,))
                rows = cursor.fetchall()
        finally:
            put_db_connection(conn)
        
        if not rows:
            bot.send_message(chat_id, STRINGS[lang]["no_products"], reply_markup=get_back_button(lang))
            return
        
        for p_id, name_am, price, stock in rows:
            text = f"📦 #{p_id} {name_am}\n💰 {price} ETB | 📦 {stock}"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✏️ አርትዕ", callback_data=f"editproduct_{p_id}"),
                types.InlineKeyboardButton("🗑️ ሰርዝ", callback_data=f"deleteproduct_{p_id}"),
                types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main")
            )
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    def show_orders(chat_id, bot, token, lang):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT id, customer_id, total_price, status_stage 
                                  FROM orders WHERE token=%s AND status_stage NOT IN (3, -1)
                                  ORDER BY id DESC LIMIT 15''', (token,))
                rows = cursor.fetchall()
        finally:
            put_db_connection(conn)
        
        if not rows:
            bot.send_message(chat_id, "📋 ምንም ትዕዛዝ የለም", reply_markup=get_back_button(lang))
            return
        
        for order_id, cust_id, total, stage in rows:
            stage = stage or 0
            status = STRINGS['am']['order_stages'][stage] if 0 <= stage < 4 else "🟡 በመጠባበቅ ላይ"
            text = f"🆔 #{order_id}\n💵 {total} ETB\n📌 {status}"
            
            markup = types.InlineKeyboardMarkup()
            if stage == 0:
                markup.add(
                    types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                    types.InlineKeyboardButton("❌ አትቀበል", callback_data=f"rejectorder_{order_id}")
                )
            elif stage == 1:
                markup.add(types.InlineKeyboardButton("🚚 በመንገድ ላይ", callback_data=f"advanceorder_{order_id}"))
            elif stage == 2:
                markup.add(types.InlineKeyboardButton("📦 ደርሷል", callback_data=f"advanceorder_{order_id}"))
            markup.add(types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main"))
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("advanceorder_"))
    def handle_advance_order(call):
        chat_id = call.message.chat.id
        order_id = int(call.data.split("_")[1])
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT customer_id, status_stage FROM orders WHERE id=%s AND token=%s", (order_id, token))
                row = cursor.fetchone()
                if row:
                    cust_id, stage = row
                    new_stage = min((stage or 0) + 1, 3)
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s, status_stage=%s WHERE id=%s",
                                   (STRINGS['am']['order_stages'][new_stage], 
                                    STRINGS['en']['order_stages'][new_stage], new_stage, order_id))
                    conn.commit()
                    lang = get_user_lang(cust_id)
                    status = STRINGS[lang]['order_stages'][new_stage]
                    bot.send_message(cust_id, f"📦 ትዕዛዝ #{order_id} ሁኔታ: {status}")
                    bot.edit_message_text(f"🔄 ትዕዛዝ #{order_id} → {STRINGS['am']['order_stages'][new_stage]}", 
                                         chat_id, call.message.message_id)
        finally:
            put_db_connection(conn)
        bot.answer_callback_query(call.id)
    
    def show_payment_settings(chat_id, bot, token, lang):
        store = get_store_info(token)
        if not store:
            bot.send_message(chat_id, "❌ ሱቅ አልተገኘም")
            return
        
        text = "💰 **የክፍያ ቅንብሮች**\n\n"
        text += f"📱 ቴሌብር: `{store.get('telebirr', 'አልተዘጋጀም')}`\n"
        text += f"🏦 CBE ብር: `{store.get('cbebirr', 'አልተዘጋጀም')}`\n"
        text += f"🏛️ ባንክ: `{store.get('bank_name', 'አልተዘጋጀም')}`\n"
        text += f"🔢 አካውንት: `{store.get('bank_account', 'አልተዘጋጀም')}`"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📱 ቴሌብር", callback_data="pay_telebirr"),
            types.InlineKeyboardButton("🏦 CBE", callback_data="pay_cbe"),
            types.InlineKeyboardButton("🏛️ ባንክ", callback_data="pay_bank"),
            types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main")
        )
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
    def handle_payment_update(call):
        chat_id = call.message.chat.id
        action = call.data.split("_")[1]
        
        if action == "telebirr":
            msg = bot.send_message(chat_id, "📱 የቴሌብር ቁጥር ያስገቡ:")
            bot.register_next_step_handler(msg, lambda m: update_payment(m, "telebirr", token, bot))
        elif action == "cbe":
            msg = bot.send_message(chat_id, "🏦 የCBE ብር ቁጥር ያስገቡ:")
            bot.register_next_step_handler(msg, lambda m: update_payment(m, "cbe", token, bot))
        elif action == "bank":
            bank_list = "\n".join([f"{i+1}. {b}" for i, b in enumerate([
                "አብይ ኢትዮጵያ ባንክ", "የኢትዮጵያ ልማት ባንክ", "የኢትዮጵያ ንግድ ባንክ",
                "የኢትዮጵያ የገበያ ባንክ", "የኢትዮጵያ የግብርና ባንክ", "የኢትዮጵያ የኢንዱስትሪ ባንክ",
                "የኢትዮጵያ የንግድ ባንክ", "ቴሌብር", "ሲቢኢ ብር"
            ])])
            msg = bot.send_message(chat_id, f"🏛️ ባንክ ይምረጡ:\n\n{bank_list}\n\nቁጥር ወይም ስም ያስገቡ:")
            bot.register_next_step_handler(msg, lambda m: update_bank(m, token, bot))
        bot.answer_callback_query(call.id)
    
    def update_payment(message, pay_type, token, bot):
        chat_id = message.chat.id
        value = message.text.strip()
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                field = "telebirr" if pay_type == "telebirr" else "cbebirr"
                cursor.execute(f"UPDATE stores SET {field}=%s WHERE token=%s", (value, token))
                conn.commit()
        finally:
            put_db_connection(conn)
        
        bot.reply_to(message, f"✅ {pay_type.capitalize()} `{value}` ተቀምጧል!")
    
    def update_bank(message, token, bot):
        chat_id = message.chat.id
        bank_input = message.text.strip()
        
        # Simple bank name lookup
        bank_names = [
            "አብይ ኢትዮጵያ ባንክ", "የኢትዮጵያ ልማት ባንክ", "የኢትዮጵያ ንግድ ባንክ",
            "የኢትዮጵያ የገበያ ባንክ", "የኢትዮጵያ የግብርና ባንክ", "የኢትዮጵያ የኢንዱስትሪ ባንክ",
            "የኢትዮጵያ የንግድ ባንክ", "ቴሌብር", "ሲቢኢ ብር"
        ]
        
        if bank_input.isdigit():
            idx = int(bank_input) - 1
            if 0 <= idx < len(bank_names):
                bank_name = bank_names[idx]
            else:
                bank_name = bank_input
        else:
            bank_name = bank_input
        
        with admin_states_lock:
            admin_states[(token, chat_id)] = {"state": "waiting_bank_account", "data": {"bank_name": bank_name}}
        
        bot.send_message(chat_id, f"🏛️ ባንክ: **{bank_name}**\n\nአካውንት ቁጥር ያስገቡ:")
    
    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "waiting_bank_account")
    def handle_bank_account(message):
        chat_id = message.chat.id
        account = message.text.strip()
        
        with admin_states_lock:
            bank_data = admin_states.get((token, chat_id), {}).get("data", {})
            bank_name = bank_data.get("bank_name", "")
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET bank_name=%s, bank_account=%s WHERE token=%s", 
                             (bank_name, account, token))
                conn.commit()
        finally:
            put_db_connection(conn)
        
        bot.reply_to(message, f"✅ ባንክ ተቀምጧል!\n🏛️ {bank_name}\n🔢 {account}")
        with admin_states_lock:
            admin_states[(token, chat_id)] = {"state": "", "data": {}}
    
    def show_profile(chat_id, bot, token, lang):
        store = get_store_info(token)
        if not store:
            bot.send_message(chat_id, "❌ ሱቅ አልተገኘም")
            return
        
        text = "🏪 **የሱቅ መገለጫ**\n\n"
        text += f"📛 {store.get('store_name', '')}\n"
        text += f"👤 @{store.get('username', '')}\n"
        text += f"📍 {store.get('area_text', 'አልተዘጋጀም')}\n"
        text += f"📝 {store.get('shop_description', 'አልተዘጋጀም')}\n"
        if store.get('shop_photo'):
            text += "📸 ፎቶ: ✅\n"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📍 አካባቢ", callback_data="profile_location"),
            types.InlineKeyboardButton("📸 ፎቶ", callback_data="profile_photo"),
            types.InlineKeyboardButton("📝 መግለጫ", callback_data="profile_desc"),
            types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main")
        )
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("profile_"))
    def handle_profile_update(call):
        chat_id = call.message.chat.id
        action = call.data.split("_")[1]
        
        if action == "location":
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
            bot.send_message(chat_id, "📍 አዲስ አካባቢ ያጋሩ:", reply_markup=markup)
            with admin_states_lock:
                admin_states[(token, chat_id)] = {"state": "waiting_shop_location", "data": {}}
        elif action == "photo":
            bot.send_message(chat_id, "📸 አዲስ ፎቶ ይላኩ:")
            with admin_states_lock:
                admin_states[(token, chat_id)] = {"state": "waiting_shop_photo", "data": {}}
        elif action == "desc":
            bot.send_message(chat_id, "📝 አዲስ መግለጫ ይላኩ:")
            with admin_states_lock:
                admin_states[(token, chat_id)] = {"state": "waiting_shop_desc", "data": {}}
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(content_types=['location'])
    def handle_shop_location(message):
        chat_id = message.chat.id
        state_key = (token, chat_id)
        
        with admin_states_lock:
            state = admin_states.get(state_key, {}).get("state", "")
        
        if state == "waiting_shop_location":
            lat, lng = message.location.latitude, message.location.longitude
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET shop_lat=%s, shop_lng=%s WHERE token=%s", (lat, lng, token))
                    conn.commit()
            finally:
                put_db_connection(conn)
            
            bot.reply_to(message, "✅ አካባቢ ተቀምጧል!")
            with admin_states_lock:
                admin_states[state_key] = {"state": "", "data": {}}
    
    @bot.message_handler(content_types=['photo'])
    def handle_shop_photo(message):
        chat_id = message.chat.id
        state_key = (token, chat_id)
        
        with admin_states_lock:
            state = admin_states.get(state_key, {}).get("state", "")
        
        if state == "waiting_shop_photo":
            photo_id = message.photo[-1].file_id
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET shop_photo=%s WHERE token=%s", (photo_id, token))
                    conn.commit()
            finally:
                put_db_connection(conn)
            
            bot.reply_to(message, "✅ ፎቶ ተቀምጧል!")
            with admin_states_lock:
                admin_states[state_key] = {"state": "", "data": {}}
    
    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "waiting_shop_desc")
    def handle_shop_desc(message):
        chat_id = message.chat.id
        desc = message.text.strip()
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET shop_description=%s WHERE token=%s", (desc, token))
                conn.commit()
        finally:
            put_db_connection(conn)
        
        bot.reply_to(message, "✅ መግለጫ ተቀምጧል!")
        with admin_states_lock:
            admin_states[(token, chat_id)] = {"state": "", "data": {}}
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("editproduct_"))
    def handle_edit_product(call):
        chat_id = call.message.chat.id
        p_id = int(call.data.split("_")[1])
        
        with admin_states_lock:
            admin_states[(token, chat_id)] = {"state": "waiting_edit_values", "data": {"product_id": p_id}}
        
        bot.send_message(chat_id, f"✏️ ምርት #{p_id} አዲስ ዋጋ,ብዛት በኮማ ይላኩ (ለም: 2800,15):")
        bot.answer_callback_query(call.id)
    
    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "waiting_edit_values")
    def handle_edit_values(message):
        chat_id = message.chat.id
        state_key = (token, chat_id)
        
        with admin_states_lock:
            state_info = admin_states.get(state_key, {"state": "", "data": {}})
            p_id = state_info.get("data", {}).get("product_id")
        
        if not p_id:
            bot.reply_to(message, "❌ ስህተት!")
            return
        
        try:
            parts = message.text.split(",")
            new_price = float(parts[0].strip())
            new_stock = int(parts[1].strip())
        except:
            bot.reply_to(message, "❌ የተሳሳተ ፎርማት!")
            return
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE products SET price=%s, stock=%s WHERE id=%s AND token=%s", 
                             (new_price, new_stock, p_id, token))
                conn.commit()
        finally:
            put_db_connection(conn)
        
        bot.reply_to(message, f"✅ ምርት #{p_id} ተስተካክሏል!")
        with admin_states_lock:
            admin_states[state_key] = {"state": "", "data": {}}
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("deleteproduct_"))
    def handle_delete_product(call):
        chat_id = call.message.chat.id
        p_id = call.data.split("_")[1]
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✔️ አረጋግጥ", callback_data=f"confirmdelete_{p_id}"),
            types.InlineKeyboardButton("↩️ ተመለስ", callback_data="back_to_main")
        )
        bot.send_message(chat_id, f"⚠️ ምርት #{p_id} ይሰረዝ?", reply_markup=markup)
        bot.answer_callback_query(call.id)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("confirmdelete_"))
    def handle_confirm_delete(call):
        chat_id = call.message.chat.id
        p_id = int(call.data.split("_")[1])
        
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM products WHERE id=%s AND token=%s", (p_id, token))
                conn.commit()
        finally:
            put_db_connection(conn)
        
        bot.edit_message_text(f"🗑️ ምርት #{p_id} ተሰርዟል", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)
    
    def show_stats(chat_id, bot, token, lang):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM products WHERE token=%s", (token,))
                product_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0) FROM orders WHERE token=%s AND status_stage >= 1", (token,))
                paid_count, revenue = cursor.fetchone()
                
                cursor.execute("SELECT COUNT(*) FROM orders WHERE token=%s", (token,))
                total_orders = cursor.fetchone()[0]
        finally:
            put_db_connection(conn)
        
        text = f"📊 **ስታትስቲክስ**\n\n"
        text += f"📦 ምርቶች: {product_count}\n"
        text += f"🧾 ትዕዛዞች: {total_orders}\n"
        text += f"✅ የተከፈሉ: {paid_count}\n"
        text += f"💰 ገቢ: {revenue:.2f} ETB"
        
        bot.send_message(chat_id, text, reply_markup=get_back_button(lang), parse_mode="Markdown")
    
    # ============================================================
    # START THE BOT
    # ============================================================
    def _run_bot():
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                logger.error(f"⚠️ Bot {token[:15]} polling crashed: {e}. Restarting in 5s...")
                time.sleep(5)
    
    threading.Thread(target=_run_bot, name=f"Bot_{token[:10]}", daemon=True).start()

# ============================================================
# LOAD EXISTING STORES
# ============================================================
def load_existing_stores():
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT token FROM stores WHERE is_approved = 1")
                rows = cursor.fetchall()
                for (token,) in rows:
                    start_shop_bot(token)
                logger.info(f"✅ Loaded {len(rows)} approved stores")
        finally:
            put_db_connection(conn)
    except Exception as e:
        logger.error(f"❌ Failed to load stores: {e}")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    # Initialize database
    init_database()
    
    # Load existing stores
    load_existing_stores()
    
    logger.info("🚀 All systems are running!")
    
    # Keep the main thread alive
    while True:
        time.sleep(3600)
