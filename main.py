import os
import telebot
import subprocess
import time
import logging
import json
import base64
import random
import threading
import sqlite3
from flask import Flask, request
from waitress import serve
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# إعدادات البوت
BOT_TOKEN = '8038261927:AAFBGVndGTTwyB9WpeQXTxJDRyYg1z9njgg'
ADMIN_ID = 6689435577
BOT_USERNAME = '@HOZ7_BOT'
CHANNEL_ID = '-1003091756917'
WEBHOOK_URL = 'https://greenpo-1.onrender.com'

# إعدادات الملفات
UPLOAD_DIR = 'uploaded_files'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# قواعد البيانات
DB_FILE = 'bot_database.db'

# إعدادات الأداء - غير محدودة
MAX_CONCURRENT_PROCESSES = None  # غير محدود
PROCESS_TIMEOUT = None  # بدون timeout

# قائمة الرموز التعبيرية
RANDOM_EMOJIS = ['🦜', '🦚', '🐸', '🐊', '🐢', '🦎', '🐍', '🐲', '🐉', '🦕', '🐛', '🪲', '💐', '🦠', '🌲', '🌳', '🌵', '🌴', '🌾', '🌿', '🌱', '☘️', '🍀', '🪴', '🍃']

# تخزين العمليات النشطة
active_processes = {}
user_states = {}
banned_users = set()
process_executor = ThreadPoolExecutor(max_workers=None)  # غير محدود

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

# تهيئة البوت
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=100)

# إنشاء تطبيق Flask
app = Flask(__name__)

# تهيئة قاعدة البيانات
def init_database():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # جدول الملفات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_name TEXT,
                file_content BLOB,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # جدول المستخدمين المحظورين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول العمليات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processes (
                process_id TEXT PRIMARY KEY,
                user_id INTEGER,
                file_name TEXT,
                start_time TIMESTAMP,
                status TEXT DEFAULT 'running'
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully")
        
    except Exception as e:
        logging.error(f"Database initialization error: {e}")

# الحصول على رمز تعبيري عشوائي
def get_random_emoji():
    return random.choice(RANDOM_EMOJIS)

# حفظ الملف في قاعدة البيانات
def save_file_to_db(user_id, file_name, file_content):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO files (user_id, file_name, file_content, file_size)
            VALUES (?, ?, ?, ?)
        ''', (user_id, file_name, file_content, len(file_content)))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Error saving file to DB: {e}")
        return False

# تحميل الملف من قاعدة البيانات
def load_file_from_db(user_id, file_name):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT file_content FROM files 
            WHERE user_id = ? AND file_name = ? AND is_active = 1
        ''', (user_id, file_name))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    except Exception as e:
        logging.error(f"Error loading file from DB: {e}")
        return None

# الحصول على جميع الملفات من قاعدة البيانات
def get_all_files_from_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, file_name, file_content FROM files WHERE is_active = 1')
        files = cursor.fetchall()
        conn.close()
        
        return files
    except Exception as e:
        logging.error(f"Error getting files from DB: {e}")
        return []

