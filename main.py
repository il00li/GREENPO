import telebot
import requests
import json
import sqlite3
from datetime import datetime
import threading
import time

# إعدادات البوت
BOT_TOKEN = "8110119856:AAGOAGLdU5zb-NRJt75fEYyeZa7FbPz794w"
ADMIN_ID = 7251748706
CHANNELS = ["@crazys7", "@AWU87"]
LUMMI_API_KEY = "lummi-b06d12ba02329efb74404de07e20b434aff295de34419f35c56eb3e200f05a71"

bot = telebot.TeleBot(BOT_TOKEN)

# إعداد قاعدة البيانات
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TEXT,
            is_banned INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            search_count INTEGER DEFAULT 0,
            download_count INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_sessions (
            user_id INTEGER,
            query TEXT,
            media_type TEXT,
            results TEXT,
            current_index INTEGER DEFAULT 0
        )
    ''')
    
    # إعدادات افتراضية
    cursor.execute('INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)', ('bot_active', '1'))
    cursor.execute('INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)', ('paid_mode', '0'))
    cursor.execute('INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)', ('stop_message', 'البوت متوقف مؤقتاً'))
    
    conn.commit()
    conn.close()

init_db()

# دوال قاعدة البيانات
def add_user(user_id, username, first_name):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, join_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_stats(user_id, stat_type):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    if stat_type == 'search':
        cursor.execute('UPDATE users SET search_count = search_count + 1 WHERE user_id = ?', (user_id,))
    elif stat_type == 'download':
        cursor.execute('UPDATE users SET download_count = download_count + 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_bot_setting(key):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM bot_settings WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_bot_setting(key, value):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(search_count) FROM users')
    total_searches = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(download_count) FROM users')
    total_downloads = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_premium = 1')
    active_subscribers = cursor.fetchone()[0]
    
    conn.close()
    return total_users, total_searches, total_downloads, active_subscribers

# دالة التحقق من الاشتراك
def check_subscription(user_id):
    try:
        for channel in CHANNELS:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked']:
                return False
        return True
    except:
        return False

# دالة البحث في Lummi
def search_lummi(query, media_type):
    try:
        url = "https://api.lummi.ai/v1/search"
        headers = {
            "Authorization": f"Bearer {LUMMI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "query": query,
            "type": media_type.lower(),
            "limit": 20
        }
        
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

# دالة حفظ جلسة البحث
def save_search_session(user_id, query, media_type, results):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM search_sessions WHERE user_id = ?', (user_id,))
    cursor.execute('''
        INSERT INTO search_sessions (user_id, query, media_type, results, current_index)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, query, media_type, json.dumps(results), 0))
    conn.commit()
    conn.close()

