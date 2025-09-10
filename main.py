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
from datetime import datetime, timedelta

# إعدادات البوت
BOT_TOKEN = '8038261927:AAEFA02UtYJdaTZ-qxJBzRtSLA6XexG2flA'
ADMIN_ID = 6689435577
BOT_USERNAME = '@te7st878bot'
CHANNEL_ID = '-1003091756917'  # قناة الملفات
USER_DATA_CHANNEL_ID = '3088700358'  # قناة بيانات المستخدمين
WEBHOOK_URL = 'https://greenpo-1.onrender.com'

# الحصول على المنفذ من متغيرات البيئة (مطلوب للتشغيل على Render)
port = int(os.environ.get('PORT', 5000))

# إعدادات الملفات
UPLOAD_DIR = 'uploaded_files'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# قواعد البيانات
DB_FILE = 'bot_database.db'

# إعدادات الأداء - غير محدودة
MAX_CONCURRENT_PROCESSES = None
PROCESS_TIMEOUT = 600  # 10 دقائق للتشغيل العادي

# قائمة الرموز التعبيرية
RANDOM_EMOJIS = ['🦜', '🦚', '🐸', '🐊', '🐢', '🦎', '🐍', '🐲', '🐉', '🦕', '🐛', '🪲', '💐', '🦠', '🌲', '🌳', '🌵', '🌴', '🌾', '🌿', '🌱', '☘️', '🍀', '🪴', '🍃']

# تخزين العمليات النشطة
active_processes = {}
user_states = {}
banned_users = set()
premium_users = {}
process_executor = ThreadPoolExecutor(max_workers=None)
bot_enabled = True  # حالة البوت (مفعل/معطل)

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
                is_active BOOLEAN DEFAULT 1,
                is_permanent BOOLEAN DEFAULT 0
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
                status TEXT DEFAULT 'running',
                is_permanent BOOLEAN DEFAULT 0
            )
        ''')
        
        # جدول النقاط
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_points (
                user_id INTEGER PRIMARY KEY,
                points INTEGER DEFAULT 0,
                invited_by INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الدعوات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER,
                referred_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (referrer_id, referred_id)
            )
        ''')
        
        # جدول المستخدمين المميزين
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id INTEGER PRIMARY KEY,
                expiry_date TIMESTAMP,
                auto_renew BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول إعدادات البوت
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully")
        
    except Exception as e:
        logging.error(f"Database initialization error: {e}")

# حفظ إعدادات البوت
def save_bot_setting(key, value):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO bot_settings (key, value)
            VALUES (?, ?)
        ''', (key, value))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Error saving bot setting: {e}")
        return False

# تحميل إعدادات البوت
def load_bot_setting(key, default=None):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM bot_settings WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else default
    except Exception as e:
        logging.error(f"Error loading bot setting: {e}")
        return default

# الحصول على رمز تعبيري عشوائي
def get_random_emoji():
    return random.choice(RANDOM_EMOJIS)

# الحصول على نقاط المستخدم
def get_user_points(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT points FROM user_points WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else 0
    except Exception as e:
        logging.error(f"Error getting user points: {e}")
        return 0

# إضافة نقاط للمستخدم
def add_user_points(user_id, points):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO user_points (user_id, points)
            VALUES (?, COALESCE((SELECT points FROM user_points WHERE user_id = ?), 0) + ?)
        ''', (user_id, user_id, points))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Error adding user points: {e}")
        return False

# تسجيل دعوة
def add_referral(referrer_id, referred_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)', 
                      (referrer_id, referred_id))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Error adding referral: {e}")
        return False

