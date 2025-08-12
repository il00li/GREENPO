import telebot
from telebot import types
import requests
import sqlite3
import json
import time
from datetime import datetime

# Tokens and API keys
TOKEN = "8110119856:AAEMbomUhyXXrR8Y-YvmTJR4jmDP1-y-tQo"
ADMIN_ID = 7251748706
CHANNELS = ["@crazys7", "@AWU87"]
LUMNI_API = "lummi-b06d12ba02329efb74404de07e20b434aff295de34419f35c56eb3e200f05a71"
PIXABAY_API = "51444506-bffefcaf12816bd85a20222d1"
ICONFINDER_API = "7K3SAYeDJcF2F7OsiUe6hAvobN0mZ485PY8iX1lJktLihGgipDUFudsKahNiyHiG"
ICONFINDER_CLIENT = "TFGLeU74JhSRdGhfAPNPqMtWCyD8yBvoOgyxWhavP2hnwFRSjjAEg92fjrX9kkQk"

bot = telebot.TeleBot(TOKEN)

# Database setup
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_date TEXT,
                last_active TEXT,
                is_subscribed INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_users INTEGER DEFAULT 0,
                total_searches INTEGER DEFAULT 0,
                total_downloads INTEGER DEFAULT 0,
                active_users INTEGER DEFAULT 0
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS bot_settings (
                id INTEGER PRIMARY KEY,
                is_active INTEGER DEFAULT 1,
                is_premium_mode INTEGER DEFAULT 0,
                stop_message TEXT DEFAULT ''
            )''')

# Initialize settings
c.execute("INSERT OR IGNORE INTO bot_settings (id) VALUES (1)")
c.execute("INSERT OR IGNORE INTO stats (id) VALUES (1)")
conn.commit()

# Helper functions
def check_subscription(user_id):
    try:
        for channel in CHANNELS:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except Exception as e:
        print(f"Subscription check error: {e}")
        return False

def update_stats(field):
    c.execute(f"UPDATE stats SET {field} = {field} + 1 WHERE id = 1")
    conn.commit()

def get_stats():
    c.execute("SELECT total_users, total_searches, total_downloads, active_users FROM stats WHERE id = 1")
    return c.fetchone()

def is_admin(user_id):
    return user_id == ADMIN_ID

def get_user(user_id):
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    return c.fetchone()

def create_user(user_id, username, full_name):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, joined_date, last_active) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, full_name, now, now))
    conn.commit()
    update_stats('total_users')

def update_activity(user_id):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (now, user_id))
    conn.commit()

# Bot handlers
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.first_name + " " + (message.from_user.last_name or "")
    
    create_user(user_id, username, full_name)
    update_activity(user_id)
    
    # Check if bot is stopped
    c.execute("SELECT is_active, stop_message FROM bot_settings WHERE id = 1")
    setting = c.fetchone()
    if setting and setting[0] == 0 and not is_admin(user_id):
        bot.send_message(user_id, setting[1] or "البوت متوقف مؤقتًا للصيانة. نعتذر للإزعاج.")
        return
    
    # Check subscription
    if check_subscription(user_id):
        show_main_menu(message)
    else:
        welcome_msg = "(¬‿¬)ノ\n♨️| اشترك في القنوات للتمكن من استخدام البوت"
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for channel in CHANNELS:
            keyboard.add(types.InlineKeyboardButton(f"✅ قناة {channel}", url=f"https://t.me/{channel[1:]}"))
        keyboard.add(types.InlineKeyboardButton("🔍 تحقق", callback_data="check_subscription"))
        
        bot.send_message(user_id, welcome_msg, reply_markup=keyboard)

def show_main_menu(message):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("✦ انقر للبحث ✦", callback_data="search"),
        types.InlineKeyboardButton("𓆩عن المطور𓆪", callback_data="about_dev"),
        types.InlineKeyboardButton("『📊』الإحصائيات", callback_data="stats")
    )
    
    if is_admin(message.from_user.id):
        keyboard.add(types.InlineKeyboardButton("🧑‍💼 لوحة الإدارة", callback_data="admin_panel"))
    
    bot.send_message(message.chat.id, "مرحبًا بك في القائمة الرئيسية:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def check_subscription_callback(call):
    if check_subscription(call.from_user.id):
        # Notify admin
        user_info = f"👤 الاسم: {call.from_user.first_name}\n🆔 المعرف: {call.from_user.id}"
        bot.send_message(ADMIN_ID, f"📥 مستخدم جديد تم تأكيد اشتراكه\n{user_info}")
        
        # Update user status
        c.execute("UPDATE users SET is_subscribed = 1 WHERE user_id = ?", (call.from_user.id,))
        conn.commit()
        
        # Show main menu
        bot.delete_message(call.message.chat.id, call.message.message_id)
        show_main_menu(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ لم تشترك في جميع القنوات المطلوبة!", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "search")
def search_menu(call):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🎥 فيديو", callback_data="search_video"),
        types.InlineKeyboardButton("🖼️ صور", callback_data="search_image"),
        types.InlineKeyboardButton("🧩 أيقونات", callback_data="search_icon"),
        types.InlineKeyboardButton("🎨 رسومات", callback_data="search_art"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="اختر نوع البحث:",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data in ["search_video", "search_image", "search_icon", "search_art"])
def handle_search(call):
    search_type = call.data.split("_")[1]
    bot.answer_callback_query(call.id, "أدخل كلمة البحث:")
    
    msg = bot.send_message(call.message.chat.id, "أرسل كلمة البحث:")
    bot.register_next_step_handler(msg, process_search, search_type)

def process_search(message, search_type):
    try:
        query = message.text
        user_id = message.from_user.id
        update_activity(user_id)
        update_stats('total_searches')
        
        # Store current search data
        bot.current_search = {
            'type': search_type,
            'query': query,
            'results': [],
            'index': 0
        }
        
        # Fetch results based on type
        if search_type == 'video':
            results = search_pixabay(query, 'video')
        elif search_type == 'image':
            results = search_pixabay(query, 'photo')
        elif search_type == 'icon':
            results = search_iconfinder(query)
        else:  # art
            results = search_lumni(query)
        
        if not results:
            bot.send_message(user_id, "⚠️ لم يتم العثور على نتائج. حاول بكلمات أخرى.")
            return
        
        bot.current_search['results'] = results
        show_result(message.chat.id, 0)
    except Exception as e:
        bot.reply_to(message, f"حدث خطأ أثناء البحث: {str(e)}")
        print(f"Error in process_search: {e}")

def show_result(chat_id, index):
    result = bot.current_search['results'][index]
    search_type = bot.current_search['type']
    
    # Prepare navigation keyboard
    keyboard = types.InlineKeyboardMarkup()
    prev_btn = types.InlineKeyboardButton("«« السابق", callback_data=f"prev_{index}")
    next_btn = types.InlineKeyboardButton("»» التالي", callback_data=f"next_{index}")
    download_btn = types.InlineKeyboardButton("◤تحميل◥", callback_data=f"download_{index}")
    
    if index == 0:
        keyboard.add(next_btn, download_btn)
    elif index == len(bot.current_search['results']) - 1:
        keyboard.add(prev_btn, download_btn)
    else:
        keyboard.add(prev_btn, next_btn, download_btn)
    
    # Send result based on type
    if search_type in ['video', 'image']:
        if search_type == 'video':
            bot.send_video(chat_id, result['url'], reply_markup=keyboard)
        else:
            bot.send_photo(chat_id, result['url'], reply_markup=keyboard)
    else:
        bot.send_photo(chat_id, result['url'], reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('prev_', 'next_', 'download_')))
def handle_navigation(call):
    action, index = call.data.split('_')
    index = int(index)
    
    if action == 'prev':
        new_index = index - 1
    elif action == 'next':
        new_index = index + 1
    else:  # download
        result = bot.current_search['results'][index]
        search_type = bot.current_search['type']
        
        # Send to channel
        caption = f"تم التحميل بواسطة: @{call.from_user.username}\n"
        caption += f"نوع البحث: {search_type}\n"
        caption += f"الكلمة: {bot.current_search['query']}"
        
        if search_type == 'video':
            bot.send_video("@AWU87", result['url'], caption=caption)
        else:
            bot.send_photo("@AWU87", result['url'], caption=caption)
        
        # Update stats
        update_stats('total_downloads')
        
        # Update UI
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        bot.send_message(call.message.chat.id, "✅ تم التحميل بنجاح!\nلإجراء بحث جديد، أرسل /start")
        return
    
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_result(call.message.chat.id, new_index)

# API Search Functions - FIXED FOR VIDEOS
def search_pixabay(query, media_type):
    url = f"https://pixabay.com/api/?key={PIXABAY_API}&q={query}&per_page=20"
    if media_type == 'video':
        url += "&video=true"
    else:
        url += "&image_type=photo"
    
    response = requests.get(url)
    if response.status_code != 200:
        return []
    
    results = []
    data = response.json()
    
    if media_type == 'video':
        # For each video in the results
        for video in data['hits'][:10]:
            if 'videos' in video:
                # Look for the best quality available
                best_quality = None
                for quality in ['large', 'medium', 'small']:
                    if quality in video['videos']:
                        best_quality = quality
                        break
                
                if best_quality:
                    results.append({'url': video['videos'][best_quality]['url']})
    else:  # photo
        for photo in data['hits'][:10]:
            results.append({'url': photo['largeImageURL']})
    
    return results

def search_iconfinder(query):
    url = "https://api.iconfinder.com/v4/icons/search"
    headers = {
        "Authorization": f"Bearer {ICONFINDER_API}",
        "Accept": "application/json"
    }
    params = {
        "query": query,
        "count": 10,
        "premium": "false"
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        return []
    
    icons = response.json()['icons']
    results = []
    for icon in icons:
        if icon['raster_sizes'] and len(icon['raster_sizes'][0]['formats']) > 0:
            results.append({'url': icon['raster_sizes'][0]['formats'][0]['preview_url']})
    return results

def search_lumni(query):
    url = "https://api.lummi.ai/api/v1/images"
    headers = {
        "Authorization": f"Bearer {LUMNI_API}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
        "num_results": 10
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        return []
    
    results = []
    for img in response.json()['images']:
        results.append({'url': img['url']})
    return results

# About Developer
@bot.callback_query_handler(func=lambda call: call.data == "about_dev")
def about_developer(call):
    about_text = """
🔧 المطوّر @Ili8_8ill

شاب يمني دخل عالم البرمجة والبوتات في تيليجرام وهو مليان شغف وحماس. بدأ يتعلّم خطوة خطوة، من الصفر، وكل يوم يزيد خبرته من خلال التجربة والمشاريع الصغيرة اللي لها فايدة حقيقية.

ما شاء الله عليه، يتميّز بـ:  
• حبّه للاستكشاف والتعلّم بنفسه  
• قدرته على بناء بوتات بسيطة تخدم الناس  
• استخدامه لأدوات مثل BotFather وPython  
• تقبّله للنقد وسعيه للتطوير المستمر

📢 القنوات اللي يشتغل فيها:  
@crazys7 – @AWU87

🌟 رؤيته:  
ماشي في طريق البرمجة من الأساسيات نحو الاحتراف، بخطوات ثابتة وطموح كبير إنه يصنع بوتات تخدم الناس وتضيف قيمة حقيقية.

📬 للتواصل:  
تابع حسابه: @Ili8_8ill
"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=about_text,
        reply_markup=keyboard
    )

# Statistics
@bot.callback_query_handler(func=lambda call: call.data == "stats")
def show_stats(call):
    stats = get_stats()
    text = f"""
📊 إحصائيات البوت:

👥 عدد المستخدمين الإجمالي: {stats[0]}
🔍 عدد عمليات البحث: {stats[1]}
💾 عدد التحميلات: {stats[2]}
⚡ المشتركين النشطين: {stats[3]}
"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=keyboard
    )

# Admin Panel
@bot.callback_query_handler(func=lambda call: call.data == "admin_panel" and is_admin(call.from_user.id))
def admin_panel(call):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton("🚫 حظر عضو", callback_data="ban_user"),
        types.InlineKeyboardButton("✅ إلغاء الحظر", callback_data="unban_user"),
        types.InlineKeyboardButton("🛑 إيقاف البوت", callback_data="stop_bot"),
        types.InlineKeyboardButton("🔄 تشغيل البوت", callback_data="start_bot"),
        types.InlineKeyboardButton("💰 الوضع المدفوع", callback_data="premium_mode"),
        types.InlineKeyboardButton("📊 الإحصائيات المتقدمة", callback_data="advanced_stats"),
        types.InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")
    )
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="🧑‍💼 لوحة إدارة البوت:",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "advanced_stats" and is_admin(call.from_user.id))
def advanced_stats(call):
    # Get user stats
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
    banned_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
    premium_users = c.fetchone()[0]
    
    # Get bot settings
    c.execute("SELECT is_active, is_premium_mode, stop_message FROM bot_settings WHERE id = 1")
    settings = c.fetchone()
    
    stats_text = f"""
📈 إحصائيات متقدمة:

👤 إجمالي المستخدمين: {total_users}
🚫 المحظورين: {banned_users}
💎 المميزين: {premium_users}

⚙️ إعدادات البوت:
{'🟢 نشط' if settings[0] else '🔴 متوقف'}
{'💰 الوضع المدفوع مفعل' if settings[1] else '🆓 النسخة المجانية'}
📝 رسالة التوقف: {settings[2] or 'غير معينة'}
"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel"))
    
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=stats_text,
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "premium_mode" and is_admin(call.from_user.id))
def toggle_premium_mode(call):
    c.execute("SELECT is_premium_mode FROM bot_settings WHERE id = 1")
    current_mode = c.fetchone()[0]
    new_mode = 0 if current_mode else 1
    
    c.execute("UPDATE bot_settings SET is_premium_mode = ? WHERE id = 1", (new_mode,))
    conn.commit()
    
    bot.answer_callback_query(call.id, f"تم {'تفعيل' if new_mode else 'إلغاء'} الوضع المدفوع")

@bot.callback_query_handler(func=lambda call: call.data in ["stop_bot", "start_bot"] and is_admin(call.from_user.id))
def toggle_bot_status(call):
    new_status = 0 if call.data == "stop_bot" else 1
    
    if new_status == 0:  # Stopping bot
        msg = bot.send_message(call.message.chat.id, "أرسل رسالة التوقف:")
        bot.register_next_step_handler(msg, set_stop_message)
    else:
        c.execute("UPDATE bot_settings SET is_active = ? WHERE id = 1", (new_status,))
        conn.commit()
        bot.answer_callback_query(call.id, "تم تشغيل البوت بنجاح")

def set_stop_message(message):
    stop_msg = message.text
    c.execute("UPDATE bot_settings SET is_active = 0, stop_message = ? WHERE id = 1", (stop_msg,))
    conn.commit()
    bot.send_message(message.chat.id, "تم إيقاف البوت بنجاح مع تعيين رسالة التوقف")

# Back to main menu
@bot.callback_query_handler(func=lambda call: call.data == "main_menu")
def back_to_main(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    show_main_menu(call.message)

# Run the bot with skip_pending to avoid conflicts
if __name__ == "__main__":
    print("Starting bot with skip_pending=True...")
    bot.infinity_polling(skip_pending=True)