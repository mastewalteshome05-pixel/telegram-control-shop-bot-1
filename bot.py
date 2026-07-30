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
# 3. POSTGRESQL (persistent, thread-safe, auto-reconnect)
# ============================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL environment variable is missing!")

db_pool_lock = threading.Lock()

try:
    db_pool = ThreadedConnectionPool(1, 20, dsn=DATABASE_URL)
    print("✅ PostgreSQL Connection Pool initialized (ThreadedConnectionPool).")
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
            print("🔄 Re-initializing connection pool due to disconnect...")
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
            cursor.execute('''CREATE TABLE IF NOT EXISTS stores (
                                id SERIAL,
                                token TEXT PRIMARY KEY,
                                store_name TEXT,
                                admin_id BIGINT,
                                password_hash TEXT,
                                password_salt TEXT,
                                telebirr TEXT,
                                is_active INTEGER DEFAULT 1)''')

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
                                total_price REAL)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS user_langs (
                                chat_id BIGINT PRIMARY KEY,
                                lang TEXT)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS customer_info (
                                chat_id BIGINT PRIMARY KEY,
                                phone TEXT,
                                lat REAL,
                                lng REAL)''')

            cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS shop_lat REAL")
            cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS shop_lng REAL")
            cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS area_text TEXT")
            cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS shop_photo TEXT")
            cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS shop_description TEXT")
            cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS cbebirr TEXT")

            cursor.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS delivery_fee REAL DEFAULT 0")
            cursor.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS status_stage INTEGER DEFAULT 0")

            # New tables for search engine
            cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
                                id SERIAL PRIMARY KEY,
                                token TEXT,
                                name_am TEXT,
                                name_en TEXT,
                                icon TEXT)''')
            
            cursor.execute('''CREATE TABLE IF NOT EXISTS product_categories (
                                product_id INTEGER,
                                category_id INTEGER,
                                PRIMARY KEY (product_id, category_id))''')
            
            cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS category_id INTEGER")
            cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS location_text TEXT")
            
            conn.commit()
    finally:
        put_conn(conn)

