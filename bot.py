import os
import threading
import hashlib
import secrets
import time
import telebot
from telebot import types, apihelper
import google.generativeai as genai
from flask import Flask
import psycopg2
from psycopg2 import pool

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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')

# ============================================================
# 3. POSTGRESQL (persistent, auto-reconnect)
# ============================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("❌ DATABASE_URL environment variable is missing!")

try:
    db_pool = psycopg2.pool.SimpleConnectionPool(1, 20, dsn=DATABASE_URL)
    print("✅ PostgreSQL Connection Pool initialized.")
except Exception as e:
    print(f"❌ Failed to connect to PostgreSQL: {e}")
    raise e

def get_safe_connection():
    global db_pool
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        return conn
    except (psycopg2.InterfaceError, psycopg2.OperationalError):
        print("🔄 Re-initializing connection pool due to disconnect...")
        db_pool = psycopg2.pool.SimpleConnectionPool(1, 20, dsn=DATABASE_URL)
        return db_pool.getconn()

def init_db():
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            # id = ውስጣዊ የማይደበቅ ቁጥር (callback_data ላይ ጥቅም ላይ ይውላል)
            # token = እውነተኛው Telegram bot secret (callback_data ላይ በፍጹም አይጋለጥም)
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
            conn.commit()
    finally:
        db_pool.putconn(conn)

init_db()

