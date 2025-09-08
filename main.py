import os
import telebot
import subprocess
import time
import logging
import random
import threading
import json
import google.generativeai as genai
from flask import Flask, request
from waitress import serve
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import signal
import atexit
import requests
from io import BytesIO

# إعدادات البوت
BOT_TOKEN = os.getenv('BOT_TOKEN', '8268382565:AAGIx2RqP_964unFhiXF9hKOs1H1Ay1ifNs')
ADMIN_ID = 6689435577
BOT_USERNAME = '@HOZ7_BOT'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyD3w0ZtC-GOvOVVlUxb_l0ayRAVsar64FI')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://greenpo-1.onrender.com')
CHANNEL_ID = os.getenv('CHANNEL_ID', '-1003091756917')  # معرف القناة

# إعدادات الملفات
UPLOAD_DIR = 'uploaded_files'
USERS_FILE = 'users.json'
ACTIVE_PROCESSES_FILE = 'active_processes.json'
BOT_STATE_FILE = 'bot_state.json'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# تخزين العمليات النشطة والمحادثات
active_processes = {}
ai_sessions = {}
bot_active = True  # حالة البوت

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
bot = telebot.TeleBot(BOT_TOKEN)

# تهيئة Gemini AI
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.0-flash')
    GEMINI_AVAILABLE = True
    logging.info("Gemini AI initialized successfully")
except Exception as e:
    logging.error(f"Failed to initialize Gemini AI: {e}")
    GEMINI_AVAILABLE = False

# إنشاء تطبيق Flask
app = Flask(__name__)

# تحميل بيانات المستخدمين
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading users: {e}")
            return {}
    return {}

# حفظ بيانات المستخدمين
def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save users: {e}")

# تحميل العمليات النشطة
def load_active_processes():
    if os.path.exists(ACTIVE_PROCESSES_FILE):
        try:
            with open(ACTIVE_PROCESSES_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading processes: {e}")
            return {}
    return {}

# حفظ العمليات النشطة
def save_active_processes(processes):
    try:
        serializable_data = {}
        for key, value in processes.items():
            serializable_value = value.copy()
            if 'process' in serializable_value:
                del serializable_value['process']
            serializable_data[key] = serializable_value
        
        with open(ACTIVE_PROCESSES_FILE, 'w') as f:
            json.dump(serializable_data, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save active processes: {e}")

# تحميل حالة البوت
def load_bot_state():
    if os.path.exists(BOT_STATE_FILE):
        try:
            with open(BOT_STATE_FILE, 'r') as f:
                return json.load(f).get('active', True)
        except:
            return True
    return True

# حفظ حالة البوت
def save_bot_state(active):
    try:
        with open(BOT_STATE_FILE, 'w') as f:
            json.dump({'active': active}, f)
    except Exception as e:
        logging.error(f"Failed to save bot state: {e}")

# تحميل البيانات
users = load_users()
active_processes = load_active_processes()
bot_active = load_bot_state()

# دالة لحفظ جميع البيانات
def save_all_data():
    save_users(users)
    save_active_processes(active_processes)
    save_bot_state(bot_active)
    logging.info("All data saved successfully")

# تسجيل دالة حفظ البيانات عند الخروج
atexit.register(save_all_data)

# معالجة إشارات النظام
def signal_handler(sig, frame):
    logging.info("Received termination signal, saving data...")
    save_all_data()
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@app.route('/')
def health_check():
    return "البوت يعمل بشكل صحيح ✅", 200

@app.route('/status')
def status_check():
    status = "نشط 🟢" if bot_active else "متوقف 🔴"
    return f"حالة البوت: {status}", 200

@app.route('/test')
def test_bot():
    try:
        bot_info = bot.get_me()
        status = "نشط 🟢" if bot_active else "متوقف 🔴"
        return f"البوت {status}: {bot_info.first_name} ({bot_info.username})", 200
    except Exception as e:
        return f"خطأ في البوت: {str(e)}", 500

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        if request.headers.get('content-type') == 'application/json':
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            logging.info("Webhook request processed successfully")
            return 'OK', 200
        return 'Bad request', 400
    except Exception as e:
        logging.error(f"Error in webhook: {e}")
        return 'Error', 500

# استخدام المنفذ من متغير البيئة
port = int(os.environ.get('PORT', 10000))

def run_flask():
    try:
        logging.info(f"Starting Flask server on port {port}")
        serve(app, host='0.0.0.0', port=port)
    except Exception as e:
        logging.error(f"Flask server error: {e}")
        time.sleep(60)
        run_flask()

# بدء Flask في الخلفية
flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# إنشاء لوحة إنلاين رئيسية
def create_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton('📤 رفع ملف', callback_data='upload_file'),
        InlineKeyboardButton('⚙️ الإعدادات', callback_data='settings_menu'),
        InlineKeyboardButton('🤖 محادثة AI', callback_data='ai_chat'),
        InlineKeyboardButton('📊 حالة البوت', callback_data='bot_status'),
        InlineKeyboardButton('👥 دعوة الأصدقاء', callback_data='invite_friends')
    ]
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    keyboard.add(buttons[4])
    return keyboard

# إنشاء لوحة إنلاين للإعدادات
def create_settings_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton('🛑 إيقاف الملفات', callback_data='stop_files'),
        InlineKeyboardButton('📚 تثبيت مكتبة', callback_data='install_library'),
        InlineKeyboardButton('🚀 سرعة البوت', callback_data='bot_speed'),
        InlineKeyboardButton('🔙 رجوع', callback_data='main_menu')
    ]
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    return keyboard