init_db()

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
# 4. LOCALIZATION
# ============================================================
STRINGS = {
    "am": {
        "welcome": "እንኳን ወደ AI የሽያጭ ረዳት ቦት በደህና መጡ! 👋",
        "shop": "🛍️ ምርቶችን እይ",
        "cart": "🛒 የእኔ ጋሪ",
        "track": "📦 ትዕዛዝ መከታተያ",
        "faq": "❓ መረጃ (FAQ)",
        "search": "🔍 ፍለጋ/Search",
        "empty": "🛒 ጋሪዎ በአሁኑ ሰዓት ባዶ ነው።",
        "added": "ወደ ጋሪ ተጨምሯል! 🛒",
        "total": "አጠቃላይ ድምር",
        "price_label": "ዋጋ",
        "checkout_btn": "💳 ሂሳብ ማጠቃለያ",
        "clear_btn": "🗑️ ጋሪ አጽዳ",
        "enter_id": "🔢 እባክዎ የትዕዛዝ ቁጥርዎን (Order ID) ያስገቡ፦",
        "not_found": "❌ የትዕዛዝ ቁጥሩ አልተገኘም ወይም የዚህ ሱቅ አይደለም።",
        "invalid_id": "❌ የተሳሳተ ቁጥር ገብቷል።",
        "approved_msg": "🎉 ደስ የሚል ዜና! የትዕዛዝ ቁጥርዎ ክፍያ ተረጋግጦ ዕቃው እየመጣላችሁ ነው። 🛵",
        "rejected_msg": "❌ የትዕዛዝ ቁጥርዎ ክፍያ ማረጋገጫ ውድቅ ተደርጓል። እባክዎ ባለቤቱን ያነጋግሩ።",
        "receipt_prompt": "እባክዎ የከፈሉበትን የቴሌብር ደረሰኝ (Screenshot ፎቶ) እዚህ ላይ ይላኩ። 📸",
        "faq_text": "ℹ️ **ስለ ሱቃችን መረጃ**\n\n📍 አድራሻችን፦ አዲስ አበባ፣ ኢትዮጵያ\n📞 ስልክ፦ 0911223344\n⏱️ የስራ ሰዓት፦ ከሰኞ - ቅዳሜ (2:00 ሰዓት - 12:00 ሰዓት)\n\nማንኛውንም ጥያቄ እዚህ በመጻፍ AI ረዳታችንን መጠየቅ ይችላሉ!"
    },
    "en": {
        "welcome": "Welcome to AI Customer Service Bot! 👋",
        "shop": "🛍️ Shop Products",
        "cart": "🛒 My Cart",
        "track": "📦 Track Order",
        "faq": "❓ FAQ Info",
        "search": "🔍 Search",
        "empty": "🛒 Your cart is currently empty.",
        "added": "Added to cart! 🛒",
        "total": "Total",
        "price_label": "Price",
        "checkout_btn": "💳 Checkout",
        "clear_btn": "🗑️ Clear Cart",
        "enter_id": "🔢 Please enter your Order ID:",
        "not_found": "❌ Order ID not found or invalid for this store.",
        "invalid_id": "❌ Invalid ID entered.",
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
    markup.add(types.KeyboardButton(ln["shop"]), types.KeyboardButton(ln["cart"]))
    markup.add(types.KeyboardButton(ln["search"]), types.KeyboardButton(ln["track"]))
    markup.add(types.KeyboardButton(ln["faq"]))
    return markup

def get_admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton(ADMIN_BTN["add_product"]), types.KeyboardButton(ADMIN_BTN["my_products"]))
    markup.add(types.KeyboardButton(ADMIN_BTN["orders"]), types.KeyboardButton(ADMIN_BTN["payment"]))
    markup.add(types.KeyboardButton(ADMIN_BTN["stats"]), types.KeyboardButton(ADMIN_BTN["profile"]))
    markup.add(types.KeyboardButton(ADMIN_BTN["changepass"]), types.KeyboardButton(ADMIN_BTN["logout"]))
    return markup

# ============================================================
# 5. SHOP BOT ENGINE
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
                                  cbebirr, area_text, shop_photo, shop_description, shop_lat, shop_lng
                                  FROM stores WHERE token=%s''', (token,))
                row = cursor.fetchone()
        finally:
            put_conn(conn)
        if row:
            return {
                "store_name": row[0], "admin_id": row[1], "telebirr": row[2], "is_active": row[3],
                "pass_hash": row[4], "salt": row[5], "cbebirr": row[6], "area_text": row[7],
                "shop_photo": row[8], "shop_description": row[9], "shop_lat": row[10], "shop_lng": row[11]
            }
        return None

    def check_active_middleware(chat_id):
        store = get_store_info()
        if not store:
            bot.send_message(chat_id, "🏪 ይህ ሱቅ ገና አልተመዘገበም።")
            return False
        if not store["is_active"]:
            bot.send_message(chat_id, "❌ ይህ ሱቅ ንቁ አይደለም (Subscription Expired)። እባክዎ ባለቤቱን ያነጋግሩ።")
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

    # ============================================================
    # 5.1 SEARCH ENGINE
    # ============================================================
    class ProductSearchEngine:
        def __init__(self, token):
            self.token = token
        
        def search(self, query=None, min_price=None, max_price=None, category=None, location=None, lat=None, lng=None):
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    sql = """SELECT p.id, p.name_am, p.name_en, p.price, p.stock, p.desc_am, p.desc_en, p.image_url,
                                    c.name_am as category_am, c.name_en as category_en,
                                    s.store_name, s.shop_lat, s.shop_lng, s.area_text
                             FROM products p
                             LEFT JOIN categories c ON p.category_id = c.id
                             LEFT JOIN stores s ON p.token = s.token
                             WHERE p.token = %s AND p.stock > 0"""
                    params = [self.token]
                    
                    if query:
                        words = query.strip().split()
                        name_conditions = []
                        for word in words:
                            if len(word) > 2:
                                name_conditions.append("(p.name_am ILIKE %s OR p.name_en ILIKE %s)")
                                params.extend([f"%{word}%", f"%{word}%"])
                        if name_conditions:
                            sql += " AND (" + " OR ".join(name_conditions) + ")"
                    
                    if min_price is not None:
                        sql += " AND p.price >= %s"
                        params.append(float(min_price))
                    if max_price is not None:
                        sql += " AND p.price <= %s"
                        params.append(float(max_price))
                    
                    if category:
                        sql += " AND (c.name_am ILIKE %s OR c.name_en ILIKE %s)"
                        params.extend([f"%{category}%", f"%{category}%"])
                    
                    if location and lat and lng:
                        sql += """ AND (
                            (s.shop_lat IS NOT NULL AND s.shop_lng IS NOT NULL AND 
                             (6371 * acos(cos(radians(%s)) * cos(radians(s.shop_lat)) * 
                              cos(radians(s.shop_lng) - radians(%s)) + sin(radians(%s)) * 
                              sin(radians(s.shop_lat)))) < 10)
                            OR s.area_text ILIKE %s
                        )"""
                        params.extend([lat, lng, lat, f"%{location}%"])
                    
                    sql += " ORDER BY p.price ASC LIMIT 20"
                    cursor.execute(sql, params)
                    return cursor.fetchall()
            finally:
                put_conn(conn)
        
        def search_by_ai(self, natural_query, lang='am'):
            if ai_model is None:
                return None
            
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""SELECT p.id, p.name_am, p.name_en, p.price, p.stock, p.desc_am, p.desc_en,
                                             c.name_am as category_am, c.name_en as category_en
                                      FROM products p
                                      LEFT JOIN categories c ON p.category_id = c.id
                                      WHERE p.token = %s AND p.stock > 0""", (self.token,))
                    products = cursor.fetchall()
                    
                    if not products:
                        return []
                    
                    product_list = []
                    for p in products:
                        name = p[1] if lang == 'am' else p[2]
                        price = p[3]
                        desc = p[5] if lang == 'am' else p[6]
                        cat = p[7] if lang == 'am' else p[8]
                        product_list.append(f"- ID:{p[0]}, Name:{name}, Price:{price} ETB, Category:{cat}, Desc:{desc}")
                    
                    product_text = "\n".join(product_list)
                    
                    prompt = f"""You are a smart product search assistant. 
                    Analyze the user's query and find the best matching products from this list.
                    Return ONLY the product IDs that match, separated by commas.
                    If no products match, return "NONE".
                    
                    Available products:
                    {product_text}
                    
                    User query: {natural_query}
                    """
                    
                    response = ai_model.generate_content(prompt)
                    result = response.text.strip()
                    
                    if result == "NONE" or not result:
                        return []
                    
                    ids = re.findall(r'\d+', result)
                    if not ids:
                        return []
                    
                    placeholders = ','.join(['%s'] * len(ids))
                    cursor.execute(f"""SELECT p.id, p.name_am, p.name_en, p.price, p.stock, p.desc_am, p.desc_en, p.image_url,
                                               c.name_am as category_am, c.name_en as category_en
                                        FROM products p
                                        LEFT JOIN categories c ON p.category_id = c.id
                                        WHERE p.token = %s AND p.id IN ({placeholders})""", 
                                   [self.token] + ids)
                    return cursor.fetchall()
            finally:
                put_conn(conn)

    def display_search_results(chat_id, lang, results, title):
        if not results:
            bot.send_message(chat_id, "🔍 ምንም ውጤት አልተገኘም / No results found.")
            return
        
        if len(results) > 10:
            bot.send_message(chat_id, f"📊 {len(results)} ምርቶች ተገኝተዋል! የመጀመሪያዎቹ 10 እዚህ አሉ:")
            results = results[:10]
        
        for row in results:
            p_id, name_am, name_en, price, stock, desc_am, desc_en, image_url, cat_am, cat_en = row[:10]
            name = name_am if lang == 'am' else name_en
            desc = desc_am if lang == 'am' else desc_en
            category = cat_am if lang == 'am' else cat_en
            
            stock_status = "✅ ይገኛል" if (stock or 0) > 0 else "❌ ተሟጧል"
            
            text = f"📦 **{name}**\n"
            text += f"💰 {STRINGS[lang]['price_label']}: {price} ETB\n"
            text += f"📌 ሁኔታ: {stock_status}\n"
            if category:
                text += f"🏷️ ምድብ: {category}\n"
            if desc:
                text += f"📝 {desc[:100]}...\n"
            text += f"🆔 #{p_id}"
            
            markup = types.InlineKeyboardMarkup()
            if (stock or 0) > 0:
                btn_text = "🛒 ወደ ጋሪ ጨምር" if lang == 'am' else "🛒 Add to Cart"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"shopadd_{p_id}"))
            
            try:
                if image_url:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                else:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    # ============================================================
    # 5.2 BOT HANDLERS
    # ============================================================
    
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

    @bot.message_handler(commands=['login'])
    def login_store(message):
        chat_id = message.chat.id
        store = get_store_info()
        if not store:
            bot.reply_to(message, "❌ ይህ ሱቅ ገና አልተመዘገበም። ባለቤቱ Control Bot ላይ `/connect` ማድረግ አለበት።")
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
            bot.reply_to(message, "🔓 በስኬት ገብተዋል! የ 2 ሰዓት ሴሽን ተጀምሯል።\n\nከታች ያሉትን የአስተዳደር አማራጮች ይጠቀሙ 👇", reply_markup=get_admin_menu())
        else:
            attempt["count"] += 1
            if attempt["count"] >= 5:
                attempt["lockout_until"] = time.time() + 900
                bot.reply_to(message, "❌ 5 ጊዜ ተሳስተዋል። ለ15 ደቂቃ ታግደዋል።")
            else:
                left = 5 - attempt["count"]
                bot.reply_to(message, f"❌ የተሳሳተ የይለፍ ቃል! {left} ሙከራዎች ቀርተውዎታል።")

    def do_logout(chat_id):
        session_key = (token, chat_id)
        if session_key in active_sessions:
            del active_sessions[session_key]
        lang = get_user_lang(chat_id)
        bot.send_message(chat_id, "🔒 ከአስተዳደር ወጥተዋል።", reply_markup=get_main_menu(lang))

    @bot.message_handler(commands=['logout'])
    def logout_store_cmd(message):
        do_logout(message.chat.id)

    @bot.message_handler(func=lambda m: m.text in ADMIN_BTN.values())
    def admin_menu_router(message):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            bot.reply_to(message, "❌ ይህ መብት የሚፈቀደው በ `/login` ለገቡ አድሚኖች ብቻ ነው።")
            return

        text = message.text
        if text == ADMIN_BTN["add_product"]:
            bot.reply_to(message, "📝 እባክዎ የምርቱን መረጃ በዚህ ፎርማት ይጻፉ፦\n`[የአማርኛ ስም],[የእንግሊዝኛ ስም],[ዋጋ],[ብዛት],[አማርኛ መግለጫ],[እንግሊዝኛ መግለጫ]`\n\n*ምሳሌ፦*\n`የወንድ ጫማ,Men Shoe,2500,10,የቆዳ ጫማ,Leather shoe`", parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": "WAITING_PRODUCT_DETAILS", "data": {}}
        elif text == ADMIN_BTN["my_products"]:
            show_my_products(chat_id)
        elif text == ADMIN_BTN["orders"]:
            show_pending_orders(chat_id)
        elif text == ADMIN_BTN["payment"]:
            bot.reply_to(message, "💰 እባክዎ **የቴሌብር እና CBE Birr ቁጥርዎን** በኮማ (,) ለይተው ይላኩ፦\n\n*ምሳሌ፦* `0911223344,1000123456789`\n\n(CBE Birr ከሌለዎት 'የለም' ብለው ይላኩ)", parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": "WAITING_PAYMENT_NUMBER", "data": {}}
        elif text == ADMIN_BTN["stats"]:
            show_stats(chat_id)
        elif text == ADMIN_BTN["profile"]:
            loc_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            loc_markup.add(types.KeyboardButton("📍 የሱቅ አካባቢ አጋራ", request_location=True))
            bot.send_message(chat_id, "🏪 **የሱቅ መገለጫ ማዘጋጀት**\n\nደረጃ 1/4: እባክዎ የሱቅዎን አካባቢ (Location) ያጋሩ 👇", reply_markup=loc_markup, parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": "WAITING_SHOP_LOCATION", "data": {}}
        elif text == ADMIN_BTN["changepass"]:
            bot.reply_to(message, "🔑 እባክዎ **አዲሱን የይለፍ ቃል** ይላኩ (ቢያንስ 8 ፊደል/ቁጥር መሆን አለበት)፦", parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": "WAITING_NEW_PASSWORD", "data": {}}
        elif text == ADMIN_BTN["logout"]:
            do_logout(chat_id)

    def show_my_products(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name_am, price, stock FROM products WHERE token=%s ORDER BY id", (token,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)

        if not rows:
            bot.send_message(chat_id, "📋 ገና ምንም ምርት አልጨመሩም። '➕ ምርት ጨምር' ይጠቀሙ።")
            return

        for p_id, name_am, price, stock in rows:
            text = f"📦 **#{p_id} {name_am}**\n💰 {price} ETB | 📦 ብዛት፦ {stock}"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✏️ አርትዕ (ዋጋ/ብዛት)", callback_data=f"editproduct_{p_id}"),
                types.InlineKeyboardButton("🗑️ ሰርዝ", callback_data=f"deleteproduct_{p_id}")
            )
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
            bot.send_message(chat_id, "📋 በአሁኑ ሰዓት ያልተጠናቀቁ ትዕዛዞች የሉም።")
            return

        for order_id, cust_id, total, stage in rows:
            stage = stage or 0
            status_label = ORDER_STAGES_AM[stage] if 0 <= stage <= 3 else "🟡 Pending"
            text = f"🆔 **ትዕዛዝ #{order_id}**\n💵 {total} ETB\n📌 ሁኔታ፦ {status_label}"
            markup = types.InlineKeyboardMarkup()
            if stage == 0:
                markup.add(
                    types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                    types.InlineKeyboardButton("❌ አትቀበል", callback_data=f"rejectorder_{order_id}")
                )
            elif stage == 1:
                markup.add(types.InlineKeyboardButton("🚚 On the way ብዬ ላድርገው", callback_data=f"advance_{order_id}"))
            elif stage == 2:
                markup.add(types.InlineKeyboardButton("✅ Delivered ብዬ ላድርገው", callback_data=f"advance_{order_id}"))
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

        text = (
            f"📊 **የሱቅ ስታትስቲክስ**\n\n"
            f"📦 ጠቅላላ ምርት፦ {product_count}\n"
            f"🧾 ጠቅላላ ትዕዛዝ፦ {total_orders}\n"
            f"✅ የተከፈለ ትዕዛዝ፦ {paid_count}\n"
            f"💵 ጠቅላላ ገቢ፦ {revenue} ETB"
        )
        bot.send_message(chat_id, text, parse_mode="Markdown")

    # ============================================================
    # 5.3 SEARCH HANDLERS
    # ============================================================
    
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["search"])
    def search_menu(message):
        chat_id = message.chat.id
        if not check_active_middleware(chat_id):
            return
        lang = get_user_lang(chat_id)
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📝 በስም ፈልግ", callback_data="search_name"),
            types.InlineKeyboardButton("💰 በዋጋ አጣራ", callback_data="search_price"),
            types.InlineKeyboardButton("🏷️ በምድብ ፈልግ", callback_data="search_category"),
            types.InlineKeyboardButton("📍 በአካባቢ ፈልግ", callback_data="search_location"),
            types.InlineKeyboardButton("🤖 AI ፍለጋ", callback_data="search_ai")
        )
        bot.send_message(chat_id, "🔍 **የፍለጋ አማራጮች / Search Options**", reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("search_"))
    def handle_search_options(call):
        chat_id = call.message.chat.id
        if not check_active_middleware(chat_id):
            return
        lang = get_user_lang(chat_id)
        
        if call.data == "search_name":
            msg = bot.send_message(chat_id, "📝 **የምርት ስም ያስገቡ:**" if lang == 'am' else "📝 **Enter product name:**")
            bot.register_next_step_handler(msg, process_search_by_name)
        
        elif call.data == "search_price":
            msg = bot.send_message(chat_id, "💰 **በኮማ የሚለይ ዝቅተኛ እና ከፍተኛ ዋጋ ያስገቡ (ለም: 100,500):**" if lang == 'am' else "💰 **Enter min and max price separated by comma (e.g., 100,500):**")
            bot.register_next_step_handler(msg, process_search_by_price)
        
        elif call.data == "search_category":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT name_am, name_en FROM categories WHERE token=%s", (token,))
                    categories = cursor.fetchall()
            finally:
                put_conn(conn)
            
            if categories:
                cat_text = "🏷️ **ያሉ ምድቦች:**\n" if lang == 'am' else "🏷️ **Available Categories:**\n"
                for cat_am, cat_en in categories:
                    cat_text += f"• {cat_am} / {cat_en}\n"
                cat_text += "\n" + ("የምድብ ስም ያስገቡ:" if lang == 'am' else "Enter category name:")
                msg = bot.send_message(chat_id, cat_text, parse_mode="Markdown")
                bot.register_next_step_handler(msg, process_search_by_category)
            else:
                bot.send_message(chat_id, "❌ ምንም ምድቦች የሉም / No categories available.")
        
        elif call.data == "search_location":
            loc_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            loc_markup.add(types.KeyboardButton("📍 አካባቢዬን አጋራ", request_location=True))
            bot.send_message(chat_id, "📍 **እባክዎ አካባቢዎን ያጋሩ ወይም የከተማ ስም ያስገቡ:**", reply_markup=loc_markup, parse_mode="Markdown")
        
        elif call.data == "search_ai":
            msg = bot.send_message(chat_id, "🤖 **የሚፈልጉትን በተፈጥሮ ቋንቋ ይጻፉ (ለም: '10,000 ብር በታች ያለ ስልክ አሳየኝ'):**" if lang == 'am' else "🤖 **Describe what you want in natural language (e.g., 'Show me phones under 10,000 ETB'):**")
            bot.register_next_step_handler(msg, process_search_by_ai)

    def process_search_by_name(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        search_query = message.text.strip()
        
        if not search_query:
            bot.send_message(chat_id, "❌ እባክዎ የምርት ስም ያስገቡ / Please enter a product name.")
            return
        
        search_engine = ProductSearchEngine(token)
        results = search_engine.search(query=search_query)
        display_search_results(chat_id, lang, results, f"📝 **{search_query}**")

    def process_search_by_price(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        try:
            parts = message.text.strip().split(',')
            min_price = float(parts[0].strip())
            max_price = float(parts[1].strip()) if len(parts) > 1 else None
        except:
            bot.send_message(chat_id, "❌ የተሳሳተ ፎርማት! እባክዎ እንደ '100,500' ባለ ፎርማት ይላኩ.")
            return
        
        search_engine = ProductSearchEngine(token)
        results = search_engine.search(min_price=min_price, max_price=max_price)
        display_search_results(chat_id, lang, results, f"💰 **ዋጋ: {min_price} - {max_price if max_price else '∞'} ETB**")

    def process_search_by_category(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        category = message.text.strip()
        
        if not category:
            bot.send_message(chat_id, "❌ እባክዎ የምድብ ስም ያስገቡ / Please enter a category name.")
            return
        
        search_engine = ProductSearchEngine(token)
        results = search_engine.search(category=category)
        display_search_results(chat_id, lang, results, f"🏷️ **{category}**")

    def process_search_by_location(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        if message.location:
            lat = message.location.latitude
            lng = message.location.longitude
            search_engine = ProductSearchEngine(token)
            results = search_engine.search(location="", lat=lat, lng=lng)
            display_search_results(chat_id, lang, results, "📍 **በአቅራቢያ / Nearby**")
        else:
            location = message.text.strip()
            if not location:
                bot.send_message(chat_id, "❌ እባክዎ የከተማ ስም ያስገቡ / Please enter a city name.")
                return
            search_engine = ProductSearchEngine(token)
            results = search_engine.search(location=location)
            display_search_results(chat_id, lang, results, f"📍 **{location}**")

    def process_search_by_ai(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        query = message.text.strip()
        
        if not query:
            bot.send_message(chat_id, "❌ እባክዎ ጥያቄ ያስገቡ / Please enter a query.")
            return
        
        if ai_model is None:
            bot.send_message(chat_id, "❌ AI በአሁኑ ሰዓት አይገኝም / AI not available.")
            return
        
        bot.send_chat_action(chat_id, 'typing')
        search_engine = ProductSearchEngine(token)
        
        try:
            results = search_engine.search_by_ai(query, lang)
            if results:
                display_search_results(chat_id, lang, results, f"🤖 **AI ምክር / AI Suggestion**\n💬 **{query}**")
            else:
                bot.send_message(chat_id, "🔍 ለጥያቄዎ የሚስማሙ ምርቶች አልተገኙም / No matching products found.")
        except Exception as e:
            print(f"AI search error: {e}")
            bot.send_message(chat_id, "❌ AI በመፈለግ ላይ ስህተት ተከስቷል / AI search error.")

    # ============================================================
    # 5.4 CUSTOMER HANDLERS
    # ============================================================
    
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
            bot.send_message(chat_id, "🛍️ ምንም ምርት የለም።" if lang == "am" else "🛍️ No products available.")
            return

        for row in rows:
            p_id, name_am, name_en, price, stock, desc_am, desc_en, image_url = row
            stock = stock or 0
            name = name_am if lang == "am" else name_en
            desc = desc_am if lang == "am" else desc_en
            status = "✅ In Stock" if stock > 0 else "❌ Out of Stock"
            text = f"📦 **{name}**\n💰 {STRINGS[lang]['price_label']}: {price} ETB\n📌 Status: {status}\n📝 {desc}"

            markup = types.InlineKeyboardMarkup()
            if stock > 0:
                btn_text = "🛒 ወደ ጋሪ ጨምር" if lang == "am" else "🛒 Add to Cart"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"shopadd_{p_id}"))

            sent = False
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                    sent = True
                except:
                    pass

            if not sent:
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

        if not prod:
            bot.answer_callback_query(call.id, "❌ Error: Product mismatch.")
            return

        available = prod[0] or 0
        cart_key = (token, chat_id)
        if cart_key not in user_carts:
            user_carts[cart_key] = {}
        current_qty = user_carts[cart_key].get(p_id, 0)

        if current_qty + 1 > available:
            bot.answer_callback_query(call.id, "❌ በቂ ክምችት የለም / Not enough stock.", show_alert=True)
            return

        user_carts[cart_key][p_id] = current_qty + 1
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
        text = "🛒 **Your Cart / የእርስዎ ጋሪ፦**\n\n"

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

    def finalize_checkout(chat_id, lang, edit_call=None):
        cart_key = (token, chat_id)
        cart = user_carts.get(cart_key, {})
        if not cart:
            return
        store = get_store_info()
        if not store:
            bot.send_message(chat_id, "🏪 ይህ ሱቅ አልተገኘም። እባክዎ ቆይተው ይሞክሩ።")
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
                    bot.send_message(chat_id, "❌ ካርትዎ ውስጥ ያሉት ምርቶች አሁን የሉም (Out of stock)።")
                    user_carts[cart_key] = {}
                    return

                delivery_fee = 0
                distance_note = ""
                if store.get("shop_lat") and store.get("shop_lng") and cust_info and cust_info.get("lat") and cust_info.get("lng"):
                    dist_km = calculate_distance_km(store["shop_lat"], store["shop_lng"], cust_info["lat"], cust_info["lng"])
                    delivery_fee = calculate_delivery_fee(dist_km)
                    distance_note = f"📏 ርቀት፦ {dist_km:.1f} ኪ.ሜ\n🚚 የማድረሻ ዋጋ፦ {delivery_fee} ETB\n"

                grand_total = items_total + delivery_fee

                cursor.execute('''INSERT INTO orders (token, customer_id, status_am, status_en, total_price, delivery_fee, status_stage)
                                  VALUES (%s, %s, %s, %s, %s, %s, 0) RETURNING id''',
                               (token, chat_id, ORDER_STAGES_AM[0], ORDER_STAGES_EN[0], items_total, delivery_fee))
                order_id = cursor.fetchone()[0]

                cursor.execute("CREATE TABLE IF NOT EXISTS order_items (id SERIAL PRIMARY KEY, order_id INTEGER, product_id INTEGER, qty INTEGER, price REAL)")
                
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

        pay_text = (
            f"🆔 **Order ID፦** `{order_id}`\n\n"
            f"💵 የእቃ ድምር፦ {items_total} ETB\n"
            f"{distance_note}"
            f"💰 **አጠቃላይ የሚከፈል፦ {grand_total} ETB**\n\n"
            f"{pay_methods}\n\n{STRINGS[lang]['receipt_prompt']}"
        )

        if edit_call:
            try:
                bot.edit_message_text(pay_text, chat_id, edit_call.message.message_id, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, pay_text, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, pay_text, parse_mode="Markdown", reply_markup=get_main_menu(lang))

        admin_states[(token, chat_id)] = {"state": f"AWAITING_RECEIPT_{order_id}", "data": {}}

    @bot.callback_query_handler(func=lambda call: call.data in ["shop_checkout", "shop_clear"])
    def cart_actions(call):
        chat_id = call.message.chat.id
        if not check_active_middleware(chat_id):
            return
        lang = get_user_lang(chat_id)
        cart_key = (token, chat_id)

        if call.data == "shop_clear":
            user_carts[cart_key] = {}
            bot.edit_message_text("🛒 Cart cleared / ጋሪው ጸድቷል!", chat_id, call.message.message_id)
        elif call.data == "shop_checkout":
            cart = user_carts.get(cart_key, {})
            if not cart:
                return

            cust_info = get_customer_info(chat_id)
            has_phone = cust_info and cust_info.get("phone")
            has_location = cust_info and cust_info.get("lat") and cust_info.get("lng")

            if has_phone and has_location:
                finalize_checkout(chat_id, lang, edit_call=call)
            else:
                gate_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                if not has_phone:
                    gate_markup.add(types.KeyboardButton("📱 ስልክ ቁጥሬን አጋራ", request_contact=True))
                if not has_location:
                    gate_markup.add(types.KeyboardButton("📍 አካባቢዬን አጋራ", request_location=True))
                bot.send_message(
                    chat_id,
                    "🚚 ትዕዛዝ ከመፈጸማችን በፊት፣ **ለማድረሻ አገልግሎት** ስልክ ቁጥርዎን እና አካባቢዎን ማጋራት ያስፈልጋል 👇",
                    reply_markup=gate_markup, parse_mode="Markdown"
                )
                admin_states[(token, chat_id)] = {"state": "PENDING_CHECKOUT", "data": {}}

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
                loc_markup.add(types.KeyboardButton("📍 አካባቢዬን አጋራ", request_location=True))
                bot.send_message(chat_id, "✅ ስልክ ቁጥር ተቀብለናል። አሁን አካባቢዎን ያጋሩ 👇", reply_markup=loc_markup)

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
            bot.send_message(chat_id, "✅ አካባቢ ተቀምጧል።\n\nደረጃ 2/4: እባክዎ የሱቅዎን አካባቢ ስም (ለምሳሌ 'ቦሌ፣ አዲስ አበባ') በጽሁፍ ይላኩ፦")
            admin_states[session_key] = {"state": "WAITING_SHOP_AREA", "data": {}}
            return
        
        # Also handle location for search
        if state == "" or state == "PENDING_CHECKOUT":
            save_customer_location(chat_id, message.location.latitude, message.location.longitude)
            
            if state == "PENDING_CHECKOUT":
                cust_info = get_customer_info(chat_id)
                if cust_info and cust_info.get("phone"):
                    lang = get_user_lang(chat_id)
                    finalize_checkout(chat_id, lang)
                else:
                    phone_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                    phone_markup.add(types.KeyboardButton("📱 ስልክ ቁጥሬን አጋራ", request_contact=True))
                    bot.send_message(chat_id, "✅ አካባቢ ተቀብለናል። አሁን ስልክ ቁጥርዎን ያጋሩ 👇", reply_markup=phone_markup)
            else:
                # User shared location from search menu
                lang = get_user_lang(chat_id)
                search_engine = ProductSearchEngine(token)
                results = search_engine.search(location="", lat=message.location.latitude, lng=message.location.longitude)
                display_search_results(chat_id, lang, results, "📍 **በአቅራቢያ / Nearby**")

    # Shop profile wizard - step 2/4
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
        bot.reply_to(message, "✅ ተቀምጧል።\n\nደረጃ 3/4: እባክዎ የሱቅዎን ፎቶ (ለምሳሌ የሱቅዎ/ምርትዎ ፎቶ) ይላኩ፦")
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
        bot.reply_to(message, "🎉 የሱቅ መገለጫዎ ሙሉ በሙሉ ተጠናቅቋል!")
        admin_states[(token, chat_id)] = {"state": "", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_NEW_PASSWORD")
    def process_new_password(message):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            return
        new_pass = message.text.strip()
        if len(new_pass) < 8:
            bot.reply_to(message, "❌ የይለፍ ቃል ቢያንስ **8 ፊደል/ቁጥር** መያዝ አለበት። እባክዎ ሌላ ይላኩ፦", parse_mode="Markdown")
            return
        h_pass, salt = hash_password(new_pass)
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET password_hash=%s, password_salt=%s WHERE token=%s", (h_pass, salt, token))
                conn.commit()
        finally:
            put_conn(conn)
        bot.reply_to(message, "✅ የይለፍ ቃልዎ በስኬት ተቀይሯል!")
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
            markup.add(
                types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                types.InlineKeyboardButton("❌ አትቀበል", callback_data=f"rejectorder_{order_id}")
            )
            phone_line = f"\n📞 ስልክ፦ `{cust_info['phone']}`" if cust_info and cust_info.get('phone') else ""
            bot.send_message(admin_id, f"🔔 **አዲስ የክፍያ ደረሰኝ ለትዕዛዝ ቁጥር #{order_id}!**{phone_line}", reply_markup=markup, parse_mode="Markdown")
            if cust_info and cust_info.get("lat") and cust_info.get("lng"):
                bot.send_location(admin_id, cust_info["lat"], cust_info["lng"])
            bot.forward_message(admin_id, chat_id, message.message_id)

            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s WHERE id=%s AND token=%s",
                                   ("ክፍያ ተልኳል (በማረጋገጥ ላይ)", "Payment sent (Verifying)", order_id, token))
                    conn.commit()
            finally:
                put_conn(conn)

            bot.reply_to(message, "✅ የክፍያ ማረጋገጫ ፎቶዎ ተልኳል።")
            admin_states[session_key] = {"state": "", "data": {}}

        elif state == "WAITING_SHOP_PHOTO":
            if not is_verified_admin(chat_id):
                bot.reply_to(message, "❌ የአድሚን ሴሽንዎ አልቋል። እባክዎ ዳግም ይግቡ።")
                return
            photo_id = message.photo[-1].file_id
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET shop_photo=%s WHERE token=%s", (photo_id, token))
                    conn.commit()
            finally:
                put_conn(conn)
            bot.reply_to(message, "✅ ተቀምጧል።\n\nደረጃ 4/4: እባክዎ ስለ ሱቅዎ አጭር መግለጫ ይጻፉ (ለምሳሌ 'ጥራት ያለው የወንድ/ሴት ልብስ በተመጣጣኝ ዋጋ')፦")
            admin_states[session_key] = {"state": "WAITING_SHOP_DESC", "data": {}}

        elif state == "WAITING_PRODUCT_PHOTO":
            if not is_verified_admin(chat_id):
                bot.reply_to(message, "❌ የአድሚን ሴሽንዎ አልቋል። እባክዎ ዳግም ይግቡ።")
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
            bot.reply_to(message, f"🎉 ምርቱ '{p_data['name_am']}' በስኬት ተጨምሯል!")
            admin_states[session_key] = {"state": "", "data": {}}
        else:
            bot.reply_to(message, "📸 ፎቶ ስለላኩልን እናመሰግናለን!")

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
            product_data = {
                "name_am": parts[0].strip(),
                "name_en": parts[1].strip(),
                "price": float(parts[2].strip()),
                "stock": int(parts[3].strip()),
                "desc_am": parts[4].strip(),
                "desc_en": parts[5].strip()
            }
            bot.reply_to(message, "📸 አሁን ደግሞ የምርቱን ፎቶ ይላኩ። ፎቶ ከሌለ 'none' ይበሉ፦")
            admin_states[session_key] = {"state": "WAITING_PRODUCT_PHOTO", "data": product_data}
        except (IndexError, ValueError):
            bot.reply_to(message, "❌ ፎርማት ስህተት አለው። በኮማ (,) በመለየት ይሞክሩ።")
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
        bot.reply_to(message, f"🎉 ምርቱ '{p_data['name_am']}' ያለ ፎቶ ተጨምሯል!")
        admin_states[session_key] = {"state": "", "data": {}}

    # ---------- Edit/Delete product handlers ----------
    @bot.callback_query_handler(func=lambda call: call.data.startswith("editproduct_"))
    def edit_product_start(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም።")
            return
        p_id = int(call.data.split("_")[1])
        admin_states[(token, chat_id)] = {"state": "WAITING_EDIT_VALUES", "data": {"product_id": p_id}}
        bot.send_message(chat_id, f"✏️ ለምርት #{p_id} አዲሱን ዋጋ እና ብዛት በኮማ ይላኩ፦\n*ምሳሌ፦* `2800,15`", parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_EDIT_VALUES")
    def process_edit_product(message):
        chat_id = message.chat.id
        session_key = (token, chat_id)
        if not is_verified_admin(chat_id):
            return
        p_id = admin_states[session_key]["data"]["product_id"]
        try:
            parts = message.text.split(",")
            new_price = float(parts[0].strip())
            new_stock = int(parts[1].strip())
        except (IndexError, ValueError):
            bot.reply_to(message, "❌ ፎርማት ስህተት አለው። `ዋጋ,ብዛት` (ለምሳሌ፦ `2800,15`) ብለው ይላኩ።")
            return

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE products SET price=%s, stock=%s WHERE id=%s AND token=%s", (new_price, new_stock, p_id, token))
                conn.commit()
        finally:
            put_conn(conn)

        bot.reply_to(message, f"✅ ምርት #{p_id} ዋጋ፦ {new_price} ETB፣ ብዛት፦ {new_stock} ተብሎ ተስተካክሏል!")
        admin_states[session_key] = {"state": "", "data": {}}

    @bot.callback_query_handler(func=lambda call: call.data.startswith("deleteproduct_"))
    def delete_product_confirm(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም።")
            return
        p_id = call.data.split("_")[1]
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✔️ አረጋግጥ ሰርዝ", callback_data=f"confirmdelete_{p_id}"),
            types.InlineKeyboardButton("↩️ ተመለስ", callback_data="canceldelete")
        )
        bot.send_message(chat_id, f"⚠️ እርግጠኛ ነዎት ምርት #{p_id} ይሰረዝ?", reply_markup=markup)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("confirmdelete_"))
    def delete_product_confirmed(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም።")
            return
        p_id = call.data.split("_")[1]

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM products WHERE id=%s AND token=%s", (p_id, token))
                conn.commit()
        finally:
            put_conn(conn)

        bot.edit_message_text(f"🗑️ ምርት #{p_id} ተሰርዟል!", chat_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == "canceldelete")
    def delete_product_cancel(call):
        bot.edit_message_text("ማጥፋቱ ተሰርዟል።", call.message.chat.id, call.message.message_id)

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_PAYMENT_NUMBER")
    def process_payment_number(message):
        if not is_verified_admin(message.chat.id):
            return
        parts = message.text.strip().split(",")
        telebirr_num = parts[0].strip()
        cbe_num = parts[1].strip() if len(parts) > 1 else ""
        if cbe_num.lower() in ["የለም", "none", "no"]:
            cbe_num = ""

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET telebirr=%s, cbebirr=%s WHERE token=%s", (telebirr_num, cbe_num, token))
                conn.commit()
        finally:
            put_conn(conn)

        cbe_display = cbe_num if cbe_num else "አልገባም"
        bot.reply_to(message, f"✅ Telebirr: `{telebirr_num}`\n✅ CBE Birr: `{cbe_display}`", parse_mode="Markdown")
        admin_states[(token, message.chat.id)] = {"state": "", "data": {}}

    # ---------- Order approve/reject ----------
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
                    bot.send_message(cust_id, f"{STRINGS[cust_lang]['approved_msg']}\n\n📌 {ORDER_STAGES_AM[1] if cust_lang == 'am' else ORDER_STAGES_EN[1]}")
        finally:
            put_conn(conn)

        bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ጸድቋል! (Confirmed)", chat_id, call.message.message_id)
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
                                   ("❌ ውድቅ ተደርጓል", "❌ Rejected", order_id))
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

        new_stage = None
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT customer_id, status_stage FROM orders WHERE id=%s AND token=%s", (order_id, token))
                row = cursor.fetchone()
                if not row:
                    bot.answer_callback_query(call.id, "❌ Order አልተገኘም።")
                    return
                cust_id, stage = row
                new_stage = min((stage or 0) + 1, 3)
                cursor.execute("UPDATE orders SET status_am=%s, status_en=%s, status_stage=%s WHERE id=%s",
                               (ORDER_STAGES_AM[new_stage], ORDER_STAGES_EN[new_stage], new_stage, order_id))
                conn.commit()
                cust_lang = get_user_lang(cust_id)
                label = ORDER_STAGES_AM[new_stage] if cust_lang == "am" else ORDER_STAGES_EN[new_stage]
                bot.send_message(cust_id, f"📦 የትዕዛዝ #{order_id} ሁኔታ ተቀይሯል፦\n{label}")
        finally:
            put_conn(conn)

        bot.edit_message_text(f"🔄 ትዕዛዝ #{order_id} → {ORDER_STAGES_AM[new_stage]}", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "ተቀይሯል!")

    # ---------- AI fallback ----------
    @bot.message_handler(func=lambda message: True)
    def handle_global_ai(message):
        if not check_active_middleware(message.chat.id):
            return
        if ai_model is None:
            bot.reply_to(message, "🤖 AI በአሁኑ ሰዓት አይገኝም።")
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
# 6. DYNAMIC MULTI-TENANT LAUNCHER
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
    print(f"✅ {len(rows)} previously registered shop bot(s) restored from database.")

load_existing_stores_from_db()

# ============================================================
# 7. CONTROL BOT
# ============================================================
CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")

if CONTROL_BOT_TOKEN:
    control_bot = telebot.TeleBot(CONTROL_BOT_TOKEN)
    try:
        control_bot.remove_webhook()
    except Exception:
        pass

    @control_bot.message_handler(commands=['start', 'help'])
    def control_help(message):
        control_bot.reply_to(
            message,
            "👋 እንኳን ወደ ሱቅ ቦት መመዝገቢያ በደህና መጡ!\n\n"
            "የራስዎን ቦት ለማስመዝገብ፦\n"
            "1️⃣ @BotFather ጋር ሄደው `/newbot` በማድረግ የራስዎን ቦት ይፍጠሩ እና Token ይውሰዱ\n"
            "2️⃣ እዚህ ይላኩ፦\n"
            "`/connect [የቦትዎ_token] [የይለፍ_ቃል] [የሱቅ_ስም]`\n\n"
            "*ምሳሌ፦*\n"
            "`/connect 123456:ABC-xyz 123456 የኔ ሱቅ`",
            parse_mode="Markdown"
        )

    @control_bot.message_handler(commands=['connect'])
    def connect_new_shop(message):
        chat_id = message.chat.id
        args = message.text.split(maxsplit=3)
        if len(args) < 4:
            control_bot.reply_to(message, "⚠️ አጠቃቀም፦ `/connect [ቦት_token] [የይለፍ_ቃል] [የሱቅ_ስም]`", parse_mode="Markdown")
            return

        new_token = args[1].strip()
        password = args[2].strip()
        store_name = args[3].strip()

        if len(password) < 6:
            control_bot.reply_to(message, "❌ የይለፍ ቃል ቢያንስ 6 ፊደል/ቁጥር መሆን አለበት።")
            return

        try:
            test_bot = telebot.TeleBot(new_token)
            bot_info = test_bot.get_me()
        except Exception:
            control_bot.reply_to(message, "❌ ይህ Token ልክ አይደለም። እባክዎ ከ@BotFather ያገኙትን ትክክለኛ token ያስገቡ።")
            return

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM stores WHERE token=%s", (new_token,))
                if cursor.fetchone():
                    control_bot.reply_to(message, "❌ ይህ ቦት ቀድሞውኑ ተመዝግቧል።")
                    return

                h_pass, salt = hash_password(password)
                cursor.execute('''INSERT INTO stores (token, store_name, admin_id, password_hash, password_salt, telebirr)
                                  VALUES (%s, %s, %s, %s, %s, %s)''',
                               (new_token, store_name, chat_id, h_pass, salt, "0900000000"))
                conn.commit()
        except Exception as e:
            control_bot.reply_to(message, f"❌ Database error: {e}")
            return
        finally:
            put_conn(conn)

        start_shop_bot(new_token)

        control_bot.reply_to(
            message,
            f"🎉 ስኬታማ! '@{bot_info.username}' ለ '{store_name}' ተመዝግቦ ተነስቷል!\n\n"
            f"አሁን ወደ @{bot_info.username} ሄደው፦\n"
            f"`/login {password}`\n\nብለው ወደ አድሚን ፓናል ይግቡ።",
            parse_mode="Markdown"
        )

    # ---------------- Super Admin panel ----------------
    SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
    SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
    SUPPORT_USERNAME = os.environ.get("SUPPORT_USERNAME", "@support")

    super_admin_sessions = {}
    super_login_attempts = {}

    def is_super_admin(chat_id):
        return chat_id in super_admin_sessions and time.time() < super_admin_sessions[chat_id]

    def get_super_admin_keyboard():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("➕ አዲስ ሱቅ መዝግብ (Register)"),
            types.KeyboardButton("🏢 የተመዘገቡ ሱቆች"),
            types.KeyboardButton("📊 የሁሉም ሱቆች ስታትስቲክስ"),
            types.KeyboardButton("❓ Help / እርዳታ")
        )
        return markup

    @control_bot.message_handler(commands=['superadmin'])
    def super_auth_start(message):
        chat_id = message.chat.id
        if not SUPER_ADMIN_PASSWORD:
            control_bot.reply_to(message, "❌ SUPER_ADMIN_PASSWORD environment variable አልተዘጋጀም።")
            return
        if SUPER_ADMIN_ID != 0 and chat_id != SUPER_ADMIN_ID:
            control_bot.reply_to(message, "❌ ይህንን ትእዛዝ የመጠቀም መብት የለዎትም።")
            return

        attempt = super_login_attempts.setdefault(chat_id, {"count": 0, "lockout_until": 0})
        if time.time() < attempt["lockout_until"]:
            remaining = int(attempt["lockout_until"] - time.time())
            control_bot.reply_to(message, f"🔒 እገዳ ላይ ነዎት! ከ {remaining} ሰከንድ በኋላ ይሞክሩ።")
            return

        msg = control_bot.send_message(chat_id, "🔐 **እባክዎ የ Super Admin የይለፍ ቃል ያስገቡ፦**", parse_mode="Markdown")
        control_bot.register_next_step_handler(msg, process_super_pass)

    def process_super_pass(message):
        chat_id = message.chat.id
        attempt = super_login_attempts.setdefault(chat_id, {"count": 0, "lockout_until": 0})

        if message.text == SUPER_ADMIN_PASSWORD:
            super_admin_sessions[chat_id] = time.time() + 7200
            super_login_attempts[chat_id] = {"count": 0, "lockout_until": 0}
            control_bot.send_message(
                chat_id,
                "🔓 **እንኳን ወደ Super Admin ፓነል በደህና መጡ!** (የ2 ሰዓት ሴሽን)\n\nከታች ያሉትን አማራጮች ይጠቀሙ፦",
                reply_markup=get_super_admin_keyboard(),
                parse_mode="Markdown"
            )
        else:
            attempt["count"] += 1
            if attempt["count"] >= 5:
                attempt["lockout_until"] = time.time() + 900
                control_bot.send_message(chat_id, "❌ 5 ጊዜ ተሳስተዋል። ለ15 ደቂቃ ታግደዋል።")
            else:
                left = 5 - attempt["count"]
                control_bot.send_message(chat_id, f"❌ የተሳሳተ የይለፍ ቃል! {left} ሙከራዎች ቀርተውዎታል። ዳግም ለመሞከር `/superadmin`", parse_mode="Markdown")

    @control_bot.message_handler(func=lambda m: is_super_admin(m.chat.id) and m.text in [
        "➕ አዲስ ሱቅ መዝግብ (Register)", "🏢 የተመዘገቡ ሱቆች", "📊 የሁሉም ሱቆች ስታትስቲክስ", "❓ Help / እርዳታ"
    ])
    def handle_super_actions(message):
        chat_id = message.chat.id
        text = message.text

        if text == "➕ አዲስ ሱቅ መዝግብ (Register)":
            reg_text = (
                "📝 **አዲስ ሱቅ ለመመዝገብ (ራስ-አገልግሎት - ያለ redeploy)፦**\n\n"
                "1️⃣ የሱቁ ባለቤት @BotFather ላይ ገብቶ ቦት ይፍጠር እና Token ይውሰድ\n"
                "2️⃣ ወደ *ይህ Control Bot* ሄዶ ራሱ ይላክ፦\n"
                "`/connect [Token] [የይለፍ_ቃል] [የሱቅ_ስም]`\n\n"
                "ቦቱ ወዲያውኑ በራሱ ይነሳል - ምንም Render ማስተካከል አያስፈልግም።\n\n"
                f"🛠️ ለቴክኒክ እርዳታ፦ {SUPPORT_USERNAME}"
            )
            control_bot.reply_to(message, reg_text, parse_mode="Markdown")

        elif text == "🏢 የተመዘገቡ ሱቆች":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, store_name, is_active, telebirr FROM stores ORDER BY id")
                    stores = cur.fetchall()
            except Exception as e:
                control_bot.reply_to(message, f"❌ Database error: {e}")
                return
            finally:
                put_conn(conn)

            if not stores:
                control_bot.reply_to(message, "📜 እስካሁን የተመዘገበ ሱቅ የለም።")
                return

            for store_id, name, is_act, phone in stores:
                status_str = "🟢 ንቁ (Active)" if is_act == 1 else "🔴 የታገደ (Blocked)"
                msg_text = f"🏪 **ሱቅ #{store_id}፦** {name}\n📞 **ቴሌብር፦** `{phone}`\n📌 **ሁኔታ፦** {status_str}"

                markup = types.InlineKeyboardMarkup()
                if is_act == 1:
                    markup.add(types.InlineKeyboardButton("🔴 አግድ", callback_data=f"blk_{store_id}"))
                else:
                    markup.add(types.InlineKeyboardButton("🟢 አንቃ", callback_data=f"unblk_{store_id}"))

                control_bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode="Markdown")

        elif text == "📊 የሁሉም ሱቆች ስታትስቲክስ":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM stores")
                    tot_stores = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM products")
                    tot_products = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)), 0) FROM orders WHERE status_stage >= 1")
                    paid_orders, total_rev = cur.fetchone()
            except Exception as e:
                control_bot.reply_to(message, f"❌ Database error: {e}")
                return
            finally:
                put_conn(conn)

            report = (
                f"📊 **የሲስተሙ አጠቃላይ መረጃ**\n\n"
                f"🏢 **ጠቅላላ ሱቆች፦** {tot_stores}\n"
                f"📦 **የተጫኑ እቃዎች፦** {tot_products}\n"
                f"🧾 **የተሸጡ ትዕዛዞች፦** {paid_orders}\n"
                f"💰 **ጠቅላላ የዞረ ገንዘብ፦** {total_rev} ETB"
            )
            control_bot.reply_to(message, report, parse_mode="Markdown")

        elif text == "❓ Help / እርዳታ":
            help_msg = (
                "ℹ️ **የሲስተም አጠቃቀም**\n\n"
                "• ሱቅ ለማገድ/ለማንሳት **'🏢 የተመዘገቡ ሱቆች'** ይጠቀሙ\n"
                "• አዲስ ሱቅ ለመመዝገብ **'➕ አዲስ ሱቅ መዝግብ'** መመሪያውን ይከተሉ\n\n"
                f"📞 ተጨማሪ ጥያቄ ካለ፦ {SUPPORT_USERNAME}"
            )
            control_bot.reply_to(message, help_msg, parse_mode="Markdown")

    @control_bot.callback_query_handler(func=lambda call: call.data.startswith(("blk_", "unblk_")))
    def toggle_store_status(call):
        chat_id = call.message.chat.id
        if not is_super_admin(chat_id):
            control_bot.answer_callback_query(call.id, "❌ ሴሽንዎ አልቋል። /superadmin ብለው ዳግም ይግቡ።")
            return

        action, store_id_str = call.data.split("_", 1)
        new_status = 0 if action == "blk" else 1

        conn = get_safe_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE stores SET is_active = %s WHERE id = %s", (new_status, int(store_id_str)))
                conn.commit()
        except Exception as e:
            control_bot.answer_callback_query(call.id, f"❌ Error: {e}")
            return
        finally:
            put_conn(conn)

        status_msg = "🔴 ሱቁ ተግዷል" if new_status == 0 else "🟢 ሱቁ ተነቅቷል"
        try:
            control_bot.edit_message_text(f"{call.message.text}\n\n⚠️ **{status_msg}**", chat_id, call.message.message_id, parse_mode="Markdown")
        except:
            pass
        control_bot.answer_callback_query(call.id, status_msg)

    def _run_control_bot():
        while True:
            try:
                control_bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                print(f"⚠️ Control bot polling crashed: {e}. Restarting in 5s...")
                time.sleep(5)

    threading.Thread(target=_run_control_bot, name="ControlBot", daemon=True).start()
    print("✅ Control Bot is running (self-registration + super admin panel).")
else:
    print("⚠️ CONTROL_BOT_TOKEN not set - falling back to static BOT_TOKENS only.")
    RAW_TOKENS = os.environ.get("BOT_TOKENS", "")
    if RAW_TOKENS:
        for t in [x.strip() for x in RAW_TOKENS.split(",") if x.strip()]:
            start_shop_bot(t)

while True:
    time.sleep(3600)
