import asyncio
from telethon import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
import sqlite3
import os
import random
import threading

# إعدادات Telethon
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'

# إعدادات بوت التلجرام
BOT_TOKEN = '8300609210:AAGHCu5Un2UDMEnxy4Oh-QCY1_kVDm3S6Ro'
bot = telebot.TeleBot(BOT_TOKEN)

# رموز تعبيرية عشوائية
EMOJIS = ['🦗', '🐌', '🐗', '🦅', '🦃', '🦆', '🐐', '🦇', '🐕', '🐶']

# جلسة Telethon الجاهزة
SESSION_STRING = "1BJWap1wBu56xGro9VFUD1nPK6l1gVBxtfqacLwevl8n54WuZdL9_AJL-VLwYVMkYOP7oZlQ7VVqvcqu1M5k3uxi00Syd_skjjnpbG6LUZMAMmPvoRq9i8SnfTDveV33cT4TwbGO2uOw_xHqE_mY6wrK3vTv9-i89-pY1YK1-yoKGoMiCHax0F0UCoMAq6EkXrF5RDOXVoQXSyMYaKrocQz1WK6FxnI2s9ZCw5e05KUUhXcitlED0FKZIpNPb3dluV9ohKEZ3MSW2zTTc9K_zXbC1uK2McR1ML1VPYJG2H95BCEE7LTuQCCfZS6shDkWo0yvCjbf-viXGbQPyiejL058pCfpUcNA="

# تخزين العمليات النشطة
active_transfers = {}

# تهيئة قاعدة البيانات
def init_db():
    conn = sqlite3.connect('member_transfer.db')
    cursor = conn.cursor()
    
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
    markup.add(InlineKeyboardButton(f"نقل الأعضاء {random.choice(EMOJIS)}", callback_data="transfer"))
    markup.add(InlineKeyboardButton(f"حالة النقل {random.choice(EMOJIS)}", callback_data="status"))
    markup.add(InlineKeyboardButton(f"إلغاء العملية {random.choice(EMOJIS)}", callback_data="cancel"))
    
    bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=markup)

# معالجات البوت
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    show_main_menu(user_id)

@bot.callback_query_handler(func=lambda call: call.data == "transfer")
def request_source_group(call):
    user_id = call.from_user.id
    
    # إلغاء أي عملية نقل نشطة سابقة
    if user_id in active_transfers:
        del active_transfers[user_id]
    
    msg = bot.send_message(user_id, "أرسل معرف المجموعة المصدر (مثل: @group_username):")
    bot.register_next_step_handler(msg, process_source_group)

def process_source_group(message):
    user_id = message.from_user.id
    source_group = message.text.replace('@', '')
    
    # حفظ المجموعة المصدر
    active_transfers[user_id] = {'source_group': source_group}
    
    msg = bot.send_message(user_id, "أرسل معرف المجموعة الهدف (القناة أو المجموعة التي تريد نقل الأعضاء إليها):")
    bot.register_next_step_handler(msg, process_target_group)

def process_target_group(message):
    user_id = message.from_user.id
    target_group = message.text.replace('@', '')
    
    # حفظ المجموعة الهدف
    if user_id in active_transfers:
        active_transfers[user_id]['target_group'] = target_group
    
    # تأكيد البدء في عملية النقل
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton(f"نعم، ابدأ النقل {random.choice(EMOJIS)}", callback_data="confirm_transfer"))
    markup.add(InlineKeyboardButton(f"لا، إلغاء {random.choice(EMOJIS)}", callback_data="cancel_transfer"))
    
    bot.send_message(user_id, 
                    f"هل تريد بدء نقل الأعضاء من @{active_transfers[user_id]['source_group']} إلى @{target_group}؟",
                    reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "confirm_transfer")
