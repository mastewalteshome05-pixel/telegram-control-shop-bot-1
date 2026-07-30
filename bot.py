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
    return "Unified AI Shop Platform is Running!"

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
    print("⚠️ GEMINI_API_KEY not set")

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
            # ============================================================
            # FIXED: Added is_approved column to stores table
            # ============================================================
            cursor.execute('''CREATE TABLE IF NOT EXISTS stores (
                                id SERIAL,
                                token TEXT PRIMARY KEY,
                                store_name TEXT,
                                admin_id BIGINT,
                                username TEXT,
                                password_hash TEXT,
                                password_salt TEXT,
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
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

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
                                category_id INTEGER)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                                id SERIAL PRIMARY KEY,
                                token TEXT,
                                customer_id BIGINT,
                                status_am TEXT,
                                status_en TEXT,
                                total_price REAL,
                                delivery_fee REAL DEFAULT 0,
                                status_stage INTEGER DEFAULT 0,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS user_langs (
                                chat_id BIGINT PRIMARY KEY,
                                lang TEXT)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS customer_info (
                                chat_id BIGINT PRIMARY KEY,
                                phone TEXT,
                                lat REAL,
                                lng REAL)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
                                id SERIAL PRIMARY KEY,
                                token TEXT,
                                name_am TEXT,
                                name_en TEXT,
                                icon TEXT)''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS order_items (
                                id SERIAL PRIMARY KEY,
                                order_id INTEGER,
                                product_id INTEGER,
                                qty INTEGER,
                                price REAL)''')
            
            # ============================================================
            # FIXED: Add is_approved column if it doesn't exist
            # ============================================================
            cursor.execute("ALTER TABLE stores ADD COLUMN IF NOT EXISTS is_approved INTEGER DEFAULT 0")
            
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

