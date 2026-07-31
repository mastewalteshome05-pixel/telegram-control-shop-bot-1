
💡 እባክዎ እንደገና ይሞክሩ ወይም ድጋፍ ያነጋግሩ
""",
                parse_mode="Markdown"
            )
            
            logger.audit(chat_id, "payment_failed", {"order_id": order_id, "reason": details[:200]})
    
    # ============================================================
    # SMART SEARCH (AI-Powered)
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == "🔍 ፍለጋ")
    def handle_search(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        msg = bot.send_message(
            chat_id,
            "🔍 **የምርት ፍለጋ**\n\n"
            "📝 በስም ወይም በተፈጥሮ ቋንቋ መፈለግ ይችላሉ\n\n"
            "ለምሳሌ:\n"
            "- \"ስልክ አሳየኝ\"\n"
            "- \"10,000 ብር በታች ጫማ\"\n"
            "- \"የተፈጥሮ መዋቢያዎች\"",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_search)
    
    def process_search(message):
        chat_id = message.chat.id
        query = message.text.strip()
        lang = get_user_lang(chat_id)
        
        if not query:
            bot.send_message(chat_id, "❌ እባክዎ ፍለጋ ቃል ያስገቡ")
            return
        
        bot.send_chat_action(chat_id, 'typing')
        
        # Get all products
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name_am, name_en, price, stock, desc_am, desc_en, image_url
                    FROM products
                    WHERE token = %s AND is_active = 1 AND stock > 0
                """, (token,))
                products = cur.fetchall()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not products:
            bot.send_message(
                chat_id,
                "🔍 ምንም ምርት አልተገኘም" if lang == "am" else "No products found"
            )
            return
        
        # Try AI search first
        ai_results = None
        if AIEngine.is_available():
            try:
                ai_results = AIEngine.search_products(query, products, lang)
            except Exception as e:
                logger.error(f"AI search error: {e}")
        
        # Fallback to keyword search
        if not ai_results:
            results = []
            query_lower = query.lower()
            for p in products:
                name = p.get('name_am', '').lower() if lang == 'am' else p.get('name_en', '').lower()
                desc = p.get('desc_am', '').lower() if lang == 'am' else p.get('desc_en', '').lower()
                if query_lower in name or query_lower in desc:
                    results.append(p)
        else:
            results = ai_results
        
        if not results:
            bot.send_message(
                chat_id,
                f"🔍 '{query}' ምንም አልተገኘም" if lang == "am" else f"🔍 No results for '{query}'"
            )
            return
        
        # Display results
        display_results(chat_id, results[:10], lang, query)
    
    def display_results(chat_id, results, lang, query):
        if not results:
            return
        
        bot.send_message(
            chat_id,
            f"📊 {len(results)} {lang == 'am' and 'ምርቶች ተገኝተዋል' or 'products found'}:\n"
            f"🔍 '{query}'",
            parse_mode="Markdown"
        )
        
        for p in results[:10]:
            name = p.get('name_am', '') if lang == 'am' else p.get('name_en', '')
            price = p.get('price', 0)
            stock = p.get('stock', 0)
            image_url = p.get('image_url')
            
            text = f"📦 **{name}**\n"
            text += f"💰 {format_currency(price)}\n"
            text += f"📌 {'✅ ይገኛል' if stock > 0 else '❌ ተሟጧል'}"
            
            markup = types.InlineKeyboardMarkup()
            if stock > 0:
                markup.add(types.InlineKeyboardButton("🛒 ወደ ጋሪ ጨምር", callback_data=f"add_{p['id']}"))
            
            if image_url:
                try:
                    bot.send_photo(chat_id, image_url, caption=text, reply_markup=markup, parse_mode="Markdown")
                except:
                    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
            else:
                bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    
    # ============================================================
    # TRACK ORDER
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == "📦 ትዕዛዝ")
    def handle_track(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        msg = bot.send_message(
            chat_id,
            "🔢 የትዕዛዝ ቁጥር ያስገቡ:" if lang == "am" else "Please enter your order ID:"
        )
        bot.register_next_step_handler(msg, process_track_order)
    
    def process_track_order(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        try:
            order_id = int(message.text.strip())
        except ValueError:
            bot.send_message(chat_id, "❌ የተሳሳተ ቁጥር!")
            return
        
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status_am, status_en, total_price, delivery_fee, created_at
                    FROM orders
                    WHERE id = %s AND token = %s
                """, (order_id, token))
                order = cur.fetchone()
        finally:
            if conn:
                put_db_connection(conn)
        
        if not order:
            bot.send_message(
                chat_id,
                "❌ ትዕዛዝ አልተገኘም" if lang == "am" else "Order not found"
            )
            return
        
        status_am, status_en, total, delivery, created = order
        status = status_am if lang == "am" else status_en
        
        text = f"📦 **{lang == 'am' and 'ትዕዛዝ' or 'Order'} #{order_id}**\n\n"
        text += f"📌 **{lang == 'am' and 'ሁኔታ' or 'Status'}:** {status}\n"
        text += f"💰 **{lang == 'am' and 'ድምር' or 'Total'}:** {format_currency(total + delivery)}\n"
        text += f"📅 **{lang == 'am' and 'ቀን' or 'Date'}:** {format_date(created)}"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
    
    # ============================================================
    # STORE INFO
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == "📍 መረጃ")
    def handle_store_info(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
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
        text += f"⭐ {store.get('rating', 0)}/5.0"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
    
    # ============================================================
    # HELP
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == "❓ እርዳታ")
    def handle_help(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
        text = """
❓ **እርዳታ**

🛍️ ምርቶች - የሱቁን ምርቶች ይመልከቱ
🛒 ጋሪ - የእርስዎን ጋሪ ይመልከቱ
🔍 ፍለጋ - AI የሚመራ ምርት ፍለጋ
📦 ትዕዛዝ - ትዕዛዝዎን ይከታተሉ
📍 መረጃ - ስለ ሱቁ መረጃ

💡 **AI Features:**
- 🤖 Natural Language Product Search
- 📸 AI-Powered Payment Verification
- 💬 Smart Chat Assistant

📞 ለተጨማሪ እርዳታ አስተዳዳሪውን ያነጋግሩ
"""
        bot.send_message(chat_id, text, parse_mode="Markdown")
    
    # ============================================================
    # BACK TO MAIN
    # ============================================================
    @bot.message_handler(func=lambda m: m.text == "🔙 ወደ ኋላ")
    def handle_back(message):
        chat_id = message.chat.id
        lang = get_user_lang(chat_id)
        
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
            types.KeyboardButton("📍 መረጃ"),
            types.KeyboardButton("❓ እርዳታ")
        )
        
        bot.send_message(
            chat_id,
            "🔙 ወደ ዋና ሜኑ" if lang == "am" else "Back to main menu",
            reply_markup=markup
        )
    
    # ============================================================
    # CONTACT & LOCATION HANDLERS
    # ============================================================
    @bot.message_handler(content_types=['contact'])
    def handle_contact(message):
        chat_id = message.chat.id
        if message.contact and message.contact.user_id == message.from_user.id:
            save_customer_info(chat_id, phone=message.contact.phone_number)
            bot.reply_to(message, "✅ ስልክ ተቀብለናል")
    
    @bot.message_handler(content_types=['location'])
    def handle_location(message):
        chat_id = message.chat.id
        save_customer_info(
            chat_id,
            lat=message.location.latitude,
            lng=message.location.longitude
        )
        bot.reply_to(message, "✅ አካባቢ ተቀብለናል")
    
    # ============================================================
    # AI CHAT
    # ============================================================
    @bot.message_handler(func=lambda m: True)
    def handle_ai_chat(message):
        chat_id = message.chat.id
        
        if not AIEngine.is_available():
            bot.reply_to(message, "🤖 AI በአሁኑ ጊዜ አይገኝም")
            return
        
        store = get_store_info(token)
        if not store:
            return
        
        bot.send_chat_action(chat_id, 'typing')
        
        context = f"""
        You are an AI assistant for '{store.get('store_name', '')}' store.
        Respond in the user's language (Amharic or English).
        Keep responses helpful, concise, and friendly.
        """
        
        response = AIEngine.generate_response(message.text, context)
        
        if response:
            bot.reply_to(message, response[:1000])
        else:
            bot.reply_to(message, "🤖 እባክዎ እንደገና ይሞክሩ")
    
    # ============================================================
    # POLLING
    # ============================================================
    def _run_bot():
        while True:
            try:
                bot.infinity_polling(skip_pending=True, timeout=30)
            except Exception as e:
                logger.error(f"Bot {token[:15]} polling error: {e}")
                time.sleep(5)
    
    threading.Thread(target=_run_bot, daemon=True).start()

# =================================================================================================
#                           CONTROL BOT - Super Admin
# =================================================================================================

class ControlBot:
    """Super Admin Control Bot"""
    
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
        logger.info("✅ Control Bot initialized")
    
    def _register_handlers(self):
        # ============================================================
        # COMMAND: /start, /help
        # ============================================================
        @self.bot.message_handler(commands=['start', 'help'])
        def cmd_start(message):
            chat_id = message.chat.id
            lang = get_user_lang(chat_id)
            
            text = f"""
👋 **{lang == 'am' and 'እንኳን ወደ ሱቅ ቦት መመዝገቢያ በደህና መጡ' or 'Welcome to Store Registration Bot'}!**

📌 **{lang == 'am' and 'አዲስ ሱቅ ለመመዝገብ' or 'To register a new store'}:**
1️⃣ @BotFather ላይ `/newbot` በማድረግ ቦት ይፍጠሩ
2️⃣ Token ከተቀበሉ '📝 አዲስ ሱቅ መዝግብ' ይጫኑ
3️⃣ 5 ደረጃዎችን ይሙሉ

📌 **{lang == 'am' and 'ሱቆችዎን ለማየት' or 'View your stores'}:** 🏪 ሱቆቼ

👑 **{lang == 'am' and 'Super Admin ከሆኑ' or 'If you are Super Admin'}:** `/superadmin`

🤖 **AI Features:**
- 🔍 Natural Language Product Search
- 📸 AI-Powered Payment Verification
- 💬 Smart Chat Assistant
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
        
        # ============================================================
        # COMMAND: /superadmin
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
        
        # ============================================================
        # COMMAND: /panel
        # ============================================================
        @self.bot.message_handler(commands=['panel'])
        def cmd_panel(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_dashboard(message)
        
        # ============================================================
        # COMMAND: /analytics
        # ============================================================
        @self.bot.message_handler(commands=['analytics'])
        def cmd_analytics(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_analytics(message)
        
        # ============================================================
        # COMMAND: /stores
        # ============================================================
        @self.bot.message_handler(commands=['stores'])
        def cmd_stores(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_all_stores(message)
        
        # ============================================================
        # COMMAND: /broadcast
        # ============================================================
        @self.bot.message_handler(commands=['broadcast'])
        def cmd_broadcast(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            self._show_broadcast_menu(message)
        
        # ============================================================
        # COMMAND: /ai
        # ============================================================
        @self.bot.message_handler(commands=['ai'])
        def cmd_ai(message):
            chat_id = message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.reply_to(message, "❌ /superadmin በማድረግ መጀመሪያ ይግቡ።")
                return
            
            status = "✅" if AIEngine.is_available() else "❌"
            text = f"""
🤖 **AI Status**

{status} Gemini AI: {'Available' if AIEngine.is_available() else 'Not Available'}

**Features:**
- Natural Language Search: {'✅' if AIEngine.is_available() else '❌'}
- Payment Receipt Verification: {'✅' if AIEngine.is_available() else '❌'}
- Smart Chat Assistant: {'✅' if AIEngine.is_available() else '❌'}

📌 {AIEngine.is_available() and 'All AI features are operational' or 'AI features are disabled. Please check GEMINI_API_KEY'}
"""
            self.bot.send_message(chat_id, text, parse_mode="Markdown")
        
        # ============================================================
        # DASHBOARD CALLBACKS
        # ============================================================
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
        
        # ============================================================
        # STORE APPROVAL CALLBACKS
        # ============================================================
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
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sblock_"))
        def handle_block(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            store_id = int(call.data.split("_")[1])
            self._block_store(chat_id, store_id, call)
        
        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("sunblock_"))
        def handle_unblock(call):
            chat_id = call.message.chat.id
            if not self._is_super_admin(chat_id):
                self.bot.answer_callback_query(call.id, "❌ ሴሽን አልቋል!")
                return
            store_id = int(call.data.split("_")[1])
            self._unblock_store(chat_id, store_id, call)
        
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
        
        # ============================================================
        # SEARCH CALLBACKS
        # ============================================================
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
        
        @self.bot.message_handler(content_types=['location'])
        def handle_location(message):
            self._search_by_location(message)
        
        # ============================================================
        # TEXT HANDLERS
        # ============================================================
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
        
        # ============================================================
        # REGISTRATION STEPS
        # ============================================================
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
    
    # ============================================================
    # PRIVATE METHODS
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
    
    def _get_main_menu(self, lang: str = "am"):
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
    
    def _get_dashboard_markup(self):
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
    
    # ============================================================
    # SUPER ADMIN LOGIN
    # ============================================================
    
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
                "🔓 **እንኳን ወደ Super Admin ፓነል በደህና መጡ!**\n\n"
                "🤖 AI-Powered Store Management System",
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
        self.bot.send_message(
            chat_id,
            "🔒 ከአስተዳደር ወጥተዋል።",
            reply_markup=self._get_main_menu()
        )
        logger.audit(chat_id, "super_admin_logout", {})
    
    # ============================================================
    # DASHBOARD
    # ============================================================
    
    def _show_dashboard(self, message):
        chat_id = message.chat.id
        
        try:
            total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
            pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
            active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
            total_products = db_execute("SELECT COUNT(*) FROM products", fetch=True)[0][0]
            total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
            revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
            
            text = f"""
🎛 **Super Admin Dashboard**

🏪 Total Stores: **{total_stores}**
⏳ Pending Approval: **{pending}**
🟢 Active Stores: **{active}**
📦 Total Products: **{total_products}**
🧾 Total Orders: **{total_orders}**
💰 Total Revenue: **{format_currency(revenue)}**

🤖 AI Status: {'✅ Active' if AIEngine.is_available() else '❌ Disabled'}

📌 ርምጫ ይምረጡ:
"""
            
            self.bot.send_message(
                chat_id,
                text,
                reply_markup=self._get_dashboard_markup(),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    # ============================================================
    # PENDING STORES
    # ============================================================
    
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
📝 {store['shop_description'][:50] if store['shop_description'] else ''}...
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
            logger.error(f"Pending stores error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    # ============================================================
    # ALL STORES
    # ============================================================
    
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
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🔴 አግድ", callback_data="sblock_menu"),
                types.InlineKeyboardButton("🟢 አንቃ", callback_data="sunblock_menu")
            )
            markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"All stores error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    # ============================================================
    # ANALYTICS
    # ============================================================
    
    def _show_analytics(self, message):
        chat_id = message.chat.id
        
        try:
            total_stores = db_execute("SELECT COUNT(*) FROM stores", fetch=True)[0][0]
            pending = db_execute("SELECT COUNT(*) FROM stores WHERE is_approved = 0", fetch=True)[0][0]
            active = db_execute("SELECT COUNT(*) FROM stores WHERE is_active = 1 AND is_approved = 1", fetch=True)[0][0]
            total_products = db_execute("SELECT COUNT(*) FROM products", fetch=True)[0][0]
            total_orders = db_execute("SELECT COUNT(*) FROM orders", fetch=True)[0][0]
            revenue = db_execute("SELECT COALESCE(SUM(total_price + delivery_fee), 0) FROM orders WHERE status_stage >= 1", fetch=True)[0][0]
            active_users = db_execute("SELECT COUNT(DISTINCT customer_id) FROM orders", fetch=True)[0][0]
            
            # Top stores
            top_stores = db_execute_dict("""
                SELECT s.store_name, COUNT(o.id) as orders, 
                       COALESCE(SUM(o.total_price + o.delivery_fee), 0) as revenue
                FROM stores s
                LEFT JOIN orders o ON s.token = o.token AND o.status_stage >= 1
                GROUP BY s.id, s.store_name
                ORDER BY revenue DESC
                LIMIT 5
            """)
            
            text = f"""
📊 **System Analytics**

🏪 **Stores**
  • Total: {total_stores}
  • Active: {active}
  • Pending: {pending}

📦 **Products:** {total_products}

🧾 **Orders**
  • Total: {total_orders}
  • Active Users: {active_users}

💰 **Revenue:** {format_currency(revenue)}

🤖 **AI Status:** {'✅ Active' if AIEngine.is_available() else '❌ Disabled'}

🏆 **Top Stores by Revenue:**
"""
            for i, store in enumerate(top_stores, 1):
                text += f"  {i}. {store['store_name']} - {store['orders']} orders - {format_currency(store['revenue'])}\n"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔙 ወደ ኋላ", callback_data="dash_back"))
            
            self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Analytics error: {e}")
            self.bot.send_message(chat_id, f"❌ ስህተት: {e}")
    
    # ============================================================
    # BROADCAST
    # ============================================================
    
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
            "📢 **Broadcast Message**\n\nWho do you want to send the message to?",
            reply_markup=markup
        )
    
    def _broadcast_to_all(self, message, target):
        chat_id = message.chat.id
        msg_text = message.text
        
        try:
            if target == "owners":
                users = db_execute_dict("SELECT DISTINCT admin_id FROM stores WHERE admin_id > 0 AND is_approved = 1")
            else:
                users = db_execute_dict("SELECT DISTINCT customer_id FROM orders")
            
            if not users:
                self.bot.reply_to(message, "❌ No users found!")
                return
            
            self.bot.reply_to(message, f"⏳ Sending to {len(users)} users...")
            
            success = 0
            failed = 0
            
            for user in users:
                user_id = user.get('admin_id') or user.get('customer_id')
                if not user_id:
                    continue
                try:
                    self.bot.send_message(
                        user_id,
                        f"📢 **System Broadcast**\n\n{msg_text}"
                    )
                    success += 1
                    time.sleep(0.05)
                except:
                    failed += 1
            
            self.bot.send_message(
                chat_id,
                f"✅ Broadcast complete!\n\n✅ Success: {success}\n❌ Failed: {failed}",
                reply_markup=self._get_dashboard_markup()
            )
            
            logger.audit(chat_id, "broadcast_sent", {
                "target": target,
                "success": success,
                "failed": failed
            })
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            self.bot.reply_to(message, f"❌ Error: {e}")
    
    def _broadcast_to_user(self, message):
        chat_id = message.chat.id
        
        try:
            user_id = int(message.text.strip())
        except:
            self.bot.reply_to(message, "❌ Invalid user ID!")
            return
        
        msg = self.bot.send_message(chat_id, "📝 Enter the message to send:")
        self.bot.register_next_step_handler(
            msg,
            lambda m: self._send_single_message(m, user_id)
        )
    
    def _send_single_message(self, message, user_id):
        chat_id = message.chat.id
        msg_text = message.text
        
        try:
            self.bot.send_message(
                user_id,
                f"📢 **System Broadcast**\n\n{msg_text}"
            )
            self.bot.reply_to(
                message,
                f"✅ Message sent to user {user_id}!",
                reply_markup=self._get_dashboard_markup()
            )
            logger.audit(chat_id, "single_message_sent", {"user_id": user_id})
        except Exception as e:
            self.bot.reply_to(
                message,
                f"❌ Failed to send: {e}",
                reply_markup=self._get_dashboard_markup()
            )
    
    # ============================================================
    # STORE APPROVAL / REJECTION / BLOCK / UNBLOCK
    # ============================================================
    
    def _approve_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT token, store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ Store not found!")
                return
            
            store = store[0]
            db_execute("UPDATE stores SET is_approved = 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (store_id,))
            start_shop_bot(store['token'])
            
            try:
                self.bot.send_message(
                    store['admin_id'],
                    f"🎉 **Your store has been approved!**\n\n"
                    f"🏪 {store['store_name']}\n"
                    f"🔑 Use /login to access admin panel"
                )
            except:
                pass
            
            if call:
                self.bot.edit_message_text(
                    f"✅ Store #{store_id} approved!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "Approved!")
            
            self._show_dashboard(call.message if call else None)
            logger.audit(chat_id, "store_approved", {"store_id": store_id, "store_name": store['store_name']})
        except Exception as e:
            logger.error(f"Approve store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _reject_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ Store not found!")
                return
            
            store = store[0]
            db_execute("DELETE FROM stores WHERE id = %s", (store_id,))
            
            try:
                self.bot.send_message(
                    store['admin_id'],
                    f"❌ Your store **{store['store_name']}** has been rejected."
                )
            except:
                pass
            
            if call:
                self.bot.edit_message_text(
                    f"❌ Store #{store_id} rejected!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "Rejected!")
            
            self._show_dashboard(call.message if call else None)
            logger.audit(chat_id, "store_rejected", {"store_id": store_id, "store_name": store['store_name']})
        except Exception as e:
            logger.error(f"Reject store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _block_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ Store not found!")
                return
            
            store = store[0]
            db_execute("UPDATE stores SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (store_id,))
            
            try:
                self.bot.send_message(store['admin_id'], f"🔴 Your store **{store['store_name']}** has been blocked.")
            except:
                pass
            
            if call:
                self.bot.edit_message_text(
                    f"🔴 Store #{store_id} blocked!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "Blocked!")
            
            logger.audit(chat_id, "store_blocked", {"store_id": store_id, "store_name": store['store_name']})
        except Exception as e:
            logger.error(f"Block store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    def _unblock_store(self, chat_id: int, store_id: int, call=None):
        try:
            store = db_execute_dict("SELECT store_name, admin_id FROM stores WHERE id = %s", (store_id,))
            if not store:
                if call:
                    self.bot.answer_callback_query(call.id, "❌ Store not found!")
                return
            
            store = store[0]
            db_execute("UPDATE stores SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (store_id,))
            
            try:
                self.bot.send_message(store['admin_id'], f"🟢 Your store **{store['store_name']}** has been unblocked.")
            except:
                pass
            
            if call:
                self.bot.edit_message_text(
                    f"🟢 Store #{store_id} unblocked!\n🏪 {store['store_name']}",
                    chat_id,
                    call.message.message_id
                )
                self.bot.answer_callback_query(call.id, "Unblocked!")
            
            logger.audit(chat_id, "store_unblocked", {"store_id": store_id, "store_name": store['store_name']})
        except Exception as e:
            logger.error(f"Unblock store error: {e}")
            if call:
                self.bot.answer_callback_query(call.id, f"❌ {str(e)}")
    
    # ============================================================
    # STORE REGISTRATION
    # ============================================================
    
    def _start_registration(self, message):
        chat_id = message.chat.id
        self._clear_reg_state(chat_id)
        self._set_reg_state(chat_id, "step", 1)
        self._set_reg_state(chat_id, "data", {})
        
        msg = self.bot.send_message(
            chat_id,
            "📝 **Step 1/5: Bot Token**\n\nEnter the token you got from @BotFather:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_token)
    
    def _process_reg_token(self, message):
        chat_id = message.chat.id
        token = message.text.strip()
        
        try:
            test_bot = telebot.TeleBot(token)
            bot_info = test_bot.get_me()
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            self.bot.reply_to(message, "❌ Invalid token! Please check and try again.")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["token"] = token
        data["bot_username"] = bot_info.username
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 2)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ Token verified! 👤 @{bot_info.username}\n\n"
            "📝 **Step 2/5: Store Name**\n\nEnter your store name:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_name)
    
    def _process_reg_name(self, message):
        chat_id = message.chat.id
        name = sanitize_input(message.text.strip())
        
        if not name or len(name) < 3:
            self.bot.reply_to(message, "❌ Store name must be at least 3 characters!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["store_name"] = name
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 3)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ Store name: **{name}**\n\n"
            "📝 **Step 3/5: Password**\n\n"
            "Enter a password for store admin (min 8 characters):"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_password)
    
    def _process_reg_password(self, message):
        chat_id = message.chat.id
        password = message.text.strip()
        
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
            f"✅ Password received\n\n"
            "📝 **Step 4/5: Store Location**\n\n"
            "Share your store location or enter city name:",
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
            location_text = sanitize_input(message.text.strip())
            if not location_text:
                self.bot.reply_to(message, "❌ Please enter a location!")
                return
            data["area_text"] = location_text
        
        self._set_reg_state(chat_id, "data", data)
        self._set_reg_state(chat_id, "step", 5)
        
        msg = self.bot.send_message(
            chat_id,
            f"✅ Location: {location_text}\n\n"
            "📝 **Step 5/5: Store Description**\n\n"
            "Enter a short description of your store:"
        )
        self.bot.register_next_step_handler(msg, self._process_reg_description)
    
    def _process_reg_description(self, message):
        chat_id = message.chat.id
        description = sanitize_input(message.text.strip())
        
        if not description:
            self.bot.reply_to(message, "❌ Please enter a description!")
            return
        
        data = self._get_reg_state(chat_id, "data") or {}
        data["shop_description"] = description
        data["username"] = data.get("bot_username", f"shop_{chat_id}")
        
        try:
            existing = db_execute_dict("SELECT 1 FROM stores WHERE token = %s", (data["token"],))
            if existing:
                self.bot.reply_to(message, "❌ This token is already registered!")
                return
            
            h_pass, salt = hash_password(data["password"])
            
            db_execute("""
                INSERT INTO stores (
                    token, store_name, admin_id, username,
                    password_hash, password_salt,
                    is_active, is_approved, shop_lat, shop_lng,
                    area_text, shop_description
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data["token"], data["store_name"], chat_id, data["username"],
                h_pass, salt, 1, 0,
                data.get("shop_lat"), data.get("shop_lng"),
                data.get("area_text", ""), data.get("shop_description", "")
            ))
            
            start_shop_bot(data["token"])
            
            if Config.SUPER_ADMIN_ID:
                try:
                    self.bot.send_message(
                        Config.SUPER_ADMIN_ID,
                        f"🔔 **New store pending approval!**\n\n"
                        f"🏪 {data['store_name']}\n"
                        f"👤 @{data['username']}\n"
                        f"📍 {data.get('area_text', 'N/A')}"
                    )
                except:
                    pass
            
            self._clear_reg_state(chat_id)
            
            self.bot.reply_to(
                message,
                f"✅ **Store registered successfully!**\n\n"
                f"🏪 Name: {data['store_name']}\n"
                f"👤 Username: @{data['username']}\n"
                f"📍 Location: {data.get('area_text', 'Saved')}\n"
                f"🔑 Password: `{data['password']}`\n\n"
                f"⏳ Your store is pending approval by the Super Admin.",
                reply_markup=self._get_main_menu(),
                parse_mode="Markdown"
            )
            
            logger.audit(chat_id, "store_registered", {
                "store_name": data["store_name"],
                "store_id": data["token"]
            })
        except Exception as e:
            logger.error(f"Registration error: {e}")
            self.bot.reply_to(message, f"❌ Error: {e}")
    
    # ============================================================
    # MY STORES
    # ============================================================
    
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
                    "❌ You haven't registered any stores yet.\n\n"
                    "📌 Click '📝 Register New Store' to get started.",
                    reply_markup=self._get_main_menu()
                )
                return
            
            text = "🏪 **Your Stores:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                approved = "✅" if store['is_approved'] else "⏳"
                text += f"""
{status} {approved} **{store['store_name']}**
  👤 @{store['username'] or 'N/A'}
  📍 {store['area_text'] or 'N/A'}
  🆔 #{store['id']}
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu())
        except Exception as e:
            logger.error(f"My stores error: {e}")
            self.bot.reply_to(message, f"❌ Error: {e}")
    
    # ============================================================
    # SEARCH
    # ============================================================
    
    def _search_by_name(self, message):
        chat_id = message.chat.id
        query = sanitize_input(message.text.strip())
        
        if not query:
            self.bot.reply_to(message, "❌ Please enter a store name!")
            return
        
        try:
            stores = db_execute_dict("""
                SELECT store_name, username, area_text, is_active, is_approved
                FROM stores
                WHERE (store_name ILIKE %s OR username ILIKE %s) AND is_approved = 1
                LIMIT 10
            """, (f"%{query}%", f"%{query}%"))
            
            if not stores:
                self.bot.reply_to(
                    message,
                    "🔍 No stores found.",
                    reply_markup=self._get_main_menu()
                )
                return
            
            text = "🔍 **Search Results:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                text += f"""
{status} **{store['store_name']}**
  👤 @{store['username'] or 'N/A'}
  📍 {store['area_text'] or 'N/A'}
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu())
        except Exception as e:
            logger.error(f"Search error: {e}")
            self.bot.reply_to(message, f"❌ Error: {e}")
    
    def _search_by_location(self, message):
        chat_id = message.chat.id
        
        if not message.location:
            self.bot.reply_to(message, "❌ Please share your location!")
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
                    "🔍 No stores found nearby.",
                    reply_markup=self._get_main_menu()
                )
                return
            
            text = "📍 **Nearby Stores:**\n\n"
            for store in stores:
                status = "🟢" if store['is_active'] else "🔴"
                distance = store.get('distance', 0)
                text += f"""
{status} **{store['store_name']}**
  👤 @{store['username'] or 'N/A'}
  📍 {store['area_text'] or 'N/A'}
  📏 {distance:.1f} km
"""
            
            self.bot.reply_to(message, text, reply_markup=self._get_main_menu())
        except Exception as e:
            logger.error(f"Location search error: {e}")
            self.bot.reply_to(message, f"❌ Error: {e}")
    
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
        stores = db_execute_dict("SELECT token FROM stores")
        count = 0
        for store in stores:
            if start_shop_bot(store['token']):
                count += 1
        logger.info(f"✅ {count} stores loaded")
    except Exception as e:
        logger.error(f"❌ Failed to load stores: {e}")

load_existing_stores()

# =================================================================================================
#                           MAIN ENTRY POINT
# =================================================================================================

if __name__ == "__main__":
    try:
        control_bot = ControlBot()
        logger.info("🚀 Multi-Tenant Shop Bot v5.0 is running!")
        logger.info(f"🤖 AI Status: {'✅ Active' if AIEngine.is_available() else '❌ Disabled'}")
        logger.info(f"📊 Web Dashboard: http://{Config.HOST}:{Config.PORT}")
        
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        while True:
            time.sleep(60)
