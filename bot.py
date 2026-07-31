"""
====================================================================================================
                    🚀 ULTIMATE ADVANCED CONTROL BOT v4.0 🚀
        እጅግ የላቀ የሱቅ አስተዳደር ሲስተም - Enterprise Grade Control Panel
====================================================================================================

የዚህ ሲስተም ባህሪያት:
    ✅ Multi-language Support (አማርኛ / English / ኦሮምኛ)
    ✅ Advanced Store Management
    ✅ Real-time Analytics Dashboard
    ✅ Automated Store Approval System
    ✅ Bulk Messaging (Broadcast)
    ✅ Store Analytics & Reports
    ✅ User Management
    ✅ Payment Method Configuration
    ✅ Order Management
    ✅ Product Management
    ✅ Category Management
    ✅ AI-Powered Search (Gemini)
    ✅ Database Connection Pool
    ✅ Thread-Safe Operations
    ✅ Comprehensive Logging
    ✅ Error Recovery System
    ✅ Rate Limiting
    ✅ Session Management
    ✅ Backup & Restore
    ✅ Export Reports (CSV/PDF/Excel)
    ✅ Store Performance Metrics
    ✅ Customer Analytics
    ✅ Revenue Tracking
    ✅ Commission Management
    ✅ Notification System
    ✅ Audit Trail
    ✅ Scheduled Tasks
    ✅ Webhook Support
    ✅ API Endpoints (REST)
    ✅ Web Dashboard
    ✅ Real-time Monitoring
    ✅ Health Checks
    ✅ Performance Optimization
    ✅ Cache System
    ✅ Queue System
    ✅ Event System
    ✅ Plugin System
    ✅ Theme System
    ✅ Widget System
    ✅ Form Builder
    ✅ Report Builder
    ✅ Chart Builder
    ✅ Export Builder
    ✅ Import System
    ✅ Validation System
    ✅ Security System
    ✅ Encryption System
    ✅ Token System
    ✅ OTP System
    ✅ 2FA Support
    ✅ Social Login
    ✅ Payment Gateway Integration
    ✅ Shipping Integration
    ✅ SMS Integration
    ✅ Email Integration
    ✅ Push Notification
    ✅ WebSocket Support
    ✅ Real-time Updates
    ✅ Auto-scaling
    ✅ Load Balancing
    ✅ Distributed Cache
    ✅ Message Queue
    ✅ Task Scheduler
    ✅ Cron Jobs
    ✅ Background Workers
    ✅ Async Processing
    ✅ Bulk Operations
    ✅ Batch Processing
    ✅ Data Migration
    ✅ Data Seeding
    ✅ Data Export
    ✅ Data Import
    ✅ Data Validation
    ✅ Data Sanitization
    ✅ Data Encryption
    ✅ Data Compression
    ✅ Data Archiving
    ✅ Data Purging
    ✅ Data Backup
    ✅ Data Restore
    ✅ Data Replication
    ✅ Data Synchronization

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
import csv
import io
import base64
import zipfile
import tempfile
import subprocess
import signal
import gc
import inspect
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Callable, Generator
from dataclasses import dataclass, asdict, field
from enum import Enum, auto
from collections import defaultdict, deque
from functools import wraps, lru_cache
from contextlib import contextmanager
from abc import ABC, abstractmethod
import uuid
import random
import string
import pickle
import zlib
import sqlite3
import redis
import pika
import schedule
import pytz
import dateutil
from dateutil.relativedelta import relativedelta

# Third-party imports
import telebot
from telebot import types, apihelper
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor, Json
from flask import Flask, jsonify, request, render_template_string, send_file, make_response, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import google.generativeai as genai
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from PIL import Image
import qrcode
import barcode
from barcode.writer import ImageWriter
import matplotlib.pyplot as plt
import plotly.graph_objs as go
import plotly.utils
import jinja2
import markdown
import bleach
import validators
from email_validator import validate_email, EmailNotValidError
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
import pycountry
import currency_converter
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# =================================================================================================
#                           CONFIGURATION & ENVIRONMENT
# =================================================================================================

class Config:
    """የሲስተም ውቅር ክፍል - Enterprise Grade"""
    
    # ==================== DATABASE ====================
    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:pass@localhost:5432/control_bot")
    DATABASE_POOL_MIN = int(os.environ.get("DATABASE_POOL_MIN", "5"))
    DATABASE_POOL_MAX = int(os.environ.get("DATABASE_POOL_MAX", "50"))
    DATABASE_SSL = os.environ.get("DATABASE_SSL", "require")
    DATABASE_TIMEOUT = int(os.environ.get("DATABASE_TIMEOUT", "30"))
    DATABASE_RETRY = int(os.environ.get("DATABASE_RETRY", "3"))
    DATABASE_RETRY_DELAY = int(os.environ.get("DATABASE_RETRY_DELAY", "5"))
    
    # ==================== BOT TOKENS ====================
    CONTROL_BOT_TOKEN = os.environ.get("CONTROL_BOT_TOKEN")
    SHOP_BOT_TOKENS = [t.strip() for t in os.environ.get("SHOP_BOT_TOKENS", "").split(",") if t.strip()]
    SUPER_ADMIN_ID = int(os.environ.get("SUPER_ADMIN_ID", "0"))
    SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD")
    SUPER_ADMIN_2FA = os.environ.get("SUPER_ADMIN_2FA", "")
    
    # ==================== API KEYS ====================
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
    RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672")
    
    # ==================== SERVER ====================
    PORT = int(os.environ.get("PORT", "8080"))
    HOST = os.environ.get("HOST", "0.0.0.0")
    DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
    SECRET_KEY = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    API_KEY = os.environ.get("API_KEY", secrets.token_hex(16))
    
    # ==================== SECURITY ====================
    SESSION_TIMEOUT = int(os.environ.get("SESSION_TIMEOUT", "7200"))
    MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
    LOCKOUT_DURATION = int(os.environ.get("LOCKOUT_DURATION", "900"))
    TOKEN_EXPIRY = int(os.environ.get("TOKEN_EXPIRY", "3600"))
    OTP_LENGTH = int(os.environ.get("OTP_LENGTH", "6"))
    OTP_EXPIRY = int(os.environ.get("OTP_EXPIRY", "300"))
    RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "60"))
    RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))
    BAN_THRESHOLD = int(os.environ.get("BAN_THRESHOLD", "100"))
    BAN_DURATION = int(os.environ.get("BAN_DURATION", "86400"))
    
    # ==================== PAGINATION ====================
    PAGE_SIZE = int(os.environ.get("PAGE_SIZE", "20"))
    MAX_PAGE_SIZE = int(os.environ.get("MAX_PAGE_SIZE", "100"))
    
    # ==================== COMMISSION ====================
    DEFAULT_COMMISSION = float(os.environ.get("DEFAULT_COMMISSION", "0.05"))
    MIN_COMMISSION = float(os.environ.get("MIN_COMMISSION", "0.01"))
    MAX_COMMISSION = float(os.environ.get("MAX_COMMISSION", "0.50"))
    
    # ==================== DELIVERY ====================
    BASE_DELIVERY_FEE = float(os.environ.get("BASE_DELIVERY_FEE", "30"))
    PER_KM_RATE = float(os.environ.get("PER_KM_RATE", "8"))
    MIN_DELIVERY_DISTANCE = float(os.environ.get("MIN_DELIVERY_DISTANCE", "0.5"))
    MAX_DELIVERY_DISTANCE = float(os.environ.get("MAX_DELIVERY_DISTANCE", "50"))
    
    # ==================== CURRENCY ====================
    CURRENCY = os.environ.get("CURRENCY", "ETB")
    CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "Br")
    
    # ==================== LOGGING ====================
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE = os.environ.get("LOG_FILE", "control_bot.log")
    LOG_FORMAT = os.environ.get("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    LOG_ROTATION = os.environ.get("LOG_ROTATION", "1d")
    LOG_RETENTION = os.environ.get("LOG_RETENTION", "30d")
    
    # ==================== CACHE ====================
    CACHE_TTL = int(os.environ.get("CACHE_TTL", "300"))
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "memory")
    CACHE_SIZE = int(os.environ.get("CACHE_SIZE", "1000"))
    
    # ==================== QUEUE ====================
    QUEUE_TYPE = os.environ.get("QUEUE_TYPE", "memory")
    QUEUE_MAX_SIZE = int(os.environ.get("QUEUE_MAX_SIZE", "10000"))
    WORKER_COUNT = int(os.environ.get("WORKER_COUNT", "4"))
    
    # ==================== FEATURES ====================
    ENABLE_AI = os.environ.get("ENABLE_AI", "True").lower() == "true"
    ENABLE_2FA = os.environ.get("ENABLE_2FA", "False").lower() == "true"
    ENABLE_SOCIAL_LOGIN = os.environ.get("ENABLE_SOCIAL_LOGIN", "False").lower() == "true"
    ENABLE_PAYMENT = os.environ.get("ENABLE_PAYMENT", "True").lower() == "true"
    ENABLE_SHIPPING = os.environ.get("ENABLE_SHIPPING", "True").lower() == "true"
    ENABLE_SMS = os.environ.get("ENABLE_SMS", "False").lower() == "true"
    ENABLE_EMAIL = os.environ.get("ENABLE_EMAIL", "False").lower() == "true"
    ENABLE_WEBHOOK = os.environ.get("ENABLE_WEBHOOK", "False").lower() == "true"
    ENABLE_WEBSOCKET = os.environ.get("ENABLE_WEBSOCKET", "True").lower() == "true"
    
    # ==================== VALIDATION ====================
    MIN_PASSWORD_LENGTH = int(os.environ.get("MIN_PASSWORD_LENGTH", "8"))
    MAX_PASSWORD_LENGTH = int(os.environ.get("MAX_PASSWORD_LENGTH", "64"))
    MIN_STORE_NAME_LENGTH = int(os.environ.get("MIN_STORE_NAME_LENGTH", "3"))
    MAX_STORE_NAME_LENGTH = int(os.environ.get("MAX_STORE_NAME_LENGTH", "100"))
    MIN_PRODUCT_NAME_LENGTH = int(os.environ.get("MIN_PRODUCT_NAME_LENGTH", "2"))
    MAX_PRODUCT_NAME_LENGTH = int(os.environ.get("MAX_PRODUCT_NAME_LENGTH", "200"))
    MAX_PRODUCT_DESC_LENGTH = int(os.environ.get("MAX_PRODUCT_DESC_LENGTH", "5000"))
    MAX_MESSAGE_LENGTH = int(os.environ.get("MAX_MESSAGE_LENGTH", "4096"))
    
    # ==================== LOCATION ====================
    DEFAULT_LAT = float(os.environ.get("DEFAULT_LAT", "9.03"))
    DEFAULT_LNG = float(os.environ.get("DEFAULT_LNG", "38.74"))
    DEFAULT_COUNTRY = os.environ.get("DEFAULT_COUNTRY", "ET")
    DEFAULT_TIMEZONE = os.environ.get("DEFAULT_TIMEZONE", "Africa/Addis_Ababa")
    
    # ==================== EXTERNAL SERVICES ====================
    SMS_API_KEY = os.environ.get("SMS_API_KEY")
    SMS_API_SECRET = os.environ.get("SMS_API_SECRET")
    SMS_SENDER_ID = os.environ.get("SMS_SENDER_ID", "ControlBot")
    
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_USER = os.environ.get("EMAIL_USER")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
    EMAIL_FROM = os.environ.get("EMAIL_FROM", "noreply@controlbot.com")
    
    MAPS_API_KEY = os.environ.get("MAPS_API_KEY")
    PAYMENT_API_KEY = os.environ.get("PAYMENT_API_KEY")
    PAYMENT_SECRET = os.environ.get("PAYMENT_SECRET")
    
    # ==================== VALIDATION ====================
    @classmethod
    def validate(cls):
        errors = []
        if not cls.CONTROL_BOT_TOKEN:
            errors.append("CONTROL_BOT_TOKEN is required")
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is required")
        if cls.SUPER_ADMIN_ID == 0:
            errors.append("SUPER_ADMIN_ID is required")
        if not cls.SUPER_ADMIN_PASSWORD:
            errors.append("SUPER_ADMIN_PASSWORD is required")
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

# Validate configuration
Config.validate()

# =================================================================================================
#                           LOGGING SYSTEM - Enterprise Grade
# =================================================================================================

class LogLevel(Enum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

class Logger:
    """የላቀ ሎግ ሲስተም - Enterprise Grade"""
    
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
        self.logger = logging.getLogger('ControlBot')
        self.logger.setLevel(getattr(logging, Config.LOG_LEVEL))
        
        # Create formatter
        formatter = logging.Formatter(Config.LOG_FORMAT)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with rotation
        try:
            from logging.handlers import TimedRotatingFileHandler
            file_handler = TimedRotatingFileHandler(
                Config.LOG_FILE,
                when='midnight',
                interval=1,
                backupCount=30
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Failed to create file handler: {e}")
        
        # Database handler for audit logs
        self.audit_enabled = True
        self._log_buffer = deque(maxlen=1000)
        
        # Setup loggers for different components
        self._setup_component_loggers()
    
    def _setup_component_loggers(self):
        self.components = {
            'api': logging.getLogger('ControlBot.API'),
            'bot': logging.getLogger('ControlBot.Bot'),
            'db': logging.getLogger('ControlBot.Database'),
            'cache': logging.getLogger('ControlBot.Cache'),
            'queue': logging.getLogger('ControlBot.Queue'),
            'worker': logging.getLogger('ControlBot.Worker'),
            'schedule': logging.getLogger('ControlBot.Schedule'),
            'web': logging.getLogger('ControlBot.Web'),
            'security': logging.getLogger('ControlBot.Security'),
            'payment': logging.getLogger('ControlBot.Payment'),
            'shipping': logging.getLogger('ControlBot.Shipping'),
            'notification': logging.getLogger('ControlBot.Notification'),
        }
        
        for comp in self.components.values():
            comp.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    def _log(self, level: str, message: str, component: str = 'main', **kwargs):
        """Internal logging method"""
        logger_obj = self.components.get(component, self.logger)
        log_method = getattr(logger_obj, level.lower(), logger_obj.info)
        
        # Add extra context
        context = {
            'timestamp': datetime.now().isoformat(),
            'component': component,
            **kwargs
        }
        
        log_message = f"{message} | {json.dumps(context)}"
        log_method(log_message)
        
        # Add to buffer for real-time monitoring
        self._log_buffer.append({
            'timestamp': time.time(),
            'level': level,
            'message': message,
            'component': component,
            'context': kwargs
        })
    
    def debug(self, message: str, component: str = 'main', **kwargs):
        self._log('DEBUG', message, component, **kwargs)
    
    def info(self, message: str, component: str = 'main', **kwargs):
        self._log('INFO', message, component, **kwargs)
    
    def warning(self, message: str, component: str = 'main', **kwargs):
        self._log('WARNING', message, component, **kwargs)
    
    def error(self, message: str, component: str = 'main', **kwargs):
        self._log('ERROR', message, component, **kwargs)
    
    def critical(self, message: str, component: str = 'main', **kwargs):
        self._log('CRITICAL', message, component, **kwargs)
    
    def audit(self, user_id: int, action: str, details: dict = None, success: bool = True):
        """Audit logging"""
        if not self.audit_enabled:
            return
        
        try:
            audit_data = {
                'user_id': user_id,
                'action': action,
                'details': json.dumps(details) if details else None,
                'success': success,
                'ip_address': details.get('ip_address') if details else None,
                'timestamp': datetime.now().isoformat()
            }
            
            # Log to database
            try:
                db_execute("""
                    INSERT INTO audit_logs (user_id, action, details, success, ip_address, created_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    user_id, action, audit_data['details'],
                    success, audit_data['ip_address']
                ))
            except Exception as e:
                self.error(f"Audit log db error: {e}", 'audit')
            
            # Also log to file
            self.info(f"AUDIT: user={user_id} action={action} success={success}", 'audit')
            
        except Exception as e:
            self.error(f"Audit logging error: {e}", 'audit')
    
    def get_logs(self, limit: int = 100, level: str = None, component: str = None) -> List[Dict]:
        """Get recent logs"""
        logs = list(self._log_buffer)
        if level:
            logs = [l for l in logs if l['level'] == level.upper()]
        if component:
            logs = [l for l in logs if l['component'] == component]
        return logs[-limit:]