ETHIOPIAN_BANKS = [
    "አብይ ኢትዮጵያ ባንክ (Commercial Bank of Ethiopia)",
    "የኢትዮጵያ ልማት ባንክ (Development Bank of Ethiopia)",
    "የኢትዮጵያ ንግድ ባንክ (Bank of Abyssinia)",
    "የኢትዮጵያ የገበያ ባንክ (Awash Bank)",
    "የኢትዮጵያ የግብርና ባንክ (Dashen Bank)",
    "የኢትዮጵያ የኢንዱስትሪ ባንክ (Wegagen Bank)",
    "የኢትዮጵያ የንግድ ባንክ (Oromia Bank)",
    "የኢትዮጵያ የልማት ባንክ (Zemen Bank)",
    "የኢትዮጵያ የህዝብ ባንክ (Bereka Bank)",
    "ቴሌብር (Telebirr)",
    "ሲቢኢ ብር (CBE Birr)"
]

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
        "back": "🔙 ወደ ኋላ / Back",
        "empty": "🛒 ጋሪዎ በአሁኑ ሰዓት ባዶ ነው።",
        "added": "ወደ ጋሪ ተጨምሯል! 🛒",
        "total": "አጠቃላይ ድምር",
        "price_label": "ዋጋ",
        "checkout_btn": "💳 ሂሳብ ማጠቃለያ",
        "clear_btn": "🗑️ ጋሪ አጽዳ",
        "enter_id": "🔢 እባክዎ የትዕዛዝ ቁጥርዎን ያስገቡ፦",
        "not_found": "❌ የትዕዛዝ ቁጥሩ አልተገኘም።",
        "invalid_id": "❌ የተሳሳተ ቁጥር ገብቷል።",
        "approved_msg": "🎉 ደስ የሚል ዜና! ክፍያ ተረጋግጧል! 🛵",
        "rejected_msg": "❌ ክፍያ አልተረጋገጠም። እባክዎ ባለቤቱን ያነጋግሩ።",
        "receipt_prompt": "እባክዎ የክፍያ ማረጋገጫ ፎቶ ይላኩ። 📸",
        "faq_text": "ℹ️ **ስለ ሱቃችን መረጃ**\n\n📍 አድራሻችን፦ አዲስ አበባ፣ ኢትዮጵያ\n📞 ስልክ፦ 0911223344\n⏱️ የስራ ሰዓት፦ ከሰኞ - ቅዳሜ (2:00 - 12:00)"
    },
    "en": {
        "welcome": "Welcome to AI Customer Service Bot! 👋",
        "shop": "🛍️ Shop Products",
        "cart": "🛒 My Cart",
        "track": "📦 Track Order",
        "faq": "❓ FAQ Info",
        "search": "🔍 Search",
        "back": "🔙 Back",
        "empty": "🛒 Your cart is currently empty.",
        "added": "Added to cart! 🛒",
        "total": "Total",
        "price_label": "Price",
        "checkout_btn": "💳 Checkout",
        "clear_btn": "🗑️ Clear Cart",
        "enter_id": "🔢 Please enter your Order ID:",
        "not_found": "❌ Order ID not found.",
        "invalid_id": "❌ Invalid ID entered.",
        "approved_msg": "🎉 Great news! Payment approved! 🛵",
        "rejected_msg": "❌ Payment rejected. Please contact store owner.",
        "receipt_prompt": "Please send payment confirmation photo. 📸",
        "faq_text": "ℹ️ **About Our Store**\n\n📍 Location: Addis Ababa, Ethiopia\n📞 Phone: +251911223344\n⏱️ Hours: Mon - Sat (8:00 AM - 6:00 PM)"
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

def get_back_button(lang):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main"))
    return markup

# ============================================================
# 5. SHOP BOT ENGINE
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
        return True
    except Exception as e:
        print(f"❌ Failed to start bot {token[:10]}: {e}")
        with running_lock:
            running_tokens.discard(token)
        return False

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
                cursor.execute('''SELECT store_name, admin_id, username, telebirr, is_active, is_approved, password_hash, password_salt,
                                  cbebirr, area_text, shop_photo, shop_description, shop_lat, shop_lng,
                                  bank_name, bank_account
                                  FROM stores WHERE token=%s''', (token,))
                row = cursor.fetchone()
        finally:
            put_conn(conn)
        if row:
            return {
                "store_name": row[0], "admin_id": row[1], "username": row[2], "telebirr": row[3], 
                "is_active": row[4], "is_approved": row[5], "pass_hash": row[6], "salt": row[7],
                "cbebirr": row[8], "area_text": row[9], "shop_photo": row[10], 
                "shop_description": row[11], "shop_lat": row[12], "shop_lng": row[13],
                "bank_name": row[14], "bank_account": row[15]
            }
        return None

    def check_active_middleware(chat_id):
        store = get_store_info()
        if not store:
            bot.send_message(chat_id, "🏪 ይህ ሱቅ ገና አልተመዘገበም።")
            return False
        if not store["is_active"]:
            bot.send_message(chat_id, "❌ ይህ ሱቅ ንቁ አይደለም። እባክዎ አድሚኑን ያነጋግሩ።")
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
        
        def search(self, query=None, min_price=None, max_price=None, category=None):
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    sql = """SELECT p.id, p.name_am, p.name_en, p.price, p.stock, p.desc_am, p.desc_en, p.image_url,
                                    c.name_am as category_am, c.name_en as category_en
                             FROM products p
                             LEFT JOIN categories c ON p.category_id = c.id
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
            bot.send_message(chat_id, "🔍 ምንም ውጤት አልተገኘም / No results found.", reply_markup=get_back_button(lang))
            return
        
        if len(results) > 10:
            bot.send_message(chat_id, f"📊 {len(results)} ምርቶች ተገኝተዋል! የመጀመሪያዎቹ 10:")
            results = results[:10]
        
        for row in results:
            p_id, name_am, name_en, price, stock, desc_am, desc_en, image_url, cat_am, cat_en = row[:10]
            name = name_am if lang == 'am' else name_en
            desc = desc_am if lang == 'am' else desc_en
            category = cat_am if lang == 'am' else cat_en
            
            stock_status = "✅ ይገኛል" if (stock or 0) > 0 else "❌ ተሟጧል"
            
            text = f"📦 **{name}**\n💰 {STRINGS[lang]['price_label']}: {price} ETB\n📌 {stock_status}"
            if category:
                text += f"\n🏷️ {category}"
            if desc:
                text += f"\n📝 {desc[:100]}..."
            
            markup = types.InlineKeyboardMarkup()
            if (stock or 0) > 0:
                btn_text = "🛒 ወደ ጋሪ ጨምር" if lang == 'am' else "🛒 Add to Cart"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"shopadd_{p_id}"))
            markup.add(types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main"))
            
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
    
    # ============================================================
    # FIXED: START HANDLER - works even if store not approved
    # ============================================================
    @bot.message_handler(commands=['start'])
    def choose_language(message):
        chat_id = message.chat.id
        store = get_store_info()
        
        if not store:
            bot.send_message(
                chat_id, 
                "🏪 ይህ ቦት ገና አልተመዘገበም።\n"
                "እባክዎ በControl Bot ይመዝገቡ!\n\n"
                "📌 ለእርዳታ አድሚኑን ያነጋግሩ"
            )
            return
        
        # Store not approved yet
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
        
        # Store is blocked
        if not store["is_active"]:
            bot.send_message(
                chat_id,
                "❌ ይህ ሱቅ ንቁ አይደለም። እባክዎ አድሚኑን ያነጋግሩ።"
            )
            return
        
        # Store is approved and active
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="shoplang_am"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data="shoplang_en")
        )
        bot.send_message(
            chat_id, 
            f"🌐 Welcome to {store['store_name']}!\n\nቋንቋ ይምረጡ / Select Language:", 
            reply_markup=markup
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("shoplang_"))
    def set_language(call):
        chat_id = call.message.chat.id
        store = get_store_info()
        if not store or not store["is_active"]:
            bot.answer_callback_query(call.id, "❌ ሱቅ ንቁ አይደለም!")
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
            bot.reply_to(message, "❌ ይህ ሱቅ ገና አልተመዘገበም። በControl Bot ይመዝገቡ!")
            return
        
        if store.get("is_approved", 0) != 1:
            bot.reply_to(
                message, 
                "⏳ ይህ ሱቅ ገና አልጸደቀም።\n"
                "እባክዎ ለማጽደቅ ይጠብቁ።"
            )
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
            bot.reply_to(message, "📝 የምርት መረጃ በዚህ ፎርማት ይላኩ፦\n`[አማርኛ ስም],[እንግሊዝኛ ስም],[ዋጋ],[ብዛት],[አማርኛ መግለጫ],[እንግሊዝኛ መግለጫ]`", parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": "WAITING_PRODUCT_DETAILS", "data": {}}
        elif text == ADMIN_BTN["my_products"]:
            show_my_products(chat_id)
        elif text == ADMIN_BTN["orders"]:
            show_pending_orders(chat_id)
        elif text == ADMIN_BTN["payment"]:
            show_payment_settings(chat_id)
        elif text == ADMIN_BTN["stats"]:
            show_stats(chat_id)
        elif text == ADMIN_BTN["profile"]:
            show_profile_menu(chat_id)
        elif text == ADMIN_BTN["changepass"]:
            bot.reply_to(message, "🔑 አዲስ የይለፍ ቃል ይላኩ (ቢያንስ 8 ፊደል):")
            admin_states[(token, chat_id)] = {"state": "WAITING_NEW_PASSWORD", "data": {}}
        elif text == ADMIN_BTN["logout"]:
            do_logout(chat_id)

    def show_payment_settings(chat_id):
        lang = get_user_lang(chat_id)
        store = get_store_info()
        
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
    def handle_payment_settings(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም።")
            return
        
        if call.data == "pay_telebirr":
            msg = bot.send_message(chat_id, "📱 የቴሌብር ቁጥር ያስገቡ:")
            bot.register_next_step_handler(msg, lambda m: process_payment_setup(m, "telebirr"))
        elif call.data == "pay_cbe":
            msg = bot.send_message(chat_id, "🏦 የCBE ብር ቁጥር ያስገቡ:")
            bot.register_next_step_handler(msg, lambda m: process_payment_setup(m, "cbe"))
        elif call.data == "pay_bank":
            bank_text = "🏛️ **የኢትዮጵያ ባንኮች**\n\n"
            for i, bank in enumerate(ETHIOPIAN_BANKS[:10], 1):
                bank_text += f"{i}. {bank}\n"
            bank_text += "\nቁጥር ወይም ስም ይምረጡ:"
            msg = bot.send_message(chat_id, bank_text)
            bot.register_next_step_handler(msg, process_bank_setup)

    def process_payment_setup(message, pay_type):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            return
        value = message.text.strip()
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                if pay_type == "telebirr":
                    cursor.execute("UPDATE stores SET telebirr=%s WHERE token=%s", (value, token))
                    bot.reply_to(message, f"✅ ቴሌብር `{value}` ተቀምጧል!")
                elif pay_type == "cbe":
                    cursor.execute("UPDATE stores SET cbebirr=%s WHERE token=%s", (value, token))
                    bot.reply_to(message, f"✅ CBE ብር `{value}` ተቀምጧል!")
                conn.commit()
        finally:
            put_conn(conn)

    def process_bank_setup(message):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            return
        bank_input = message.text.strip()
        
        if bank_input.isdigit():
            idx = int(bank_input) - 1
            if 0 <= idx < len(ETHIOPIAN_BANKS):
                bank_name = ETHIOPIAN_BANKS[idx]
            else:
                bank_name = bank_input
        else:
            bank_name = bank_input
        
        admin_states[(token, chat_id)] = {"state": "WAITING_BANK_ACCOUNT", "data": {"bank_name": bank_name}}
        bot.send_message(chat_id, f"🏛️ ባንክ: **{bank_name}**\n\nአካውንት ቁጥር ያስገቡ:")

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_BANK_ACCOUNT")
    def process_bank_account(message):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            return
        
        account_num = message.text.strip()
        bank_data = admin_states[(token, chat_id)]["data"]
        bank_name = bank_data.get("bank_name", "")
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET bank_name=%s, bank_account=%s WHERE token=%s", 
                             (bank_name, account_num, token))
                conn.commit()
        finally:
            put_conn(conn)
        
        bot.reply_to(message, f"✅ ባንክ ተቀምጧል!\n🏛️ {bank_name}\n🔢 {account_num}")
        admin_states[(token, chat_id)] = {"state": "", "data": {}}

    def show_profile_menu(chat_id):
        lang = get_user_lang(chat_id)
        store = get_store_info()
        
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
    def handle_profile_updates(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም።")
            return
        
        action = call.data.split("_")[1]
        
        if action == "location":
            loc_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            loc_markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
            bot.send_message(chat_id, "📍 አዲስ አካባቢ ያጋሩ:", reply_markup=loc_markup)
            admin_states[(token, chat_id)] = {"state": "WAITING_SHOP_LOCATION", "data": {}}
        elif action == "photo":
            bot.send_message(chat_id, "📸 አዲስ ፎቶ ይላኩ:")
            admin_states[(token, chat_id)] = {"state": "WAITING_SHOP_PHOTO", "data": {}}
        elif action == "desc":
            bot.send_message(chat_id, "📝 አዲስ መግለጫ ይላኩ:")
            admin_states[(token, chat_id)] = {"state": "WAITING_SHOP_DESC", "data": {}}

    def show_my_products(chat_id):
        lang = get_user_lang(chat_id)
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name_am, price, stock FROM products WHERE token=%s ORDER BY id", (token,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)

        if not rows:
            bot.send_message(chat_id, "📋 ምንም ምርት የለም።", reply_markup=get_back_button(lang))
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

    def show_pending_orders(chat_id):
        lang = get_user_lang(chat_id)
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
            bot.send_message(chat_id, "📋 ምንም ትዕዛዝ የለም።", reply_markup=get_back_button(lang))
            return

        for order_id, cust_id, total, stage in rows:
            stage = stage or 0
            status_label = ORDER_STAGES_AM[stage] if 0 <= stage <= 3 else "🟡 Pending"
            text = f"🆔 #{order_id}\n💵 {total} ETB\n📌 {status_label}"
            markup = types.InlineKeyboardMarkup()
            if stage == 0:
                markup.add(
                    types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                    types.InlineKeyboardButton("❌ አትቀበል", callback_data=f"rejectorder_{order_id}")
                )
            elif stage == 1:
                markup.add(types.InlineKeyboardButton("🚚 On the way", callback_data=f"advance_{order_id}"))
            elif stage == 2:
                markup.add(types.InlineKeyboardButton("✅ Delivered", callback_data=f"advance_{order_id}"))
            markup.add(types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main"))
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    def show_stats(chat_id):
        lang = get_user_lang(chat_id)
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
        bot.send_message(chat_id, text, reply_markup=get_back_button(lang), parse_mode="Markdown")

    # ============================================================
    # 5.3 BACK BUTTON
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
    def back_to_main(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        bot.send_message(chat_id, "🔙 ወደ ዋና ሜኑ", reply_markup=get_main_menu(lang))

    # ============================================================
    # 5.4 SEARCH HANDLERS
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
            types.InlineKeyboardButton("💰 በዋጋ", callback_data="search_price"),
            types.InlineKeyboardButton("🏷️ በምድብ", callback_data="search_category"),
            types.InlineKeyboardButton("🤖 AI ፍለጋ", callback_data="search_ai"),
            types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main")
        )
        bot.send_message(chat_id, "🔍 **የፍለጋ አማራጮች**", reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("search_"))
    def handle_search_options(call):
        chat_id = call.message.chat.id
        if not check_active_middleware(chat_id):
            return
        lang = get_user_lang(chat_id)
        
        if call.data == "search_name":
            msg = bot.send_message(chat_id, "📝 የምርት ስም ያስገቡ:")
            bot.register_next_step_handler(msg, process_search_by_name)
        elif call.data == "search_price":
            msg = bot.send_message(chat_id, "💰 ዝቅተኛ እና ከፍተኛ ዋጋ በኮማ ይላኩ (ለም: 100,500):")
            bot.register_next_step_handler(msg, process_search_by_price)
        elif call.data == "search_category":
            msg = bot.send_message(chat_id, "🏷️ የምድብ ስም ያስገቡ:")
            bot.register_next_step_handler(msg, process_search_by_category)
        elif call.data == "search_ai":
            msg = bot.send_message(chat_id, "🤖 ፍለጋዎን በተፈጥሮ ቋንቋ ይጻፉ:")
            bot.register_next_step_handler(msg, process_search_by_ai)

    def process_search_by_name(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        query = message.text.strip()
        if not query:
            bot.send_message(chat_id, "❌ ስም ያስገቡ", reply_markup=get_back_button(lang))
            return
        search_engine = ProductSearchEngine(token)
        results = search_engine.search(query=query)
        display_search_results(chat_id, lang, results, f"📝 {query}")

    def process_search_by_price(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        try:
            parts = message.text.strip().split(',')
            min_price = float(parts[0].strip())
            max_price = float(parts[1].strip()) if len(parts) > 1 else None
        except:
            bot.send_message(chat_id, "❌ የተሳሳተ ፎርማት", reply_markup=get_back_button(lang))
            return
        search_engine = ProductSearchEngine(token)
        results = search_engine.search(min_price=min_price, max_price=max_price)
        display_search_results(chat_id, lang, results, f"💰 {min_price} - {max_price if max_price else '∞'} ETB")

    def process_search_by_category(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        category = message.text.strip()
        if not category:
            bot.send_message(chat_id, "❌ ምድብ ያስገቡ", reply_markup=get_back_button(lang))
            return
        search_engine = ProductSearchEngine(token)
        results = search_engine.search(category=category)
        display_search_results(chat_id, lang, results, f"🏷️ {category}")

    def process_search_by_ai(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        query = message.text.strip()
        if not query:
            bot.send_message(chat_id, "❌ ጥያቄ ያስገቡ", reply_markup=get_back_button(lang))
            return
        if ai_model is None:
            bot.send_message(chat_id, "❌ AI አይገኝም", reply_markup=get_back_button(lang))
            return
        bot.send_chat_action(chat_id, 'typing')
        search_engine = ProductSearchEngine(token)
        try:
            results = search_engine.search_by_ai(query, lang)
            if results:
                display_search_results(chat_id, lang, results, f"🤖 {query}")
            else:
                bot.send_message(chat_id, "🔍 ምንም አልተገኘም", reply_markup=get_back_button(lang))
        except Exception as e:
            print(f"AI error: {e}")
            bot.send_message(chat_id, "❌ AI ስህተት", reply_markup=get_back_button(lang))

    # ============================================================
    # 5.5 CUSTOMER HANDLERS
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
            bot.send_message(chat_id, "🛍️ ምንም ምርት የለም", reply_markup=get_back_button(lang))
            return

        for row in rows:
            p_id, name_am, name_en, price, stock, desc_am, desc_en, image_url = row
            stock = stock or 0
            name = name_am if lang == "am" else name_en
            desc = desc_am if lang == "am" else desc_en
            status = "✅ In Stock" if stock > 0 else "❌ Out of Stock"
            text = f"📦 **{name}**\n💰 {STRINGS[lang]['price_label']}: {price} ETB\n📌 {status}\n📝 {desc}"

            markup = types.InlineKeyboardMarkup()
            if stock > 0:
                btn_text = "🛒 ወደ ጋሪ ጨምር" if lang == "am" else "🛒 Add to Cart"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"shopadd_{p_id}"))
            markup.add(types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main"))

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
            bot.answer_callback_query(call.id, "❌ Error")
            return

        available = prod[0] or 0
        cart_key = (token, chat_id)
        if cart_key not in user_carts:
            user_carts[cart_key] = {}
        current_qty = user_carts[cart_key].get(p_id, 0)

        if current_qty + 1 > available:
            bot.answer_callback_query(call.id, "❌ በቂ ክምችት የለም", show_alert=True)
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
            bot.send_message(chat_id, STRINGS[lang]["empty"], reply_markup=get_back_button(lang))
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
        markup.add(
            types.InlineKeyboardButton(STRINGS[lang]["checkout_btn"], callback_data="shop_checkout"),
            types.InlineKeyboardButton(STRINGS[lang]["clear_btn"], callback_data="shop_clear"),
            types.InlineKeyboardButton(STRINGS[lang]["back"], callback_data="back_to_main")
        )
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    def finalize_checkout(chat_id, lang, edit_call=None):
        cart_key = (token, chat_id)
        cart = user_carts.get(cart_key, {})
        if not cart:
            return
        store = get_store_info()
        if not store:
            bot.send_message(chat_id, "🏪 ሱቅ አልተገኘም")
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
                    bot.send_message(chat_id, "❌ ምርቶች አልቀሩም")
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

        pay_methods = ""
        if store.get('telebirr'):
            pay_methods += f"📱 ቴሌብር: `{store.get('telebirr')}`\n"
        if store.get('cbebirr'):
            pay_methods += f"🏦 CBE ብር: `{store.get('cbebirr')}`\n"
        if store.get('bank_name') and store.get('bank_account'):
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

        if edit_call:
            try:
                bot.edit_message_text(pay_text, chat_id, edit_call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, pay_text, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, pay_text, reply_markup=markup, parse_mode="Markdown")

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
            bot.edit_message_text("🛒 ጋሪ ጸድቷል", chat_id, call.message.message_id)
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
                    gate_markup.add(types.KeyboardButton("📱 ስልክ አጋራ", request_contact=True))
                if not has_location:
                    gate_markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
                bot.send_message(
                    chat_id,
                    "🚚 ለማድረሻ ስልክ እና አካባቢ ያጋሩ 👇",
                    reply_markup=gate_markup
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
                loc_markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
                bot.send_message(chat_id, "✅ ስልክ ተቀብለናል! አካባቢ ያጋሩ", reply_markup=loc_markup)

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
            bot.send_message(chat_id, "✅ አካባቢ ተቀምጧል!\n\nደረጃ 2/4: የአካባቢ ስም ይላኩ (ለም: ቦሌ):")
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
                phone_markup.add(types.KeyboardButton("📱 ስልክ አጋራ", request_contact=True))
                bot.send_message(chat_id, "✅ አካባቢ ተቀብለናል! ስልክ ያጋሩ", reply_markup=phone_markup)

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
        bot.reply_to(message, "✅ ተቀምጧል!\n\nደረጃ 3/4: ፎቶ ይላኩ (ወይም 'ስቀር'):")
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
        bot.reply_to(message, "✅ መግለጫ ተቀምጧል!")
        admin_states[(token, chat_id)] = {"state": "", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_NEW_PASSWORD")
    def process_new_password(message):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            return
        new_pass = message.text.strip()
        if len(new_pass) < 8:
            bot.reply_to(message, "❌ ቢያንስ 8 ፊደል")
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
            markup.add(
                types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                types.InlineKeyboardButton("❌ አትቀበል", callback_data=f"rejectorder_{order_id}")
            )
            phone_line = f"\n📞 {cust_info['phone']}" if cust_info and cust_info.get('phone') else ""
            bot.send_message(admin_id, f"🔔 **አዲስ ደረሰኝ #{order_id}!**{phone_line}", reply_markup=markup, parse_mode="Markdown")
            if cust_info and cust_info.get("lat") and cust_info.get("lng"):
                bot.send_location(admin_id, cust_info["lat"], cust_info["lng"])
            bot.forward_message(admin_id, chat_id, message.message_id)

            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE orders SET status_am='ክፍያ ተልኳል', status_en='Payment sent' WHERE id=%s AND token=%s", (order_id, token))
                    conn.commit()
            finally:
                put_conn(conn)

            bot.reply_to(message, "✅ ደረሰኝ ተልኳል!")
            admin_states[session_key] = {"state": "", "data": {}}

        elif state == "WAITING_SHOP_PHOTO":
            if not is_verified_admin(chat_id):
                bot.reply_to(message, "❌ ሴሽን አልቋል")
                return
            photo_id = message.photo[-1].file_id
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET shop_photo=%s WHERE token=%s", (photo_id, token))
                    conn.commit()
            finally:
                put_conn(conn)
            bot.reply_to(message, "✅ ፎቶ ተቀምጧል!\n\nደረጃ 4/4: ስለ ሱቅ መግለጫ ይላኩ:")
            admin_states[session_key] = {"state": "WAITING_SHOP_DESC", "data": {}}

        elif state == "WAITING_PRODUCT_PHOTO":
            if not is_verified_admin(chat_id):
                bot.reply_to(message, "❌ ሴሽን አልቋል")
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
            bot.reply_to(message, f"🎉 ምርት '{p_data['name_am']}' ተጨምሯል!")
            admin_states[session_key] = {"state": "", "data": {}}
        else:
            bot.reply_to(message, "📸 እናመሰግናለን!")

    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["faq"])
    def show_faq(message):
        if not check_active_middleware(message.chat.id):
            return
        lang = get_user_lang(message.chat.id)
        store = get_store_info()
        text = STRINGS[lang]["faq_text"]
        if store:
            if store.get('shop_description'):
                text += f"\n\n📝 {store.get('shop_description')}"
            if store.get('area_text'):
                text += f"\n📍 {store.get('area_text')}"
            if store.get('username'):
                text += f"\n👤 @{store.get('username')}"
        bot.reply_to(message, text, reply_markup=get_back_button(lang), parse_mode="Markdown")

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
                bot.reply_to(message, f"📦 **Status:** {status}", reply_markup=get_back_button(lang))
            else:
                bot.reply_to(message, STRINGS[lang]["not_found"], reply_markup=get_back_button(lang))
        except ValueError:
            bot.reply_to(message, STRINGS[lang]["invalid_id"], reply_markup=get_back_button(lang))

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
            bot.reply_to(message, "📸 ፎቶ ይላኩ (ወይም 'none'):")
            admin_states[session_key] = {"state": "WAITING_PRODUCT_PHOTO", "data": product_data}
        except (IndexError, ValueError):
            bot.reply_to(message, "❌ ፎርማት ስህተት")
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
        bot.reply_to(message, f"🎉 ምርት '{p_data['name_am']}' ተጨምሯል!")
        admin_states[session_key] = {"state": "", "data": {}}

    @bot.callback_query_handler(func=lambda call: call.data.startswith("editproduct_"))
    def edit_product_start(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም")
            return
        p_id = int(call.data.split("_")[1])
        admin_states[(token, chat_id)] = {"state": "WAITING_EDIT_VALUES", "data": {"product_id": p_id}}
        bot.send_message(chat_id, f"✏️ አዲስ ዋጋ,ብዛት በኮማ ይላኩ (ለም: 2800,15):")
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
            bot.reply_to(message, "❌ ፎርማት ስህተት")
            return

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE products SET price=%s, stock=%s WHERE id=%s AND token=%s", (new_price, new_stock, p_id, token))
                conn.commit()
        finally:
            put_conn(conn)

        bot.reply_to(message, f"✅ ምርት #{p_id} ተስተካክሏል!")
        admin_states[session_key] = {"state": "", "data": {}}

    @bot.callback_query_handler(func=lambda call: call.data.startswith("deleteproduct_"))
    def delete_product_confirm(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም")
            return
        p_id = call.data.split("_")[1]
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✔️ አረጋግጥ", callback_data=f"confirmdelete_{p_id}"),
            types.InlineKeyboardButton("↩️ ተመለስ", callback_data="canceldelete")
        )
        bot.send_message(chat_id, f"⚠️ ምርት #{p_id} ይሰረዝ?", reply_markup=markup)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("confirmdelete_"))
    def delete_product_confirmed(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም")
            return
        p_id = call.data.split("_")[1]
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM products WHERE id=%s AND token=%s", (p_id, token))
                conn.commit()
        finally:
            put_conn(conn)
        bot.edit_message_text(f"🗑️ ምርት #{p_id} ተሰርዟል", chat_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == "canceldelete")
    def delete_product_cancel(call):
        bot.edit_message_text("ማጥፋቱ ተሰርዟል", call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("approveorder_"))
    def approve_order_btn(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም")
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
                    bot.send_message(cust_id, STRINGS[cust_lang]["approved_msg"])
        finally:
            put_conn(conn)

        bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ጸድቋል", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "ጸድቋል!")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("rejectorder_"))
    def reject_order_btn(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም")
            return
        order_id = int(call.data.split("_")[1])

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT customer_id FROM orders WHERE id=%s AND token=%s", (order_id, token))
                row = cursor.fetchone()
                if row:
                    cust_id = row[0]
                    cursor.execute("UPDATE orders SET status_am='❌ ውድቅ', status_en='❌ Rejected', status_stage=-1 WHERE id=%s", (order_id,))
                    conn.commit()
                    cust_lang = get_user_lang(cust_id)
                    bot.send_message(cust_id, STRINGS[cust_lang]["rejected_msg"])
        finally:
            put_conn(conn)

        bot.edit_message_text(f"❌ ትዕዛዝ #{order_id} ውድቅ ተደርጓል", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "ውድቅ ተደርጓል")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("advance_"))
    def advance_order_btn(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            bot.answer_callback_query(call.id, "❌ ፍቃድ የለዎትም")
            return
        order_id = int(call.data.split("_")[1])

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT customer_id, status_stage FROM orders WHERE id=%s AND token=%s", (order_id, token))
                row = cursor.fetchone()
                if not row:
                    bot.answer_callback_query(call.id, "❌ Order አልተገኘም")
                    return
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

    @bot.message_handler(func=lambda message: True)
    def handle_global_ai(message):
        if not check_active_middleware(message.chat.id):
            return
        if ai_model is None:
            bot.reply_to(message, "🤖 AI አይገኝም")
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
# 6. LOAD EXISTING STORES
# ============================================================
def load_existing_stores_from_db():
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT token FROM stores WHERE is_approved = 1")
            rows = cursor.fetchall()
    finally:
        put_conn(conn)
    for (tok,) in rows:
        start_shop_bot(tok)
    print(f"✅ {len(rows)} approved stores restored.")

load_existing_stores_from_db()

# ============================================================
# 7. CONTROL BOT WITH SUPER ADMIN PANEL
# ============================================================
CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")
SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")

if CONTROL_BOT_TOKEN:
    control_bot = telebot.TeleBot(CONTROL_BOT_TOKEN)
    try:
        control_bot.remove_webhook()
    except Exception:
        pass

    super_admin_sessions = {}
    super_login_attempts = {}
    reg_states = {}

    def is_super_admin(chat_id):
        return chat_id in super_admin_sessions and time.time() < super_admin_sessions[chat_id]

    # ============================================================
    # 7.1 DASHBOARD FUNCTIONS
    # ============================================================
    
    def render_dashboard_text():
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM stores WHERE is_approved=0")
                pending = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM stores WHERE is_active=1 AND is_approved=1")
                active = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM stores")
                total = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM orders WHERE created_at > NOW() - INTERVAL '24 hours'")
                today_orders = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM orders")
                total_orders = cursor.fetchone()[0]
                cursor.execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1")
                revenue = cursor.fetchone()[0]
        finally:
            put_conn(conn)
        return (
            "🎛 **Super Admin Dashboard**\n\n"
            f"🏪 Total stores: **{total}**\n"
            f"⏳ Pending approval: **{pending}**\n"
            f"🟢 Active stores: **{active}**\n"
            f"🧾 Orders (24h): **{today_orders}**\n"
            f"📦 Total orders: **{total_orders}**\n"
            f"💰 Revenue: **{revenue:,.2f} ETB**\n\n"
            "Choose an action below 👇"
        )

    def get_dashboard_markup():
        m = types.InlineKeyboardMarkup(row_width=2)
        m.add(
            types.InlineKeyboardButton("⏳ Pending Stores", callback_data="dash_pending"),
            types.InlineKeyboardButton("🏢 All Stores", callback_data="dash_all"),
            types.InlineKeyboardButton("📊 Stats", callback_data="dash_stats"),
            types.InlineKeyboardButton("📢 Broadcast", callback_data="dash_broadcast"),
            types.InlineKeyboardButton("🔄 Refresh", callback_data="dash_refresh"),
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="dash_back")
        )
        return m

    # ============================================================
    # 7.2 SUPER ADMIN LOGIN
    # ============================================================
    @control_bot.message_handler(commands=['superadmin'])
    def super_auth_start(message):
        chat_id = message.chat.id
        if not SUPER_ADMIN_PASSWORD:
            control_bot.reply_to(message, "❌ SUPER_ADMIN_PASSWORD not set!")
            return
        if SUPER_ADMIN_ID != 0 and chat_id != SUPER_ADMIN_ID:
            control_bot.reply_to(message, "❌ መብት የለዎትም!")
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
                "🔓 **እንኳን ወደ Super Admin ፓነል በደህና መጡ!** (የ2 ሰዓት ሴሽን)",
                parse_mode="Markdown"
            )
            
            control_bot.send_message(
                chat_id,
                render_dashboard_text(),
                reply_markup=get_dashboard_markup(),
                parse_mode="Markdown"
            )
        else:
            attempt["count"] += 1
            if attempt["count"] >= 5:
                attempt["lockout_until"] = time.time() + 900
                control_bot.send_message(chat_id, "❌ 5 ጊዜ ተሳስተዋል። ለ15 ደቂቃ ታግደዋል።")
            else:
                left = 5 - attempt["count"]
                control_bot.send_message(chat_id, f"❌ የተሳሳተ የይለፍ ቃል! {left} ሙከራዎች ቀርተውዎታል።")

    # ============================================================
    # 7.3 DASHBOARD PANEL - /panel COMMAND
    # ============================================================
    @control_bot.message_handler(commands=['panel'])
    def open_dashboard(message):
        chat_id = message.chat.id
        if not is_super_admin(chat_id):
            control_bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
            return
        control_bot.send_message(
            chat_id,
            render_dashboard_text(),
            reply_markup=get_dashboard_markup(),
            parse_mode="Markdown"
        )

    # ============================================================
    # 7.4 DASHBOARD CALLBACK HANDLER
    # ============================================================
    @control_bot.callback_query_handler(func=lambda call: call.data.startswith("dash_"))
    def dashboard_router(call):
        chat_id = call.message.chat.id
        if not is_super_admin(chat_id):
            control_bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
            return
        
        action = call.data.split("_")[1]
        
        if action == "refresh":
            control_bot.edit_message_text(
                render_dashboard_text(),
                chat_id,
                call.message.message_id,
                reply_markup=get_dashboard_markup(),
                parse_mode="Markdown"
            )
            control_bot.answer_callback_query(call.id, "🔄 Refreshed!")
        
        elif action == "pending":
            control_bot.answer_callback_query(call.id)
            show_pending_stores(call.message)
        
        elif action == "all":
            control_bot.answer_callback_query(call.id)
            show_all_stores(call.message)
        
        elif action == "stats":
            control_bot.answer_callback_query(call.id)
            show_system_stats(call.message)
        
        elif action == "broadcast":
            control_bot.answer_callback_query(call.id)
            broadcast_menu(call.message)
        
        elif action == "back":
            control_bot.answer_callback_query(call.id)
            try:
                control_bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            control_bot.send_message(
                chat_id,
                render_dashboard_text(),
                reply_markup=get_dashboard_markup(),
                parse_mode="Markdown"
            )

    # ============================================================
    # 7.5 PENDING STORES APPROVAL
    # ============================================================
    def show_pending_stores(message):
        chat_id = message.chat.id
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""SELECT id, store_name, username, area_text, shop_description, created_at, admin_id, token 
                                  FROM stores WHERE is_approved = 0 AND is_active = 1 ORDER BY created_at DESC""")
                stores = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not stores:
            control_bot.send_message(chat_id, "✅ ምንም ያልተጸደቁ ሱቆች የሉም!", reply_markup=get_dashboard_markup())
            return
        
        for store in stores:
            store_id, name, username, area, desc, created, admin_id, token = store
            text = f"🏪 **{name}**\n"
            text += f"🆔 #{store_id}\n"
            text += f"👤 @{username if username else 'ስም'}\n"
            text += f"📍 {area if area else 'አልተዘጋጀም'}\n"
            text += f"📝 {desc[:50] if desc else ''}...\n"
            text += f"📅 {created.strftime('%Y-%m-%d %H:%M')}\n"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"sapprove_{store_id}"),
                types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"sreject_{store_id}"),
                types.InlineKeyboardButton("🔙 Back", callback_data="dash_back")
            )
            control_bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @control_bot.callback_query_handler(func=lambda call: call.data.startswith("sapprove_"))
    def super_approve_store(call):
        chat_id = call.message.chat.id
        if not is_super_admin(chat_id):
            control_bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
            return
        
        store_id = int(call.data.split("_")[1])
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT token, store_name, admin_id FROM stores WHERE id=%s", (store_id,))
                store = cursor.fetchone()
                if store:
                    token, name, admin_id = store
                    cursor.execute("UPDATE stores SET is_approved = 1 WHERE id=%s", (store_id,))
                    conn.commit()
                    
                    start_shop_bot(token)
                    
                    try:
                        control_bot.send_message(
                            admin_id,
                            f"🎉 **ሱቅዎ ተጸድቋል!**\n\n"
                            f"🏪 {name}\n"
                            f"🔑 አሁን /login [የይለፍ_ቃል] በማድረግ መግባት ይችላሉ"
                        )
                    except:
                        pass
                    
                    control_bot.edit_message_text(
                        f"✅ ሱቅ #{store_id} ተጸድቋል!\n🏪 {name}",
                        chat_id, call.message.message_id
                    )
                    control_bot.answer_callback_query(call.id, "ተጸድቋል!")
                    
                    control_bot.send_message(
                        chat_id,
                        render_dashboard_text(),
                        reply_markup=get_dashboard_markup(),
                        parse_mode="Markdown"
                    )
        finally:
            put_conn(conn)

    @control_bot.callback_query_handler(func=lambda call: call.data.startswith("sreject_"))
    def super_reject_store(call):
        chat_id = call.message.chat.id
        if not is_super_admin(chat_id):
            control_bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
            return
        
        store_id = int(call.data.split("_")[1])
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT store_name, admin_id FROM stores WHERE id=%s", (store_id,))
                store = cursor.fetchone()
                if store:
                    name, admin_id = store
                    cursor.execute("DELETE FROM stores WHERE id=%s", (store_id,))
                    conn.commit()
                    
                    try:
                        control_bot.send_message(
                            admin_id,
                            f"❌ ሱቅዎ **{name}** ውድቅ ተደርጓል።"
                        )
                    except:
                        pass
                    
                    control_bot.edit_message_text(
                        f"❌ ሱቅ #{store_id} ውድቅ ተደርጓል!\n🏪 {name}",
                        chat_id, call.message.message_id
                    )
                    control_bot.answer_callback_query(call.id, "ውድቅ ተደርጓል!")
                    
                    control_bot.send_message(
                        chat_id,
                        render_dashboard_text(),
                        reply_markup=get_dashboard_markup(),
                        parse_mode="Markdown"
                    )
        finally:
            put_conn(conn)

    # ============================================================
    # 7.6 ALL STORES MANAGEMENT
    # ============================================================
    def show_all_stores(message):
        chat_id = message.chat.id
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""SELECT id, store_name, username, is_active, is_approved, created_at 
                                  FROM stores ORDER BY created_at DESC LIMIT 20""")
                stores = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not stores:
            control_bot.send_message(chat_id, "📜 ምንም ሱቅ የለም!", reply_markup=get_dashboard_markup())
            return
        
        text = "🏢 **ሁሉም ሱቆች**\n\n"
        for store in stores:
            store_id, name, username, is_active, is_approved, created = store
            status = "🟢" if is_active == 1 else "🔴"
            approved = "✅" if is_approved == 1 else "⏳"
            text += f"{status} {approved} **{name}**\n"
            text += f"  🆔 #{store_id} | 👤 @{username if username else 'ስም'}\n"
            text += f"  📅 {created.strftime('%Y-%m-%d')}\n\n"
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔴 ሱቅ አግድ", callback_data="sblock_menu"),
            types.InlineKeyboardButton("🟢 ሱቅ አንቃ", callback_data="sunblock_menu"),
            types.InlineKeyboardButton("🗑️ ሱቅ ሰርዝ", callback_data="sdelete_menu"),
            types.InlineKeyboardButton("🔙 Back", callback_data="dash_back")
        )
        control_bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @control_bot.callback_query_handler(func=lambda call: call.data in ["sblock_menu", "sunblock_menu", "sdelete_menu"])
    def store_management_menu(call):
        chat_id = call.message.chat.id
        if not is_super_admin(chat_id):
            control_bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
            return
        
        action = call.data.split("_")[0]
        action_text = {
            "sblock": "🔴 ለማገድ የሱቅ ቁጥር ያስገቡ:",
            "sunblock": "🟢 ለማንቃት የሱቅ ቁጥር ያስገቡ:",
            "sdelete": "🗑️ ለመሰረዝ የሱቅ ቁጥር ያስገቡ:"
        }
        
        msg = control_bot.send_message(chat_id, action_text.get(action, "የሱቅ ቁጥር ያስገቡ:"))
        control_bot.register_next_step_handler(msg, lambda m: process_store_action(m, action))

    def process_store_action(message, action):
        chat_id = message.chat.id
        if not is_super_admin(chat_id):
            return
        
        try:
            store_id = int(message.text.strip())
        except:
            control_bot.reply_to(message, "❌ የተሳሳተ ቁጥር!")
            return
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT store_name, token, admin_id FROM stores WHERE id=%s", (store_id,))
                store = cursor.fetchone()
                if not store:
                    control_bot.reply_to(message, "❌ ሱቅ አልተገኘም!")
                    return
                
                name, token, admin_id = store
                
                if action == "sblock":
                    cursor.execute("UPDATE stores SET is_active = 0 WHERE id=%s", (store_id,))
                    action_text = f"🔴 ሱቅ **{name}** ተግዷል!"
                    try:
                        control_bot.send_message(admin_id, f"🔴 ሱቅዎ **{name}** ተግዷል!")
                    except:
                        pass
                elif action == "sunblock":
                    cursor.execute("UPDATE stores SET is_active = 1 WHERE id=%s", (store_id,))
                    action_text = f"🟢 ሱቅ **{name}** ተነቅቷል!"
                    try:
                        control_bot.send_message(admin_id, f"🟢 ሱቅዎ **{name}** ተነቅቷል!")
                    except:
                        pass
                elif action == "sdelete":
                    cursor.execute("DELETE FROM products WHERE token=%s", (token,))
                    cursor.execute("DELETE FROM orders WHERE token=%s", (token,))
                    cursor.execute("DELETE FROM stores WHERE id=%s", (store_id,))
                    action_text = f"🗑️ ሱቅ **{name}** ተሰርዟል!"
                    try:
                        control_bot.send_message(admin_id, f"🗑️ ሱቅዎ **{name}** ተሰርዟል!")
                    except:
                        pass
                
                conn.commit()
                control_bot.reply_to(message, f"✅ {action_text}")
                
                control_bot.send_message(
                    chat_id,
                    render_dashboard_text(),
                    reply_markup=get_dashboard_markup(),
                    parse_mode="Markdown"
                )
        finally:
            put_conn(conn)

    # ============================================================
    # 7.7 SYSTEM STATS
    # ============================================================
    def show_system_stats(message):
        chat_id = message.chat.id
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM stores")
                total_stores = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1")
                active_stores = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0")
                pending_stores = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM products")
                total_products = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM orders")
                total_orders = cursor.fetchone()[0]
                
                cursor.execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1")
                total_revenue = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT customer_id) FROM orders")
                active_users = cursor.fetchone()[0]
                
                cursor.execute("""SELECT status_stage, COUNT(*) FROM orders GROUP BY status_stage""")
                orders_by_stage = cursor.fetchall()
                
                cursor.execute("""SELECT COUNT(*) FROM orders WHERE created_at > NOW() - INTERVAL '7 days'""")
                recent_orders = cursor.fetchone()[0]
        finally:
            put_conn(conn)
        
        stage_names = ["🟡 በመጠባበቅ ላይ", "✅ ተረጋግጧል", "🚚 በመንገድ ላይ", "📦 ደርሷል", "❌ ውድቅ"]
        
        text = "📊 **የሲስተም ስታቲስቲክስ**\n\n"
        text += f"🏪 **ሱቆች**\n"
        text += f"  • ጠቅላላ: {total_stores}\n"
        text += f"  • ንቁ: {active_stores}\n"
        text += f"  • ያልተጸደቀ: {pending_stores}\n\n"
        text += f"📦 **ምርቶች:** {total_products}\n\n"
        text += f"🧾 **ትዕዛዞች**\n"
        text += f"  • ጠቅላላ: {total_orders}\n"
        text += f"  • የቅርብ 7 ቀናት: {recent_orders}\n"
        text += f"  • ንቁ ተጠቃሚዎች: {active_users}\n\n"
        
        for stage, count in orders_by_stage:
            if stage >= 0 and stage < len(stage_names):
                text += f"  • {stage_names[stage]}: {count}\n"
        
        text += f"\n💰 **ጠቅላላ ገቢ:** {total_revenue:,.2f} ETB"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="dash_back"))
        control_bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    # ============================================================
    # 7.8 BROADCAST MESSAGING
    # ============================================================
    def broadcast_menu(message):
        chat_id = message.chat.id
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📢 ለሱቅ ባለቤቶች", callback_data="broadcast_owners"),
            types.InlineKeyboardButton("👥 ለደንበኞች", callback_data="broadcast_customers"),
            types.InlineKeyboardButton("👤 ለአንድ ተጠቃሚ", callback_data="broadcast_user"),
            types.InlineKeyboardButton("🔙 Back", callback_data="dash_back")
        )
        control_bot.send_message(
            chat_id,
            "📢 **ብሮድካስት መልእክት**\n\n"
            "መልእክት ለማን መላክ ይፈልጋሉ?",
            reply_markup=markup
        )

    @control_bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_"))
    def broadcast_type(call):
        chat_id = call.message.chat.id
        if not is_super_admin(chat_id):
            control_bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
            return
        
        broadcast_type = call.data.split("_")[1]
        control_bot.answer_callback_query(call.id)
        
        if broadcast_type == "user":
            msg = control_bot.send_message(chat_id, "👤 የተጠቃሚ አይዲ (User ID) ያስገቡ:")
            control_bot.register_next_step_handler(msg, lambda m: broadcast_to_user(m))
        else:
            msg = control_bot.send_message(
                chat_id,
                f"📝 **መልእክት ይላኩ**\n\n"
                f"ለ{'ሱቅ ባለቤቶች' if broadcast_type == 'owners' else 'ደንበኞች'} የሚላከውን መልእክት ይላኩ:"
            )
            control_bot.register_next_step_handler(msg, lambda m: broadcast_to_all(m, broadcast_type))

    def broadcast_to_all(message, target):
        chat_id = message.chat.id
        if not is_super_admin(chat_id):
            return
        
        msg_text = message.text
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                if target == "owners":
                    cursor.execute("SELECT DISTINCT admin_id FROM stores WHERE admin_id > 0 AND is_approved = 1")
                else:
                    cursor.execute("SELECT DISTINCT customer_id FROM orders")
                users = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not users:
            control_bot.reply_to(message, "❌ ምንም ተጠቃሚ አልተገኘም!")
            return
        
        control_bot.reply_to(message, f"⏳ ለ {len(users)} ተጠቃሚዎች በማስተላለፍ ላይ...")
        
        success = 0
        failed = 0
        
        for (user_id,) in users:
            try:
                control_bot.send_message(
                    user_id,
                    f"📢 **የሲስተም ማስታወቂያ**\n\n{msg_text}"
                )
                success += 1
                time.sleep(0.05)
            except:
                failed += 1
        
        control_bot.send_message(
            chat_id,
            f"✅ ብሮድካስት ተጠናቋል!\n\n✅ የተሳካ: {success}\n❌ ያልተሳካ: {failed}",
            reply_markup=get_dashboard_markup()
        )

    def broadcast_to_user(message):
        chat_id = message.chat.id
        if not is_super_admin(chat_id):
            return
        
        try:
            user_id = int(message.text.strip())
        except:
            control_bot.reply_to(message, "❌ የተሳሳተ አይዲ!")
            return
        
        msg = control_bot.send_message(chat_id, "📝 ለተጠቃሚው የሚላከውን መልእክት ይላኩ:")
        control_bot.register_next_step_handler(msg, lambda m: send_to_single_user(m, user_id))

    def send_to_single_user(message, user_id):
        chat_id = message.chat.id
        if not is_super_admin(chat_id):
            return
        
        msg_text = message.text
        
        try:
            control_bot.send_message(
                user_id,
                f"📢 **የሲስተም ማስታወቂያ**\n\n{msg_text}"
            )
            control_bot.reply_to(message, f"✅ መልእክት ለተጠቃሚ {user_id} ተልኳል!", reply_markup=get_dashboard_markup())
        except:
            control_bot.reply_to(message, f"❌ መልእክት ለ {user_id} መላክ አልተቻለም!", reply_markup=get_dashboard_markup())

    # ============================================================
    # 7.9 NORMAL USER COMMANDS
    # ============================================================
    @control_bot.message_handler(commands=['start', 'help'])
    def control_help(message):
        chat_id = message.chat.id
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("📝 አዲስ ሱቅ መዝግብ"),
            types.KeyboardButton("🏪 ሱቆቼ"),
            types.KeyboardButton("🔍 ሱቆችን ፈልግ"),
            types.KeyboardButton("❓ እርዳታ")
        )
        
        help_text = (
            "👋 እንኳን ወደ ሱቅ ቦት መመዝገቢያ በደህና መጡ!\n\n"
            "📌 **አዲስ ሱቅ ለመመዝገብ:**\n"
            "1️⃣ @BotFather ላይ `/newbot` በማድረግ ቦት ይፍጠሩ\n"
            "2️⃣ Token ከተቀበሉ '📝 አዲስ ሱቅ መዝግብ' ይጫኑ\n"
            "3️⃣ 5 ደረጃዎችን ይሙሉ\n\n"
            "📌 **ለሙከራ ሱቅ:** `/demo`\n"
            "📌 **ሱቆችዎን ለማየት:** 🏪 ሱቆቼ\n\n"
            "👑 **Super Admin ከሆኑ:** `/superadmin`"
        )
        control_bot.send_message(chat_id, help_text, reply_markup=markup, parse_mode="Markdown")

    @control_bot.message_handler(commands=['demo'])
    def create_demo_store(message):
        chat_id = message.chat.id
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT token, store_name FROM stores WHERE admin_id=%s", (chat_id,))
                existing = cursor.fetchone()
                
                if existing:
                    control_bot.reply_to(
                        message,
                        f"✅ ቀድሞውኑ ሱቅ አለዎት!\n\n🏪 **{existing[1]}**\n🔑 `{existing[0][:20]}...`"
                    )
                    return
                
                demo_token = f"demo_{chat_id}_{int(time.time())}"
                demo_name = f"የሙከራ ሱቅ #{chat_id}"
                demo_username = f"demo_{chat_id}"
                
                h_pass, salt = hash_password("demo123")
                cursor.execute('''INSERT INTO stores (token, store_name, admin_id, username, password_hash, password_salt, 
                                  telebirr, cbebirr, is_active, is_approved, shop_lat, shop_lng, area_text, shop_description)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                               (demo_token, demo_name, chat_id, demo_username, h_pass, salt, 
                                "0911223344", "1000123456789", 1, 1, 9.03, 38.74, "አዲስ አበባ", 
                                "ይህ የሙከራ ሱቅ ነው!"))
                conn.commit()
                
                start_shop_bot(demo_token)
                
                control_bot.reply_to(
                    message,
                    f"🎉 **የሙከራ ሱቅ ተፈጠረ!**\n\n"
                    f"🏪 **ስም:** {demo_name}\n"
                    f"👤 **ዩዘርኔም:** @{demo_username}\n"
                    f"📍 **አካባቢ:** አዲስ አበባ\n"
                    f"🔑 **የይለፍ ቃል:** `demo123`\n\n"
                    f"📌 ወደ ሱቅዎ ቦት ይሂዱ እና `/login demo123` ይላኩ"
                )
        except Exception as e:
            control_bot.reply_to(message, f"❌ ስህተት: {e}")
        finally:
            put_conn(conn)

    @control_bot.message_handler(func=lambda m: m.text == "📝 አዲስ ሱቅ መዝግብ")
    def start_registration(message):
        chat_id = message.chat.id
        
        reg_states[chat_id] = {"step": 1, "data": {}}
        
        msg = control_bot.send_message(
            chat_id,
            "📝 **ደረጃ 1/5: የቦት ቶከን**\n\n"
            "ከ @BotFather ያገኙትን ቶከን ያስገቡ:"
        )
        control_bot.register_next_step_handler(msg, reg_step_token)

    def reg_step_token(message):
        chat_id = message.chat.id
        token = message.text.strip()
        
        try:
            test_bot = telebot.TeleBot(token)
            bot_info = test_bot.get_me()
        except Exception:
            control_bot.reply_to(message, "❌ ቶከን ልክ አይደለም!")
            return
        
        reg_states[chat_id]["data"]["token"] = token
        reg_states[chat_id]["data"]["bot_username"] = bot_info.username
        reg_states[chat_id]["step"] = 2
        
        msg = control_bot.send_message(
            chat_id,
            f"✅ ቶከን ተረጋግጧል! 👤 @{bot_info.username}\n\n"
            "📝 **ደረጃ 2/5: የሱቅ ስም**\n\n"
            "የሱቅዎን ስም ያስገቡ:"
        )
        control_bot.register_next_step_handler(msg, reg_step_name)

    def reg_step_name(message):
        chat_id = message.chat.id
        name = message.text.strip()
        
        reg_states[chat_id]["data"]["store_name"] = name
        reg_states[chat_id]["step"] = 3
        
        msg = control_bot.send_message(
            chat_id,
            f"✅ ስም: **{name}**\n\n"
            "📝 **ደረጃ 3/5: የይለፍ ቃል**\n\n"
            "ለሱቅ አስተዳደር የይለፍ ቃል ያስገቡ (ቢያንስ 6 ፊደል):"
        )
        control_bot.register_next_step_handler(msg, reg_step_password)

    def reg_step_password(message):
        chat_id = message.chat.id
        password = message.text.strip()
        
        if len(password) < 6:
            control_bot.reply_to(message, "❌ ቢያንስ 6 ፊደል!")
            return
        
        reg_states[chat_id]["data"]["password"] = password
        reg_states[chat_id]["step"] = 4
        
        msg = control_bot.send_message(
            chat_id,
            f"✅ የይለፍ ቃል ተቀብለናል\n\n"
            "📝 **ደረጃ 4/5: የሱቅ አካባቢ**\n\n"
            "የሱቅዎን አካባቢ ያጋሩ (ቁልፉን ይጫኑ) ወይም የከተማ ስም ያስገቡ:",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            .add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
        )
        control_bot.register_next_step_handler(msg, reg_step_location)

    def reg_step_location(message):
        chat_id = message.chat.id
        
        if message.location:
            lat = message.location.latitude
            lng = message.location.longitude
            reg_states[chat_id]["data"]["shop_lat"] = lat
            reg_states[chat_id]["data"]["shop_lng"] = lng
            location_text = f"📍 {lat}, {lng}"
        else:
            location_text = message.text.strip()
            reg_states[chat_id]["data"]["area_text"] = location_text
        
        reg_states[chat_id]["step"] = 5
        
        msg = control_bot.send_message(
            chat_id,
            f"✅ አካባቢ: {location_text}\n\n"
            "📝 **ደረጃ 5/5: ስለ ሱቅ መግለጫ**\n\n"
            "ስለ ሱቅዎ አጭር መግለጫ ይላኩ:"
        )
        control_bot.register_next_step_handler(msg, reg_step_description)

    def reg_step_description(message):
        chat_id = message.chat.id
        description = message.text.strip()
        
        data = reg_states[chat_id]["data"]
        data["shop_description"] = description
        data["username"] = f"shop_{chat_id}_{int(time.time())}"
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM stores WHERE token=%s", (data["token"],))
                if cursor.fetchone():
                    control_bot.reply_to(message, "❌ ቶከን ቀድሞውኑ ተመዝግቧል!")
                    return
                
                h_pass, salt = hash_password(data["password"])
                
                cursor.execute('''INSERT INTO stores 
                                  (token, store_name, admin_id, username, password_hash, password_salt, 
                                   telebirr, cbebirr, is_active, is_approved, shop_lat, shop_lng, area_text, shop_description)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                               (data["token"], data["store_name"], chat_id, data["username"],
                                h_pass, salt, "", "", 1, 0,
                                data.get("shop_lat"), data.get("shop_lng"), data.get("area_text", ""),
                                data.get("shop_description", "")))
                conn.commit()
                
                if SUPER_ADMIN_ID:
                    try:
                        control_bot.send_message(
                            SUPER_ADMIN_ID,
                            f"🔔 **አዲስ ሱቅ ለማጽደቅ ተመዝግቧል!**\n\n"
                            f"🏪 **{data['store_name']}**\n"
                            f"👤 @{data['username']}\n"
                            f"📍 {data.get('area_text', 'አልተዘጋጀም')}"
                        )
                    except:
                        pass
                
                del reg_states[chat_id]
                
                control_bot.reply_to(
                    message,
                    f"✅ **ሱቅ ተመዝግቧል!**\n\n"
                    f"🏪 **ስም:** {data['store_name']}\n"
                    f"👤 **ዩዘርኔም:** @{data['username']}\n"
                    f"📍 **አካባቢ:** {data.get('area_text', 'ተቀምጧል')}\n"
                    f"📝 **መግለጫ:** {data.get('shop_description', '')[:50]}...\n\n"
                    f"🔑 **የይለፍ ቃል:** `{data['password']}`\n\n"
                    f"⏳ **ሱቅዎ ለማጽደቅ በመጠባበቅ ላይ ነው!**"
                )
        except Exception as e:
            control_bot.reply_to(message, f"❌ ስህተት: {e}")
        finally:
            put_conn(conn)

    @control_bot.message_handler(func=lambda m: m.text == "🏪 ሱቆቼ")
    def show_my_stores_control(message):
        chat_id = message.chat.id
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, store_name, token, is_active, is_approved, username, area_text FROM stores WHERE admin_id=%s", (chat_id,))
                stores = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not stores:
            control_bot.reply_to(
                message,
                "❌ ምንም ሱቅ አልተመዘገቡም።\n\n"
                "📌 አዲስ ሱቅ ለመመዝገብ '📝 አዲስ ሱቅ መዝግብ' ይጫኑ"
            )
            return
        
        text = "🏪 **ሱቆችዎ:**\n\n"
        for store_id, name, token, is_active, is_approved, username, area in stores:
            status = "🟢" if is_active == 1 else "🔴"
            approved = "✅" if is_approved == 1 else "⏳"
            text += f"{status} {approved} **{name}**\n"
            text += f"  👤 @{username if username else 'ስም'}\n"
            text += f"  📍 {area if area else 'አልተዘጋጀም'}\n"
            text += f"  🆔 #{store_id}\n\n"
        
        control_bot.reply_to(message, text)

    @control_bot.message_handler(func=lambda m: m.text == "🔍 ሱቆችን ፈልግ")
    def search_stores_control(message):
        chat_id = message.chat.id
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📝 በስም ፈልግ", callback_data="csearch_name"),
            types.InlineKeyboardButton("📍 በአካባቢ ፈልግ", callback_data="csearch_location")
        )
        control_bot.send_message(
            chat_id,
            "🔍 **ሱቆችን ፈልግ**\n\nበስም ወይም በአካባቢ መፈለግ ይችላሉ",
            reply_markup=markup
        )

    @control_bot.callback_query_handler(func=lambda call: call.data.startswith("csearch_"))
    def handle_control_search(call):
        chat_id = call.message.chat.id
        
        if call.data == "csearch_name":
            msg = control_bot.send_message(chat_id, "📝 የሱቅ ስም ያስገቡ:")
            control_bot.register_next_step_handler(msg, process_control_search_name)
        elif call.data == "csearch_location":
            loc_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            loc_markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
            control_bot.send_message(chat_id, "📍 አካባቢ ያጋሩ:", reply_markup=loc_markup)

    def process_control_search_name(message):
        chat_id = message.chat.id
        query = message.text.strip()
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""SELECT store_name, username, area_text, shop_description, is_active, is_approved
                                  FROM stores 
                                  WHERE (store_name ILIKE %s OR username ILIKE %s) AND is_approved = 1
                                  LIMIT 10""", (f"%{query}%", f"%{query}%"))
                stores = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not stores:
            control_bot.reply_to(message, "🔍 ምንም ሱቅ አልተገኘም")
            return
        
        text = "🔍 **የተገኙ ሱቆች:**\n\n"
        for name, username, area, desc, active, approved in stores:
            status = "🟢" if active == 1 else "🔴"
            text += f"{status} **{name}**\n"
            text += f"  👤 @{username if username else 'ስም'}\n"
            text += f"  📍 {area if area else 'አልተዘጋጀም'}\n\n"
        
        control_bot.reply_to(message, text)

    @control_bot.message_handler(content_types=['location'])
    def handle_control_location_search(message):
        chat_id = message.chat.id
        lat = message.location.latitude
        lng = message.location.longitude
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""SELECT store_name, username, area_text, shop_description, is_active
                                  FROM stores 
                                  WHERE shop_lat IS NOT NULL AND shop_lng IS NOT NULL AND is_approved = 1
                                  AND (6371 * acos(cos(radians(%s)) * cos(radians(shop_lat)) * 
                                   cos(radians(shop_lng) - radians(%s)) + sin(radians(%s)) * 
                                   sin(radians(shop_lat)))) < 10
                                  LIMIT 10""", (lat, lng, lat))
                stores = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not stores:
            control_bot.reply_to(message, "🔍 በአቅራቢያ ምንም ሱቅ አልተገኘም")
            return
        
        text = "📍 **በአቅራቢያ ያሉ ሱቆች:**\n\n"
        for name, username, area, desc, active in stores:
            status = "🟢" if active == 1 else "🔴"
            text += f"{status} **{name}**\n"
            text += f"  👤 @{username if username else 'ስም'}\n"
            text += f"  📍 {area if area else 'አልተዘጋጀም'}\n\n"
        
        control_bot.reply_to(message, text)

    @control_bot.message_handler(func=lambda m: m.text == "❓ እርዳታ")
    def control_help_btn(message):
        control_help(message)

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
    RAW_TOKENS = os.environ.get("BOT_TOKENS", "")
    if RAW_TOKENS:
        for t in [x.strip() for x in RAW_TOKENS.split(",") if x.strip()]:
            start_shop_bot(t)

while True:
    time.sleep(3600)
