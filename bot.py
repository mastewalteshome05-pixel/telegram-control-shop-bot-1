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
                                name_or TEXT,
                                price REAL,
                                stock INTEGER,
                                desc_am TEXT,
                                desc_en TEXT,
                                desc_or TEXT,
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
                                status_or TEXT,
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

            # Promo codes / Coupons
            cursor.execute('''CREATE TABLE IF NOT EXISTS coupons (
                                id SERIAL PRIMARY KEY,
                                code TEXT UNIQUE,
                                discount_percent INTEGER,
                                valid_until TIMESTAMP,
                                used_by BIGINT[] DEFAULT '{}',
                                store_token TEXT)''')

            # User points / Rewards
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

ORDER_STAGES = {
    "am": ["🟡 በመጠባበቅ ላይ", "✅ ተረጋግጧል", "🚚 በመንገድ ላይ", "📦 ደርሷል"],
    "en": ["🟡 Pending", "✅ Confirmed", "🚚 On the way", "📦 Delivered"],
    "or": ["🟡 Eegamaa", "✅ Mirkanaa'e", "🚚 Karaa irra", "📦 Gahe"]
}

# ============================================================
# 5. MULTI-LANGUAGE SUPPORT - Amharic, Oromo, English
# ============================================================
STRINGS = {
    "am": {
        "welcome": "እንኳን ወደ EthioSuq - የኢትዮጵያ ገበያ በደህና መጡ! 👋",
        "explore_stores": "🏪 ሱቆችን አስስ",
        "ai_search": "🔍 AI ፍለጋ",
        "trending": "🔥 ተወዳጅ ምርቶች",
        "deals": "🎁 ቅናሾች",
        "cart": "🛒 ጋሪዬ",
        "orders": "📦 ትዕዛዞቼ",
        "favorites": "❤️ ተወዳጆች",
        "reviews": "⭐ ግምገማዎች",
        "register_store": "➕ ሱቅ መዝግብ",
        "profile": "👤 መገለጫዬ",
        "notifications": "🔔 ማስታወቂያዎች",
        "support": "📞 ድጋፍ",
        "coupons": "🎟 ኩፖኖች",
        "rewards": "🎯 ሽልማቶች",
        "empty_cart": "🛒 ጋሪዎ ባዶ ነው",
        "added_to_cart": "✅ ወደ ጋሪ ተጨምሯል",
        "checkout": "💳 ሂሳብ አስተካክል",
        "total": "አጠቃላይ",
        "price": "ዋጋ",
        "stock": "ክምችት",
        "in_stock": "✅ አለ",
        "out_of_stock": "❌ የለም",
        "phone_share": "📱 ስልክ ቁጥሬን አጋራ",
        "location_share": "📍 አካባቢዬን አጋራ",
        "phone_required": "📱 እባክዎ ስልክ ቁጥርዎን ያጋሩ",
        "location_required": "📍 እባክዎ አካባቢዎን ያጋሩ",
        "phone_saved": "✅ ስልክ ቁጥርዎ ተቀምጧል",
        "location_saved": "✅ አካባቢዎ ተቀምጧል",
        "order_placed": "✅ ትዕዛዝዎ ተላኩልናል!",
        "order_id": "🆔 የትዕዛዝ ቁጥር",
        "delivery_fee": "🚚 የማድረሻ ዋጋ",
        "grand_total": "💰 አጠቃላይ የሚከፈል",
        "receipt_prompt": "📸 የክፍያ ደረሰኝ ይላኩ",
        "categories": ["ሁሉም", "ኤሌክትሮኒክስ", "ልብስ", "ውበት", "ምግብ", "ቤት", "ስፖርት"],
        "trending_title": "🔥 በዛሬው ቀን ተወዳጅ ምርቶች",
        "deals_title": "🎁 ልዩ ቅናሾች እና ፕሮሞሽኖች",
        "no_stores": "🏪 ምንም የተመዘገበ ሱቅ የለም",
        "no_products": "📦 ምንም ምርት የለም",
        "pending_orders": "🟡 በመጠባበቅ ላይ",
        "delivered_orders": "📦 የደረሱ",
        "cancelled_orders": "❌ የተሰረዙ",
        "search_prompt": "🔍 ምን ይፈልጋሉ?",
        "coupon_title": "🎟 የእኔ ኩፖኖች",
        "rewards_title": "🎯 የእኔ ሽልማቶች",
        "points": "ነጥቦች",
        "no_coupons": "ምንም ኩፖን የለም",
        "no_rewards": "ምንም ሽልማት የለም"
    },
    "or": {
        "welcome": "EthioSuq - Gabaa Itoophiyaatti baga nagaan dhufte! 👋",
        "explore_stores": "🏪 Dukaaneen",
        "ai_search": "🔍 AI Barbaadaa",
        "trending": "🔥 Oomishaalee beekamoo",
        "deals": "🎁 Gatii qabsiisa",
        "cart": "🛒 Kaartii koo",
        "orders": "📦 Ajajawwan koo",
        "favorites": "❤️ Jaallatamoo",
        "reviews": "⭐ Madaallii",
        "register_store": "➕ Dukaana galmeessuu",
        "profile": "👤 Pr'oofayilii koo",
        "notifications": "🔔 Beeksisaa",
        "support": "📞 Gargaarsa",
        "coupons": "🎟 Kuupoonii",
        "rewards": "🎯 Badhaasa",
        "empty_cart": "🛒 Kaartiin kee duwwaa dha",
        "added_to_cart": "✅ Kaartii keessatti dabale",
        "checkout": "💳 Kaffaltii",
        "total": "Walumaa galatti",
        "price": "Gatii",
        "stock": "Kumsi",
        "in_stock": "✅ Jira",
        "out_of_stock": "❌ Hin jiru",
        "phone_share": "📱 Lakkoobsa bilbilaa koo qoodhu",
        "location_share": "📍 iddoo koo qoodhu",
        "phone_required": "📱 Lakkoobsa bilbilaa keessan qoodhaa",
        "location_required": "📍 Iddoo keessan qoodhaa",
        "phone_saved": "✅ Lakkoobsi bilbilaa keessan qabameera",
        "location_saved": "✅ Iddoon keessan qabameera",
        "order_placed": "✅ Ajajni keessan ergameera!",
        "order_id": "🆔 Lakkoobsa ajaja",
        "delivery_fee": "🚚 Gatii naannoo",
        "grand_total": "💰 Walumaa galatti kaffaltii",
        "receipt_prompt": "📸 Rasiidii kaffaltii ergaa",
        "categories": ["Hunda", "Elek'irooniks", "Uffata", "Miidhagina", "Nyaata", "Mana", "Isporti"],
        "trending_title": "🔥 Oomishaaleen har'aa beekamoo",
        "deals_title": "🎁 Gatii qabsiisa addaa",
        "no_stores": "🏪 Dukaan tokko iyyuu hin galmeessine",
        "no_products": "📦 Oomisha tokko iyyuu hin jiru",
        "pending_orders": "🟡 Eegamaa",
        "delivered_orders": "📦 Gahe",
        "cancelled_orders": "❌ Haqame",
        "search_prompt": "🔍 Maal barbaadda?",
        "coupon_title": "🎟 Kuupoonii koo",
        "rewards_title": "🎯 Badhaasa koo",
        "points": "P'uuntii",
        "no_coupons": "Kuupoonii tokko iyyuu hin jiru",
        "no_rewards": "Badhaasa tokko iyyuu hin jiru"
    },
    "en": {
        "welcome": "Welcome to EthioSuq - Ethiopia's Marketplace! 👋",
        "explore_stores": "🏪 Explore Stores",
        "ai_search": "🔍 AI Search",
        "trending": "🔥 Trending Products",
        "deals": "🎁 Deals & Offers",
        "cart": "🛒 My Cart",
        "orders": "📦 My Orders",
        "favorites": "❤️ Favorites",
        "reviews": "⭐ Reviews",
        "register_store": "➕ Register Store",
        "profile": "👤 My Profile",
        "notifications": "🔔 Notifications",
        "support": "📞 Support",
        "coupons": "🎟 Coupons",
        "rewards": "🎯 Rewards",
        "empty_cart": "🛒 Your cart is empty",
        "added_to_cart": "✅ Added to cart",
        "checkout": "💳 Checkout",
        "total": "Total",
        "price": "Price",
        "stock": "Stock",
        "in_stock": "✅ In Stock",
        "out_of_stock": "❌ Out of Stock",
        "phone_share": "📱 Share My Phone",
        "location_share": "📍 Share My Location",
        "phone_required": "📱 Please share your phone number",
        "location_required": "📍 Please share your location",
        "phone_saved": "✅ Phone number saved",
        "location_saved": "✅ Location saved",
        "order_placed": "✅ Order placed!",
        "order_id": "🆔 Order ID",
        "delivery_fee": "🚚 Delivery Fee",
        "grand_total": "💰 Grand Total",
        "receipt_prompt": "📸 Send payment receipt",
        "categories": ["All", "Electronics", "Fashion", "Beauty", "Food", "Home", "Sports"],
        "trending_title": "🔥 Today's Trending Products",
        "deals_title": "🎁 Special Deals & Promotions",
        "no_stores": "🏪 No stores registered",
        "no_products": "📦 No products available",
        "pending_orders": "🟡 Pending",
        "delivered_orders": "📦 Delivered",
        "cancelled_orders": "❌ Cancelled",
        "search_prompt": "🔍 What are you looking for?",
        "coupon_title": "🎟 My Coupons",
        "rewards_title": "🎯 My Rewards",
        "points": "Points",
        "no_coupons": "No coupons available",
        "no_rewards": "No rewards yet"
    }
}