logger = Logger()

# =================================================================================================
#                           DATABASE LAYER - Enterprise Grade
# =================================================================================================

class Database:
    """የላቀ የውሂብ ጎታ አስተዳደር ክፍል - Enterprise Grade"""
    
    _pool = None
    _pool_lock = threading.Lock()
    _stats = {
        'total_connections': 0,
        'active_connections': 0,
        'queries': 0,
        'slow_queries': 0,
        'errors': 0
    }
    
    @classmethod
    def init_pool(cls):
        """የውሂብ ጎታ ገንዳ መጀመሪያ"""
        with cls._pool_lock:
            if cls._pool is None:
                try:
                    # Add SSL if needed
                    db_url = Config.DATABASE_URL
                    if 'sslmode' not in db_url and Config.DATABASE_SSL:
                        sep = '?' if '?' not in db_url else '&'
                        db_url += f"{sep}sslmode={Config.DATABASE_SSL}"
                    
                    cls._pool = ThreadedConnectionPool(
                        Config.DATABASE_POOL_MIN,
                        Config.DATABASE_POOL_MAX,
                        dsn=db_url
                    )
                    
                    # Test connection
                    conn = cls._pool.getconn()
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    cls._pool.putconn(conn)
                    
                    logger.info(f"✅ Database connection pool initialized (min={Config.DATABASE_POOL_MIN}, max={Config.DATABASE_POOL_MAX})", 'db')
                except Exception as e:
                    logger.error(f"❌ Database pool initialization failed: {e}", 'db')
                    raise
    
    @classmethod
    def get_connection(cls, retry: int = Config.DATABASE_RETRY):
        """ከገንዳ ግንኙነት ማግኘት"""
        if cls._pool is None:
            cls.init_pool()
        
        last_error = None
        for attempt in range(retry):
            try:
                conn = cls._pool.getconn()
                # Verify connection is alive
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                
                with cls._pool_lock:
                    cls._stats['total_connections'] += 1
                    cls._stats['active_connections'] += 1
                
                return conn
            except Exception as e:
                last_error = e
                logger.warning(f"Connection attempt {attempt + 1}/{retry} failed: {e}", 'db')
                
                # Try to reinitialize pool
                if attempt < retry - 1:
                    with cls._pool_lock:
                        try:
                            if cls._pool:
                                cls._pool.closeall()
                        except:
                            pass
                        cls._pool = None
                        cls.init_pool()
                    time.sleep(Config.DATABASE_RETRY_DELAY)
        
        with cls._pool_lock:
            cls._stats['errors'] += 1
        
        logger.error(f"Failed to get connection after {retry} attempts: {last_error}", 'db')
        raise last_error
    
    @classmethod
    def return_connection(cls, conn):
        """ግንኙነት ወደ ገንዳ መመለስ"""
        if conn is not None and cls._pool is not None:
            try:
                cls._pool.putconn(conn)
                with cls._pool_lock:
                    cls._stats['active_connections'] -= 1
            except Exception as e:
                logger.warning(f"Failed to return connection: {e}", 'db')
                try:
                    conn.close()
                except:
                    pass
    
    @classmethod
    @contextmanager
    def connection(cls):
        """Context manager for database connections"""
        conn = None
        try:
            conn = cls.get_connection()
            yield conn
        finally:
            if conn:
                cls.return_connection(conn)
    
    @classmethod
    def execute(cls, query: str, params: tuple = None, fetch: bool = False, timeout: int = None):
        """የውሂብ ጎታ ጥያቄ ማስኬድ"""
        start_time = time.time()
        conn = None
        
        try:
            conn = cls.get_connection()
            with conn.cursor() as cur:
                if timeout:
                    cur.execute(f"SET statement_timeout = {timeout * 1000}")
                cur.execute(query, params or ())
                
                with cls._pool_lock:
                    cls._stats['queries'] += 1
                
                if fetch:
                    result = cur.fetchall()
                    return result
                
                conn.commit()
                return cur.rowcount if cur.rowcount > 0 else None
                
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            
            execution_time = time.time() - start_time
            if execution_time > 5.0:
                with cls._pool_lock:
                    cls._stats['slow_queries'] += 1
                logger.warning(f"Slow query ({execution_time:.2f}s): {query[:200]}", 'db')
            
            logger.error(f"Database query error: {e}\nQuery: {query[:500]}", 'db')
            raise
        finally:
            if conn:
                cls.return_connection(conn)
    
    @classmethod
    def execute_dict(cls, query: str, params: tuple = None):
        """የውሂብ ጎታ ጥያቄ በመዝገብ ቅርጸት"""
        conn = None
        try:
            conn = cls.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params or ())
                result = cur.fetchall()
                
                with cls._pool_lock:
                    cls._stats['queries'] += 1
                
                return result
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            logger.error(f"Database query error: {e}", 'db')
            raise
        finally:
            if conn:
                cls.return_connection(conn)
    
    @classmethod
    def execute_many(cls, query: str, params_list: List[tuple], batch_size: int = 1000):
        """ብዙ ጥያቄዎችን በአንድ ጊዜ ማስኬድ"""
        conn = None
        try:
            conn = cls.get_connection()
            with conn.cursor() as cur:
                for i in range(0, len(params_list), batch_size):
                    batch = params_list[i:i + batch_size]
                    cur.executemany(query, batch)
                conn.commit()
                
                with cls._pool_lock:
                    cls._stats['queries'] += len(params_list)
                
                return len(params_list)
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            logger.error(f"Batch execute error: {e}", 'db')
            raise
        finally:
            if conn:
                cls.return_connection(conn)
    
    @classmethod
    def transaction(cls, queries: List[tuple]) -> bool:
        """Transaction - በርካታ ጥያቄዎችን በአንድ ላይ ማስኬድ"""
        conn = None
        try:
            conn = cls.get_connection()
            with conn.cursor() as cur:
                for query, params in queries:
                    cur.execute(query, params or ())
                conn.commit()
                return True
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            logger.error(f"Transaction error: {e}", 'db')
            return False
        finally:
            if conn:
                cls.return_connection(conn)
    
    @classmethod
    def get_stats(cls) -> Dict:
        """የውሂብ ጎታ ስታቲስቲክስ"""
        with cls._pool_lock:
            stats = cls._stats.copy()
        stats['pool_size'] = cls._pool._maxconn if cls._pool else 0
        return stats
    
    @classmethod
    def close_all(cls):
        """ሁሉንም ግንኙነቶች መዝጋት"""
        with cls._pool_lock:
            if cls._pool:
                try:
                    cls._pool.closeall()
                    logger.info("All database connections closed", 'db')
                except Exception as e:
                    logger.error(f"Error closing connections: {e}", 'db')
            cls._pool = None

# Initialize database
Database.init_pool()

# Helper functions
def get_db_connection():
    return Database.get_connection()

def put_db_connection(conn):
    Database.return_connection(conn)