# الحصول على عدد الدعوات
def get_referral_count(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else 0
    except Exception as e:
        logging.error(f"Error getting referral count: {e}")
        return 0

# إضافة/تحديث مستخدم مميز
def add_premium_user(user_id, days=7):
    try:
        expiry_date = datetime.now() + timedelta(days=days)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO premium_users (user_id, expiry_date)
            VALUES (?, ?)
        ''', (user_id, expiry_date.timestamp()))
        
        conn.commit()
        conn.close()
        
        # تحديث الذاكرة المؤقتة
        premium_users[user_id] = expiry_date
        
        # حفظ بيانات المستخدم في القناة
        save_user_data_to_channel(user_id, {
            'action': 'premium_added',
            'days': days,
            'expiry_date': expiry_date.timestamp()
        })
        
        return True
    except Exception as e:
        logging.error(f"Error adding premium user: {e}")
        return False

# التحقق من حالة المستخدم المميز
def is_premium_user(user_id):
    try:
        # التحقق من الذاكرة المؤقتة أولاً
        if user_id in premium_users:
            if datetime.now() < premium_users[user_id]:
                return True
            else:
                del premium_users[user_id]
                return False
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT expiry_date FROM premium_users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            expiry_date = datetime.fromtimestamp(result[0])
            if datetime.now() < expiry_date:
                premium_users[user_id] = expiry_date
                return True
            else:
                # حذف المستخدم من القائمة إذا انتهت مدة الاشتراك
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM premium_users WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()
                
                # حفظ بيانات المستخدم في القناة
                save_user_data_to_channel(user_id, {
                    'action': 'premium_expired',
                    'user_id': user_id
                })
                
                return False
        
        return False
    except Exception as e:
        logging.error(f"Error checking premium user: {e}")
        return False

# الحصول على تاريخ انتهاء الاشتراك
def get_premium_expiry(user_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT expiry_date FROM premium_users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return datetime.fromtimestamp(result[0])
        return None
    except Exception as e:
        logging.error(f"Error getting premium expiry: {e}")
        return None

# الحصول على جميع المستخدمين المميزين
def get_all_premium_users():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, expiry_date FROM premium_users')
        users = cursor.fetchall()
        conn.close()
        
        return [(user_id, datetime.fromtimestamp(expiry_date)) for user_id, expiry_date in users]
    except Exception as e:
        logging.error(f"Error getting premium users: {e}")
        return []

# حفظ بيانات المستخدم في القناة
def save_user_data_to_channel(user_id, data):
    try:
        message = f"USER_DATA:{user_id}:{json.dumps(data)}"
        bot.send_message(USER_DATA_CHANNEL_ID, message)
        return True
    except Exception as e:
        logging.error(f"Error saving user data to channel: {e}")
        return False

# حفظ الملف في قاعدة البيانات
def save_file_to_db(user_id, file_name, file_content, is_permanent=False):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO files (user_id, file_name, file_content, file_size, is_permanent)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, file_name, file_content, len(file_content), is_permanent))
        
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
            SELECT file_content, is_permanent FROM files 
            WHERE user_id = ? AND file_name = ? AND is_active = 1
        ''', (user_id, file_name))
        
        result = cursor.fetchone()
        conn.close()
        
        return result if result else None
    except Exception as e:
        logging.error(f"Error loading file from DB: {e}")
        return None

