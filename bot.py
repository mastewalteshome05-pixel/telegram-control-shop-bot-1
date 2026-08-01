import os
import threading
import hashlib
import secrets
import time
import math
import telebot
from telebot import types, apihelper
import google.generativeai as genai
from flask import Flask
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

# ============================================================
# 1. FLASK KEEP-ALIVE SERVER
# ============================================================
app = Flask('')

@app.route('/')
def home():
    return "Unified AI Shop Platform (Shop Engine + Control Bot + Super Admin) is Running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask, daemon=True).start()

# ============================================================
# 2. GEMINI AI
# ============================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None
    print("⚠️ GEMINI_API_KEY not set - AI fallback disabled.")

# ============================================================
# 3. POSTGRESQL
# ============================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL environment variable is missing!")

db_pool_lock = threading.Lock()

try:
    db_pool = ThreadedConnectionPool(1, 20, dsn=DATABASE_URL)
    print("✅ PostgreSQL Connection Pool initialized.")
except Exception as e:
    print(f"❌ Failed to connect to PostgreSQL: {e}")
    raise e

def get_safe_connection():
    global db_pool
    last_err = None
    for _ in range(2):
        try:
            conn = db_pool.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            return conn
        except (psycopg2.InterfaceError, psycopg2.OperationalError, psycopg2.pool.PoolError) as e:
            last_err = e
            print("🔄 Re-initializing connection pool...")
            with db_pool_lock:
                try:
                    db_pool.closeall()
                except Exception:
                    pass
                db_pool = ThreadedConnectionPool(1, 20, dsn=DATABASE_URL)
    raise last_err

def put_conn(conn):
    if conn is None:
        return
    try:
        db_pool.putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass

def init_db():
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            # Main stores table
            cursor.execute('''CREATE TABLE IF NOT EXISTS stores (
                                id SERIAL,
                                token TEXT PRIMARY KEY,
                                store_name TEXT,
                                admin_id BIGINT,
                                password_hash TEXT,
                                password_salt TEXT,
                                telebirr TEXT,
                                is_active INTEGER DEFAULT 1,
                                shop_lat REAL,
                                shop_lng REAL,
                                area_text TEXT,
                                shop_photo TEXT,
                                shop_description TEXT,
                                cbebirr TEXT,
                                username TEXT,
                                owner_name TEXT,
                                owner_phone TEXT,
                                is_approved INTEGER DEFAULT 1)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS products (
                                id SERIAL PRIMARY KEY,
                                token TEXT,
                                name_am TEXT,
                                name_en TEXT,
                                price REAL,
                                stock INTEGER,
                                desc_am TEXT,
                                desc_en TEXT,
                                image_url TEXT)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                                id SERIAL PRIMARY KEY,
                                token TEXT,
                                customer_id BIGINT,
                                status_am TEXT,
                                status_en TEXT,
                                total_price REAL,
                                delivery_fee REAL DEFAULT 0,
                                status_stage INTEGER DEFAULT 0)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS order_items (
                                id SERIAL PRIMARY KEY,
                                order_id INTEGER,
                                product_id INTEGER,
                                qty INTEGER,
                                price REAL)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS user_langs (
                                chat_id BIGINT PRIMARY KEY,
                                lang TEXT)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS customer_info (
                                chat_id BIGINT PRIMARY KEY,
                                phone TEXT,
                                lat REAL,
                                lng REAL)''')

            # NEW: Favorites table
            cursor.execute('''CREATE TABLE IF NOT EXISTS favorites (
                                chat_id BIGINT,
                                product_id INTEGER,
                                token TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                PRIMARY KEY (chat_id, product_id))''')

            # NEW: Reviews table
            cursor.execute('''CREATE TABLE IF NOT EXISTS reviews (
                                id SERIAL PRIMARY KEY,
                                chat_id BIGINT,
                                token TEXT,
                                product_id INTEGER,
                                order_id INTEGER,
                                rating INTEGER,
                                comment TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

            conn.commit()
    finally:
        put_conn(conn)

init_db()

# ============================================================
# 4. HELPER FUNCTIONS
# ============================================================
def hash_password(password, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def calculate_distance_km(lat1, lng1, lat2, lng2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

BASE_DELIVERY_FEE = 30
PER_KM_RATE = 8

def calculate_delivery_fee(distance_km):
    return round(BASE_DELIVERY_FEE + (distance_km * PER_KM_RATE), 2)

ORDER_STAGES_AM = ["🟡 በመጠባበቅ ላይ", "✅ ተረጋግጧል", "🚚 በመንገድ ላይ", "📦 ደርሷል"]
ORDER_STAGES_EN = ["🟡 Pending", "✅ Confirmed", "🚚 On the way", "📦 Delivered"]

def get_customer_info(chat_id):
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT phone, lat, lng FROM customer_info WHERE chat_id=%s", (chat_id,))
            row = cursor.fetchone()
    finally:
        put_conn(conn)
    if row:
        return {"phone": row[0], "lat": row[1], "lng": row[2]}
    return None

def save_customer_phone(chat_id, phone):
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''INSERT INTO customer_info (chat_id, phone) VALUES (%s, %s)
                              ON CONFLICT (chat_id) DO UPDATE SET phone = EXCLUDED.phone''', (chat_id, phone))
            conn.commit()
    finally:
        put_conn(conn)