# دالة الحصول على جلسة البحث
def get_search_session(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM search_sessions WHERE user_id = ?', (user_id,))
    session = cursor.fetchone()
    conn.close()
    if session:
        return {
            'query': session[1],
            'media_type': session[2],
            'results': json.loads(session[3]),
            'current_index': session[4]
        }
    return None

# دالة تحديث فهرس البحث
def update_search_index(user_id, new_index):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE search_sessions SET current_index = ? WHERE user_id = ?', (new_index, user_id))
    conn.commit()
    conn.close()

# أزرار البداية
def start_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.row(
        telebot.types.InlineKeyboardButton("✅ قناة @crazys7", url="https://t.me/crazys7"),
        telebot.types.InlineKeyboardButton("✅ قناة @AWU87", url="https://t.me/AWU87")
    )
    keyboard.row(telebot.types.InlineKeyboardButton("🔍 تحقق", callback_data="check_subscription"))
    return keyboard

# أزرار القائمة الرئيسية
def main_menu_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.row(telebot.types.InlineKeyboardButton("✦ انقر للبحث ✦", callback_data="search_menu"))
    keyboard.row(telebot.types.InlineKeyboardButton("𓆩عن المطور𓆪", callback_data="about_dev"))
    keyboard.row(telebot.types.InlineKeyboardButton("『📊』الإحصائيات", callback_data="stats"))
    return keyboard

# أزرار البحث
def search_menu_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.row(telebot.types.InlineKeyboardButton("🎨 رسومات توضيحية", callback_data="search_illustrations"))
    keyboard.row(telebot.types.InlineKeyboardButton("🧊 نماذج ثلاثية الأبعاد", callback_data="search_3d"))
    keyboard.row(telebot.types.InlineKeyboardButton("🖌️ أنماط مرئية مخصصة", callback_data="search_styles"))
    keyboard.row(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    return keyboard

# أزرار التنقل في النتائج
def navigation_keyboard(current_index, total_results):
    keyboard = telebot.types.InlineKeyboardMarkup()
    nav_buttons = []
    
    if current_index > 0:
        nav_buttons.append(telebot.types.InlineKeyboardButton("«« النتيجة السابقة", callback_data="prev_result"))
    
    if current_index < total_results - 1:
        nav_buttons.append(telebot.types.InlineKeyboardButton("»» النتيجة التالية", callback_data="next_result"))
    
    if nav_buttons:
        keyboard.row(*nav_buttons)
    
    keyboard.row(telebot.types.InlineKeyboardButton("◤تحميل◥", callback_data="download_media"))
    keyboard.row(telebot.types.InlineKeyboardButton("🔙 رجوع للبحث", callback_data="search_menu"))
    return keyboard

# أزرار الإدارة
def admin_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.row(telebot.types.InlineKeyboardButton("🔒 إدارة الأعضاء", callback_data="manage_users"))
    keyboard.row(telebot.types.InlineKeyboardButton("💰 الوضع المدفوع", callback_data="paid_mode"))
    keyboard.row(telebot.types.InlineKeyboardButton("🧾 إدارة الاشتراكات", callback_data="manage_subs"))
    keyboard.row(telebot.types.InlineKeyboardButton("🛑 إيقاف البوت", callback_data="stop_bot"))
    keyboard.row(telebot.types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="bot_settings"))
    return keyboard

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    # التحقق من حالة البوت
    if get_bot_setting('bot_active') == '0' and user_id != ADMIN_ID:
        stop_msg = get_bot_setting('stop_message')
        bot.send_message(user_id, stop_msg)
        return
    
    # التحقق من الحظر
    user = get_user(user_id)
    if user and user[4] == 1:  # is_banned
        bot.send_message(user_id, "❌ تم حظرك من استخدام البوت")
        return
    
    # إضافة المستخدم إلى قاعدة البيانات
    add_user(user_id, message.from_user.username, message.from_user.first_name)
    
    # لوحة الإدارة للمدير
    if user_id == ADMIN_ID:
        bot.send_message(user_id, "🔧 مرحباً بك في لوحة الإدارة", reply_markup=admin_keyboard())
        return
    
    # التحقق من الاشتراك
    if not check_subscription(user_id):
        welcome_msg = "(¬‿¬)ノ ♨️| اشترك في القنوات للتمكن من استخدام البوت"
        bot.send_message(user_id, welcome_msg, reply_markup=start_keyboard())
    else:
        bot.send_message(user_id, "🎉 مرحباً بك! اختر ما تريد:", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    # التحقق من حالة البوت
    if get_bot_setting('bot_active') == '0' and user_id != ADMIN_ID:
        stop_msg = get_bot_setting('stop_message')
        bot.answer_callback_query(call.id, stop_msg, show_alert=True)
        return
    
    if call.data == "check_subscription":
        if check_subscription(user_id):
            # إشعار المدير
            user_info = f"📥 مستخدم جديد تم تأكيد اشتراكه\n👤 الاسم: {call.from_user.first_name}\n🆔 المعرف: {user_id}"
            try:
                bot.send_message(ADMIN_ID, user_info)
            except:
                pass
            
            bot.edit_message_text("🎉 مرحباً بك! اختر ما تريد:", call.message.chat.id, call.message.message_id, reply_markup=main_menu_keyboard())
        else:
            bot.answer_callback_query(call.id, "❌ يجب الاشتراك في جميع القنوات أولاً", show_alert=True)
    
    elif call.data == "main_menu":
        bot.edit_message_text("🎉 مرحباً بك! اختر ما تريد:", call.message.chat.id, call.message.message_id, reply_markup=main_menu_keyboard())
    
    elif call.data == "search_menu":
        bot.edit_message_text("🔍 اختر نوع الوسائط للبحث:", call.message.chat.id, call.message.message_id, reply_markup=search_menu_keyboard())
    
    elif call.data.startswith("search_"):
        media_type = call.data.replace("search_", "")
        type_names = {
            "illustrations": "🎨 رسومات توضيحية",
            "3d": "🧊 نماذج ثلاثية الأبعاد", 
            "styles": "🖌️ أنماط مرئية مخصصة"
        }
        
        bot.edit_message_text(f"🔍 أرسل كلمة البحث لـ {type_names.get(media_type, media_type)}:", 
                             call.message.chat.id, call.message.message_id)
        
        # حفظ نوع البحث المطلوب
        set_bot_setting(f"search_type_{user_id}", media_type)
    
    elif call.data == "about_dev":
        about_text = """🔧 المطوّر @Ili8_8ill

شاب يمني دخل عالم البرمجة والبوتات في تيليجرام وهو مليان شغف وحماس. بدأ يتعلّم خطوة خطوة، من الصفر، وكل يوم يزيد خبرته من خلال التجربة والمشاريع الصغيرة اللي لها فايدة حقيقية.

ما شاء الله عليه، يتميّز بـ:
• حبّه للاستكشاف والتعلّم بنفسه
• قدرته على بناء بوتات بسيطة تخدم الناس
• استخدامه لأدوات مثل BotFather وPython
• تقبّله للنقد وسعيه للتطوير المستمر

📢 القنوات اللي يشتغل فيها: @crazys7 – @AWU87

🌟 رؤيته: ماشي في طريق البرمجة من الأساسيات نحو الاحتراف، بخطوات ثابتة وطموح كبير إنه يصنع بوتات تخدم الناس وتضيف قيمة حقيقية.

📬 للتواصل: تابع حسابه: @Ili8_8ill"""
        
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.row(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
        
        bot.edit_message_text(about_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif call.data == "stats":
        total_users, total_searches, total_downloads, active_subscribers = get_stats()
        stats_text = f"""📊 إحصائيات البوت:

👥 عدد المستخدمين الإجمالي: {total_users}
🔍 عدد عمليات البحث: {total_searches}
📥 عدد التحميلات: {total_downloads}
⭐ عدد المشتركين النشطين: {active_subscribers}"""
        
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.row(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
        
        bot.edit_message_text(stats_text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif call.data == "prev_result":
        session = get_search_session(user_id)
        if session and session['current_index'] > 0:
            new_index = session['current_index'] - 1
            update_search_index(user_id, new_index)
            show_search_result(call.message, session['results'], new_index)
    
    elif call.data == "next_result":
        session = get_search_session(user_id)
        if session and session['current_index'] < len(session['results']) - 1:
            new_index = session['current_index'] + 1
            update_search_index(user_id, new_index)
            show_search_result(call.message, session['results'], new_index)
    
    elif call.data == "download_media":
        session = get_search_session(user_id)
        if session:
            result = session['results'][session['current_index']]
            
            # إرسال الوسائط إلى القناة
            try:
                caption = f"📥 تم التحميل بواسطة: {call.from_user.first_name}\n🔍 البحث: {session['query']}\n📂 النوع: {session['media_type']}"
                
                if result.get('type') == 'image':
                    bot.send_photo("@AWU87", result['url'], caption=caption)
                else:
                    bot.send_document("@AWU87", result['url'], caption=caption)
                
                # تحديث الإحصائيات
                update_user_stats(user_id, 'download')
                
                # رسالة النجاح
                bot.edit_message_text("✅ تم التحميل بنجاح! لإجراء بحث جديد، أرسل /start", 
                                     call.message.chat.id, call.message.message_id)
                
            except Exception as e:
                bot.answer_callback_query(call.id, "❌ حدث خطأ في التحميل", show_alert=True)
    
    # معالجة أزرار الإدارة
    elif user_id == ADMIN_ID:
        handle_admin_callbacks(call)

def handle_admin_callbacks(call):
    if call.data == "manage_users":
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.row(telebot.types.InlineKeyboardButton("🚫 حظر عضو", callback_data="ban_user"))
        keyboard.row(telebot.types.InlineKeyboardButton("✅ إلغاء الحظر", callback_data="unban_user"))
        keyboard.row(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_menu"))
        
        bot.edit_message_text("🔒 إدارة الأعضاء:", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif call.data == "paid_mode":
        current_mode = get_bot_setting('paid_mode')
        status = "مفعل" if current_mode == '1' else "معطل"
        
        keyboard = telebot.types.InlineKeyboardMarkup()
        if current_mode == '0':
            keyboard.row(telebot.types.InlineKeyboardButton("🔄 تحويل إلى مدفوع", callback_data="enable_paid"))
        else:
            keyboard.row(telebot.types.InlineKeyboardButton("🔄 تحويل إلى مجاني", callback_data="disable_paid"))
        keyboard.row(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_menu"))
        
        bot.edit_message_text(f"💰 الوضع المدفوع: {status}", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif call.data == "stop_bot":
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.row(telebot.types.InlineKeyboardButton("🛑 إيقاف البوت", callback_data="confirm_stop"))
        keyboard.row(telebot.types.InlineKeyboardButton("🔄 تشغيل البوت", callback_data="start_bot"))
        keyboard.row(telebot.types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_menu"))
        
        bot_status = "نشط" if get_bot_setting('bot_active') == '1' else "متوقف"
        bot.edit_message_text(f"🛑 حالة البوت: {bot_status}", call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    
    elif call.data == "confirm_stop":
        set_bot_setting('bot_active', '0')
        bot.answer_callback_query(call.id, "تم إيقاف البوت للمستخدمين العاديين")
    
    elif call.data == "start_bot":
        set_bot_setting('bot_active', '1')
        bot.answer_callback_query(call.id, "تم تشغيل البوت")
    
    elif call.data == "admin_menu":
        bot.edit_message_text("🔧 لوحة الإدارة", call.message.chat.id, call.message.message_id, reply_markup=admin_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_search_query(message):
    user_id = message.from_user.id
    
    # التحقق من حالة البوت
    if get_bot_setting('bot_active') == '0' and user_id != ADMIN_ID:
        return
    
    # التحقق من وجود نوع بحث محفوظ
    search_type = get_bot_setting(f"search_type_{user_id}")
    if not search_type:
        return
    
    # إزالة نوع البحث المحفوظ
    set_bot_setting(f"search_type_{user_id}", "")
    
    query = message.text
    
    # إرسال رسالة انتظار
    wait_msg = bot.send_message(user_id, "🔍 جاري البحث...")
    
    # البحث في Lummi
    results = search_lummi(query, search_type)
    
    if results and results.get('data'):
        # حفظ جلسة البحث
        save_search_session(user_id, query, search_type, results['data'])
        
        # تحديث الإحصائيات
        update_user_stats(user_id, 'search')
        
        # عرض أول نتيجة
        show_search_result(wait_msg, results['data'], 0)
    else:
        bot.edit_message_text("❌ لم يتم العثور على نتائج", wait_msg.chat.id, wait_msg.message_id)

def show_search_result(message, results, index):
    if not results or index >= len(results):
        return
    
    result = results[index]
    
    try:
        # إرسال الوسائط
        if result.get('type') == 'image' or 'image' in result.get('content_type', ''):
            bot.send_photo(message.chat.id, result['url'], 
                          caption=f"🔍 النتيجة {index + 1} من {len(results)}\n📝 {result.get('title', 'بدون عنوان')}",
                          reply_markup=navigation_keyboard(index, len(results)))
        else:
            bot.send_document(message.chat.id, result['url'],
                             caption=f"🔍 النتيجة {index + 1} من {len(results)}\n📝 {result.get('title', 'بدون عنوان')}",
                             reply_markup=navigation_keyboard(index, len(results)))
        
        # حذف رسالة الانتظار
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
            
    except Exception as e:
        bot.edit_message_text(f"❌ خطأ في عرض النتيجة: {str(e)}", message.chat.id, message.message_id)

if __name__ == "__main__":
    print("🤖 تم تشغيل البوت...")
    bot.infinity_polling()
 
