import os
import threading
import hashlib
import secrets
import time
import math
import re
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
    return "EthioSuq Marketplace is Running!"

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

# ============================================================
# 3. POSTGRESQL
# ============================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL missing!")

db_pool_lock = threading.Lock()

try:
    db_pool = ThreadedConnectionPool(1, 20, dsn=DATABASE_URL)
    print("✅ PostgreSQL Connection Pool initialized.")
except Exception as e:
    print(f"❌ Failed to connect: {e}")
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
            with db_pool_lock:
                try:
                    db_pool.closeall()
                except:
                    pass
                db_pool = ThreadedConnectionPool(1, 20, dsn=DATABASE_URL)
    raise last_err

def put_conn(conn):
    if conn is None:
        return
    try:
        db_pool.putconn(conn)
    except:
        try:
            conn.close()
        except:
            pass

# ============================================================
# 3.1 FIXED: init_db() - Categories table without token column
# ============================================================
def init_db():
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            # Stores table
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
                                is_approved INTEGER DEFAULT 0,
                                category TEXT,
                                rating REAL DEFAULT 0,
                                total_reviews INTEGER DEFAULT 0,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

            # Products table
            cursor.execute('''CREATE TABLE IF NOT EXISTS products (
                                id SERIAL PRIMARY KEY,
                                token TEXT,
                                name_am TEXT,
                                name_en TEXT,
                                price REAL,
                                stock INTEGER,
                                desc_am TEXT,
                                desc_en TEXT,
                                image_url TEXT,
                                category TEXT,
                                discount_percent INTEGER DEFAULT 0,
                                views INTEGER DEFAULT 0,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

            # Orders table
            cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                                id SERIAL PRIMARY KEY,
                                token TEXT,
                                customer_id BIGINT,
                                status_am TEXT,
                                status_en TEXT,
                                total_price REAL,
                                delivery_fee REAL DEFAULT 0,
                                status_stage INTEGER DEFAULT 0,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                delivered_at TIMESTAMP)''')

            # Order items
            cursor.execute('''CREATE TABLE IF NOT EXISTS order_items (
                                id SERIAL PRIMARY KEY,
                                order_id INTEGER,
                                product_id INTEGER,
                                qty INTEGER,
                                price REAL)''')

            # User languages
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_langs (
                                chat_id BIGINT PRIMARY KEY,
                                lang TEXT)''')

            # Customer info
            cursor.execute('''CREATE TABLE IF NOT EXISTS customer_info (
                                chat_id BIGINT PRIMARY KEY,
                                phone TEXT,
                                lat REAL,
                                lng REAL,
                                username TEXT,
                                full_name TEXT)''')

            # Favorites
            cursor.execute('''CREATE TABLE IF NOT EXISTS favorites (
                                chat_id BIGINT,
                                product_id INTEGER,
                                token TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                PRIMARY KEY (chat_id, product_id))''')

            # Favorite stores
            cursor.execute('''CREATE TABLE IF NOT EXISTS favorite_stores (
                                chat_id BIGINT,
                                store_token TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                PRIMARY KEY (chat_id, store_token))''')

            # Reviews
            cursor.execute('''CREATE TABLE IF NOT EXISTS reviews (
                                id SERIAL PRIMARY KEY,
                                chat_id BIGINT,
                                token TEXT,
                                product_id INTEGER,
                                order_id INTEGER,
                                rating INTEGER,
                                comment TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

            # Coupons
            cursor.execute('''CREATE TABLE IF NOT EXISTS coupons (
                                id SERIAL PRIMARY KEY,
                                code TEXT UNIQUE,
                                discount_percent INTEGER,
                                valid_until TIMESTAMP,
                                used_by BIGINT[] DEFAULT '{}',
                                store_token TEXT)''')

            # User points
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_points (
                                chat_id BIGINT PRIMARY KEY,
                                points INTEGER DEFAULT 0,
                                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

            # Notifications
            cursor.execute('''CREATE TABLE IF NOT EXISTS notifications (
                                id SERIAL PRIMARY KEY,
                                chat_id BIGINT,
                                title TEXT,
                                message TEXT,
                                is_read INTEGER DEFAULT 0,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

            # ============================================================
            # FIXED: Categories table - Drop and recreate without token column
            # ============================================================
            # First, check if categories table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'categories'
                )
            """)
            table_exists = cursor.fetchone()[0]
            
            if table_exists:
                # Check if token column exists
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name='categories' AND column_name='token'
                """)
                has_token = cursor.fetchone()
                
                if has_token:
                    # Drop the token column
                    cursor.execute("ALTER TABLE categories DROP COLUMN token")
                    print("✅ Removed token column from categories")
            else:
                # Create fresh categories table
                cursor.execute('''CREATE TABLE categories (
                                    id SERIAL PRIMARY KEY,
                                    name_am TEXT UNIQUE,
                                    name_en TEXT,
                                    icon TEXT,
                                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
                print("✅ Created categories table")

            # Insert default categories
            cursor.execute('''INSERT INTO categories (name_am, name_en, icon) VALUES 
                              ('ሁሉም', 'All', '📋'),
                              ('ልብስ', 'Fashion', '👗'),
                              ('ጫማ', 'Shoes', '👟'),
                              ('ሞባይል', 'Mobile', '📱'),
                              ('ኤሌክትሮኒክስ', 'Electronics', '💻'),
                              ('ውበት', 'Beauty', '💄'),
                              ('ምግብ', 'Food', '🍕'),
                              ('ቤት', 'Home', '🏠'),
                              ('ስፖርት', 'Sports', '⚽'),
                              ('መኪና', 'Cars', '🚗'),
                              ('ጨዋታ', 'Games', '🎮')
                              ON CONFLICT (name_am) DO NOTHING''')
            
            conn.commit()
            print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Error in init_db: {e}")
        conn.rollback()
        raise e
    finally:
        put_conn(conn)

# Call init_db
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

def is_valid_phone(phone):
    return bool(re.match(r'^[0-9]{10}$', phone))

def is_valid_password(password):
    return len(password) >= 6

# ============================================================
# 5. ETHIOSUQ MAIN BOT
# ============================================================
CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")

if CONTROL_BOT_TOKEN:
    bot = telebot.TeleBot(CONTROL_BOT_TOKEN)
    try:
        bot.remove_webhook()
    except:
        pass

    # Global states
    user_carts = {}
    active_sessions = {}
    admin_states = {}
    reg_wizard_states = {}
    login_attempts = {}
    lang_cache = {}
    super_admin_sessions = {}
    super_login_attempts = {}

    # Super Admin config
    SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
    SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
    SUPPORT_USERNAME = os.environ.get("SUPPORT_USERNAME", "@support")

    # ============================================================
    # 5.1 LANGUAGE
    # ============================================================
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

    def set_user_lang(chat_id, lang):
        lang_cache[chat_id] = lang
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO user_langs (chat_id, lang) VALUES (%s, %s)
                                  ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang''', (chat_id, lang))
                conn.commit()
        finally:
            put_conn(conn)

    def is_super_admin(chat_id):
        return chat_id in super_admin_sessions and time.time() < super_admin_sessions[chat_id]

    # ============================================================
    # 5.2 MAIN MENU (3 BUTTONS)
    # ============================================================
    def get_main_menu():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(
            types.KeyboardButton("📝 መዝገብ ማእከል"),
            types.KeyboardButton("🤖 AI ፍለጋ"),
            types.KeyboardButton("💬 እርዳታ ማእከል")
        )
        return markup

    def get_super_admin_menu():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("📊 ዳሽቦርድ"),
            types.KeyboardButton("🏪 ሁሉም ሱቆች"),
            types.KeyboardButton("🛡 ለማጽደቅ የቆሙ"),
            types.KeyboardButton("📦 ሁሉም ትዕዛዞች"),
            types.KeyboardButton("💰 ገቢ"),
            types.KeyboardButton("👥 ተጠቃሚዎች"),
            types.KeyboardButton("📢 መልዕክት ላክ"),
            types.KeyboardButton("🚪 ውጣ")
        )
        return markup

    # ============================================================
    # 5.3 START
    # ============================================================
    @bot.message_handler(commands=['start'])
    def start_message(message):
        chat_id = message.chat.id
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="lang_am"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")
        )
        bot.send_message(
            chat_id,
            "🌍 **ቋንቋ ይምረጡ / Select Language**",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
    def set_language(call):
        chat_id = call.message.chat.id
        lang = call.data.split("_")[1]
        set_user_lang(chat_id, lang)
        bot.delete_message(chat_id, call.message.message_id)
        
        welcome = "👋 **እንኳን ወደ EthioSuq ገበያ በደህና መጡ!**\n\nእባክዎ ከታች ካሉት አማራጮች ይምረጡ:" if lang == "am" else "👋 **Welcome to EthioSuq Marketplace!**\n\nPlease choose from the options below:"
        bot.send_message(chat_id, welcome, reply_markup=get_main_menu(), parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    # ============================================================
    # 5.4 SUPER ADMIN LOGIN
    # ============================================================
    @bot.message_handler(commands=['superadmin'])
    def super_auth_start(message):
        chat_id = message.chat.id
        if not SUPER_ADMIN_PASSWORD:
            bot.reply_to(message, "❌ SUPER_ADMIN_PASSWORD not set.")
            return
        if SUPER_ADMIN_ID != 0 and chat_id != SUPER_ADMIN_ID:
            bot.reply_to(message, "❌ Unauthorized.")
            return

        attempt = super_login_attempts.setdefault(chat_id, {"count": 0, "lockout_until": 0})
        if time.time() < attempt["lockout_until"]:
            remaining = int(attempt["lockout_until"] - time.time())
            bot.reply_to(message, f"🔒 Locked! Try in {remaining}s.")
            return

        msg = bot.send_message(chat_id, "🔐 **Enter Super Admin Password:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_super_pass)

    def process_super_pass(message):
        chat_id = message.chat.id
        attempt = super_login_attempts.setdefault(chat_id, {"count": 0, "lockout_until": 0})

        if message.text == SUPER_ADMIN_PASSWORD:
            super_admin_sessions[chat_id] = time.time() + 7200
            super_login_attempts[chat_id] = {"count": 0, "lockout_until": 0}
            bot.send_message(
                chat_id,
                "🔓 **Welcome Super Admin!**\n\nSelect an option:",
                reply_markup=get_super_admin_menu(),
                parse_mode="Markdown"
            )
        else:
            attempt["count"] += 1
            if attempt["count"] >= 5:
                attempt["lockout_until"] = time.time() + 900
                bot.send_message(chat_id, "❌ Locked for 15 minutes.")
            else:
                left = 5 - attempt["count"]
                bot.send_message(chat_id, f"❌ Wrong password! {left} attempts remaining.")

    # ============================================================
    # 5.5 SUPER ADMIN - DASHBOARD
    # ============================================================
    @bot.message_handler(func=lambda m: is_super_admin(m.chat.id) and m.text in [
        "📊 ዳሽቦርድ", "🏪 ሁሉም ሱቆች", "🛡 ለማጽደቅ የቆሙ",
        "📦 ሁሉም ትዕዛዞች", "💰 ገቢ", "👥 ተጠቃሚዎች",
        "📢 መልዕክት ላክ", "🚪 ውጣ"
    ])
    def handle_super_admin_actions(message):
        chat_id = message.chat.id
        text = message.text

        if text == "📊 ዳሽቦርድ":
            show_dashboard(chat_id)
        elif text == "🏪 ሁሉም ሱቆች":
            show_all_stores(chat_id)
        elif text == "🛡 ለማጽደቅ የቆሙ":
            show_pending_stores(chat_id)
        elif text == "📦 ሁሉም ትዕዛዞች":
            show_all_orders(chat_id)
        elif text == "💰 ገቢ":
            show_revenue(chat_id)
        elif text == "👥 ተጠቃሚዎች":
            show_users(chat_id)
        elif text == "📢 መልዕክት ላክ":
            broadcast_prompt(chat_id)
        elif text == "🚪 ውጣ":
            super_admin_sessions.pop(chat_id, None)
            bot.send_message(chat_id, "🔒 Logged out.", reply_markup=get_main_menu())

    def show_dashboard(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM stores")
                total_stores = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM stores WHERE is_approved=1 AND is_active=1")
                active_stores = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM stores WHERE is_approved=0")
                pending_stores = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM stores WHERE is_active=0")
                blocked_stores = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM products")
                total_products = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM orders")
                total_orders = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0) FROM orders WHERE status_stage >= 1")
                paid_orders, revenue = cursor.fetchone()
                cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM orders")
                total_users = cursor.fetchone()[0]
        finally:
            put_conn(conn)

        text = (
            "📊 **Super Admin Dashboard**\n\n"
            f"🏪 Total Stores: {total_stores}\n"
            f"🟢 Active: {active_stores}\n"
            f"🟡 Pending: {pending_stores}\n"
            f"🔴 Blocked: {blocked_stores}\n"
            f"📦 Products: {total_products}\n"
            f"📦 Orders: {total_orders}\n"
            f"✅ Paid: {paid_orders}\n"
            f"💰 Revenue: {revenue} ETB\n"
            f"👥 Users: {total_users}\n"
            f"📅 {time.strftime('%Y-%m-%d %H:%M')}"
        )
        bot.send_message(chat_id, text, parse_mode="Markdown")

    # ============================================================
    # 5.6 SUPER ADMIN - ALL STORES
    # ============================================================
    def show_all_stores(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT id, store_name, admin_id, username, owner_name, owner_phone, 
                                  is_approved, is_active, category, rating, created_at, token
                                  FROM stores ORDER BY id''')
                stores = cursor.fetchall()
        finally:
            put_conn(conn)

        if not stores:
            bot.send_message(chat_id, "🏪 No stores registered.")
            return

        for store in stores:
            store_id, name, admin_id, username, owner, phone, is_approved, is_active, category, rating, created, token = store
            
            status = "✅ Approved" if is_approved == 1 else "⏳ Pending"
            active = "🟢 Active" if is_active == 1 else "🔴 Blocked"
            stars = "⭐" * int(rating) if rating else ""
            
            text = (
                f"🏪 **#{store_id} {name}**\n"
                f"👤 {owner}\n"
                f"📱 {phone}\n"
                f"🤖 @{username}\n"
                f"📂 {category or 'General'}\n"
                f"{stars}\n"
                f"📌 {status} | {active}"
            )
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            # Approval buttons
            if is_approved == 0:
                markup.add(
                    types.InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_store_{store_id}"),
                    types.InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_store_{store_id}")
                )
            
            # Active/Block buttons
            if is_active == 1:
                markup.add(types.InlineKeyboardButton("🔴 Block", callback_data=f"admin_block_store_{store_id}"))
            else:
                markup.add(types.InlineKeyboardButton("🟢 Activate", callback_data=f"admin_activate_store_{store_id}"))
            
            # View buttons
            markup.add(
                types.InlineKeyboardButton("📦 Products", callback_data=f"admin_products_{store_id}"),
                types.InlineKeyboardButton("📬 Orders", callback_data=f"admin_orders_{store_id}")
            )
            markup.add(types.InlineKeyboardButton("📊 Stats", callback_data=f"admin_stats_{store_id}"))
            
            # Visit store
            if username:
                markup.add(types.InlineKeyboardButton("🛍️ Visit", url=f"https://t.me/{username}"))
            
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            time.sleep(0.05)

    def show_pending_stores(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT id, store_name, admin_id, username, owner_name, owner_phone, 
                                  category, created_at, token
                                  FROM stores WHERE is_approved=0 ORDER BY id''')
                stores = cursor.fetchall()
        finally:
            put_conn(conn)

        if not stores:
            bot.send_message(chat_id, "🛡 No pending stores.")
            return

        for store in stores:
            store_id, name, admin_id, username, owner, phone, category, created, token = store
            
            text = (
                f"🛡 **#{store_id} {name}**\n"
                f"👤 {owner}\n"
                f"📱 {phone}\n"
                f"🤖 @{username}\n"
                f"📂 {category or 'General'}\n"
                f"📅 {created}"
            )
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_store_{store_id}"),
                types.InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_store_{store_id}")
            )
            
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            time.sleep(0.05)

    # ============================================================
    # 5.7 SUPER ADMIN - ORDERS
    # ============================================================
    def show_all_orders(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT o.id, o.total_price, o.delivery_fee, o.status_stage, 
                                  o.customer_id, o.created_at, s.store_name
                                  FROM orders o JOIN stores s ON o.token = s.token
                                  ORDER BY o.id DESC LIMIT 20''')
                orders = cursor.fetchall()
        finally:
            put_conn(conn)

        if not orders:
            bot.send_message(chat_id, "📦 No orders.")
            return

        stages = ["🟡 Pending", "✅ Confirmed", "🚚 On the way", "📦 Delivered", "❌ Cancelled"]
        
        for order in orders:
            order_id, total, fee, stage, customer, created, store_name = order
            stage_label = stages[stage] if 0 <= stage <= 4 else "Unknown"
            
            text = (
                f"🆔 **#{order_id}**\n"
                f"🏪 {store_name}\n"
                f"👤 {customer}\n"
                f"💰 {total + (fee or 0)} ETB\n"
                f"📌 {stage_label}\n"
                f"📅 {created}"
            )
            
            markup = types.InlineKeyboardMarkup()
            if stage == 0:
                markup.add(
                    types.InlineKeyboardButton("✅ Confirm", callback_data=f"admin_confirm_order_{order_id}"),
                    types.InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cancel_order_{order_id}")
                )
            elif stage == 1:
                markup.add(types.InlineKeyboardButton("🚚 Ship", callback_data=f"admin_ship_order_{order_id}"))
            elif stage == 2:
                markup.add(types.InlineKeyboardButton("📦 Deliver", callback_data=f"admin_deliver_order_{order_id}"))
            
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            time.sleep(0.05)

    def show_revenue(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT s.store_name, s.id, 
                                  COUNT(o.id) as order_count,
                                  COALESCE(SUM(o.total_price + COALESCE(o.delivery_fee,0)),0) as revenue,
                                  COUNT(DISTINCT o.customer_id) as customers
                                  FROM stores s 
                                  LEFT JOIN orders o ON s.token = o.token AND o.status_stage >= 1
                                  GROUP BY s.id, s.store_name
                                  ORDER BY revenue DESC''')
                reports = cursor.fetchall()
        finally:
            put_conn(conn)

        if not reports:
            bot.send_message(chat_id, "💰 No revenue data.")
            return

        total_revenue = sum(r[2] for r in reports)
        
        text = f"💰 **Revenue Report**\n\nTotal: {total_revenue} ETB\n\n"
        
        for store_name, store_id, order_count, revenue, customers in reports[:15]:
            if revenue > 0:
                text += f"🏪 **{store_name}**\n"
                text += f"   📦 {order_count} orders\n"
                text += f"   💰 {revenue} ETB\n"
                text += f"   👥 {customers} customers\n\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")

    def show_users(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT DISTINCT customer_id, COUNT(*) as orders, 
                                  COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0) as spent
                                  FROM orders GROUP BY customer_id 
                                  ORDER BY orders DESC LIMIT 20''')
                users = cursor.fetchall()
                
                cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM orders")
                total_users = cursor.fetchone()[0]
        finally:
            put_conn(conn)

        text = f"👥 **Users**\n\nTotal: {total_users}\n\n"
        
        for user_id, orders, spent in users:
            text += f"🆔 {user_id}\n"
            text += f"   📦 {orders} orders\n"
            text += f"   💰 {spent} ETB\n\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")

    def broadcast_prompt(chat_id):
        msg = bot.send_message(chat_id, "📢 **Broadcast**\n\nEnter message:")
        bot.register_next_step_handler(msg, send_broadcast)

    def send_broadcast(message):
        chat_id = message.chat.id
        text = message.text
        
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
                bot.send_message(user_id, f"📢 **Broadcast**\n\n{text}")
                sent += 1
                time.sleep(0.05)
            except:
                pass
        
        bot.reply_to(message, f"✅ Sent to {sent} users.")

    # ============================================================
    # 5.8 SUPER ADMIN - CALLBACKS
    # ============================================================
    @bot.callback_query_handler(func=lambda call: is_super_admin(call.message.chat.id) and call.data.startswith("admin_"))
    def handle_super_admin_callbacks(call):
        chat_id = call.message.chat.id
        data = call.data
        parts = data.split("_")
        action = parts[1]
        
        if action == "approve_store":
            store_id = int(parts[2])
            approve_store(call, store_id)
        elif action == "reject_store":
            store_id = int(parts[2])
            reject_store(call, store_id)
        elif action == "block_store":
            store_id = int(parts[2])
            block_store(call, store_id)
        elif action == "activate_store":
            store_id = int(parts[2])
            activate_store(call, store_id)
        elif action == "products":
            store_id = int(parts[2])
            view_store_products(call, store_id)
        elif action == "orders":
            store_id = int(parts[2])
            view_store_orders(call, store_id)
        elif action == "stats":
            store_id = int(parts[2])
            view_store_stats(call, store_id)
        elif action == "confirm_order":
            order_id = int(parts[2])
            confirm_order(call, order_id)
        elif action == "cancel_order":
            order_id = int(parts[2])
            cancel_order(call, order_id)
        elif action == "ship_order":
            order_id = int(parts[2])
            ship_order(call, order_id)
        elif action == "deliver_order":
            order_id = int(parts[2])
            deliver_order(call, order_id)

    def approve_store(call, store_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT token, store_name, admin_id, username FROM stores WHERE id=%s", (store_id,))
                store = cursor.fetchone()
                if store:
                    token, store_name, admin_id, username = store
                    cursor.execute("UPDATE stores SET is_approved=1 WHERE id=%s", (store_id,))
                    conn.commit()
                    
                    try:
                        bot.send_message(admin_id, f"🎉 **Congratulations!**\n\nYour store '{store_name}' has been approved!\n\nYou can now manage your store at https://t.me/{username}")
                    except:
                        pass
                    
                    bot.answer_callback_query(call.id, "✅ Store approved!")
                    bot.edit_message_text(f"{call.message.text}\n\n✅ **APPROVED!**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        finally:
            put_conn(conn)

    def reject_store(call, store_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT store_name, admin_id FROM stores WHERE id=%s", (store_id,))
                store = cursor.fetchone()
                if store:
                    store_name, admin_id = store
                    cursor.execute("DELETE FROM stores WHERE id=%s", (store_id,))
                    conn.commit()
                    
                    try:
                        bot.send_message(admin_id, f"❌ **Store Rejected**\n\nYour store '{store_name}' has been rejected.")
                    except:
                        pass
                    
                    bot.answer_callback_query(call.id, "❌ Rejected!")
                    bot.edit_message_text(f"{call.message.text}\n\n❌ **REJECTED**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        finally:
            put_conn(conn)

    def block_store(call, store_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET is_active=0 WHERE id=%s", (store_id,))
                conn.commit()
            bot.answer_callback_query(call.id, "🔴 Blocked!")
            bot.edit_message_text(f"{call.message.text}\n\n🔴 **BLOCKED**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        finally:
            put_conn(conn)

    def activate_store(call, store_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET is_active=1 WHERE id=%s", (store_id,))
                conn.commit()
            bot.answer_callback_query(call.id, "🟢 Activated!")
            bot.edit_message_text(f"{call.message.text}\n\n🟢 **ACTIVATED**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        finally:
            put_conn(conn)

    def view_store_products(call, store_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT token FROM stores WHERE id=%s", (store_id,))
                store = cursor.fetchone()
                if store:
                    token = store[0]
                    cursor.execute("SELECT id, name_am, name_en, price, stock, category FROM products WHERE token=%s ORDER BY id LIMIT 10", (token,))
                    products = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not products:
            bot.send_message(call.message.chat.id, "📦 No products.")
            bot.answer_callback_query(call.id)
            return
        
        text = f"📦 **Products ({len(products)})**\n\n"
        for p_id, name_am, name_en, price, stock, category in products:
            text += f"🆔 #{p_id} {name_am}\n"
            text += f"   💰 {price} ETB | 📦 {stock}\n"
            text += f"   📂 {category or 'General'}\n\n"
        
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    def view_store_orders(call, store_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT token FROM stores WHERE id=%s", (store_id,))
                store = cursor.fetchone()
                if store:
                    token = store[0]
                    cursor.execute('''SELECT id, customer_id, total_price, delivery_fee, status_stage, created_at
                                      FROM orders WHERE token=%s ORDER BY id DESC LIMIT 10''', (token,))
                    orders = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not orders:
            bot.send_message(call.message.chat.id, "📬 No orders.")
            bot.answer_callback_query(call.id)
            return
        
        stages = ["🟡 Pending", "✅ Confirmed", "🚚 On the way", "📦 Delivered", "❌ Cancelled"]
        text = f"📬 **Orders**\n\n"
        for order_id, customer, total, fee, stage, created in orders:
            stage_label = stages[stage] if 0 <= stage <= 4 else "Unknown"
            text += f"🆔 #{order_id} | 👤 {customer}\n"
            text += f"   💰 {total + (fee or 0)} ETB | {stage_label}\n"
            text += f"   📅 {created}\n\n"
        
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    def view_store_stats(call, store_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT token, store_name FROM stores WHERE id=%s", (store_id,))
                store = cursor.fetchone()
                if store:
                    token, name = store
                    cursor.execute("SELECT COUNT(*) FROM products WHERE token=%s", (token,))
                    products = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM orders WHERE token=%s", (token,))
                    orders = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0) FROM orders WHERE token=%s AND status_stage >= 1", (token,))
                    paid_orders, revenue = cursor.fetchone()
                    cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM orders WHERE token=%s", (token,))
                    customers = cursor.fetchone()[0]
        finally:
            put_conn(conn)
        
        text = f"📊 **{name}**\n\n"
        text += f"📦 Products: {products}\n"
        text += f"📦 Orders: {orders}\n"
        text += f"✅ Paid: {paid_orders}\n"
        text += f"💰 Revenue: {revenue} ETB\n"
        text += f"👥 Customers: {customers}\n"
        
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    def confirm_order(call, order_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE orders SET status_stage=1, status_am=%s, status_en=%s WHERE id=%s",
                               (ORDER_STAGES_AM[1], ORDER_STAGES_EN[1], order_id))
                conn.commit()
            bot.answer_callback_query(call.id, "✅ Confirmed!")
            bot.edit_message_text(f"{call.message.text}\n\n✅ **CONFIRMED**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        finally:
            put_conn(conn)

    def cancel_order(call, order_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE orders SET status_stage=-1, status_am=%s, status_en=%s WHERE id=%s",
                               ("❌ ተሰርዟል", "❌ Cancelled", order_id))
                conn.commit()
            bot.answer_callback_query(call.id, "❌ Cancelled!")
            bot.edit_message_text(f"{call.message.text}\n\n❌ **CANCELLED**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        finally:
            put_conn(conn)

    def ship_order(call, order_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE orders SET status_stage=2, status_am=%s, status_en=%s WHERE id=%s",
                               (ORDER_STAGES_AM[2], ORDER_STAGES_EN[2], order_id))
                conn.commit()
            bot.answer_callback_query(call.id, "🚚 Shipped!")
            bot.edit_message_text(f"{call.message.text}\n\n🚚 **SHIPPED**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        finally:
            put_conn(conn)

    def deliver_order(call, order_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE orders SET status_stage=3, status_am=%s, status_en=%s, delivered_at=NOW() WHERE id=%s",
                               (ORDER_STAGES_AM[3], ORDER_STAGES_EN[3], order_id))
                conn.commit()
            bot.answer_callback_query(call.id, "📦 Delivered!")
            bot.edit_message_text(f"{call.message.text}\n\n📦 **DELIVERED**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        finally:
            put_conn(conn)

    # ============================================================
    # 5.9 📝 መዝገብ ማእከል - REGISTER STORE
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == "📝 መዝገብ ማእከል")
    def register_wizard_start(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        reg_wizard_states[chat_id] = {"data": {}}
        
        msg = bot.send_message(
            chat_id,
            "🏪 **የሱቅ ስም ያስገቡ**\n\nለምሳሌ: ቴክ ሱቅ" if lang == "am" else "🏪 **Enter store name**\n\nExample: Tech Store",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, reg_w_store_name)

    def reg_w_store_name(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        reg_wizard_states[chat_id]["data"]["store_name"] = message.text.strip()
        
        msg = bot.send_message(
            chat_id,
            "📱 **ስልክ ቁጥር ያስገቡ**\n\n⚠️ 10 አሃዝ ቁጥሮች ብቻ\n\nለምሳሌ: 0912345678" if lang == "am" else "📱 **Enter phone number**\n\n⚠️ 10 digits only\n\nExample: 0912345678",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, reg_w_phone)

    def reg_w_phone(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        phone = message.text.strip()
        
        if not is_valid_phone(phone):
            msg = bot.reply_to(
                message,
                "❌ **የተሳሳተ ስልክ ቁጥር!**\n\n10 አሃዝ ቁጥሮች ብቻ\n\nእንደገና ይሞክሩ:" if lang == "am" else "❌ **Invalid phone!**\n\n10 digits only.\n\nTry again:",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, reg_w_phone)
            return
        
        reg_wizard_states[chat_id]["data"]["owner_phone"] = phone
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("📍 አካባቢ አጋራ" if lang == "am" else "📍 Share Location", request_location=True))
        msg = bot.send_message(
            chat_id,
            "📍 **አካባቢ ያጋሩ**\n\nከታች ያለውን አዝራር በመጫን ብቻ 👇" if lang == "am" else "📍 **Share location**\n\nUse the button below 👇",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, reg_w_location)

    def reg_w_location(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        if not message.location:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(types.KeyboardButton("📍 አካባቢ አጋራ" if lang == "am" else "📍 Share Location", request_location=True))
            msg = bot.send_message(
                chat_id,
                "❌ **አካባቢ አልተጋሩም!**\n\nእባክዎ አዝራሩን ይጫኑ 👇" if lang == "am" else "❌ **Location not shared!**\n\nPlease click the button 👇",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, reg_w_location)
            return
        
        reg_wizard_states[chat_id]["data"]["shop_lat"] = message.location.latitude
        reg_wizard_states[chat_id]["data"]["shop_lng"] = message.location.longitude
        
        # Get categories
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT name_am, name_en FROM categories ORDER BY id")
                categories = cursor.fetchall()
        finally:
            put_conn(conn)
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        for cat_am, cat_en in categories:
            label = cat_am if lang == "am" else cat_en
            markup.add(types.InlineKeyboardButton(label, callback_data=f"regcat_{cat_am}"))
        
        msg = bot.send_message(
            chat_id,
            "📂 **ምድብ ይምረጡ**" if lang == "am" else "📂 **Select category**",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, reg_w_category)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("regcat_"))
    def reg_category_callback(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        category = call.data.split("_")[1]
        
        if chat_id in reg_wizard_states:
            reg_wizard_states[chat_id]["data"]["category"] = category
        
        bot.answer_callback_query(call.id, f"✅ {category}")
        
        msg = bot.send_message(
            chat_id,
            "🖼 **የሱቅ ፎቶ ያስገቡ**\n\n'ዝለል' ብለው መልእክት ማለፍ ይችላሉ" if lang == "am" else "🖼 **Enter store photo**\n\nType 'skip' to skip",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, reg_w_photo)

    def reg_w_category(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        if chat_id in reg_wizard_states:
            reg_wizard_states[chat_id]["data"]["category"] = message.text.strip()
        
        msg = bot.send_message(
            chat_id,
            "🖼 **የሱቅ ፎቶ ያስገቡ**\n\n'ዝለል' ብለው መልእክት ማለፍ ይችላሉ" if lang == "am" else "🖼 **Enter store photo**\n\nType 'skip' to skip",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, reg_w_photo)

    def reg_w_photo(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        if message.photo:
            reg_wizard_states[chat_id]["data"]["shop_photo"] = message.photo[-1].file_id
        else:
            reg_wizard_states[chat_id]["data"]["shop_photo"] = ""
        
        msg = bot.send_message(
            chat_id,
            "🔑 **የሱቅ ይለፍ ቃል ያስገቡ**\n\n⚠️ ቢያንስ 6 ቁምፊዎች" if lang == "am" else "🔑 **Enter store password**\n\n⚠️ Minimum 6 characters",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, reg_w_password)

    def reg_w_password(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        password = message.text.strip()
        
        if not is_valid_password(password):
            msg = bot.reply_to(
                message,
                "❌ **የይለፍ ቃሉ በጣም አጭር ነው!**\n\nቢያንስ 6 ቁምፊዎች\n\nእንደገና ይሞክሩ:" if lang == "am" else "❌ **Password too short!**\n\nMinimum 6 characters.\n\nTry again:",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, reg_w_password)
            return
        
        reg_wizard_states[chat_id]["data"]["password"] = password
        
        msg = bot.send_message(
            chat_id,
            "🤖 **Bot API Token ያስገቡ**\n\nከ @BotFather ያገኙትን Token\n\nየሱቅዎ ቦት በራስ-ሰር ይገናኛል!" if lang == "am" else "🤖 **Enter Bot API Token**\n\nFrom @BotFather\n\nAuto-connect!",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, reg_w_token)

    def reg_w_token(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        token = message.text.strip()
        
        try:
            test_bot = telebot.TeleBot(token)
            bot_info = test_bot.get_me()
        except:
            msg = bot.reply_to(
                message,
                "❌ **የተሳሳተ Token!**\n\nእንደገና ይሞክሩ:" if lang == "am" else "❌ **Invalid Token!**\n\nTry again:",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, reg_w_token)
            return
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM stores WHERE token=%s", (token,))
                if cursor.fetchone():
                    msg = bot.reply_to(
                        message,
                        "❌ **ቀድሞውኑ ተመዝግቧል!**\n\nሌላ ቶከን ይጠቀሙ" if lang == "am" else "❌ **Already registered!**\n\nUse another token",
                        parse_mode="Markdown"
                    )
                    bot.register_next_step_handler(msg, reg_w_token)
                    return
        finally:
            put_conn(conn)
        
        reg_wizard_states[chat_id]["data"]["token"] = token
        reg_wizard_states[chat_id]["data"]["bot_username"] = bot_info.username
        
        data = reg_wizard_states[chat_id]["data"]
        h_pass, salt = hash_password(data["password"])
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO stores
                                  (token, store_name, admin_id, username, owner_name, owner_phone,
                                   shop_lat, shop_lng, shop_photo, category, password_hash, password_salt, is_approved)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)''',
                               (data["token"], data["store_name"], chat_id, data["bot_username"],
                                data["owner_name"], data["owner_phone"], data.get("shop_lat"),
                                data.get("shop_lng"), data.get("shop_photo", ""), data.get("category", "General"),
                                h_pass, salt))
                conn.commit()
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {e}")
            reg_wizard_states.pop(chat_id, None)
            return
        finally:
            put_conn(conn)
        
        reg_wizard_states.pop(chat_id, None)
        
        bot.send_message(
            chat_id,
            "🎉 **ሱቅዎ ተመዝግቧል!**\n\n"
            f"🏪 {data['store_name']}\n"
            f"🤖 @{data['bot_username']}\n\n"
            "✅ በራስ-ሰር ተገናኝቷል!\n"
            "⏳ ለማጽደቅ ይጠብቁ።" if lang == "am" else 
            "🎉 **Store registered!**\n\n"
            f"🏪 {data['store_name']}\n"
            f"🤖 @{data['bot_username']}\n\n"
            "✅ Auto-connected!\n"
            "⏳ Waiting for approval.",
            reply_markup=get_main_menu(),
            parse_mode="Markdown"
        )
        
        if SUPER_ADMIN_ID:
            try:
                bot.send_message(
                    SUPER_ADMIN_ID,
                    f"🔔 **አዲስ ሱቅ!**\n\n"
                    f"🏪 {data['store_name']}\n"
                    f"👤 {data['owner_name']}\n"
                    f"📱 {data['owner_phone']}\n"
                    f"🤖 @{data['bot_username']}"
                )
            except:
                pass

    # ============================================================
    # 5.10 🤖 AI ፍለጋ
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == "🤖 AI ፍለጋ")
    def ai_search_prompt(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        msg = bot.send_message(
            chat_id,
            "🔍 **ምን ይፈልጋሉ?**\n\nለምሳሌ: ልብስ፣ ጫማ፣ ሞባይል፣ ሱቅ ስም" if lang == "am" else "🔍 **What are you looking for?**\n\nExample: Fashion, Shoes, Mobile, Store name",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, ai_search_run)

    def ai_search_run(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        query = message.text.strip()
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT s.id, s.store_name, s.category, s.area_text, s.shop_photo, s.rating, s.username
                                  FROM stores s
                                  WHERE s.is_approved=1 AND s.is_active=1
                                  AND (s.store_name ILIKE %s OR s.category ILIKE %s)
                                  LIMIT 10''', (f"%{query}%", f"%{query}%"))
                stores = cursor.fetchall()
                
                cursor.execute('''SELECT p.id, p.name_am, p.name_en, p.price, p.image_url, s.store_name, s.username
                                  FROM products p JOIN stores s ON p.token = s.token
                                  WHERE s.is_approved=1 AND s.is_active=1 AND p.stock > 0
                                  AND (p.name_am ILIKE %s OR p.name_en ILIKE %s OR p.category ILIKE %s)
                                  LIMIT 10''', (f"%{query}%", f"%{query}%", f"%{query}%"))
                products = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not stores and not products:
            if ai_model:
                try:
                    bot.send_chat_action(chat_id, 'typing')
                    response = ai_model.generate_content(f"You are EthioSuq assistant. User searching for '{query}'. Suggest in {'Amharic' if lang == 'am' else 'English'}.")
                    bot.reply_to(message, f"🤖 {response.text[:500]}")
                    return
                except:
                    pass
            bot.reply_to(message, "🔍 No results found.")
            return
        
        if stores:
            text = "🏪 **Stores:**\n\n" if lang == "am" else "🏪 **Stores:**\n\n"
            for store in stores[:5]:
                store_id, name, category, area, photo, rating, username = store
                stars = "⭐" * int(rating) if rating else ""
                text += f"▪️ **{name}**\n"
                text += f"   📂 {category or 'General'}\n"
                text += f"   📍 {area or 'N/A'}\n"
                text += f"   {stars}\n"
                if username:
                    text += f"   🤖 @{username}\n"
                text += "\n"
            bot.send_message(chat_id, text, parse_mode="Markdown")
        
        if products:
            text = "📦 **Products:**\n\n" if lang == "am" else "📦 **Products:**\n\n"
            for p_id, name_am, name_en, price, image_url, store_name, username in products[:5]:
                name = name_am if lang == "am" else name_en
                text += f"▪️ **{name}**\n"
                text += f"   💰 {price} ETB\n"
                text += f"   🏪 {store_name}\n"
                if username:
                    text += f"   🤖 @{username}\n"
                text += "\n"
            bot.send_message(chat_id, text, parse_mode="Markdown")

    # ============================================================
    # 5.11 💬 እርዳታ ማእከል
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == "💬 እርዳታ ማእከል")
    def support_center(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📞 Contact Admin" if lang == "am" else "📞 Contact Admin", callback_data="support_admin"),
            types.InlineKeyboardButton("❓ FAQ" if lang == "am" else "❓ FAQ", callback_data="support_faq"),
            types.InlineKeyboardButton("📝 Report" if lang == "am" else "📝 Report", callback_data="support_report")
        )
        bot.send_message(
            chat_id,
            "💬 **Support Center**\n\nChoose an option:" if lang == "en" else "💬 **የእርዳታ ማእከል**\n\nአማራጭ ይምረጡ:",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("support_"))
    def support_actions(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        action = call.data.split("_")[1]
        
        if action == "admin":
            msg = bot.send_message(
                chat_id,
                "📞 Enter store name or username:" if lang == "en" else "📞 የሱቅ ስም ወይም የተጠቃሚ ስም ያስገቡ:",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, support_contact_admin)
        elif action == "faq":
            faq = "❓ **FAQ**\n\n1. How to open a store?\n   → Click '📝 መዝገብ ማእከል'\n\n2. How to find products?\n   → Click '🤖 AI ፍለጋ'\n\n3. How to find stores?\n   → Type store name in '🤖 AI ፍለጋ'\n\n4. How to see store location?\n   → Shows in AI search results\n\n5. How to see store photo?\n   → Shows in AI search results"
            bot.send_message(chat_id, faq, parse_mode="Markdown")
        elif action == "report":
            msg = bot.send_message(
                chat_id,
                "📝 Describe your problem:" if lang == "en" else "📝 ችግሩን ይግለጹ:",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(msg, support_report_problem)
        bot.answer_callback_query(call.id)

    def support_contact_admin(message):
        chat_id = message.chat.id
        query = message.text.strip()
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT store_name, admin_id, username FROM stores WHERE store_name ILIKE %s AND is_approved=1", (f"%{query}%",))
                store = cursor.fetchone()
        finally:
            put_conn(conn)
        
        if store:
            store_name, admin_id, username = store
            text = f"✅ **{store_name}** found!\n🤖 @{username}" if lang == "en" else f"✅ **{store_name}** ተገኝቷል!\n🤖 @{username}"
            if admin_id:
                try:
                    bot.send_message(admin_id, f"📞 Support request from {chat_id}\nStore: {store_name}")
                except:
                    pass
            bot.send_message(chat_id, text + "\n\n📞 Admin notified!", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "❌ Store not found. Try again." if lang == "en" else "❌ ሱቅ አልተገኘም። እንደገና ይሞክሩ።")

    def support_report_problem(message):
        chat_id = message.chat.id
        problem = message.text.strip()
        lang = get_user_lang(chat_id)
        
        if SUPER_ADMIN_ID:
            try:
                bot.send_message(SUPER_ADMIN_ID, f"📝 **Problem Report**\n\nFrom: {chat_id}\n\n{problem}")
            except:
                pass
        
        bot.send_message(chat_id, "✅ Report submitted! Admin will review." if lang == "en" else "✅ ሪፖርትዎ ተልኳል! አስተዳዳሪ ይመለከተዋል።")

    # ============================================================
    # 5.12 FALLBACK
    # ============================================================
    @bot.message_handler(func=lambda message: True)
    def fallback_handler(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        if ai_model:
            try:
                bot.send_chat_action(chat_id, 'typing')
                response = ai_model.generate_content(f"You are EthioSuq assistant. Answer in {'Amharic' if lang == 'am' else 'English'}: {message.text}")
                bot.reply_to(message, f"🤖 {response.text[:500]}")
                return
            except:
                pass
        
        bot.reply_to(
            message,
            "📌 Please use the menu buttons below:" if lang == "en" else "📌 እባክዎ ከታች ካሉት አማራጮች ይምረጡ:",
            reply_markup=get_main_menu()
        )

    # ============================================================
    # 5.13 START BOT
    # ============================================================
    def _run_bot():
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                print(f"⚠️ EthioSuq bot crashed: {e}. Restarting in 5s...")
                time.sleep(5)

    threading.Thread(target=_run_bot, name="EthioSuqBot", daemon=True).start()
    print("✅ EthioSuq Bot is running!")

else:
    print("⚠️ CONTROL_BOT_TOKEN not set!")

# ============================================================
# 6. MAIN LOOP
# ============================================================
while True:
    time.sleep(3600)