# إنشاء لوحة إنلاين لإيقاف التشغيل
def create_stop_inline_keyboard(file_name, user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton('🛑 إيقاف التشغيل', callback_data=f'stop_{user_id}_{file_name}')
    )
    return keyboard

# إنشاء لوحة إنلاين لإنهاء المحادثة
def create_end_chat_inline_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton('❌ إنهاء المحادثة', callback_data='end_chat'),
        InlineKeyboardButton('🔙 رجوع', callback_data='main_menu')
    )
    return keyboard

# إنشاء لوحة إنلاين مع زر الرجوع
def create_back_keyboard():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton('🔙 رجوع', callback_data='main_menu'))
    return keyboard

# التحقق من صلاحية المستخدم
def is_user_authorized(user_id):
    global users
    users = load_users()
    
    if str(user_id) == str(ADMIN_ID):
        return True
    
    if str(user_id) in users:
        user_data = users[str(user_id)]
        # التحقق إذا كان المستخدم محظوراً
        if user_data.get('banned', False):
            return False
        if user_data.get('approved', False) or user_data.get('free_attempts', 0) > 0:
            return True
    
    return False

# تقليل عدد المحاولات المجانية
def decrement_free_attempts(user_id):
    global users
    if str(user_id) in users:
        if users[str(user_id)].get('free_attempts', 0) > 0:
            users[str(user_id)]['free_attempts'] -= 1
            save_users(users)
            return users[str(user_id)]['free_attempts']
    return 0

# استعادة المحاولات المجانية
def restore_free_attempts(user_id):
    global users
    if str(user_id) in users:
        users[str(user_id)]['free_attempts'] = users[str(user_id)].get('free_attempts', 0) + 1
        save_users(users)
        return users[str(user_id)]['free_attempts']
    return 0