# الحصول على جميع الملفات من قاعدة البيانات
def get_all_files_from_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, file_name, file_content, is_permanent FROM files WHERE is_active = 1')
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
        
        cursor.execute('SELECT file_name, is_permanent FROM files WHERE user_id = ? AND is_active = 1', (user_id,))
        files = cursor.fetchall()
        conn.close()
        
        return files
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
        
        # حفظ بيانات المستخدم في القناة
        save_user_data_to_channel(user_id, {
            'action': 'user_banned',
            'user_id': user_id
        })
        
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
        
        # حفظ بيانات المستخدم في القناة
        save_user_data_to_channel(user_id, {
            'action': 'user_unbanned',
            'user_id': user_id
        })
        
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
def run_python_file(file_path, process_key, is_permanent=False):
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
            'status': 'running',
            'is_permanent': is_permanent
        }
        
        # إذا كان التشغيل دائمًا، لا نضع timeout
        if is_permanent:
            stdout, stderr = process.communicate()
        else:
            # للتشغيل العادي، نضع timeout 10 دقائق
            stdout, stderr = process.communicate(timeout=PROCESS_TIMEOUT)
        
        return {
            'success': process.returncode == 0,
            'stdout': stdout,
            'stderr': stderr,
            'execution_time': time.time() - active_processes[process_key]['start_time']
        }
        
    except subprocess.TimeoutExpired:
        process.kill()
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Process timeout exceeded (10 minutes)',
            'execution_time': PROCESS_TIMEOUT
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
def run_file_async(file_path, process_key, chat_id, user_id, file_name, is_permanent=False):
    try:
        result = run_python_file(file_path, process_key, is_permanent)
        
        if result['success']:
            message = f"""
{get_random_emoji()} تم تشغيل الملف: {file_name}
{get_random_emoji()} وقت التنفيذ: {result['execution_time']:.2f} ثانية
"""
            if result['stdout']:
                message += f"\n{get_random_emoji()} الناتج:\n{result['stdout'][-1000:]}\n"
            
            # إرسال إشعار للمدير عن الملفات الناجحة
            if is_permanent:
                try:
                    bot.send_message(ADMIN_ID, f"✅ ملف دائم ناجح: {file_name}\n👤 المستخدم: {user_id}\n⏱ الوقت: {result['execution_time']:.2f} ثانية")
                except:
                    pass
        else:
            message = f"""
{get_random_emoji()} فشل تشغيل الملف: {file_name}
{get_random_emoji()} الخطأ:\n{result['stderr'][-1000:]}
"""
            
            # إذا فشل التشغيل، حذف الملف
            try:
                os.remove(file_path)
                delete_file_from_db(user_id, file_name)
                
                # إرسال إشعار للمدير عن الملفات الفاشلة
                try:
                    bot.send_message(ADMIN_ID, f"❌ ملف فاشل: {file_name}\n👤 المستخدم: {user_id}\n📋 الخطأ: {result['stderr'][-500:]}")
                except:
                    pass
            except:
                pass
        
        bot.send_message(chat_id, message)
        
    except Exception as e:
        logging.error(f"Error in async file execution: {e}")

# استعادة جميع الملفات من القناة
def restore_all_files_from_channel():
    try:
        # التحقق أولاً إذا كان هناك ملفات في القناة
        try:
            messages = bot.get_chat_history(CHANNEL_ID, limit=1)
            if not messages:
                logging.info("No files found in channel, skipping restoration")
                return
        except Exception as e:
            logging.error(f"Error checking channel for files: {e}")
            return
        
        offset = 0
        restored_count = 0
        file_count = 0
        
        # إرسال إشعار للمدير ببدء الاستعادة
        try:
            bot.send_message(ADMIN_ID, "🔄 جاري استعادة الملفات من القناة...")
        except:
            pass
        
        while True:
            messages = bot.get_chat_history(CHANNEL_ID, limit=100, offset=offset)
            if not messages:
                break
            
            for message in messages:
                if message.caption and message.caption.startswith("FILE_DATA:"):
                    file_count += 1
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
            
        # إرسال إشعار للمدير بنتيجة الاستعادة
        try:
            bot.send_message(ADMIN_ID, f"✅ تم استعادة {restored_count} من أصل {file_count} ملف من القناة")
        except:
            pass
        
        logging.info(f"Total files restored: {restored_count}")
        
    except Exception as e:
        logging.error(f"Error restoring files from channel: {e}")
        try:
            bot.send_message(ADMIN_ID, f"❌ فشل في استعادة الملفات: {str(e)}")
        except:
            pass

# تشغيل جميع الملفات المحفوظة
def run_all_saved_files():
    try:
        files = get_all_files_from_db()
        if not files:
            logging.info("No saved files to run")
            return
            
        logging.info(f"Starting {len(files)} saved files...")
        
        # إرسال إشعار للمدير ببدء التشغيل
        try:
            bot.send_message(ADMIN_ID, f"🔄 جاري تشغيل {len(files)} ملف محفوظ...")
        except:
            pass
        
        success_count = 0
        for user_id, file_name, file_content, is_permanent in files:
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
                    file_name,
                    is_permanent
                )
                
                success_count += 1
                
            except Exception as e:
                logging.error(f"Failed to start file {file_name}: {e}")
                
        # إرسال إشعار للمدير بنتيجة التشغيل
        try:
            bot.send_message(ADMIN_ID, f"✅ تم بدء تشغيل {success_count} من أصل {len(files)} ملف بنجاح")
        except:
            pass
            
    except Exception as e:
        logging.error(f"Error running saved files: {e}")
        try:
            bot.send_message(ADMIN_ID, f"❌ فشل في تشغيل الملفات المحفوظة: {str(e)}")
        except:
            pass