def confirm_transfer(call):
    user_id = call.from_user.id
    
    if user_id not in active_transfers:
        bot.send_message(user_id, "لم يتم العثور على معلومات النقل. يرجى البدء من جديد.")
        show_main_menu(user_id)
        return
    
    source_group = active_transfers[user_id]['source_group']
    target_group = active_transfers[user_id]['target_group']
    
    # البدء في عملية نقل الأعضاء
    bot.send_message(user_id, "جاري بدء عملية نقل الأعضاء...")
    
    # تشغيل عملية النقل في thread منفصل
    threading.Thread(target=run_async_transfer, args=(user_id, source_group, target_group)).start()

@bot.callback_query_handler(func=lambda call: call.data == "cancel_transfer")
def cancel_transfer(call):
    user_id = call.from_user.id
    
    if user_id in active_transfers:
        del active_transfers[user_id]
    
    bot.send_message(user_id, "تم إلغاء عملية النقل.")
    show_main_menu(user_id)

def run_async_transfer(user_id, source_group, target_group):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(transfer_members(user_id, source_group, target_group))
    loop.close()

async def transfer_members(user_id, source_group, target_group):
    try:
        # إنشاء العميل باستخدام الجلسة الجاهزة
        client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        
        await client.connect()
        
        if not await client.is_user_authorized():
            bot.send_message(user_id, "❌ الجلسة غير صالحة. يرجى تحديث الجلسة.")
            show_main_menu(user_id)
            return
        
        # الحصول على أعضاء المجموعة المصدر
        bot.send_message(user_id, "🔍 جاري جلب قائمة الأعضاء من المجموعة المصدر...")
        members = await get_group_members(client, source_group)
        
        if not members:
            bot.send_message(user_id, "❌ لم يتم العثور على أعضاء أو لا يمكن الوصول إلى المجموعة.")
            show_main_menu(user_id)
            return
        
        bot.send_message(user_id, f"✅ تم العثور على {len(members)} عضو. جاري بدء عملية النقل...")
        
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
                    bot.send_message(user_id, f"📊 تم معالجة {i + 1}/{len(members)} عضو: {success_count} نجاح, {fail_count} فشل")
                
                # تأجيل بين كل عملية لإظهار السلاسة
                await asyncio.sleep(random.uniform(2, 5))
                
            except Exception as e:
                print(f"Error transferring member {member.id}: {e}")
                fail_count += 1
        
        # حفظ سجل النقل
        save_transfer_record(user_id, source_group, target_group, len(members), success_count, "مكتمل")
        
        # إرسال النتيجة النهائية
        bot.send_message(user_id, f"✅ اكتملت عملية النقل:\nالنجاح: {success_count}\nالفشل: {fail_count}")
        
    except Exception as e:
        bot.send_message(user_id, f"❌ حدث خطأ أثناء عملية النقل: {e}")
        save_transfer_record(user_id, source_group, target_group, len(members) if 'members' in locals() else 0, 
                            success_count if 'success_count' in locals() else 0, f"فشل: {e}")
    finally:
        if 'client' in locals():
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
        bot.send_message(user_id, "📭 لا توجد عمليات نقل سابقة.")
        return
    
    status_text = "📊 آخر 5 عمليات نقل:\n\n"
    for transfer in transfers:
        status_text += f"من: {transfer[0]}\nإلى: {transfer[1]}\nالمحاولة: {transfer[2]}\nالنجاح: {transfer[3]}\nالحالة: {transfer[4]}\nالتاريخ: {transfer[5]}\n\n"
    
    bot.send_message(user_id, status_text)
    show_main_menu(user_id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel")
def cancel_operation(call):
    user_id = call.from_user.id
    
    if user_id in active_transfers:
        del active_transfers[user_id]
    
    bot.send_message(user_id, "✅ تم إلغاء العملية الحالية.")
    show_main_menu(user_id)

# معالجة أي رسائل أخرى
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = message.from_user.id
    show_main_menu(user_id)

# التأكد من وجود مجلد الجلسات
if not os.path.exists('sessions'):
    os.makedirs('sessions')

# تشغيل البوت
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling() 
