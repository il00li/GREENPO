import asyncio
from telethon import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import sqlite3
import os
import random
import threading

# إعدادات Telethon
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'

# إعدادات بوت التلجرام
BOT_TOKEN = '7545979856:AAH4YXddSwBWwgvjQPxY8tGarBgptMhy0p0'
bot = telebot.TeleBot(BOT_TOKEN)

# رموز تعبيرية عشوائية
EMOJIS = ['🦗', '🐌', '🐗', '🦅', '🦃', '🦆', '🐐', '🦇', '🐕', '🐶']

# تخزين جلسات المستخدمين
user_sessions = {}
transfer_tasks = {}

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('member_transfer.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        phone TEXT,
        session_file TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        source_group TEXT,
        target_group TEXT,
        members_count INTEGER,
        success_count INTEGER,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# وظائف المساعدة لقاعدة البيانات
def get_db_connection():
    return sqlite3.connect('member_transfer.db')

def save_user_session(user_id, phone, session_file):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, phone, session_file) VALUES (?, ?, ?)',
                   (user_id, phone, session_file))
    conn.commit()
    conn.close()

def get_user_session(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT phone, session_file FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def save_transfer_record(user_id, source_group, target_group, members_count, success_count, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO transfers (user_id, source_group, target_group, members_count, success_count, status) VALUES (?, ?, ?, ?, ?, ?)',
                   (user_id, source_group, target_group, members_count, success_count, status))
    conn.commit()
    conn.close()

# وظائف Telethon
async def get_group_members(client, group_username):
    try:
        entity = await client.get_entity(group_username)
        participants = await client.get_participants(entity)
        return [participant for participant in participants if not participant.bot and not participant.is_self]
    except Exception as e:
        print(f"Error getting group members: {e}")
        return []

async def add_member_to_group(client, user, target_group):
    try:
        # الحصول على كيان المجموعة الهدف
        target_entity = await client.get_entity(target_group)
        
        # إضافة العضو مباشرة إلى المجموعة/القناة
        await client(InviteToChannelRequest(
            channel=target_entity,
            users=[user]
        ))
        return True
    except Exception as e:
        print(f"Error adding member {user.id} to {target_group}: {e}")
        return False

# دالة لإزالة أزرار الكيبورد
def remove_keyboard(chat_id, text="تم إزالة الأزرار"):
    bot.send_message(chat_id, text, reply_markup=ReplyKeyboardRemove())

# دالة لعرض القائمة الرئيسية باستخدام Inline Keyboard
def show_main_menu(chat_id):
    remove_keyboard(chat_id, "اختر من الخيارات التالية:")
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"تسجيل {random.choice(EMOJIS)}", callback_data="register"))
    markup.add(InlineKeyboardButton(f"نقل الأعضاء {random.choice(EMOJIS)}", callback_data="transfer"))
    markup.add(InlineKeyboardButton(f"حالة النقل {random.choice(EMOJIS)}", callback_data="status"))
    
    bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=markup)

# معالجات البوت
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    show_main_menu(user_id)

@bot.callback_query_handler(func=lambda call: call.data == "register")
def request_phone(call):
    user_id = call.from_user.id
    msg = bot.send_message(user_id, "أرسل رقم هاتفك (مثل: +1234567890):")
    bot.register_next_step_handler(msg, process_phone)

def process_phone(message):
    user_id = message.from_user.id
    phone = message.text
    
    # حفظ رقم الهاتف
    session_file = f"sessions/{user_id}.session"
    save_user_session(user_id, phone, session_file)
    
    # بدء عملية تسجيل الدخول في thread منفصل
    threading.Thread(target=run_async_login, args=(user_id, phone, session_file)).start()
    
    bot.send_message(user_id, "تم حفظ معلوماتك. جاري إرسال رمز التحقق...")

def run_async_login(user_id, phone, session_file):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(login_user(user_id, phone, session_file))
    loop.close()

async def login_user(user_id, phone, session_file):
    client = TelegramClient(session_file, API_ID, API_HASH)
    
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        user_sessions[user_id] = {'client': client, 'phone': phone, 'step': 'code'}
        bot.send_message(user_id, "تم إرسال رمز التحقق. أرسل الرمز الآن.")

@bot.callback_query_handler(func=lambda call: call.data == "transfer")
def request_source_group(call):
    user_id = call.from_user.id
    
    # التحقق من أن المستخدم سجل الدخول
    session_info = get_user_session(user_id)
    if not session_info:
        bot.send_message(user_id, "يجب عليك تسجيل الدخول أولاً.")
        show_main_menu(user_id)
        return
    
    msg = bot.send_message(user_id, "أرسل معرف المجموعة المصدر (مثل: @group_username):")
    bot.register_next_step_handler(msg, process_source_group)

def process_source_group(message):
    user_id = message.from_user.id
    source_group = message.text
    
    msg = bot.send_message(user_id, "أرسل معرف المجموعة الهدف (القناة أو المجموعة التي تريد نقل الأعضاء إليها):")
    bot.register_next_step_handler(msg, lambda m: process_target_group(m, source_group))