# إنشاء لوحة إنلاين رئيسية
def create_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} رفع ملف', callback_data='upload_file'),
        InlineKeyboardButton(f'{get_random_emoji()} الإعدادات', callback_data='settings_menu')
    )
    return keyboard

# إنشاء لوحة إنلاين لخيارات التشغيل
def create_run_options_keyboard(user_id, file_name):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    user_points = get_user_points(user_id)
    is_premium = is_premium_user(user_id)
    
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} تشغيل عادي (10 دقائق)', callback_data=f'run_normal_{user_id}_{file_name}')
    )
    
    if user_points > 0 or user_id == ADMIN_ID or is_premium:
        keyboard.add(
            InlineKeyboardButton(f'{get_random_emoji()} تشغيل دائم (يستهلك نقطة)', callback_data=f'run_permanent_{user_id}_{file_name}')
        )
    else:
        keyboard.add(
            InlineKeyboardButton(f'{get_random_emoji()} شارك الرابط للحصول على نقاط', callback_data='share_referral')
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

# إنشاء لوحة إنلاين للملفات المحفوظة
def create_saved_files_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    user_files = get_user_files_from_db(user_id)
    
    if not user_files:
        keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} لا توجد ملفات محفوظة', callback_data='none'))
    else:
        for file_name, is_permanent in user_files[:15]:
            emoji = '♾️' if is_permanent else '⏱️'
            keyboard.add(InlineKeyboardButton(
                f"{emoji} {file_name}", 
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
        for file_name, is_permanent in user_files[:15]:
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
        for file_name, is_permanent in user_files[:15]:
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
    
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} ترقية عضو', callback_data='admin_upgrade_user'),
        InlineKeyboardButton(f'{get_random_emoji()} تجديد اشتراك', callback_data='admin_renew_subscription')
    )
    
    # زر إتاحة/إيقاف البوت
    bot_status = "معطل" if not bot_enabled else "مفعل"
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} إتاحة البوت ({bot_status})', callback_data='admin_toggle_bot')
    )
    
    keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='main_menu'))
    
    return keyboard

# إنشاء لوحة إنلاين لترقية المستخدم
def create_upgrade_options_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} أسبوع', callback_data='upgrade_7'),
        InlineKeyboardButton(f'{get_random_emoji()} شهر', callback_data='upgrade_30')
    )
    
    keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='admin_menu'))
    
    return keyboard

# إنشاء لوحة إنلاين لتجديد الاشتراك
def create_renew_options_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} أسبوع', callback_data='renew_7'),
        InlineKeyboardButton(f'{get_random_emoji()} شهر', callback_data='renew_30')
    )
    
    keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='admin_menu'))
    
    return keyboard

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"
        
        # التحقق من حالة البوت
        if not bot_enabled and user_id != ADMIN_ID and not is_premium_user(user_id):
            bot.send_message(chat_id, f"{get_random_emoji()} البوت معطل حالياً للصيانة. فقط الأعضاء المميزون يمكنهم استخدامه.")
            return
            
        if user_id in banned_users:
            bot.send_message(chat_id, f"{get_random_emoji()} أنت محظور من استخدام البوت.")
            return
        
        # التحقق من وجود رابط دعوة
        if len(message.text.split()) > 1:
            ref_code = message.text.split()[1]
            if ref_code.startswith('ref_'):
                try:
                    referrer_id = int(ref_code[4:])
                    if referrer_id != user_id:
                        # إضافة النقطة للمدعو
                        add_user_points(user_id, 1)
                        # إضافة النقطة للمدعي
                        add_user_points(referrer_id, 1)
                        # تسجيل الدعوة
                        add_referral(referrer_id, user_id)
                        
                        # إرسال إشعار للمدعي
                        try:
                            bot.send_message(referrer_id, f"{get_random_emoji()} لقد حصلت على نقطة جديدة! قام {username} بالتسجيل عبر رابط الدعوة الخاص بك.")
                        except:
                            pass
                        
                        # إرسال إشعار للمدعو
                        bot.send_message(chat_id, f"{get_random_emoji()} لقد حصلت على نقطة ترحيب! يمكنك استخدامها لتشغيل ملف بشكل دائم.")
                except ValueError:
                    pass
        
        # التحقق من حالة الاشتراك المميز
        is_premium = is_premium_user(user_id)
        premium_status = f"{get_random_emoji()} عضو مميز" if is_premium else f"{get_random_emoji()} عضو عادي"
        
        if is_premium:
            expiry_date = get_premium_expiry(user_id)
            if expiry_date:
                premium_status += f" (تنتهي في {expiry_date.strftime('%Y-%m-%d')})"
        
        welcome_text = f"""
{get_random_emoji()} مرحباً بك في بوت استضافة الملفات {BOT_USERNAME}

{get_random_emoji()} حالة العضوية: {premium_status}
{get_random_emoji()} نقاطك الحالية: {get_user_points(user_id)}
{get_random_emoji()} عدد دعواتك: {get_referral_count(user_id)}

{get_random_emoji()} المميزات المتاحة:
{get_random_emoji()} رفع وتشغيل عدد لا نهائي من الملفات
{get_random_emoji()} تشغيل عادي (10 دقائق) أو دائم (باستخدام النقاط)
{get_random_emoji()} نظام نقاط لدعوة الأصدقاء

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
        
        # إحصائيات المستخدمين المميزين
        premium_users_list = get_all_premium_users()
        active_premium = sum(1 for _, expiry in premium_users_list if datetime.now() < expiry)
        expired_premium = len(premium_users_list) - active_premium
        
        admin_text = f"""
{get_random_emoji()} لوحة إدارة البوت

