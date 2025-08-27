import os
import json
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import sqlite3
from datetime import datetime, timedelta
import time
import threading
from apscheduler.schedulers.background import BackgroundScheduler

# إعدادات البوت
BOT_TOKEN = "7545979856:AAH4YXddSwBWwgvjQPxY8tGarBgptMhy0p0"
ADMIN_ID = 6837782553
MANDATORY_CHANNEL = "@iIl337"  # قناة الاشتراك الإجباري

# إعداد Gemini API
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_API_KEY = "AIzaSyD3w0ZtC-GOvOVVlUxb_l0ayRAVsar64FI"

# تهيئة البوت
bot = telebot.TeleBot(BOT_TOKEN)

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        is_banned INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول القنوات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS channels (
        channel_id INTEGER PRIMARY KEY,
        channel_username TEXT,
        channel_title TEXT,
        owner_id INTEGER,
        content_type TEXT,
        post_time TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (owner_id) REFERENCES users (user_id)
    )
    ''')
    
    # جدول المحتوى
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content_type TEXT,
        prompt TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # إدخال أنواع المحتوى الافتراضية
    default_content = [
        ("عبارات اسلامية", "اكتب لي آية قرآنية قصيرة وتحتها شرح للآية (ارسل الآية بدون اي تعليق او شرح)"),
        ("كبرياء وغرور", "اكتب لي عبارة مكونة من سطر واحد تدل على الثقة بالنفس والتعالي وتعظيم الذات (ارسل العبارة بدون تعليق او شرح)"),
        ("كوميديا سوداء", "اكتب لي عبارة مكونة من سطر واحد أو سطرين فقط مضحكة سوداوية وغير جارحة ولاكنها تعبر عن التعاسة (ارسل العبارة بدون اي شرح او تعليق)"),
        ("اذكار المسلم", "اكتب لي عبارة من اذكار المسلم وفقا للكتب السنية والقرآن (ارسل العبارة فقط وبدون شرح او تعليق)")
    ]
    
    cursor.executemany('INSERT OR IGNORE INTO content (content_type, prompt) VALUES (?, ?)', default_content)
    
    conn.commit()
    conn.close()

init_db()

# وظائف المساعدة لقاعدة البيانات
def get_db_connection():
    return sqlite3.connect('bot.db')

def check_user_exists(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user is not None

def add_user(user_id, username, first_name, last_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
                   (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()

def is_user_banned(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == 1

def get_user_channels(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT channel_id, channel_username, channel_title, content_type, post_time FROM channels WHERE owner_id = ? AND is_active = 1', (user_id,))
    channels = cursor.fetchall()
    conn.close()
    return channels

def add_channel(user_id, channel_username, channel_title, content_type, post_time):
    conn = get_db_connection()
    cursor = conn.cursor()
    # استخدام channel_username كمعرف افتراضي (يمكن تغييره لاحقًا)
    channel_id = abs(hash(channel_username)) % (10 ** 8)  # إنشاء معرف فريد للقناة
    cursor.execute('INSERT INTO channels (channel_id, channel_username, channel_title, owner_id, content_type, post_time) VALUES (?, ?, ?, ?, ?, ?)',
                   (channel_id, channel_username, channel_title, user_id, content_type, post_time))
    conn.commit()
    conn.close()
    return channel_id

def get_all_channels():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT channel_id, channel_username, channel_title, owner_id, content_type, post_time FROM channels WHERE is_active = 1')
    channels = cursor.fetchall()
    conn.close()
    return channels

def get_content_types():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT content_type FROM content')
    content_types = [row[0] for row in cursor.fetchall()]
    conn.close()
    return content_types

def get_prompt_for_content_type(content_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT prompt FROM content WHERE content_type = ?', (content_type,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else ""

# وظائف Gemini AI
def generate_content(prompt):
    headers = {
        'Content-Type': 'application/json',
        'X-goog-api-key': GEMINI_API_KEY
    }
    
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(GEMINI_API_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Error generating content: {e}")
        return "عذرًا، حدث خطأ أثناء توليد المحتوى. يرجى المحاولة مرة أخرى."

# وظائف البوت
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # التحقق من الاشتراك الإجباري
    try:
        chat_member = bot.get_chat_member(MANDATORY_CHANNEL, user_id)
        if chat_member.status not in ['member', 'administrator', 'creator']:
            bot.send_message(message.chat.id, f"يجب عليك الانضمام إلى قناتنا أولاً: {MANDATORY_CHANNEL}")
            return
    except:
        bot.send_message(message.chat.id, f"يجب عليك الانضمام إلى قناتنا أولاً: {MANDATORY_CHANNEL}")
        return
    
    # إضافة المستخدم إلى قاعدة البيانات
    add_user(user_id, username, first_name, last_name)
    
    # التحقق من حظر المستخدم
    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "تم حظرك من استخدام البوت.")
        return
    
    # عرض قائمة الخيارات
    show_main_menu(message.chat.id)

def show_main_menu(chat_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("توليد عبارة 🐒"))
    markup.add(KeyboardButton("إعداد البوت 🐶"))
    
    if chat_id == ADMIN_ID:
        markup.add(KeyboardButton("لوحة التحكم (المدير) 🦅"))
    
    bot.send_message(chat_id, "مرحبًا! اختر من الخيارات أدناه:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "توليد عبارة 🐒")
def show_content_types(message):
    if is_user_banned(message.from_user.id):
        bot.send_message(message.chat.id, "تم حظرك من استخدام البوت.")
        return
    
    content_types = get_content_types()
    markup = InlineKeyboardMarkup()
    
    for content_type in content_types:
        markup.add(InlineKeyboardButton(content_type, callback_data=f"generate_{content_type}"))
    
    bot.send_message(message.chat.id, "اختر نوع العبارة التي تريد توليدها:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "إعداد البوت 🐶")
def show_bot_settings(message):
    if is_user_banned(message.from_user.id):
        bot.send_message(message.chat.id, "تم حظرك من استخدام البوت.")
        return
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("إضافة قناة 🐕", callback_data="add_channel"))
    markup.add(InlineKeyboardButton("قنواتي 🐐", callback_data="my_channels"))
    
    bot.send_message(message.chat.id, "إعدادات البوت:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "لوحة التحكم (المدير) 🦅" and message.from_user.id == ADMIN_ID)
def show_admin_panel(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("إحصائيات 📊", callback_data="admin_stats"))
    markup.add(InlineKeyboardButton("إدارة المستخدمين 👥", callback_data="admin_users"))
    markup.add(InlineKeyboardButton("إدارة القنوات 📺", callback_data="admin_channels"))
    markup.add(InlineKeyboardButton("إشعار للمستخدمين 📢", callback_data="admin_broadcast"))
    
    bot.send_message(message.chat.id, "لوحة تحكم المدير:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    
    if is_user_banned(user_id):
        bot.answer_callback_query(call.id, "تم حظرك من استخدام البوت.")
        return
    
    if call.data.startswith("generate_"):
        content_type = call.data.replace("generate_", "")
        prompt = get_prompt_for_content_type(content_type)
        generated_content = generate_content(prompt)
        
        # حفظ المحتوى المولد مؤقتًا للتنقل بين العبارات
        # (هذا تنفيذ مبسط، في الإصدار النهائي يجب حفظ المحتوى في قاعدة البيانات)
        
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("السابق ◀️", callback_data=f"prev_{content_type}"),
            InlineKeyboardButton("التالي ▶️", callback_data=f"next_{content_type}"),
            InlineKeyboardButton("نشر في قناتي 📣", callback_data=f"publish_{content_type}")
        )
        
        bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, 
                             text=generated_content, reply_markup=markup)
    
    elif call.data == "add_channel":
        msg = bot.send_message(call.message.chat.id, "أرسل معرف القناة (يجب أن يكون البوت مشرفًا فيها):")
        bot.register_next_step_handler(msg, process_channel_username)
    
    elif call.data == "my_channels":
        user_channels = get_user_channels(user_id)
        if not user_channels:
            bot.send_message(call.message.chat.id, "ليس لديك أي قنوات مضافّة.")
            return
        
        channels_text = "قنواتك:\n\n"
        for channel in user_channels:
            channels_text += f"- {channel[2]} (@{channel[1]})\n  نوع المحتوى: {channel[3]}\n  وقت النشر: {channel[4]}\n\n"
        
        bot.send_message(call.message.chat.id, channels_text)
    
    elif call.data.startswith("admin_"):
        if user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "ليس لديك صلاحية للوصول إلى هذه الوظيفة.")
            return
        
        if call.data == "admin_stats":
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM users')
            users_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM channels')
            channels_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = 1')
            banned_count = cursor.fetchone()[0]
            
            conn.close()
            
            stats_text = f"إحصائيات البوت:\n\n"
            stats_text += f"عدد المستخدمين: {users_count}\n"
            stats_text += f"عدد القنوات: {channels_count}\n"
            stats_text += f"عدد المستخدمين المحظورين: {banned_count}"
            
            bot.send_message(call.message.chat.id, stats_text)
        
        elif call.data == "admin_users":
            # عرض قائمة المستخدمين للإدارة
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, username, first_name, is_banned FROM users ORDER BY created_at DESC LIMIT 20')
            users = cursor.fetchall()
            conn.close()
            
            users_text = "آخر 20 مستخدم:\n\n"
            for user in users:
                status = "محظور" if user[3] == 1 else "نشط"
                users_text += f"ID: {user[0]}\nUsername: @{user[1]}\nالاسم: {user[2]}\nالحالة: {status}\n\n"
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("حظر مستخدم 🚫", callback_data="ban_user"))
            markup.add(InlineKeyboardButton("رفع حظر مستخدم ✅", callback_data="unban_user"))
            
            bot.send_message(call.message.chat.id, users_text, reply_markup=markup)
        
        elif call.data == "admin_channels":
            # عرض قائمة القنوات للإدارة
            channels = get_all_channels()
            
            channels_text = "جميع القنوات:\n\n"
            for channel in channels:
                channels_text += f"ID: {channel[0]}\nالقناة: @{channel[1]}\nالمالك: {channel[3]}\nنوع المحتوى: {channel[4]}\nوقت النشر: {channel[5]}\n\n"
            
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("تعطيل قناة ⏸️", callback_data="disable_channel"))
            markup.add(InlineKeyboardButton("تمكين قناة ▶️", callback_data="enable_channel"))
            
            bot.send_message(call.message.chat.id, channels_text, reply_markup=markup)
        
        elif call.data == "admin_broadcast":
            msg = bot.send_message(call.message.chat.id, "أرسل الرسالة التي تريد نشرها لجميع المستخدمين:")
            bot.register_next_step_handler(msg, process_broadcast_message)

def process_channel_username(message):
    user_id = message.from_user.id
    channel_username = message.text.replace('@', '')
    
    try:
        # محاولة الحصول على معلومات القناة
        chat = bot.get_chat(f"@{channel_username}")
        
        # التحقق من أن البوت مشرف في القناة
        bot_member = bot.get_chat_member(chat.id, bot.get_me().id)
        if bot_member.status not in ['administrator', 'creator']:
            bot.send_message(message.chat.id, "يجب أن يكون البوت مشرفًا في القناة أولاً.")
            return
        
        # عرض خيارات نوع المحتوى
        content_types = get_content_types()
        markup = InlineKeyboardMarkup()
        
        for content_type in content_types:
            markup.add(InlineKeyboardButton(content_type, callback_data=f"setcontent_{channel_username}_{content_type}"))
        
        bot.send_message(message.chat.id, "اختر نوع المحتوى للقناة:", reply_markup=markup)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"حدث خطأ: {e}. تأكد من أن البوت مشرف في القناة وأن المعرف صحيح.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("setcontent_"))
def set_channel_content(call):
    data_parts = call.data.split("_")
    channel_username = data_parts[1]
    content_type = "_".join(data_parts[2:])
    
    msg = bot.send_message(call.message.chat.id, "أرسل وقت النشر اليومي (مثل: 08:00):")
    bot.register_next_step_handler(msg, lambda m: process_post_time(m, channel_username, content_type))

def process_post_time(message, channel_username, content_type):
    post_time = message.text
    
    try:
        # التحقق من صيغة الوقت
        datetime.strptime(post_time, "%H:%M")
        
        # إضافة القناة إلى قاعدة البيانات
        try:
            chat = bot.get_chat(f"@{channel_username}")
            channel_id = add_channel(message.from_user.id, channel_username, chat.title, content_type, post_time)
            
            bot.send_message(message.chat.id, f"تم إضافة القناة @{channel_username} بنجاح!\nنوع المحتوى: {content_type}\nوقت النشر: {post_time}")
        
        except Exception as e:
            bot.send_message(message.chat.id, f"حدث خطأ أثناء إضافة القناة: {e}")
    
    except ValueError:
        bot.send_message(message.chat.id, "صيغة الوقت غير صحيحة. يرجى استخدام الصيغة HH:MM (مثل: 08:00)")
        return

def process_broadcast_message(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    # الحصول على جميع المستخدمين
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE is_banned = 0')
    users = cursor.fetchall()
    conn.close()
    
    # إرسال الرسالة لجميع المستخدمين
    success_count = 0
    for user in users:
        try:
            bot.send_message(user[0], f"إشعار من الإدارة:\n\n{message.text}")
            success_count += 1
        except:
            continue
    
    bot.send_message(message.chat.id, f"تم إرسال الإشعار إلى {success_count} مستخدم.")

# جدولة النشر التلقائي
def schedule_posts():
    scheduler = BackgroundScheduler()
    
    def post_to_channel():
        now = datetime.now().strftime("%H:%M")
        channels = get_all_channels()
        
        for channel in channels:
            if channel[5] == now:  # وقت النشر
                content_type = channel[4]
                prompt = get_prompt_for_content_type(content_type)
                content = generate_content(prompt)
                
                try:
                    bot.send_message(channel[1], content)
                    print(f"تم النشر في القناة @{channel[1]} الساعة {now}")
                except Exception as e:
                    print(f"فشل النشر في القناة @{channel[1]}: {e}")
    
    # جدولة المهمة لت run كل دقيقة
    scheduler.add_job(post_to_channel, 'interval', minutes=1)
    scheduler.start()

# بدء جدولة النشر في thread منفصل
scheduler_thread = threading.Thread(target=schedule_posts)
scheduler_thread.daemon = True
scheduler_thread.start()

# تشغيل البوت
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