# الحصول على ملفات مستخدم معين
def get_user_files_from_db(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT file_name FROM files WHERE user_id = ? AND is_active = 1', (user_id,))
        files = cursor.fetchall()
        conn.close()
        
        return [file[0] for file in files]
    except Exception as e:
        logging.error(f"Error getting user files from DB: {e}")
        return []

# حذف ملف من قاعدة البيانات
def delete_file_from_db(user_id, file_name):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE files SET is_active = 0 
            WHERE user_id = ? AND file_name = ?
        ''', (user_id, file_name))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Error deleting file from DB: {e}")
        return False

# حظر مستخدم
def ban_user(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('INSERT OR REPLACE INTO banned_users (user_id) VALUES (?)', (user_id,))
        
        conn.commit()
        conn.close()
        banned_users.add(user_id)
        return True
    except Exception as e:
        logging.error(f"Error banning user: {e}")
        return False

# إلغاء حظر مستخدم
def unban_user(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        if user_id in banned_users:
            banned_users.remove(user_id)
        return True
    except Exception as e:
        logging.error(f"Error unbanning user: {e}")
        return False

# الحصول على المستخدمين المحظورين
def get_banned_users():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM banned_users')
        users = cursor.fetchall()
        conn.close()
        
        return [user[0] for user in users]
    except Exception as e:
        logging.error(f"Error getting banned users: {e}")
        return []

# تشغيل ملف بايثون
def run_python_file(file_path, process_key):
    try:
        process = subprocess.Popen(
            ['python', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        active_processes[process_key] = {
            'process': process,
            'start_time': time.time(),
            'status': 'running'
        }
        
        # الانتظار بدون timeout
        stdout, stderr = process.communicate()
        
        return {
            'success': process.returncode == 0,
            'stdout': stdout,
            'stderr': stderr,
            'execution_time': time.time() - active_processes[process_key]['start_time']
        }
        
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'execution_time': 0
        }
    finally:
        if process_key in active_processes:
            del active_processes[process_key]

# تشغيل ملف بشكل غير متزامن
def run_file_async(file_path, process_key, chat_id, user_id, file_name):
    try:
        result = run_python_file(file_path, process_key)
        
        if result['success']:
            message = f"""
{get_random_emoji()} تم تشغيل الملف: {file_name}
{get_random_emoji()} وقت التنفيذ: {result['execution_time']:.2f} ثانية
"""
            if result['stdout']:
                message += f"\n{get_random_emoji()} الناتج:\n{result['stdout'][-1000:]}\n"
        else:
            message = f"""
{get_random_emoji()} فشل تشغيل الملف: {file_name}
{get_random_emoji()} الخطأ:\n{result['stderr'][-1000:]}
"""
        
        bot.send_message(chat_id, message)
        
    except Exception as e:
        logging.error(f"Error in async file execution: {e}")

# استعادة جميع الملفات من القناة
def restore_all_files_from_channel():
    try:
        offset = 0
        restored_count = 0
        
        while True:
            messages = bot.get_chat_history(CHANNEL_ID, limit=100, offset=offset)
            if not messages:
                break
            
            for message in messages:
                if message.caption and message.caption.startswith("FILE_DATA:"):
                    parts = message.caption.split(":")
                    if len(parts) >= 4:
                        user_id = int(parts[1])
                        file_name = parts[2]
                        
                        try:
                            file_info = bot.get_file(message.document.file_id)
                            downloaded_file = bot.download_file(file_info.file_path)
                            
                            # حفظ في قاعدة البيانات
                            save_file_to_db(user_id, file_name, downloaded_file)
                            
                            # حفظ محلياً للتشغيل
                            file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
                            with open(file_path, 'wb') as f:
                                f.write(downloaded_file)
                            
                            restored_count += 1
                            logging.info(f"Restored file: {file_name}")
                            
                        except Exception as e:
                            logging.error(f"Failed to restore file {file_name}: {e}")
            
            offset += 100
            time.sleep(0.1)
            
        logging.info(f"Total files restored: {restored_count}")
        
    except Exception as e:
        logging.error(f"Error restoring files from channel: {e}")

# تشغيل جميع الملفات المحفوظة
def run_all_saved_files():
    try:
        files = get_all_files_from_db()
        logging.info(f"Starting {len(files)} saved files...")
        
        for user_id, file_name, file_content in files:
            try:
                file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
                
                # التأكد من وجود الملف محلياً
                if not os.path.exists(file_path):
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
                
                process_key = f"{user_id}_{file_name}"
                
                # تشغيل الملف بشكل غير متزامن
                process_executor.submit(
                    run_file_async, 
                    file_path, 
                    process_key,
                    0,
                    user_id,
                    file_name
                )
                
            except Exception as e:
                logging.error(f"Failed to start file {file_name}: {e}")
                
    except Exception as e:
        logging.error(f"Error running saved files: {e}")

# إنشاء لوحة إنلاين رئيسية
def create_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} رفع ملف', callback_data='upload_file'),
        InlineKeyboardButton(f'{get_random_emoji()} الإعدادات', callback_data='settings_menu')
    )
    return keyboard

# إنشاء لوحة إنلاين للإعدادات
def create_settings_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} صنع ملف', callback_data='create_file'),
        InlineKeyboardButton(f'{get_random_emoji()} الملفات المحفوظة', callback_data='saved_files'),
        InlineKeyboardButton(f'{get_random_emoji()} استبدال ملف', callback_data='replace_file'),
        InlineKeyboardButton(f'{get_random_emoji()} حذف ملف', callback_data='delete_file'),
        InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='main_menu')
    )
    return keyboard

# إنشاء لوحة إنلاين لتشغيل الملف
def create_run_inline_keyboard(file_name, user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} تشغيل الملف', callback_data=f'run_{user_id}_{file_name}')
    )
    return keyboard

# إنشاء لوحة إنلاين لإيقاف التشغيل
def create_stop_inline_keyboard(file_name, user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} إيقاف التشغيل', callback_data=f'stop_{user_id}_{file_name}')
    )
    return keyboard

# إنشاء لوحة إنلاين للملفات المحفوظة
def create_saved_files_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    user_files = get_user_files_from_db(user_id)
    
    if not user_files:
        keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} لا توجد ملفات محفوظة', callback_data='none'))
    else:
        for file_name in user_files[:15]:
            keyboard.add(InlineKeyboardButton(
                f"{get_random_emoji()} {file_name}", 
                callback_data=f"run_{user_id}_{file_name}"
            ))
    
    keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='settings_menu'))
    return keyboard

# إنشاء لوحة إنلاين لاستبدال الملف
def create_replace_files_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    user_files = get_user_files_from_db(user_id)
    
    if not user_files:
        keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} لا توجد ملفات محفوظة', callback_data='none'))
    else:
        for file_name in user_files[:15]:
            keyboard.add(InlineKeyboardButton(
                f"{get_random_emoji()} {file_name}", 
                callback_data=f"replace_{user_id}_{file_name}"
            ))
    
    keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='settings_menu'))
    return keyboard

# إنشاء لوحة إنلاين لحذف الملف
def create_delete_files_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    user_files = get_user_files_from_db(user_id)
    
    if not user_files:
        keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} لا توجد ملفات محفوظة', callback_data='none'))
    else:
        for file_name in user_files[:15]:
            keyboard.add(InlineKeyboardButton(
                f"{get_random_emoji()} {file_name}", 
                callback_data=f"delete_{user_id}_{file_name}"
            ))
    
    keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='settings_menu'))
    return keyboard

# إنشاء لوحة إنلاين للإدارة
def create_admin_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} حظر', callback_data='admin_ban_user'),
        InlineKeyboardButton(f'{get_random_emoji()} إلغاء حظر', callback_data='admin_unban_user')
    )
    
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} كشف ملفات', callback_data='admin_list_files'),
        InlineKeyboardButton(f'{get_random_emoji()} إيقاف ملفات', callback_data='admin_stop_files')
    )
    
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} منع رفع', callback_data='admin_ban_upload'),
        InlineKeyboardButton(f'{get_random_emoji()} إعادة تشغيل', callback_data='admin_restart')
    )
    
    keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='main_menu'))
    
    return keyboard

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        if user_id in banned_users:
            bot.send_message(chat_id, f"{get_random_emoji()} أنت محظور من استخدام البوت.")
            return
        
        welcome_text = f"""
{get_random_emoji()} مرحباً بك في بوت استضافة الملفات {BOT_USERNAME}

{get_random_emoji()} المميزات المتاحة:
{get_random_emoji()} رفع وتشغيل عدد لا نهائي من الملفات
{get_random_emoji()} تشغيل متزامن غير محدود
{get_random_emoji()} استعادة تلقائية لجميع الملفات

{get_random_emoji()} اختر أحد الخيارات:
"""
        bot.send_message(chat_id, welcome_text, reply_markup=create_main_keyboard())
        
    except Exception as e:
        logging.error(f"Error in /start command: {e}")

# معالجة أمر /admin
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        if user_id != ADMIN_ID:
            bot.send_message(chat_id, f"{get_random_emoji()} ليس لديك صلاحية الوصول إلى لوحة الإدارة.")
            return
        
        admin_text = f"""
{get_random_emoji()} لوحة إدارة البوت

{get_random_emoji()} الإحصائيات:
{get_random_emoji()} الملفات المحفوظة: {len(get_all_files_from_db())}
{get_random_emoji()} العمليات النشطة: {len(active_processes)}
{get_random_emoji()} المستخدمين المحظورين: {len(banned_users)}

{get_random_emoji()} اختر أحد خيارات الإدارة:
"""
        bot.send_message(chat_id, admin_text, reply_markup=create_admin_keyboard())
        
    except Exception as e:
        logging.error(f"Error in admin command: {e}")

# معالجة رفع الملفات
@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if user_id in banned_users:
        bot.send_message(chat_id, f"{get_random_emoji()} أنت محظور من رفع الملفات.")
        return
    
    try:
        if not message.document.file_name.endswith('.py'):
            bot.send_message(chat_id, f"{get_random_emoji()} يسمح فقط بملفات البايثون py")
            return
        
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_name = message.document.file_name
        
        # حفظ الملف
        file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # حفظ في قاعدة البيانات
        save_file_to_db(user_id, file_name, downloaded_file)
        
        # إرسال إلى القناة
        with open(file_path, 'rb') as file:
            bot.send_document(
                CHANNEL_ID, 
                file, 
                caption=f"FILE_DATA:{user_id}:{file_name}:{int(time.time())}"
            )
        
        file_size = len(downloaded_file) / (1024 * 1024)
        
        bot.send_message(
            chat_id, 
            f"{get_random_emoji()} تم رفع الملف: {file_name} ({file_size:.2f} MB)",
            reply_markup=create_run_inline_keyboard(file_name, user_id)
        )
        
    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        bot.send_message(chat_id, f"{get_random_emoji()} حدث خطأ أثناء رفع الملف")

# معالجة الرسائل النصية لصنع الملفات
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text
    
    if user_id in banned_users:
        bot.send_message(chat_id, f"{get_random_emoji()} أنت محظور من استخدام البوت.")
        return
    
    # إذا كان المستخدم في وضع صنع ملف
    if user_id in user_states and user_states[user_id].get('action') == 'waiting_create_file':
        try:
            file_name = f"code_{int(time.time())}.py"
            file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
            
            with open(file_path, 'w', encoding='utf-8') as new_file:
                new_file.write(text)
            
            # حفظ في قاعدة البيانات
            with open(file_path, 'rb') as f:
                file_content = f.read()
                save_file_to_db(user_id, file_name, file_content)
            
            # إرسال إلى القناة
            with open(file_path, 'rb') as file:
                bot.send_document(
                    CHANNEL_ID, 
                    file, 
                    caption=f"FILE_DATA:{user_id}:{file_name}:{int(time.time())}"
                )
            
            del user_states[user_id]
            
            with open(file_path, 'rb') as file:
                bot.send_document(
                    chat_id,
                    file,
                    caption=f"{get_random_emoji()} تم إنشاء الملف: {file_name}",
                    reply_markup=create_run_inline_keyboard(file_name, user_id)
                )
            
        except Exception as e:
            logging.error(f"Error creating file: {str(e)}")
            bot.send_message(chat_id, f"{get_random_emoji()} حدث خطأ أثناء إنشاء الملف")
    
    # إذا كان المستخدم في وضع إداري
    elif user_id == ADMIN_ID and user_id in user_states:
        admin_action = user_states[user_id].get('action')
        
        if admin_action == 'waiting_ban_user':
            try:
                target_user_id = int(text)
                ban_user(target_user_id)
                del user_states[user_id]
                bot.send_message(chat_id, f"{get_random_emoji()} تم حظر المستخدم: {target_user_id}")
            except:
                bot.send_message(chat_id, f"{get_random_emoji()} معرّف المستخدم غير صحيح")
        
        elif admin_action == 'waiting_unban_user':
            try:
                target_user_id = int(text)
                unban_user(target_user_id)
                del user_states[user_id]
                bot.send_message(chat_id, f"{get_random_emoji()} تم إلغاء حظر المستخدم: {target_user_id}")
            except:
                bot.send_message(chat_id, f"{get_random_emoji()} معرّف المستخدم غير صحيح")
        
        elif admin_action == 'waiting_list_files':
            try:
                target_user_id = int(text)
                user_files = get_user_files_from_db(target_user_id)
                
                if not user_files:
                    bot.send_message(chat_id, f"{get_random_emoji()} لا توجد ملفات للمستخدم: {target_user_id}")
                else:
                    files_list = "\n".join([f"{get_random_emoji()} {file_name}" for file_name in user_files])
                    bot.send_message(chat_id, f"{get_random_emoji()} ملفات المستخدم {target_user_id}:\n\n{files_list}")
                
                del user_states[user_id]
            except:
                bot.send_message(chat_id, f"{get_random_emoji()} معرّف المستخدم غير صحيح")
    
    else:
        bot.send_message(chat_id, f"{get_random_emoji()} مرحباً! اختر خياراً من القائمة:", reply_markup=create_main_keyboard())

# معالجة callback queries
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_id = call.from_user.id
    data = call.data
    
    try:
        if data == 'upload_file':
            bot.edit_message_text(
                f"{get_random_emoji()} أرسل لي ملف بايثون (py) لرفعه",
                chat_id,
                message_id
            )
        
        elif data == 'settings_menu':
            bot.edit_message_text(
                f"{get_random_emoji()} الإعدادات:\n\n{get_random_emoji()} اختر أحد الخيارات:",
                chat_id,
                message_id,
                reply_markup=create_settings_keyboard()
            )
        
        elif data == 'create_file':
            user_states[user_id] = {'action': 'waiting_create_file'}
            bot.edit_message_text(
                f"{get_random_emoji()} أرسل لي كود بايثون وسأقوم بتحويله إلى ملف وتشغيله",
                chat_id,
                message_id
            )
        
        elif data == 'saved_files':
            bot.edit_message_text(
                f"{get_random_emoji()} الملفات المحفوظة:\n\n{get_random_emoji()} اختر ملفاً لتشغيله:",
                chat_id,
                message_id,
                reply_markup=create_saved_files_keyboard(user_id)
            )
        
        elif data == 'replace_file':
            bot.edit_message_text(
                f"{get_random_emoji()} استبدال ملف:\n\n{get_random_emoji()} اختر الملف الذي تريد استبداله:",
                chat_id,
                message_id,
                reply_markup=create_replace_files_keyboard(user_id)
            )
        
        elif data == 'delete_file':
            bot.edit_message_text(
                f"{get_random_emoji()} حذف ملف:\n\n{get_random_emoji()} اختر الملف الذي تريد حذفه:",
                chat_id,
                message_id,
                reply_markup=create_delete_files_keyboard(user_id)
            )
        
        elif data == 'main_menu':
            bot.edit_message_text(
                f"{get_random_emoji()} مرحباً! اختر خياراً من القائمة:",
                chat_id,
                message_id,
                reply_markup=create_main_keyboard()
            )
        
        # إدارة البوت
        elif data == 'admin_ban_user':
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            user_states[user_id] = {'action': 'waiting_ban_user'}
            bot.edit_message_text(
                f"{get_random_emoji()} أرسل معرّف المستخدم الذي تريد حظره:",
                chat_id,
                message_id
            )
        
        elif data == 'admin_unban_user':
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            user_states[user_id] = {'action': 'waiting_unban_user'}
            bot.edit_message_text(
                f"{get_random_emoji()} أرسل معرّف المستخدم الذي تريد إلغاء حظره:",
                chat_id,
                message_id
            )
        
        elif data == 'admin_list_files':
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            user_states[user_id] = {'action': 'waiting_list_files'}
            bot.edit_message_text(
                f"{get_random_emoji()} أرسل معرّف المستخدم لعرض ملفاته:",
                chat_id,
                message_id
            )
        
        elif data == 'admin_stop_files':
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            # إيقاف جميع العمليات النشطة
            for process_key, process_info in list(active_processes.items()):
                try:
                    if 'process' in process_info and process_info['process'].poll() is None:
                        process_info['process'].terminate()
                        time.sleep(0.1)
                        if process_info['process'].poll() is None:
                            process_info['process'].kill()
                except:
                    pass
            
            active_processes.clear()
            bot.edit_message_text(
                f"{get_random_emoji()} تم إيقاف جميع الملفات النشطة",
                chat_id,
                message_id
            )
        
        elif data == 'admin_ban_upload':
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            user_states[user_id] = {'action': 'waiting_ban_user'}
            bot.edit_message_text(
                f"{get_random_emoji()} أرسل معرّف المستخدم الذي تريد منعه من رفع الملفات:",
                chat_id,
                message_id
            )
        
        elif data == 'admin_restart':
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            bot.edit_message_text(
                f"{get_random_emoji()} جاري إعادة التشغيل...",
                chat_id,
                message_id
            )
            
            # إعادة تشغيل جميع الملفات المحفوظة
            run_all_saved_files()
            
            bot.edit_message_text(
                f"{get_random_emoji()} تم إعادة تشغيل البوت وجميع الملفات المحفوظة",
                chat_id,
                message_id
            )
        
        elif data.startswith('run_'):
            parts = data.split('_')
            if len(parts) >= 3:
                target_user_id = int(parts[1])
                file_name = '_'.join(parts[2:])
                
                file_path = os.path.join(UPLOAD_DIR, f"{target_user_id}_{file_name}")
                
                if os.path.exists(file_path):
                    process_key = f"{target_user_id}_{file_name}"
                    
                    # تشغيل الملف بشكل غير متزامن
                    process_executor.submit(
                        run_file_async, 
                        file_path, 
                        process_key,
                        chat_id,
                        target_user_id,
                        file_name
                    )
                    
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} جاري التشغيل...")
                else:
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} الملف غير موجود")
        
        elif data.startswith('replace_'):
            parts = data.split('_')
            if len(parts) >= 3:
                target_user_id = int(parts[1])
                file_name = '_'.join(parts[2:])
                
                user_states[user_id] = {
                    'action': 'waiting_replace_file',
                    'target_user_id': target_user_id,
                    'file_name': file_name
                }
                
                bot.edit_message_text(
                    f"{get_random_emoji()} أرسل الكود الجديد للملف: {file_name}",
                    chat_id,
                    message_id
                )
        
        elif data.startswith('delete_'):
            parts = data.split('_')
            if len(parts) >= 3:
                target_user_id = int(parts[1])
                file_name = '_'.join(parts[2:])
                
                # حذف الملف
                file_path = os.path.join(UPLOAD_DIR, f"{target_user_id}_{file_name}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                # حذف من قاعدة البيانات
                delete_file_from_db(target_user_id, file_name)
                
                bot.edit_message_text(
                    f"{get_random_emoji()} تم حذف الملف: {file_name}",
                    chat_id,
                    message_id,
                    reply_markup=create_delete_files_keyboard(user_id)
                )
        
        elif data.startswith('stop_'):
            parts = data.split('_')
            if len(parts) >= 3:
                target_user_id = int(parts[1])
                file_name = '_'.join(parts[2:])
                
                process_key = f"{target_user_id}_{file_name}"
                if process_key in active_processes:
                    try:
                        process_info = active_processes[process_key]
                        if 'process' in process_info and process_info['process'].poll() is None:
                            process_info['process'].terminate()
                            time.sleep(0.1)
                            if process_info['process'].poll() is None:
                                process_info['process'].kill()
                        
                        del active_processes[process_key]
                        bot.answer_callback_query(call.id, f"{get_random_emoji()} تم إيقاف التشغيل")
                    except:
                        bot.answer_callback_query(call.id, f"{get_random_emoji()} خطأ في الإيقاف")
                else:
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} الملف غير نشط")
        
        bot.answer_callback_query(call.id)
    
    except Exception as e:
        logging.error(f"Error in callback: {e}")
        bot.answer_callback_query(call.id, f"{get_random_emoji()} حدث خطأ")

@app.route('/')
def health_check():
    return "البوت يعمل بشكل صحيح ✅", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return 'OK', 200
        return 'Bad request', 400
    except Exception as e:
        logging.error(f"Error in webhook: {e}")
        return 'Error', 500

# استخدام المنفذ من متغير البيئة
port = int(os.environ.get('PORT', 10000))

# تشغيل البوت
def run_bot():
    try:
        # تهيئة قاعدة البيانات
        init_database()
        
        # تحميل المستخدمين المحظورين
        banned_users.update(get_banned_users())
        
        # استعادة الملفات من القناة
        restore_all_files_from_channel()
        
        # تشغيل جميع الملفات المحفوظة
        run_all_saved_files()
        
        # إعداد Webhook
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.set_webhook(url=webhook_url)
        logging.info(f"Webhook set to: {webhook_url}")
        
        # تشغيل الخادم
        serve(app, host='0.0.0.0', port=port)
        
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        bot.polling(none_stop=True)

if __name__ == '__main__':
    run_bot() 