{get_random_emoji()} الإحصائيات:
{get_random_emoji()} الملفات المحفوظة: {len(get_all_files_from_db())}
{get_random_emoji()} العمليات النشطة: {len(active_processes)}
{get_random_emoji()} المستخدمين المحظورين: {len(banned_users)}
{get_random_emoji()} الأعضاء المميزين: {active_premium} نشط, {expired_premium} منتهي
{get_random_emoji()} حالة البوت: {'مفعل' if bot_enabled else 'معطل'}

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
    
    # التحقق من حالة البوت
    if not bot_enabled and user_id != ADMIN_ID and not is_premium_user(user_id):
        bot.send_message(chat_id, f"{get_random_emoji()} البوت معطل حالياً للصيانة. فقط الأعضاء المميزون يمكنهم استخدامه.")
        return
        
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
        
        # حفظ في قاعدة البيانات (مؤقت حتى يختار المستخدم)
        user_states[user_id] = {
            'action': 'waiting_run_choice',
            'file_name': file_name,
            'file_content': downloaded_file
        }
        
        file_size = len(downloaded_file) / (1024 * 1024)
        
        bot.send_message(
            chat_id, 
            f"{get_random_emoji()} تم رفع الملف: {file_name} ({file_size:.2f} MB)\n\n{get_random_emoji()} اختر نوع التشغيل:",
            reply_markup=create_run_options_keyboard(user_id, file_name)
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
    
    # التحقق من حالة البوت
    if not bot_enabled and user_id != ADMIN_ID and not is_premium_user(user_id):
        bot.send_message(chat_id, f"{get_random_emoji()} البوت معطل حالياً للصيانة. فقط الأعضاء المميزون يمكنهم استخدامه.")
        return
        
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
            
            # حفظ في قاعدة البيانات (مؤقت حتى يختار المستخدم)
            with open(file_path, 'rb') as f:
                file_content = f.read()
                user_states[user_id] = {
                    'action': 'waiting_run_choice',
                    'file_name': file_name,
                    'file_content': file_content
                }
            
            bot.send_message(
                chat_id, 
                f"{get_random_emoji()} تم إنشاء الملف: {file_name}\n\n{get_random_emoji()} اختر نوع التشغيل:",
                reply_markup=create_run_options_keyboard(user_id, file_name)
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
                    files_list = "\n".join([f"{'♾️' if is_permanent else '⏱️'} {file_name}" for file_name, is_permanent in user_files])
                    bot.send_message(chat_id, f"{get_random_emoji()} ملفات المستخدم {target_user_id}:\n\n{files_list}")
                
                del user_states[user_id]
            except:
                bot.send_message(chat_id, f"{get_random_emoji()} معرّف المستخدم غير صحيح")
        
        elif admin_action == 'waiting_upgrade_user':
            try:
                target_user_id = int(text)
                user_states[user_id] = {
                    'action': 'waiting_upgrade_duration',
                    'target_user_id': target_user_id
                }
                bot.send_message(chat_id, f"{get_random_emoji()} اختر مدة الترقية للمستخدم {target_user_id}:", reply_markup=create_upgrade_options_keyboard())
            except:
                bot.send_message(chat_id, f"{get_random_emoji()} معرّف المستخدم غير صحيح")
        
        elif admin_action == 'waiting_renew_user':
            try:
                target_user_id = int(text)
                user_states[user_id] = {
                    'action': 'waiting_renew_duration',
                    'target_user_id': target_user_id
                }
                bot.send_message(chat_id, f"{get_random_emoji()} اختر مدة التجديد للمستخدم {target_user_id}:", reply_markup=create_renew_options_keyboard())
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
        
        elif data == 'share_referral':
            referral_link = f"https://t.me/{BOT_USERNAME[1:]}?start=ref_{user_id}"
            bot.edit_message_text(
                f"{get_random_emoji()} رابط الدعوة الخاص بك:\n\n{referral_link}\n\n{get_random_emoji()} لكل شخص يسجل عبر هذا الرابط، تحصل أنت وهو على نقطة مجانية!",
                chat_id,
                message_id
            )
        
        elif data == 'admin_menu':
            admin_panel(call.message)
        
        # إدارة البوت - ترقية عضو
        elif data == 'admin_upgrade_user':
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            user_states[user_id] = {'action': 'waiting_upgrade_user'}
            bot.edit_message_text(
                f"{get_random_emoji()} أرسل معرّف المستخدم الذي تريد ترقيته:",
                chat_id,
                message_id
            )
        
        # إدارة البوت - تجديد اشتراك
        elif data == 'admin_renew_subscription':
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            user_states[user_id] = {'action': 'waiting_renew_user'}
            bot.edit_message_text(
                f"{get_random_emoji()} أرسل معرّف المستخدم الذي تريد تجديد اشتراكه:",
                chat_id,
                message_id
            )
        
        # إدارة البوت - تفعيل/تعطيل البوت
        elif data == 'admin_toggle_bot':
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            global bot_enabled
            bot_enabled = not bot_enabled
            save_bot_setting('bot_enabled', '1' if bot_enabled else '0')
            
            # حفظ بيانات الإعداد في القناة
            save_user_data_to_channel(user_id, {
                'action': 'bot_toggled',
                'status': 'enabled' if bot_enabled else 'disabled',
                'admin_id': user_id
            })
            
            bot.edit_message_text(
                f"{get_random_emoji()} تم {'تفعيل' if bot_enabled else 'تعطيل'} البوت بنجاح",
                chat_id,
                message_id,
                reply_markup=create_admin_keyboard()
            )
        
        # خيارات الترقية
        elif data.startswith('upgrade_'):
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            if 'target_user_id' not in user_states[user_id]:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} خطأ في البيانات")
                return
            
            target_user_id = user_states[user_id]['target_user_id']
            days = int(data.split('_')[1])
            
            if add_premium_user(target_user_id, days):
                expiry_date = get_premium_expiry(target_user_id)
                bot.edit_message_text(
                    f"{get_random_emoji()} تم ترقية المستخدم {target_user_id} بنجاح\n{get_random_emoji()} المدة: {days} يوم\n{get_random_emoji()} ينتهي في: {expiry_date.strftime('%Y-%m-%d')}",
                    chat_id,
                    message_id
                )
                
                # إرسال إشعار للمستخدم
                try:
                    bot.send_message(target_user_id, f"{get_random_emoji()} تم ترقيتك إلى عضو مميز! يمكنك الآن رفع وتشغيل الملفات بشكل دائم لمدة {days} يوم.")
                except:
                    pass
            else:
                bot.edit_message_text(
                    f"{get_random_emoji()} فشل في ترقية المستخدم {target_user_id}",
                    chat_id,
                    message_id
                )
            
            del user_states[user_id]
        
        # خيارات التجديد
        elif data.startswith('renew_'):
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية")
                return
            
            if 'target_user_id' not in user_states[user_id]:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} خطأ في البيانات")
                return
            
            target_user_id = user_states[user_id]['target_user_id']
            days = int(data.split('_')[1])
            
            # الحصول على تاريخ الانتهاء الحالي
            current_expiry = get_premium_expiry(target_user_id)
            if current_expiry:
                new_expiry = current_expiry + timedelta(days=days)
            else:
                new_expiry = datetime.now() + timedelta(days=days)
            
            # تحديث تاريخ الانتهاء
            try:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute('UPDATE premium_users SET expiry_date = ? WHERE user_id = ?', 
                              (new_expiry.timestamp(), target_user_id))
                conn.commit()
                conn.close()
                
                # تحديث الذاكرة المؤقتة
                premium_users[target_user_id] = new_expiry
                
                bot.edit_message_text(
                    f"{get_random_emoji()} تم تجديد اشتراك المستخدم {target_user_id} بنجاح\n{get_random_emoji()} المدة المضافة: {days} يوم\n{get_random_emoji()} ينتهي الآن في: {new_expiry.strftime('%Y-%m-%d')}",
                    chat_id,
                    message_id
                )
                
                # إرسال إشعار للمستخدم
                try:
                    bot.send_message(target_user_id, f"{get_random_emoji()} تم تجديد اشتراكك المميز! يمكنك الآن الاستمرار في رفع وتشغيل الملفات بشكل دائم لمدة {days} يوم إضافية.")
                except:
                    pass
            except Exception as e:
                logging.error(f"Error renewing subscription: {e}")
                bot.edit_message_text(
                    f"{get_random_emoji()} فشل في تجديد اشتراك المستخدم {target_user_id}",
                    chat_id,
                    message_id
                )
            
            del user_states[user_id]
        
        elif data.startswith('run_normal_'):
            parts = data.split('_')
            if len(parts) >= 4:
                target_user_id = int(parts[2])
                file_name = '_'.join(parts[3:])
                
                if user_id != target_user_id and user_id != ADMIN_ID:
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية تشغيل هذا الملف")
                    return
                
                # حفظ الملف في قاعدة البيانات (تشغيل عادي)
                if user_id in user_states and user_states[user_id].get('action') == 'waiting_run_choice':
                    file_content = user_states[user_id]['file_content']
                    save_file_to_db(user_id, file_name, file_content, False)
                    
                    # إرسال الملف إلى القناة
                    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
                    
                    with open(file_path, 'rb') as file:
                        bot.send_document(
                            CHANNEL_ID, 
                            file, 
                            caption=f"FILE_DATA:{user_id}:{file_name}:{int(time.time())}:normal"
                        )
                    
                    del user_states[user_id]
                
                file_path = os.path.join(UPLOAD_DIR, f"{target_user_id}_{file_name}")
                
                if os.path.exists(file_path):
                    process_key = f"{target_user_id}_{file_name}"
                    
                    # تشغيل الملف بشكل غير متزامن (عادي)
                    process_executor.submit(
                        run_file_async, 
                        file_path, 
                        process_key,
                        chat_id,
                        target_user_id,
                        file_name,
                        False
                    )
                    
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} جاري التشغيل العادي...")
                else:
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} الملف غير موجود")
        
        elif data.startswith('run_permanent_'):
            parts = data.split('_')
            if len(parts) >= 4:
                target_user_id = int(parts[2])
                file_name = '_'.join(parts[3:])
                
                if user_id != target_user_id and user_id != ADMIN_ID:
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية تشغيل هذا الملف")
                    return
                
                user_points = get_user_points(user_id)
                is_premium = is_premium_user(user_id)
                
                if user_points <= 0 and user_id != ADMIN_ID and not is_premium:
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك نقاط كافية")
                    return
                
                # خصم نقطة من المستخدم (ما عدا المدير والأعضاء المميزين)
                if user_id != ADMIN_ID and not is_premium:
                    add_user_points(user_id, -1)
                
                # حفظ الملف في قاعدة البيانات (تشغيل دائم)
                if user_id in user_states and user_states[user_id].get('action') == 'waiting_run_choice':
                    file_content = user_states[user_id]['file_content']
                    save_file_to_db(user_id, file_name, file_content, True)
                    
                    # إرسال الملف إلى القناة
                    file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
                    
                    with open(file_path, 'rb') as file:
                        bot.send_document(
                            CHANNEL_ID, 
                            file, 
                            caption=f"FILE_DATA:{user_id}:{file_name}:{int(time.time())}:permanent"
                        )
                    
                    del user_states[user_id]
                
                file_path = os.path.join(UPLOAD_DIR, f"{target_user_id}_{file_name}")
                
                if os.path.exists(file_path):
                    process_key = f"{target_user_id}_{file_name}"
                    
                    # تشغيل الملف بشكل غير متزامن (دائم)
                    process_executor.submit(
                        run_file_async, 
                        file_path, 
                        process_key,
                        chat_id,
                        target_user_id,
                        file_name,
                        True
                    )
                    
                    if user_id != ADMIN_ID and not is_premium:
                        bot.answer_callback_query(call.id, f"{get_random_emoji()} جاري التشغيل الدائم! تم خصم نقطة.")
                    else:
                        bot.answer_callback_query(call.id, f"{get_random_emoji()} جاري التشغيل الدائم!")
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