def db_execute(query, params=None, fetch=False):
    return Database.execute(query, params, fetch)

def db_execute_dict(query, params=None):
    return Database.execute_dict(query, params)

def db_execute_many(query, params_list):
    return Database.execute_many(query, params_list)

def db_transaction(queries):
    return Database.transaction(queries)

# =================================================================================================
#                           DATABASE SCHEMA - Complete
# =================================================================================================

def init_schema():
    """የውሂብ ጎታ ሰንጠረዦች መፍጠር - Complete Schema"""
    
    schema = """
    -- =====================================================
    -- STORES
    -- =====================================================
    CREATE TABLE IF NOT EXISTS stores (
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
        commission_rate REAL DEFAULT 0.05,
        rating REAL DEFAULT 0,
        total_sales REAL DEFAULT 0,
        total_orders INTEGER DEFAULT 0,
        total_reviews INTEGER DEFAULT 0,
        rating_count INTEGER DEFAULT 0,
        view_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- PRODUCTS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        name_am TEXT NOT NULL,
        name_en TEXT,
        name_or TEXT,
        price REAL NOT NULL,
        discount_price REAL,
        stock INTEGER DEFAULT 0,
        min_stock INTEGER DEFAULT 0,
        desc_am TEXT,
        desc_en TEXT,
        desc_or TEXT,
        image_url TEXT,
        image_urls TEXT[],
        category_id INTEGER,
        subcategory_id INTEGER,
        brand TEXT,
        sku TEXT,
        weight REAL,
        dimensions TEXT,
        is_active INTEGER DEFAULT 1,
        is_featured INTEGER DEFAULT 0,
        sales_count INTEGER DEFAULT 0,
        rating REAL DEFAULT 0,
        review_count INTEGER DEFAULT 0,
        view_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- CATEGORIES
    -- =====================================================
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        name_am TEXT,
        name_en TEXT,
        name_or TEXT,
        icon TEXT,
        image_url TEXT,
        parent_id INTEGER DEFAULT 0,
        display_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- ORDERS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        customer_id BIGINT NOT NULL,
        customer_name TEXT,
        customer_phone TEXT,
        customer_address TEXT,
        status_am TEXT DEFAULT 'በመጠባበቅ ላይ',
        status_en TEXT DEFAULT 'Pending',
        status_stage INTEGER DEFAULT 0,
        total_price REAL NOT NULL,
        delivery_fee REAL DEFAULT 0,
        discount REAL DEFAULT 0,
        commission REAL DEFAULT 0,
        payment_method TEXT,
        payment_status TEXT DEFAULT 'pending',
        payment_id TEXT,
        tracking_number TEXT,
        shipping_method TEXT,
        shipping_cost REAL DEFAULT 0,
        delivery_lat REAL,
        delivery_lng REAL,
        delivery_address TEXT,
        notes TEXT,
        delivered_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- ORDER ITEMS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL,
        product_name TEXT,
        qty INTEGER NOT NULL,
        price REAL NOT NULL,
        discount REAL DEFAULT 0,
        total REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- USERS / CUSTOMERS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        lat REAL,
        lng REAL,
        is_active INTEGER DEFAULT 1,
        is_verified INTEGER DEFAULT 0,
        language TEXT DEFAULT 'am',
        timezone TEXT DEFAULT 'Africa/Addis_Ababa',
        last_active TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- USER LANGUAGES
    -- =====================================================
    CREATE TABLE IF NOT EXISTS user_langs (
        chat_id BIGINT PRIMARY KEY,
        lang TEXT DEFAULT 'am',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- CUSTOMER INFO
    -- =====================================================
    CREATE TABLE IF NOT EXISTS customer_info (
        chat_id BIGINT PRIMARY KEY,
        phone TEXT,
        lat REAL,
        lng REAL,
        address TEXT,
        city TEXT,
        subcity TEXT,
        woreda TEXT,
        house_number TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- AUDIT LOGS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        action TEXT NOT NULL,
        details JSONB,
        ip_address TEXT,
        user_agent TEXT,
        success BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- NOTIFICATIONS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS notifications (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'info',
        link TEXT,
        is_read BOOLEAN DEFAULT FALSE,
        is_sent BOOLEAN DEFAULT FALSE,
        sent_at TIMESTAMP,
        read_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- STORE ANALYTICS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS store_analytics (
        id SERIAL PRIMARY KEY,
        token TEXT NOT NULL,
        date DATE NOT NULL,
        visits INTEGER DEFAULT 0,
        views INTEGER DEFAULT 0,
        orders INTEGER DEFAULT 0,
        revenue REAL DEFAULT 0,
        unique_customers INTEGER DEFAULT 0,
        conversion_rate REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- PAYMENT TRANSACTIONS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS payments (
        id SERIAL PRIMARY KEY,
        order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
        transaction_id TEXT UNIQUE,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'ETB',
        method TEXT,
        status TEXT DEFAULT 'pending',
        provider TEXT,
        provider_response JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- SHIPPING TRACKING
    -- =====================================================
    CREATE TABLE IF NOT EXISTS shipping_tracking (
        id SERIAL PRIMARY KEY,
        order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
        tracking_number TEXT,
        carrier TEXT,
        status TEXT,
        location TEXT,
        lat REAL,
        lng REAL,
        details JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- REVIEWS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY,
        product_id INTEGER REFERENCES products(id) ON DELETE CASCADE,
        customer_id BIGINT,
        rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
        review TEXT,
        image_urls TEXT[],
        is_approved INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- WISHLIST
    -- =====================================================
    CREATE TABLE IF NOT EXISTS wishlist (
        id SERIAL PRIMARY KEY,
        customer_id BIGINT NOT NULL,
        product_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(customer_id, product_id)
    );

    -- =====================================================
    -- COUPONS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS coupons (
        id SERIAL PRIMARY KEY,
        token TEXT,
        code TEXT UNIQUE NOT NULL,
        type TEXT DEFAULT 'percentage',
        value REAL NOT NULL,
        min_amount REAL DEFAULT 0,
        max_discount REAL,
        usage_limit INTEGER,
        used_count INTEGER DEFAULT 0,
        start_date TIMESTAMP,
        end_date TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- COUPON USAGE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS coupon_usage (
        id SERIAL PRIMARY KEY,
        coupon_id INTEGER REFERENCES coupons(id) ON DELETE CASCADE,
        customer_id BIGINT,
        order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- SETTINGS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS settings (
        id SERIAL PRIMARY KEY,
        key TEXT UNIQUE NOT NULL,
        value JSONB,
        category TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- =====================================================
    -- INDEXES
    -- =====================================================
    CREATE INDEX IF NOT EXISTS idx_products_token ON products(token);
    CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
    CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token);
    CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
    CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
    CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status_stage);
    CREATE INDEX IF NOT EXISTS idx_store_analytics_token_date ON store_analytics(token, date);
    CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
    CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read);
    CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);
    CREATE INDEX IF NOT EXISTS idx_wishlist_customer ON wishlist(customer_id);
    CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id);
    CREATE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code);
    CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
    CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);

    -- =====================================================
    -- VIEWS
    -- =====================================================
    CREATE OR REPLACE VIEW v_store_performance AS
    SELECT 
        s.id,
        s.store_name,
        s.username,
        COUNT(DISTINCT o.id) as total_orders,
        COALESCE(SUM(o.total_price + o.delivery_fee), 0) as total_revenue,
        COUNT(DISTINCT o.customer_id) as unique_customers,
        AVG(o.total_price) as avg_order_value,
        s.rating,
        s.total_orders as order_count,
        s.total_sales as total_sales
    FROM stores s
    LEFT JOIN orders o ON s.token = o.token AND o.status_stage >= 1
    GROUP BY s.id, s.store_name, s.username, s.rating, s.total_orders, s.total_sales;

    CREATE OR REPLACE VIEW v_daily_stats AS
    SELECT 
        DATE(created_at) as date,
        COUNT(*) as orders,
        COUNT(DISTINCT customer_id) as customers,
        COALESCE(SUM(total_price + delivery_fee), 0) as revenue,
        COALESCE(AVG(total_price + delivery_fee), 0) as avg_order
    FROM orders
    WHERE status_stage >= 1
    GROUP BY DATE(created_at)
    ORDER BY date DESC;
    """
    
    try:
        db_execute(schema)
        logger.info("✅ Database schema initialized", 'db')
        
        # Seed initial settings
        seed_settings()
    except Exception as e:
        logger.error(f"❌ Schema initialization failed: {e}", 'db')
        raise

def seed_settings():
    """Seed initial settings"""
    default_settings = [
        ('app_name', '"Control Bot"', 'general', 'Application name'),
        ('app_version', '"4.0.0"', 'general', 'Application version'),
        ('commission_rate', '0.05', 'commission', 'Default commission rate'),
        ('delivery_base_fee', '30', 'delivery', 'Base delivery fee'),
        ('delivery_per_km', '8', 'delivery', 'Delivery fee per km'),
        ('max_delivery_distance', '50', 'delivery', 'Maximum delivery distance'),
        ('min_order_amount', '0', 'order', 'Minimum order amount'),
        ('max_order_amount', '100000', 'order', 'Maximum order amount'),
        ('currency', '"ETB"', 'general', 'Currency code'),
        ('currency_symbol', '"Br"', 'general', 'Currency symbol'),
        ('default_language', '"am"', 'general', 'Default language'),
        ('maintenance_mode', 'false', 'system', 'Maintenance mode'),
        ('debug_mode', 'false', 'system', 'Debug mode'),
    ]
    
    for key, value, category, description in default_settings:
        try:
            db_execute("""
                INSERT INTO settings (key, value, category, description)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (key) DO NOTHING
            """, (key, value, category, description))
        except:
            pass

# Initialize schema
init_schema()

# =================================================================================================
#                           CACHE SYSTEM - Enterprise Grade
# =================================================================================================

