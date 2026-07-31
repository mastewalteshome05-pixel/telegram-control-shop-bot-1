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

            conn.commit()
    finally:
        put_conn(conn)


init_db()


def hash_password(password, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt


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
# 4. LOCALIZATION (11 Languages Support)
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
        "receipt_prompt": "እባክዎ የከፈሉበትን የባንክ ወይም የቴሌብር ደረሰኝ (Screenshot ፎቶ) እዚህ ላይ ይላኩ። 📸",
        "faq_text": "ℹ️ **ስለ ሱቃችን መረጃ**\n\n📍 አድራሻችን፦ አዲስ አበባ፣ ኢትዮጵያ\n📞 ስልክ፦ 0911223344"
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
        "receipt_prompt": "Please send the Bank or Telebirr payment confirmation screenshot here. 📸",
        "faq_text": "ℹ️ **About Our Store**\n\n📍 Location: Addis Ababa, Ethiopia\n📞 Phone: +251911223344"
    },
    "zh": {
        "welcome": "欢迎使用 AI 客户服务机器人！ 👋",
        "shop": "🛍️ 购买商品", "cart": "🛒 我的购物车", "track": "📦 订单追踪", "faq": "❓ 常见问题",
        "empty": "🛒 您的购物车当前为空。", "added": "已加入购物车！ 🛒", "total": "总计",
        "price_label": "价格", "checkout_btn": "💳 结账", "clear_btn": "🗑️ 清空购物车",
        "enter_id": "🔢 请输入您的订单编号：",
        "not_found": "❌ 未找到订单编号或对此商店无效。", "invalid_id": "❌ 输入的编号无效。",
        "approved_msg": "🎉 好消息！您的付款已验证，商品正在配送中！ 🛵",
        "rejected_msg": "❌ 您的付款无法验证，请联系店主。",
        "receipt_prompt": "请在此发送银行或支付凭证截图。 📸",
        "faq_text": "ℹ️ **关于我们**\n\n📍 地点：埃塞俄比亚亚的斯亚贝巴\n📞 电话：+251911223344"
    },
    "hi": {
        "welcome": "AI ग्राहक सेवा बॉट में आपका स्वागत है! 👋",
        "shop": "🛍️ उत्पाद खरीदें", "cart": "🛒 मेरी कार्ट", "track": "📦 ऑर्डर ट्रैक करें", "faq": "❓ अक्सर पूछे जाने वाले प्रश्न",
        "empty": "🛒 आपकी कार्ट वर्तमान में खाली है।", "added": "कार्ट में जोड़ा गया! 🛒", "total": "कुल",
        "price_label": "कीमत", "checkout_btn": "💳 चेकआउट", "clear_btn": "🗑️ कार्ट साफ़ करें",
        "enter_id": "🔢 कृपया अपनी ऑर्डर आईडी दर्ज करें:",
        "not_found": "❌ ऑर्डर आईडी नहीं मिली या इस स्टोर के लिए अमान्य है।", "invalid_id": "❌ अमान्य आईडी दर्ज की गई।",
        "approved_msg": "🎉 अच्छी खबर! आपका भुगतान स्वीकृत हो गया है और आपका सामान रास्ते में है! 🛵",
        "rejected_msg": "❌ आपके भुगतान की पुष्टि नहीं हो सकी। कृपया स्टोर मालिक से संपर्क करें।",
        "receipt_prompt": "कृपया यहाँ बैंक या भुगतान स्क्रीनशॉट भेजें। 📸",
        "faq_text": "ℹ️ **हमारे स्टोर के बारे में**\n\n📍 स्थान: अदीस अबाबा, इथियोपिया\n📞 फोन: +251911223344"
    },
    "es": {
        "welcome": "¡Bienvenido al bot de servicio al cliente de IA! 👋",
        "shop": "🛍️ Comprar", "cart": "🛒 Mi Carrito", "track": "📦 Rastrear Pedido", "faq": "❓ Preguntas Frecuentes",
        "empty": "🛒 Tu carrito está vacío.", "added": "¡Agregado al carrito! 🛒", "total": "Total",
        "price_label": "Precio", "checkout_btn": "💳 Pagar", "clear_btn": "🗑️ Vaciar Carrito",
        "enter_id": "🔢 Por favor ingresa tu ID de pedido:",
        "not_found": "❌ ID de pedido no encontrado.", "invalid_id": "❌ ID inválido.",
        "approved_msg": "¡Buenas noticias! Tu pago ha sido aprobado y tu pedido está en camino. 🛵",
        "rejected_msg": "❌ Su pago no pudo ser verificado. Contacte al tendero.",
        "receipt_prompt": "Envía aquí la captura de pantalla del pago. 📸",
        "faq_text": "ℹ️ **Información de la Tienda**\n\n📍 Ubicación: Adís Abeba, Etiopía\n📞 Teléfono: +251911223344"
    },
    "ar": {
        "welcome": "أهلاً بك في بوت خدمة العملاء! 👋",
        "shop": "🛍️ تسوق المنتجات", "cart": "🛒 سلة التسوق", "track": "📦 تتبع الطلب", "faq": "❓ الأسئلة الشائعة",
        "empty": "🛒 سلة التسوق فارغة حالياً.", "added": "تمت الإضافة إلى السلة! 🛒", "total": "المجموع",
        "price_label": "السعر", "checkout_btn": "💳 إتمام الشراء", "clear_btn": "🗑️ تفريغ السلة",
        "enter_id": "🔢 يرجى إدخال رقم الطلب:",
        "not_found": "❌ رقم الطلب غير موجود أو غير صالح.", "invalid_id": "❌ رقم غير صالح.",
        "approved_msg": "🎉 أخبار سارة! تم اعتماد الدفع وطلبك في طريقه إليك. 🛵",
        "rejected_msg": "❌ تعذر التحقق من الدفع. يرجى الاتصال بصاحب المتجر.",
        "receipt_prompt": "يرجى إرسال لقطة شاشة إيصال الدفع هنا. 📸",
        "faq_text": "ℹ️ **معلومات المتجر**\n\n📍 الموقع: أديس أبابا، إثيوبيا\n📞 الهاتف: +251911223344"
    },
    "fr": {
        "welcome": "Bienvenue sur le bot du service client IA ! 👋",
        "shop": "🛍️ Acheter", "cart": "🛒 Mon Panier", "track": "📦 Suivre la commande", "faq": "❓ FAQ",
        "empty": "🛒 Votre panier est vide.", "added": "Ajouté au panier ! 🛒", "total": "Total",
        "price_label": "Prix", "checkout_btn": "💳 Commander", "clear_btn": "🗑️ Vider le panier",
        "enter_id": "🔢 Veuillez entrer votre ID de commande :",
        "not_found": "❌ ID de commande introuvable.", "invalid_id": "❌ ID invalide.",
        "approved_msg": "🎉 Bonne nouvelle ! Votre paiement a été approuvé et votre article est en route ! 🛵",
        "rejected_msg": "❌ Échec de la vérification du paiement. Contactez le propriétaire.",
        "receipt_prompt": "Veuillez envoyer la capture d'écran du reçu de paiement ici. 📸",
        "faq_text": "ℹ️ **À propos de notre magasin**\n\n📍 Lieu : Addis-Abeba, Éthiopie\n📞 Téléphone : +251911223344"
    },
    "om": {
        "welcome": "Baga nagaan gara Bot Tajaajila Maamilootaa nagaan dhuftan! 👋",
        "shop": "🛍️ Oomishaalee Ilaali", "cart": "🛒 Kaartii Koo", "track": "📦 Ajaja Hordofaa", "faq": "❓ Odeeffannoo (FAQ)",
        "empty": "🛒 Kaartiin keessan amma duwwaa dha.", "added": "Kaartitti dabalamooti! 🛒", "total": "Waliigala",
        "price_label": "Gatii", "checkout_btn": "💳 Baasii Xumuri", "clear_btn": "🗑️ Kaartii Qulqulleessi",
        "enter_id": "🔢 Maaloo Lakkoofsa Ajajaa (Order ID) galchaa:",
        "not_found": "❌ Lakkoofsi ajajaa hin argamne.", "invalid_id": "❌ Lakkoofsi dogoggoraan galeera.",
        "approved_msg": "🎉 Oduu gammachiisaa! Kaffaltiin keessan mirkanaa'ee oomishni karaa irra jira. 🛵",
        "rejected_msg": "❌ Kaffaltiin keessan mirkanaa'uu hin dandeenye.",
        "receipt_prompt": "Maaloo ragaa kaffaltii (Screenshot) asitti ergaa. 📸",
        "faq_text": "ℹ️ **Waa'ee keenya**\n\n📍 Teessoo: Finfinnee, Itoophiyaa\n📞 Bilbila: 0911223344"
    },
    "ti": {
        "welcome": "ብደሓን መጻእኩም ናብ AI ኣገልግሎት ዓሚል ቦት! 👋",
        "shop": "🛍️ ንብረት ርአ", "cart": "🛒 ሰፈረይ (Cart)", "track": "📦 ትእዛዝ ተከታተል", "faq": "❓ ሓበሬታ (FAQ)",
        "empty": "🛒 ሰፈርካ ድኩም እዩ።", "added": "ናብ ሰፈር ተወሲኹ! 🛒", "total": "ጠቕላላ",
        "price_label": "ዋጋ", "checkout_btn": "💳 ክፍሊት ዛዘም", "clear_btn": "🗑️ ሰፈር ኣጽርይ",
        "enter_id": "🔢 እኩብ ቁጽሪ ትእዛዝ (Order ID) ኣእቱ፦",
        "not_found": "❌ ቁጽሪ ትእዛዝ ኣይተረኽበን።", "invalid_id": "❌ ግጉይ ቁጽሪ ኣትዩ።",
        "approved_msg": "🎉 ጽቡቕ ዜና! ክፍሊትካ ተረጋጊጹ ንብረት ብመገዲ ኣሎ። 🛵",
        "rejected_msg": "❌ ክፍሊትካ ክረጋገጽ ኣይክኣለን።",
        "receipt_prompt": "በጃኹም መረጋገጺ ክፍሊት (Screenshot) ኣብዚ ስደዱ። 📸",
        "faq_text": "ℹ️ **ብዛዕባ ድኳንና**\n\n📍 ኣድራሻ፦ ኣዲስ ኣበባ፣ ኢትዮጵያ\n📞 ስልኪ፦ 0911223344"
    },
    "so": {
        "welcome": "Ku soo dhawoow Adeegga Macmiilka AI! 👋",
        "shop": "🛍️ Alaabta Iibso", "cart": "🛒 Gaarigayga", "track": "📦 Raadi Dalabka", "faq": "❓ Macluumaad",
        "empty": "🛒 Gaarigagu waa madhan yahay.", "added": "Lagu daray gaariga! 🛒", "total": "Wadarta guud",
        "price_label": "Qiimaha", "checkout_btn": "💳 Bixi", "clear_btn": "🗑️ Nadiifi Gaariga",
        "enter_id": "🔢 Fadlan geli Aqoonsiga Dalabka (Order ID):",
        "not_found": "❌ Lama helin lambarka dalabka.", "invalid_id": "❌ Lambar khaldan.",
        "approved_msg": "🎉 War farxad leh! Lacag bixintaadi waa la xaqiijiyay oo alaabtu way socotaa. 🛵",
        "rejected_msg": "❌ Lacag bixintaada lama xaqiijin karin.",
        "receipt_prompt": "Fadlan halkan ka soo dir sawirka lacag bixinta (Screenshot). 📸",
        "faq_text": "ℹ️ **Nagu saabsan**\n\n📍 Goobta: Addis Ababa, Itoobiya\n📞 Taleefanka: +251911223344"
    },
    "aa": {
        "welcome": "AI Abbaayih Taysuma Bot fan inkih marhabax baah! 👋",
        "shop": "🛍️ Yanim Taysuma", "cart": "🛒 Ayunti Giriya", "track": "📦 Diggi Amri", "faq": "❓ Geytinna",
        "empty": "🛒 Ayuntik gari maaliyo.", "added": "Garih fanah abte! 🛒", "total": "Gabaaba",
        "price_label": "Qhiya", "checkout_btn": "💳 Xage", "clear_btn": "🗑️ Gari Gacsi",
        "enter_id": "🔢 Amri id (Order ID) rubba:",
        "not_found": "❌ Amri id ma geyne.", "invalid_id": "❌ Gugsissa id.",
        "approved_msg": "🎉 Wagsi xab! Xaqsu sugteh amaana ayyaaham yemeete. 🛵",
        "rejected_msg": "❌ Xaqsu ma sugto.",
        "receipt_prompt": "Xaqsu sate screenshot-hadih taniih xaysi. 📸",
        "faq_text": "ℹ️ **Dukaan geytinna**\n\n📍 Adda: Addis Ababa, Ethiopia\n📞 Telefoon: +251911223344"
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
    "logout": "🚪 ውጣ",
    "back": "⬅️ ተመለס (Back)"
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
    markup.add(types.KeyboardButton(ADMIN_BTN["back"]))
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
            bot.send_message(chat_id, "❌ ይህ ሱቅ ንቁ አይደለም።")
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

    @bot.message_handler(commands=['start'])
    def choose_language(message):
        if not check_active_middleware(message.chat.id):
            return
        store = get_store_info()
        
        store_desc = store.get('shop_description') or "ጥራት ያለው እቃ ማቅረቢያ ሱቅ"
        store_loc = store.get('area_text') or "አዲስ አበባ"
        
        caption = (
            f"🏪 **{store['store_name']}**\n\n"
            f"📝 **መግለጫ / Description:** {store_desc}\n"
            f"📍 **አድራሻ / Location:** {store_loc}\n\n"
            f"🌐 ቋንቋ ይምረጡ / Choose Language:"
        )
        
        # All 11 Languages Inline Buttons
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="shoplang_am"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data="shoplang_en"),
            types.InlineKeyboardButton("Mandarin (中文) 🇨🇳", callback_data="shoplang_zh"),
            types.InlineKeyboardButton("Hindi (हिन्दी) 🇮🇳", callback_data="shoplang_hi"),
            types.InlineKeyboardButton("Spanish (Español) 🇪🇸", callback_data="shoplang_es"),
            types.InlineKeyboardButton("Arabic (العربية) 🇸🇦", callback_data="shoplang_ar"),
            types.InlineKeyboardButton("French (Français) 🇫🇷", callback_data="shoplang_fr"),
            types.InlineKeyboardButton("ኦሮምኛ 🇪🇹", callback_data="shoplang_om"),
            types.InlineKeyboardButton("ትግርኛ 🇪🇹", callback_data="shoplang_ti"),
            types.InlineKeyboardButton("Somali (Soomaali) 🇸🇴", callback_data="shoplang_so"),
            types.InlineKeyboardButton("Afar (Qafar) 🇪🇹", callback_data="shoplang_aa")
        )
        
        if store.get('shop_photo'):
            try:
                bot.send_photo(message.chat.id, store['shop_photo'], caption=caption, reply_markup=markup, parse_mode="Markdown")
                return
            except Exception:
                pass
        bot.send_message(message.chat.id, caption, reply_markup=markup, parse_mode="Markdown")

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
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except Exception:
            pass
        bot.send_message(chat_id, STRINGS[lang_code]["welcome"], reply_markup=get_main_menu(lang_code))

    @bot.message_handler(commands=['login'])
    def login_store(message):
        chat_id = message.chat.id
        store = get_store_info()
        if not store:
            bot.reply_to(message, "❌ ይህ ሱቅ ገና አልተመዘገበም።")
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

    @bot.message_handler(func=lambda m: m.text == ADMIN_BTN["back"])
    def admin_back_button(message):
        do_logout(message.chat.id)

    @bot.message_handler(func=lambda m: m.text in ADMIN_BTN.values())
    def admin_menu_router(message):
        chat_id = message.chat.id
        if not is_verified_admin(chat_id):
            bot.reply_to(message, "❌ እባክዎ መጀመሪያ በ `/login` ይግቡ።")
            return

        text = message.text
        if text == ADMIN_BTN["add_product"]:
            bot.reply_to(message, "📝 እባክዎ የምርቱን መረጃ በዚህ ፎርማት ይጻፉ፦\n`[የአማርኛ ስም],[የእንግሊዝኛ ስም],[ዋጋ],[ብዛት],[አማርኛ መግለጫ],[እንግሊዝኛ መግለጫ]`", parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": "WAITING_PRODUCT_DETAILS", "data": {}}
        elif text == ADMIN_BTN["my_products"]:
            show_my_products(chat_id)
        elif text == ADMIN_BTN["orders"]:
            show_pending_orders(chat_id)
        elif text == ADMIN_BTN["payment"]:
            bot.reply_to(message, "💰 እባክዎ **የቴሌብር እና CBE Birr ቁጥርዎን** በኮማ (,) ለይተው ይላኩ (ለምሳሌ፦ `0911223344,1000123456789`)፦", parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": "WAITING_PAYMENT_NUMBER", "data": {}}
        elif text == ADMIN_BTN["stats"]:
            show_stats(chat_id)
        elif text == ADMIN_BTN["profile"]:
            loc_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            loc_markup.add(types.KeyboardButton("📍 የሱቅ አካባቢ አጋራ", request_location=True), types.KeyboardButton(ADMIN_BTN["back"]))
            bot.send_message(chat_id, "🏪 **የሱቅ መገለጫ ማዘጋጀት**\n\nደረጃ 1/4: እባክዎ የሱቅዎን አካባቢ (Location) ያጋሩ 👇", reply_markup=loc_markup, parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": "WAITING_SHOP_LOCATION", "data": {}}
        elif text == ADMIN_BTN["changepass"]:
            bot.reply_to(message, "🔑 እባክዎ **አዲሱን የይለፍ ቃል** ይላኩ (ቢያንስ 8 ፊደል/ቁጥር)፦", parse_mode="Markdown")
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
            bot.send_message(chat_id, "📋 ምንም ምርት የለም።")
            return

        for p_id, name_am, price, stock in rows:
            text = f"📦 **#{p_id} {name_am}**\n💰 {price} ETB | 📦 ብዛት፦ {stock}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🗑️ ሰርዝ", callback_data=f"deleteproduct_{p_id}"))
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
            text = f"🆔 **ትዕዛዝ #{order_id}**\n💵 {total} ETB\n📌 ሁኔታ፦ {status_label}"
            markup = types.InlineKeyboardMarkup()
            if stage == 0:
                markup.add(types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                           types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"rejectorder_{order_id}"))
            elif stage == 1:
                markup.add(types.InlineKeyboardButton("🚚 በመንገድ ላይ (On the way)", callback_data=f"advance_{order_id}"))
            elif stage == 2:
                markup.add(types.InlineKeyboardButton("📦 ደርሷል (Delivered)", callback_data=f"advance_{order_id}"))
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    def show_stats(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM products WHERE token=%s", (token,))
                product_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0) FROM orders WHERE token=%s AND status_stage >= 1", (token,))
                paid_count, revenue = cursor.fetchone()
        finally:
            put_conn(conn)

        text = f"📊 **ስቲስቲክስ**\n\n📦 ምርቶች፦ {product_count}\n✅ የተከፈሉ፦ {paid_count}\n💵 ገቢ፦ {revenue} ETB"
        bot.send_message(chat_id, text, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("deleteproduct_"))
    def delete_product_confirmed(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
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

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_PAYMENT_NUMBER")
    def process_payment_number(message):
        if not is_verified_admin(message.chat.id):
            return
        parts = message.text.strip().split(",")
        tele_num = parts[0].strip()
        cbe_num = parts[1].strip() if len(parts) > 1 else ""
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET telebirr=%s, cbebirr=%s WHERE token=%s", (tele_num, cbe_num, token))
                conn.commit()
        finally:
            put_conn(conn)
        bot.reply_to(message, f"✅ Telebirr: `{tele_num}`\n✅ CBE Birr: `{cbe_num}`", parse_mode="Markdown")
        admin_states[(token, message.chat.id)] = {"state": "", "data": {}}

    @bot.callback_query_handler(func=lambda call: call.data.startswith("approveorder_"))
    def approve_order_btn(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
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
                    bot.send_message(cust_id, STRINGS.get(cust_lang, STRINGS["am"])["approved_msg"])
        finally:
            put_conn(conn)
        bot.edit_message_text(f"✅ ትዕዛዝ #{order_id} ጸድቋል!", chat_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("rejectorder_"))
    def reject_order_btn(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            return
        order_id = int(call.data.split("_")[1])
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT customer_id FROM orders WHERE id=%s AND token=%s", (order_id, token))
                row = cursor.fetchone()
                if row:
                    cust_id = row[0]
                    cursor.execute("UPDATE orders SET status_stage=-1 WHERE id=%s", (order_id,))
                    conn.commit()
                    cust_lang = get_user_lang(cust_id)
                    bot.send_message(cust_id, STRINGS.get(cust_lang, STRINGS["am"])["rejected_msg"])
        finally:
            put_conn(conn)
        bot.edit_message_text(f"❌ ትዕዛዝ #{order_id} ውድቅ ተደርጓል።", chat_id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("advance_"))
    def advance_order_btn(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
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
                    bot.send_message(cust_id, f"📦 የትዕዛዝ ሁኔታ ተቀይሯል፦ {ORDER_STAGES_AM[new_stage]}")
        finally:
            put_conn(conn)
        bot.edit_message_text(f"🔄 ትዕዛዝ #{order_id} ተዘምኗል።", chat_id, call.message.message_id)

    @bot.message_handler(func=lambda m: m.text in [STRINGS[l]["shop"] for l in STRINGS])
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
            bot.send_message(chat_id, "🛍️ ምንም ምርት የለም።")
            return

        for row in rows:
            p_id, name_am, name_en, price, stock, desc_am, desc_en, image_url = row
            name = name_am if lang in ["am", "om", "ti"] else name_en
            desc = desc_am if lang in ["am", "om", "ti"] else desc_en
            text = f"📦 **{name}**\n💰 ዋጋ፦ {price} ETB\n📝 {desc}"
            markup = types.InlineKeyboardMarkup()
            if (stock or 0) > 0:
                markup.add(types.InlineKeyboardButton("🛒 ወደ ጋሪ ጨምር", callback_data=f"shopadd_{p_id}"))
            
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                    continue
                except Exception:
                    pass
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("shopadd_"))
    def add_to_cart(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        p_id = int(call.data.split("_")[1])
        cart_key = (token, chat_id)
        if cart_key not in user_carts:
            user_carts[cart_key] = {}
        user_carts[cart_key][p_id] = user_carts[cart_key].get(p_id, 0) + 1
        bot.answer_callback_query(call.id, STRINGS.get(lang, STRINGS["am"])["added"])

    @bot.message_handler(func=lambda m: m.text in [STRINGS[l]["cart"] for l in STRINGS])
    def show_cart(message):
        chat_id = message.chat.id
        if not check_active_middleware(chat_id):
            return
        lang = get_user_lang(chat_id)
        ln = STRINGS.get(lang, STRINGS["am"])
        cart = user_carts.get((token, chat_id), {})
        if not cart:
            bot.send_message(chat_id, ln["empty"])
            return

        total = 0
        text = "🛒 **ጋሪዎ / Cart:**\n\n"
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                for p_id, qty in list(cart.items()):
                    cursor.execute("SELECT name_am, name_en, price FROM products WHERE id=%s AND token=%s", (p_id, token))
                    row = cursor.fetchone()
                    if row:
                        name = row[0] if lang in ["am", "om", "ti"] else row[1]
                        subtotal = row[2] * qty
                        total += subtotal
                        text += f"▪️ {name} x {qty} = {subtotal} ETB\n"
        finally:
            put_conn(conn)

        text += f"\n💵 **አጠቃላይ / Total፦ {total} ETB**"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(ln["checkout_btn"], callback_data="shop_checkout"),
                   types.InlineKeyboardButton(ln["clear_btn"], callback_data="shop_clear"))
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    def finalize_checkout(chat_id, lang):
        cart_key = (token, chat_id)
        cart = user_carts.get(cart_key, {})
        if not cart:
            return
        store = get_store_info()
        items_total = 0
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                for p_id, qty in cart.items():
                    cursor.execute("SELECT price FROM products WHERE id=%s AND token=%s", (p_id, token))
                    row = cursor.fetchone()
                    if row:
                        items_total += row[0] * qty

                cursor.execute('''INSERT INTO orders (token, customer_id, status_am, status_en, total_price, status_stage)
                                  VALUES (%s, %s, %s, %s, %s, 0) RETURNING id''',
                               (token, chat_id, ORDER_STAGES_AM[0], ORDER_STAGES_EN[0], items_total))
                order_id = cursor.fetchone()[0]
                conn.commit()
        finally:
            put_conn(conn)

        user_carts[cart_key] = {}
        ln = STRINGS.get(lang, STRINGS["am"])
        pay_info = f"📱 **Telebirr:** `{store.get('telebirr')}`"
        if store.get('cbebirr'):
            pay_info += f"\n🏦 **CBE Birr:** `{store.get('cbebirr')}`"

        pay_text = f"🆔 **Order ID:** `{order_id}`\n💵 **ሂሳብ / Total፦** {items_total} ETB\n\n{pay_info}\n\n{ln['receipt_prompt']}"
        bot.send_message(chat_id, pay_text, parse_mode="Markdown", reply_markup=get_main_menu(lang))
        admin_states[(token, chat_id)] = {"state": f"AWAITING_RECEIPT_{order_id}", "data": {}}

    @bot.callback_query_handler(func=lambda call: call.data in ["shop_checkout", "shop_clear"])
    def cart_actions(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        cart_key = (token, chat_id)
        if call.data == "shop_clear":
            user_carts[cart_key] = {}
            bot.edit_message_text("🛒 ጋሪው ጸድቷል!", chat_id, call.message.message_id)
        elif call.data == "shop_checkout":
            cust = get_customer_info(chat_id)
            if cust and cust.get("phone") and cust.get("lat"):
                finalize_checkout(chat_id, lang)
            else:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton("📱 ስልክ ቁጥር አጋራ", request_contact=True), types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
                bot.send_message(chat_id, "📱 እባክዎ ትዕዛዝ ከመፈጸምዎ በፊት ስልክ ቁጥርዎን እና አካባቢዎን ያጋሩ 👇", reply_markup=markup)
                admin_states[(token, chat_id)] = {"state": "PENDING_CHECKOUT", "data": {}}

    @bot.message_handler(content_types=['contact'])
    def handle_contact(message):
        if message.contact:
            save_customer_phone(message.chat.id, message.contact.phone_number)
            bot.reply_to(message, "✅ ስልክ ቁጥርዎ ተመዝግቧል!")

    @bot.message_handler(content_types=['location'])
    def handle_location(message):
        chat_id = message.chat.id
        session_key = (token, chat_id)
        state = admin_states.get(session_key, {}).get("state", "")
        
        if state == "WAITING_SHOP_LOCATION":
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET shop_lat=%s, shop_lng=%s WHERE token=%s", (message.location.latitude, message.location.longitude, token))
                    conn.commit()
            finally:
                put_conn(conn)
            bot.send_message(chat_id, "✅ አካባቢ ተቀምጧል!\n\nደረጃ 2/4: የሱቅዎን አካባቢ ስም (ለምሳሌ 'ቦሌ') በጽሁፍ ይላኩ፦")
            admin_states[session_key] = {"state": "WAITING_SHOP_AREA", "data": {}}
            return

        save_customer_location(chat_id, message.location.latitude, message.location.longitude)
        if state == "PENDING_CHECKOUT":
            finalize_checkout(chat_id, get_user_lang(chat_id))

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_SHOP_AREA")
    def process_shop_area(message):
        chat_id = message.chat.id
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET area_text=%s WHERE token=%s", (message.text.strip(), token))
                conn.commit()
        finally:
            put_conn(conn)
        bot.reply_to(message, "✅ ተቀምጧል!\n\nደረጃ 3/4: የሱቅዎን ፎቶ (Logo ወይም Shop Photo) ይላኩ፦")
        admin_states[(token, chat_id)] = {"state": "WAITING_SHOP_PHOTO", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_SHOP_DESC")
    def process_shop_desc(message):
        chat_id = message.chat.id
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET shop_description=%s WHERE token=%s", (message.text.strip(), token))
                conn.commit()
        finally:
            put_conn(conn)
        bot.reply_to(message, "🎉 የሱቅዎ መገለጫ ሙሉ በሙሉ ተጠናቅቆ ተመዝግቧል!", reply_markup=get_admin_menu())
        admin_states[(token, chat_id)] = {"state": "", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_NEW_PASSWORD")
    def process_new_pass(message):
        chat_id = message.chat.id
        h_pass, salt = hash_password(message.text.strip())
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
    def handle_photos(message):
        chat_id = message.chat.id
        session_key = (token, chat_id)
        state_dict = admin_states.get(session_key, {"state": "", "data": {}})
        state = state_dict["state"]
        store = get_store_info()

        if state.startswith("AWAITING_RECEIPT_"):
            order_id = int(state.split("_")[2])
            admin_id = store["admin_id"] if store else chat_id
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                       types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"rejectorder_{order_id}"))
            bot.send_message(admin_id, f"🔔 **አዲስ የክፍያ ደረሰኝ ለትዕዛዝ #{order_id}**", reply_markup=markup, parse_mode="Markdown")
            bot.forward_message(admin_id, chat_id, message.message_id)
            bot.reply_to(message, "✅ ደረሰኝዎ ተልኳል።")
            admin_states[session_key] = {"state": "", "data": {}}
        elif state == "WAITING_SHOP_PHOTO":
            photo_id = message.photo[-1].file_id
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET shop_photo=%s WHERE token=%s", (photo_id, token))
                    conn.commit()
            finally:
                put_conn(conn)
            bot.reply_to(message, "✅ ፎቶ ተቀምጧል!\n\nደረጃ 4/4: ስለ ሱቅዎ አጭር መግለጫ (Description) ይጻፉ፦")
            admin_states[session_key] = {"state": "WAITING_SHOP_DESC", "data": {}}
        elif state == "WAITING_PRODUCT_PHOTO":
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

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_PRODUCT_DETAILS")
    def process_add_prod(message):
        session_key = (token, message.chat.id)
        try:
            parts = message.text.split(",")
            product_data = {
                "name_am": parts[0].strip(), "name_en": parts[1].strip(),
                "price": float(parts[2].strip()), "stock": int(parts[3].strip()),
                "desc_am": parts[4].strip(), "desc_en": parts[5].strip()
            }
            bot.reply_to(message, "📸 የምርቱን ፎቶ ይላኩ፦")
            admin_states[session_key] = {"state": "WAITING_PRODUCT_PHOTO", "data": product_data}
        except Exception:
            bot.reply_to(message, "❌ የፎርማት ስህተት አለ። በድጋሚ ይሞክሩ።")

    @bot.message_handler(func=lambda m: True)
    def handle_ai_fallback(message):
        if not check_active_middleware(message.chat.id):
            return
        if ai_model is None:
            return
        bot.send_chat_action(message.chat.id, 'typing')
        lang = get_user_lang(message.chat.id)
        store = get_store_info()
        try:
            prompt = f"You are an assistant for '{store['store_name']}'. Respond in {lang}."
            res = ai_model.generate_content(f"{prompt} {message.text}")
            bot.reply_to(message, res.text)
        except Exception:
            pass

    def _run_bot():
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception:
                time.sleep(5)

    threading.Thread(target=_run_bot, daemon=True).start()


def start_shop_bot(token):
    try:
        setup_bot_handlers(token)
    except Exception:
        return False
    return True


def load_stores():
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT token FROM stores")
            rows = cursor.fetchall()
    finally:
        put_conn(conn)
    for (tok,) in rows:
        start_shop_bot(tok)


load_stores()

# ============================================================
# 6. CONTROL BOT
# ============================================================
CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")

if CONTROL_BOT_TOKEN:
    control_bot = telebot.TeleBot(CONTROL_BOT_TOKEN)

    @control_bot.message_handler(commands=['start'])
    def control_start(message):
        control_bot.reply_to(
            message,
            "👋 እንኳን ወደ Control Bot በደህና መጡ!\n\n"
            "ቦት ለመመዝገብ፦\n"
            "`/connect [Token] [Password] [Store Name]`",
            parse_mode="Markdown"
        )

    @control_bot.message_handler(commands=['connect'])
    def connect_shop(message):
        args = message.text.split(maxsplit=3)
        if len(args) < 4:
            control_bot.reply_to(message, "⚠️ አጠቃቀም፦ `/connect [token] [password] [store_name]`", parse_mode="Markdown")
            return

        new_token, password, store_name = args[1].strip(), args[2].strip(), args[3].strip()
        try:
            bot_info = telebot.TeleBot(new_token).get_me()
        except Exception:
            control_bot.reply_to(message, "❌ የተሳሳተ Token!")
            return

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 FROM stores WHERE token=%s", (new_token,))
                if cursor.fetchone():
                    control_bot.reply_to(message, "❌ ይህ ቦት ተመዝግቧል።")
                    return
                h_pass, salt = hash_password(password)
                cursor.execute('''INSERT INTO stores (token, store_name, admin_id, password_hash, password_salt, telebirr)
                                  VALUES (%s, %s, %s, %s, %s, %s)''',
                               (new_token, store_name, message.chat.id, h_pass, salt, "0900000000"))
                conn.commit()
        finally:
            put_conn(conn)

        start_shop_bot(new_token)
        control_bot.reply_to(message, f"🎉 @{bot_info.username} ለ '{store_name}' ተመዝግቧል!")

    @control_bot.message_handler(commands=['search', 'search_engine'])
    def control_search_engine(message):
        control_bot.reply_to(message, "🔍 **የሰርች ሞተር መቆጣጠሪያ (Search Engine Control)**\n\nምርት ለመፈለግ የሚፈልጉትን ስም ብቻ ይጻፉ፦", parse_mode="Markdown")

    @control_bot.message_handler(func=lambda m: True)
    def control_search_handler(message):
        query = message.text.strip()
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT name_am, price, token FROM products WHERE name_am ILIKE %s OR name_en ILIKE %s LIMIT 5", (f"%{query}%", f"%{query}%"))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)

        if not rows:
            control_bot.reply_to(message, "❌ ምንም አልተገኘም።")
            return

        text = "🔍 **የፍለጋ ውጤቶች፦**\n\n"
        for name, price, tok in rows:
            text += f"▪️ {name} — {price} ETB\n"
        control_bot.reply_to(message, text, parse_mode="Markdown")

    def _run_control():
        while True:
            try:
                control_bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception:
                time.sleep(5)

    threading.Thread(target=_run_control, daemon=True).start()

while True:
    time.sleep(3600)
