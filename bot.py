import os
import threading
import hashlib
import secrets
import time
import math
import json
from datetime import datetime, timedelta
import telebot
from telebot import types, apihelper
import google.generativeai as genai
from flask import Flask, jsonify, request
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

# ============================================================
# 1. FLASK KEEP-ALIVE SERVER
# ============================================================
app = Flask('')

@app.route('/')
def home():
    return "🚀 Unified AI Shop Platform (Advanced Version) is Running!"

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/stats')
def stats():
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM stores")
            stores = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM products")
            products = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM orders")
            orders = cursor.fetchone()[0]
    finally:
        put_conn(conn)
    return jsonify({"stores": stores, "products": products, "orders": orders})

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
            # Stores table with additional fields
            cursor.execute('''CREATE TABLE IF NOT EXISTS stores (
                id SERIAL,
                token TEXT PRIMARY KEY,
                store_name TEXT,
                admin_id BIGINT,
                password_hash TEXT,
                password_salt TEXT,
                telebirr TEXT,
                cbebirr TEXT,
                is_active INTEGER DEFAULT 1,
                shop_lat REAL,
                shop_lng REAL,
                area_text TEXT,
                shop_photo TEXT,
                shop_description TEXT,
                opening_hours TEXT,
                delivery_radius REAL DEFAULT 5,
                min_order REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # Products table with discount
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
                discount REAL DEFAULT 0,
                discount_until TIMESTAMP,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # Orders table with more details
            cursor.execute('''CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                token TEXT,
                customer_id BIGINT,
                customer_phone TEXT,
                customer_lat REAL,
                customer_lng REAL,
                status_am TEXT,
                status_en TEXT,
                total_price REAL,
                delivery_fee REAL DEFAULT 0,
                discount_amount REAL DEFAULT 0,
                status_stage INTEGER DEFAULT 0,
                payment_method TEXT,
                payment_confirmed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # Order items table
            cursor.execute('''CREATE TABLE IF NOT EXISTS order_items (
                id SERIAL PRIMARY KEY,
                order_id INTEGER REFERENCES orders(id),
                product_id INTEGER REFERENCES products(id),
                product_name TEXT,
                quantity INTEGER,
                price REAL,
                subtotal REAL
            )''')

            # Reviews table
            cursor.execute('''CREATE TABLE IF NOT EXISTS reviews (
                id SERIAL PRIMARY KEY,
                product_id INTEGER REFERENCES products(id),
                customer_id BIGINT,
                rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # User language table
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_langs (
                chat_id BIGINT PRIMARY KEY,
                lang TEXT
            )''')

            # Customer info with more details
            cursor.execute('''CREATE TABLE IF NOT EXISTS customer_info (
                chat_id BIGINT PRIMARY KEY,
                phone TEXT,
                lat REAL,
                lng REAL,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')

            # Admin sessions
            cursor.execute('''CREATE TABLE IF NOT EXISTS admin_sessions (
                token TEXT,
                chat_id BIGINT,
                session_key TEXT,
                expires_at TIMESTAMP,
                PRIMARY KEY (token, chat_id)
            )''')

            conn.commit()
    finally:
        put_conn(conn)

init_db()

def hash_password(password, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def generate_session_token():
    return secrets.token_hex(32)

ORDER_STAGES_AM = ["🟡 በመጠባበቅ ላይ", "✅ ተረጋግጧል", "🚚 በመንገድ ላይ", "📦 ደርሷል"]
ORDER_STAGES_EN = ["🟡 Pending", "✅ Confirmed", "🚚 On the way", "📦 Delivered"]

# ============================================================
# 4. LOCALIZATION (11 Languages Support)
# ============================================================
STRINGS = {
    "am": {
        "welcome": "እንኳን ወደ AI የሽያጭ ረዳት ቦት በደህና መጡ! 👋",
        "shop": "🛍️ ምርቶችን እይ",
        "cart": "🛒 የእኔ ጋሪ",
        "track": "📦 ትዕዛዝ መከታተያ",
        "faq": "❓ መረጃ (FAQ)",
        "reviews": "⭐ ግምገማዎች",
        "empty": "🛒 ጋሪዎ በአሁኑ ሰዓት ባዶ ነው።",
        "added": "ወደ ጋሪ ተጨምሯል! 🛒",
        "total": "አጠቃላይ ድምር",
        "price_label": "ዋጋ",
        "discount": "ቅናሽ",
        "checkout_btn": "💳 ሂሳብ ማጠቃለያ",
        "clear_btn": "🗑️ ጋሪ አጽዳ",
        "enter_id": "🔢 እባክዎ የትዕዛዝ ቁጥርዎን (Order ID) ያስገቡ፦",
        "not_found": "❌ የትዕዛዝ ቁጥሩ አልተገኘም ወይም የዚህ ሱቅ አይደለም።",
        "invalid_id": "❌ የተሳሳተ ቁጥር ገብቷል።",
        "approved_msg": "🎉 ደስ የሚል ዜና! የትዕዛዝ ቁጥርዎ ክፍያ ተረጋግጦ ዕቃው እየመጣላችሁ ነው። 🛵",
        "rejected_msg": "❌ የትዕዛዝ ቁጥርዎ ክፍያ ማረጋገጫ ውድቅ ተደርጓል።",
        "receipt_prompt": "📸 እባክዎ የከፈሉበትን ደረሰኝ (Screenshot) ይላኩ።",
        "faq_text": "ℹ️ **ስለ ሱቃችን መረጃ**\n\n📍 አድራሻችን፦ አዲስ አበባ፣ ኢትዮጵያ\n📞 ስልክ፦ 0911223344",
        "rate_product": "⭐ ምርቱን ደረጃ ይስጡ",
        "thank_review": "🙏 ለግምገማዎ እናመሰግናለን!",
        "delivery_info": "🚚 የማድረስ መረጃ"
    },
    "en": {
        "welcome": "Welcome to AI Customer Service Bot! 👋",
        "shop": "🛍️ Shop Products",
        "cart": "🛒 My Cart",
        "track": "📦 Track Order",
        "faq": "❓ FAQ Info",
        "reviews": "⭐ Reviews",
        "empty": "🛒 Your cart is currently empty.",
        "added": "Added to cart! 🛒",
        "total": "Total",
        "price_label": "Price",
        "discount": "Discount",
        "checkout_btn": "💳 Checkout",
        "clear_btn": "🗑️ Clear Cart",
        "enter_id": "🔢 Please enter your Order ID:",
        "not_found": "❌ Order ID not found or invalid for this store.",
        "invalid_id": "❌ Invalid ID entered.",
        "approved_msg": "🎉 Great news! Your payment has been approved and your item is on the way! 🛵",
        "rejected_msg": "❌ Your payment could not be verified.",
        "receipt_prompt": "📸 Please send the payment confirmation screenshot here.",
        "faq_text": "ℹ️ **About Our Store**\n\n📍 Location: Addis Ababa, Ethiopia\n📞 Phone: +251911223344",
        "rate_product": "⭐ Rate this product",
        "thank_review": "🙏 Thank you for your review!",
        "delivery_info": "🚚 Delivery Information"
    },
    "zh": {
        "welcome": "欢迎使用 AI 客户服务机器人！ 👋",
        "shop": "🛍️ 购买商品",
        "cart": "🛒 我的购物车",
        "track": "📦 订单追踪",
        "faq": "❓ 常见问题",
        "reviews": "⭐ 评价",
        "empty": "🛒 您的购物车当前为空。",
        "added": "已加入购物车！ 🛒",
        "total": "总计",
        "price_label": "价格",
        "discount": "折扣",
        "checkout_btn": "💳 结账",
        "clear_btn": "🗑️ 清空购物车",
        "enter_id": "🔢 请输入您的订单编号：",
        "not_found": "❌ 未找到订单编号或对此商店无效。",
        "invalid_id": "❌ 输入的编号无效。",
        "approved_msg": "🎉 好消息！您的付款已验证，商品正在配送中！ 🛵",
        "rejected_msg": "❌ 您的付款无法验证。",
        "receipt_prompt": "📸 请在此发送支付凭证截图。",
        "faq_text": "ℹ️ **关于我们**\n\n📍 地点：埃塞俄比亚亚的斯亚贝巴\n📞 电话：+251911223344",
        "rate_product": "⭐ 评价此产品",
        "thank_review": "🙏 感谢您的评价！",
        "delivery_info": "🚚 配送信息"
    },
    "hi": {
        "welcome": "AI ग्राहक सेवा बॉट में आपका स्वागत है! 👋",
        "shop": "🛍️ उत्पाद खरीदें",
        "cart": "🛒 मेरी कार्ट",
        "track": "📦 ऑर्डर ट्रैक करें",
        "faq": "❓ अक्सर पूछे जाने वाले प्रश्न",
        "reviews": "⭐ समीक्षाएँ",
        "empty": "🛒 आपकी कार्ट वर्तमान में खाली है।",
        "added": "कार्ट में जोड़ा गया! 🛒",
        "total": "कुल",
        "price_label": "कीमत",
        "discount": "छूट",
        "checkout_btn": "💳 चेकआउट",
        "clear_btn": "🗑️ कार्ट साफ़ करें",
        "enter_id": "🔢 कृपया अपनी ऑर्डर आईडी दर्ज करें:",
        "not_found": "❌ ऑर्डर आईडी नहीं मिली या इस स्टोर के लिए अमान्य है।",
        "invalid_id": "❌ अमान्य आईडी दर्ज की गई।",
        "approved_msg": "🎉 अच्छी खबर! आपका भुगतान स्वीकृत हो गया है! 🛵",
        "rejected_msg": "❌ आपके भुगतान की पुष्टि नहीं हो सकी।",
        "receipt_prompt": "📸 कृपया यहाँ भुगतान स्क्रीनशॉट भेजें।",
        "faq_text": "ℹ️ **हमारे स्टोर के बारे में**\n\n📍 स्थान: अदीस अबाबा, इथियोपिया\n📞 फोन: +251911223344",
        "rate_product": "⭐ इस उत्पाद को रेट करें",
        "thank_review": "🙏 आपकी समीक्षा के लिए धन्यवाद!",
        "delivery_info": "🚚 डिलीवरी जानकारी"
    },
    "es": {
        "welcome": "¡Bienvenido al bot de servicio al cliente de IA! 👋",
        "shop": "🛍️ Comprar",
        "cart": "🛒 Mi Carrito",
        "track": "📦 Rastrear Pedido",
        "faq": "❓ Preguntas Frecuentes",
        "reviews": "⭐ Reseñas",
        "empty": "🛒 Tu carrito está vacío.",
        "added": "¡Agregado al carrito! 🛒",
        "total": "Total",
        "price_label": "Precio",
        "discount": "Descuento",
        "checkout_btn": "💳 Pagar",
        "clear_btn": "🗑️ Vaciar Carrito",
        "enter_id": "🔢 Por favor ingresa tu ID de pedido:",
        "not_found": "❌ ID de pedido no encontrado.",
        "invalid_id": "❌ ID inválido.",
        "approved_msg": "¡Buenas noticias! Tu pago ha sido aprobado. 🛵",
        "rejected_msg": "❌ Su pago no pudo ser verificado.",
        "receipt_prompt": "📸 Envía aquí la captura de pantalla del pago.",
        "faq_text": "ℹ️ **Información de la Tienda**\n\n📍 Ubicación: Adís Abeba, Etiopía\n📞 Teléfono: +251911223344",
        "rate_product": "⭐ Califica este producto",
        "thank_review": "🙏 ¡Gracias por tu reseña!",
        "delivery_info": "🚚 Información de entrega"
    },
    "ar": {
        "welcome": "أهلاً بك في بوت خدمة العملاء! 👋",
        "shop": "🛍️ تسوق المنتجات",
        "cart": "🛒 سلة التسوق",
        "track": "📦 تتبع الطلب",
        "faq": "❓ الأسئلة الشائعة",
        "reviews": "⭐ التقييمات",
        "empty": "🛒 سلة التسوق فارغة حالياً.",
        "added": "تمت الإضافة إلى السلة! 🛒",
        "total": "المجموع",
        "price_label": "السعر",
        "discount": "خصم",
        "checkout_btn": "💳 إتمام الشراء",
        "clear_btn": "🗑️ تفريغ السلة",
        "enter_id": "🔢 يرجى إدخال رقم الطلب:",
        "not_found": "❌ رقم الطلب غير موجود أو غير صالح.",
        "invalid_id": "❌ رقم غير صالح.",
        "approved_msg": "🎉 أخبار سارة! تم اعتماد الدفع! 🛵",
        "rejected_msg": "❌ تعذر التحقق من الدفع.",
        "receipt_prompt": "📸 يرجى إرسال لقطة شاشة إيصال الدفع هنا.",
        "faq_text": "ℹ️ **معلومات المتجر**\n\n📍 الموقع: أديس أبابا، إثيوبيا\n📞 الهاتف: +251911223344",
        "rate_product": "⭐ قيم هذا المنتج",
        "thank_review": "🙏 شكراً لتقييمك!",
        "delivery_info": "🚚 معلومات التوصيل"
    },
    "fr": {
        "welcome": "Bienvenue sur le bot du service client IA ! 👋",
        "shop": "🛍️ Acheter",
        "cart": "🛒 Mon Panier",
        "track": "📦 Suivre la commande",
        "faq": "❓ FAQ",
        "reviews": "⭐ Avis",
        "empty": "🛒 Votre panier est vide.",
        "added": "Ajouté au panier ! 🛒",
        "total": "Total",
        "price_label": "Prix",
        "discount": "Réduction",
        "checkout_btn": "💳 Commander",
        "clear_btn": "🗑️ Vider le panier",
        "enter_id": "🔢 Veuillez entrer votre ID de commande :",
        "not_found": "❌ ID de commande introuvable.",
        "invalid_id": "❌ ID invalide.",
        "approved_msg": "🎉 Bonne nouvelle ! Votre paiement a été approuvé ! 🛵",
        "rejected_msg": "❌ Échec de la vérification du paiement.",
        "receipt_prompt": "📸 Veuillez envoyer la capture d'écran du reçu de paiement ici.",
        "faq_text": "ℹ️ **À propos de notre magasin**\n\n📍 Lieu : Addis-Abeba, Éthiopie\n📞 Téléphone : +251911223344",
        "rate_product": "⭐ Notez ce produit",
        "thank_review": "🙏 Merci pour votre avis !",
        "delivery_info": "🚚 Informations de livraison"
    },
    "om": {
        "welcome": "Baga nagaan gara Bot Tajaajila Maamilootaa nagaan dhuftan! 👋",
        "shop": "🛍️ Oomishaalee Ilaali",
        "cart": "🛒 Kaartii Koo",
        "track": "📦 Ajaja Hordofaa",
        "faq": "❓ Odeeffannoo (FAQ)",
        "reviews": "⭐ Madaallii",
        "empty": "🛒 Kaartiin keessan amma duwwaa dha.",
        "added": "Kaartitti dabalamooti! 🛒",
        "total": "Waliigala",
        "price_label": "Gatii",
        "discount": "Kaffaltii Hir'ina",
        "checkout_btn": "💳 Baasii Xumuri",
        "clear_btn": "🗑️ Kaartii Qulqulleessi",
        "enter_id": "🔢 Maaloo Lakkoofsa Ajajaa (Order ID) galchaa:",
        "not_found": "❌ Lakkoofsi ajajaa hin argamne.",
        "invalid_id": "❌ Lakkoofsi dogoggoraan galeera.",
        "approved_msg": "🎉 Oduu gammachiisaa! Kaffaltiin keessan mirkanaa'ee jira! 🛵",
        "rejected_msg": "❌ Kaffaltiin keessan mirkanaa'uu hin dandeenye.",
        "receipt_prompt": "📸 Maaloo ragaa kaffaltii (Screenshot) asitti ergaa.",
        "faq_text": "ℹ️ **Waa'ee keenya**\n\n📍 Teessoo: Finfinnee, Itoophiyaa\n📞 Bilbila: 0911223344",
        "rate_product": "⭐ Oomisha kana madaali",
        "thank_review": "🙏 Madaallii keessaniif galatoomaa!",
        "delivery_info": "🚚 Odeeffannoo Dhiibuu"
    },
    "ti": {
        "welcome": "ብደሓን መጻእኩም ናብ AI ኣገልግሎት ዓሚል ቦት! 👋",
        "shop": "🛍️ ንብረት ርአ",
        "cart": "🛒 ሰፈረይ (Cart)",
        "track": "📦 ትእዛዝ ተከታተል",
        "faq": "❓ ሓበሬታ (FAQ)",
        "reviews": "⭐ ግምገማታት",
        "empty": "🛒 ሰፈርካ ድኩም እዩ።",
        "added": "ናብ ሰፈር ተወሲኹ! 🛒",
        "total": "ጠቕላላ",
        "price_label": "ዋጋ",
        "discount": "ቅናሽ",
        "checkout_btn": "💳 ክፍሊት ዛዘም",
        "clear_btn": "🗑️ ሰፈር ኣጽርይ",
        "enter_id": "🔢 እኩብ ቁጽሪ ትእዛዝ (Order ID) ኣእቱ፦",
        "not_found": "❌ ቁጽሪ ትእዛዝ ኣይተረኽበን።",
        "invalid_id": "❌ ግጉይ ቁጽሪ ኣትዩ።",
        "approved_msg": "🎉 ጽቡቕ ዜና! ክፍሊትካ ተረጋጊጹ ኣሎ! 🛵",
        "rejected_msg": "❌ ክፍሊትካ ክረጋገጽ ኣይክኣለን።",
        "receipt_prompt": "📸 በጃኹም መረጋገጺ ክፍሊት (Screenshot) ኣብዚ ስደዱ።",
        "faq_text": "ℹ️ **ብዛዕባ ድኳንና**\n\n📍 ኣድራሻ፦ ኣዲስ ኣበባ፣ ኢትዮጵያ\n📞 ስልኪ፦ 0911223344",
        "rate_product": "⭐ ንዚ ንብረት ደረጃ ሃብ",
        "thank_review": "🙏 ንግምገምካ እናመስግን!",
        "delivery_info": "🚚 ሓበሬታ ምድላው"
    },
    "so": {
        "welcome": "Ku soo dhawoow Adeegga Macmiilka AI! 👋",
        "shop": "🛍️ Alaabta Iibso",
        "cart": "🛒 Gaarigayga",
        "track": "📦 Raadi Dalabka",
        "faq": "❓ Macluumaad",
        "reviews": "⭐ Qiimaynta",
        "empty": "🛒 Gaarigagu waa madhan yahay.",
        "added": "Lagu daray gaariga! 🛒",
        "total": "Wadarta guud",
        "price_label": "Qiimaha",
        "discount": "Dhimis",
        "checkout_btn": "💳 Bixi",
        "clear_btn": "🗑️ Nadiifi Gaariga",
        "enter_id": "🔢 Fadlan geli Aqoonsiga Dalabka (Order ID):",
        "not_found": "❌ Lama helin lambarka dalabka.",
        "invalid_id": "❌ Lambar khaldan.",
        "approved_msg": "🎉 War farxad leh! Lacag bixintaadi waa la xaqiijiyay! 🛵",
        "rejected_msg": "❌ Lacag bixintaada lama xaqiijin karin.",
        "receipt_prompt": "📸 Fadlan halkan ka soo dir sawirka lacag bixinta (Screenshot).",
        "faq_text": "ℹ️ **Nagu saabsan**\n\n📍 Goobta: Addis Ababa, Itoobiya\n📞 Taleefanka: +251911223344",
        "rate_product": "⭐ Qiimee alaabtan",
        "thank_review": "🙏 Waad ku mahadsan tahay qiimayntaada!",
        "delivery_info": "🚚 Macluumaadka Dhiibista"
    },
    "aa": {
        "welcome": "AI Abbaayih Taysuma Bot fan inkih marhabax baah! 👋",
        "shop": "🛍️ Yanim Taysuma",
        "cart": "🛒 Ayunti Giriya",
        "track": "📦 Diggi Amri",
        "faq": "❓ Geytinna",
        "reviews": "⭐ Addad",
        "empty": "🛒 Ayuntik gari maaliyo.",
        "added": "Garih fanah abte! 🛒",
        "total": "Gabaaba",
        "price_label": "Qhiya",
        "discount": "Qhiya xagta",
        "checkout_btn": "💳 Xage",
        "clear_btn": "🗑️ Gari Gacsi",
        "enter_id": "🔢 Amri id (Order ID) rubba:",
        "not_found": "❌ Amri id ma geyne.",
        "invalid_id": "❌ Gugsissa id.",
        "approved_msg": "🎉 Wagsi xab! Xaqsu sugteh amaana ayyaaham yemeete! 🛵",
        "rejected_msg": "❌ Xaqsu ma sugto.",
        "receipt_prompt": "📸 Xaqsu sate screenshot-hadih taniih xaysi.",
        "faq_text": "ℹ️ **Dukaan geytinna**\n\n📍 Adda: Addis Ababa, Ethiopia\n📞 Telefoon: +251911223344",
        "rate_product": "⭐ Taamitak addada",
        "thank_review": "🙏 Addadiih gadda!",
        "delivery_info": "🚚 Waddak geytinna"
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
    "discounts": "🏷️ ቅናሾች",
    "reviews_manage": "⭐ ግምገማዎች",
    "logout": "🚪 ውጣ",
    "back": "⬅️ ተመለስ"
}

user_carts = {}
admin_states = {}
login_attempts = {}
lang_cache = {}

def get_main_menu(lang):
    ln = STRINGS[lang]
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton(ln["shop"]),
        types.KeyboardButton(ln["cart"]),
        types.KeyboardButton(ln["track"]),
        types.KeyboardButton(ln["faq"])
    )
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
        types.KeyboardButton(ADMIN_BTN["discounts"]),
        types.KeyboardButton(ADMIN_BTN["reviews_manage"])
    )
    markup.add(
        types.KeyboardButton(ADMIN_BTN["changepass"]),
        types.KeyboardButton(ADMIN_BTN["logout"])
    )
    markup.add(types.KeyboardButton(ADMIN_BTN["back"]))
    return markup

def get_customer_info(chat_id):
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT phone, lat, lng, address FROM customer_info WHERE chat_id=%s", (chat_id,))
            row = cursor.fetchone()
    finally:
        put_conn(conn)
    if row:
        return {"phone": row[0], "lat": row[1], "lng": row[2], "address": row[3]}
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

def get_store_info(token):
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''SELECT store_name, admin_id, telebirr, cbebirr, is_active, 
                              password_hash, password_salt, shop_lat, shop_lng, area_text,
                              shop_photo, shop_description, opening_hours, delivery_radius,
                              min_order, created_at
                              FROM stores WHERE token=%s''', (token,))
            row = cursor.fetchone()
    finally:
        put_conn(conn)
    if row:
        return {
            "store_name": row[0], "admin_id": row[1], "telebirr": row[2],
            "cbebirr": row[3], "is_active": row[4], "pass_hash": row[5],
            "salt": row[6], "shop_lat": row[7], "shop_lng": row[8],
            "area_text": row[9], "shop_photo": row[10], "shop_description": row[11],
            "opening_hours": row[12], "delivery_radius": row[13],
            "min_order": row[14], "created_at": row[15]
        }
    return None

# ============================================================
# 5. SHOP BOT ENGINE
# ============================================================
def setup_bot_handlers(token):
    bot = telebot.TeleBot(token)

    try:
        bot.remove_webhook()
    except Exception:
        pass

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
        store = get_store_info(token)
        if store and store["admin_id"] == chat_id:
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT expires_at FROM admin_sessions WHERE token=%s AND chat_id=%s",
                                   (token, chat_id))
                    row = cursor.fetchone()
                    if row and row[0] > datetime.now():
                        return True
            finally:
                put_conn(conn)
        return False

    def check_active_middleware(chat_id):
        store = get_store_info(token)
        if not store:
            bot.send_message(chat_id, "🏪 ይህ ሱቅ ገና አልተመዘገበም።")
            return False
        if not store["is_active"]:
            bot.send_message(chat_id, "❌ ይህ ሱቅ ንቁ አይደለም።")
            return False
        return True

    @bot.message_handler(commands=['start'])
    def choose_language(message):
        if not check_active_middleware(message.chat.id):
            return
        store = get_store_info(token)
        
        store_desc = store.get('shop_description') or "ጥራት ያለው እቃ ማቅረቢያ ሱቅ"
        store_loc = store.get('area_text') or "አዲስ አበባ"
        opening = store.get('opening_hours') or "መደበኛ ሰዓታት"
        
        caption = (
            f"🏪 **{store['store_name']}**\n\n"
            f"📝 **መግለጫ / Description:** {store_desc}\n"
            f"📍 **አድራሻ / Location:** {store_loc}\n"
            f"🕐 **ክፍት ሰዓታት / Hours:** {opening}\n"
            f"🚚 **የማድረስ ርቀት / Delivery Radius:** {store.get('delivery_radius', 5)} km\n"
            f"💰 **ዝቅተኛ ትዕዛዝ / Min Order:** {store.get('min_order', 0)} ETB\n\n"
            f"🌐 ቋንቋ ይምረጡ / Choose Language:"
        )
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="shoplang_am"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data="shoplang_en"),
            types.InlineKeyboardButton("Mandarin 🇨🇳", callback_data="shoplang_zh"),
            types.InlineKeyboardButton("Hindi 🇮🇳", callback_data="shoplang_hi"),
            types.InlineKeyboardButton("Spanish 🇪🇸", callback_data="shoplang_es"),
            types.InlineKeyboardButton("Arabic 🇸🇦", callback_data="shoplang_ar"),
            types.InlineKeyboardButton("French 🇫🇷", callback_data="shoplang_fr"),
            types.InlineKeyboardButton("ኦሮምኛ 🇪🇹", callback_data="shoplang_om"),
            types.InlineKeyboardButton("ትግርኛ 🇪🇹", callback_data="shoplang_ti"),
            types.InlineKeyboardButton("Somali 🇸🇴", callback_data="shoplang_so"),
            types.InlineKeyboardButton("Afar 🇪🇹", callback_data="shoplang_aa")
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
        store = get_store_info(token)
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
                    session_token = generate_session_token()
                    expires_at = datetime.now() + timedelta(hours=2)
                    cursor.execute('''INSERT INTO admin_sessions (token, chat_id, session_key, expires_at)
                                      VALUES (%s, %s, %s, %s)
                                      ON CONFLICT (token, chat_id) DO UPDATE 
                                      SET session_key = EXCLUDED.session_key, expires_at = EXCLUDED.expires_at''',
                                   (token, chat_id, session_token, expires_at))
                    conn.commit()
            finally:
                put_conn(conn)
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
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM admin_sessions WHERE token=%s AND chat_id=%s", (token, chat_id))
                conn.commit()
        finally:
            put_conn(conn)
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
            show_orders(chat_id)
        elif text == ADMIN_BTN["payment"]:
            bot.reply_to(message, "💰 እባክዎ **የቴሌብር እና CBE Birr ቁጥርዎን** በኮማ (,) ለይተው ይላኩ (ለምሳሌ፦ `0911223344,1000123456789`)፦", parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": "WAITING_PAYMENT_NUMBER", "data": {}}
        elif text == ADMIN_BTN["stats"]:
            show_stats(chat_id)
        elif text == ADMIN_BTN["profile"]:
            show_profile_setup(chat_id)
        elif text == ADMIN_BTN["discounts"]:
            show_discount_menu(chat_id)
        elif text == ADMIN_BTN["reviews_manage"]:
            show_reviews_manage(chat_id)
        elif text == ADMIN_BTN["changepass"]:
            bot.reply_to(message, "🔑 እባክዎ **አዲሱን የይለፍ ቃል** ይላኩ (ቢያንስ 8 ፊደል/ቁጥር)፦", parse_mode="Markdown")
            admin_states[(token, chat_id)] = {"state": "WAITING_NEW_PASSWORD", "data": {}}
        elif text == ADMIN_BTN["logout"]:
            do_logout(chat_id)

    def show_profile_setup(chat_id):
        loc_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        loc_markup.add(
            types.KeyboardButton("📍 የሱቅ አካባቢ አጋራ", request_location=True),
            types.KeyboardButton(ADMIN_BTN["back"])
        )
        bot.send_message(chat_id, "🏪 **የሱቅ መገለጫ ማዘጋጀት**\n\nደረጃ 1/6: የሱቅዎን አካባቢ (Location) ያጋሩ 👇", reply_markup=loc_markup, parse_mode="Markdown")
        admin_states[(token, chat_id)] = {"state": "WAITING_SHOP_LOCATION", "data": {}}

    def show_my_products(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name_am, price, stock, discount FROM products WHERE token=%s ORDER BY id", (token,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)

        if not rows:
            bot.send_message(chat_id, "📋 ምንም ምርት የለም።")
            return

        for p_id, name_am, price, stock, discount in rows:
            discount_text = f" 🏷️ {discount}% OFF" if discount and discount > 0 else ""
            text = f"📦 **#{p_id} {name_am}**\n💰 {price} ETB{discount_text}\n📦 ብዛት፦ {stock}"
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🗑️ ሰርዝ", callback_data=f"deleteproduct_{p_id}"),
                types.InlineKeyboardButton("🏷️ ቅናሽ አስተካክል", callback_data=f"discountprod_{p_id}")
            )
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    def show_orders(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT id, customer_id, total_price, status_stage, customer_phone,
                                  created_at, payment_method, payment_confirmed
                                  FROM orders WHERE token=%s AND status_stage NOT IN (3, -1)
                                  ORDER BY id DESC LIMIT 20''', (token,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)

        if not rows:
            bot.send_message(chat_id, "📋 ያልተጠናቀቁ ትዕዛዞች የሉም።")
            return

        for order in rows:
            order_id, cust_id, total, stage, phone, created_at, payment_method, confirmed = order
            stage = stage or 0
            status_label = ORDER_STAGES_AM[stage] if 0 <= stage <= 3 else "🟡 Pending"
            payment_status = "✅ Confirmed" if confirmed else "⏳ Pending"
            created = created_at.strftime("%Y-%m-%d %H:%M") if created_at else "N/A"
            
            text = (
                f"🆔 **ትዕዛዝ #{order_id}**\n"
                f"📅 {created}\n"
                f"📞 {phone or 'N/A'}\n"
                f"💵 {total} ETB\n"
                f"💰 {payment_status}\n"
                f"📌 {status_label}"
            )
            markup = types.InlineKeyboardMarkup()
            if stage == 0:
                markup.add(
                    types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                    types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"rejectorder_{order_id}")
                )
            elif stage == 1:
                markup.add(types.InlineKeyboardButton("🚚 በመንገድ ላይ", callback_data=f"advance_{order_id}"))
            elif stage == 2:
                markup.add(types.InlineKeyboardButton("📦 ደርሷል", callback_data=f"advance_{order_id}"))
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    def show_stats(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                # Total products
                cursor.execute("SELECT COUNT(*) FROM products WHERE token=%s", (token,))
                product_count = cursor.fetchone()[0]
                
                # Orders stats
                cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0) FROM orders WHERE token=%s AND status_stage >= 1", (token,))
                paid_count, revenue = cursor.fetchone()
                
                # Pending orders
                cursor.execute("SELECT COUNT(*) FROM orders WHERE token=%s AND status_stage=0", (token,))
                pending = cursor.fetchone()[0]
                
                # Average rating
                cursor.execute('''SELECT AVG(r.rating) FROM reviews r 
                                  JOIN products p ON r.product_id = p.id 
                                  WHERE p.token=%s''', (token,))
                avg_rating = cursor.fetchone()[0] or 0
                
                # Recent orders (last 7 days)
                cursor.execute('''SELECT COUNT(*) FROM orders 
                                  WHERE token=%s AND created_at > NOW() - INTERVAL '7 days' 
                                  AND status_stage >= 1''', (token,))
                weekly_orders = cursor.fetchone()[0]
        finally:
            put_conn(conn)

        text = (
            f"📊 **ስቲስቲክስ / Statistics**\n\n"
            f"📦 ምርቶች / Products: {product_count}\n"
            f"✅ የተከፈሉ / Paid Orders: {paid_count}\n"
            f"⏳ በመጠባበቅ ላይ / Pending: {pending}\n"
            f"💵 ገቢ / Revenue: {revenue:.2f} ETB\n"
            f"📈 በሳምንት / Weekly Orders: {weekly_orders}\n"
            f"⭐ አማካይ ደረጃ / Avg Rating: {avg_rating:.1f}/5.0"
        )
        bot.send_message(chat_id, text, parse_mode="Markdown")

    def show_discount_menu(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, name_am, price, discount FROM products WHERE token=%s", (token,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)

        if not rows:
            bot.send_message(chat_id, "📋 ምንም ምርት የለም።")
            return

        text = "🏷️ **የቅናሾች አስተዳደር / Discount Management**\n\n"
        for p_id, name, price, discount in rows:
            disc_text = f"{discount}% OFF" if discount and discount > 0 else "No discount"
            text += f"▪️ #{p_id} {name}: {discount_text}\n"
        
        text += "\n💡 ለቅናሽ ማከል የሚፈልጉትን ምርት ቁጥር እና ቅናሽ መጠን በኮማ ይላኩ፦\n`[product_id],[discount_percent]`"
        bot.send_message(chat_id, text, parse_mode="Markdown")
        admin_states[(token, chat_id)] = {"state": "WAITING_DISCOUNT", "data": {}}

    def show_reviews_manage(chat_id):
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''SELECT r.id, p.name_am, r.rating, r.comment, r.created_at, r.customer_id
                                  FROM reviews r JOIN products p ON r.product_id = p.id
                                  WHERE p.token=%s ORDER BY r.created_at DESC LIMIT 20''', (token,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)

        if not rows:
            bot.send_message(chat_id, "⭐ እስካሁን ምንም ግምገማ የለም።")
            return

        text = "⭐ **የቅርብ ጊዜ ግምገማዎች / Recent Reviews**\n\n"
        for r_id, p_name, rating, comment, created, cust_id in rows:
            stars = "⭐" * int(rating) + "☆" * (5 - int(rating))
            created_str = created.strftime("%Y-%m-%d") if created else "N/A"
            text += f"📦 {p_name}\n{stars} {rating}/5\n💬 {comment[:50]}...\n📅 {created_str}\n---\n"
        
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

    @bot.callback_query_handler(func=lambda call: call.data.startswith("discountprod_"))
    def set_product_discount(call):
        chat_id = call.message.chat.id
        if not is_verified_admin(chat_id):
            return
        p_id = call.data.split("_")[1]
        bot.send_message(chat_id, f"🏷️ ለምርት #{p_id} ቅናሽ መጠን በመቶኛ (1-99) ይላኩ፦")
        admin_states[(token, chat_id)] = {"state": f"WAITING_DISCOUNT_{p_id}", "data": {}}

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
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s, status_stage=1, payment_confirmed=TRUE, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
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
                    cursor.execute("UPDATE orders SET status_stage=-1, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (order_id,))
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
                    cursor.execute("UPDATE orders SET status_am=%s, status_en=%s, status_stage=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                                   (ORDER_STAGES_AM[new_stage], ORDER_STAGES_EN[new_stage], new_stage, order_id))
                    conn.commit()
                    cust_lang = get_user_lang(cust_id)
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
                cursor.execute('''SELECT id, name_am, name_en, price, stock, desc_am, desc_en, 
                                  image_url, discount, discount_until 
                                  FROM products WHERE token=%s''', (token,))
                rows = cursor.fetchall()
        finally:
            put_conn(conn)

        if not rows:
            bot.send_message(chat_id, "🛍️ ምንም ምርት የለም።")
            return

        for row in rows:
            p_id, name_am, name_en, price, stock, desc_am, desc_en, image_url, discount, discount_until = row
            name = name_am if lang in ["am", "om", "ti"] else name_en
            desc = desc_am if lang in ["am", "om", "ti"] else desc_en
            
            # Check if discount is valid
            discount_text = ""
            if discount and discount > 0:
                if discount_until is None or discount_until > datetime.now():
                    final_price = price * (1 - discount / 100)
                    discount_text = f"\n🏷️ {discount}% OFF → **{final_price:.2f} ETB**"
                else:
                    discount = 0
            
            text = f"📦 **{name}**\n💰 ዋጋ፦ {price} ETB{discount_text}\n📝 {desc}"
            markup = types.InlineKeyboardMarkup()
            if (stock or 0) > 0:
                markup.add(
                    types.InlineKeyboardButton("🛒 ወደ ጋሪ ጨምር", callback_data=f"shopadd_{p_id}"),
                    types.InlineKeyboardButton("⭐ ደረጃ ስጥ", callback_data=f"rateproduct_{p_id}")
                )
            
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

    @bot.callback_query_handler(func=lambda call: call.data.startswith("rateproduct_"))
    def rate_product(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        p_id = int(call.data.split("_")[1])
        
        markup = types.InlineKeyboardMarkup(row_width=5)
        for i in range(1, 6):
            markup.add(types.InlineKeyboardButton("⭐" * i, callback_data=f"rating_{p_id}_{i}"))
        
        bot.send_message(chat_id, STRINGS.get(lang, STRINGS["am"])["rate_product"], reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("rating_"))
    def process_rating(call):
        chat_id = call.message.chat.id
        lang = get_user_lang(chat_id)
        _, p_id, rating = call.data.split("_")
        p_id, rating = int(p_id), int(rating)
        
        # Request comment
        msg = bot.send_message(chat_id, "💬 እባክዎ ለምርቱ አስተያየትዎን ይጻፉ (ወይም 'ለቀው')፦")
        bot.register_next_step_handler(msg, process_review_comment, p_id, rating)
        bot.delete_message(chat_id, call.message.message_id)

    def process_review_comment(message, product_id, rating):
        chat_id = message.chat.id
        comment = message.text if message.text != "ለቀው" else ""
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('''INSERT INTO reviews (product_id, customer_id, rating, comment)
                                  VALUES (%s, %s, %s, %s)''',
                               (product_id, chat_id, rating, comment))
                conn.commit()
        finally:
            put_conn(conn)
        
        lang = get_user_lang(chat_id)
        bot.send_message(chat_id, STRINGS.get(lang, STRINGS["am"])["thank_review"])

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
                    cursor.execute("SELECT name_am, name_en, price, discount, discount_until FROM products WHERE id=%s AND token=%s", (p_id, token))
                    row = cursor.fetchone()
                    if row:
                        name = row[0] if lang in ["am", "om", "ti"] else row[1]
                        price = row[2]
                        discount = row[3] if row[3] and row[3] > 0 else 0
                        if discount and (row[4] is None or row[4] > datetime.now()):
                            price = price * (1 - discount / 100)
                        subtotal = price * qty
                        total += subtotal
                        text += f"▪️ {name} x {qty} = {subtotal:.2f} ETB\n"
        finally:
            put_conn(conn)

        store = get_store_info(token)
        min_order = store.get('min_order', 0) if store else 0
        
        text += f"\n💵 **አጠቃላይ / Total፦ {total:.2f} ETB**"
        if min_order > 0 and total < min_order:
            text += f"\n⚠️ ዝቅተኛ ትዕዛዝ {min_order} ETB ነው"
        
        markup = types.InlineKeyboardMarkup()
        if total >= min_order:
            markup.add(types.InlineKeyboardButton(ln["checkout_btn"], callback_data="shop_checkout"))
        markup.add(types.InlineKeyboardButton(ln["clear_btn"], callback_data="shop_clear"))
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

    def calculate_distance(lat1, lon1, lat2, lon2):
        # Haversine formula
        R = 6371  # Earth's radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    def finalize_checkout(chat_id, lang):
        cart_key = (token, chat_id)
        cart = user_carts.get(cart_key, {})
        if not cart:
            return
        
        store = get_store_info(token)
        items_total = 0
        delivery_fee = 0
        
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                # Calculate total with discounts
                for p_id, qty in cart.items():
                    cursor.execute("SELECT price, discount, discount_until FROM products WHERE id=%s AND token=%s", (p_id, token))
                    row = cursor.fetchone()
                    if row:
                        price = row[0]
                        discount = row[1] if row[1] and row[1] > 0 else 0
                        if discount and (row[2] is None or row[2] > datetime.now()):
                            price = price * (1 - discount / 100)
                        items_total += price * qty

                # Check delivery radius
                customer = get_customer_info(chat_id)
                if customer and customer.get('lat') and store and store.get('shop_lat'):
                    distance = calculate_distance(
                        store['shop_lat'], store['shop_lng'],
                        customer['lat'], customer['lng']
                    )
                    if distance > store.get('delivery_radius', 5):
                        delivery_fee = 50  # Additional fee for far delivery

                # Create order
                cursor.execute('''INSERT INTO orders (token, customer_id, customer_phone, customer_lat, customer_lng,
                                  status_am, status_en, total_price, delivery_fee, status_stage, created_at)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, CURRENT_TIMESTAMP) RETURNING id''',
                               (token, chat_id, customer.get('phone') if customer else None,
                                customer.get('lat') if customer else None, customer.get('lng') if customer else None,
                                ORDER_STAGES_AM[0], ORDER_STAGES_EN[0], items_total, delivery_fee))
                order_id = cursor.fetchone()[0]
                
                # Add order items
                for p_id, qty in cart.items():
                    cursor.execute("SELECT name_am, price FROM products WHERE id=%s AND token=%s", (p_id, token))
                    row = cursor.fetchone()
                    if row:
                        cursor.execute('''INSERT INTO order_items (order_id, product_id, product_name, quantity, price, subtotal)
                                          VALUES (%s, %s, %s, %s, %s, %s)''',
                                       (order_id, p_id, row[0], qty, row[1], row[1] * qty))
                
                conn.commit()
        finally:
            put_conn(conn)

        user_carts[cart_key] = {}
        ln = STRINGS.get(lang, STRINGS["am"])
        pay_info = f"📱 **Telebirr:** `{store.get('telebirr')}`"
        if store.get('cbebirr'):
            pay_info += f"\n🏦 **CBE Birr:** `{store.get('cbebirr')}`"
        
        total_with_delivery = items_total + delivery_fee
        delivery_text = f"\n🚚 የማድረስ ወጪ / Delivery Fee: {delivery_fee} ETB" if delivery_fee > 0 else ""

        pay_text = (
            f"🆔 **Order ID:** `{order_id}`\n"
            f"💵 **ሂሳብ / Total፦** {items_total:.2f} ETB{delivery_text}\n"
            f"💰 **አጠቃላይ / Grand Total:** {total_with_delivery:.2f} ETB\n\n"
            f"{pay_info}\n\n{ln['receipt_prompt']}"
        )
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
                markup.add(
                    types.KeyboardButton("📱 ስልክ ቁጥር አጋራ", request_contact=True),
                    types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True)
                )
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
                    cursor.execute("UPDATE stores SET shop_lat=%s, shop_lng=%s WHERE token=%s", 
                                   (message.location.latitude, message.location.longitude, token))
                    conn.commit()
            finally:
                put_conn(conn)
            bot.send_message(chat_id, "✅ አካባቢ ተቀምጧል!\n\nደረጃ 2/6: የሱቅዎን አካባቢ ስም (ለምሳሌ 'ቦሌ') በጽሁፍ ይላኩ፦")
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
        bot.reply_to(message, "✅ ተቀምጧል!\n\nደረጃ 3/6: የሱቅዎን ፎቶ (Logo ወይም Shop Photo) ይላኩ፦")
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
        bot.reply_to(message, "✅ ተቀምጧል!\n\nደረጃ 5/6: የሱቅዎን ክፍት ሰዓታት (ለምሳሌ 'ሰኞ-ቅዳሜ 8:00-20:00') ይላኩ፦")
        admin_states[(token, chat_id)] = {"state": "WAITING_SHOP_HOURS", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_SHOP_HOURS")
    def process_shop_hours(message):
        chat_id = message.chat.id
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE stores SET opening_hours=%s WHERE token=%s", (message.text.strip(), token))
                conn.commit()
        finally:
            put_conn(conn)
        bot.reply_to(message, "✅ ተቀምጧል!\n\nደረጃ 6/6: ዝቅተኛ የትዕዛዝ መጠን (Min Order) በETB ይላኩ (ለምሳሌ '200')፦")
        admin_states[(token, chat_id)] = {"state": "WAITING_MIN_ORDER", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_MIN_ORDER")
    def process_min_order(message):
        chat_id = message.chat.id
        try:
            min_order = float(message.text.strip())
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET min_order=%s WHERE token=%s", (min_order, token))
                    conn.commit()
            finally:
                put_conn(conn)
            bot.reply_to(message, "🎉 የሱቅዎ መገለጫ ሙሉ በሙሉ ተጠናቅቆ ተመዝግቧል!", reply_markup=get_admin_menu())
        except ValueError:
            bot.reply_to(message, "❌ የተሳሳተ ቁጥር! እባክዎ ደግመው ይሞክሩ።")
            return
        admin_states[(token, chat_id)] = {"state": "", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_NEW_PASSWORD")
    def process_new_pass(message):
        chat_id = message.chat.id
        if len(message.text.strip()) < 8:
            bot.reply_to(message, "❌ የይለፍ ቃሉ ቢያንስ 8 ፊደል/ቁጥር መሆን አለበት።")
            return
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

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state", "").startswith("WAITING_DISCOUNT"))
    def process_discount(message):
        chat_id = message.chat.id
        state = admin_states.get((token, chat_id), {}).get("state", "")
        
        try:
            if "_" in state:
                p_id = int(state.split("_")[1])
                discount = float(message.text.strip())
                if discount < 0 or discount > 99:
                    bot.reply_to(message, "❌ ቅናሽ ከ 0 እስከ 99 መቶኛ መሆን አለበት።")
                    return
                
                conn = get_safe_connection()
                try:
                    with conn.cursor() as cursor:
                        cursor.execute("UPDATE products SET discount=%s, discount_until=CURRENT_TIMESTAMP + INTERVAL '30 days' WHERE id=%s AND token=%s",
                                       (discount, p_id, token))
                        conn.commit()
                finally:
                    put_conn(conn)
                bot.reply_to(message, f"✅ ለምርት #{p_id} {discount}% ቅናሽ ተጨምሯል!")
            else:
                # Bulk discount from discount menu
                parts = message.text.split(",")
                if len(parts) == 2:
                    p_id, discount = int(parts[0].strip()), float(parts[1].strip())
                    if discount < 0 or discount > 99:
                        bot.reply_to(message, "❌ ቅናሽ ከ 0 እስከ 99 መቶኛ መሆን አለበት።")
                        return
                    conn = get_safe_connection()
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("UPDATE products SET discount=%s, discount_until=CURRENT_TIMESTAMP + INTERVAL '30 days' WHERE id=%s AND token=%s",
                                           (discount, p_id, token))
                            conn.commit()
                    finally:
                        put_conn(conn)
                    bot.reply_to(message, f"✅ ለምርት #{p_id} {discount}% ቅናሽ ተጨምሯል!")
                else:
                    bot.reply_to(message, "❌ የተሳሳተ ፎርማት! እባክዎ `[product_id],[discount_percent]` ይላኩ።")
        except ValueError:
            bot.reply_to(message, "❌ የተሳሳተ ቁጥር! እባክዎ ደግመው ይሞክሩ።")
        admin_states[(token, chat_id)] = {"state": "", "data": {}}

    @bot.message_handler(content_types=['photo'])
    def handle_photos(message):
        chat_id = message.chat.id
        session_key = (token, chat_id)
        state_dict = admin_states.get(session_key, {"state": "", "data": {}})
        state = state_dict["state"]
        store = get_store_info(token)

        if state.startswith("AWAITING_RECEIPT_"):
            order_id = int(state.split("_")[2])
            admin_id = store["admin_id"] if store else chat_id
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approveorder_{order_id}"),
                types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"rejectorder_{order_id}")
            )
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
            bot.reply_to(message, "✅ ፎቶ ተቀምጧል!\n\nደረጃ 4/6: ስለ ሱቅዎ አጭር መግለጫ (Description) ይጻፉ፦")
            admin_states[session_key] = {"state": "WAITING_SHOP_DESC", "data": {}}
        elif state == "WAITING_PRODUCT_PHOTO":
            photo_id = message.photo[-1].file_id
            p_data = state_dict["data"]
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute('''INSERT INTO products (token, name_am, name_en, price, stock, desc_am, desc_en, image_url)
                                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                                   (token, p_data["name_am"], p_data["name_en"], p_data["price"], p_data["stock"], 
                                    p_data["desc_am"], p_data["desc_en"], photo_id))
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
            if len(parts) < 6:
                bot.reply_to(message, "❌ ሁሉንም 6 መረጃዎች ማስገባት አለብዎት!")
                return
            product_data = {
                "name_am": parts[0].strip(),
                "name_en": parts[1].strip(),
                "price": float(parts[2].strip()),
                "stock": int(parts[3].strip()),
                "desc_am": parts[4].strip(),
                "desc_en": parts[5].strip()
            }
            bot.reply_to(message, "📸 የምርቱን ፎቶ ይላኩ፦")
            admin_states[session_key] = {"state": "WAITING_PRODUCT_PHOTO", "data": product_data}
        except Exception as e:
            bot.reply_to(message, f"❌ የፎርማት ስህተት አለ። በድጋሚ ይሞክሩ። {e}")

    @bot.message_handler(func=lambda m: m.text in [STRINGS[l]["track"] for l in STRINGS])
    def track_order(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        bot.reply_to(message, STRINGS.get(lang, STRINGS["am"])["enter_id"])
        admin_states[(token, chat_id)] = {"state": "WAITING_ORDER_TRACK", "data": {}}

    @bot.message_handler(func=lambda m: admin_states.get((token, m.chat.id), {}).get("state") == "WAITING_ORDER_TRACK")
    def process_order_track(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        try:
            order_id = int(message.text.strip())
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute('''SELECT status_am, status_en, total_price, delivery_fee, status_stage,
                                      created_at, customer_phone
                                      FROM orders WHERE id=%s AND token=%s AND customer_id=%s''',
                                   (order_id, token, chat_id))
                    row = cursor.fetchone()
            finally:
                put_conn(conn)
            
            if row:
                status_am, status_en, total, delivery, stage, created, phone = row
                stage = stage or 0
                status = status_am if lang in ["am", "om", "ti"] else status_en
                created_str = created.strftime("%Y-%m-%d %H:%M") if created else "N/A"
                
                text = (
                    f"📦 **ትዕዛዝ / Order #{order_id}**\n"
                    f"📅 {created_str}\n"
                    f"📞 {phone or 'N/A'}\n"
                    f"💵 {total:.2f} ETB"
                )
                if delivery and delivery > 0:
                    text += f"\n🚚 +{delivery:.2f} ETB (የማድረስ ወጪ)"
                text += f"\n📌 **{status}**"
                
                # Show progress bar
                stages = ["⬜", "⬜", "⬜", "⬜"]
                for i in range(min(stage, 3)):
                    stages[i] = "🟩"
                text += f"\n\n{''.join(stages)}"
                
                bot.send_message(chat_id, text, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, STRINGS.get(lang, STRINGS["am"])["not_found"])
        except ValueError:
            bot.send_message(chat_id, STRINGS.get(lang, STRINGS["am"])["invalid_id"])
        admin_states[(token, chat_id)] = {"state": "", "data": {}}

    @bot.message_handler(func=lambda m: m.text in [STRINGS[l]["faq"] for l in STRINGS])
    def show_faq(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        store = get_store_info(token)
        
        faq_text = STRINGS.get(lang, STRINGS["am"])["faq_text"]
        if store:
            extra_info = (
                f"\n\n🚚 **የማድረስ መረጃ / Delivery Info**\n"
                f"📍 አካባቢ / Area: {store.get('area_text', 'N/A')}\n"
                f"📏 ርቀት / Radius: {store.get('delivery_radius', 5)} km\n"
                f"💰 ዝቅተኛ ትዕዛዝ / Min Order: {store.get('min_order', 0)} ETB"
            )
            faq_text += extra_info
        
        bot.send_message(chat_id, faq_text, parse_mode="Markdown")

    @bot.message_handler(func=lambda m: True)
    def handle_ai_fallback(message):
        if not check_active_middleware(message.chat.id):
            return
        if ai_model is None:
            return
        bot.send_chat_action(message.chat.id, 'typing')
        lang = get_user_lang(message.chat.id)
        store = get_store_info(token)
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
        return True
    except Exception as e:
        print(f"Error starting bot for token {token[:10]}...: {e}")
        return False

def load_stores():
    conn = get_safe_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT token FROM stores WHERE is_active=1")
            rows = cursor.fetchall()
    finally:
        put_conn(conn)
    
    for (tok,) in rows:
        start_shop_bot(tok)

load_stores()

# ============================================================
# 6. SUPER ADMIN & CONTROL BOT ENGINE (SECURE & ADVANCED)
# ============================================================
CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")

if CONTROL_BOT_TOKEN:
    control_bot = telebot.TeleBot(CONTROL_BOT_TOKEN)

    # Admin authentication for control bot
    SUPER_ADMIN_IDS = [int(id) for id in os.environ.get("SUPER_ADMIN_IDS", "").split(",") if id]

    def is_super_admin(chat_id):
        return not SUPER_ADMIN_IDS or chat_id in SUPER_ADMIN_IDS

    def get_control_main_menu():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("📊 አጠቃላይ ስታቲስቲክስ (Analytics)"),
            types.KeyboardButton("📢 ማስታወቂያ አስተላልፍ (Broadcast)"),
            types.KeyboardButton("🏪 ሱቆችን አስተዳድር (Manage Stores)"),
            types.KeyboardButton("➕ አዲስ ሱቅ መዝግብ (Register Store)"),
            types.KeyboardButton("🤖 AI Business Assistant"),
            types.KeyboardButton("📈 ሪፖርቶች (Reports)"),
            types.KeyboardButton("❌ ውጣ / ሪሰት (Logout)")
        )
        return markup

    @control_bot.message_handler(commands=['start'])
    def control_start(message):
        if not is_super_admin(message.chat.id):
            control_bot.reply_to(message, "⛔ ያልተፈቀደ መዳረሻ! Unauthorized access!")
            return
            
        control_bot.reply_to(
            message,
            "🚀 **Super Admin Control Center**\n\n"
            "ይህ ሲስተም ሁሉንም ሱቆች ለመቆጣጠር ነው።\n"
            "ከታች ያሉትን ቁልፎች በመጫን ይጠቀሙ።",
            reply_markup=get_control_main_menu(),
            parse_mode="Markdown"
        )

    @control_bot.message_handler(func=lambda m: m.text == "➕ አዲስ ሱቅ መዝግብ (Register Store)")
    def prompt_register(message):
        if not is_super_admin(message.chat.id):
            return
        msg = control_bot.reply_to(
            message,
            "📝 **አዲስ ሱቅ ለመመዝገብ መረጃውን በሚከተለው ፎርማት ይላኩ፦**\n\n"
            "`[Token]#[Password]#[Store Name]`\n\n"
            "*(ምሳሌ፦ `123456:ABC-DEF#mypass123#የእኔ ሱቅ`)*",
            parse_mode="Markdown"
        )
        control_bot.register_next_step_handler(msg, process_store_registration)

    def process_store_registration(message):
        if not is_super_admin(message.chat.id):
            return
        try:
            control_bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass

        try:
            parts = message.text.split('#')
            if len(parts) < 3:
                control_bot.send_message(message.chat.id, "⚠️ የተሳሳተ ፎርማት!", reply_markup=get_control_main_menu())
                return

            new_token, password, store_name = parts[0].strip(), parts[1].strip(), parts[2].strip()
            bot_info = telebot.TeleBot(new_token).get_me()

            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM stores WHERE token=%s", (new_token,))
                    if cursor.fetchone():
                        control_bot.send_message(message.chat.id, "❌ ይህ ቦት ቀደም ሲል ተመዝግቧል!", reply_markup=get_control_main_menu())
                        return
                    h_pass, salt = hash_password(password)
                    cursor.execute('''INSERT INTO stores (token, store_name, admin_id, password_hash, password_salt, telebirr)
                                      VALUES (%s, %s, %s, %s, %s, %s)''',
                                   (new_token, store_name, message.chat.id, h_pass, salt, "0900000000"))
                    conn.commit()
            finally:
                put_conn(conn)

            start_shop_bot(new_token)
            control_bot.send_message(
                message.chat.id,
                f"🎉 **ሱቁ በስኬት ተመዝግቧል!**\n\n"
                f"🤖 ቦት፦ @{bot_info.username}\n"
                f"🏪 ሱቅ፦ {store_name}\n"
                f"🔒 ፓስወርድ ደህንነቱ ተጠብቆ ተቀምጧል።",
                reply_markup=get_control_main_menu(),
                parse_mode="Markdown"
            )
        except Exception as e:
            control_bot.send_message(message.chat.id, f"❌ ስህተት ተፈጥሯል፦ {e}", reply_markup=get_control_main_menu())

    @control_bot.message_handler(func=lambda m: m.text == "📊 አጠቃላይ ስታቲስቲክስ (Analytics)")
    def control_analytics(message):
        if not is_super_admin(message.chat.id):
            return
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM stores")
                total_stores = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0) FROM orders WHERE status_stage >= 1")
                total_orders, total_revenue = cursor.fetchone()
                cursor.execute("SELECT COUNT(*) FROM products")
                total_products = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM reviews")
                total_reviews = cursor.fetchone()[0]
                
                # Monthly revenue
                cursor.execute('''SELECT TO_CHAR(created_at, 'YYYY-MM'), COUNT(*), COALESCE(SUM(total_price + COALESCE(delivery_fee,0)),0)
                                  FROM orders WHERE status_stage >= 1 
                                  GROUP BY TO_CHAR(created_at, 'YYYY-MM') 
                                  ORDER BY 1 DESC LIMIT 6''')
                monthly_data = cursor.fetchall()
        finally:
            put_conn(conn)

        text = (
            f"📊 **የሲስተሙ አጠቃላይ መረጃ (Global Analytics)**\n\n"
            f"🏪 የተመዘገቡ ሱቆች፦ {total_stores}\n"
            f"📦 ምርቶች፦ {total_products}\n"
            f"⭐ ግምገማዎች፦ {total_reviews}\n"
            f"✅ የተጠናቀቁ ትዕዛዞች፦ {total_orders}\n"
            f"💵 አጠቃላይ ገቢ፦ {total_revenue:.2f} ETB\n\n"
            f"📈 **የቅርብ ጊዜ ወርሃዊ ገቢ / Monthly Revenue**\n"
        )
        
        for month, count, revenue in monthly_data:
            text += f"▪️ {month}: {count} orders - {revenue:.2f} ETB\n"

        control_bot.send_message(message.chat.id, text, reply_markup=get_control_main_menu(), parse_mode="Markdown")

    @control_bot.message_handler(func=lambda m: m.text == "📈 ሪፖርቶች (Reports)")
    def control_reports(message):
        if not is_super_admin(message.chat.id):
            return
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                # Top stores by revenue
                cursor.execute('''SELECT s.store_name, COUNT(o.id), COALESCE(SUM(o.total_price + COALESCE(o.delivery_fee,0)),0) as revenue
                                  FROM stores s 
                                  LEFT JOIN orders o ON s.token = o.token AND o.status_stage >= 1
                                  GROUP BY s.store_name
                                  ORDER BY revenue DESC LIMIT 5''')
                top_stores = cursor.fetchall()
                
                # Top products
                cursor.execute('''SELECT p.name_am, COUNT(oi.id) as sales, SUM(oi.quantity) as quantity
                                  FROM products p 
                                  JOIN order_items oi ON p.id = oi.product_id
                                  JOIN orders o ON oi.order_id = o.id
                                  WHERE o.status_stage >= 1
                                  GROUP BY p.name_am
                                  ORDER BY sales DESC LIMIT 5''')
                top_products = cursor.fetchall()
        finally:
            put_conn(conn)

        text = "📈 **ሪፖርቶች / Reports**\n\n"
        
        text += "🏆 **ከፍተኛ ገቢ ያላቸው ሱቆች / Top Stores**\n"
        for name, count, revenue in top_stores:
            text += f"▪️ {name}: {count} orders - {revenue:.2f} ETB\n"
        
        text += "\n📦 **በጣም የተሸጡ ምርቶች / Top Products**\n"
        for name, sales, quantity in top_products:
            text += f"▪️ {name}: {quantity} units ({sales} orders)\n"

        control_bot.send_message(message.chat.id, text, reply_markup=get_control_main_menu(), parse_mode="Markdown")

    @control_bot.message_handler(func=lambda m: m.text == "🏪 ሱቆችን አስተዳድር (Manage Stores)")
    def manage_stores(message):
        if not is_super_admin(message.chat.id):
            return
        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT store_name, token, is_active FROM stores")
                stores = cursor.fetchall()
        finally:
            put_conn(conn)

        if not stores:
            control_bot.send_message(message.chat.id, "⚠️ እስካሁን የተመዘገበ ሱቅ የለም።", reply_markup=get_control_main_menu())
            return

        text = "🏪 **የተመዘገቡ ሱቆች ዝርዝር፦**\n\n"
        for name, tok, active in stores:
            status = "✅ Active" if active else "❌ Inactive"
            text += f"▪️ **{name}** (`{tok[:10]}...`) - {status}\n"
        
        text += "\n💡 ሱቅን ለማንቃት/ለማጥፋት የሚከተሉትን ይላኩ፦\n`[token]#[on/off]`"
        control_bot.send_message(message.chat.id, text, reply_markup=get_control_main_menu(), parse_mode="Markdown")
        admin_states[("control", message.chat.id)] = {"state": "WAITING_STORE_TOGGLE", "data": {}}

    @control_bot.message_handler(func=lambda m: admin_states.get(("control", m.chat.id), {}).get("state") == "WAITING_STORE_TOGGLE")
    def process_store_toggle(message):
        if not is_super_admin(message.chat.id):
            return
        try:
            parts = message.text.split("#")
            if len(parts) < 2:
                control_bot.reply_to(message, "❌ የተሳሳተ ፎርማት! `[token]#[on/off]`", reply_markup=get_control_main_menu())
                return
            
            tok, action = parts[0].strip(), parts[1].strip()
            is_active = 1 if action.lower() == "on" else 0
            
            conn = get_safe_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE stores SET is_active=%s WHERE token=%s", (is_active, tok))
                    conn.commit()
            finally:
                put_conn(conn)
            
            status = "አንቃቷል" if is_active else "አጥፍቷል"
            control_bot.send_message(message.chat.id, f"✅ ሱቁ በስኬት {status}!", reply_markup=get_control_main_menu())
        except Exception as e:
            control_bot.send_message(message.chat.id, f"❌ ስህተት፦ {e}", reply_markup=get_control_main_menu())
        admin_states[("control", message.chat.id)] = {"state": "", "data": {}}

    @control_bot.message_handler(func=lambda m: m.text == "📢 ማስታወቂያ አስተላልፍ (Broadcast)")
    def prompt_broadcast(message):
        if not is_super_admin(message.chat.id):
            return
        msg = control_bot.reply_to(
            message,
            "📢 ለሁሉም የሱቅ ባለቤቶች ማስተላለፍ የሚፈልጉትን መልእክት ይጻፉ:\n\n"
            "💡 መልእክቱ ከስር ባለው ፎርማት ይላኩ:\n"
            "`[Text]#[Image_URL (optional)]`\n"
            "(ምሳሌ፦ `የአዲስ ዓመት መልካም ምኞት!#https://example.com/photo.jpg`)"
        )
        control_bot.register_next_step_handler(msg, execute_broadcast)

    def execute_broadcast(message):
        if not is_super_admin(message.chat.id):
            return
        parts = message.text.split("#")
        broadcast_text = parts[0].strip()
        image_url = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None

        conn = get_safe_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT DISTINCT admin_id FROM stores WHERE admin_id IS NOT NULL")
                admins = cursor.fetchall()
        finally:
            put_conn(conn)

        success_count = 0
        fail_count = 0
        
        for (adm_id,) in admins:
            try:
                if image_url:
                    control_bot.send_photo(
                        adm_id,
                        image_url,
                        caption=f"📢 **ከዋናው አስተዳዳሪ የተላከ ማስታወቂያ፦**\n\n{broadcast_text}",
                        parse_mode="Markdown"
                    )
                else:
                    control_bot.send_message(
                        adm_id,
                        f"📢 **ከዋናው አስተዳዳሪ የተላከ ማስታወቂያ፦**\n\n{broadcast_text}",
                        parse_mode="Markdown"
                    )
                success_count += 1
            except Exception:
                fail_count += 1

        control_bot.send_message(
            message.chat.id,
            f"✅ መልእክቱ ለ {success_count} የሱቅ ባለቤቶች ተልኳል!\n"
            f"❌ {fail_count} አልተላኩም።",
            reply_markup=get_control_main_menu()
        )

    @control_bot.message_handler(func=lambda m: m.text == "🤖 AI Business Assistant")
    def prompt_ai(message):
        if not is_super_admin(message.chat.id):
            return
        msg = control_bot.reply_to(
            message,
            "🤖 **AI Business Assistant**\n\n"
            "ስለ ንግድ ስራዎ፣ የዋጋ አወጣጥ፣ የደንበኛ አገልግሎት፣\n"
            "ወይም ሌላ ማንኛውም ጥያቄ መጠየቅ ይችላሉ።"
        )
        control_bot.register_next_step_handler(msg, execute_ai_query)

    def execute_ai_query(message):
        if not is_super_admin(message.chat.id):
            return
        query = message.text
        if ai_model:
            try:
                control_bot.send_chat_action(message.chat.id, 'typing')
                res = ai_model.generate_content(
                    f"You are an expert E-commerce and Business Advisor in Ethiopia. "
                    f"Give practical, actionable advice. Question: {query}"
                )
                control_bot.send_message(
                    message.chat.id,
                    f"🤖 **AI Response**\n\n{res.text}",
                    reply_markup=get_control_main_menu()
                )
                return
            except Exception as e:
                control_bot.send_message(
                    message.chat.id,
                    f"❌ AI አገልግሎት ማግኘት አልተቻለም። Error: {e}",
                    reply_markup=get_control_main_menu()
                )
        else:
            control_bot.send_message(
                message.chat.id,
                "❌ AI አገልግሎት አልተዋቀረም።",
                reply_markup=get_control_main_menu()
            )

    @control_bot.message_handler(func=lambda m: m.text == "❌ ውጣ / ሪሰት (Logout)")
    def logout_control(message):
        if not is_super_admin(message.chat.id):
            return
        control_bot.send_message(
            message.chat.id,
            "🔒 ሲስተሙን በሰላም ዘግተዋል። እንደገና ለመጀመር `/start` ይጫኑ።",
            reply_markup=types.ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )

    def _run_control():
        while True:
            try:
                control_bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception:
                time.sleep(5)

    threading.Thread(target=_run_control, daemon=True).start()

while True:
    time.sleep(3600)