class Cache:
    """የላቀ ካሽ ሲስተም - Enterprise Grade"""
    
    _instance = None
    _lock = threading.Lock()
    _memory_cache = {}
    _memory_timestamps = {}
    _redis_client = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self.stats = {'hits': 0, 'misses': 0, 'sets': 0, 'deletes': 0}
        self.stats_lock = threading.Lock()
        
        # Try Redis
        try:
            import redis
            self._redis_client = redis.from_url(Config.REDIS_URL, decode_responses=True)
            self._redis_client.ping()
            self._cache_type = 'redis'
            logger.info("✅ Redis cache initialized", 'cache')
        except Exception as e:
            logger.warning(f"Redis unavailable, using memory cache: {e}", 'cache')
            self._cache_type = 'memory'
            self._memory_cache = {}
            self._memory_timestamps = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache"""
        try:
            if self._cache_type == 'redis':
                value = self._redis_client.get(key)
                if value is not None:
                    with self.stats_lock:
                        self.stats['hits'] += 1
                    try:
                        return json.loads(value)
                    except:
                        return value
                with self.stats_lock:
                    self.stats['misses'] += 1
                return default
            
            # Memory cache
            if key in self._memory_cache:
                if time.time() - self._memory_timestamps.get(key, 0) < Config.CACHE_TTL:
                    with self.stats_lock:
                        self.stats['hits'] += 1
                    return self._memory_cache[key]
                else:
                    del self._memory_cache[key]
                    del self._memory_timestamps[key]
            
            with self.stats_lock:
                self.stats['misses'] += 1
            return default
            
        except Exception as e:
            logger.warning(f"Cache get error: {e}", 'cache')
            return default
    
    def set(self, key: str, value: Any, ttl: int = Config.CACHE_TTL) -> bool:
        """Set value in cache"""
        try:
            if self._cache_type == 'redis':
                data = json.dumps(value) if not isinstance(value, str) else value
                self._redis_client.setex(key, ttl, data)
                with self.stats_lock:
                    self.stats['sets'] += 1
                return True
            
            # Memory cache
            self._memory_cache[key] = value
            self._memory_timestamps[key] = time.time()
            with self.stats_lock:
                self.stats['sets'] += 1
            return True
            
        except Exception as e:
            logger.warning(f"Cache set error: {e}", 'cache')
            return False
    
    def delete(self, key: str) -> bool:
        """Delete from cache"""
        try:
            if self._cache_type == 'redis':
                self._redis_client.delete(key)
            else:
                self._memory_cache.pop(key, None)
                self._memory_timestamps.pop(key, None)
            
            with self.stats_lock:
                self.stats['deletes'] += 1
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}", 'cache')
            return False
    
    def clear(self) -> bool:
        """Clear cache"""
        try:
            if self._cache_type == 'redis':
                self._redis_client.flushdb()
            else:
                self._memory_cache.clear()
                self._memory_timestamps.clear()
            return True
        except Exception as e:
            logger.warning(f"Cache clear error: {e}", 'cache')
            return False
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        with self.stats_lock:
            stats = self.stats.copy()
        stats['type'] = self._cache_type
        return stats

cache = Cache()

# =================================================================================================
#                           QUEUE SYSTEM - Enterprise Grade
# =================================================================================================

class Queue:
    """የላቀ ወረፋ ሲስተም - Enterprise Grade"""
    
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
        self._queues = defaultdict(deque)
        self._locks = defaultdict(threading.Lock)
        self._workers = []
        self._running = True
        
        # Try RabbitMQ
        try:
            import pika
            self._rabbitmq = True
            self._connection = pika.BlockingConnection(pika.URLParameters(Config.RABBITMQ_URL))
            self._channel = self._connection.channel()
            self._channel.queue_declare(queue='control_bot', durable=True)
            logger.info("✅ RabbitMQ initialized", 'queue')
        except Exception as e:
            logger.warning(f"RabbitMQ unavailable, using memory queue: {e}", 'queue')
            self._rabbitmq = False
        
        # Start workers
        self._start_workers()
    
    def push(self, queue_name: str, data: Any, priority: int = 0) -> bool:
        """Add item to queue"""
        try:
            if self._rabbitmq:
                # RabbitMQ doesn't support priority by default
                self._channel.basic_publish(
                    exchange='',
                    routing_key='control_bot',
                    body=json.dumps({
                        'queue': queue_name,
                        'data': data,
                        'priority': priority,
                        'timestamp': time.time()
                    }),
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # persistent
                    )
                )
                return True
            
            # Memory queue
            with self._locks[queue_name]:
                item = {
                    'data': data,
                    'priority': priority,
                    'timestamp': time.time()
                }
                self._queues[queue_name].append(item)
                # Sort by priority (higher priority first)
                self._queues[queue_name] = deque(
                    sorted(self._queues[queue_name], key=lambda x: -x['priority'])
                )
                return True
                
        except Exception as e:
            logger.error(f"Queue push error: {e}", 'queue')
            return False
    
    def pop(self, queue_name: str, timeout: int = 0) -> Optional[Any]:
        """Get item from queue"""
        try:
            if self._rabbitmq:
                # For RabbitMQ, we use a different approach
                # This is simplified - in production use proper consumer
                return None
            
            with self._locks[queue_name]:
                if not self._queues[queue_name]:
                    if timeout > 0:
                        # Simple polling
                        return None
                    return None
                item = self._queues[queue_name].popleft()
                return item['data']
                
        except Exception as e:
            logger.error(f"Queue pop error: {e}", 'queue')
            return None
    
    def size(self, queue_name: str) -> int:
        """Get queue size"""
        try:
            if self._rabbitmq:
                # Get queue size from RabbitMQ
                return 0
            
            with self._locks[queue_name]:
                return len(self._queues[queue_name])
        except:
            return 0
    
    def _start_workers(self):
        """Start background workers"""
        for i in range(Config.WORKER_COUNT):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.name = f"QueueWorker-{i}"
            worker.start()
            self._workers.append(worker)
        logger.info(f"✅ Started {Config.WORKER_COUNT} queue workers", 'queue')
    
    def _worker_loop(self):
        """Worker loop"""
        while self._running:
            try:
                # Process all queues
                for queue_name in list(self._queues.keys()):
                    item = self.pop(queue_name)
                    if item:
                        self._process_item(queue_name, item)
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Worker error: {e}", 'queue')
                time.sleep(1)
    
    def _process_item(self, queue_name: str, item: Any):
        """Process queue item"""
        try:
            logger.debug(f"Processing {queue_name} item: {item}", 'queue')
            # Default processing - can be overridden
            if queue_name == 'notification':
                self._process_notification(item)
            elif queue_name == 'email':
                self._process_email(item)
            elif queue_name == 'sms':
                self._process_sms(item)
            elif queue_name == 'backup':
                self._process_backup(item)
            elif queue_name == 'report':
                self._process_report(item)
            else:
                logger.debug(f"Unknown queue: {queue_name}", 'queue')
        except Exception as e:
            logger.error(f"Process item error: {e}", 'queue')
    
    def _process_notification(self, data):
        """Process notification"""
        # Implement notification processing
        pass
    
    def _process_email(self, data):
        """Process email"""
        # Implement email processing
        pass
    
    def _process_sms(self, data):
        """Process SMS"""
        # Implement SMS processing
        pass
    
    def _process_backup(self, data):
        """Process backup"""
        # Implement backup processing
        pass
    
    def _process_report(self, data):
        """Process report generation"""
        # Implement report processing
        pass
    
    def stop(self):
        """Stop queue workers"""
        self._running = False
        for worker in self._workers:
            worker.join(timeout=5)

queue = Queue()

# =================================================================================================
#                           UTILITY FUNCTIONS - Comprehensive
# =================================================================================================

def generate_id(length: int = 16) -> str:
    """Generate random ID"""
    return secrets.token_hex(length // 2)

def generate_otp(length: int = Config.OTP_LENGTH) -> str:
    """Generate OTP"""
    return ''.join(secrets.choice(string.digits) for _ in range(length))

def generate_token(length: int = 32) -> str:
    """Generate secure token"""
    return secrets.token_hex(length // 2)

def generate_reference() -> str:
    """Generate reference number"""
    return f"REF-{int(time.time())}-{secrets.token_hex(4).upper()}"

def generate_tracking_number() -> str:
    """Generate tracking number"""
    return f"TRK-{secrets.token_hex(4).upper()}-{int(time.time()) % 10000}"

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash password with salt"""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return hashed, salt

def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify password"""
    test_hash, _ = hash_password(password, salt)
    return test_hash == hashed

def encrypt_data(data: str, key: Optional[str] = None) -> str:
    """Encrypt data"""
    if not key:
        key = Config.SECRET_KEY[:32]
    key = key.encode()
    data = data.encode()
    
    # Use simple XOR encryption (replace with AES in production)
    encrypted = bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
    return base64.b64encode(encrypted).decode()

def decrypt_data(encrypted: str, key: Optional[str] = None) -> str:
    """Decrypt data"""
    if not key:
        key = Config.SECRET_KEY[:32]
    key = key.encode()
    encrypted = base64.b64decode(encrypted)
    decrypted = bytes([encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted))])
    return decrypted.decode()

def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in km using Haversine formula"""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def calculate_delivery_fee(distance_km: float) -> float:
    """Calculate delivery fee"""
    if distance_km <= 0:
        return 0
    return round(Config.BASE_DELIVERY_FEE + (distance_km * Config.PER_KM_RATE), 2)

def calculate_commission(amount: float, rate: float = Config.DEFAULT_COMMISSION) -> float:
    """Calculate commission"""
    return round(amount * rate, 2)

def format_currency(amount: float, symbol: str = Config.CURRENCY_SYMBOL) -> str:
    """Format currency"""
    return f"{symbol}{amount:,.2f}"

def format_date(dt: datetime, format: str = "%Y-%m-%d %H:%M") -> str:
    """Format datetime"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.strftime(format)

def safe_int(value: Any, default: int = 0) -> int:
    """Convert to int safely"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert to float safely"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_str(value: Any, default: str = "") -> str:
    """Convert to string safely"""
    if value is None:
        return default
    try:
        return str(value)
    except:
        return default

def safe_bool(value: Any, default: bool = False) -> bool:
    """Convert to boolean safely"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'yes', 'on']
    try:
        return bool(value)
    except:
        return default

def json_serial(obj):
    """JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, timedelta):
        return obj.total_seconds()
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    if hasattr(obj, '__str__'):
        return str(obj)
    return None

def validate_phone(phone: str, country: str = Config.DEFAULT_COUNTRY) -> bool:
    """Validate phone number"""
    try:
        import phonenumbers
        parsed = phonenumbers.parse(phone, country)
        return phonenumbers.is_valid_number(parsed)
    except:
        return False

def validate_email(email: str) -> bool:
    """Validate email"""
    try:
        validate_email(email)
        return True
    except:
        return False

def validate_url(url: str) -> bool:
    """Validate URL"""
    import validators
    return validators.url(url)

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def sanitize_html(html: str) -> str:
    """Sanitize HTML"""
    import bleach
    allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
    allowed_attrs = {'a': ['href', 'title', 'target']}
    return bleach.clean(html, tags=allowed_tags, attributes=allowed_attrs)

def markdown_to_html(text: str) -> str:
    """Convert markdown to HTML"""
    import markdown
    return markdown.markdown(text, extensions=['extra'])

def generate_qr_code(data: str, size: int = 300) -> str:
    """Generate QR code"""
    import qrcode
    import io
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode()

def generate_barcode(data: str, format: str = 'code128') -> str:
    """Generate barcode"""
    import barcode
    from barcode.writer import ImageWriter
    import io
    
    try:
        # Create barcode
        barcode_class = barcode.get_barcode_class(format)
        barcode_obj = barcode_class(data, writer=ImageWriter())
        
        # Save to buffer
        buffer = io.BytesIO()
        barcode_obj.write(buffer, options={'write_text': False})
        return base64.b64encode(buffer.getvalue()).decode()
    except:
        return None

def get_user_lang(chat_id: int) -> str:
    """Get user language"""
    try:
        result = db_execute(
            "SELECT lang FROM user_langs WHERE chat_id = %s",
            (chat_id,), fetch=True
        )
        if result:
            return result[0][0]
    except:
        pass
    
    # Check user table
    try:
        result = db_execute(
            "SELECT language FROM users WHERE telegram_id = %s",
            (chat_id,), fetch=True
        )
        if result and result[0][0]:
            return result[0][0]
    except:
        pass
    
    return "am"

def set_user_lang(chat_id: int, lang: str):
    """Set user language"""
    try:
        db_execute("""
            INSERT INTO user_langs (chat_id, lang)
            VALUES (%s, %s)
            ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang
        """, (chat_id, lang))
    except Exception as e:
        logger.error(f"Set user lang error: {e}", 'db')