def hash_password(password, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

# ============================================================
# 4. LOCALIZATION (ደንበኛ ገጽታ - 2 ቋንቋ)
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

# Admin panel (የሱቅ ባለቤት) - አማርኛ ብቻ ለቀላልነት
ADMIN_BTN = {
    "add_product": "➕ ምርት ጨምር",
    "my_products": "📋 ምርቶቼ",
    "orders": "📬 ትዕዛዞች",
    "payment": "💰 የክፍያ ቅንብር",
    "stats": "📊 ስታትስቲክስ",
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
    markup.add(types.KeyboardButton(ADMIN_BTN["stats"]), types.KeyboardButton(ADMIN_BTN["logout"]))
    return markup

# ============================================================
# 5. SHOP BOT ENGINE (customer + shop-admin, per token)
# ============================================================
def setup_bot_handlers(token):
    bot = telebot.TeleBot(token)

    def get_store_info():
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT store_name, admin_id, telebirr, is_active, password_hash, password_salt FROM stores WHERE token=%s", (token,))
                row = cursor.fetchone()
        finally:
            db_pool.putconn(conn)
        if row:
            return {"store_name": row[0], "admin_id": row[1], "telebirr": row[2], "is_active": row[3], "pass_hash": row[4], "salt": row[5]}
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
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT lang FROM user_langs WHERE chat_id=%s", (chat_id,))
                row = cursor.fetchone()
        finally:
            db_pool.putconn(conn)
        return row[0] if row else "am"

    def is_verified_admin(chat_id):
        store = get_store_info()
        session_key = (token, chat_id)
        if store and store["admin_id"] == chat_id:
            if session_key in active_sessions and time.time() < active_sessions[session_key]:
                return True
        return False

    # ---------- Customer: language ----------
    @bot.message_handler(commands=['start'])
    def choose_language(message):
        if not check_active_middleware(message.chat.id): return
        store = get_store_info()
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="shoplang_am"),
                   types.InlineKeyboardButton("English 🇬🇧", callback_data="shoplang_en"))
        bot.send_message(message.chat.id, f"🌐 Welcome to {store['store_name']}!\n\nቋንቋ ይምረጡ / Select Language:", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("shoplang_"))
    def set_language(call):
        chat_id = call.message.chat.id
        if not check_active_middleware(chat_id): return
        lang_code = call.data.split("_")[1]

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO user_langs (chat_id, lang) VALUES (%s, %s)
                                  ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang''', (chat_id, lang_code))
                conn.commit()
        finally:
            db_pool.putconn(conn)

        bot.delete_message(chat_id, call.message.message_id)
        bot.send_message(chat_id, STRINGS[lang_code]["welcome"], reply_markup=get_main_menu(lang_code))

    # ---------- Shop admin: login/logout ----------
    # ማሳሰቢያ: /register ከዚህ ቦት አልቀረም - ምዝገባ የሚደረገው በ CONTROL BOT በኩል (/connect) ብቻ ነው

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
                db_pool.putconn(conn)
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

    # ---------- Shop admin: menu router ----------
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
            bot.reply_to(message, "💰 እባክዎ አዲሱን የቴሌብር ቁጥርዎን ይላኩ፦")
            admin_states[(token, chat_id)] = {"state": "WAITING_PAYMENT_NUMBER", "data": {}}
        elif text == ADMIN_BTN["stats"]:
            show_stats(chat_id)
        elif text == ADMIN_BTN["logout"]:
            do_logout(chat_id)

    def show_my_products(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name_am, price, stock FROM products WHERE token=%s ORDER BY id", (token,))
                rows = cursor.fetchall()
        finally:
            db_pool.putconn(conn)

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
                cursor.execute('''SELECT id, customer_id, total_price, status_am FROM orders
                                  WHERE token=%s AND status_am != %s AND status_am != %s
                                  ORDER BY id DESC LIMIT 15''',
                               (token, "✅ ተከፍሏል", "❌ ውድቅ ተደርጓል"))
                rows = cursor.fetchall()
        finally:
            db_pool.putconn(conn)

        if not rows:
            bot.send_message(chat_id, "📋 በአሁኑ ሰዓት ያልፀደቁ ትዕዛዞች የሉም።")
            return

        for order_id, cust_id, total, status in rows:
            text = f"🆔 **ትዕዛዝ #{order_id}**\n💵 {total} ETB\n📌 ሁኔታ፦ {status}"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                types.InlineKeyboardButton("❌ አትቀበል", callback_data=f"rejectorder_{order_id}")
            )
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    def show_stats(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM products WHERE token=%s", (token,))
                product_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_price),0) FROM orders WHERE token=%s AND status_am=%s", (token, "✅ ተከፍሏል"))
                paid_count, revenue = cursor.fetchone()
                cursor.execute("SELECT COUNT(*) FROM orders WHERE token=%s", (token,))
                total_orders = cursor.fetchone()[0]
        finally:
            db_pool.putconn(conn)

        text = (
            f"📊 **የሱቅ ስታትስቲክስ**\n\n"
            f"📦 ጠቅላላ ምርት፦ {product_count}\n"
            f"🧾 ጠቅላላ ትዕዛዝ፦ {total_orders}\n"
            f"✅ የተከፈለ ትዕዛዝ፦ {paid_count}\n"
            f"💵 ጠቅላላ ገቢ፦ {revenue} ETB"
        )
        bot.send_message(chat_id, text, parse_mode="Markdown")

    # ---------- Shop admin: edit / delete product ----------
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
            db_pool.putconn(conn)

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
            db_pool.putconn(conn)

        bot.edit_message_text(f"🗑️ ምርት #{p_id} ተሰርዟል!", chat_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == "canceldelete")
    def delete_product_cancel(call):
        bot.edit_message_text("ማጥፋቱ ተሰርዟል።", call.message.chat.id, call.message.message_id)

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_PAYMENT_NUMBER")
    def process_payment_number(message):
        if not is_verified_admin(message.chat.id): return
        new_number = message.text.strip()

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET telebirr=%s WHERE token=%s", (new_number, token))
                conn.commit()
        finally:
            db_pool.putconn(conn)

        bot.reply_to(message, f"✅ የቴሌብር ቁጥር ወደ `{new_number}` ተቀይሯል።", parse_mode="Markdown")
        admin_states[(token, message.chat.id)] = {"state": "", "data": {}}

    # ---------- Order approve/reject (inline) ----------
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
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s WHERE id=%s", ("✅ ተከፍሏል", "✅ Paid", order_id))
                    conn.commit()
                    cust_lang = get_user_lang(cust_id)
                    bot.send_message(cust_id, STRINGS[cust_lang]["approved_msg"])
        finally:
            db_pool.putconn(conn)

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
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s WHERE id=%s", ("❌ ውድቅ ተደርጓል", "❌ Rejected", order_id))
                    conn.commit()
                    cust_lang = get_user_lang(cust_id)
                    bot.send_message(cust_id, STRINGS[cust_lang]["rejected_msg"])
        finally:
            db_pool.putconn(conn)

        bot.edit_message_text(f"❌ ትዕዛዝ #{order_id} ውድቅ ተደርጓል።", chat_id, call.message.message_id)
        bot.answer_callback_query(call.id, "ውድቅ ተደርጓል")

    # ---------- Customer: browse / cart ----------
    @bot.message_handler(func=lambda m: any(m.text == STRINGS[k]["shop"] for k in STRINGS if get_user_lang(m.chat.id) == k))
    def list_products(message):
        chat_id = message.chat.id
        if not check_active_middleware(chat_id): return
        lang = get_user_lang(chat_id)

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name_am, name_en, price, stock, desc_am, desc_en, image_url FROM products WHERE token=%s", (token,))
                rows = cursor.fetchall()
        finally:
            db_pool.putconn(conn)

        if not rows:
            bot.send_message(chat_id, "🛍️ ምንም ምርት የለም።" if lang == "am" else "🛍️ No products available.")
            return

        for row in rows:
            p_id, name_am, name_en, price, stock, desc_am, desc_en, image_url = row
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
                except apihelper.ApiTelegramException:
                    text += "\n\n⚠️ *(Image could not be loaded)*"

            if not sent:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("shopadd_"))
    def add_to_cart(call):
        chat_id = call.message.chat.id
        if not check_active_middleware(chat_id): return
        lang = get_user_lang(chat_id)
        p_id = int(call.data.split("_")[1])

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM products WHERE id=%s AND token=%s", (p_id, token))
                exists = cursor.fetchone()
        finally:
            db_pool.putconn(conn)

        if not exists:
            bot.answer_callback_query(call.id, "❌ Error: Product mismatch.")
            return

        cart_key = (token, chat_id)
        if cart_key not in user_carts: user_carts[cart_key] = {}
        user_carts[cart_key][p_id] = user_carts[cart_key].get(p_id, 0) + 1
        bot.answer_callback_query(call.id, STRINGS[lang]["added"])

    @bot.message_handler(func=lambda m: any(m.text == STRINGS[k]["cart"] for k in STRINGS if get_user_lang(m.chat.id) == k))
    def show_cart(message):
        chat_id = message.chat.id
        if not check_active_middleware(chat_id): return
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
            db_pool.putconn(conn)

        text += f"\n💵 **{STRINGS[lang]['total']}: {total} ETB**"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(STRINGS[lang]["checkout_btn"], callback_data="shop_checkout"),
                   types.InlineKeyboardButton(STRINGS[lang]["clear_btn"], callback_data="shop_clear"))
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data in ["shop_checkout", "shop_clear"])
    def cart_actions(call):
        chat_id = call.message.chat.id
        if not check_active_middleware(chat_id): return
        lang = get_user_lang(chat_id)
        cart_key = (token, chat_id)
        store = get_store_info()

        if call.data == "shop_clear":
            user_carts[cart_key] = {}
            bot.edit_message_text("🛒 Cart cleared / ጋሪው ጸድቷል!", chat_id, call.message.message_id)
        elif call.data == "shop_checkout":
            cart = user_carts.get(cart_key, {})
            if not cart: return

            total_price = 0
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    for p_id, qty in list(cart.items()):
                        cursor.execute("SELECT price FROM products WHERE id=%s AND token=%s", (p_id, token))
                        p_row = cursor.fetchone()
                        if p_row:
                            total_price += p_row[0] * qty
                        else:
                            del cart[p_id]

                    cursor.execute('''INSERT INTO orders (token, customer_id, status_am, status_en, total_price)
                                      VALUES (%s, %s, %s, %s, %s) RETURNING id''',
                                   (token, chat_id, "በመጠባበቅ ላይ (ፎቶ ይጠበቃል)", "Pending (Awaiting Screenshot)", total_price))
                    order_id = cursor.fetchone()[0]
                    conn.commit()
            finally:
                db_pool.putconn(conn)

            user_carts[cart_key] = {}
            pay_text = f"🆔 **Order ID / የትዕዛዝ ቁጥር፦** `{order_id}`\n\n📱 **Telebirr / ቴሌብር፦** `{store['telebirr']}`\n\n{STRINGS[lang]['receipt_prompt']}"
            bot.edit_message_text(pay_text, chat_id, call.message.message_id, parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": f"AWAITING_RECEIPT_{order_id}", "data": {}}

    # ---------- Photo handler (receipt / product photo) ----------
    @bot.message_handler(content_types=['photo'])
    def handle_incoming_photos(message):
        chat_id = message.chat.id
        if not check_active_middleware(chat_id): return

        session_key = (token, chat_id)
        state_dict = admin_states.get(session_key, {"state": "", "data": {}})
        state = state_dict["state"]
        store = get_store_info()

        if state.startswith("AWAITING_RECEIPT_"):
            order_id = int(state.split("_")[2])
            admin_id = store["admin_id"] if store else chat_id

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                types.InlineKeyboardButton("❌ አትቀበል", callback_data=f"rejectorder_{order_id}")
            )
            bot.send_message(admin_id, f"🔔 **አዲስ የክፍያ ደረሰኝ ለትዕዛዝ ቁጥር #{order_id}!**", reply_markup=markup, parse_mode="Markdown")
            bot.forward_message(admin_id, chat_id, message.message_id)

            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s WHERE id=%s AND token=%s",
                                   ("ክፍያ ተልኳል (በማረጋገጥ ላይ)", "Payment sent (Verifying)", order_id, token))
                    conn.commit()
            finally:
                db_pool.putconn(conn)

            bot.reply_to(message, "✅ የክፍያ ማረጋገጫ ፎቶዎ ተልኳል።")
            admin_states[session_key] = {"state": "", "data": {}}

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
                db_pool.putconn(conn)
            bot.reply_to(message, f"🎉 ምርቱ '{p_data['name_am']}' በስኬት ተጨምሯል!")
            admin_states[session_key] = {"state": "", "data": {}}
        else:
            bot.reply_to(message, "📸 ፎቶ ስለላኩልን እናመሰግናለን!")

    # ---------- FAQ / Track ----------
    @bot.message_handler(func=lambda m: any(m.text == STRINGS[k]["faq"] for k in STRINGS if get_user_lang(m.chat.id) == k))
    def show_faq(message):
        if not check_active_middleware(message.chat.id): return
        lang = get_user_lang(message.chat.id)
        bot.reply_to(message, STRINGS[lang]["faq_text"], parse_mode="Markdown")

    @bot.message_handler(func=lambda m: any(m.text == STRINGS[k]["track"] for k in STRINGS if get_user_lang(m.chat.id) == k))
    def track_order(message):
        if not check_active_middleware(message.chat.id): return
        lang = get_user_lang(message.chat.id)
        msg = bot.reply_to(message, STRINGS[lang]["enter_id"])
        bot.register_next_step_handler(msg, process_track)

    def process_track(message):
        if not check_active_middleware(message.chat.id): return
        lang = get_user_lang(message.chat.id)
        try:
            order_id = int(message.text)
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT status_am, status_en FROM orders WHERE id=%s AND token=%s", (order_id, token))
                    row = cursor.fetchone()
            finally:
                db_pool.putconn(conn)

            if row:
                status = row[0] if lang == "am" else row[1]
                bot.reply_to(message, f"📦 **Status:** {status}")
            else:
                bot.reply_to(message, STRINGS[lang]["not_found"])
        except ValueError:
            bot.reply_to(message, STRINGS[lang]["invalid_id"])

    # ---------- Add product flow ----------
    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_PRODUCT_DETAILS")
    def process_add_product_fields(message):
        session_key = (token, message.chat.id)
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
        if not is_verified_admin(message.chat.id): return
        p_data = admin_states[session_key]["data"]

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO products (token, name_am, name_en, price, stock, desc_am, desc_en, image_url)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                               (token, p_data["name_am"], p_data["name_en"], p_data["price"], p_data["stock"], p_data["desc_am"], p_data["desc_en"], ""))
                conn.commit()
        finally:
            db_pool.putconn(conn)
        bot.reply_to(message, f"🎉 ምርቱ '{p_data['name_am']}' ያለ ፎቶ ተጨምሯል!")
        admin_states[session_key] = {"state": "", "data": {}}

    # ---------- AI fallback ----------
    @bot.message_handler(func=lambda message: True)
    def handle_global_ai(message):
        if not check_active_middleware(message.chat.id): return
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

    threading.Thread(target=bot.infinity_polling, name=f"Bot_{token}", daemon=True).start()

# ============================================================
# 6. DYNAMIC MULTI-TENANT LAUNCHER (409-safe, restart-safe)
# ============================================================
running_tokens = set()
running_lock = threading.Lock()

def start_shop_bot(token):
    with running_lock:
        if token in running_tokens:
            return False
        running_tokens.add(token)
    print(f"🚀 Starting shop bot: {token[:10]}...")
    setup_bot_handlers(token)
    return True

def load_existing_stores_from_db():
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT token FROM stores")
            rows = cursor.fetchall()
    finally:
        db_pool.putconn(conn)
    for (tok,) in rows:
        start_shop_bot(tok)
    print(f"✅ {len(rows)} previously registered shop bot(s) restored from database.")

load_existing_stores_from_db()

# ============================================================
# 7. CONTROL BOT (self-service registration + super admin panel)
# ============================================================
CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN", "")

if CONTROL_BOT_TOKEN:
    control_bot = telebot.TeleBot(CONTROL_BOT_TOKEN)

    # ---------------- Self-service shop registration ----------------
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
            db_pool.putconn(conn)

        start_shop_bot(new_token)

        control_bot.reply_to(
            message,
            f"🎉 ስኬታማ! '@{bot_info.username}' ለ '{store_name}' ተመዝግቦ ተነስቷል!\n\n"
            f"አሁን ወደ @{bot_info.username} ሄደው፦\n"
            f"`/login {password}`\n\nብለው ወደ አድሚን ፓናል ይግቡ።",
            parse_mode="Markdown"
        )

    # ---------------- Super Admin panel (system owner only) ----------------
    SUPER_ADMIN_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
    SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")
    SUPPORT_USERNAME = os.environ.get("SUPPORT_USERNAME", "@your_support_username")

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
                db_pool.putconn(conn)

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
                    cur.execute("SELECT COUNT(*), COALESCE(SUM(total_price), 0) FROM orders WHERE status_am = %s", ("✅ ተከፍሏል",))
                    paid_orders, total_rev = cur.fetchone()
            except Exception as e:
                control_bot.reply_to(message, f"❌ Database error: {e}")
                return
            finally:
                db_pool.putconn(conn)

            report = (
                f"📊 **የሲስተሙ አጠቃላይ መረጃ**\n\n"
                f"🏢 **ጠቅላላ ሱቆች፦** {tot_stores}\n"
                f"📦 **የተጫኑ እቃዎች፦** {tot_products}\n"
                f"🧾 **የተሸጡ እቃዎች፦** {paid_orders}\n"
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
            db_pool.putconn(conn)

        status_msg = "🔴 ሱቁ ተግዷል" if new_status == 0 else "🟢 ሱቁ ተነቅቷል"
        try:
            control_bot.edit_message_text(f"{call.message.text}\n\n⚠️ **{status_msg}**", chat_id, call.message.message_id, parse_mode="Markdown")
        except apihelper.ApiTelegramException:
            pass
        control_bot.answer_callback_query(call.id, status_msg)

    threading.Thread(target=control_bot.infinity_polling, name="ControlBot", daemon=True).start()
    print("✅ Control Bot is running (self-registration + super admin panel).")
else:
    print("⚠️ CONTROL_BOT_TOKEN not set - falling back to static BOT_TOKENS only.")
    RAW_TOKENS = os.environ.get("BOT_TOKENS", "")
    if RAW_TOKENS:
        for t in [x.strip() for x in RAW_TOKENS.split(",") if x.strip()]:
            start_shop_bot(t)

while True:
    time.sleep(3600)
