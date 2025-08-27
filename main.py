import asyncio
from telethon import TelegramClient, events
from telethon.tl.functions.channels import InviteToChannelRequest, GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch, InputPeerUser
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
import sqlite3
import os
import random

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

# معالجات البوت
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton(f"تسجيل {random.choice(EMOJIS)}"))
    markup.add(KeyboardButton(f"نقل {random.choice(EMOJIS)}"))
    markup.add(KeyboardButton(f"حالة {random.choice(EMOJIS)}"))
    
    bot.send_message(message.chat.id, "مرحبًا! اختر من الخيارات:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text.startswith("تسجيل"))
def request_phone(message):
    msg = bot.send_message(message.chat.id, "أرسل رقم هاتفك (مثل: +1234567890):")
    bot.register_next_step_handler(msg, process_phone)

def process_phone(message):
    user_id = message.from_user.id
    phone = message.text
    
    # حفظ رقم الهاتف
    session_file = f"sessions/{user_id}.session"
    save_user_session(user_id, phone, session_file)
    
    # بدء عملية تسجيل الدخول
    asyncio.run(login_user(user_id, phone, session_file))
    
    bot.send_message(message.chat.id, "تم الحفظ. سنرسل رمز التحقق قريبًا.")

async def login_user(user_id, phone, session_file):
    client = TelegramClient(session_file, API_ID, API_HASH)
    
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        user_sessions[user_id] = {'client': client, 'phone': phone, 'step': 'code'}
        bot.send_message(user_id, "تم إرسال رمز التحقق. أرسله الآن.")

@bot.message_handler(func=lambda message: message.text.startswith("نقل"))
def request_source_group(message):
    user_id = message.from_user.id
    
    # التحقق من أن المستخدم سجل الدخول
    session_info = get_user_session(user_id)
    if not session_info:
        bot.send_message(message.chat.id, "سجل الدخول أولاً.")
        return
    
    msg = bot.send_message(message.chat.id, "أرسل معرف المصدر (مثل: @group_username):")
    bot.register_next_step_handler(msg, process_source_group)

def process_source_group(message):
    user_id = message.from_user.id
    source_group = message.text
    
    msg = bot.send_message(message.chat.id, "أرسل معرف الهدف (القناة/المجموعة):")
    bot.register_next_step_handler(msg, lambda m: process_target_group(m, source_group))

def process_target_group(message, source_group):
    user_id = message.from_user.id
    target_group = message.text
    
    # البدء في عملية نقل الأعضاء
    bot.send_message(message.chat.id, "جاري البدء...")
    
    # تشغيل عملية النقل في الخلفية
    asyncio.run(transfer_members(user_id, source_group, target_group))

async def transfer_members(user_id, source_group, target_group):
    session_info = get_user_session(user_id)
    if not session_info:
        bot.send_message(user_id, "لم يتم العثور على الجلسة.")
        return
    
    phone, session_file = session_info
    
    client = TelegramClient(session_file, API_ID, API_HASH)
    
    try:
        await client.connect()
        
        if not await client.is_user_authorized():
            bot.send_message(user_id, "أكمل التسجيل أولاً.")
            return
        
        # الحصول على أعضاء المجموعة المصدر
        bot.send_message(user_id, "جاري جلب الأعضاء...")
        members = await get_group_members(client, source_group)
        
        if not members:
            bot.send_message(user_id, "لم يتم العثور على أعضاء.")
            return
        
        bot.send_message(user_id, f"تم العثور على {len(members)} عضو. جاري النقل...")
        
        success_count = 0
        fail_count = 0
        
        for member in members:
            try:
                # إضافة العضو إلى المجموعة الهدف مباشرة
                if await add_member_to_group(client, member, target_group):
                    success_count += 1
                    # تأجيل بين كل عملية إضافة
                    await asyncio.sleep(random.uniform(2, 5))
                else:
                    fail_count += 1
                
                # إرسال تحديث كل 5 أعضاء
                if (success_count + fail_count) % 5 == 0:
                    bot.send_message(user_id, f"تم: {success_count + fail_count}/{len(members)}")
                
            except Exception as e:
                print(f"Error transferring member {member.id}: {e}")
                fail_count += 1
        
        # حفظ سجل النقل
        save_transfer_record(user_id, source_group, target_group, len(members), success_count, "مكتمل")
        
        # إرسال النتيجة النهائية
        bot.send_message(user_id, f"تم بنجاح: {success_count}\nفشل: {fail_count}")
        
    except Exception as e:
        bot.send_message(user_id, f"خطأ: {e}")
        save_transfer_record(user_id, source_group, target_group, len(members) if 'members' in locals() else 0, success_count if 'success_count' in locals() else 0, f"فشل: {e}")
    finally:
        await client.disconnect()

@bot.message_handler(func=lambda message: message.text.startswith("حالة"))
def show_transfer_status(message):
    user_id = message.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT source_group, target_group, members_count, success_count, status, created_at FROM transfers WHERE user_id = ? ORDER BY created_at DESC LIMIT 5', (user_id,))
    transfers = cursor.fetchall()
    conn.close()
    
    if not transfers:
        bot.send_message(message.chat.id, "لا توجد عمليات سابقة.")
        return
    
    status_text = "آخر العمليات:\n\n"
    for transfer in transfers:
        status_text += f"من: {transfer[0]}\nإلى: {transfer[1]}\nالمحاولة: {transfer[2]}\nالنجاح: {transfer[3]}\nالحالة: {transfer[4]}\nالتاريخ: {transfer[5]}\n\n"
    
    bot.send_message(message.chat.id, status_text)

# معالجة رموز التحقق
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    user_id = message.from_user.id
    text = message.text.strip()
    
    # إذا كان المستخدم في مرحلة إدخال الرمز
    if user_id in user_sessions and user_sessions[user_id].get('step') == 'code':
        asyncio.run(verify_code(user_id, text))

async def verify_code(user_id, code):
    session_info = user_sessions[user_id]
    client = session_info['client']
    phone = session_info['phone']
    
    try:
        await client.sign_in(phone, code)
        bot.send_message(user_id, "تم التسجيل!")
        user_sessions[user_id]['step'] = 'completed'
    except Exception as e:
        bot.send_message(user_id, f"فشل: {e}")

# التأكد من وجود مجلد الجلسات
if not os.path.exists('sessions'):
    os.makedirs('sessions')

# تشغيل البوت
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