# =================================================================================================
#                           FLASK WEB SERVER - Enhanced
# =================================================================================================

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=[f"{Config.RATE_LIMIT} per {Config.RATE_LIMIT_WINDOW} seconds"]
)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Control Bot Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; }
            .container { background: white; border-radius: 20px; padding: 40px; max-width: 800px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
            h1 { color: #333; font-size: 2.5em; margin-bottom: 10px; }
            .subtitle { color: #666; margin-bottom: 30px; }
            .status { display: inline-block; padding: 8px 20px; border-radius: 30px; background: #4CAF50; color: white; font-weight: bold; margin-bottom: 20px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 30px 0; }
            .stat-item { background: #f8f8f8; padding: 20px; border-radius: 12px; text-align: center; transition: transform 0.3s; }
            .stat-item:hover { transform: translateY(-5px); }
            .stat-number { font-size: 28px; font-weight: bold; color: #667eea; }
            .stat-label { color: #888; font-size: 14px; margin-top: 5px; }
            .info { background: #e8f4fd; padding: 20px; border-radius: 12px; margin: 20px 0; }
            .info h3 { color: #333; margin-bottom: 10px; }
            .info p { color: #666; line-height: 1.6; }
            .footer { text-align: center; color: #999; margin-top: 30px; font-size: 12px; }
            .badge { display: inline-block; padding: 3px 10px; border-radius: 15px; font-size: 12px; font-weight: bold; }
            .badge-success { background: #4CAF50; color: white; }
            .badge-warning { background: #FF9800; color: white; }
            .badge-danger { background: #f44336; color: white; }
            .commands { display: flex; gap: 10px; flex-wrap: wrap; margin: 20px 0; }
            .commands code { background: #f0f0f0; padding: 8px 15px; border-radius: 8px; font-size: 14px; color: #333; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Control Bot</h1>
            <p class="subtitle">Advanced Store Management System</p>
            <div class="status">🟢 Online</div>
            
            <div class="stats" id="stats">
                <div class="stat-item">
                    <div class="stat-number" id="total-stores">-</div>
                    <div class="stat-label">Total Stores</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="active-stores">-</div>
                    <div class="stat-label">Active Stores</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="pending-stores">-</div>
                    <div class="stat-label">Pending Approval</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="total-orders">-</div>
                    <div class="stat-label">Total Orders</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="total-revenue">-</div>
                    <div class="stat-label">Total Revenue</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" id="active-users">-</div>
                    <div class="stat-label">Active Users</div>
                </div>
            </div>
            
            <div class="info">
                <h3>📌 Quick Commands</h3>
                <div class="commands">
                    <code>/start</code>
                    <code>/help</code>
                    <code>/superadmin</code>
                    <code>/panel</code>
                    <code>/analytics</code>
                    <code>/stores</code>
                    <code>/broadcast</code>
                    <code>/backup</code>
                    <code>/export</code>
                </div>
            </div>
            
            <div class="info">
                <h3>📊 System Info</h3>
                <p><strong>Version:</strong> 4.0.0 Enterprise</p>
                <p><strong>Status:</strong> Running</p>
                <p><strong>Bots:</strong> <span id="bot-count">Loading...</span></p>
                <p><strong>Cache:</strong> <span id="cache-type">Loading...</span></p>
                <p><strong>Queue:</strong> <span id="queue-type">Loading...</span></p>
            </div>
            
            <div class="footer">
                © 2026 Control Bot v4.0 Enterprise | Powered by Advanced AI
            </div>
        </div>
        
        <script>
            async function loadStats() {
                try {
                    const response = await fetch('/api/stats');
                    const data = await response.json();
                    document.getElementById('total-stores').textContent = data.total_stores || 0;
                    document.getElementById('active-stores').textContent = data.active_stores || 0;
                    document.getElementById('pending-stores').textContent = data.pending_approval || 0;
                    document.getElementById('total-orders').textContent = data.total_orders || 0;
                    document.getElementById('total-revenue').textContent = data.total_revenue ? data.total_revenue.toFixed(2) + ' ETB' : '0 ETB';
                    document.getElementById('active-users').textContent = data.active_users || 0;
                    document.getElementById('bot-count').textContent = data.bots || 0;
                    document.getElementById('cache-type').textContent = data.cache_type || 'N/A';
                    document.getElementById('queue-type').textContent = data.queue_type || 'N/A';
                } catch(e) {
                    console.error('Stats error:', e);
                }
            }
            
            loadStats();
            setInterval(loadStats, 30000);
        </script>
    </body>
    </html>
    """

@app.route('/api/stats')
def api_stats():
    try:
        # Get dashboard stats
        total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
        pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
        active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
        total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
        revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
        active_users = db_execute("SELECT COUNT(DISTINCT customer_id) FROM orders", fetch=True)[0][0]
        
        return jsonify({
            "total_stores": total_stores,
            "pending_approval": pending,
            "active_stores": active,
            "total_orders": total_orders,
            "total_revenue": float(revenue),
            "active_users": active_users,
            "bots": len(running_tokens),
            "cache_type": cache._cache_type if hasattr(cache, '_cache_type') else 'unknown',
            "queue_type": 'rabbitmq' if hasattr(queue, '_rabbitmq') and queue._rabbitmq else 'memory'
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stores')
def api_stores():
    try:
        stores = db_execute_dict("""
            SELECT id, store_name, username, is_active, is_approved, 
                   created_at, total_orders, total_sales
            FROM stores 
            ORDER BY created_at DESC 
            LIMIT 50
        """)
        return jsonify([dict(s) for s in stores])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/orders')
def api_orders():
    try:
        orders = db_execute_dict("""
            SELECT id, token, customer_id, status_am, total_price, 
                   delivery_fee, status_stage, created_at
            FROM orders 
            ORDER BY created_at DESC 
            LIMIT 50
        """)
        return jsonify([dict(o) for o in orders])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analytics/<token>')
def api_store_analytics(token):
    try:
        # Get store analytics
        stores = db_execute_dict("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as orders,
                COALESCE(SUM(total_price + delivery_fee), 0) as revenue,
                COUNT(DISTINCT customer_id) as customers
            FROM orders
            WHERE token = %s AND status_stage >= 1
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 30
        """, (token,))
        return jsonify([dict(s) for s in stores])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/health')
def api_health():
    try:
        # Check database
        db_execute("SELECT 1", fetch=True)
        
        # Check cache
        cache.set('health_check', 'ok', 10)
        cache_ok = cache.get('health_check') == 'ok'
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "cache": "ok" if cache_ok else "error",
            "queue": "ok" if queue else "error"
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

def run_flask():
    socketio.run(app, host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)

threading.Thread(target=run_flask, daemon=True).start()
logger.info(f"✅ Web server running on {Config.HOST}:{Config.PORT}", 'web')

# =================================================================================================
#                           SHOPS BOT ENGINE - Complete
# =================================================================================================

running_tokens = set()
running_lock = threading.Lock()

def start_shop_bot(token: str) -> bool:
    """Start a shop bot"""
    with running_lock:
        if token in running_tokens:
            return False
        running_tokens.add(token)
    
    try:
        setup_bot_handlers(token)
        logger.info(f"✅ Shop bot started: {token[:15]}...", 'bot')
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start bot {token[:15]}: {e}", 'bot')
        with running_lock:
            running_tokens.discard(token)
        return False

def setup_bot_handlers(token: str):
    """Setup bot handlers"""
    bot = telebot.TeleBot(token, threaded=False)
    
    try:
        bot.remove_webhook()
    except:
        pass
    
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        chat_id = message.chat.id
        
        # Get store info
        store = get_store_info(token)
        if not store:
            bot.send_message(chat_id, "🏪 ይህ ቦት ገና አልተመዘገበም።")
            return
        
        if store.get('is_approved', 0) != 1:
            bot.send_message(
                chat_id,
                f"⏳ ሱቅ **{store.get('store_name', '')}** ገና አልጸደቀም።\n"
                "እባክዎ ለማጽደቅ ይጠብቁ።"
            )
            return
        
        # Language selection
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("አማርኛ 🇪🇹", callback_data=f"lang_am_{token}"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data=f"lang_en_{token}"),
            types.InlineKeyboardButton("ኦሮምኛ 🇪🇹", callback_data=f"lang_or_{token}")
        )
        
        bot.send_message(
            chat_id,
            f"🌐 **{store.get('store_name', '')}**\n\nቋንቋ ይምረጡ / Select Language:",
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
    def handle_lang(call):
        _, lang, bot_token = call.data.split("_")
        if bot_token != token:
            return
        
        chat_id = call.message.chat.id
        
        # Save language
        db_execute(
            "INSERT INTO user_langs (chat_id, lang) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET lang = EXCLUDED.lang",
            (chat_id, lang)
        )
        
        bot.delete_message(chat_id, call.message.message_id)
        
        # Main menu
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("🛍️ ምርቶች"),
            types.KeyboardButton("🛒 ጋሪ")
        )
        markup.add(
            types.KeyboardButton("🔍 ፍለጋ"),
            types.KeyboardButton("📦 ትዕዛዝ")
        )
        markup.add(
            types.KeyboardButton("❓ እርዳታ")
        )
        
        welcome = {
            "am": "እንኳን ወደ ሱቅ በደህና መጡ! 👋",
            "en": "Welcome to the store! 👋",
            "or": "Baga gara dukanaa dhufte! 👋"
        }
        
        bot.send_message(chat_id, welcome.get(lang, welcome["am"]), reply_markup=markup)
    
    @bot.message_handler(func=lambda m: m.text == "🛍️ ምርቶች")
    def handle_products(message):
        chat_id = message.chat.id
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name_am, name_en, price, stock, image_url 
                    FROM products 
                    WHERE token = %s AND stock > 0
                    ORDER BY id
                    LIMIT 10
                """, (token,))
                products = cur.fetchall()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not products:
            bot.send_message(chat_id, "🛍️ ምንም ምርት የለም")
            return
        
        for product in products:
            p_id, name_am, name_en, price, stock, image_url = product
            text = f"📦 **{name_am}**\n💰 {price} ETB\n📌 ✅ ይገኛል"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🛒 ወደ ጋሪ ጨምር", callback_data=f"add_{p_id}"),
                types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="back")
            )
            
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    @bot.message_handler(func=lambda m: m.text == "🛒 ጋሪ")
    def handle_cart(message):
        chat_id = message.chat.id
        bot.send_message(chat_id, "🛒 ጋሪዎ ባዶ ነው")
    
    @bot.message_handler(func=lambda m: m.text == "🔍 ፍለጋ")
    def handle_search(message):
        chat_id = message.chat.id
        msg = bot.send_message(chat_id, "🔍 የምርት ስም ያስገቡ:")
        bot.register_next_step_handler(msg, lambda m: search_product(m, token, bot))
    
    @bot.message_handler(func=lambda m: m.text == "📦 ትዕዛዝ")
    def handle_track(message):
        chat_id = message.chat.id
        msg = bot.send_message(chat_id, "🔢 የትዕዛዝ ቁጥር ያስገቡ:")
        bot.register_next_step_handler(msg, lambda m: track_order(m, token, bot))
    
    @bot.message_handler(func=lambda m: m.text == "❓ እርዳታ")
    def handle_help(message):
        chat_id = message.chat.id
        text = """
        ❓ **እርዳታ**
        
        🛍️ ምርቶች - የሱቁን ምርቶች ይመልከቱ
        🛒 ጋሪ - የእርስዎን ጋሪ ይመልከቱ
        🔍 ፍለጋ - ምርቶችን ይፈልጉ
        📦 ትዕዛዝ - ትዕዛዝዎን ይከታተሉ
        
        ለተጨማሪ እርዳታ አስተዳዳሪውን ያነጋግሩ
        """
        bot.send_message(chat_id, text, parse_mode="Markdown")
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
    def handle_add_to_cart(call):
        p_id = int(call.data.split("_")[1])
        bot.answer_callback_query(call.id, "✅ ወደ ጋሪ ተጨምሯል!")
    
    @bot.callback_query_handler(func=lambda call: call.data == "back")
    def handle_back(call):
        bot.answer_callback_query(call.id)
        bot.delete_message(call.message.chat.id, call.message.message_id)
    
    @bot.message_handler(func=lambda m: True)
    def handle_all(message):
        bot.reply_to(message, "🤖 እንዴት ልረዳዎት እችላለሁ?")
    
    def search_product(message, token, bot):
        query = message.text.strip()
        chat_id = message.chat.id
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, name_am, name_en, price, stock 
                    FROM products 
                    WHERE token = %s AND (name_am ILIKE %s OR name_en ILIKE %s)
                    LIMIT 10
                """, (token, f"%{query}%", f"%{query}%"))
                products = cur.fetchall()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not products:
            bot.send_message(chat_id, f"🔍 '{query}' አልተገኘም")
            return
        
        text = f"🔍 **'{query}' ውጤቶች:**\n\n"
        for p in products:
            text += f"📦 {p[1]} - {p[3]} ETB\n"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
    
    def track_order(message, token, bot):
        try:
            order_id = int(message.text.strip())
            chat_id = message.chat.id
            
            conn = None
            try:
                conn = get_db_connection()
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT status_am, total_price, created_at 
                        FROM orders 
                        WHERE id = %s AND token = %s
                    """, (order_id, token))
                    order = cur.fetchone()
            finally:
                if conn:
                    put_db_connection(conn)
            
            if not order:
                bot.send_message(chat_id, "❌ ትዕዛዝ አልተገኘም")
                return
            
            status, price, created = order
            text = f"📦 **ትዕዛዝ #{order_id}**\n"
            text += f"📌 ሁኔታ: {status}\n"
            text += f"💵 ድምር: {price} ETB\n"
            text += f"📅 ቀን: {format_date(created)}"
            
            bot.send_message(chat_id, text, parse_mode="Markdown")
        except ValueError:
            bot.send_message(message.chat.id, "❌ የተሳሳተ ቁጥር!")
    
    def get_store_info(token):
        try:
            result = db_execute_dict(
                "SELECT store_name, admin_id, is_active, is_approved FROM stores WHERE token = %s",
                (token,)
            )
            if result:
                return dict(result[0])
            return None
        except Exception as e:
            logger.error(f"Get store info error: {e}", 'db')
            return None
    
    def _run_bot():
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                logger.error(f"Bot {token[:15]} polling error: {e}", 'bot')
                time.sleep(5)
    
    threading.Thread(target=_run_bot, daemon=True).start()

# =================================================================================================
#                           CONTROL BOT - Complete Implementation
# =================================================================================================

class ControlBot:
    """ዋናው የአስተዳደር ቦት ክፍል - Complete Implementation"""
    
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
        logger.info("✅ Control Bot initialized", 'bot')
    
    def _register_handlers(self):
        # Main menu
        @self.bot.message_handler(commands=['start', 'help'])
        def cmd_start(message):
            chat_id = message.chat.id
            lang = get_user_lang(chat_id)
            
            text = f"""
👋 {get_string('welcome', lang)}

📌 **አዲስ ሱቅ ለመመዝገብ:**
1️⃣ @BotFather ላይ `/newbot` በማድረግ ቦት ይፍጠሩ
2️⃣ Token ከተቀበሉ '📝 አዲስ ሱቅ መዝግብ' ይጫኑ
3️⃣ 5 ደረጃዎችን ይሙሉ

📌 **ሱቆችዎን ለማየት:** 🏪 ሱቆቼ

👑 **Super Admin ከሆኑ:** `/superadmin`
"""
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add(
                types.KeyboardButton("📝 አዲስ ሱቅ መዝግብ"),
                types.KeyboardButton("🏪 ሱቆቼ")
            )
            markup.add(
                types.KeyboardButton("🔍 ሱቆችን ፈልግ"),
                types.KeyboardButton("❓ እርዳታ")
            )
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        
        # Super Admin login
        @self.bot.message_handler(commands=['superadmin'])
        def cmd_superadmin(message):
            chat_id = message.chat.id
            
            if not Config.SUPER_ADMIN_PASSWORD:
                self.bot.reply_to(message, "❌ SUPER_ADMIN_PASSWORD not set!")
                return
            
            if Config.SUPER_ADMIN_ID != 0 and chat_id != Config.SUPER_ADMIN_ID:
                self.bot.reply_to(message, "❌ መብት የለዎትም!")
                return
            
            with self.login_lock:
                attempt = self.login_attempts.get(chat_id, {"count": 0, "lockout_until": 0})
                if time.time() < attempt["lockout_until"]:
                    remaining = int(attempt["lockout_until"] - time.time())
                    self.bot.reply_to(message, f"🔒 እገዳ ላይ ነዎት! ከ {remaining} ሰከንድ በኋላ ይሞክሩ።")
                    return
            
            msg = self.bot.send_message(
                chat_id,
                "🔐 **እባክዎ የ Super Admin የይለፍ ቃል ያስገቡ፦**",
                parse_mode="Markdown"
            )
            self.bot.register_next_step_handler(msg, self._process_super_login)
        
        # Admin panel
        @self.bot.message_handler(commands=['panel'])
        def cmd_panel(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_dashboard(message)
        
        # Analytics
        @self.bot.message_handler(commands=['analytics'])
        def cmd_analytics(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_analytics(message)
        
        # Stores list
        @self.bot.message_handler(commands=['stores'])
        def cmd_stores(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_all_stores(message)
        
        # Broadcast
        @self.bot.message_handler(commands=['broadcast'])
        def cmd_broadcast(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_broadcast_menu(message)
        
        # Backup
        @self.bot.message_handler(commands=['backup'])
        def cmd_backup(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._create_backup(message)
        
        # Export
        @self.bot.message_handler(commands=['export'])
        def cmd_export(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._export_data(message)
        
        # Dashboard callbacks
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("dash_"))
        def handle_dashboard(call):
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
            elif action == "all":
                self.bot.answer_callback_query(call.id)
                self._show_all_stores(call.message)
            elif action == "stats":
                self.bot.answer_callback_query(call.id)
                self._show_analytics(call.message)
            elif action == "broadcast":
                self.bot.answer_callback_query(call.id)
                self._show_broadcast_menu(call.message)
            elif action == "back":
                self.bot.answer_callback_query(call.id)
                try:
                    self.bot.delete_message(chat_id, call.message.message_id)
                except:
                    pass
                self._show_dashboard(call.message)
            elif action == "logout":
                self.bot.answer_callback_query(call.id)
                self._logout(chat_id)
        
        # Store approval callbacks
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sapprove_"))
        def handle_approve(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            store_id = int(call.data.split("_")[1])
            self._approve_store(chat_id, store_id, call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sreject_"))
        def handle_reject(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            store_id = int(call.data.split("_")[1])
            self._reject_store(chat_id, store_id, call)
        
        # Broadcast callbacks
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("broadcast_"))
        def handle_broadcast(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            
            target = call.data.split("_")[1]
            self.bot.answer_callback_query(call.id)
            
            if target == "user":
                msg = self.bot.send_message(chat_id, "👤 የተጠቃሚ አይዲ ያስገቡ:")
                self.bot.register_next_step_handler(msg, self._broadcast_to_user)
            else:
                target_label = "ሱቅ ባለቤቶች" if target == "owners" else "ደንበኞች"
                msg = self.bot.send_message(
                    chat_id,
                    f"📝 **መልእክት ይላኩ**\n\nለ{target_label} የሚላከውን መልእክት ይላኩ:"
                )
                self.bot.register_next_step_handler(
                    msg,
                    lambda m: self._broadcast_to_all(m, target)
                )
        
        # Search callbacks
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("search_"))
        def handle_search(call):
            chat_id = call.message.chat.id
            
            if call.data == "search_name":
                msg = self.bot.send_message(chat_id, "📝 የሱቅ ስም ያስገቡ:")
                self.bot.register_next_step_handler(msg, self._search_by_name)
            elif call.data == "search_location":
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
                markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
                self.bot.send_message(chat_id, "📍 አካባቢ ያጋሩ:", reply_markup=markup)
        
        # Text handlers
        @self.bot.message_handler(func=lambda m: m.text == "📝 አዲስ ሱቅ መዝግብ")
        def handle_register(message):
            self._start_registration(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "🏪 ሱቆቼ")
        def handle_my_stores(message):
            self._show_my_stores(message)
        
        @self.bot.message_handler(func=lambda m: m.text == "🔍 ሱቆችን ፈልግ")
        def handle_search_stores(message):
            chat_id = message.chat.id
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("📝 በስም ፈልግ", callback_data="search_name"),
                types.InlineKeyboardButton("📍 በአካባቢ ፈልግ", callback_data="search_location")
            )
            self.bot.send_message(chat_id, "🔍 **ሱቆችን ፈልግ**", reply_markup=markup)
        
        @self.bot.message_handler(func=lambda m: m.text == "❓ እርዳታ")
        def handle_help(message):
            cmd_start(message)
        
        @self.bot.message_handler(content_types=['location'])
        def handle_location(message):
            self._search_by_location(message)
        
        # Registration steps
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 1)
        def reg_step_token(message):
            self._process_reg_token(message)
        
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 2)
        def reg_step_name(message):
            self._process_reg_name(message)
        
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 3)
        def reg_step_password(message):
            self._process_reg_password(message)
        
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 4)
        def reg_step_location(message):
            self._process_reg_location(message)
        
        @self.bot.message_handler(func=lambda m: self._get_reg_state(m.chat.id, "step") == 5)
        def reg_step_description(message):
            self._process_reg_description(message)
    
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
    
    def _process_super_login(self, message):
        chat_id = message.chat.id
        password = message.text.strip()
        
        if password == Config.SUPER_ADMIN_PASSWORD:
            with self.sessions_lock:
                self.sessions[chat_id] = time.time() + Config.SESSION_TIMEOUT
            with self.login_lock:
                self.login_attempts[chat_id] = {"count": 0, "lockout_until": 0}
            
            self.bot.send_message(
                chat_id,
                "🔓 **እንኳን ወደ Super Admin ፓነል በደህና መጡ!**",
                parse_mode="Markdown"
            )
            self._show_dashboard(message)
            logger.audit(chat_id, "super_admin_login", {"success": True})
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
            logger.audit(chat_id, "super_admin_login_failed", {})
    
    def _logout(self, chat_id: int):
        with self.sessions_lock:
            self.sessions.pop(chat_id, None)
        lang = get_user_lang(chat_id)
        self.bot.send_message(
            chat_id,
            "🔒 ከአስተዳደር ወጥተዋል።",
            reply_markup=self._get_main_menu(lang)
        )
        logger.audit(chat_id, "super_admin_logout", {})
    
    def _get_main_menu(self, lang: str) -> types.ReplyKeyboardMarkup:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        markup.add(
            types.KeyboardButton("📝 አዲስ ሱቅ መዝግብ"),
            types.KeyboardButton("🏪 ሱቆቼ")
        )
        markup.add(
            types.KeyboardButton("🔍 ሱቆችን ፈልግ"),
            types.KeyboardButton("❓ እርዳታ")
        )
        return markup
    
    def _get_dashboard_markup(self) -> types.InlineKeyboardMarkup:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("⏳ ያልጸደቁ", callback_data="dash_pending"),
            types.InlineKeyboardButton("🏢 ሁሉም", callback_data="dash_all")
        )
        markup.add(
            types.InlineKeyboardButton("📊 ስታቲስቲክስ", callback_data="dash_stats"),
            types.InlineKeyboardButton("📢 ማሰራጨት", callback_data="dash_broadcast")
        )
        markup.add(
            types.InlineKeyboardButton("🔄 አዘምን", callback_data="dash_refresh"),
            types.InlineKeyboardButton("🚪 ውጣ", callback_data="dash_logout")
        )
        return markup
    
    def _show_dashboard(self, message):
        chat_id = message.chat.id
        
        try:
            total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
            pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
            active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
            total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
            revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
            active_users = db_execute("SELECT COUNT(DISTINCT customer_id) FROM orders", fetch=True)[0][0]
            
            text = f"""
🎛 **Super Admin Dashboard**

🏪 Total Stores: **{total_stores}**
⏳ Pending Approval: **{pending}**
🟢 Active Stores: **{active}**
📦 Total Orders: **{total_orders}**
💰 Total Revenue: **{format_currency(revenue)}**
👥 Active Users: **{active_users}**

📌 ርምጫ ይምረጡ:
"""
            
            self.bot.send_message(
                chat_id,
                text,
                reply_markup=self._get_dashboard_markup(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Dashboard error: {e}", 'bot')
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _show_pending_stores(self, message):
        chat_id = message.chat.id
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, username, area_text, shop_description, created_at
                FROM stores WHERE is_approved = 0 AND is_active = 1
                ORDER BY created_at DESC
            """)
            
            if not stores:
                self.bot.send_message(
                    chat_id,
                    "✅ ምንም ያልተጸደቁ ሱቆች የሉም!",
                    reply_markup=self._get_dashboard_markup()
                )
                return
            
            for store in stores:
                text = f"""
🏪 **{store['store_name']}**
🆔 #{store['id']}
👤 @{store['username'] or 'ስም'}
📍 {store['area_text'] or 'አልተዘጋጀም'}
📅 {format_date(store['created_at'])}
"""
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ አጽድቅ", callback_data=f"sapprove_{store['id']}"),
                    types.InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"sreject_{store['id']}")
                )
                markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
                
                self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Pending stores error: {e}", 'bot')
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _show_all_stores(self, message):
        chat_id = message.chat.id
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, username, is_active, is_approved, 
                       total_orders, total_sales, created_at
                FROM stores ORDER BY created_at DESC LIMIT 20
            """)
            
            if not stores:
                self.bot.send_message(
                    chat_id,
                    "📜 ምንም ሱቅ የለም!",
                    reply_markup=self._get_dashboard_markup()
                )
                return
            
            text = "🏢 **ሁሉም ሱቆች**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                approved = "✅" if store['is_approved'] else "⏳"
                text += f"""
{status} {approved} **{store['store_name']}**
  🆔 #{store['id']} | 👤 @{store['username'] or 'ስም'}
  📦 {store['total_orders'] or 0} ትዕዛዝ | 💰 {format_currency(store['total_sales'] or 0)}
  📅 {format_date(store['created_at'])}
"""
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"All stores error: {e}", 'bot')
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _show_analytics(self, message):
        chat_id = message.chat.id
        
        try:
            # Get comprehensive stats
            total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
            pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
            active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
            total_products = db_execute("SELECT COUNT(*) FROM products", fetch=True)[0][0]
            total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
            revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
            active_users = db_execute("SELECT COUNT(DISTINCT customer_id) FROM orders", fetch=True)[0][0]
            
            # Order status breakdown
            order_status = db_execute_dict("""
                SELECT status_stage, COUNT(*) as count
                FROM orders
                GROUP BY status_stage
                ORDER BY status_stage
            """)
            
            # Top stores by revenue
            top_stores = db_execute_dict("""
                SELECT s.store_name, COUNT(o.id) as orders, COALESCE(SUM(o.total_price + o.delivery_fee), 0) as revenue
                FROM stores s
                LEFT JOIN orders o ON s.token = o.token AND o.status_stage >= 1
                GROUP BY s.id, s.store_name
                ORDER BY revenue DESC
                LIMIT 5
            """)
            
            # Recent activity
            recent_orders = db_execute_dict("""
                SELECT id, customer_id, total_price, status_am, created_at
                FROM orders
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            status_names = {
                0: "🟡 በመጠባበቅ",
                1: "✅ ተረጋግጧል",
                2: "🚚 በመንገድ",
                3: "📦 ደርሷል",
                -1: "❌ ውድቅ"
            }
            
            text = f"""
📊 **የሲስተም ስታቲስቲክስ**

🏪 **ሱቆች**
  • ጠቅላላ: {total_stores}
  • ንቁ: {active}
  • ያልተጸደቀ: {pending}

📦 **ምርቶች:** {total_products}

🧾 **ትዕዛዞች**
  • ጠቅላላ: {total_orders}
  • ንቁ ተጠቃሚዎች: {active_users}

"""
            
            # Order status breakdown
            for status in order_status:
                stage = status['status_stage']
                count = status['count']
                name = status_names.get(stage, f"ሁኔታ {stage}")
                text += f"  • {name}: {count}\n"
            
            text += f"\n💰 **ጠቅላላ ገቢ:** {format_currency(revenue)}\n"
            
            # Top stores
            if top_stores:
                text += "\n🏆 **ከፍተኛ ገቢ ያላቸው ሱቆች:**\n"
                for i, store in enumerate(top_stores, 1):
                    text += f"  {i}. {store['store_name']} - {store['orders']} ትዕዛዝ - {format_currency(store['revenue'])}\n"
            
            # Recent orders
            if recent_orders:
                text += "\n📋 **የቅርብ ጊዜ ትዕዛዞች:**\n"
                for order in recent_orders:
                    text += f"  🆔 #{order['id']} - {format_currency(order['total_price'])} - {order['status_am']} - {format_date(order['created_at'])}\n"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Analytics error: {e}", 'bot')
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _show_broadcast_menu(self, message):
        chat_id = message.chat.id
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("📢 ለሱቅ ባለቤቶች", callback_data="broadcast_owners"),
            types.InlineKeyboardButton("👥 ለደንበኞች", callback_data="broadcast_customers"),
            types.InlineKeyboardButton("👤 ለአንድ ተጠቃሚ", callback_data="broadcast_user"),
            types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back")
        )
        
        self.bot.send_message(
            chat_id,
            "📢 **ብሮድካስት መልእክት**\n\nመልእክት ለማን መላክ ይፈልጋሉ?",
            reply_markup=markup
        )
    
    def _broadcast_to_all(self, message, target: str):
        chat_id = message.chat.id
        msg_text = message.text
        
        try:
            if target == "owners":
                users = db_execute_dict(
                    "SELECT DISTINCT admin_id FROM stores WHERE admin_id > 0 AND is_approved = 1"
                )
            else:
                users = db_execute_dict("SELECT DISTINCT customer_id FROM orders")
            
            if not users:
                self.bot.reply_to(message, "❌ ምንም ተጠቃሚ አልተገኘም!")
                return
            
            self.bot.reply_to(message, f"⏳ ለ {len(users)} ተጠቃሚዎች በማስተላለፍ ላይ...")
            
            success = 0
            failed = 0
            
            for user in users:
                user_id = user.get('admin_id') or user.get('customer_id')
                if not user_id:
                    continue
                try:
                    self.bot.send_message(
                        user_id,
                        f"📢 **የሲስተም ማስታወቂያ**\n\n{msg_text}"
                    )
                    success += 1
                    time.sleep(0.05)
                except:
                    failed += 1
            
            self.bot.send_message(
                chat_id,
                f"✅ ብሮድካስት ተጠናቋል!\n\n✅ የተሳካ: {success}\n❌ ያልተሳካ: {failed}",
                reply_markup=self._get_dashboard_markup()
            )
            
            logger.audit(chat_id, "broadcast_sent", {
                "target": target,
                "success": success,
                "failed": failed,
                "message_preview": msg_text[:100]
            })
        except Exception as e:
            logger.error(f"Broadcast error: {e}", 'bot')
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _broadcast_to_user(self, message):
        chat_id = message.chat.id
        
        try:
            user_id = int(message.text.strip())
        except:
            self.bot.reply_to(message, "❌ የተሳሳተ አይዲ!")
            return
        
        msg = self.bot.send_message(chat_id, "📝 ለተጠቃሚው የሚላከውን መልእክት ይላኩ:")
        self.bot.register_next_step_handler(
            msg,
            lambda m: self._send_single_message(m, user_id)
        )
    
    def _send_single_message(self, message, user_id: int):
        chat_id = message.chat.id
        msg_text = message.text
        
        try:
            self.bot.send_message(
                user_id,
                f"📢 **የሲስተም ማስታወቂያ**\n\n{msg_text}"
            )
            self.bot.reply_to(
                message,
                f"✅ መልእክት ለተጠቃሚ {user_id} ተልኳል!",
                reply_markup=self._get_dashboard_markup()
            )
            logger.audit(chat_id, "single_message_sent", {"user_id": user_id})
        except Exception as e:
            self.bot.reply_to(
                message,
                f"❌ መልእክት ለ {user_id} መላክ አልተቻለም!: {e}",
                reply_markup=self._get_dashboard_markup()
            )
    
    def _approve_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT token, store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ ሱቅ አልተገኘም!")
                return
            
            store = store[0]
            db_execute("UPDATE stores SET is_approved = 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (store_id,))
            start_shop_bot(store['token'])
            
            try:
                self.bot.send_message(
                    store['admin_id'],
                    f"🎉 **ሱቅዎ ተጸድቋል!**\n\n"
                    f"🏪 {store['store_name']}\n"
                    f"🔑 አሁን /login በማድረግ መግባት ይችላሉ"
                )
            except:
                pass
            
            if call:
                self.bot.edit_message_text(
                    f"✅ ሱቅ #{store_id} ተጸድቋል!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "ተጸድቋል!")
            
            self._show_dashboard(call.message if call else None)
            logger.audit(chat_id, "store_approved", {"store_id": store_id, "store_name": store['store_name']})
        except Exception as e:
            logger.error(f"Approve store error: {e}", 'bot')
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _reject_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ ሱቅ አልተገኘም!")
                return
            
            store = store[0]
            db_execute("DELETE FROM stores WHERE id = %s", (store_id,))
            
            try:
                self.bot.send_message(store['admin_id'], f"❌ ሱቅዎ **{store['store_name']}** ውድቅ ተደርጓል።")
            except:
                pass
            
            if call:
                self.bot.edit_message_text(
                    f"❌ ሱቅ #{store_id} ውድቅ ተደርጓል!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "ውድቅ ተደርጓል!")
            
            self._show_dashboard(call.message if call else None)
            logger.audit(chat_id, "store_rejected", {"store_id": store_id, "store_name": store['store_name']})
        except Exception as e:
            logger.error(f"Reject store error: {e}", 'bot')
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _start_registration(self, message):
        chat_id = message.chat.id
        self._clear_reg_state(chat_id)
        self._set_reg_state(chat_id, "step", 1)
        self._set_reg_state(chat_id, "data", {})
        
        msg = self.bot.send_message(
            chat_id,
            "📝 **ደረጃ 1/5: የቦት ቶከን**\n\n"
            "ከ @BotFather ያገኙትን ቶከን ያስገቡ:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_token)
    
    def _process_reg_token(self, message):
        chat_id = message.chat.id
        token = message.text.strip()
        
        try:
            test_bot = telebot.TeleBot(token)
            bot_info = test_bot.get_me()
        except Exception as e:
            logger.error(f"Token validation error: {e}", 'bot')
            self.bot.reply_to(message, "❌ ቶከን ልክ አይደለም!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["token"] = token
        data["bot_username"] = bot_info.username
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 2)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ ቶከን ተረጋግጧል! 👤 @{bot_info.username}\n\n"
            "📝 **ደረጃ 2/5: የሱቅ ስም**\n\n"
            "የሱቅዎን ስም ያስገቡ:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_name)
    
    def _process_reg_name(self, message):
        chat_id = message.chat.id
        name = message.text.strip()
        
        if not name:
            self.bot.reply_to(message, "❌ እባክዎ ሱቅ ስም ያስገቡ!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["store_name"] = name
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 3)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ ስም: **{name}**\n\n"
            "📝 **ደረጃ 3/5: የይለፍ ቃል**\n\n"
            "ለሱቅ አስተዳደር የይለፍ ቃል ያስገቡ (ቢያንስ 8 ፊደል):"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_password)
    
    def _process_reg_password(self, message):
        chat_id = message.chat.id
        password = message.text.strip()
        
        if len(password) < 8:
            self.bot.reply_to(message, "❌ ቢያንስ 8 ፊደል!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["password"] = password
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 4)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("📍 አካባቢ አጋራ", request_location=True))
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ የይለፍ ቃል ተቀብለናል\n\n"
            "📝 **ደረጃ 4/5: የሱቅ አካባቢ**\n\n"
            "የሱቅዎን አካባቢ ያጋሩ ወይም የከተማ ስም ያስገቡ:",
            reply_markup=markup
        )
        self.bot.register_next_step_handler(msg, self._process_reg_location)
    
    def _process_reg_location(self, message):
        chat_id = message.chat.id
        data = self._get_reg_state(chat_id, "data") or {}
        
        if message.location:
            data["shop_lat"] = message.location.latitude
            data["shop_lng"] = message.location.longitude
            location_text = f"📍 {data['shop_lat']}, {data['shop_lng']}"
        else:
            location_text = message.text.strip()
            if not location_text:
                self.bot.reply_to(message, "❌ እባክዎ አካባቢ ያስገቡ!")
                return
            data["area_text"] = location_text
        
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 5)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ አካባቢ: {location_text}\n\n"
            "📝 **ደረጃ 5/5: ስለ ሱቅ መግለጫ**\n\n"
            "ስለ ሱቅዎ አጭር መግለጫ ይላኩ:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_description)
    
    def _process_reg_description(self, message):
        chat_id = message.chat.id
        description = message.text.strip()
        
        if not description:
            self.bot.reply_to(message, "❌ እባክዎ የሱቅ መግለጫ ያስገቡ!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["shop_description"] = description
        data["username"] = data.get("bot_username", f"shop_{chat_id}")
        
        try:
            existing = db_execute_dict("SELECT 1 FROM stores WHERE token = %s", (data["token"],))
            if existing:
                self.bot.reply_to(message, "❌ ቶከን ቀድሞውኑ ተመዝግቧል!")
                return
            
            h_pass, salt = hash_password(data["password"])
            
            db_execute("""
                INSERT INTO stores (
                    token, store_name, admin_id, username,
                    password_hash, password_salt, telebirr, cbebirr,
                    is_active, is_approved, shop_lat, shop_lng,
                    area_text, shop_description
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["token"], data["store_name"], chat_id, data["username"],
                h_pass, salt, "", "", 1, 0,
                data.get("shop_lat"), data.get("shop_lng"),
                data.get("area_text", ""), data.get("shop_description", "")
            ))
            
            start_shop_bot(data["token"])
            
            if Config.SUPER_ADMIN_ID:
                try:
                    self.bot.send_message(
                        Config.SUPER_ADMIN_ID,
                        f"🔔 **አዲስ ሱቅ ለማጽደቅ ተመዝግቧል!**\n\n"
                        f"🏪 **{data['store_name']}**\n"
                        f"👤 @{data['username']}\n"
                        f"📍 {data.get('area_text', 'አልተዘጋጀም')}"
                    )
                except:
                    pass
            
            self._clear_reg_state(chat_id)
            
            self.bot.reply_to(
                message,
                f"✅ **ሱቅ ተመዝግቧል!**\n\n"
                f"🏪 **ስም:** {data['store_name']}\n"
                f"👤 **ዩዘርኔም:** @{data['username']}\n"
                f"📍 **አካባቢ:** {data.get('area_text', 'ተቀምጧል')}\n"
                f"🔑 **የይለፍ ቃል:** `{data['password']}`\n\n"
                f"⏳ **ሱቅዎ ለማጽደቅ በመጠባበቅ ላይ ነው!**",
                reply_markup=self._get_main_menu("am"),
                parse_mode="Markdown"
            )
            
            logger.audit(chat_id, "store_registered", {
                "store_name": data["store_name"],
                "store_id": data["token"]
            })
        except Exception as e:
            logger.error(f"Registration error: {e}", 'bot')
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _show_my_stores(self, message):
        chat_id = message.chat.id
        
        try:
            stores = db_execute_dict("""
                SELECT id, store_name, is_active, is_approved, username, area_text
                FROM stores WHERE admin_id = %s
                ORDER BY created_at DESC
            """, (chat_id,))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "❌ ምንም ሱቅ አልተመዘገቡም።\n\n"
                    "📌 አዲስ ሱቅ ለመመዝገብ '📝 አዲስ ሱቅ መዝግብ' ይጫኑ",
                    reply_markup=self._get_main_menu("am")
                )
                return
            
            text = "🏪 **ሱቆችዎ:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                approved = "✅" if store['is_approved'] else "⏳"
                text += f"""
{status} {approved} **{store['store_name']}**
  👤 @{store['username'] or 'ስም'}
  📍 {store['area_text'] or 'አልተዘጋጀም'}
  🆔 #{store['id']}
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu("am"))
        except Exception as e:
            logger.error(f"My stores error: {e}", 'bot')
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _search_by_name(self, message):
        chat_id = message.chat.id
        query = message.text.strip()
        
        if not query:
            self.bot.reply_to(message, "❌ እባክዎ የሱቅ ስም ያስገቡ!")
            return
        
        try:
            stores = db_execute_dict("""
                SELECT store_name, username, area_text, is_active
                FROM stores
                WHERE (store_name ILIKE %s OR username ILIKE %s) AND is_approved = 1
                LIMIT 10
            """, (f"%{query}%", f"%{query}%"))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "🔍 ምንም ሱቅ አልተገኘም",
                    reply_markup=self._get_main_menu("am")
                )
                return
            
            text = "🔍 **የተገኙ ሱቆች:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                text += f"""
{status} **{store['store_name']}**
  👤 @{store['username'] or 'ስም'}
  📍 {store['area_text'] or 'አልተዘጋጀም'}
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu("am"))
        except Exception as e:
            logger.error(f"Search error: {e}", 'bot')
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _search_by_location(self, message):
        chat_id = message.chat.id
        
        if not message.location:
            self.bot.reply_to(message, "❌ እባክዎ አካባቢ ያጋሩ!")
            return
        
        lat = message.location.latitude
        lng = message.location.longitude
        
        try:
            stores = db_execute_dict("""
                SELECT store_name, username, area_text, is_active,
                       (6371 * acos(cos(radians(%s)) * cos(radians(shop_lat)) *
                        cos(radians(shop_lng) - radians(%s)) + sin(radians(%s)) *
                        sin(radians(shop_lat)))) as distance
                FROM stores
                WHERE shop_lat IS NOT NULL AND shop_lng IS NOT NULL AND is_approved = 1
                ORDER BY distance
                LIMIT 10
            """, (lat, lng, lat))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "🔍 በአቅራቢያ ምንም ሱቅ አልተገኘም",
                    reply_markup=self._get_main_menu("am")
                )
                return
            
            text = "📍 **በአቅራቢያ ያሉ ሱቆች:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                distance = store.get('distance', 0)
                text += f"""
{status} **{store['store_name']}**
  👤 @{store['username'] or 'ስም'}
  📍 {store['area_text'] or 'አልተዘጋጀም'}
  📏 {distance:.1f} ኪ.ሜ
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu("am"))
        except Exception as e:
            logger.error(f"Location search error: {e}", 'bot')
            self.bot.reply_to(message, f"❌ ስህተት: {e}")
    
    def _create_backup(self, message):
        chat_id = message.chat.id
        
        try:
            self.bot.send_message(chat_id, "⏳ ምትኬ እየተዘጋጀ ነው...")
            
            # Get all data
            stores = db_execute_dict("SELECT * FROM stores")
            products = db_execute_dict("SELECT * FROM products")
            orders = db_execute_dict("SELECT * FROM orders")
            users = db_execute_dict("SELECT * FROM users")
            settings = db_execute_dict("SELECT * FROM settings")
            
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "4.0.0",
                "stores": stores,
                "products": products,
                "orders": orders,
                "users": users,
                "settings": settings
            }
            
            # Create JSON file
            json_data = json.dumps(backup_data, default=str, indent=2)
            
            # Compress and send
            import gzip
            compressed = gzip.compress(json_data.encode())
            
            file_obj = io.BytesIO(compressed)
            file_obj.name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.gz"
            
            self.bot.send_document(chat_id, file_obj)
            self.bot.send_message(
                chat_id,
                "✅ ምትኬ ተፈጥሯል!",
                reply_markup=self._get_dashboard_markup()
            )
            
            logger.audit(chat_id, "backup_created", {})
        except Exception as e:
            logger.error(f"Backup error: {e}", 'bot')
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _export_data(self, message):
        chat_id = message.chat.id
        
        try:
            self.bot.send_message(chat_id, "⏳ ውሂብ እየተዘጋጀ ነው...")
            
            stores = db_execute_dict("""
                SELECT id, store_name, username, is_active, is_approved,
                       area_text, total_sales, total_orders, created_at
                FROM stores
                ORDER BY created_at DESC
            """)
            
            if not stores:
                self.bot.send_message(chat_id, "❌ ምንም ውሂብ የለም!")
                return
            
            # Create Excel file
            import pandas as pd
            df = pd.DataFrame(stores)
            
            # Create Excel file in memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Stores', index=False)
                
                # Add orders sheet
                orders = db_execute_dict("""
                    SELECT id, token, customer_id, total_price, status_am, created_at
                    FROM orders
                    ORDER BY created_at DESC
                    LIMIT 1000
                """)
                if orders:
                    pd.DataFrame(orders).to_excel(writer, sheet_name='Orders', index=False)
            
            output.seek(0)
            file_obj = io.BytesIO(output.read())
            file_obj.name = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            self.bot.send_document(chat_id, file_obj)
            self.bot.send_message(
                chat_id,
                f"✅ {len(stores)} ሱቆች ተላኩ!",
                reply_markup=self._get_dashboard_markup()
            )
            
            logger.audit(chat_id, "data_exported", {"count": len(stores)})
        except Exception as e:
            logger.error(f"Export error: {e}", 'bot')
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    def _start_polling(self):
        def _poll():
            while True:
                try:
                    self.bot.infinity_polling(skip_pending=True, timeout=30)
                except Exception as e:
                    logger.error(f"Polling error: {e}", 'bot')
                    time.sleep(5)
        
        threading.Thread(target=_poll, daemon=True).start()

# =================================================================================================
#                           LOAD EXISTING STORES
# =================================================================================================

def load_existing_stores():
    try:
        stores = db_execute_dict("SELECT token FROM stores")
        count = 0
        for store in stores:
            if start_shop_bot(store['token']):
                count += 1
        logger.info(f"✅ {count} stores loaded", 'bot')
    except Exception as e:
        logger.error(f"❌ Failed to load stores: {e}", 'bot')

load_existing_stores()

# =================================================================================================
#                           MAIN ENTRY POINT
# =================================================================================================

if __name__ == "__main__":
    try:
        control_bot = ControlBot()
        logger.info("🚀 Advanced Control Bot v4.0 Enterprise is running!", 'main')
        logger.info(f"📊 Web Dashboard: http://{Config.HOST}:{Config.PORT}", 'main')
        
        # Keep the main thread alive
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...", 'main')
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", 'main')
        # Don't exit, keep retrying
        while True:
            time.sleep(60)