def save_customer_location(chat_id, lat, lng):
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''INSERT INTO customer_info (chat_id, lat, lng) VALUES (%s, %s, %s)
                              ON CONFLICT (chat_id) DO UPDATE SET lat = EXCLUDED.lat, lng = EXCLUDED.lng''', (chat_id, lat, lng))
            conn.commit()
    finally:
        put_conn(conn)

# ============================================================
# 5. LOCALIZATION
# ============================================================
STRINGS = {
    "am": {
        "welcome": "እንኳን ወደ AI የሽያጭ ረዳት ቦት በደህና መጡ! 👋",
        "shop": "🛍️ ምርቶችን እይ", "cart": "🛒 የእኔ ጋሪ", "track": "📦 ትዕዛዝ መከታተያ", "faq": "❓ መረጃ (FAQ)",
        "empty": "🛒 ጋሪዎ በአሁኑ ሰዓት ባዶ ነው።", "added": "ወደ ጋሪ ተጨምሯል! 🛒", "total": "አጠቃላይ ድምር",
        "price_label": "ዋጋ", "checkout_btn": "💳 ሂሳብ ማጠቃለያ", "clear_btn": "🗑️ ጋሪ አጽዳ",
        "enter_id": "🔢 እባክዎ የትዕዛዝ ቁጥርዎን (Order ID) ያስገቡ፦",
        "not_found": "❌ የትዕዛዝ ቁጥሩ አልተገኘም ወይም የዚህ ሱቅ አይደለም።", "invalid_id": "❌ የተሳሳተ ቁጥር ገብቷል።",
        "approved_msg": "🎉 ደስ የሚል ዜና! የትዕዛዝ ቁጥርዎ ክፍያ ተረጋግጦ ዕቃው እየመጣላችሁ ነው። 🛵",
        "rejected_msg": "❌ የትዕዛዝ ቁጥርዎ ክፍያ ማረጋገጫ ውድቅ ተደርጓል። እባክዎ ባለቤቱን ያነጋግሩ።",
        "receipt_prompt": "እባክዎ የከፈሉበትን የቴሌብር ደረሰኝ (Screenshot ፎቶ) እዚህ ላይ ይላኩ። 📸",
        "faq_text": "ℹ️ **ስለ ሱቃችን መረጃ**\n\n📍 አድራሻችን፦ አዲስ አበባ፣ ኢትዮጵያ\n📞 ስልክ፦ 0911223344\n⏱️ የስራ ሰዓት፦ ከሰኞ - ቅዳሜ (2:00 ሰዓት - 12:00 ሰዓት)\n\nማንኛውንም ጥያቄ እዚህ በመጻፍ AI ረዳታችንን መጠየቅ ይችላሉ!"
    },
    "en": {
        "welcome": "Welcome to AI Customer Service Bot! 👋",
        "shop": "🛍️ Shop Products", "cart": "🛒 My Cart", "track": "📦 Track Order", "faq": "❓ FAQ Info",
        "empty": "🛒 Your cart is currently empty.", "added": "Added to cart! 🛒", "total": "Total",
        "price_label": "Price", "checkout_btn": "💳 Checkout", "clear_btn": "🗑️ Clear Cart",
        "enter_id": "🔢 Please enter your Order ID:",
        "not_found": "❌ Order ID not found or invalid for this store.", "invalid_id": "❌ Invalid ID entered.",
        "approved_msg": "🎉 Great news! Your payment has been approved and your item is on the way! 🛵",
        "rejected_msg": "❌ Your payment could not be verified. Please contact the store owner.",
        "receipt_prompt": "Please send the Telebirr payment confirmation screenshot here. 📸",
        "faq_text": "ℹ️ **About Our Store**\n\n📍 Location: Addis Ababa, Ethiopia\n📞 Phone: +251911223344\n⏱️ Hours: Mon - Sat (8:00 AM - 6:00 PM)\n\nYou can ask our AI anything else by just typing your question!"
    }
}

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

user_carts = {}
active_sessions = {}
admin_states = {}
login_attempts = {}

def get_main_menu(lang):
    ln = STRINGS[lang]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton(ln["shop"]), types.KeyboardButton(ln["cart"]),
               types.KeyboardButton(ln["track"]), types.KeyboardButton(ln["faq"]))
    return markup

def get_admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton(ADMIN_BTN["add_product"]), types.KeyboardButton(ADMIN_BTN["my_products"]))
    markup.add(types.KeyboardButton(ADMIN_BTN["orders"]), types.KeyboardButton(ADMIN_BTN["payment"]))
    markup.add(types.KeyboardButton(ADMIN_BTN["stats"]), types.KeyboardButton(ADMIN_BTN["profile"]))
    markup.add(types.KeyboardButton(ADMIN_BTN["changepass"]), types.KeyboardButton(ADMIN_BTN["logout"]))
    return markup

# ============================================================
# 6. SHOP BOT ENGINE (per token)
# ============================================================
def setup_bot_handlers(token):
    bot = telebot.TeleBot(token)
    try:
        bot.remove_webhook()
    except Exception:
        pass

    lang_cache = {}

    def get_store_info():
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT store_name, admin_id, telebirr, is_active, password_hash, password_salt,
                                  cbebirr, area_text, shop_photo, shop_description, shop_lat, shop_lng,
                                  username, is_approved
                                  FROM stores WHERE token=%s''', (token,))
                row = cursor.fetchone()
        finally:
            put_conn(conn)
        if row:
            return {
                "store_name": row[0], "admin_id": row[1], "telebirr": row[2], "is_active": row[3],
                "pass_hash": row[4], "salt": row[5], "cbebirr": row[6], "area_text": row[7],
                "shop_photo": row[8], "shop_description": row[9], "shop_lat": row[10], "shop_lng": row[11],
                "username": row[12], "is_approved": row[13] if row[13] is not None else 1
            }
        return None

    def check_active_middleware(chat_id):
        store = get_store_info()
        if not store:
            bot.send_message(chat_id, "🏪 ይህ ሱቅ ገና አልተመዘገበም።")
            return False
        if not store["is_active"]:
            bot.send_message(chat_id, "❌ ይህ ሱቅ ንቁ አይደለም.")
            return False
        if store.get("is_approved", 1) != 1:
            bot.send_message(chat_id, "⏳ ይህ ሱቅ ገና አልጸደቀም። እባክዎ ለማጽደቅ ይጠብቁ።")
            return False
        return True

    def get_user_lang(chat_id):
        if chat_id in lang_cache:
            return lang_cache[chat_id]
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT lang FROM user_langs WHERE chat_id=%s", (chat_id,))
                row = cursor.fetchone()
        finally:
            put_conn(conn)
        lang = row[0] if row else "am"
        lang_cache[chat_id] = lang
        return lang

    def is_verified_admin(chat_id):
        store = get_store_info()
        session_key = (token, chat_id)
        if store and store["admin_id"] == chat_id:
            if session_key in active_sessions and time.time() < active_sessions[session_key]:
                return True
        return False

    # ---------- START ----------
    @bot.message_handler(commands=['start'])
    def choose_language(message):
        if not check_active_middleware(message.chat.id):
            return
        store = get_store_info()
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="shoplang_am"),
                   types.InlineKeyboardButton("English 🇬🇧", callback_data="shoplang_en"))
        bot.send_message(message.chat.id, f"🌐 Welcome to {store['store_name']}!\n\nቋንቋ ይምረጡ / Select Language:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("shoplang_"))
    def set_language(call):
        chat_id = call.message.chat.id
        if not check_active_middleware(chat_id):
            return
        lang_code = call.data.split("_")[1]
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO user_langs (chat_id, lang) VALUES (%s, %s)
                                  ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang''', (chat_id, lang_code))
                conn.commit()
        finally:
            put_conn(conn)
        lang_cache[chat_id] = lang_code
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(chat_id, STRINGS[lang_code]["welcome"], reply_markup=get_main_menu(lang_code))

    # ---------- ADMIN LOGIN ----------
    @bot.message_handler(commands=['login'])
    def login_store(message):
        chat_id = message.chat.id
        store = get_store_info()
        if not store:
            bot.reply_to(message, "❌ ይህ ሱቅ ገና አልተመዘገበም።")
            return
        if store.get("is_approved", 1) != 1:
            bot.reply_to(message, "⏳ ይህ ሱቅ ገና አልጸደቀም።")
            return

        attempt_key = (token, chat_id)
        attempt = login_attempts.setdefault(attempt_key, {"count": 0, "lockout_until": 0})
        if time.time() < attempt["lockout_until"]:
            remaining = int(attempt["lockout_until"] - time.time())
            bot.reply_to(message, f"🔒 እገዳ ላይ ነዎት! ከ {remaining} ሰከንድ በኋላ ይሞክሩ።")
            return

        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ አጠቃቀም፦ `/login [የይለፍ_ቃል]`")
            return

        input_pass = args[1]
        test_hash, _ = hash_password(input_pass, store["salt"])

        if test_hash == store["pass_hash"]:
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET admin_id=%s WHERE token=%s", (chat_id, token))
                    conn.commit()
            finally:
                put_conn(conn)
            active_sessions[(token, chat_id)] = time.time() + 7200
            login_attempts[attempt_key] = {"count": 0, "lockout_until": 0}
            bot.reply_to(message, "🔓 በስኬት ገብተዋል! የ 2 ሰዓት ሴሽን ተጀምሯል።", reply_markup=get_admin_menu())
        else:
            attempt["count"] += 1
            if attempt["count"] >= 5:
                attempt["lockout_until"] = time.time() + 900
                bot.reply_to(message, "❌ 5 ጊዜ ተሳስተዋል። ለ15 ደቂቃ ታግደዋል።")
            else:
                left = 5 - attempt["count"]
                bot.reply_to(message, f"❌ የተሳሳተ የይለፍ ቃል! {left} ሙከራዎች ቀርተውዎታል።")

    @bot.message_handler(commands=['logout'])
    def logout_store_cmd(message):
        session_key = (token, message.chat.id)
        if session_key in active_sessions:
            del active_sessions[session_key]
        lang = get_user_lang(message.chat.id)
        bot.send_message(message.chat.id, "🔒 ከአስተዳደር ወጥተዋል።", reply_markup=get_main_menu(lang))

    # ---------- ADMIN MENU ----------
    @bot.message_handler(func=lambda m: m.text in ADMIN_BTN.values())
    def admin_menu_router(message):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            bot.reply_to(message, "❌ ይህ መብት የሚፈቀደው በ `/login` ለገቡ አድሚኖች ብቻ ነው።")
            return

        text = message.text
        if text == ADMIN_BTN["add_product"]:
            bot.reply_to(message, "📝 የምርቱን መረጃ በዚህ ፎርማት ይጻፉ፦\n`[አማርኛ],[እንግሊዝኛ],[ዋጋ],[ብዛት],[አማርኛ መግለጫ],[እንግሊዝኛ መግለጫ]`")
            admin_states[(token, chat_id)] = {"state": "WAITING_PRODUCT_DETAILS", "data": {}}
        elif text == ADMIN_BTN["my_products"]:
            show_my_products(chat_id)
        elif text == ADMIN_BTN["orders"]:
            show_pending_orders(chat_id)
        elif text == ADMIN_BTN["payment"]:
            bot.reply_to(message, "💰 እባክዎ **የቴሌብር እና CBE Birr ቁጥርዎን** በኮማ ይላኩ፦")
            admin_states[(token, chat_id)] = {"state": "WAITING_PAYMENT_NUMBER", "data": {}}
        elif text == ADMIN_BTN["stats"]:
            show_stats(chat_id)
        elif text == ADMIN_BTN["profile"]:
            loc_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            loc_markup.add(types.KeyboardButton("📍 የሱቅ አካባቢ አጋራ", request_location=True))
            bot.send_message(chat_id, "🏪 **የሱቅ መገለጫ**\n\nደረጃ 1/4: አካባቢ ያጋሩ 👇", reply_markup=loc_markup)
            admin_states[(token, chat_id)] = {"state": "WAITING_SHOP_LOCATION", "data": {}}
        elif text == ADMIN_BTN["changepass"]:
            bot.reply_to(message, "🔑 አዲሱን የይለፍ ቃል ይላኩ (ቢያንስ 8 ፊደል):")
            admin_states[(token, chat_id)] = {"state": "WAITING_NEW_PASSWORD", "data": {}}
        elif text == ADMIN_BTN["logout"]:
            session_key = (token, chat_id)
            if session_key in active_sessions:
                del active_sessions[session_key]
            lang = get_user_lang(chat_id)
            bot.send_message(chat_id, "🔒 ወጥተዋል።", reply_markup=get_main_menu(lang))

    def show_my_products(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name_am, price, stock FROM products WHERE token=%s ORDER BY id", (token,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)
        if not rows:
            bot.send_message(chat_id, "📋 ምንም ምርት የለም።")
            return
        for p_id, name_am, price, stock in rows:
            text = f"📦 **#{p_id} {name_am}**\n💰 {price} ETB | 📦 {stock}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✏️ አርትዕ", callback_data=f"editproduct_{p_id}"),
                       types.InlineKeyboardButton("🗑️ ሰርዝ", callback_data=f"deleteproduct_{p_id}"))
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    def show_pending_orders(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT id, customer_id, total_price, status_stage FROM orders
                                  WHERE token=%s AND status_stage NOT IN (3, -1)
                                  ORDER BY id DESC LIMIT 15''', (token,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)
        if not rows:
            bot.send_message(chat_id, "📋 ያልተጠናቀቁ ትዕዛዞች የሉም።")
            return
        for order_id, cust_id, total, stage in rows:
            stage = stage or 0
            status_label = ORDER_STAGES_AM[stage] if 0 <= stage <= 3 else "🟡 Pending"
            text = f"🆔 **#{order_id}**\n💵 {total} ETB\n📌 {status_label}"
            markup = types.InlineKeyboardMarkup()
            if stage == 0:
                markup.add(types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                           types.InlineKeyboardButton("❌ አትቀበል", callback_data=f"rejectorder_{order_id}"))
            elif stage == 1:
                markup.add(types.InlineKeyboardButton("🚚 On the way", callback_data=f"advance_{order_id}"))
            elif stage == 2:
                markup.add(types.InlineKeyboardButton("✅ Delivered", callback_data=f"advance_{order_id}"))
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    def show_stats(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM products WHERE token=%s", (token,))
                product_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0) FROM orders WHERE token=%s AND status_stage >= 1", (token,))
                paid_count, revenue = cursor.fetchone()
                cursor.execute("SELECT COUNT(*) FROM orders WHERE token=%s", (token,))
                total_orders = cursor.fetchone()[0]
        finally:
            put_conn(conn)
        text = f"📊 **ስታትስቲክስ**\n\n📦 ምርት: {product_count}\n🧾 ትዕዛዝ: {total_orders}\n✅ የተከፈለ: {paid_count}\n💵 ገቢ: {revenue} ETB"
        bot.send_message(chat_id, text, parse_mode="Markdown")

    # ---------- ORDER MANAGEMENT ----------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("approveorder_"))
    def approve_order_btn(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም።")
            return
        order_id = int(call.data.split("_")[1])
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT customer_id FROM orders WHERE id=%s AND token=%s", (order_id, token))
                row = cursor.fetchone()
                if row:
                    cust_id = row[0]
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s, status_stage=1 WHERE id=%s",
                                   (ORDER_STAGES_AM[1], ORDER_STAGES_EN[1], order_id))
                    conn.commit()
                    cust_lang = get_user_lang(cust_id)
                    bot.send_message(cust_id, f"{STRINGS[cust_lang]['approved_msg']}")
        finally:
            put_conn(conn)
        bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ጸድቋል!", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "ጸድቋል!")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("rejectorder_"))
    def reject_order_btn(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም።")
            return
        order_id = int(call.data.split("_")[1])
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT customer_id FROM orders WHERE id=%s AND token=%s", (order_id, token))
                row = cursor.fetchone()
                if row:
                    cust_id = row[0]
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s, status_stage=-1 WHERE id=%s",
                                   ("❌ ውድቅ", "❌ Rejected", order_id))
                    conn.commit()
                    cust_lang = get_user_lang(cust_id)
                    bot.send_message(cust_id, STRINGS[cust_lang]["rejected_msg"])
        finally:
            put_conn(conn)
        bot.edit_message_text(f"❌ ትዕዛዝ #{order_id} ውድቅ ተደርጓል።", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "ውድቅ ተደርጓል")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("advance_"))
    def advance_order_btn(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም።")
            return
        order_id = int(call.data.split("_")[1])
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT customer_id, status_stage FROM orders WHERE id=%s AND token=%s", (order_id, token))
                row = cursor.fetchone()
                if row:
                    cust_id, stage = row
                    new_stage = min((stage or 0) + 1, 3)
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s, status_stage=%s WHERE id=%s",
                                   (ORDER_STAGES_AM[new_stage], ORDER_STAGES_EN[new_stage], new_stage, order_id))
                    conn.commit()
                    cust_lang = get_user_lang(cust_id)
                    label = ORDER_STAGES_AM[new_stage] if cust_lang == "am" else ORDER_STAGES_EN[new_stage]
                    bot.send_message(cust_id, f"📦 ትዕዛዝ #{order_id} ሁኔታ: {label}")
        finally:
            put_conn(conn)
        bot.edit_message_text(f"🔄 ትዕዛዝ #{order_id} → {ORDER_STAGES_AM[new_stage]}", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "ተቀይሯል!")

    # ---------- CUSTOMER SHOPPING ----------
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["shop"])
    def list_products(message):
        chat_id = message.chat.id
        if not check_active_middleware(chat_id):
            return
        lang = get_user_lang(chat_id)
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name_am, name_en, price, stock, desc_am, desc_en, image_url FROM products WHERE token=%s", (token,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)
        if not rows:
            bot.send_message(chat_id, "🛍️ ምንም ምርት የለም።" if lang == "am" else "🛍️ No products.")
            return
        for row in rows:
            p_id, name_am, name_en, price, stock, desc_am, desc_en, image_url = row
            name = name_am if lang == "am" else name_en
            desc = desc_am if lang == "am" else desc_en
            status = "✅ In Stock" if stock > 0 else "❌ Out of Stock"
            text = f"📦 **{name}**\n💰 {price} ETB\n📌 {status}\n📝 {desc}"
            markup = types.InlineKeyboardMarkup()
            if stock > 0:
                markup.add(types.InlineKeyboardButton("🛒 ጨምር", callback_data=f"shopadd_{p_id}"))
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("shopadd_"))
    def add_to_cart(call):
        chat_id = call.message.chat.id
        if not check_active_middleware(chat_id):
            return
        lang = get_user_lang(chat_id)
        p_id = int(call.data.split("_")[1])
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT stock FROM products WHERE id=%s AND token=%s", (p_id, token))
                prod = cursor.fetchone()
        finally:
            put_conn(conn)
        if not prod or (prod[0] or 0) <= 0:
            bot.answer_callback_query(call.id, "❌ ክምችት የለም")
            return
        cart_key = (token, chat_id)
        if cart_key not in user_carts:
            user_carts[cart_key] = {}
        user_carts[cart_key][p_id] = user_carts[cart_key].get(p_id, 0) + 1
        bot.answer_callback_query(call.id, STRINGS[lang]["added"])

    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["cart"])
    def show_cart(message):
        chat_id = message.chat.id
        if not check_active_middleware(chat_id):
            return
        lang = get_user_lang(chat_id)
        cart = user_carts.get((token, chat_id), {})
        if not cart:
            bot.send_message(chat_id, STRINGS[lang]["empty"])
            return
        total = 0
        text = "🛒 **ጋሪ**\n\n"
        conn = get_safe_connection()
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
                        text += f"▪️ {name} x {qty} = {subtotal} ETB\n"
                    else:
                        del cart[p_id]
        finally:
            put_conn(conn)
        text += f"\n💵 **{STRINGS[lang]['total']}: {total} ETB**"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(STRINGS[lang]["checkout_btn"], callback_data="shop_checkout"),
                   types.InlineKeyboardButton(STRINGS[lang]["clear_btn"], callback_data="shop_clear"))
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data in ["shop_checkout", "shop_clear"])
    def cart_actions(call):
        chat_id = call.message.chat.id
        if not check_active_middleware(chat_id):
            return
        lang = get_user_lang(chat_id)
        cart_key = (token, chat_id)
        if call.data == "shop_clear":
            user_carts[cart_key] = {}
            bot.edit_message_text("🛒 Cart cleared!", chat_id, call.message.message_id)
        elif call.data == "shop_checkout":
            cart = user_carts.get(cart_key, {})
            if not cart:
                return
            cust_info = get_customer_info(chat_id)
            has_phone = cust_info and cust_info.get("phone")
            has_location = cust_info and cust_info.get("lat") and cust_info.get("lng")
            if has_phone and has_location:
                finalize_checkout(chat_id, lang, call)
            else:
                gate_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                if not has_phone:
                    gate_markup.add(types.KeyboardButton("📱 ስልክ", request_contact=True))
                if not has_location:
                    gate_markup.add(types.KeyboardButton("📍 አካባቢ", request_location=True))
                bot.send_message(chat_id, "🚚 ስልክ እና አካባቢ ያጋሩ", reply_markup=gate_markup)
                admin_states[(token, chat_id)] = {"state": "PENDING_CHECKOUT", "data": {}}

    def finalize_checkout(chat_id, lang, edit_call=None):
        cart_key = (token, chat_id)
        cart = user_carts.get(cart_key, {})
        if not cart:
            return
        store = get_store_info()
        if not store:
            return
        cust_info = get_customer_info(chat_id)
        items_total = 0
        order_lines = []
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                for p_id, qty in list(cart.items()):
                    cursor.execute("SELECT price, stock FROM products WHERE id=%s AND token=%s FOR UPDATE", (p_id, token))
                    p_row = cursor.fetchone()
                    if not p_row:
                        continue
                    price, stock = p_row[0], (p_row[1] or 0)
                    buy_qty = min(qty, stock)
                    if buy_qty <= 0:
                        continue
                    items_total += price * buy_qty
                    order_lines.append((p_id, buy_qty, price))
                if not order_lines:
                    conn.rollback()
                    bot.send_message(chat_id, "❌ Out of stock")
                    user_carts[cart_key] = {}
                    return
                delivery_fee = 0
                distance_note = ""
                if store.get("shop_lat") and store.get("shop_lng") and cust_info and cust_info.get("lat") and cust_info.get("lng"):
                    dist_km = calculate_distance_km(store["shop_lat"], store["shop_lng"], cust_info["lat"], cust_info["lng"])
                    delivery_fee = calculate_delivery_fee(dist_km)
                    distance_note = f"📏 ርቀት: {dist_km:.1f} ኪ.ሜ\n🚚 ማድረሻ: {delivery_fee} ETB\n"
                grand_total = items_total + delivery_fee
                cursor.execute('''INSERT INTO orders (token, customer_id, status_am, status_en, total_price, delivery_fee, status_stage)
                                  VALUES (%s, %s, %s, %s, %s, %s, 0) RETURNING id''',
                               (token, chat_id, ORDER_STAGES_AM[0], ORDER_STAGES_EN[0], items_total, delivery_fee))
                order_id = cursor.fetchone()[0]
                for p_id, buy_qty, price in order_lines:
                    cursor.execute("INSERT INTO order_items (order_id, product_id, qty, price) VALUES (%s, %s, %s, %s)",
                                   (order_id, p_id, buy_qty, price))
                    cursor.execute("UPDATE products SET stock = stock - %s WHERE id=%s AND token=%s", (buy_qty, p_id, token))
                conn.commit()
        finally:
            put_conn(conn)
        user_carts[cart_key] = {}
        pay_methods = f"📱 **Telebirr:** `{store.get('telebirr')}`"
        if store.get("cbebirr"):
            pay_methods += f"\n🏦 **CBE Birr:** `{store.get('cbebirr')}`"
        pay_text = f"🆔 **Order ID:** `{order_id}`\n\n💵 {items_total} ETB\n{distance_note}💰 **አጠቃላይ: {grand_total} ETB**\n\n{pay_methods}\n\n{STRINGS[lang]['receipt_prompt']}"
        if edit_call:
            try:
                bot.edit_message_text(pay_text, chat_id, edit_call.message.message_id, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, pay_text, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, pay_text, parse_mode="Markdown")
        admin_states[(token, chat_id)] = {"state": f"AWAITING_RECEIPT_{order_id}", "data": {}}

    @bot.message_handler(content_types=['contact'])
    def handle_contact_share(message):
        chat_id = message.chat.id
        if message.contact and message.contact.user_id == message.from_user.id:
            save_customer_phone(chat_id, message.contact.phone_number)
        session_key = (token, chat_id)
        if admin_states.get(session_key, {}).get("state") == "PENDING_CHECKOUT":
            cust_info = get_customer_info(chat_id)
            if cust_info and cust_info.get("lat") and cust_info.get("lng"):
                lang = get_user_lang(chat_id)
                finalize_checkout(chat_id, lang)
            else:
                loc_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                loc_markup.add(types.KeyboardButton("📍 አካባቢ", request_location=True))
                bot.send_message(chat_id, "✅ ስልክ ተቀብለናል። አካባቢ ያጋሩ", reply_markup=loc_markup)

    @bot.message_handler(content_types=['location'])
    def handle_location_share(message):
        chat_id = message.chat.id
        session_key = (token, chat_id)
        state = admin_states.get(session_key, {}).get("state", "")
        if state == "WAITING_SHOP_LOCATION":
            if not is_verified_admin(chat_id):
                return
            lat, lng = message.location.latitude, message.location.longitude
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET shop_lat=%s, shop_lng=%s WHERE token=%s", (lat, lng, token))
                    conn.commit()
            finally:
                put_conn(conn)
            bot.send_message(chat_id, "✅ አካባቢ ተቀምጧል።\n\nደረጃ 2/4: የሱቅ አካባቢ ስም ያስገቡ:")
            admin_states[session_key] = {"state": "WAITING_SHOP_AREA", "data": {}}
            return
        save_customer_location(chat_id, message.location.latitude, message.location.longitude)
        if state == "PENDING_CHECKOUT":
            cust_info = get_customer_info(chat_id)
            if cust_info and cust_info.get("phone"):
                lang = get_user_lang(chat_id)
                finalize_checkout(chat_id, lang)
            else:
                phone_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                phone_markup.add(types.KeyboardButton("📱 ስልክ", request_contact=True))
                bot.send_message(chat_id, "✅ አካባቢ ተቀብለናል። ስልክ ያጋሩ", reply_markup=phone_markup)

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_SHOP_AREA")
    def process_shop_area(message):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            return
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET area_text=%s WHERE token=%s", (message.text.strip(), token))
                conn.commit()
        finally:
            put_conn(conn)
        bot.reply_to(message, "✅ ተቀምጧል።\n\nደረጃ 3/4: የሱቅ ፎቶ ይላኩ")
        admin_states[(token, chat_id)] = {"state": "WAITING_SHOP_PHOTO", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_SHOP_DESC")
    def process_shop_description(message):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            return
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET shop_description=%s WHERE token=%s", (message.text.strip(), token))
                conn.commit()
        finally:
            put_conn(conn)
        bot.reply_to(message, "🎉 የሱቅ መገለጫ ተጠናቋል!")
        admin_states[(token, chat_id)] = {"state": "", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_NEW_PASSWORD")
    def process_new_password(message):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            return
        new_pass = message.text.strip()
        if len(new_pass) < 8:
            bot.reply_to(message, "❌ ቢያንስ 8 ፊደል ያስፈልጋል")
            return
        h_pass, salt = hash_password(new_pass)
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET password_hash=%s, password_salt=%s WHERE token=%s", (h_pass, salt, token))
                conn.commit()
        finally:
            put_conn(conn)
        bot.reply_to(message, "✅ የይለፍ ቃል ተቀይሯል!")
        admin_states[(token, chat_id)] = {"state": "", "data": {}}

    @bot.message_handler(content_types=['photo'])
    def handle_incoming_photos(message):
        chat_id = message.chat.id
        if not check_active_middleware(chat_id):
            return
        session_key = (token, chat_id)
        state_dict = admin_states.get(session_key, {"state": "", "data": {}})
        state = state_dict["state"]
        store = get_store_info()
        if state.startswith("AWAITING_RECEIPT_"):
            order_id = int(state.split("_")[2])
            admin_id = store["admin_id"] if store else chat_id
            cust_info = get_customer_info(chat_id)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                       types.InlineKeyboardButton("❌ አትቀበል", callback_data=f"rejectorder_{order_id}"))
            phone_line = f"\n📞 ስልክ: `{cust_info['phone']}`" if cust_info and cust_info.get('phone') else ""
            bot.send_message(admin_id, f"🔔 **አዲስ ደረሰኝ ለትዕዛዝ #{order_id}!**{phone_line}", reply_markup=markup, parse_mode="Markdown")
            if cust_info and cust_info.get("lat") and cust_info.get("lng"):
                bot.send_location(admin_id, cust_info["lat"], cust_info["lng"])
            bot.forward_message(admin_id, chat_id, message.message_id)
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s WHERE id=%s AND token=%s",
                                   ("ክፍያ ተልኳል", "Payment sent", order_id, token))
                    conn.commit()
            finally:
                put_conn(conn)
            bot.reply_to(message, "✅ የክፍያ ማረጋገጫ ተልኳል።")
            admin_states[session_key] = {"state": "", "data": {}}
        elif state == "WAITING_SHOP_PHOTO":
            if not is_verified_admin(chat_id):
                return
            photo_id = message.photo[-1].file_id
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET shop_photo=%s WHERE token=%s", (photo_id, token))
                    conn.commit()
            finally:
                put_conn(conn)
            bot.reply_to(message, "✅ ተቀምጧል።\n\nደረጃ 4/4: የሱቅ መግለጫ ይጻፉ:")
            admin_states[session_key] = {"state": "WAITING_SHOP_DESC", "data": {}}
        elif state == "WAITING_PRODUCT_PHOTO":
            if not is_verified_admin(chat_id):
                return
            photo_id = message.photo[-1].file_id
            p_data = state_dict["data"]
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute('''INSERT INTO products (token, name_am, name_en, price, stock, desc_am, desc_en, image_url)
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                                   (token, p_data["name_am"], p_data["name_en"], p_data["price"], p_data["stock"], p_data["desc_am"], p_data["desc_en"], photo_id))
                    conn.commit()
            finally:
                put_conn(conn)
            bot.reply_to(message, f"🎉 ምርቱ '{p_data['name_am']}' ተጨምሯል!")
            admin_states[session_key] = {"state": "", "data": {}}

    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["faq"])
    def show_faq(message):
        if not check_active_middleware(message.chat.id):
            return
        lang = get_user_lang(message.chat.id)
        bot.reply_to(message, STRINGS[lang]["faq_text"], parse_mode="Markdown")

    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["track"])
    def track_order(message):
        if not check_active_middleware(message.chat.id):
            return
        lang = get_user_lang(message.chat.id)
        msg = bot.reply_to(message, STRINGS[lang]["enter_id"])
        bot.register_next_step_handler(msg, process_track)

    def process_track(message):
        if not check_active_middleware(message.chat.id):
            return
        lang = get_user_lang(message.chat.id)
        try:
            order_id = int(message.text)
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT status_am, status_en FROM orders WHERE id=%s AND token=%s", (order_id, token))
                    row = cursor.fetchone()
            finally:
                put_conn(conn)
            if row:
                status = row[0] if lang == "am" else row[1]
                bot.reply_to(message, f"📦 **Status:** {status}")
            else:
                bot.reply_to(message, STRINGS[lang]["not_found"])
        except ValueError:
            bot.reply_to(message, STRINGS[lang]["invalid_id"])

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_PRODUCT_DETAILS")
    def process_add_product_fields(message):
        session_key = (token, message.chat.id)
        if not is_verified_admin(message.chat.id):
            return
        try:
            parts = message.text.split(",")
            product_data = {"name_am": parts[0].strip(), "name_en": parts[1].strip(), "price": float(parts[2].strip()), "stock": int(parts[3].strip()), "desc_am": parts[4].strip(), "desc_en": parts[5].strip()}
            bot.reply_to(message, "📸 የምርቱን ፎቶ ይላኩ (ወይም 'none'):")
            admin_states[session_key] = {"state": "WAITING_PRODUCT_PHOTO", "data": product_data}
        except (IndexError, ValueError):
            bot.reply_to(message, "❌ ስህተት! በኮማ ይለዩ")
            admin_states[session_key] = {"state": "", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_PRODUCT_PHOTO" and m.text and m.text.lower() == 'none')
    def process_product_no_photo(message):
        session_key = (token, message.chat.id)
        if not is_verified_admin(message.chat.id):
            return
        p_data = admin_states[session_key]["data"]
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO products (token, name_am, name_en, price, stock, desc_am, desc_en, image_url)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                               (token, p_data["name_am"], p_data["name_en"], p_data["price"], p_data["stock"], p_data["desc_am"], p_data["desc_en"], ""))
                conn.commit()
        finally:
            put_conn(conn)
        bot.reply_to(message, f"🎉 ምርቱ '{p_data['name_am']}' ተጨምሯል!")
        admin_states[session_key] = {"state": "", "data": {}}

    @bot.message_handler(func=lambda message: True)
    def handle_global_ai(message):
        if not check_active_middleware(message.chat.id):
            return
        if ai_model is None:
            bot.reply_to(message, "🤖 AI አይገኝም።")
            return
        bot.send_chat_action(message.chat.id, 'typing')
        lang = get_user_lang(message.chat.id)
        store = get_store_info()
        store_name = store["store_name"] if store else "Our Shop"
        try:
            system_instruction = f"You are an AI assistant for '{store_name}'. Respond in {lang}. Keep it short."
            response = ai_model.generate_content(f"{system_instruction} {message.text}")
            bot.reply_to(message, response.text)
        except Exception as e:
            print(f"AI error: {e}")
            bot.reply_to(message, "❌ System busy.")

    def _run_bot():
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                print(f"⚠️ Bot {token[:10]} polling crashed: {e}. Restarting in 5s...")
                time.sleep(5)

    threading.Thread(target=_run_bot, name=f"Bot_{token[:10]}", daemon=True).start()

# ============================================================
# 7. LAUNCH EXISTING STORES
# ============================================================
running_tokens = set()
running_lock = threading.Lock()

def start_shop_bot(token):
    with running_lock:
        if token in running_tokens:
            return False
        running_tokens.add(token)
    print(f"🚀 Starting shop bot: {token[:10]}...")
    try:
        setup_bot_handlers(token)
    except Exception as e:
        print(f"❌ Failed to start bot {token[:10]}: {e}")
        with running_lock:
            running_tokens.discard(token)
        return False
    return True

def load_existing_stores_from_db():
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT token FROM stores")
            rows = cursor.fetchall()
    finally:
        put_conn(conn)
    for (tok,) in rows:
        start_shop_bot(tok)
    print(f"✅ {len(rows)} stores restored.")

load_existing_stores_from_db()

# ============================================================
# 8. CONTROL BOT (Super Admin + Registration + Marketplace)
# ============================================================
CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")

if CONTROL_BOT_TOKEN:
    control_bot = telebot.TeleBot(CONTROL_BOT_TOKEN)
    try:
        control_bot.remove_webhook()
    except Exception:
        pass

    SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
    SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
    SUPPORT_USERNAME = os.environ.get("SUPPORT_USERNAME", "@support")

    super_admin_sessions = {}
    super_login_attempts = {}

    def is_super_admin(chat_id):
        return chat_id in super_admin_sessions and time.time() < super_admin_sessions[chat_id]

    def get_marketplace_menu():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(types.KeyboardButton("🔍 የምርት ፍለጋ"), types.KeyboardButton("🏪 ሱቆችን አስስ"))
        markup.add(types.KeyboardButton("🛒 የእኔ ጋሪ"), types.KeyboardButton("📦 የእኔ ትዕዛዞች"))
        markup.add(types.KeyboardButton("⭐ የወደድኳቸው"), types.KeyboardButton("📝 ግምገማዎች"))
        markup.add(types.KeyboardButton("➕ ሱቅ መዝግብ"), types.KeyboardButton("👤 መገለጫዬ"))
        markup.add(types.KeyboardButton("📞 ድጋፍ"))
        return markup

    def get_super_admin_keyboard():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(types.KeyboardButton("📊 Analytics"), types.KeyboardButton("👥 Users"))
        markup.add(types.KeyboardButton("🏪 Stores"), types.KeyboardButton("📦 Orders"))
        markup.add(types.KeyboardButton("🛡 Verification"), types.KeyboardButton("⭐ Reviews"))
        markup.add(types.KeyboardButton("📢 Broadcast"), types.KeyboardButton("💰 Revenue"))
        markup.add(types.KeyboardButton("📈 Reports"), types.KeyboardButton("⚙️ Settings"))
        markup.add(types.KeyboardButton("🚪 Logout"))
        return markup

    # ---------- PUBLIC MARKETPLACE ----------
    @control_bot.message_handler(commands=['start'])
    def control_start(message):
        control_bot.send_message(message.chat.id, "👋 **Welcome to Marketplace!**\n\nSelect an option:", reply_markup=get_marketplace_menu(), parse_mode="Markdown")

    @control_bot.message_handler(commands=['help'])
    def control_help(message):
        control_bot.reply_to(message, "ℹ️ **Help**\n\n🔍 Search Products\n🏪 Browse Stores\n🛒 My Cart\n📦 My Orders\n⭐ Favorites\n📝 Reviews\n➕ Register Store\n👤 My Profile\n📞 Support")

    @control_bot.message_handler(func=lambda m: m.text == "🔍 የምርት ፍለጋ")
    def marketplace_search_prompt(message):
        msg = control_bot.send_message(message.chat.id, "🔍 Enter product name:")
        control_bot.register_next_step_handler(msg, marketplace_search_run)

    def marketplace_search_run(message):
        chat_id = message.chat.id
        query = message.text.strip()
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT p.id, p.name_am, p.price, p.stock, s.store_name, s.username
                                  FROM products p JOIN stores s ON p.token = s.token
                                  WHERE s.is_approved=1 AND s.is_active=1 AND p.stock > 0
                                  AND (p.name_am ILIKE %s OR p.name_en ILIKE %s)
                                  ORDER BY p.price ASC LIMIT 10''', (f"%{query}%", f"%{query}%"))
                results = cursor.fetchall()
        finally:
            put_conn(conn)
        if not results:
            control_bot.reply_to(message, "🔍 No results found.")
            return
        for p_id, name, price, stock, store_name, username in results:
            text = f"📦 **{name}**\n💰 {price} ETB\n🏪 {store_name}"
            markup = types.InlineKeyboardMarkup()
            if username:
                markup.add(types.InlineKeyboardButton("🛍️ Visit Store", url=f"https://t.me/{username}"))
            markup.add(types.InlineKeyboardButton("⭐ Add to Favorites", callback_data=f"fav_{p_id}"))
            control_bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @control_bot.callback_query_handler(func=lambda call: call.data.startswith("fav_"))
    def add_favorite(call):
        chat_id = call.message.chat.id
        p_id = int(call.data.split("_")[1])
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT token FROM products WHERE id=%s", (p_id,))
                row = cursor.fetchone()
                if row:
                    cursor.execute('''INSERT INTO favorites (chat_id, product_id, token) VALUES (%s, %s, %s)
                                      ON CONFLICT (chat_id, product_id) DO NOTHING''', (chat_id, p_id, row[0]))
                    conn.commit()
        finally:
            put_conn(conn)
        control_bot.answer_callback_query(call.id, "⭐ Added to favorites!")

    @control_bot.message_handler(func=lambda m: m.text == "🏪 ሱቆችን አስስ")
    def browse_stores(message):
        chat_id = message.chat.id
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT store_name, username, area_text, shop_description
                                  FROM stores WHERE is_approved=1 AND is_active=1 ORDER BY store_name LIMIT 20''')
                stores = cursor.fetchall()
        finally:
            put_conn(conn)
        if not stores:
            control_bot.reply_to(message, "🏪 No stores registered.")
            return
        for name, username, area, desc in stores:
            text = f"🏪 **{name}**\n📍 {area or 'Not specified'}\n📝 {(desc or '')[:100]}"
            markup = types.InlineKeyboardMarkup()
            if username:
                markup.add(types.InlineKeyboardButton("🛍️ Visit Store", url=f"https://t.me/{username}"))
            control_bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @control_bot.message_handler(func=lambda m: m.text == "🛒 የእኔ ጋሪ")
    def marketplace_my_cart(message):
        chat_id = message.chat.id
        found = False
        text = "🛒 **My Cart (All Stores)**\n\n"
        for (tok, cid), cart in list(user_carts.items()):
            if cid == chat_id and cart:
                found = True
                conn = get_safe_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT store_name, username FROM stores WHERE token=%s", (tok,))
                        srow = cursor.fetchone()
                except:
                    srow = None
                finally:
                    put_conn(conn)
                store_name = srow[0] if srow else "Store"
                username = srow[1] if srow else None
                item_count = sum(cart.values())
                text += f"🏪 **{store_name}** — {item_count} items"
                if username:
                    text += f" — https://t.me/{username}"
                text += "\n"
        if not found:
            control_bot.reply_to(message, "🛒 Your cart is empty.")
            return
        control_bot.reply_to(message, text, parse_mode="Markdown", disable_web_page_preview=True)

    @control_bot.message_handler(func=lambda m: m.text == "📦 የእኔ ትዕዛዞች")
    def marketplace_my_orders(message):
        chat_id = message.chat.id
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT o.id, o.total_price, o.delivery_fee, o.status_am, s.store_name
                                  FROM orders o JOIN stores s ON o.token = s.token
                                  WHERE o.customer_id=%s ORDER BY o.id DESC LIMIT 15''', (chat_id,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)
        if not rows:
            control_bot.reply_to(message, "📦 No orders.")
            return
        text = "📦 **My Orders**\n\n"
        for oid, total, fee, status, store_name in rows:
            text += f"🆔 #{oid} | 🏪 {store_name}\n💰 {total + (fee or 0)} ETB | 📌 {status}\n\n"
        control_bot.reply_to(message, text, parse_mode="Markdown")

    @control_bot.message_handler(func=lambda m: m.text == "⭐ የወደድኳቸው")
    def marketplace_favorites(message):
        chat_id = message.chat.id
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT p.name_am, p.price, s.store_name, s.username
                                  FROM favorites f JOIN products p ON f.product_id = p.id
                                  JOIN stores s ON f.token = s.token
                                  WHERE f.chat_id=%s ORDER BY f.created_at DESC LIMIT 15''', (chat_id,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)
        if not rows:
            control_bot.reply_to(message, "⭐ No favorites yet.")
            return
        for name, price, store_name, username in rows:
            text = f"⭐ **{name}**\n💰 {price} ETB\n🏪 {store_name}"
            markup = types.InlineKeyboardMarkup()
            if username:
                markup.add(types.InlineKeyboardButton("🛍️ Visit Store", url=f"https://t.me/{username}"))
            control_bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @control_bot.message_handler(func=lambda m: m.text == "📝 ግምገማዎች")
    def marketplace_reviews_prompt(message):
        chat_id = message.chat.id
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT o.id, s.store_name FROM orders o JOIN stores s ON o.token=s.token
                                  WHERE o.customer_id=%s AND o.status_stage=3
                                  AND o.id NOT IN (SELECT order_id FROM reviews WHERE chat_id=%s AND order_id IS NOT NULL)
                                  ORDER BY o.id DESC LIMIT 10''', (chat_id, chat_id))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)
        if not rows:
            control_bot.reply_to(message, "📝 No orders to review.")
            return
        markup = types.InlineKeyboardMarkup()
        for oid, store_name in rows:
            markup.add(types.InlineKeyboardButton(f"#{oid} - {store_name}", callback_data=f"reviewpick_{oid}"))
        control_bot.send_message(chat_id, "📝 Select order to review:", reply_markup=markup)

    @control_bot.callback_query_handler(func=lambda call: call.data.startswith("reviewpick_"))
    def review_pick_order(call):
        chat_id = call.message.chat.id
        order_id = int(call.data.split("_")[1])
        markup = types.InlineKeyboardMarkup(row_width=5)
        markup.add(*[types.InlineKeyboardButton("⭐" * i, callback_data=f"reviewrate_{order_id}_{i}") for i in range(1, 6)])
        control_bot.send_message(chat_id, "⭐ Select rating:", reply_markup=markup)
        control_bot.answer_callback_query(call.id)

    @control_bot.callback_query_handler(func=lambda call: call.data.startswith("reviewrate_"))
    def review_rate_order(call):
        chat_id = call.message.chat.id
        _, order_id, rating = call.data.split("_")
        msg = control_bot.send_message(chat_id, "📝 Write a comment (or type 'skip'):")
        control_bot.register_next_step_handler(msg, lambda m: save_review(m, int(order_id), int(rating)))
        control_bot.answer_callback_query(call.id)

    def save_review(message, order_id, rating):
        chat_id = message.chat.id
        comment = message.text.strip()
        if comment.lower() == "skip":
            comment = ""
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT token FROM orders WHERE id=%s", (order_id,))
                row = cursor.fetchone()
                tok = row[0] if row else None
                cursor.execute('''INSERT INTO reviews (chat_id, token, order_id, rating, comment)
                                  VALUES (%s, %s, %s, %s, %s)''', (chat_id, tok, order_id, rating, comment))
                conn.commit()
        finally:
            put_conn(conn)
        control_bot.reply_to(message, f"✅ Thank you! {'⭐' * rating}")

    @control_bot.message_handler(func=lambda m: m.text == "👤 መገለጫዬ")
    def marketplace_my_profile(message):
        chat_id = message.chat.id
        info = get_customer_info(chat_id)
        text = "👤 **Profile**\n\n"
        text += f"📱 Phone: {info['phone'] if info and info.get('phone') else 'Not set'}\n"
        text += f"📍 Location: {'Set ✅' if info and info.get('lat') else 'Not set'}\n"
        control_bot.reply_to(message, text, parse_mode="Markdown")

    @control_bot.message_handler(func=lambda m: m.text == "📞 ድጋፍ")
    def marketplace_support(message):
        control_bot.reply_to(message, f"📞 Contact: {SUPPORT_USERNAME}")

    # ---------- REGISTER STORE (Wizard) ----------
    reg_wizard_states = {}

    @control_bot.message_handler(func=lambda m: m.text == "➕ ሱቅ መዝግብ")
    def register_wizard_start(message):
        chat_id = message.chat.id
        reg_wizard_states[chat_id] = {"data": {}}
        msg = control_bot.send_message(chat_id, "🏪 **Step 1/7: Store Name**\n\nEnter store name:", parse_mode="Markdown")
        control_bot.register_next_step_handler(msg, reg_w_store_name)

    def reg_w_store_name(message):
        chat_id = message.chat.id
        reg_wizard_states[chat_id]["data"]["store_name"] = message.text.strip()
        msg = control_bot.send_message(chat_id, "👤 **Step 2/7: Owner Name**\n\nEnter your full name:", parse_mode="Markdown")
        control_bot.register_next_step_handler(msg, reg_w_owner_name)

    def reg_w_owner_name(message):
        chat_id = message.chat.id
        reg_wizard_states[chat_id]["data"]["owner_name"] = message.text.strip()
        msg = control_bot.send_message(chat_id, "📱 **Step 3/7: Phone Number**\n\nEnter your phone number:", parse_mode="Markdown")
        control_bot.register_next_step_handler(msg, reg_w_phone)

    def reg_w_phone(message):
        chat_id = message.chat.id
        phone = message.contact.phone_number if message.contact else message.text.strip()
        reg_wizard_states[chat_id]["data"]["owner_phone"] = phone
        msg = control_bot.send_message(chat_id, "📍 **Step 4/7: Location**\n\nEnter store location:", parse_mode="Markdown")
        control_bot.register_next_step_handler(msg, reg_w_location)

    def reg_w_location(message):
        chat_id = message.chat.id
        data = reg_wizard_states[chat_id]["data"]
        if message.location:
            data["shop_lat"] = message.location.latitude
            data["shop_lng"] = message.location.longitude
            data["area_text"] = ""
        else:
            data["area_text"] = message.text.strip()
        msg = control_bot.send_message(chat_id, "🖼 **Step 5/7: Store Logo**\n\nSend a photo (or type 'skip'):", parse_mode="Markdown")
        control_bot.register_next_step_handler(msg, reg_w_logo)

    def reg_w_logo(message):
        chat_id = message.chat.id
        data = reg_wizard_states[chat_id]["data"]
        data["shop_photo"] = message.photo[-1].file_id if message.photo else ""
        msg = control_bot.send_message(chat_id, "🤖 **Step 6/7: Bot Token**\n\nEnter your Bot Token from @BotFather:", parse_mode="Markdown")
        control_bot.register_next_step_handler(msg, reg_w_token)

    def reg_w_token(message):
        chat_id = message.chat.id
        tok = message.text.strip()
        try:
            test_bot = telebot.TeleBot(tok)
            bot_info = test_bot.get_me()
        except:
            control_bot.reply_to(message, "❌ Invalid token. Please start over.")
            reg_wizard_states.pop(chat_id, None)
            return
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM stores WHERE token=%s", (tok,))
                if cursor.fetchone():
                    control_bot.reply_to(message, "❌ Token already registered.")
                    reg_wizard_states.pop(chat_id, None)
                    return
        finally:
            put_conn(conn)
        reg_wizard_states[chat_id]["data"]["token"] = tok
        reg_wizard_states[chat_id]["data"]["bot_username"] = bot_info.username
        msg = control_bot.send_message(chat_id, f"✅ Token verified! (@{bot_info.username})\n\n📝 **Step 7/7: Description**\n\nEnter store description:", parse_mode="Markdown")
        control_bot.register_next_step_handler(msg, reg_w_description)

    def reg_w_description(message):
        chat_id = message.chat.id
        data = reg_wizard_states[chat_id]["data"]
        data["shop_description"] = message.text.strip()

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO stores
                                  (token, store_name, admin_id, username, owner_name, owner_phone,
                                   area_text, shop_lat, shop_lng, shop_photo, shop_description, is_approved)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)''',
                               (data["token"], data["store_name"], chat_id, data["bot_username"],
                                data["owner_name"], data["owner_phone"], data.get("area_text", ""),
                                data.get("shop_lat"), data.get("shop_lng"), data.get("shop_photo", ""),
                                data["shop_description"]))
                conn.commit()
        except Exception as e:
            control_bot.reply_to(message, f"❌ Error: {e}")
            reg_wizard_states.pop(chat_id, None)
            return
        finally:
            put_conn(conn)

        reg_wizard_states.pop(chat_id, None)
        control_bot.reply_to(message, "⏳ **Your application has been submitted.**\nWaiting for admin verification.", reply_markup=get_marketplace_menu(), parse_mode="Markdown")
        if SUPER_ADMIN_ID:
            try:
                control_bot.send_message(SUPER_ADMIN_ID, f"🔔 **New Store Application!**\n\n🏪 {data['store_name']}\n👤 {data['owner_name']}\n📱 {data['owner_phone']}\n\nCheck 🛡 Verification")
            except:
                pass

    # ---------- SUPER ADMIN ----------
    @control_bot.message_handler(commands=['superadmin'])
    def super_auth_start(message):
        chat_id = message.chat.id
        if not SUPER_ADMIN_PASSWORD:
            control_bot.reply_to(message, "❌ SUPER_ADMIN_PASSWORD not set.")
            return
        if SUPER_ADMIN_ID != 0 and chat_id != SUPER_ADMIN_ID:
            control_bot.reply_to(message, "❌ Unauthorized.")
            return

        attempt = super_login_attempts.setdefault(chat_id, {"count": 0, "lockout_until": 0})
        if time.time() < attempt["lockout_until"]:
            remaining = int(attempt["lockout_until"] - time.time())
            control_bot.reply_to(message, f"🔒 Locked! Try in {remaining}s.")
            return

        msg = control_bot.send_message(chat_id, "🔐 **Enter Super Admin Password:**", parse_mode="Markdown")
        control_bot.register_next_step_handler(msg, process_super_pass)

    def process_super_pass(message):
        chat_id = message.chat.id
        attempt = super_login_attempts.setdefault(chat_id, {"count": 0, "lockout_until": 0})

        if message.text == SUPER_ADMIN_PASSWORD:
            super_admin_sessions[chat_id] = time.time() + 7200
            super_login_attempts[chat_id] = {"count": 0, "lockout_until": 0}
            control_bot.send_message(chat_id, "🔓 **Welcome Super Admin!**", reply_markup=get_super_admin_keyboard(), parse_mode="Markdown")
        else:
            attempt["count"] += 1
            if attempt["count"] >= 5:
                attempt["lockout_until"] = time.time() + 900
                control_bot.send_message(chat_id, "❌ Locked for 15 minutes.")
            else:
                left = 5 - attempt["count"]
                control_bot.send_message(chat_id, f"❌ Wrong password! {left} attempts remaining.")

    @control_bot.message_handler(func=lambda m: is_super_admin(m.chat.id) and m.text in [
        "📊 Analytics", "👥 Users", "🏪 Stores", "📦 Orders", "🛡 Verification",
        "⭐ Reviews", "📢 Broadcast", "💰 Revenue", "📈 Reports", "⚙️ Settings", "🚪 Logout"
    ])
    def handle_super_actions(message):
        chat_id = message.chat.id
        text = message.text

        if text == "📊 Analytics":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM stores")
                    total_stores = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM stores WHERE is_active=1")
                    active_stores = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM products")
                    total_products = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM orders")
                    total_orders = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0) FROM orders WHERE status_stage >= 1")
                    paid_orders, revenue = cursor.fetchone()
                    cursor.execute("SELECT COUNT(*) FROM stores WHERE is_approved=0")
                    pending_approval = cursor.fetchone()[0]
            finally:
                put_conn(conn)
            text = f"📊 **Analytics**\n\n🏪 Total Stores: {total_stores}\n🟢 Active: {active_stores}\n⏳ Pending Approval: {pending_approval}\n📦 Products: {total_products}\n📦 Orders: {total_orders}\n💰 Revenue: {revenue} ETB\n✅ Paid Orders: {paid_orders}"
            control_bot.send_message(chat_id, text, parse_mode="Markdown")

        elif text == "👥 Users":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT DISTINCT customer_id FROM orders")
                    customers = cursor.fetchall()
            finally:
                put_conn(conn)
            text = f"👥 **Users**\n\nTotal Customers: {len(customers)}\n"
            for idx, (cust_id,) in enumerate(customers[:20], 1):
                text += f"{idx}. {cust_id}\n"
            if len(customers) > 20:
                text += f"\n... and {len(customers) - 20} more"
            control_bot.send_message(chat_id, text, parse_mode="Markdown")

        elif text == "🏪 Stores":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id, store_name, is_active, is_approved, telebirr, username FROM stores ORDER BY id")
                    stores = cursor.fetchall()
            finally:
                put_conn(conn)
            if not stores:
                control_bot.send_message(chat_id, "No stores.")
                return
            for store_id, name, is_act, is_appr, phone, username in stores:
                status = "🟢 Active" if is_act == 1 else "🔴 Blocked"
                approval = "✅ Approved" if is_appr == 1 else "⏳ Pending"
                text = f"🏪 **#{store_id} {name}**\n📌 {status} | {approval}\n📞 {phone}\n👤 @{username}"
                markup = types.InlineKeyboardMarkup()
                if is_act == 1:
                    markup.add(types.InlineKeyboardButton("🔴 Block", callback_data=f"blk_{store_id}"))
                else:
                    markup.add(types.InlineKeyboardButton("🟢 Activate", callback_data=f"unblk_{store_id}"))
                if is_appr == 0:
                    markup.add(types.InlineKeyboardButton("✅ Approve Store", callback_data=f"appr_store_{store_id}"))
                control_bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

        elif text == "📦 Orders":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute('''SELECT o.id, o.total_price, o.status_stage, s.store_name
                                      FROM orders o JOIN stores s ON o.token = s.token
                                      ORDER BY o.id DESC LIMIT 20''')
                    orders = cursor.fetchall()
            finally:
                put_conn(conn)
            if not orders:
                control_bot.send_message(chat_id, "No orders.")
                return
            stages = ["🟡 Pending", "✅ Confirmed", "🚚 On the way", "📦 Delivered"]
            text = "📦 **Recent Orders**\n\n"
            for order_id, total, stage, store_name in orders:
                stage = stage or 0
                stage_label = stages[stage] if 0 <= stage <= 3 else "Unknown"
                text += f"🆔 #{order_id} | 🏪 {store_name} | 💵 {total} ETB | {stage_label}\n"
            control_bot.send_message(chat_id, text, parse_mode="Markdown")

        elif text == "🛡 Verification":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id, store_name, owner_name, owner_phone, created_at, token, username FROM stores WHERE is_approved=0 ORDER BY id")
                    pending = cursor.fetchall()
            finally:
                put_conn(conn)
            if not pending:
                control_bot.send_message(chat_id, "🛡 No pending applications.")
                return
            for store_id, name, owner, phone, created, tok, username in pending:
                text = f"🛡 **Application #{store_id}**\n\n🏪 Store: {name}\n👤 Owner: {owner}\n📱 Phone: {phone}\n📅 Submitted: {created}\n🤖 @{username}"
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("✅ Approve", callback_data=f"appr_store_{store_id}"),
                           types.InlineKeyboardButton("❌ Reject", callback_data=f"rej_store_{store_id}"))
                control_bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

        elif text == "⭐ Reviews":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute('''SELECT r.rating, r.comment, r.created_at, s.store_name, r.chat_id
                                      FROM reviews r JOIN stores s ON r.token = s.token
                                      ORDER BY r.created_at DESC LIMIT 20''')
                    reviews = cursor.fetchall()
            finally:
                put_conn(conn)
            if not reviews:
                control_bot.send_message(chat_id, "⭐ No reviews yet.")
                return
            text = "⭐ **Recent Reviews**\n\n"
            for rating, comment, created, store_name, user_id in reviews:
                stars = "⭐" * rating
                text += f"🏪 {store_name}\n{stars}\n📝 {comment[:50]}{'...' if len(comment) > 50 else ''}\n📅 {created}\n👤 {user_id}\n\n"
            control_bot.send_message(chat_id, text, parse_mode="Markdown")

        elif text == "📢 Broadcast":
            msg = control_bot.send_message(chat_id, "📢 Enter broadcast message:")
            control_bot.register_next_step_handler(msg, send_broadcast)

        elif text == "💰 Revenue":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT s.store_name, COUNT(o.id), COALESCE(SUM(o.total_price + COALESCE(o.delivery_fee,0)),0) FROM stores s LEFT JOIN orders o ON s.token = o.token AND o.status_stage >= 1 GROUP BY s.id ORDER BY sum DESC")
                    revenue_data = cursor.fetchall()
            finally:
                put_conn(conn)
            if not revenue_data:
                control_bot.send_message(chat_id, "💰 No revenue data.")
                return
            total_revenue = sum(row[2] for row in revenue_data)
            text = f"💰 **Revenue Report**\n\nTotal Revenue: {total_revenue} ETB\n\n"
            for store_name, orders, rev in revenue_data:
                text += f"🏪 {store_name}: {orders} orders, {rev} ETB\n"
            control_bot.send_message(chat_id, text, parse_mode="Markdown")

        elif text == "📈 Reports":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM stores")
                    total_stores = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM orders")
                    total_orders = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM products")
                    total_products = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0) FROM orders WHERE status_stage >= 1")
                    paid_orders, revenue = cursor.fetchone()
                    cursor.execute("SELECT COUNT(*) FROM stores WHERE is_approved=0")
                    pending = cursor.fetchone()[0]
            finally:
                put_conn(conn)
            report = f"📈 **System Report**\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n🏪 Stores: {total_stores}\n📦 Orders: {total_orders}\n📦 Products: {total_products}\n✅ Paid Orders: {paid_orders}\n💰 Revenue: {revenue} ETB\n⏳ Pending Approval: {pending}"
            control_bot.send_message(chat_id, report, parse_mode="Markdown")

        elif text == "⚙️ Settings":
            text = f"⚙️ **Settings**\n\n📞 Support: {SUPPORT_USERNAME}\n🔐 Super Admin: {SUPER_ADMIN_ID}\n⏰ Session Timeout: 2 hours\n\nCommands:\n/superadmin - Login\n/start - Marketplace\n/help - Help"
            control_bot.send_message(chat_id, text, parse_mode="Markdown")

        elif text == "🚪 Logout":
            super_admin_sessions.pop(chat_id, None)
            control_bot.send_message(chat_id, "🔒 Logged out.", reply_markup=get_marketplace_menu())

    def send_broadcast(message):
        chat_id = message.chat.id
        broadcast_text = message.text
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT DISTINCT customer_id FROM orders")
                users = cursor.fetchall()
        finally:
            put_conn(conn)
        sent = 0
        for (user_id,) in users:
            try:
                control_bot.send_message(user_id, f"📢 **Broadcast**\n\n{broadcast_text}")
                sent += 1
                time.sleep(0.05)
            except:
                pass
        control_bot.reply_to(message, f"✅ Broadcast sent to {sent} users.")

    @control_bot.callback_query_handler(func=lambda call: call.data.startswith(("blk_", "unblk_", "appr_store_", "rej_store_")))
    def handle_store_actions(call):
        chat_id = call.message.chat.id
        if not is_super_admin(chat_id):
            control_bot.answer_callback_query(call.id, "❌ Session expired.")
            return

        action, store_id_str = call.data.split("_", 1)
        store_id = int(store_id_str)

        if action == "blk":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE stores SET is_active = 0 WHERE id = %s", (store_id,))
                    conn.commit()
            finally:
                put_conn(conn)
            control_bot.answer_callback_query(call.id, "🔴 Store blocked")
            try:
                control_bot.edit_message_text(f"{call.message.text}\n\n⚠️ **🔴 Blocked**", chat_id, call.message.message_id, parse_mode="Markdown")
            except:
                pass

        elif action == "unblk":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE stores SET is_active = 1 WHERE id = %s", (store_id,))
                    conn.commit()
            finally:
                put_conn(conn)
            control_bot.answer_callback_query(call.id, "🟢 Activated")
            try:
                control_bot.edit_message_text(f"{call.message.text}\n\n⚠️ **🟢 Activated**", chat_id, call.message.message_id, parse_mode="Markdown")
            except:
                pass

        elif action == "appr_store":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT token, store_name, admin_id, username FROM stores WHERE id=%s", (store_id,))
                    row = cur.fetchone()
                    if row:
                        tok, store_name, admin_id, username = row
                        cur.execute("UPDATE stores SET is_approved = 1 WHERE id=%s", (store_id,))
                        conn.commit()
                        # Start the bot
                        start_shop_bot(tok)
                        # Notify the owner
                        try:
                            control_bot.send_message(admin_id, f"🎉 **Congratulations!**\n\nYour store '{store_name}' has been approved!\n\nYou can now manage your store at https://t.me/{username}\nLogin: `/login [your_password]`")
                        except:
                            pass
            finally:
                put_conn(conn)
            control_bot.answer_callback_query(call.id, "✅ Store approved!")
            try:
                control_bot.edit_message_text(f"{call.message.text}\n\n✅ **Approved!**", chat_id, call.message.message_id, parse_mode="Markdown")
            except:
                pass

        elif action == "rej_store":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT admin_id, store_name FROM stores WHERE id=%s", (store_id,))
                    row = cur.fetchone()
                    if row:
                        admin_id, store_name = row
                        cur.execute("DELETE FROM stores WHERE id=%s", (store_id,))
                        conn.commit()
                        try:
                            control_bot.send_message(admin_id, f"❌ Your store '{store_name}' has been rejected.\nPlease contact support for more information.")
                        except:
                            pass
            finally:
                put_conn(conn)
            control_bot.answer_callback_query(call.id, "❌ Store rejected")
            try:
                control_bot.edit_message_text(f"{call.message.text}\n\n❌ **Rejected**", chat_id, call.message.message_id, parse_mode="Markdown")
            except:
                pass

    # ---------- START CONTROL BOT ----------
    def _run_control_bot():
        while True:
            try:
                control_bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                print(f"⚠️ Control bot crashed: {e}. Restarting in 5s...")
                time.sleep(5)

    threading.Thread(target=_run_control_bot, name="ControlBot", daemon=True).start()
    print("✅ Control Bot is running.")

else:
    print("⚠️ CONTROL_BOT_TOKEN not set.")

# ============================================================
# MAIN LOOP
# ============================================================
while True:
    time.sleep(3600)