# ============================================================
# 6. ETHIOSUQ MARKETPLACE BOT
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

    # ============================================================
    # 6.1 LANGUAGE SELECTION
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

    # ============================================================
    # 6.2 MAIN MENU
    # ============================================================
    def get_main_menu(lang):
        s = STRINGS[lang]
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton(s["explore_stores"]),
            types.KeyboardButton(s["ai_search"]),
            types.KeyboardButton(s["trending"]),
            types.KeyboardButton(s["deals"])
        )
        markup.add(
            types.KeyboardButton(s["cart"]),
            types.KeyboardButton(s["orders"]),
            types.KeyboardButton(s["favorites"]),
            types.KeyboardButton(s["reviews"])
        )
        markup.add(
            types.KeyboardButton(s["register_store"]),
            types.KeyboardButton(s["profile"]),
            types.KeyboardButton(s["notifications"]),
            types.KeyboardButton(s["support"])
        )
        markup.add(
            types.KeyboardButton(s["coupons"]),
            types.KeyboardButton(s["rewards"])
        )
        return markup

    # ============================================================
    # 6.3 START / LANGUAGE
    # ============================================================
    @bot.message_handler(commands=['start'])
    def start_message(message):
        chat_id = message.chat.id
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="lang_am"),
            types.InlineKeyboardButton("Afaan Oromoo 🇪🇹", callback_data="lang_or"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")
        )
        bot.send_message(
            chat_id,
            "🌍 **ቋንቋ ይምረጡ / Afaan filadhu / Select Language**",
            reply_markup=markup,
            parse_mode="Markdown"
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
    def set_language(call):
        chat_id = call.message.chat.id
        lang = call.data.split("_")[1]
        set_user_lang(chat_id, lang)
        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(chat_id, STRINGS[lang]["welcome"], reply_markup=get_main_menu(lang))
        bot.answer_callback_query(call.id)

    # ============================================================
    # 6.4 EXPLORE STORES
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["explore_stores"])
    def explore_stores(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, store_name, category, area_text, shop_photo, rating, username FROM stores WHERE is_approved=1 AND is_active=1 ORDER BY rating DESC")
                stores = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not stores:
            bot.send_message(chat_id, STRINGS[lang]["no_stores"])
            return
        
        # Category filter
        categories = STRINGS[lang]["categories"]
        markup = types.InlineKeyboardMarkup(row_width=3)
        for cat in categories:
            markup.add(types.InlineKeyboardButton(cat, callback_data=f"storecat_{cat}"))
        
        bot.send_message(chat_id, "📂 **Filter by Category:**", reply_markup=markup)
        
        for store_id, name, category, area, photo, rating, username in stores[:10]:
            stars = "⭐" * int(rating) if rating else "⭐" * 0
            text = f"🏪 **{name}**\n📂 {category or 'General'}\n📍 {area or 'Not specified'}\n{stars} ({rating or 0})\n"
            markup = types.InlineKeyboardMarkup()
            if username:
                markup.add(types.InlineKeyboardButton("🛍️ Visit Store", url=f"https://t.me/{username}"))
            markup.add(types.InlineKeyboardButton("❤️ Favorite", callback_data=f"favstore_{store_id}"))
            
            if photo:
                try:
                    bot.send_photo(chat_id, photo, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("storecat_"))
    def filter_stores_by_category(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        category = call.data.split("_")[1]
        
        if category == "ሁሉም" or category == "Hunda" or category == "All":
            category = None
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                if category:
                    cursor.execute("SELECT id, store_name, area_text, shop_photo, rating, username FROM stores WHERE is_approved=1 AND is_active=1 AND category=%s ORDER BY rating DESC", (category,))
                else:
                    cursor.execute("SELECT id, store_name, area_text, shop_photo, rating, username FROM stores WHERE is_approved=1 AND is_active=1 ORDER BY rating DESC")
                stores = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not stores:
            bot.send_message(chat_id, STRINGS[lang]["no_stores"])
            return
        
        for store_id, name, area, photo, rating, username in stores[:10]:
            stars = "⭐" * int(rating) if rating else ""
            text = f"🏪 **{name}**\n📍 {area or 'Not specified'}\n{stars}\n"
            markup = types.InlineKeyboardMarkup()
            if username:
                markup.add(types.InlineKeyboardButton("🛍️ Visit", url=f"https://t.me/{username}"))
            if photo:
                try:
                    bot.send_photo(chat_id, photo, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    # ============================================================
    # 6.5 AI SEARCH
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["ai_search"])
    def ai_search_prompt(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        msg = bot.send_message(chat_id, STRINGS[lang]["search_prompt"])
        bot.register_next_step_handler(msg, ai_search_run)

    def ai_search_run(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        query = message.text.strip()
        
        # Use AI if available
        if ai_model:
            try:
                bot.send_chat_action(chat_id, 'typing')
                system_prompt = f"You are EthioSuq AI assistant. User asked: '{query}'. Search in Ethiopian marketplace context. Suggest products, stores, or deals in {lang}. Keep response concise and helpful."
                response = ai_model.generate_content(system_prompt)
                bot.reply_to(message, f"🤖 **AI Search Results:**\n\n{response.text[:500]}")
                return
            except:
                pass
        
        # Fallback: search in database
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT p.name_am, p.name_en, p.name_or, p.price, p.stock, p.image_url, s.store_name
                                  FROM products p JOIN stores s ON p.token = s.token
                                  WHERE s.is_approved=1 AND s.is_active=1 AND p.stock > 0
                                  AND (p.name_am ILIKE %s OR p.name_en ILIKE %s OR p.name_or ILIKE %s OR p.desc_am ILIKE %s OR p.desc_en ILIKE %s OR p.desc_or ILIKE %s)
                                  LIMIT 10''', (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
                results = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not results:
            bot.reply_to(message, "🔍 No results found. Try a different search term.")
            return
        
        for name_am, name_en, name_or, price, stock, image_url, store_name in results:
            name = name_am if lang == "am" else name_or if lang == "or" else name_en
            text = f"📦 **{name}**\n💰 {price} ETB\n🏪 {store_name}\n📌 {STRINGS[lang]['in_stock'] if stock > 0 else STRINGS[lang]['out_of_stock']}"
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, parse_mode="Markdown")

    # ============================================================
    # 6.6 TRENDING PRODUCTS
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["trending"])
    def trending_products(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT p.id, p.name_am, p.name_en, p.name_or, p.price, p.image_url, s.store_name, p.views
                                  FROM products p JOIN stores s ON p.token = s.token
                                  WHERE s.is_approved=1 AND s.is_active=1 AND p.stock > 0
                                  ORDER BY p.views DESC, p.id DESC LIMIT 10''')
                products = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not products:
            bot.send_message(chat_id, STRINGS[lang]["no_products"])
            return
        
        bot.send_message(chat_id, STRINGS[lang]["trending_title"], parse_mode="Markdown")
        
        for p_id, name_am, name_en, name_or, price, image_url, store_name, views in products:
            name = name_am if lang == "am" else name_or if lang == "or" else name_en
            text = f"📦 **{name}**\n💰 {price} ETB\n🏪 {store_name}\n👁️ {views} views"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🛒 Add to Cart", callback_data=f"addprod_{p_id}"))
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    # ============================================================
    # 6.7 DEALS & OFFERS
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["deals"])
    def deals_products(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT p.id, p.name_am, p.name_en, p.name_or, p.price, p.discount_percent, p.image_url, s.store_name
                                  FROM products p JOIN stores s ON p.token = s.token
                                  WHERE s.is_approved=1 AND s.is_active=1 AND p.stock > 0 AND p.discount_percent > 0
                                  ORDER BY p.discount_percent DESC LIMIT 10''')
                deals = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not deals:
            bot.send_message(chat_id, "🎁 No deals available right now.")
            return
        
        bot.send_message(chat_id, STRINGS[lang]["deals_title"], parse_mode="Markdown")
        
        for p_id, name_am, name_en, name_or, price, discount, image_url, store_name in deals:
            name = name_am if lang == "am" else name_or if lang == "or" else name_en
            discounted_price = price * (1 - discount / 100)
            text = f"📦 **{name}**\n💰 ~~{price} ETB~~ → **{discounted_price:.0f} ETB** ({discount}% OFF)\n🏪 {store_name}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🛒 Add to Cart", callback_data=f"addprod_{p_id}"))
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    # ============================================================
    # 6.8 CART
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["cart"])
    def show_cart(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        cart = user_carts.get(chat_id, {})
        
        if not cart:
            bot.send_message(chat_id, STRINGS[lang]["empty_cart"])
            return
        
        total = 0
        text = "🛒 **Your Cart**\n\n"
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                for p_id, qty in list(cart.items()):
                    cursor.execute("SELECT name_am, name_en, name_or, price, token FROM products WHERE id=%s", (p_id,))
                    row = cursor.fetchone()
                    if row:
                        name_am, name_en, name_or, price, token = row
                        name = name_am if lang == "am" else name_or if lang == "or" else name_en
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
            types.InlineKeyboardButton(STRINGS[lang]["checkout"], callback_data="checkout"),
            types.InlineKeyboardButton("🗑️ Clear", callback_data="clear_cart")
        )
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("addprod_"))
    def add_to_cart_callback(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        p_id = int(call.data.split("_")[1])
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT stock FROM products WHERE id=%s", (p_id,))
                row = cursor.fetchone()
                if not row or row[0] <= 0:
                    bot.answer_callback_query(call.id, "❌ Out of stock")
                    return
        finally:
            put_conn(conn)
        
        if chat_id not in user_carts:
            user_carts[chat_id] = {}
        user_carts[chat_id][p_id] = user_carts[chat_id].get(p_id, 0) + 1
        
        bot.answer_callback_query(call.id, STRINGS[lang]["added_to_cart"])

    @bot.callback_query_handler(func=lambda call: call.data == "clear_cart")
    def clear_cart(call):
        chat_id = call.message.chat.id
        user_carts.pop(chat_id, None)
        bot.edit_message_text("🛒 Cart cleared!", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "checkout")
    def checkout_cart(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        cart = user_carts.get(chat_id, {})
        
        if not cart:
            bot.answer_callback_query(call.id, "❌ Cart is empty")
            return
        
        # Check if user has phone and location
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT phone, lat, lng FROM customer_info WHERE chat_id=%s", (chat_id,))
                row = cursor.fetchone()
        finally:
            put_conn(conn)
        
        if not row or not row[0] or not row[1]:
            # Request phone and location
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            if not row or not row[0]:
                markup.add(types.KeyboardButton(STRINGS[lang]["phone_share"], request_contact=True))
            if not row or not row[1]:
                markup.add(types.KeyboardButton(STRINGS[lang]["location_share"], request_location=True))
            bot.send_message(
                chat_id,
                f"📱 {STRINGS[lang]['phone_required']}\n📍 {STRINGS[lang]['location_required']}",
                reply_markup=markup
            )
            admin_states[chat_id] = {"state": "PENDING_CHECKOUT"}
            bot.answer_callback_query(call.id)
            return
        
        # Proceed with checkout
        finalize_checkout(chat_id, lang, call)

    def finalize_checkout(chat_id, lang, call=None):
        cart = user_carts.get(chat_id, {})
        if not cart:
            return
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT phone, lat, lng FROM customer_info WHERE chat_id=%s", (chat_id,))
                cust_info = cursor.fetchone()
                
                items_total = 0
                order_lines = []
                
                for p_id, qty in list(cart.items()):
                    cursor.execute("SELECT price, stock, token FROM products WHERE id=%s FOR UPDATE", (p_id,))
                    row = cursor.fetchone()
                    if not row:
                        continue
                    price, stock, token = row
                    buy_qty = min(qty, stock)
                    if buy_qty <= 0:
                        continue
                    items_total += price * buy_qty
                    order_lines.append((p_id, buy_qty, price, token))
                
                if not order_lines:
                    conn.rollback()
                    bot.send_message(chat_id, "❌ Some items are out of stock")
                    return
                
                # Calculate delivery fee
                delivery_fee = 0
                dist_note = ""
                if cust_info and cust_info[1] and cust_info[2]:
                    store_token = order_lines[0][3]
                    cursor.execute("SELECT shop_lat, shop_lng FROM stores WHERE token=%s", (store_token,))
                    store_loc = cursor.fetchone()
                    if store_loc and store_loc[0]:
                        dist = calculate_distance_km(store_loc[0], store_loc[1], cust_info[1], cust_info[2])
                        delivery_fee = calculate_delivery_fee(dist)
                        dist_note = f"📏 {dist:.1f} km\n🚚 {delivery_fee} ETB\n"
                
                grand_total = items_total + delivery_fee
                
                cursor.execute('''INSERT INTO orders (token, customer_id, status_am, status_en, status_or, total_price, delivery_fee, status_stage)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, 0) RETURNING id''',
                               (order_lines[0][3], chat_id, ORDER_STAGES["am"][0], ORDER_STAGES["en"][0], ORDER_STAGES["or"][0], items_total, delivery_fee))
                order_id = cursor.fetchone()[0]
                
                for p_id, buy_qty, price, token in order_lines:
                    cursor.execute("INSERT INTO order_items (order_id, product_id, qty, price) VALUES (%s, %s, %s, %s)",
                                   (order_id, p_id, buy_qty, price))
                    cursor.execute("UPDATE products SET stock = stock - %s, views = views + 1 WHERE id=%s", (buy_qty, p_id))
                
                # Add points
                points_earned = int(grand_total / 10)
                cursor.execute('''INSERT INTO user_points (chat_id, points) VALUES (%s, %s)
                                  ON CONFLICT (chat_id) DO UPDATE SET points = points + EXCLUDED.points''',
                               (chat_id, points_earned))
                
                conn.commit()
                
                # Get store info for payment
                cursor.execute("SELECT telebirr, cbebirr, store_name FROM stores WHERE token=%s", (order_lines[0][3],))
                store = cursor.fetchone()
                
        finally:
            put_conn(conn)
        
        user_carts.pop(chat_id, None)
        
        pay_text = f"🆔 **Order #{order_id}**\n\n💵 Items: {items_total} ETB\n{dist_note}💰 **Total: {grand_total} ETB**\n\n"
        if store:
            pay_text += f"📱 Telebirr: `{store[0]}`\n"
            if store[1]:
                pay_text += f"🏦 CBE Birr: `{store[1]}`\n"
            pay_text += f"\n📸 {STRINGS[lang]['receipt_prompt']}"
        
        if call:
            try:
                bot.edit_message_text(pay_text, chat_id, call.message.message_id, parse_mode="Markdown")
            except:
                bot.send_message(chat_id, pay_text, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, pay_text, parse_mode="Markdown")
        
        admin_states[chat_id] = {"state": f"AWAITING_RECEIPT_{order_id}"}
        
        # Create notification
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO notifications (chat_id, title, message) VALUES (%s, %s, %s)''',
                               (chat_id, "🛒 Order Placed", f"Your order #{order_id} has been placed successfully!"))
                conn.commit()
        finally:
            put_conn(conn)

    # ============================================================
    # 6.9 ORDERS
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["orders"])
    def show_orders(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT id, status_am, status_en, status_or, total_price, delivery_fee, status_stage, created_at
                                  FROM orders WHERE customer_id=%s ORDER BY id DESC LIMIT 20''', (chat_id,))
                orders = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not orders:
            bot.send_message(chat_id, "📦 No orders found.")
            return
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🟡 Pending", callback_data="filter_pending"),
            types.InlineKeyboardButton("📦 Delivered", callback_data="filter_delivered"),
            types.InlineKeyboardButton("❌ Cancelled", callback_data="filter_cancelled")
        )
        bot.send_message(chat_id, "📦 **Filter Orders:**", reply_markup=markup)
        
        for order in orders:
            order_id, status_am, status_en, status_or, total, fee, stage, created = order
            status = status_am if lang == "am" else status_or if lang == "or" else status_en
            stage_label = ORDER_STAGES[lang][stage] if 0 <= stage <= 3 else status
            text = f"🆔 **#{order_id}**\n💵 {total + (fee or 0)} ETB\n📌 {stage_label}\n📅 {created}"
            bot.send_message(chat_id, text, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("filter_"))
    def filter_orders(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        filter_type = call.data.split("_")[1]
        
        stage_map = {
            "pending": 0,
            "delivered": 3,
            "cancelled": -1
        }
        stage = stage_map.get(filter_type)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                if stage == -1:
                    cursor.execute('''SELECT id, status_am, status_en, status_or, total_price, delivery_fee, status_stage, created_at
                                      FROM orders WHERE customer_id=%s AND status_stage=-1 ORDER BY id DESC''', (chat_id,))
                else:
                    cursor.execute('''SELECT id, status_am, status_en, status_or, total_price, delivery_fee, status_stage, created_at
                                      FROM orders WHERE customer_id=%s AND status_stage=%s ORDER BY id DESC''', (chat_id, stage))
                orders = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not orders:
            bot.send_message(chat_id, "📦 No orders in this category.")
            return
        
        for order in orders:
            order_id, status_am, status_en, status_or, total, fee, stage, created = order
            status = status_am if lang == "am" else status_or if lang == "or" else status_en
            stage_label = ORDER_STAGES[lang][stage] if 0 <= stage <= 3 else status
            text = f"🆔 **#{order_id}**\n💵 {total + (fee or 0)} ETB\n📌 {stage_label}\n📅 {created}"
            bot.send_message(chat_id, text, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    # ============================================================
    # 6.10 FAVORITES
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["favorites"])
    def show_favorites(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                # Product favorites
                cursor.execute('''SELECT p.id, p.name_am, p.name_en, p.name_or, p.price, p.image_url, s.store_name
                                  FROM favorites f JOIN products p ON f.product_id = p.id
                                  JOIN stores s ON p.token = s.token
                                  WHERE f.chat_id=%s AND s.is_active=1
                                  ORDER BY f.created_at DESC LIMIT 10''', (chat_id,))
                products = cursor.fetchall()
                
                # Store favorites
                cursor.execute('''SELECT s.id, s.store_name, s.shop_photo, s.rating, s.username
                                  FROM favorite_stores fs JOIN stores s ON fs.store_token = s.token
                                  WHERE fs.chat_id=%s AND s.is_active=1''', (chat_id,))
                stores = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not products and not stores:
            bot.send_message(chat_id, "❤️ No favorites yet.")
            return
        
        if products:
            text = "📦 **Favorite Products:**\n\n"
            for p_id, name_am, name_en, name_or, price, image_url, store_name in products:
                name = name_am if lang == "am" else name_or if lang == "or" else name_en
                text += f"▪️ {name} - {price} ETB ({store_name})\n"
            bot.send_message(chat_id, text, parse_mode="Markdown")
        
        if stores:
            text = "🏪 **Favorite Stores:**\n\n"
            for store_id, name, photo, rating, username in stores:
                stars = "⭐" * int(rating) if rating else ""
                text += f"▪️ {name} {stars}\n"
            bot.send_message(chat_id, text, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("favstore_"))
    def favorite_store(call):
        chat_id = call.message.chat.id
        store_id = int(call.data.split("_")[1])
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT token FROM stores WHERE id=%s", (store_id,))
                row = cursor.fetchone()
                if row:
                    cursor.execute('''INSERT INTO favorite_stores (chat_id, store_token) VALUES (%s, %s)
                                      ON CONFLICT (chat_id, store_token) DO NOTHING''', (chat_id, row[0]))
                    conn.commit()
        finally:
            put_conn(conn)
        bot.answer_callback_query(call.id, "❤️ Store added to favorites!")

    # ============================================================
    # 6.11 REVIEWS
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["reviews"])
    def show_reviews(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT r.id, r.rating, r.comment, r.created_at, s.store_name, p.name_am, p.name_en, p.name_or
                                  FROM reviews r 
                                  LEFT JOIN stores s ON r.token = s.token
                                  LEFT JOIN products p ON r.product_id = p.id
                                  WHERE r.chat_id=%s
                                  ORDER BY r.created_at DESC LIMIT 10''', (chat_id,))
                reviews = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not reviews:
            bot.send_message(chat_id, "⭐ No reviews yet.")
            return
        
        text = "⭐ **Your Reviews:**\n\n"
        for rev_id, rating, comment, created, store_name, p_am, p_en, p_or in reviews:
            stars = "⭐" * rating
            prod_name = p_am if lang == "am" else p_or if lang == "or" else p_en
            text += f"🏪 {store_name or 'Unknown'}\n"
            if prod_name:
                text += f"📦 {prod_name}\n"
            text += f"{stars}\n📝 {comment[:100] if comment else 'No comment'}\n📅 {created}\n\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")

    # ============================================================
    # 6.12 REGISTER STORE (with phone & location buttons)
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["register_store"])
    def register_wizard_start(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        reg_wizard_states[chat_id] = {"data": {}}
        
        msg = bot.send_message(chat_id, "🏪 **Step 1/7: Store Name**\n\nEnter store name:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, reg_w_store_name)

    def reg_w_store_name(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        reg_wizard_states[chat_id]["data"]["store_name"] = message.text.strip()
        msg = bot.send_message(chat_id, "👤 **Step 2/7: Owner Name**\n\nEnter your full name:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, reg_w_owner_name)

    def reg_w_owner_name(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        reg_wizard_states[chat_id]["data"]["owner_name"] = message.text.strip()
        
        # Phone number with button
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton(STRINGS[lang]["phone_share"], request_contact=True))
        msg = bot.send_message(chat_id, f"📱 **Step 3/7: Phone Number**\n\n{STRINGS[lang]['phone_required']}", reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(msg, reg_w_phone)

    def reg_w_phone(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        if message.contact:
            phone = message.contact.phone_number
        else:
            phone = message.text.strip()
        
        reg_wizard_states[chat_id]["data"]["owner_phone"] = phone
        
        # Location with button
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton(STRINGS[lang]["location_share"], request_location=True))
        msg = bot.send_message(chat_id, f"📍 **Step 4/7: Location**\n\n{STRINGS[lang]['location_required']}", reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(msg, reg_w_location)

    def reg_w_location(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        data = reg_wizard_states[chat_id]["data"]
        
        if message.location:
            data["shop_lat"] = message.location.latitude
            data["shop_lng"] = message.location.longitude
            data["area_text"] = ""
        else:
            data["area_text"] = message.text.strip()
        
        markup = types.ReplyKeyboardRemove()
        msg = bot.send_message(chat_id, "🖼 **Step 5/7: Store Logo**\n\nSend a photo (or type 'skip'):", reply_markup=markup, parse_mode="Markdown")
        bot.register_next_step_handler(msg, reg_w_logo)

    def reg_w_logo(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        data = reg_wizard_states[chat_id]["data"]
        
        if message.photo:
            data["shop_photo"] = message.photo[-1].file_id
        else:
            data["shop_photo"] = ""
        
        msg = bot.send_message(chat_id, "🤖 **Step 6/7: Bot Token**\n\nEnter your Bot Token from @BotFather:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, reg_w_token)

    def reg_w_token(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        tok = message.text.strip()
        
        try:
            test_bot = telebot.TeleBot(tok)
            bot_info = test_bot.get_me()
        except:
            bot.reply_to(message, "❌ Invalid token. Please start over with /start")
            reg_wizard_states.pop(chat_id, None)
            return
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM stores WHERE token=%s", (tok,))
                if cursor.fetchone():
                    bot.reply_to(message, "❌ Token already registered.")
                    reg_wizard_states.pop(chat_id, None)
                    return
        finally:
            put_conn(conn)
        
        reg_wizard_states[chat_id]["data"]["token"] = tok
        reg_wizard_states[chat_id]["data"]["bot_username"] = bot_info.username
        msg = bot.send_message(chat_id, f"✅ Token verified! (@{bot_info.username})\n\n📝 **Step 7/7: Description**\n\nEnter store description:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, reg_w_description)

    def reg_w_description(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        data = reg_wizard_states[chat_id]["data"]
        data["shop_description"] = message.text.strip()
        
        # Ask for category
        categories = STRINGS[lang]["categories"]
        markup = types.InlineKeyboardMarkup(row_width=3)
        for cat in categories[1:]:  # Skip "All"
            markup.add(types.InlineKeyboardButton(cat, callback_data=f"regcat_{cat}"))
        
        msg = bot.send_message(chat_id, "📂 **Select Store Category:**", reply_markup=markup)
        bot.register_next_step_handler(msg, lambda m: reg_w_final(m, data))

    def reg_w_final(message, data):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        # If category selected via inline
        if message.text in STRINGS[lang]["categories"]:
            data["category"] = message.text
        else:
            data["category"] = "General"
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO stores
                                  (token, store_name, admin_id, username, owner_name, owner_phone,
                                   area_text, shop_lat, shop_lng, shop_photo, shop_description, category, is_approved)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)''',
                               (data["token"], data["store_name"], chat_id, data["bot_username"],
                                data["owner_name"], data["owner_phone"], data.get("area_text", ""),
                                data.get("shop_lat"), data.get("shop_lng"), data.get("shop_photo", ""),
                                data["shop_description"], data.get("category", "General")))
                conn.commit()
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {e}")
            reg_wizard_states.pop(chat_id, None)
            return
        finally:
            put_conn(conn)
        
        reg_wizard_states.pop(chat_id, None)
        bot.send_message(chat_id, "⏳ **Your application has been submitted.**\nWaiting for admin verification.", reply_markup=get_main_menu(lang), parse_mode="Markdown")
        
        # Notify super admin
        SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
        if SUPER_ADMIN_ID:
            try:
                bot.send_message(SUPER_ADMIN_ID, f"🔔 **New Store Application!**\n\n🏪 {data['store_name']}\n👤 {data['owner_name']}\n📱 {data['owner_phone']}\n\nCheck 🛡 Verification")
            except:
                pass

    @bot.callback_query_handler(func=lambda call: call.data.startswith("regcat_"))
    def reg_category_callback(call):
        chat_id = call.message.chat.id
        category = call.data.split("_")[1]
        
        if chat_id in reg_wizard_states:
            reg_wizard_states[chat_id]["data"]["category"] = category
        
        bot.answer_callback_query(call.id, f"✅ Category: {category}")
        
        # Continue to final step
        data = reg_wizard_states[chat_id]["data"]
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO stores
                                  (token, store_name, admin_id, username, owner_name, owner_phone,
                                   area_text, shop_lat, shop_lng, shop_photo, shop_description, category, is_approved)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)''',
                               (data["token"], data["store_name"], chat_id, data["bot_username"],
                                data["owner_name"], data["owner_phone"], data.get("area_text", ""),
                                data.get("shop_lat"), data.get("shop_lng"), data.get("shop_photo", ""),
                                data["shop_description"], category))
                conn.commit()
        except Exception as e:
            bot.send_message(chat_id, f"❌ Error: {e}")
            reg_wizard_states.pop(chat_id, None)
            return
        finally:
            put_conn(conn)
        
        lang = get_user_lang(chat_id)
        reg_wizard_states.pop(chat_id, None)
        bot.send_message(chat_id, "⏳ **Application submitted!** Waiting for verification.", reply_markup=get_main_menu(lang), parse_mode="Markdown")

    # ============================================================
    # 6.13 PROFILE
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["profile"])
    def show_profile(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT phone, lat, lng, username, full_name FROM customer_info WHERE chat_id=%s", (chat_id,))
                info = cursor.fetchone()
                
                cursor.execute("SELECT COUNT(*) FROM orders WHERE customer_id=%s", (chat_id,))
                order_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM stores WHERE admin_id=%s", (chat_id,))
                store_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT points FROM user_points WHERE chat_id=%s", (chat_id,))
                points_row = cursor.fetchone()
                points = points_row[0] if points_row else 0
        finally:
            put_conn(conn)
        
        text = "👤 **My Profile**\n\n"
        text += f"🆔 User ID: {chat_id}\n"
        text += f"📱 Phone: {info[0] if info else 'Not set'}\n"
        text += f"📍 Location: {'Set ✅' if info and info[1] else 'Not set'}\n"
        text += f"👤 Name: {info[3] if info else 'N/A'}\n"
        text += f"📦 Orders: {order_count}\n"
        text += f"🏪 Stores: {store_count}\n"
        text += f"🎯 Points: {points}\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")

    # ============================================================
    # 6.14 NOTIFICATIONS
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["notifications"])
    def show_notifications(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT id, title, message, created_at, is_read
                                  FROM notifications WHERE chat_id=%s
                                  ORDER BY created_at DESC LIMIT 20''', (chat_id,))
                notifs = cursor.fetchall()
                
                # Mark as read
                cursor.execute("UPDATE notifications SET is_read=1 WHERE chat_id=%s", (chat_id,))
                conn.commit()
        finally:
            put_conn(conn)
        
        if not notifs:
            bot.send_message(chat_id, "🔔 No notifications.")
            return
        
        text = "🔔 **Notifications:**\n\n"
        for n_id, title, msg, created, is_read in notifs:
            status = "📌" if is_read == 0 else "✅"
            text += f"{status} **{title}**\n{msg[:100]}\n📅 {created}\n\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")

    # ============================================================
    # 6.15 SUPPORT
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["support"])
    def show_support(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📞 Contact Admin", callback_data="contact_admin"),
            types.InlineKeyboardButton("❓ FAQ", callback_data="faq_support"),
            types.InlineKeyboardButton("📝 Report Problem", callback_data="report_problem")
        )
        bot.send_message(chat_id, "📞 **Support Center**\n\nChoose an option:", reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data in ["contact_admin", "faq_support", "report_problem"])
    def support_actions(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        
        if call.data == "contact_admin":
            bot.send_message(chat_id, "📞 **Contact Admin**\n\nSend a message here and we'll get back to you soon.")
        elif call.data == "faq_support":
            faq = "❓ **FAQ**\n\n1. **How to register a store?**\n   Use '➕ Register Store' button\n\n2. **How to track orders?**\n   Go to '📦 My Orders'\n\n3. **How to get discounts?**\n   Check '🎁 Deals' for offers\n\n4. **How to earn points?**\n   Every 10 ETB spent = 1 point"
            bot.send_message(chat_id, faq, parse_mode="Markdown")
        elif call.data == "report_problem":
            msg = bot.send_message(chat_id, "📝 **Report Problem**\n\nPlease describe your issue:")
            bot.register_next_step_handler(msg, report_problem_submit)
        bot.answer_callback_query(call.id)

    def report_problem_submit(message):
        chat_id = message.chat.id
        bot.send_message(chat_id, "✅ Thank you! Your report has been submitted. We'll look into it.")
        
        # Notify admin
        SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
        if SUPER_ADMIN_ID:
            try:
                bot.send_message(SUPER_ADMIN_ID, f"📝 **Problem Report**\n\nFrom: {chat_id}\n\n{message.text}")
            except:
                pass

    # ============================================================
    # 6.16 COUPONS
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["coupons"])
    def show_coupons(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT code, discount_percent, valid_until, store_token
                                  FROM coupons WHERE %s != ANY(used_by) AND valid_until > NOW()''', (chat_id,))
                coupons = cursor.fetchall()
        finally:
            put_conn(conn)
        
        if not coupons:
            bot.send_message(chat_id, STRINGS[lang]["no_coupons"])
            return
        
        text = "🎟 **My Coupons:**\n\n"
        for code, discount, valid_until, store_token in coupons:
            text += f"📌 **{code}** - {discount}% OFF\n🕐 Valid until: {valid_until}\n\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")

    # ============================================================
    # 6.17 REWARDS
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == STRINGS[get_user_lang(m.chat.id)]["rewards"])
    def show_rewards(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT points FROM user_points WHERE chat_id=%s", (chat_id,))
                row = cursor.fetchone()
                points = row[0] if row else 0
        finally:
            put_conn(conn)
        
        text = f"🎯 **{STRINGS[lang]['rewards_title']}**\n\n"
        text += f"📊 {STRINGS[lang]['points']}: {points}\n\n"
        
        if points >= 100:
            text += "🏅 **Bronze Level** - 5% discount\n"
        if points >= 250:
            text += "🥈 **Silver Level** - 10% discount\n"
        if points >= 500:
            text += "🥇 **Gold Level** - 15% discount\n"
        if points >= 1000:
            text += "💎 **Platinum Level** - 20% discount\n"
        
        text += f"\n💡 Earn {10} points for every 100 ETB spent!"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")

    # ============================================================
    # 6.18 HANDLE CONTACT & LOCATION SHARE
    # ============================================================
    @bot.message_handler(content_types=['contact'])
    def handle_contact_share(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        if message.contact and message.contact.user_id == message.from_user.id:
            save_customer_phone(chat_id, message.contact.phone_number)
            bot.send_message(chat_id, STRINGS[lang]["phone_saved"])
        
        # Check if in checkout flow
        if admin_states.get(chat_id, {}).get("state") == "PENDING_CHECKOUT":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT phone, lat, lng FROM customer_info WHERE chat_id=%s", (chat_id,))
                    row = cursor.fetchone()
            finally:
                put_conn(conn)
            
            if row and row[1] and row[2]:
                lang = get_user_lang(chat_id)
                finalize_checkout(chat_id, lang)
            else:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton(STRINGS[lang]["location_share"], request_location=True))
                bot.send_message(chat_id, STRINGS[lang]["location_required"], reply_markup=markup)

    @bot.message_handler(content_types=['location'])
    def handle_location_share(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        save_customer_location(chat_id, message.location.latitude, message.location.longitude)
        bot.send_message(chat_id, STRINGS[lang]["location_saved"])
        
        # Check if in checkout flow
        if admin_states.get(chat_id, {}).get("state") == "PENDING_CHECKOUT":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT phone, lat, lng FROM customer_info WHERE chat_id=%s", (chat_id,))
                    row = cursor.fetchone()
            finally:
                put_conn(conn)
            
            if row and row[0]:
                lang = get_user_lang(chat_id)
                finalize_checkout(chat_id, lang)
            else:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton(STRINGS[lang]["phone_share"], request_contact=True))
                bot.send_message(chat_id, STRINGS[lang]["phone_required"], reply_markup=markup)

    # ============================================================
    # 6.19 PHOTO HANDLER (Receipt)
    # ============================================================
    @bot.message_handler(content_types=['photo'])
    def handle_receipt(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        state = admin_states.get(chat_id, {}).get("state", "")
        
        if state.startswith("AWAITING_RECEIPT_"):
            order_id = int(state.split("_")[2])
            
            # Forward to store admin
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT token, total_price FROM orders WHERE id=%s", (order_id,))
                    row = cursor.fetchone()
                    if row:
                        token, total = row
                        cursor.execute("SELECT admin_id, store_name FROM stores WHERE token=%s", (token,))
                        store = cursor.fetchone()
                        if store:
                            admin_id, store_name = store
                            markup = types.InlineKeyboardMarkup()
                            markup.add(
                                types.InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{order_id}"),
                                types.InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{order_id}")
                            )
                            bot.send_photo(admin_id, message.photo[-1].file_id, caption=f"🛒 **New Payment Receipt**\nOrder #{order_id}\nStore: {store_name}\nTotal: {total} ETB", reply_markup=markup, parse_mode="Markdown")
                            
                            bot.reply_to(message, "✅ Receipt forwarded for verification.")
                            admin_states.pop(chat_id, None)
            finally:
                put_conn(conn)

    # ============================================================
    # 6.20 ADMIN CALLBACKS (Store approval from super admin)
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_approve_") or call.data.startswith("admin_reject_"))
    def admin_order_action(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        
        # Check if caller is super admin
        SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
        if chat_id != SUPER_ADMIN_ID:
            bot.answer_callback_query(call.id, "❌ Unauthorized")
            return
        
        action, order_id = call.data.split("_")[1], int(call.data.split("_")[2])
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                if action == "approve":
                    cursor.execute("UPDATE orders SET status_stage=1, status_am=%s, status_en=%s, status_or=%s WHERE id=%s",
                                   (ORDER_STAGES["am"][1], ORDER_STAGES["en"][1], ORDER_STAGES["or"][1], order_id))
                    conn.commit()
                    bot.send_message(chat_id, f"✅ Order #{order_id} approved!")
                else:
                    cursor.execute("UPDATE orders SET status_stage=-1, status_am=%s, status_en=%s, status_or=%s WHERE id=%s",
                                   ("❌ ውድቅ ተደርጓል", "❌ Rejected", "❌ Haqame", order_id))
                    
                    # Restore stock
                    cursor.execute('''UPDATE products p SET stock = stock + oi.qty
                                      FROM order_items oi
                                      WHERE oi.order_id=%s AND oi.product_id = p.id''', (order_id,))
                    conn.commit()
                    bot.send_message(chat_id, f"❌ Order #{order_id} rejected!")
        finally:
            put_conn(conn)
        
        bot.answer_callback_query(call.id)

    # ============================================================
    # 6.21 FALLBACK
    # ============================================================
    @bot.message_handler(func=lambda message: True)
    def fallback_handler(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        # Use AI if available
        if ai_model:
            try:
                bot.send_chat_action(chat_id, 'typing')
                response = ai_model.generate_content(f"You are EthioSuq assistant. Answer in {lang}: {message.text}")
                bot.reply_to(message, f"🤖 {response.text[:500]}")
                return
            except:
                pass
        
        bot.reply_to(message, "❓ Please use the menu buttons or type /start")

    # ============================================================
    # 6.22 START BOT
    # ============================================================
    def _run_bot():
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                print(f"⚠️ EthioSuq bot crashed: {e}. Restarting in 5s...")
                time.sleep(5)

    threading.Thread(target=_run_bot, name="EthioSuqBot", daemon=True).start()
    print("✅ EthioSuq Marketplace Bot is running!")

else:
    print("⚠️ CONTROL_BOT_TOKEN not set!")

# ============================================================
# 7. MAIN LOOP
# ============================================================
while True:
    time.sleep(3600)