# وظيفة للتحقق من انتهاء الاشتراكات
def check_expired_subscriptions():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # الحصول على المستخدمين المنتهية اشتراكاتهم
        cursor.execute('SELECT user_id FROM premium_users WHERE expiry_date < ?', 
                      (datetime.now().timestamp(),))
        expired_users = cursor.fetchall()
        
        for (user_id,) in expired_users:
            # حذف المستخدم من القائمة المميزة
            cursor.execute('DELETE FROM premium_users WHERE user_id = ?', (user_id,))
            
            # إرسال إشعار للمستخدم
            try:
                bot.send_message(user_id, f"{get_random_emoji()} انتهت مدة اشتراكك المميز. يمكنك التواصل مع المدير لتجديده.")
            except:
                pass
            
            # إرسال إشعار للمدير
            try:
                bot.send_message(ADMIN_ID, f"{get_random_emoji()} انتهت مدة اشتراك المستخدم {user_id}. يمكنك تجديده من لوحة الإدارة.")
            except:
                pass
        
        conn.commit()
        conn.close()
        
        # تحديث الذاكرة المؤقتة
        for user_id in expired_users:
            if user_id in premium_users:
                del premium_users[user_id]
                
    except Exception as e:
        logging.error(f"Error checking expired subscriptions: {e}")

