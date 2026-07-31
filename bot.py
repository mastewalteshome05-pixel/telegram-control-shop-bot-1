"""
====================================================================================================
                    🚀 CONTROL BOT v7.0 - 12 LANGUAGES 🚀
        የ12 ቋንቋዎች ድጋፍ ያለው የሱቅ አስተዳደር ሲስተም
====================================================================================================

የተደገፉ ቋንቋዎች:
    1. አማርኛ (Amharic) 🇪🇹
    2. English 🇬🇧
    3. Mandarin Chinese (中文) 🇨🇳
    4. Hindi (हिन्दी) 🇮🇳
    5. Spanish (Español) 🇪🇸
    6. Arabic (العربية) 🇸🇦
    7. French (Français) 🇫🇷
    8. ኦሮምኛ (Oromo) 🇪🇹
    9. ትግርኛ (Tigrinya) 🇪🇹
    10. Somali (Soomaali) 🇸🇴
    11. Afar (Qafar) 🇪🇹
    12. ሲዳምኛ (Sidama) 🇪🇹
====================================================================================================
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
import io
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

# Install required packages if missing
def install_package(package):
    try:
        __import__(package)
        return True
    except ImportError:
        print(f"⚠️ Installing {package}...")
        os.system(f"pip install {package}")
        return True

# Install required packages
for pkg in ['telebot', 'psycopg2-binary', 'flask', 'flask-cors', 'Pillow']:
    install_package(pkg)

# Third-party imports
import telebot
from telebot import types
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify
from flask_cors import CORS
from PIL import Image

# =================================================================================================
#                           CONFIGURATION
# =================================================================================================

class Config:
    DATABASE_URL = os.environ.get("DATABASE_URL")
    CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")
    SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
    SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
    PORT = int(os.environ.get("PORT", "8080"))
    HOST = os.environ.get("HOST", "0.0.0.0")
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    DATABASE_POOL_MIN = int(os.environ.get("DATABASE_POOL_MIN", "2"))
    DATABASE_POOL_MAX = int(os.environ.get("DATABASE_POOL_MAX", "20"))
    SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "7200"))
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION = int(os.environ.get("LOCKOUT_DURATION", "900"))
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("LOG_FILE", "control_bot.log")

# Validate required config
if not Config.DATABASE_URL:
    raise ValueError("❌ DATABASE_URL required!")
if not Config.CONTROL_BOT_TOKEN:
    raise ValueError("❌ CONTROL_BOT_TOKEN required!")

# =================================================================================================
#                           LOGGING
# =================================================================================================

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ControlBot')

# =================================================================================================
#                           DATABASE LAYER
# =================================================================================================

db_pool = None
db_pool_lock = threading.Lock()

def init_db_pool():
    global db_pool
    with db_pool_lock:
        if db_pool is None:
            try:
                db_pool = ThreadedConnectionPool(
                    Config.DATABASE_POOL_MIN,
                    Config.DATABASE_POOL_MAX,
                    dsn=Config.DATABASE_URL
                )
                conn = db_pool.getconn()
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                db_pool.putconn(conn)
                logger.info("✅ Database pool initialized")
            except Exception as e:
                logger.error(f"❌ Database pool init failed: {e}")
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
        logger.error(f"❌ Connection error: {e}")
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
        except:
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
        logger.error(f"❌ DB error: {e}")
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
        logger.error(f"❌ DB error: {e}")
        raise
    finally:
        if conn:
            put_db_connection(conn)

# =================================================================================================
#                           DATABASE SCHEMA
# =================================================================================================

def init_schema():
    schema = """
    CREATE TABLE IF NOT EXISTS stores (
        id SERIAL PRIMARY KEY,
        token TEXT UNIQUE NOT NULL,
        store_name TEXT NOT NULL,
        admin_id BIGINT,
        username TEXT,
        phone TEXT,
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL,
        telebirr TEXT,
        cbebirr TEXT,
        bank_name TEXT,
        bank_account TEXT,
        is_active INTEGER DEFAULT 1,
        is_approved INTEGER DEFAULT 0,
        shop_lat REAL,
        shop_lng REAL,
        area_text TEXT,
        shop_photo TEXT,
        shop_description TEXT,
        rating REAL DEFAULT 0,
        total_sales REAL DEFAULT 0,
        total_orders INTEGER DEFAULT 0,
        bot_status TEXT DEFAULT 'stopped',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_langs (
        chat_id BIGINT PRIMARY KEY,
        lang TEXT DEFAULT 'am',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS customer_info (
        chat_id BIGINT PRIMARY KEY,
        phone TEXT,
        lat REAL,
        lng REAL,
        address TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS ethiopian_banks (
        id SERIAL PRIMARY KEY,
        name_am TEXT NOT NULL,
        name_en TEXT NOT NULL,
        code TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    try:
        db_execute(schema)
        logger.info("✅ Database schema initialized")
        seed_banks()
    except Exception as e:
        logger.error(f"❌ Schema init failed: {e}")
        raise

def seed_banks():
    banks = [
        ("አብይ ኢትዮጵያ ባንክ", "Commercial Bank of Ethiopia", "CBE"),
        ("የኢትዮጵያ ልማት ባንክ", "Development Bank of Ethiopia", "DBE"),
        ("የኢትዮጵያ ንግድ ባንክ", "Bank of Abyssinia", "BOA"),
        ("የኢትዮጵያ የገበያ ባንክ", "Awash Bank", "AWB"),
        ("የኢትዮጵያ የግብርና ባንክ", "Dashen Bank", "DASH"),
        ("የኢትዮጵያ የኢንዱስትሪ ባንክ", "Wegagen Bank", "WEG"),
        ("የኢትዮጵያ የንግድ ባንክ", "Oromia Bank", "ORO"),
        ("የኢትዮጵያ የልማት ባንክ", "Zemen Bank", "ZEM"),
        ("የኢትዮጵያ የህዝብ ባንክ", "Bereka Bank", "BER"),
        ("ቴሌብር", "Telebirr", "TEL"),
        ("ሲቢኢ ብር", "CBE Birr", "CBEB"),
    ]
    
    for name_am, name_en, code in banks:
        try:
            db_execute("""
                INSERT INTO ethiopian_banks (name_am, name_en, code)
                VALUES (%s, %s, %s)
                ON CONFLICT (code) DO NOTHING
            """, (name_am, name_en, code))
        except:
            pass

init_db_pool()
init_schema()

# =================================================================================================
#                           12 LANGUAGES SUPPORT
# =================================================================================================

LANGUAGES = {
    "am": {"name": "አማርኛ", "flag": "🇪🇹", "code": "am"},
    "en": {"name": "English", "flag": "🇬🇧", "code": "en"},
    "zh": {"name": "中文", "flag": "🇨🇳", "code": "zh"},
    "hi": {"name": "हिन्दी", "flag": "🇮🇳", "code": "hi"},
    "es": {"name": "Español", "flag": "🇪🇸", "code": "es"},
    "ar": {"name": "العربية", "flag": "🇸🇦", "code": "ar"},
    "fr": {"name": "Français", "flag": "🇫🇷", "code": "fr"},
    "or": {"name": "ኦሮምኛ", "flag": "🇪🇹", "code": "or"},
    "ti": {"name": "ትግርኛ", "flag": "🇪🇹", "code": "ti"},
    "so": {"name": "Soomaali", "flag": "🇸🇴", "code": "so"},
    "aa": {"name": "Qafar", "flag": "🇪🇹", "code": "aa"},
    "sid": {"name": "ሲዳምኛ", "flag": "🇪🇹", "code": "sid"},
}

# =================================================================================================
#                           LOCALIZATION STRINGS - 12 LANGUAGES
# =================================================================================================

STRINGS = {
    "am": {  # Amharic
        "welcome": "👋 እንኳን ወደ ሱቅ አስተዳደር ሲስተም በደህና መጡ!",
        "choose_language": "🌐 ቋንቋ ይምረጡ:",
        "register": "📝 አዲስ ሱቅ መዝግብ",
        "my_stores": "🏪 ሱቆቼ",
        "search": "🔍 ሱቆችን ፈልግ",
        "help": "❓ እርዳታ",
        "back": "🔙 ወደ ኋላ",
        "no_results": "🔍 ምንም አልተገኘም",
        "phone_required": "📱 እባክዎ ስልክ ቁጥርዎን ያጋሩ:",
        "phone_verified": "✅ ስልክ ቁጥርዎ ተረጋግጧል!",
        "step_1": "📝 ደረጃ 1/6: የቦት ቶከን ያስገቡ",
        "step_2": "📛 ደረጃ 2/6: የሱቅ ስም ያስገቡ",
        "step_3": "🔐 ደረጃ 3/6: የይለፍ ቃል ያስገቡ",
        "step_4": "📍 ደረጃ 4/6: የሱቅ አካባቢ ያጋሩ",
        "step_5": "📸 ደረጃ 5/6: የሱቅ ፎቶ ይላኩ",
        "step_6": "📝 ደረጃ 6/6: ስለ ሱቅ መግለጫ ያስገቡ",
        "registration_complete": "✅ ሱቅ ተመዝግቧል!",
        "store_info": "🏪 የሱቅ መረጃ",
        "no_stores": "❌ ምንም ሱቅ አልተገኘም",
        "bank_selection": "🏛️ ባንክ ይምረጡ:",
        "products": "🛍️ ምርቶች",
        "cart": "🛒 ጋሪ",
        "orders": "📦 ትዕዛዝ",
        "location": "📍 መረጃ",
        "search_by_name": "📝 በስም ፈልግ",
        "search_by_location": "📍 በአካባቢ ፈልግ",
        "superadmin": "👑 Super Admin",
    },
    "en": {  # English
        "welcome": "👋 Welcome to Store Management System!",
        "choose_language": "🌐 Choose Language:",
        "register": "📝 Register New Store",
        "my_stores": "🏪 My Stores",
        "search": "🔍 Search Stores",
        "help": "❓ Help",
        "back": "🔙 Back",
        "no_results": "🔍 No results found",
        "phone_required": "📱 Please share your phone number:",
        "phone_verified": "✅ Phone number verified!",
        "step_1": "📝 Step 1/6: Enter Bot Token",
        "step_2": "📛 Step 2/6: Enter Store Name",
        "step_3": "🔐 Step 3/6: Enter Password",
        "step_4": "📍 Step 4/6: Share Store Location",
        "step_5": "📸 Step 5/6: Send Store Photo",
        "step_6": "📝 Step 6/6: Enter Store Description",
        "registration_complete": "✅ Store registered successfully!",
        "store_info": "🏪 Store Information",
        "no_stores": "❌ No stores found",
        "bank_selection": "🏛️ Select Bank:",
        "products": "🛍️ Products",
        "cart": "🛒 Cart",
        "orders": "📦 Orders",
        "location": "📍 Information",
        "search_by_name": "📝 Search by Name",
        "search_by_location": "📍 Search by Location",
        "superadmin": "👑 Super Admin",
    },
    "zh": {  # Mandarin Chinese
        "welcome": "👋 欢迎来到商店管理系统！",
        "choose_language": "🌐 选择语言:",
        "register": "📝 注册新商店",
        "my_stores": "🏪 我的商店",
        "search": "🔍 搜索商店",
        "help": "❓ 帮助",
        "back": "🔙 返回",
        "no_results": "🔍 未找到结果",
        "phone_required": "📱 请分享您的电话号码:",
        "phone_verified": "✅ 电话号码已验证!",
        "step_1": "📝 步骤 1/6: 输入机器人令牌",
        "step_2": "📛 步骤 2/6: 输入商店名称",
        "step_3": "🔐 步骤 3/6: 输入密码",
        "step_4": "📍 步骤 4/6: 分享商店位置",
        "step_5": "📸 步骤 5/6: 发送商店照片",
        "step_6": "📝 步骤 6/6: 输入商店描述",
        "registration_complete": "✅ 商店注册成功!",
        "store_info": "🏪 商店信息",
        "no_stores": "❌ 未找到商店",
        "bank_selection": "🏛️ 选择银行:",
        "products": "🛍️ 产品",
        "cart": "🛒 购物车",
        "orders": "📦 订单",
        "location": "📍 信息",
        "search_by_name": "📝 按名称搜索",
        "search_by_location": "📍 按位置搜索",
        "superadmin": "👑 超级管理员",
    },
    "hi": {  # Hindi
        "welcome": "👋 स्टोर प्रबंधन प्रणाली में आपका स्वागत है!",
        "choose_language": "🌐 भाषा चुनें:",
        "register": "📝 नया स्टोर पंजीकृत करें",
        "my_stores": "🏪 मेरे स्टोर",
        "search": "🔍 स्टोर खोजें",
        "help": "❓ सहायता",
        "back": "🔙 वापस",
        "no_results": "🔍 कोई परिणाम नहीं मिला",
        "phone_required": "📱 कृपया अपना फोन नंबर साझा करें:",
        "phone_verified": "✅ फोन नंबर सत्यापित!",
        "step_1": "📝 चरण 1/6: बॉट टोकन दर्ज करें",
        "step_2": "📛 चरण 2/6: स्टोर का नाम दर्ज करें",
        "step_3": "🔐 चरण 3/6: पासवर्ड दर्ज करें",
        "step_4": "📍 चरण 4/6: स्टोर स्थान साझा करें",
        "step_5": "📸 चरण 5/6: स्टोर फोटो भेजें",
        "step_6": "📝 चरण 6/6: स्टोर विवरण दर्ज करें",
        "registration_complete": "✅ स्टोर सफलतापूर्वक पंजीकृत!",
        "store_info": "🏪 स्टोर की जानकारी",
        "no_stores": "❌ कोई स्टोर नहीं मिला",
        "bank_selection": "🏛️ बैंक चुनें:",
        "products": "🛍️ उत्पाद",
        "cart": "🛒 कार्ट",
        "orders": "📦 ऑर्डर",
        "location": "📍 जानकारी",
        "search_by_name": "📝 नाम से खोजें",
        "search_by_location": "📍 स्थान से खोजें",
        "superadmin": "👑 सुपर एडमिन",
    },
    "es": {  # Spanish
        "welcome": "👋 ¡Bienvenido al Sistema de Gestión de Tiendas!",
        "choose_language": "🌐 Seleccionar idioma:",
        "register": "📝 Registrar nueva tienda",
        "my_stores": "🏪 Mis Tiendas",
        "search": "🔍 Buscar Tiendas",
        "help": "❓ Ayuda",
        "back": "🔙 Volver",
        "no_results": "🔍 No se encontraron resultados",
        "phone_required": "📱 Por favor comparta su número de teléfono:",
        "phone_verified": "✅ ¡Número de teléfono verificado!",
        "step_1": "📝 Paso 1/6: Ingresar Token del Bot",
        "step_2": "📛 Paso 2/6: Ingresar Nombre de la Tienda",
        "step_3": "🔐 Paso 3/6: Ingresar Contraseña",
        "step_4": "📍 Paso 4/6: Compartir Ubicación de la Tienda",
        "step_5": "📸 Paso 5/6: Enviar Foto de la Tienda",
        "step_6": "📝 Paso 6/6: Ingresar Descripción de la Tienda",
        "registration_complete": "✅ ¡Tienda registrada exitosamente!",
        "store_info": "🏪 Información de la Tienda",
        "no_stores": "❌ No se encontraron tiendas",
        "bank_selection": "🏛️ Seleccionar banco:",
        "products": "🛍️ Productos",
        "cart": "🛒 Carrito",
        "orders": "📦 Pedidos",
        "location": "📍 Información",
        "search_by_name": "📝 Buscar por Nombre",
        "search_by_location": "📍 Buscar por Ubicación",
        "superadmin": "👑 Super Administrador",
    },
    "ar": {  # Arabic
        "welcome": "👋 مرحبا بكم في نظام إدارة المتاجر!",
        "choose_language": "🌐 اختر اللغة:",
        "register": "📝 تسجيل متجر جديد",
        "my_stores": "🏪 متاجري",
        "search": "🔍 البحث عن متاجر",
        "help": "❓ مساعدة",
        "back": "🔙 رجوع",
        "no_results": "🔍 لم يتم العثور على نتائج",
        "phone_required": "📱 يرجى مشاركة رقم هاتفك:",
        "phone_verified": "✅ تم التحقق من رقم الهاتف!",
        "step_1": "📝 الخطوة 1/6: أدخل رمز البوت",
        "step_2": "📛 الخطوة 2/6: أدخل اسم المتجر",
        "step_3": "🔐 الخطوة 3/6: أدخل كلمة المرور",
        "step_4": "📍 الخطوة 4/6: شارك موقع المتجر",
        "step_5": "📸 الخطوة 5/6: أرسل صورة المتجر",
        "step_6": "📝 الخطوة 6/6: أدخل وصف المتجر",
        "registration_complete": "✅ تم تسجيل المتجر بنجاح!",
        "store_info": "🏪 معلومات المتجر",
        "no_stores": "❌ لم يتم العثور على متاجر",
        "bank_selection": "🏛️ اختر البنك:",
        "products": "🛍️ المنتجات",
        "cart": "🛒 السلة",
        "orders": "📦 الطلبات",
        "location": "📍 المعلومات",
        "search_by_name": "📝 البحث بالاسم",
        "search_by_location": "📍 البحث بالموقع",
        "superadmin": "👑 المشرف العام",
    },
    "fr": {  # French
        "welcome": "👋 Bienvenue dans le système de gestion de magasins!",
        "choose_language": "🌐 Choisir la langue:",
        "register": "📝 Enregistrer un nouveau magasin",
        "my_stores": "🏪 Mes Magasins",
        "search": "🔍 Rechercher des magasins",
        "help": "❓ Aide",
        "back": "🔙 Retour",
        "no_results": "🔍 Aucun résultat trouvé",
        "phone_required": "📱 Veuillez partager votre numéro de téléphone:",
        "phone_verified": "✅ Numéro de téléphone vérifié!",
        "step_1": "📝 Étape 1/6: Entrer le jeton du bot",
        "step_2": "📛 Étape 2/6: Entrer le nom du magasin",
        "step_3": "🔐 Étape 3/6: Entrer le mot de passe",
        "step_4": "📍 Étape 4/6: Partager l'emplacement du magasin",
        "step_5": "📸 Étape 5/6: Envoyer la photo du magasin",
        "step_6": "📝 Étape 6/6: Entrer la description du magasin",
        "registration_complete": "✅ Magasin enregistré avec succès!",
        "store_info": "🏪 Informations du magasin",
        "no_stores": "❌ Aucun magasin trouvé",
        "bank_selection": "🏛️ Choisir la banque:",
        "products": "🛍️ Produits",
        "cart": "🛒 Panier",
        "orders": "📦 Commandes",
        "location": "📍 Informations",
        "search_by_name": "📝 Rechercher par nom",
        "search_by_location": "📍 Rechercher par emplacement",
        "superadmin": "👑 Super Administrateur",
    },
    "or": {  # Oromo
        "welcome": "👋 Baga gara sirna bulchiinsa dukaanaa dhufte!",
        "choose_language": "🌐 Afaan filadhu:",
        "register": "📝 Dukaana haaraa galmeessuu",
        "my_stores": "🏪 Dukaanoo koo",
        "search": "🔍 Dukaanoo barbaaduu",
        "help": "❓ Gargaarsa",
        "back": "🔙 Duuba",
        "no_results": "🔍 Waan tokko hin argamne",
        "phone_required": "📱 Mee lakkoofsa bilbilaa keessan qoodaa:",
        "phone_verified": "✅ Lakkoofsi bilbilaa mirkanaa'e!",
        "step_1": "📝 Sadarkaa 1/6: Token bot galchi",
        "step_2": "📛 Sadarkaa 2/6: Maqaa dukaanaa galchi",
        "step_3": "🔐 Sadarkaa 3/6: Jecha iccitii galchi",
        "step_4": "📍 Sadarkaa 4/6: Iddoo dukaanaa qoodi",
        "step_5": "📸 Sadarkaa 5/6: Fota dukaanaa ergi",
        "step_6": "📝 Sadarkaa 6/6: Ibsa dukaanaa galchi",
        "registration_complete": "✅ Dukaanni galmeessame!",
        "store_info": "🏪 Odeeffannoo dukaanaa",
        "no_stores": "❌ Dukaanoon hin argamne",
        "bank_selection": "🏛️ Baankii filadhu:",
        "products": "🛍️ Oomishaalee",
        "cart": "🛒 Kartii",
        "orders": "📦 Ajajawwan",
        "location": "📍 Odeeffannoo",
        "search_by_name": "📝 Maqaan barbaaduu",
        "search_by_location": "📍 Iddoon barbaaduu",
        "superadmin": "👑 Bulchaa Ol'aanaa",
    },
    "ti": {  # Tigrinya
        "welcome": "👋 ናብ ስርዓተ አተዓውተራ መደብሪ ብደሓን መጹ!",
        "choose_language": "🌐 ቋንቋ ምረጹ:",
        "register": "📝 ሓደሽቲ መደብሪ ምዝገባ",
        "my_stores": "🏪 መደብርታተይ",
        "search": "🔍 መደብርታት ምድላይ",
        "help": "❓ ሓገዝ",
        "back": "🔙 ንድሕሪት",
        "no_results": "🔍 ውጽኢቲ ኣይተረኽበን",
        "phone_required": "📱 ቁጽሪ ተሌፎንኩም ኣካፍሉ:",
        "phone_verified": "✅ ቁጽሪ ተሌፎን ተረጋጊጹ!",
        "step_1": "📝 ደረጃ 1/6: ቶከን ቦት ኣእትዉ",
        "step_2": "📛 ደረጃ 2/6: ስም መደብሪ ኣእትዉ",
        "step_3": "🔐 ደረጃ 3/6: ቃል ምስጢር ኣእትዉ",
        "step_4": "📍 ደረጃ 4/6: ኣካባቢ መደብሪ ኣካፍሉ",
        "step_5": "📸 ደረጃ 5/6: ስእሊ መደብሪ ሰደዱ",
        "step_6": "📝 ደረጃ 6/6: መግለጺ መደብሪ ኣእትዉ",
        "registration_complete": "✅ መደብሪ ተዘጊቡ!",
        "store_info": "🏪 ሓበሬታ መደብሪ",
        "no_stores": "❌ መደብሪ ኣይተረኽበን",
        "bank_selection": "🏛️ ባንኪ ምረጹ:",
        "products": "🛍️ ምርትታት",
        "cart": "🛒 ቀርጢ",
        "orders": "📦 ትእዛዛት",
        "location": "📍 ሓበሬታ",
        "search_by_name": "📝 ብስም ምድላይ",
        "search_by_location": "📍 ብኣካባቢ ምድላይ",
        "superadmin": "👑 ልዑል ኣድሚን",
    },
    "so": {  # Somali
        "welcome": "👋 Ku soo dhawoow Nidaamka Maamulka Dukaanka!",
        "choose_language": "🌐 Dooro Luuqadda:",
        "register": "📝 Diiwaan geli Dukaan Cusub",
        "my_stores": "🏪 Dukaamadayda",
        "search": "🔍 Raadi Dukaano",
        "help": "❓ Caawimaad",
        "back": "🔙 Dib u noqo",
        "no_results": "🔍 Wax aan la helin",
        "phone_required": "📱 Fadlan la wadaag lambarkaaga taleefanka:",
        "phone_verified": "✅ Lambarka taleefanka waa la xaqiijiyay!",
        "step_1": "📝 Tallaabada 1/6: Geli Token-ka Bot-ka",
        "step_2": "📛 Tallaabada 2/6: Geli Magaca Dukaanka",
        "step_3": "🔐 Tallaabada 3/6: Geli Furaha Sirta ah",
        "step_4": "📍 Tallaabada 4/6: La wadaag Goobta Dukaanka",
        "step_5": "📸 Tallaabada 5/6: Soo dir Sawirka Dukaanka",
        "step_6": "📝 Tallaabada 6/6: Geli Sharaxaada Dukaanka",
        "registration_complete": "✅ Dukaanka waa la diiwaan geliyay!",
        "store_info": "🏪 Macluumaadka Dukaanka",
        "no_stores": "❌ Dukaan la helin",
        "bank_selection": "🏛️ Dooro Bangiga:",
        "products": "🛍️ Alaabooyinka",
        "cart": "🛒 Gaadhiga",
        "orders": "📦 Dalabada",
        "location": "📍 Macluumaad",
        "search_by_name": "📝 Magac u raadi",
        "search_by_location": "📍 Goob u raadi",
        "superadmin": "👑 Maamulaha Guud",
    },
    "aa": {  # Afar
        "welcome": "👋 Gaba-tuh dukana iisimah yafkune!",
        "choose_language": "🌐 Afa mannay:",
        "register": "📝 Dukana cusub kaytib",
        "my_stores": "🏪 Dukanakay",
        "search": "🔍 Dukanak gur",
        "help": "❓ Qokol",
        "back": "🔙 Fanan",
        "no_results": "🔍 Tu-ke way matoosen",
        "phone_required": "📱 Telo-kay gaccisa:",
        "phone_verified": "✅ Telo-ki kaskoote!",
        "step_1": "📝 Daraja 1/6: Bot Token culus",
        "step_2": "📛 Daraja 2/6: Dukana miga culus",
        "step_3": "🔐 Daraja 3/6: Quus culus",
        "step_4": "📍 Daraja 4/6: Dukana tanoh gaccisa",
        "step_5": "📸 Daraja 5/6: Dukana fota rub",
        "step_6": "📝 Daraja 6/6: Dukana ifa culus",
        "registration_complete": "✅ Dukana kaytibte!",
        "store_info": "🏪 Dukana ifa",
        "no_stores": "❌ Dukana matoosen",
        "bank_selection": "🏛️ Banki mannay:",
        "products": "🛍️ Alom",
        "cart": "🛒 Kartii",
        "orders": "📦 Amaan",
        "location": "📍 Ifa",
        "search_by_name": "📝 Migal gur",
        "search_by_location": "📍 Tanoh gur",
        "superadmin": "👑 Qax- admin",
    },
    "sid": {  # Sidama
        "welcome": "👋 Suuqta himmetiikko gara hojjete!",
        "choose_language": "🌐 Afaan doonni:",
        "register": "📝 Suuqta haara galchuu",
        "my_stores": "🏪 Suuqta koo",
        "search": "🔍 Suuqta barbaaduu",
        "help": "❓ Gargaarsa",
        "back": "🔙 Duubatti",
        "no_results": "🔍 Wanti tokko hin argamne",
        "phone_required": "📱 Lakkoofsa bilbilaa keessan qooda:",
        "phone_verified": "✅ Lakkoofsi bilbilaa mirkanaa'e!",
        "step_1": "📝 Sadarkaa 1/6: Token bot galchi",
        "step_2": "📛 Sadarkaa 2/6: Maqaa suuqtaa galchi",
        "step_3": "🔐 Sadarkaa 3/6: Jecha icciiti galchi",
        "step_4": "📍 Sadarkaa 4/6: Iddoo suuqtaa qoodi",
        "step_5": "📸 Sadarkaa 5/6: Fota suuqtaa ergi",
        "step_6": "📝 Sadarkaa 6/6: Ibsa suuqtaa galchi",
        "registration_complete": "✅ Suuqni galmeessame!",
        "store_info": "🏪 Odeeffannoo suuqtaa",
        "no_stores": "❌ Suuqni hin argamne",
        "bank_selection": "🏛️ Baankii filadhu:",
        "products": "🛍️ Oomishaalee",
        "cart": "🛒 Kartii",
        "orders": "📦 Ajajawwan",
        "location": "📍 Odeeffannoo",
        "search_by_name": "📝 Maqaan barbaaduu",
        "search_by_location": "📍 Iddoon barbaaduu",
        "superadmin": "👑 Bulchaa Ol'aanaa",
    },
}

# =================================================================================================
#                           UTILITY FUNCTIONS
# =================================================================================================

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def format_currency(amount: float) -> str:
    return f"{amount:,.2f} ETB"

def format_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")

def get_user_lang(chat_id: int) -> str:
    try:
        result = db_execute("SELECT lang FROM user_langs WHERE chat_id = %s", (chat_id,), fetch=True)
        if result:
            return result[0][0]
    except:
        pass
    return "am"

def set_user_lang(chat_id: int, lang: str):
    try:
        db_execute(
            "INSERT INTO user_langs (chat_id, lang) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang",
            (chat_id, lang)
        )
    except Exception as e:
        logger.error(f"Set user lang error: {e}")

def get_store_info(token: str) -> Optional[Dict]:
    try:
        result = db_execute_dict("""
            SELECT id, store_name, admin_id, username, phone, is_active, is_approved,
                   area_text, shop_description, shop_lat, shop_lng, shop_photo,
                   telebirr, cbebirr, bank_name, bank_account,
                   bot_status, total_orders, total_sales, created_at
            FROM stores WHERE token = %s
        """, (token,))
        if result:
            return dict(result[0])
        return None
    except Exception as e:
        logger.error(f"Get store info error: {e}")
        return None

def get_customer_info(chat_id: int) -> Optional[Dict]:
    try:
        result = db_execute_dict(
            "SELECT phone, lat, lng, address FROM customer_info WHERE chat_id = %s",
            (chat_id,)
        )
        if result:
            return dict(result[0])
        return None
    except Exception as e:
        logger.error(f"Get customer info error: {e}")
        return None

def save_customer_info(chat_id: int, phone: str = None, lat: float = None, lng: float = None):
    try:
        if phone:
            db_execute(
                "INSERT INTO customer_info (chat_id, phone) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET phone = EXCLUDED.phone",
                (chat_id, phone)
            )
        if lat is not None and lng is not None:
            db_execute(
                "INSERT INTO customer_info (chat_id, lat, lng) VALUES (%s, %s, %s) ON CONFLICT (chat_id) DO UPDATE SET lat = EXCLUDED.lat, lng = EXCLUDED.lng",
                (chat_id, lat, lng)
            )
    except Exception as e:
        logger.error(f"Save customer info error: {e}")

def update_bot_status(token: str, status: str):
    try:
        db_execute(
            "UPDATE stores SET bot_status = %s, updated_at = CURRENT_TIMESTAMP WHERE token = %s",
            (status, token)
        )
    except Exception as e:
        logger.error(f"Update bot status error: {e}")

def get_all_stores() -> List[Dict]:
    try:
        return db_execute_dict("""
            SELECT id, store_name, username, phone, area_text, shop_photo, shop_description,
                   rating, total_orders, total_sales, is_active, is_approved
            FROM stores WHERE is_approved = 1 AND is_active = 1
            ORDER BY rating DESC
        """)
    except Exception as e:
        logger.error(f"Get all stores error: {e}")
        return []

def search_stores_by_name(query: str) -> List[Dict]:
    try:
        return db_execute_dict("""
            SELECT id, store_name, username, phone, area_text, shop_photo, shop_description,
                   rating, total_orders, total_sales
            FROM stores 
            WHERE (store_name ILIKE %s OR username ILIKE %s) 
            AND is_approved = 1 AND is_active = 1
            ORDER BY rating DESC
            LIMIT 20
        """, (f"%{query}%", f"%{query}%"))
    except Exception as e:
        logger.error(f"Search stores by name error: {e}")
        return []

def search_stores_by_location(lat: float, lng: float, radius: float = 10) -> List[Dict]:
    try:
        return db_execute_dict("""
            SELECT id, store_name, username, phone, area_text, shop_photo, shop_description,
                   rating, total_orders, total_sales,
                   (6371 * acos(cos(radians(%s)) * cos(radians(shop_lat)) *
                    cos(radians(shop_lng) - radians(%s)) + sin(radians(%s)) *
                    sin(radians(shop_lat)))) as distance
            FROM stores
            WHERE shop_lat IS NOT NULL AND shop_lng IS NOT NULL
            AND is_approved = 1 AND is_active = 1
            HAVING distance < %s
            ORDER BY distance
            LIMIT 20
        """, (lat, lng, lat, radius))
    except Exception as e:
        logger.error(f"Search stores by location error: {e}")
        return []

def get_ethiopian_banks() -> List[Dict]:
    try:
        return db_execute_dict("SELECT id, name_am, name_en, code FROM ethiopian_banks WHERE is_active = 1")
    except Exception as e:
        logger.error(f"Get Ethiopian banks error: {e}")
        return []

# =================================================================================================
#                           FLASK WEB SERVER
# =================================================================================================

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
CORS(app)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Control Bot - 12 Languages</title></head>
    <body>
        <h1>🚀 Control Bot is Running!</h1>
        <p>Status: Online</p>
        <p>🌐 12 Languages Supported</p>
    </body>
    </html>
    """

@app.route('/api/stats')
def api_stats():
    try:
        total = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
        pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
        active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
        return jsonify({"total_stores": total, "pending_approval": pending, "active_stores": active})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_flask():
    app.run(host=Config.HOST, port=Config.PORT, debug=False)

threading.Thread(target=run_flask, daemon=True).start()
logger.info(f"✅ Web server running on {Config.HOST}:{Config.PORT}")

# =================================================================================================
#                           BOT MANAGER
# =================================================================================================

running_tokens = set()
running_lock = threading.Lock()

class BotManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self._running = True
        logger.info("✅ Bot Manager initialized")
    
    def start_bot(self, token: str) -> bool:
        with running_lock:
            if token in running_tokens:
                return True
        
        try:
            store = get_store_info(token)
            if not store or store.get('is_approved', 0) != 1 or store.get('is_active', 1) != 1:
                return False
            
            thread = threading.Thread(target=self._run_bot, args=(token,), daemon=True)
            thread.start()
            
            running_tokens.add(token)
            update_bot_status(token, 'running')
            logger.info(f"✅ Bot started: {token[:15]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to start bot {token[:15]}: {e}")
            return False
    
    def _run_bot(self, token: str):
        try:
            setup_bot_handlers(token)
        except Exception as e:
            logger.error(f"Bot {token[:15]} crashed: {e}")
            running_tokens.discard(token)
            update_bot_status(token, 'stopped')
    
    def stop_bot(self, token: str) -> bool:
        with running_lock:
            if token not in running_tokens:
                return True
            running_tokens.discard(token)
            update_bot_status(token, 'stopped')
            return True
    
    def shutdown(self):
        self._running = False

bot_manager = BotManager()

# =================================================================================================
#                           SHOP BOT ENGINE - 12 Languages
# =================================================================================================

def setup_bot_handlers(token: str):
    """የሱቅ ቦት ሃንድለሮች ማዘጋጀት - 12 Languages"""
    
    bot = telebot.TeleBot(token, threaded=False)
    
    try:
        bot.remove_webhook()
    except Exception as e:
        logger.warning(f"Webhook removal failed: {e}")
    
    # ============================================================
    # COMMAND: /start
    # ============================================================
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        chat_id = message.chat.id
        logger.info(f"✅ /start received from {chat_id} for bot {token[:15]}")
        
        store = get_store_info(token)
        
        if not store:
            bot.send_message(
                chat_id,
                "🏪 ይህ ቦት ገና አልተመዘገበም።\n\n"
                "📌 እባክዎ በ Control Bot ይመዝገቡ!",
                parse_mode="Markdown"
            )
            return
        
        if store.get('is_approved', 0) != 1:
            bot.send_message(
                chat_id,
                f"⏳ ሱቅ **{store.get('store_name', '')}** ገና አልጸደቀም።\n\n"
                f"እባክዎ ለማጽደቅ ይጠብቁ።",
                parse_mode="Markdown"
            )
            return
        
        if not store.get('is_active', 1):
            bot.send_message(
                chat_id,
                "❌ ይህ ሱቅ ንቁ አይደለም።\n\n"
                "እባክዎ አድሚኑን ያነጋግሩ።"
            )
            return
        
        # Language selection for shop
        markup = types.InlineKeyboardMarkup(row_width=3)
        lang_codes = ["am", "en", "zh", "hi", "es", "ar", "fr", "or", "ti", "so", "aa", "sid"]
        for i in range(0, len(lang_codes), 3):
            row = []
            for code in lang_codes[i:i+3]:
                lang_info = LANGUAGES[code]
                row.append(types.InlineKeyboardButton(
                    f"{lang_info['flag']} {lang_info['name']}",
                    callback_data=f"shoplang_{code}_{token}"
                ))
            markup.row(*row)
        
        bot.send_message(
            chat_id,
            f"🌐 **{store.get('store_name', '')}**\n\n"
            "ቋንቋ ይምረጡ / Select Language:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    # ============================================================
    # CALLBACK: Shop Language Selection
    # ============================================================
    @bot.callback_query_handler(func=lambda call: call.data.startswith("shoplang_"))
    def shop_set_language(call):
        _, lang, bot_token = call.data.split("_")
        if bot_token != token:
            return
        
        chat_id = call.message.chat.id
        set_user_lang(chat_id, lang)
        
        try:
            bot.delete_message(chat_id, call.message.message_id)
        except:
            pass
        
        strings = STRINGS.get(lang, STRINGS["am"])
        store = get_store_info(token)
        
        if not store:
            return
        
        # Main menu
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton(strings["products"]),
            types.KeyboardButton(strings["cart"])
        )
        markup.add(
            types.KeyboardButton(strings["search"]),
            types.KeyboardButton(strings["orders"])
        )
        markup.add(
            types.KeyboardButton(strings["location"]),
            types.KeyboardButton(strings["help"])
        )
        
        text = f"🏪 **{store.get('store_name', '')}**\n\n"
        if store.get('shop_description'):
            text += f"📝 {store['shop_description']}\n\n"
        if store.get('area_text'):
            text += f"📍 {store['area_text']}\n"
        if store.get('username'):
            text += f"👤 @{store['username']}\n"
        text += f"⭐ {store.get('rating', 0)}/5.0\n\n"
        text += strings["welcome"]
        
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
    
    # ============================================================
    # TEXT HANDLERS - Using strings
    # ============================================================
    @bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["products"] for lang in STRINGS.keys()])
    def handle_products(message):
        lang = get_user_lang(message.chat.id)
        strings = STRINGS.get(lang, STRINGS["am"])
        bot.send_message(
            message.chat.id,
            f"🛍️ {strings['products']} በቅርቡ ይገኛሉ\n\n📌 እባክዎ በየጊዜው ይጎብኙ!",
            parse_mode="Markdown"
        )
    
    @bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["cart"] for lang in STRINGS.keys()])
    def handle_cart(message):
        lang = get_user_lang(message.chat.id)
        strings = STRINGS.get(lang, STRINGS["am"])
        bot.send_message(
            message.chat.id,
            f"🛒 {strings['cart']} ባዶ ነው\n\n🛍️ ምርቶችን ይመልከቱ እና ይጨምሩ!",
            parse_mode="Markdown"
        )
    
    @bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["search"] for lang in STRINGS.keys()])
    def handle_search(message):
        lang = get_user_lang(message.chat.id)
        strings = STRINGS.get(lang, STRINGS["am"])
        bot.send_message(
            message.chat.id,
            f"🔍 {strings['search']} በቅርቡ ይገኛል\n\n📌 እባክዎ በየጊዜው ይጎብኙ!",
            parse_mode="Markdown"
        )
    
    @bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["orders"] for lang in STRINGS.keys()])
    def handle_orders(message):
        lang = get_user_lang(message.chat.id)
        strings = STRINGS.get(lang, STRINGS["am"])
        bot.send_message(
            message.chat.id,
            f"📦 {strings['orders']} በቅርቡ ይገኛሉ\n\n📌 እባክዎ በየጊዜው ይጎብኙ!",
            parse_mode="Markdown"
        )
    
    @bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["location"] for lang in STRINGS.keys()])
    def handle_location(message):
        lang = get_user_lang(message.chat.id)
        strings = STRINGS.get(lang, STRINGS["am"])
        store = get_store_info(token)
        if not store:
            return
        
        text = f"🏪 **{store.get('store_name', '')}**\n\n"
        if store.get('shop_description'):
            text += f"📝 {store['shop_description']}\n\n"
        if store.get('area_text'):
            text += f"📍 {store['area_text']}\n"
        if store.get('username'):
            text += f"👤 @{store['username']}\n"
        if store.get('shop_photo'):
            text += "📸 ፎቶ: ✅\n"
        text += f"⭐ {store.get('rating', 0)}/5.0\n"
        if store.get('total_orders'):
            text += f"📦 {store.get('total_orders')} ትዕዛዞች"
        
        if store.get('shop_photo'):
            try:
                bot.send_photo(message.chat.id, store['shop_photo'], caption=text, parse_mode="Markdown")
            except:
                bot.send_message(message.chat.id, text, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, text, parse_mode="Markdown")
    
    @bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["help"] for lang in STRINGS.keys()])
    def handle_help(message):
        lang = get_user_lang(message.chat.id)
        strings = STRINGS.get(lang, STRINGS["am"])
        
        text = f"""
❓ **{strings['help']}**

🛍️ {strings['products']} - የሱቁን ምርቶች ይመልከቱ
🛒 {strings['cart']} - የእርስዎን ጋሪ ይመልከቱ
🔍 {strings['search']} - ምርቶችን ይፈልጉ
📦 {strings['orders']} - ትዕዛዝዎን ይከታተሉ
📍 {strings['location']} - ስለ ሱቁ መረጃ

📞 ለተጨማሪ እርዳታ አስተዳዳሪውን ያነጋግሩ
"""
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    
    @bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["back"] for lang in STRINGS.keys()])
    def handle_back(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        strings = STRINGS.get(lang, STRINGS["am"])
        store = get_store_info(token)
        
        if not store:
            return
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton(strings["products"]),
            types.KeyboardButton(strings["cart"])
        )
        markup.add(
            types.KeyboardButton(strings["search"]),
            types.KeyboardButton(strings["orders"])
        )
        markup.add(
            types.KeyboardButton(strings["location"]),
            types.KeyboardButton(strings["help"])
        )
        
        bot.send_message(chat_id, strings["back"], reply_markup=markup)
    
    # ============================================================
    # CATCH ALL
    # ============================================================
    @bot.message_handler(func=lambda m: True)
    def handle_all(message):
        lang = get_user_lang(message.chat.id)
        strings = STRINGS.get(lang, STRINGS["am"])
        bot.send_message(
            message.chat.id,
            f"🤖 እንዴት ልረዳዎት እችላለሁ?\n\n"
            f"📌 {strings['help']} ይላኩ ወይም ከላይ ካሉት ቁልፎች ይምረጡ",
            parse_mode="Markdown"
        )
    
    # ============================================================
    # POLLING
    # ============================================================
    def _run_polling():
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                logger.error(f"Bot {token[:15]} polling error: {e}")
                time.sleep(5)
    
    threading.Thread(target=_run_polling, daemon=True).start()

# =================================================================================================
#                           CONTROL BOT - 12 Languages
# =================================================================================================

class ControlBot:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
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
        logger.info("✅ Control Bot initialized - 12 Languages")
    
    def _register_handlers(self):
        
        # ============================================================
        # COMMAND: /start - 12 Languages
        # ============================================================
        @self.bot.message_handler(commands=['start'])
        def cmd_start(message):
            chat_id = message.chat.id
            logger.info(f"✅ Control /start received from {chat_id}")
            
            markup = types.InlineKeyboardMarkup(row_width=3)
            lang_codes = ["am", "en", "zh", "hi", "es", "ar", "fr", "or", "ti", "so", "aa", "sid"]
            for i in range(0, len(lang_codes), 3):
                row = []
                for code in lang_codes[i:i+3]:
                    lang_info = LANGUAGES[code]
                    row.append(types.InlineKeyboardButton(
                        f"{lang_info['flag']} {lang_info['name']}",
                        callback_data=f"setlang_{code}"
                    ))
                markup.row(*row)
            
            self.bot.send_message(
                chat_id,
                "🌐 **ቋንቋ ይምረጡ / Select Language:**",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            logger.info(f"✅ Language menu sent to {chat_id}")
        
        # ============================================================
        # CALLBACK: Set Language
        # ============================================================
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("setlang_"))
        def set_language(call):
            chat_id = call.message.chat.id
            lang = call.data.split("_")[1]
            logger.info(f"✅ Language selected: {lang} by {chat_id}")
            
            set_user_lang(chat_id, lang)
            
            try:
                self.bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            
            strings = STRINGS.get(lang, STRINGS["am"])
            
            # Check phone verification
            customer = get_customer_info(chat_id)
            if not customer or not customer.get('phone'):
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton("📱 Share Phone", request_contact=True))
                self.bot.send_message(
                    chat_id,
                    strings["phone_required"],
                    reply_markup=markup
                )
                self.bot.answer_callback_query(call.id)
                return
            
            # Main menu
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add(
                types.KeyboardButton(strings["register"]),
                types.KeyboardButton(strings["my_stores"])
            )
            markup.add(
                types.KeyboardButton(strings["search"]),
                types.KeyboardButton(strings["help"])
            )
            
            self.bot.send_message(
                chat_id,
                strings["welcome"],
                reply_markup=markup
            )
            self.bot.answer_callback_query(call.id)
            logger.info(f"✅ Main menu sent to {chat_id}")
        
        # ============================================================
        # CONTACT HANDLER
        # ============================================================
        @self.bot.message_handler(content_types=['contact'])
        def handle_contact(message):
            chat_id = message.chat.id
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            if message.contact and message.contact.user_id == message.from_user.id:
                phone = message.contact.phone_number
                save_customer_info(chat_id, phone=phone)
                
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                markup.add(
                    types.KeyboardButton(strings["register"]),
                    types.KeyboardButton(strings["my_stores"])
                )
                markup.add(
                    types.KeyboardButton(strings["search"]),
                    types.KeyboardButton(strings["help"])
                )
                
                self.bot.send_message(
                    chat_id,
                    strings["phone_verified"],
                    reply_markup=markup
                )
            else:
                self.bot.send_message(chat_id, strings["phone_required"])
        
        # ============================================================
        # TEXT HANDLERS - Using strings
        # ============================================================
        @self.bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["register"] for lang in STRINGS.keys()])
        def handle_register(message):
            chat_id = message.chat.id
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            logger.info(f"✅ Registration started by {chat_id} in {lang}")
            
            customer = get_customer_info(chat_id)
            if not customer or not customer.get('phone'):
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton("📱 Share Phone", request_contact=True))
                self.bot.send_message(
                    chat_id,
                    strings["phone_required"],
                    reply_markup=markup
                )
                return
            
            self._start_registration(message)
        
        @self.bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["my_stores"] for lang in STRINGS.keys()])
        def handle_my_stores(message):
            self._show_my_stores(message)
        
        @self.bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["search"] for lang in STRINGS.keys()])
        def handle_search(message):
            chat_id = message.chat.id
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton(strings["search_by_name"], callback_data="search_name"),
                types.InlineKeyboardButton(strings["search_by_location"], callback_data="search_location")
            )
            markup.add(types.InlineKeyboardButton(strings["back"], callback_data="back_to_main"))
            
            self.bot.send_message(
                chat_id,
                strings["search"],
                reply_markup=markup
            )
        
        @self.bot.message_handler(func=lambda m: m.text in [STRINGS[get_user_lang(m.chat.id)]["help"] for lang in STRINGS.keys()])
        def handle_help(message):
            lang = get_user_lang(message.chat.id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            text = f"""
❓ **{strings['help']}**

📝 {strings['register']} - አዲስ ሱቅ ይመዝገቡ
🏪 {strings['my_stores']} - የሱቆችዎን ዝርዝር ይመልከቱ
🔍 {strings['search']} - ሱቆችን ይፈልጉ

🌐 **12 ቋንቋዎች / Languages:**
- አማርኛ, English, 中文, हिन्दी, Español
- العربية, Français, ኦሮምኛ, ትግርኛ
- Soomaali, Qafar, ሲዳምኛ

👑 **Super Admin:** `/superadmin`
"""
            self.bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
        # ============================================================
        # SEARCH CALLBACKS
        # ============================================================
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("search_"))
        def handle_search_callbacks(call):
            chat_id = call.message.chat.id
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            if call.data == "search_name":
                msg = self.bot.send_message(chat_id, f"📝 {strings['search_by_name']}:")
                self.bot.register_next_step_handler(msg, self._search_by_name)
            
            elif call.data == "search_location":
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton("📍 Share Location", request_location=True))
                self.bot.send_message(chat_id, f"📍 {strings['search_by_location']}:", reply_markup=markup)
            
            self.bot.answer_callback_query(call.id)
        
        @self.bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
        def back_to_main(call):
            chat_id = call.message.chat.id
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            try:
                self.bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add(
                types.KeyboardButton(strings["register"]),
                types.KeyboardButton(strings["my_stores"])
            )
            markup.add(
                types.KeyboardButton(strings["search"]),
                types.KeyboardButton(strings["help"])
            )
            
            self.bot.send_message(chat_id, strings["welcome"], reply_markup=markup)
            self.bot.answer_callback_query(call.id)
        
        # ============================================================
        # LOCATION HANDLER
        # ============================================================
        @self.bot.message_handler(content_types=['location'])
        def handle_location_search(message):
            chat_id = message.chat.id
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            if not message.location:
                self.bot.send_message(chat_id, strings["no_results"])
                return
            
            lat = message.location.latitude
            lng = message.location.longitude
            
            stores = search_stores_by_location(lat, lng)
            
            if not stores:
                self.bot.send_message(chat_id, strings["no_results"])
                return
            
            self._display_stores(chat_id, stores, lang)
        
        # ============================================================
        # SEARCH IMPLEMENTATIONS
        # ============================================================
        def _search_by_name(self, message):
            chat_id = message.chat.id
            query = message.text.strip()
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            if not query:
                self.bot.send_message(chat_id, strings["no_results"])
                return
            
            stores = search_stores_by_name(query)
            
            if not stores:
                self.bot.send_message(chat_id, f"{strings['no_results']}: '{query}'")
                return
            
            self._display_stores(chat_id, stores, lang)
        
        def _display_stores(self, chat_id, stores, lang):
            strings = STRINGS.get(lang, STRINGS["am"])
            
            for store in stores[:10]:
                text = f"🏪 **{store.get('store_name', 'N/A')}**\n"
                text += f"👤 @{store.get('username', 'N/A')}\n"
                if store.get('area_text'):
                    text += f"📍 {store.get('area_text')}\n"
                if store.get('rating'):
                    text += f"⭐ {store.get('rating', 0)}/5.0\n"
                if store.get('total_orders'):
                    text += f"📦 {store.get('total_orders')} {strings['orders']}\n"
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("📋 ዝርዝር", callback_data=f"viewstore_{store['id']}"),
                    types.InlineKeyboardButton(strings["back"], callback_data="back_to_main")
                )
                
                if store.get('shop_photo'):
                    try:
                        self.bot.send_photo(chat_id, store['shop_photo'], caption=text, reply_markup=markup, parse_mode="Markdown")
                    except:
                        self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
                else:
                    self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        
        # ============================================================
        # VIEW STORE DETAILS
        # ============================================================
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("viewstore_"))
        def view_store(call):
            chat_id = call.message.chat.id
            store_id = int(call.data.split("_")[1])
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            try:
                store = db_execute_dict("SELECT * FROM stores WHERE id = %s", (store_id,))
                if not store:
                    self.bot.answer_callback_query(call.id, strings["no_results"])
                    return
                
                store = store[0]
                
                text = f"🏪 **{store['store_name']}**\n\n"
                text += f"👤 @{store['username']}\n"
                if store.get('phone'):
                    text += f"📱 {store['phone']}\n"
                if store.get('area_text'):
                    text += f"📍 {store['area_text']}\n"
                if store.get('shop_description'):
                    text += f"📝 {store['shop_description']}\n"
                text += f"⭐ {store.get('rating', 0)}/5.0\n"
                text += f"📦 {store.get('total_orders', 0)} {strings['orders']}\n"
                text += f"💰 {format_currency(store.get('total_sales', 0))}\n"
                text += f"📅 {format_date(store['created_at'])}"
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(strings["back"], callback_data="back_to_main"))
                
                if store.get('shop_photo'):
                    try:
                        self.bot.send_photo(chat_id, store['shop_photo'], caption=text, reply_markup=markup, parse_mode="Markdown")
                    except:
                        self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
                else:
                    self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
                
                self.bot.answer_callback_query(call.id)
            except Exception as e:
                logger.error(f"View store error: {e}")
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
        
        # ============================================================
        # STORE REGISTRATION - 12 Languages
        # ============================================================
        def _start_registration(self, message):
            chat_id = message.chat.id
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            self._clear_reg_state(chat_id)
            self._set_reg_state(chat_id, "step", 1)
            self._set_reg_state(chat_id, "data", {})
            
            msg = self.bot.send_message(
                chat_id,
                strings["step_1"],
                parse_mode="Markdown"
            )
            self.bot.register_next_step_handler(msg, self._process_reg_token)
        
        def _process_reg_token(self, message):
            chat_id = message.chat.id
            token = message.text.strip()
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            try:
                test_bot = telebot.TeleBot(token)
                bot_info = test_bot.get_me()
            except Exception as e:
                self.bot.reply_to(message, "❌ Invalid token! Please try again.")
                return
            
            data = self._get_reg_state(chat_id, "data") or {}
            data["token"] = token
            data["bot_username"] = bot_info.username
            self._set_reg_state(chat_id, "data", data)
            self._set_reg_state(chat_id, "step", 2)
            
            msg = self.bot.send_message(
                chat_id,
                f"✅ Token verified! 👤 @{bot_info.username}\n\n{strings['step_2']}",
                parse_mode="Markdown"
            )
            self.bot.register_next_step_handler(msg, self._process_reg_name)
        
        def _process_reg_name(self, message):
            chat_id = message.chat.id
            name = message.text.strip()
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            if not name or len(name) < 3:
                self.bot.reply_to(message, "❌ Store name must be at least 3 characters!")
                return
            
            data = self._get_reg_state(chat_id, "data") or {}
            data["store_name"] = name
            self._set_reg_state(chat_id, "data", data)
            self._set_reg_state(chat_id, "step", 3)
            
            msg = self.bot.send_message(
                chat_id,
                f"✅ Store name: **{name}**\n\n{strings['step_3']}",
                parse_mode="Markdown"
            )
            self.bot.register_next_step_handler(msg, self._process_reg_password)
        
        def _process_reg_password(self, message):
            chat_id = message.chat.id
            password = message.text.strip()
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            if len(password) < 8:
                self.bot.reply_to(message, "❌ Password must be at least 8 characters!")
                return
            
            data = self._get_reg_state(chat_id, "data") or {}
            data["password"] = password
            self._set_reg_state(chat_id, "data", data)
            self._set_reg_state(chat_id, "step", 4)
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.add(types.KeyboardButton("📍 Share Location", request_location=True))
            
            msg = self.bot.send_message(
                chat_id,
                f"✅ Password received\n\n{strings['step_4']}",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            self.bot.register_next_step_handler(msg, self._process_reg_location)
        
        def _process_reg_location(self, message):
            chat_id = message.chat.id
            data = self._get_reg_state(chat_id, "data") or {}
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            if message.location:
                data["shop_lat"] = message.location.latitude
                data["shop_lng"] = message.location.longitude
                location_text = f"📍 {data['shop_lat']}, {data['shop_lng']}"
            else:
                location_text = message.text.strip()
                if not location_text:
                    self.bot.reply_to(message, "❌ Please enter a location!")
                    return
                data["area_text"] = location_text
            
            self._set_reg_state(chat_id, "data", data)
            self._set_reg_state(chat_id, "step", 5)
            
            msg = self.bot.send_message(
                chat_id,
                f"✅ Location: {location_text}\n\n{strings['step_5']}",
                parse_mode="Markdown"
            )
            self.bot.register_next_step_handler(msg, self._process_reg_photo)
        
        def _process_reg_photo(self, message):
            chat_id = message.chat.id
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            if message.photo:
                photo_id = message.photo[-1].file_id
                data = self._get_reg_state(chat_id, "data") or {}
                data["shop_photo"] = photo_id
                self._set_reg_state(chat_id, "data", data)
                self._set_reg_state(chat_id, "step", 6)
                
                msg = self.bot.send_message(
                    chat_id,
                    f"✅ Photo received!\n\n{strings['step_6']}",
                    parse_mode="Markdown"
                )
                self.bot.register_next_step_handler(msg, self._process_reg_description)
            elif message.text and message.text.lower() in ['skip', 'ስቀር', 'none']:
                self._set_reg_state(chat_id, "step", 6)
                msg = self.bot.send_message(
                    chat_id,
                    f"⏭️ Photo skipped\n\n{strings['step_6']}",
                    parse_mode="Markdown"
                )
                self.bot.register_next_step_handler(msg, self._process_reg_description)
            else:
                self.bot.reply_to(message, "📸 Please send a photo or type 'skip'")
        
        def _process_reg_description(self, message):
            chat_id = message.chat.id
            description = message.text.strip()
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            if not description:
                self.bot.reply_to(message, "❌ Please enter a description!")
                return
            
            data = self._get_reg_state(chat_id, "data") or {}
            data["shop_description"] = description
            data["username"] = data.get("bot_username", f"shop_{chat_id}")
            
            customer = get_customer_info(chat_id)
            data["phone"] = customer.get('phone', '') if customer else ''
            
            try:
                existing = db_execute_dict("SELECT 1 FROM stores WHERE token = %s", (data["token"],))
                if existing:
                    self.bot.reply_to(message, "❌ This token is already registered!")
                    return
                
                h_pass, salt = hash_password(data["password"])
                
                db_execute("""
                    INSERT INTO stores (
                        token, store_name, admin_id, username, phone,
                        password_hash, password_salt,
                        is_active, is_approved, shop_lat, shop_lng,
                        area_text, shop_photo, shop_description
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data["token"], data["store_name"], chat_id, data["username"], data["phone"],
                    h_pass, salt, 1, 0,
                    data.get("shop_lat"), data.get("shop_lng"),
                    data.get("area_text", ""), data.get("shop_photo", ""),
                    data.get("shop_description", "")
                ))
                
                bot_manager.start_bot(data["token"])
                self._clear_reg_state(chat_id)
                
                self._show_bank_selection(chat_id, data, lang)
                
            except Exception as e:
                logger.error(f"Registration error: {e}")
                self.bot.reply_to(message, f"❌ Error: {str(e)}")
        
        def _show_bank_selection(self, chat_id, data, lang):
            strings = STRINGS.get(lang, STRINGS["am"])
            banks = get_ethiopian_banks()
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            for bank in banks:
                markup.add(types.InlineKeyboardButton(
                    bank['name_am'],
                    callback_data=f"selectbank_{bank['id']}_{data['token']}"
                ))
            markup.add(types.InlineKeyboardButton("⏭️ ስቀር", callback_data=f"skipbank_{data['token']}"))
            
            self.bot.send_message(
                chat_id,
                f"✅ **{strings['registration_complete']}**\n\n"
                f"🏪 Name: {data['store_name']}\n"
                f"👤 Username: @{data['username']}\n"
                f"📱 Phone: {data['phone']}\n"
                f"🔑 Password: `{data['password']}`\n\n"
                f"⏳ {lang == 'am' and 'ሱቅዎ ለማጽደቅ በመጠባበቅ ላይ ነው' or 'Your store is pending approval'}.\n\n"
                f"{strings['bank_selection']}",
                reply_markup=markup,
                parse_mode="Markdown"
            )
        
        # ============================================================
        # BANK SELECTION CALLBACKS
        # ============================================================
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("selectbank_"))
        def select_bank(call):
            chat_id = call.message.chat.id
            _, bank_id, token = call.data.split("_")
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            try:
                self.bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            
            msg = self.bot.send_message(
                chat_id,
                f"🔢 {strings.get('enter_bank_account', 'Enter bank account number:')}"
            )
            self.bot.register_next_step_handler(msg, lambda m: self._process_bank_account(m, bank_id, token))
            self.bot.answer_callback_query(call.id)
        
        def _process_bank_account(self, message, bank_id, token):
            chat_id = message.chat.id
            account = message.text.strip()
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            try:
                bank = db_execute_dict("SELECT name_am FROM ethiopian_banks WHERE id = %s", (bank_id,))
                bank_name = bank[0]['name_am'] if bank else ""
                
                db_execute(
                    "UPDATE stores SET bank_name = %s, bank_account = %s WHERE token = %s",
                    (bank_name, account, token)
                )
                
                self.bot.reply_to(
                    message,
                    f"✅ {strings.get('bank_selection', 'Bank selected')}!\n\n"
                    f"🏛️ {bank_name}\n"
                    f"🔢 {account}\n\n"
                    f"📌 {lang == 'am' and 'ሱቅዎ ለማጽደቅ በመጠባበቅ ላይ ነው' or 'Your store is pending approval'}!"
                )
            except Exception as e:
                logger.error(f"Bank account error: {e}")
                self.bot.reply_to(message, f"❌ Error: {str(e)}")
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("skipbank_"))
        def skip_bank(call):
            chat_id = call.message.chat.id
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            try:
                self.bot.delete_message(chat_id, call.message.message_id)
            except:
                pass
            
            self.bot.send_message(
                chat_id,
                f"✅ {lang == 'am' and 'ባንክ መረጃ አልተመዘገበም' or 'Bank info skipped'}\n\n"
                f"📌 {lang == 'am' and 'ሱቅዎ ለማጽደቅ በመጠባበቅ ላይ ነው' or 'Your store is pending approval'}!"
            )
            self.bot.answer_callback_query(call.id)
        
        # ============================================================
        # MY STORES
        # ============================================================
        def _show_my_stores(self, message):
            chat_id = message.chat.id
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            stores = db_execute_dict("""
                SELECT id, store_name, username, is_active, is_approved,
                       area_text, shop_photo, shop_description,
                       rating, total_orders, total_sales
                FROM stores WHERE admin_id = %s
                ORDER BY created_at DESC
            """, (chat_id,))
            
            if not stores:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
                markup.add(
                    types.KeyboardButton(strings["register"]),
                    types.KeyboardButton(strings["search"])
                )
                self.bot.reply_to(
                    message,
                    strings["no_stores"],
                    reply_markup=markup
                )
                return
            
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                approved = "✅" if store['is_approved'] else "⏳"
                
                text = f"{status} {approved} **{store['store_name']}**\n"
                text += f"👤 @{store['username']}\n"
                if store.get('area_text'):
                    text += f"📍 {store['area_text']}\n"
                if store.get('rating'):
                    text += f"⭐ {store['rating']}/5.0\n"
                text += f"📦 {store.get('total_orders', 0)} ትዕዛዞች\n"
                text += f"💰 {format_currency(store.get('total_sales', 0))}"
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("📋 ዝርዝር", callback_data=f"mystore_{store['id']}"),
                    types.InlineKeyboardButton(strings["back"], callback_data="back_to_main")
                )
                
                if store.get('shop_photo'):
                    try:
                        self.bot.send_photo(chat_id, store['shop_photo'], caption=text, reply_markup=markup, parse_mode="Markdown")
                    except:
                        self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
                else:
                    self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("mystore_"))
        def view_my_store(call):
            chat_id = call.message.chat.id
            store_id = int(call.data.split("_")[1])
            lang = get_user_lang(chat_id)
            strings = STRINGS.get(lang, STRINGS["am"])
            
            try:
                store = db_execute_dict("SELECT * FROM stores WHERE id = %s", (store_id,))
                if not store:
                    self.bot.answer_callback_query(call.id, strings["no_results"])
                    return
                
                store = store[0]
                
                text = f"🏪 **{store['store_name']}**\n\n"
                text += f"👤 @{store['username']}\n"
                if store.get('phone'):
                    text += f"📱 {store['phone']}\n"
                if store.get('area_text'):
                    text += f"📍 {store['area_text']}\n"
                if store.get('shop_description'):
                    text += f"📝 {store['shop_description']}\n"
                text += f"⭐ {store.get('rating', 0)}/5.0\n"
                text += f"📦 {store.get('total_orders', 0)} ትዕዛዞች\n"
                text += f"💰 {format_currency(store.get('total_sales', 0))}\n"
                text += f"📅 {format_date(store['created_at'])}\n\n"
                
                if store.get('bank_name'):
                    text += f"🏛️ {store['bank_name']}\n"
                if store.get('bank_account'):
                    text += f"🔢 {store['bank_account']}\n"
                
                status_text = "🟢 ንቁ" if store['is_active'] else "🔴 የተገደለ"
                approved_text = "✅ ጸድቋል" if store['is_approved'] else "⏳ በመጠባበቅ ላይ"
                text += f"\n📌 {status_text} | {approved_text}"
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(strings["back"], callback_data="back_to_main"))
                
                if store.get('shop_photo'):
                    try:
                        self.bot.send_photo(chat_id, store['shop_photo'], caption=text, reply_markup=markup, parse_mode="Markdown")
                    except:
                        self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
                else:
                    self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
                
                self.bot.answer_callback_query(call.id)
            except Exception as e:
                logger.error(f"View my store error: {e}")
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
        
        # ============================================================
        # SUPER ADMIN
        # ============================================================
        @self.bot.message_handler(commands=['superadmin'])
        def cmd_superadmin(message):
            chat_id = message.chat.id
            
            if not Config.SUPER_ADMIN_PASSWORD:
                self.bot.reply_to(message, "❌ SUPER_ADMIN_PASSWORD not set!")
                return
            
            if Config.SUPER_ADMIN_ID != 0 and chat_id != Config.SUPER_ADMIN_ID:
                self.bot.reply_to(message, "❌ መብት የለዎትም!")
                return
            
            msg = self.bot.send_message(
                chat_id,
                "🔐 **የ Super Admin የይለፍ ቃል ያስገቡ:**",
                parse_mode="Markdown"
            )
            self.bot.register_next_step_handler(msg, self._process_super_login)
        
        def _process_super_login(self, message):
            chat_id = message.chat.id
            password = message.text.strip()
            
            if password == Config.SUPER_ADMIN_PASSWORD:
                with self.sessions_lock:
                    self.sessions[chat_id] = time.time() + Config.SESSION_TIMEOUT
                self.bot.send_message(
                    chat_id,
                    "🔓 **እንኳን ወደ Super Admin ፓነል በደህና መጡ!**\n\n"
                    "🌐 12 Languages Supported",
                    parse_mode="Markdown"
                )
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
                        self.bot.send_message(
                            chat_id,
                            f"❌ የተሳሳተ የይለፍ ቃል! {left} ሙከራዎች ቀርተውዎታል።"
                        )
        
        def _show_dashboard(self, message):
            chat_id = message.chat.id
            
            try:
                total = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
                pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
                active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
                
                text = f"""
🎛 **Super Admin Dashboard**

🏪 Total Stores: **{total}**
⏳ Pending Approval: **{pending}**
🟢 Active Stores: **{active}**

🌐 **12 Languages Supported**

📌 ርምጫ ይምረጡ:
"""
                
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("⏳ ያልጸደቁ", callback_data="dash_pending"),
                    types.InlineKeyboardButton("🔄 አዘምን", callback_data="dash_refresh")
                )
                markup.add(types.InlineKeyboardButton("🚪 ውጣ", callback_data="dash_logout"))
                
                self.bot.send_message(
                    chat_id,
                    text,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Dashboard error: {e}")
                self.bot.send_message(chat_id, f"❌ ስህተት: {str(e)}")
        
        # ============================================================
        # DASHBOARD CALLBACKS
        # ============================================================
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("dash_"))
        def dashboard_callback(call):
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
            elif action == "logout":
                self.bot.answer_callback_query(call.id)
                with self.sessions_lock:
                    self.sessions.pop(chat_id, None)
                self.bot.send_message(chat_id, "🔒 ከአስተዳደር ወጥተዋል።")
        
        def _show_pending_stores(self, message):
            chat_id = message.chat.id
            
            try:
                stores = db_execute_dict("""
                    SELECT id, store_name, username, phone, area_text, shop_photo, shop_description, created_at
                    FROM stores WHERE is_approved = 0 AND is_active = 1
                    ORDER BY created_at DESC
                """)
                
                if not stores:
                    self.bot.send_message(chat_id, "✅ ምንም ያልተጸደቁ ሱቆች የሉም!")
                    return
                
                for store in stores:
                    text = f"""
🏪 **{store['store_name']}**
🆔 #{store['id']}
👤 @{store['username'] or 'ስም'}
📱 {store['phone'] or 'አልተገኘም'}
📍 {store['area_text'] or 'አልተዘጋጀም'}
📝 {store['shop_description'][:50] if store['shop_description'] else ''}...
📅 {format_date(store['created_at'])}
"""
                    markup = types.InlineKeyboardMarkup()
                    markup.add(
                        types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"sapprove_{store['id']}"),
                        types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"sreject_{store['id']}")
                    )
                    markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
                    
                    if store.get('shop_photo'):
                        try:
                            self.bot.send_photo(chat_id, store['shop_photo'], caption=text, reply_markup=markup, parse_mode="Markdown")
                        except:
                            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
                    else:
                        self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Pending stores error: {e}")
                self.bot.send_message(chat_id, f"❌ ስህተት: {str(e)}")
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sapprove_"))
        def approve_store(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            
            store_id = int(call.data.split("_")[1])
            
            try:
                store = db_execute_dict("SELECT token, store_name, admin_id FROM stores WHERE id = %s", (store_id,))
                if not store:
                    self.bot.answer_callback_query(call.id, "❌ አልተገኘም")
                    return
                
                store = store[0]
                db_execute("UPDATE stores SET is_approved = 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (store_id,))
                bot_manager.start_bot(store['token'])
                
                try:
                    self.bot.send_message(
                        store['admin_id'],
                        f"🎉 **ሱቅዎ ጸድቋል!**\n\n🏪 {store['store_name']}"
                    )
                except:
                    pass
                
                self.bot.edit_message_text(
                    f"✅ ሱቅ #{store_id} ጸድቋል!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "Approved!")
            except Exception as e:
                logger.error(f"Approve store error: {e}")
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sreject_"))
        def reject_store(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            
            store_id = int(call.data.split("_")[1])
            
            try:
                store = db_execute_dict("SELECT store_name, admin_id FROM stores WHERE id = %s", (store_id,))
                if not store:
                    self.bot.answer_callback_query(call.id, "❌ አልተገኘም")
                    return
                
                store = store[0]
                db_execute("DELETE FROM stores WHERE id = %s", (store_id,))
                
                try:
                    self.bot.send_message(
                        store['admin_id'],
                        f"❌ ሱቅዎ **{store['store_name']}** ውድቅ ተደርጓል።"
                    )
                except:
                    pass
                
                self.bot.edit_message_text(
                    f"❌ ሱቅ #{store_id} ውድቅ ተደርጓል!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "Rejected!")
            except Exception as e:
                logger.error(f"Reject store error: {e}")
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
        
        # ============================================================
        # REGISTRATION STATE HELPERS
        # ============================================================
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
        
        # ============================================================
        # POLLING
        # ============================================================
        def _start_polling(self):
            def _poll():
                while True:
                    try:
                        self.bot.infinity_polling(skip_pending=True, timeout=30)
                    except Exception as e:
                        logger.error(f"Polling error: {e}")
                        time.sleep(5)
            
            threading.Thread(target=_poll, daemon=True).start()

# =================================================================================================
#                           LOAD EXISTING STORES
# =================================================================================================

def load_existing_stores():
    try:
        stores = db_execute_dict("SELECT token FROM stores WHERE is_approved = 1")
        count = 0
        for store in stores:
            if bot_manager.start_bot(store['token']):
                count += 1
        logger.info(f"✅ {count} stores loaded and started")
    except Exception as e:
        logger.error(f"❌ Failed to load stores: {e}")

load_existing_stores()

# =================================================================================================
#                           MAIN ENTRY POINT
# =================================================================================================

if __name__ == "__main__":
    try:
        control_bot = ControlBot()
        logger.info("🚀 Ultimate Control Bot v7.0 is running!")
        logger.info("🌐 12 Languages Supported:")
        logger.info("   🇪🇹 አማርኛ, 🇬🇧 English, 🇨🇳 中文, 🇮🇳 हिन्दी")
        logger.info("   🇪🇸 Español, 🇸🇦 العربية, 🇫🇷 Français")
        logger.info("   🇪🇹 ኦሮምኛ, 🇪🇹 ትግርኛ, 🇸🇴 Soomaali, 🇪🇹 Qafar, 🇪🇹 ሲዳምኛ")
        logger.info(f"✅ {len(running_tokens)} bots are running")
        
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        while True:
            time.sleep(60)