def process_target_group(message, source_group):
    user_id = message.from_user.id
    target_group = message.text
    
    # البدء في عملية نقل الأعضاء
    bot.send_message(user_id, "جاري بدء عملية نقل الأعضاء...")
    
    # تشغيل عملية النقل في thread منفصل
    threading.Thread(target=run_async_transfer, args=(user_id, source_group, target_group)).start()

def run_async_transfer(user_id, source_group, target_group):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(transfer_members(user_id, source_group, target_group))
    loop.close()

async def transfer_members(user_id, source_group, target_group):
    session_info = get_user_session(user_id)
    if not session_info:
        bot.send_message(user_id, "لم يتم العثور على معلومات الجلسة. يرجى تسجيل الدخول أولاً.")
        return
    
    phone, session_file = session_info
    
    client = TelegramClient(session_file, API_ID, API_HASH)
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            bot.send_message(user_id, "لم يتم تسجيل الدخول بعد. يرجى إكمال عملية التسجيل.")
            return
        
        # الحصول على أعضاء المجموعة المصدر
        bot.send_message(user_id, "جاري جلب قائمة الأعضاء من المجموعة المصدر...")
        members = await get_group_members(client, source_group)
        
        if not members:
            bot.send_message(user_id, "لم يتم العثور على أعضاء أو لا يمكن الوصول إلى المجموعة.")
            return
        
        bot.send_message(user_id, f"تم العثور على {len(members)} عضو. جاري بدء عملية النقل...")
        
        success_count = 0
        fail_count = 0
        
        for i, member in enumerate(members):
            try:
                # إضافة العضو إلى المجموعة الهدف مباشرة
                if await add_member_to_group(client, member, target_group):
                    success_count += 1
                else:
                    fail_count += 1
                
                # إرسال تحديث كل 5 أعضاء
                if (i + 1) % 5 == 0:
                    bot.send_message(user_id, f"تم معالجة {i + 1}/{len(members)} عضو: {success_count} نجاح, {fail_count} فشل")
                
                # تأجيل بين كل عملية لإظهار السلاسة
                await asyncio.sleep(random.uniform(2, 5))
                
            except Exception as e:
                print(f"Error transferring member {member.id}: {e}")
                fail_count += 1
        
        # حفظ سجل النقل
        save_transfer_record(user_id, source_group, target_group, len(members), success_count, "مكتمل")
        
        # إرسال النتيجة النهائية
        bot.send_message(user_id, f"اكتملت عملية النقل:\nالنجاح: {success_count}\nالفشل: {fail_count}")
        
    except Exception as e:
        bot.send_message(user_id, f"حدث خطأ أثناء عملية النقل: {e}")
        save_transfer_record(user_id, source_group, target_group, len(members) if 'members' in locals() else 0, 
                            success_count if 'success_count' in locals() else 0, f"فشل: {e}")
    finally:
        await client.disconnect()
        show_main_menu(user_id)

@bot.callback_query_handler(func=lambda call: call.data == "status")
def show_transfer_status(call):
    user_id = call.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT source_group, target_group, members_count, success_count, status, created_at FROM transfers WHERE user_id = ? ORDER BY created_at DESC LIMIT 5', (user_id,))
    transfers = cursor.fetchall()
    conn.close()
    
    if not transfers:
        bot.send_message(user_id, "لا توجد عمليات نقل سابقة.")
        return
    
    status_text = "آخر 5 عمليات نقل:\n\n"
    for transfer in transfers:
        status_text += f"من: {transfer[0]}\nإلى: {transfer[1]}\nالمحاولة: {transfer[2]}\nالنجاح: {transfer[3]}\nالحالة: {transfer[4]}\nالتاريخ: {transfer[5]}\n\n"
    
    bot.send_message(user_id, status_text)
    show_main_menu(user_id)

# معالجة رموز التحقق
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # إذا كان المستخدم في مرحلة إدخال الرمز
    if user_id in user_sessions and user_sessions[user_id].get('step') == 'code':
        threading.Thread(target=run_async_verify, args=(user_id, text)).start()

def run_async_verify(user_id, code):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(verify_code(user_id, code))
    loop.close()

async def verify_code(user_id, code):
    if user_id not in user_sessions:
        bot.send_message(user_id, "لم يتم العثور على جلسة التسجيل. يرجى البدء من جديد.")
        return
    
    session_info = user_sessions[user_id]
    client = session_info['client']
    phone = session_info['phone']
    
    try:
        await client.sign_in(phone, code)
        bot.send_message(user_id, "تم تسجيل الدخول بنجاح!")
        user_sessions[user_id]['step'] = 'completed'
        show_main_menu(user_id)
    except Exception as e:
        bot.send_message(user_id, f"فشل تسجيل الدخول: {e}")

# التأكد من وجود مجلد الجلسات
if not os.path.exists('sessions'):
    os.makedirs('sessions')

# تشغيل البوت
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