# تشغيل البوت
def run_bot():
    try:
        # تهيئة قاعدة البيانات
        init_database()
        
        # تحميل المستخدمين المحظورين
        banned_users.update(get_banned_users())
        
        # تحميل المستخدمين المميزين
        premium_list = get_all_premium_users()
        for user_id, expiry_date in premium_list:
            premium_users[user_id] = expiry_date
        
        # تحميل إعدادات البوت
        global bot_enabled
        bot_enabled = load_bot_setting('bot_enabled', '1') == '1'
        
        # التحقق من الاشتراكات المنتهية
        check_expired_subscriptions()
        
        # استعادة الملفات من القناة (فقط إذا كانت هناك ملفات)
        try:
            # التحقق أولاً إذا كان هناك ملفات في القناة
            messages = bot.get_chat_history(CHANNEL_ID, limit=1)
            if messages:
                restore_all_files_from_channel()
            else:
                logging.info("No files found in channel, skipping restoration")
        except Exception as e:
            logging.error(f"Error checking channel for files: {e}")
        
        # تشغيل جميع الملفات المحفوظة
        run_all_saved_files()
        
        # إعداد Webhook
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.set_webhook(url=webhook_url)
        logging.info(f"Webhook set to: {webhook_url}")
        
        # جدولة التحقق من الاشتراكات المنتهية يومياً
        def schedule_subscription_check():
            while True:
                time.sleep(86400)  # 24 ساعة
                check_expired_subscriptions()
        
        subscription_thread = threading.Thread(target=schedule_subscription_check)
        subscription_thread.daemon = True
        subscription_thread.start()
        
        # تشغيل الخادم - استخدام المتغير port الذي تم تعريفه في الأعلى
        serve(app, host='0.0.0.0', port=port)
        
    except Exception as e:
        logging.error(f"Failed to start bot: {e}")
        # في حالة الفشل، نستخدم polling كبديل
        bot.polling(none_stop=True)

# نقطة الدخول الرئيسية
if __name__ == '__main__':
    run_bot() 