# إرسال ملف إلى القناة
def send_file_to_channel(file_path, user_id, file_name):
    try:
        if CHANNEL_ID:
            with open(file_path, 'rb') as file:
                bot.send_document(
                    CHANNEL_ID, 
                    file, 
                    caption=f"ملف من المستخدم: {user_id}\nاسم الملف: {file_name}\nوقت الرفع: {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            return True
    except Exception as e:
        logging.error(f"Failed to send file to channel: {e}")
    return False

# إعادة تشغيل الملفات المحفوظة
def restart_saved_processes():
    global active_processes, bot_active
    
    if not bot_active:
        return
    
    saved_processes = load_active_processes()
    restarted_count = 0
    total_count = len(saved_processes)
    
    if total_count == 0:
        return
    
    # إرسال رسالة بدء إعادة التشغيل للمدير
    try:
        bot.send_message(ADMIN_ID, f"🔄 جاري إعادة تشغيل {total_count} ملف...")
    except:
        pass
    
    for process_key, process_info in saved_processes.items():
        try:
            if not bot_active:  # تحقق إذا تم إيقاف البوت أثناء عملية إعادة التشغيل
                break
                
            user_id = process_info.get('user_id')
            file_name = process_info.get('file_name')
            chat_id = process_info.get('chat_id')
            
            # التحقق إذا كان المستخدم محظوراً
            if str(user_id) in users and users[str(user_id)].get('banned', False):
                logging.info(f"Skipping restart for banned user: {user_id}")
                continue
                
            file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
            
            if os.path.exists(file_path):
                # تشغيل الملف
                process = subprocess.Popen(
                    ['python', file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                active_processes[process_key] = {
                    'process': process,
                    'start_time': time.time(),
                    'chat_id': chat_id,
                    'file_name': file_name,
                    'user_id': user_id
                }
                
                restarted_count += 1
                
                # إرسال إشعار للمستخدم
                try:
                    bot.send_message(
                        chat_id, 
                        f"🔄 تم إعادة تشغيل ملفك تلقائياً: {file_name}",
                        reply_markup=create_stop_inline_keyboard(file_name, user_id)
                    )
                except:
                    pass
                
                # تأخير بين عمليات إعادة التشغيل
                time.sleep(2)
                
        except Exception as e:
            logging.error(f"Failed to restart process {process_key}: {e}")
    
    # حفظ العمليات النشطة بعد إعادة التشغيل
    save_active_processes(active_processes)
    
    # إرسال إحصائية للمدير
    try:
        bot.send_message(
            ADMIN_ID, 
            f"📊 تمت إعادة تشغيل {restarted_count} من أصل {total_count} ملف\n\n" +
            f"الملفات النشطة الآن: {len(active_processes)}"
        )
    except:
        pass

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"
        
        logging.info(f"Received /start command from user {user_id} ({username})")
        
        # التحقق من حالة البوت
        if not bot_active:
            bot.send_message(chat_id, "⏹️ البوت متوقف حالياً. يرجى الانتظار حتى يتم تشغيله من قبل المدير.")
            return
        
        # التحقق إذا كان المستخدم محظوراً
        if str(user_id) in users and users[str(user_id)].get('banned', False):
            ban_reason = users[str(user_id)].get('ban_reason', 'غير محدد')
            bot.send_message(
                chat_id, 
                f"⛔ حسابك محظور من استخدام البوت.\n\nالسبب: {ban_reason}\n\nللمزيد من المعلومات، تواصل مع المدير."
            )
            return
        
        # التحقق من رابط الدعوة
        if len(message.text.split()) > 1:
            referral_code = message.text.split()[1]
            if referral_code.startswith('ref_'):
                referrer_id = referral_code.split('_')[1]
                
                if referrer_id in users:
                    users[referrer_id]['referrals'] = users[referrer_id].get('referrals', 0) + 1
                    
                    if users[referrer_id].get('referrals', 0) >= 10:
                        users[referrer_id]['free_attempts'] = users[referrer_id].get('free_attempts', 0) + 5
                        users[referrer_id]['referrals'] = 0
                        try:
                            bot.send_message(referrer_id, "🎉 مبروك! لقد حصلت على 5 محاولات مجانية لدعوة 10 أصدقاء.")
                        except:
                            pass
                
                save_users(users)
        
        # إنشاء مستخدم جديد إذا لم يكن موجوداً
        if str(user_id) not in users:
            users[str(user_id)] = {
                'username': username,
                'approved': False,
                'free_attempts': 0,
                'referrals': 0,
                'joined_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'banned': False,
                'ban_reason': '',
                'ban_date': ''
            }
            save_users(users)
        
        # التحقق من صلاحية المستخدم
        if not is_user_authorized(user_id):
            welcome_text = f"""
مرحباً {username} 👋

للأسف، ليس لديك صلاحية استخدام هذا البوت حالياً.

📋 للحصول على صلاحية الاستخدام:
1. يمكنك الانتظار حتى موافقة المدير
2. أو دعوة 10 أصدقاء للحصول على 5 محاولات مجانية

🔗 رابط الدعوة الخاص بك:
https://t.me/{BOT_USERNAME[1:]}?start=ref_{user_id}

📊 عدد الأصدقاء الذين دعوتهم: {users[str(user_id)].get('referrals', 0)}/10
"""
            bot.send_message(chat_id, welcome_text)
            return
        
        # إذا كان المستخدم مصرحاً له
        user_data = users[str(user_id)]
        free_attempts = user_data.get('free_attempts', 0)
        
        welcome_text = f"""
مرحباً بك في بوت استضافة بايثون {BOT_USERNAME}

المميزات المتاحة
- رفع وتشغيل ملفات البايثون
- إدارة الملفات الخاصة بك
- دعم المكتبات الخارجية
- محادثة مع الذكاء الاصطناعي

📊 محاولاتك المجانية المتبقية: {free_attempts}

لبدء الاستخدام
اضغط على زر رفع ملف لرفع ملف بايثون

للمساعدة
اكتب /help لعرض الشروط
"""
        bot.send_message(chat_id, welcome_text, reply_markup=create_main_keyboard())
        logging.info(f"Welcome message sent to user {user_id}")
        
    except Exception as e:
        logging.error(f"Error in /start command: {e}")
        try:
            bot.send_message(message.chat.id, "عذراً، حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.")
        except:
            pass

# معالجة أمر /ban (للمدير فقط)
@bot.message_handler(commands=['ban'])
def ban_user_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    try:
        # الحصول على معرف المستخدم وسبب الحظر
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(chat_id, "استخدام خاطئ: /ban <user_id> [سبب الحظر]")
            return
        
        target_user_id = parts[1]
        ban_reason = ' '.join(parts[2:]) if len(parts) > 2 else "غير محدد"
        
        if target_user_id in users:
            # تحديث حالة الحظر
            users[target_user_id]['banned'] = True
            users[target_user_id]['ban_reason'] = ban_reason
            users[target_user_id]['ban_date'] = time.strftime("%Y-%m-%d %H:%M:%S")
            save_users(users)
            
            # إيقاف جميع عمليات المستخدم المحظور
            user_processes = {k: v for k, v in active_processes.items() if k.startswith(f"{target_user_id}_")}
            stopped_count = 0
            
            for process_key, process_info in user_processes.items():
                try:
                    if 'process' in process_info and process_info['process'].poll() is None:
                        process_info['process'].terminate()
                    stopped_count += 1
                    del active_processes[process_key]
                except:
                    pass
            
            save_active_processes(active_processes)
            
            # إرسال رسالة للمستخدم المحظور
            try:
                bot.send_message(
                    target_user_id, 
                    f"⛔ تم حظر حسابك من استخدام البوت.\n\nالسبب: {ban_reason}\n\nللمزيد من المعلومات، تواصل مع المدير."
                )
            except:
                pass
            
            # إرسال تأكيد للمدير
            username = users[target_user_id].get('username', 'N/A')
            bot.send_message(
                chat_id, 
                f"✅ تم حظر المستخدم: {username} (ID: {target_user_id})\nالسبب: {ban_reason}\nتم إيقاف {stopped_count} من عملياته النشطة."
            )
        else:
            bot.send_message(chat_id, "المستخدم غير موجود")
    
    except Exception as e:
        logging.error(f"Error in ban command: {e}")
        bot.send_message(chat_id, f"حدث خطأ: {str(e)}")

# معالجة أمر /unban (للمدير فقط)
@bot.message_handler(commands=['unban'])
def unban_user_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    try:
        # الحصول على معرف المستخدم
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(chat_id, "استخدام خاطئ: /unban <user_id>")
            return
        
        target_user_id = parts[1]
        
        if target_user_id in users:
            # إلغاء حظر المستخدم
            users[target_user_id]['banned'] = False
            users[target_user_id]['ban_reason'] = ''
            users[target_user_id]['ban_date'] = ''
            save_users(users)
            
            # إرسال رسالة للمستخدم الذي تم إلغاء حظره
            try:
                bot.send_message(target_user_id, "✅ تم إلغاء حظر حسابك. يمكنك الآن استخدام البوت مرة أخرى.")
            except:
                pass
            
            # إرسال تأكيد للمدير
            username = users[target_user_id].get('username', 'N/A')
            bot.send_message(chat_id, f"✅ تم إلغاء حظر المستخدم: {username} (ID: {target_user_id})")
        else:
            bot.send_message(chat_id, "المستخدم غير موجود")
    
    except Exception as e:
        logging.error(f"Error in unban command: {e}")
        bot.send_message(chat_id, f"حدث خطأ: {str(e)}")

# معالجة أمر /stopuser (للمدير فقط)
@bot.message_handler(commands=['stopuser'])
def stop_user_files_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    try:
        # الحصول على معرف المستخدم
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(chat_id, "استخدام خاطئ: /stopuser <user_id>")
            return
        
        target_user_id = parts[1]
        
        # إيقاف جميع عمليات المستخدم
        user_processes = {k: v for k, v in active_processes.items() if k.startswith(f"{target_user_id}_")}
        stopped_count = 0
        
        for process_key, process_info in user_processes.items():
            try:
                if 'process' in process_info and process_info['process'].poll() is None:
                    process_info['process'].terminate()
                stopped_count += 1
                del active_processes[process_key]
            except:
                pass
        
        save_active_processes(active_processes)
        
        # إرسال تأكيد للمدير
        username = users.get(target_user_id, {}).get('username', 'N/A') if target_user_id in users else 'N/A'
        bot.send_message(
            chat_id, 
            f"✅ تم إيقاف {stopped_count} من عمليات المستخدم: {username} (ID: {target_user_id})"
        )
    
    except Exception as e:
        logging.error(f"Error in stopuser command: {e}")
        bot.send_message(chat_id, f"حدث خطأ: {str(e)}")

# معالجة أمر /restartuser (للمدير فقط)
@bot.message_handler(commands=['restartuser'])
def restart_user_files_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    try:
        # الحصول على معرف المستخدم
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(chat_id, "استخدام خاطئ: /restartuser <user_id>")
            return
        
        target_user_id = parts[1]
        
        # إعادة تشغيل ملفات المستخدم
        restarted_count = 0
        
        # البحث عن ملفات المستخدم المحفوظة
        saved_processes = load_active_processes()
        user_processes = {k: v for k, v in saved_processes.items() if k.startswith(f"{target_user_id}_")}
        
        for process_key, process_info in user_processes.items():
            try:
                if not bot_active:
                    break
                    
                file_name = process_info.get('file_name')
                chat_id = process_info.get('chat_id')
                
                file_path = os.path.join(UPLOAD_DIR, f"{target_user_id}_{file_name}")
                
                if os.path.exists(file_path):
                    # تشغيل الملف
                    process = subprocess.Popen(
                        ['python', file_path],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    
                    active_processes[process_key] = {
                        'process': process,
                        'start_time': time.time(),
                        'chat_id': chat_id,
                        'file_name': file_name,
                        'user_id': target_user_id
                    }
                    
                    restarted_count += 1
                    
                    # إرسال إشعار للمستخدم
                    try:
                        bot.send_message(
                            chat_id, 
                            f"🔄 تم إعادة تشغيل ملفك من قبل المدير: {file_name}",
                            reply_markup=create_stop_inline_keyboard(file_name, target_user_id)
                        )
                    except:
                        pass
                    
                    # تأخير بين عمليات إعادة التشغيل
                    time.sleep(2)
                    
            except Exception as e:
                logging.error(f"Failed to restart process {process_key}: {e}")
        
        # حفظ العمليات النشطة بعد إعادة التشغيل
        save_active_processes(active_processes)
        
        # إرسال تأكيد للمدير
        username = users.get(target_user_id, {}).get('username', 'N/A') if target_user_id in users else 'N/A'
        bot.send_message(
            chat_id, 
            f"✅ تم إعادة تشغيل {restarted_count} من ملفات المستخدم: {username} (ID: {target_user_id})"
        )
    
    except Exception as e:
        logging.error(f"Error in restartuser command: {e}")
        bot.send_message(chat_id, f"حدث خطأ: {str(e)}")

# معالجة أمر /bannedusers (للمدير فقط)
@bot.message_handler(commands=['bannedusers'])
def list_banned_users_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    # البحث عن المستخدمين المحظورين
    banned_users = []
    for uid, user_data in users.items():
        if user_data.get('banned', False):
            banned_users.append((uid, user_data))
    
    if not banned_users:
        bot.send_message(chat_id, "لا يوجد مستخدمين محظورين حالياً.")
        return
    
    # إنشاء قائمة بالمستخدمين المحظورين
    banned_list = "📋 قائمة المستخدمين المحظورين:\n\n"
    for i, (uid, user_data) in enumerate(banned_users, 1):
        username = user_data.get('username', 'N/A')
        ban_reason = user_data.get('ban_reason', 'غير محدد')
        ban_date = user_data.get('ban_date', 'غير معروف')
        
        banned_list += f"{i}. {username} (ID: {uid})\n"
        banned_list += f"   السبب: {ban_reason}\n"
        banned_list += f"   تاريخ الحظر: {ban_date}\n\n"
    
    bot.send_message(chat_id, banned_list)

# باقي الأوامر والإعدادات (stopbot, startbot, botstats, handle_document, etc.)
# ... [يتم الحفاظ على نفس كود الأوامر الأخرى] ...

# إعداد Webhook
def setup_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"{WEBHOOK_URL}/webhook"
        bot.set_webhook(url=webhook_url)
        logging.info(f"Webhook set to: {webhook_url}")
        
        # التحقق من حالة البوت
        bot_info = bot.get_me()
        logging.info(f"Bot is ready: {bot_info.first_name} ({bot_info.username})")
        
        return True
    except Exception as e:
        logging.error(f"Failed to set webhook: {e}")
        return False

# وظيفة للحفاظ على البيانات
def data_persister():
    """دورة حفظ البيانات بشكل دوري"""
    while True:
        try:
            save_all_data()
            time.sleep(300)  # حفظ البيانات كل 5 دقائق
        except Exception as e:
            logging.error(f"Data persister error: {e}")
            time.sleep(60)

# تشغيل البوت مع إعداد Webhook
def run_bot():
    # بدء موضوع منفصل لحفظ البيانات
    data_persister_thread = threading.Thread(target=data_persister)
    data_persister_thread.daemon = True
    data_persister_thread.start()
    
    # إعداد Webhook
    if setup_webhook():
        print("🤖 البوت يعمل في وضع Webhook!")
        print(f"🌐 Webhook URL: {WEBHOOK_URL}/webhook")
        print(f"📊 نقطة التحقق متاحة على: http://0.0.0.0:{port}/")
        print(f"🔍 نقطة اختبار البوت: {WEBHOOK_URL}/test")
        
        # إذا كان البوت نشطاً، نقوم بإعادة تشغيل الملفات المحفوظة
        if bot_active:
            print("🔄 جاري إعادة تشغيل الملفات المحفوظة...")
            threading.Thread(target=restart_saved_processes).start()
        
        # تشغيل خادم Flask
        serve(app, host='0.0.0.0', port=port)
    else:
        logging.error("Failed to setup webhook, using polling as fallback")
        print("❌ فشل إعداد Webhook، جاري استخدام Polling كحل بديل")
        
        # استخدام Polling كحل بديل
        bot.remove_webhook()
        time.sleep(1)
        bot.polling(none_stop=True)

if __name__ == '__main__':
    run_bot()
