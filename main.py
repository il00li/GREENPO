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

# إعدادات البوت - استخدام التوكن الجديد
BOT_TOKEN = os.getenv('BOT_TOKEN', '8268382565:AAGIx2RqP_964unFhiXF9hKOs1H1Ay1ifNs')
ADMIN_ID = 6689435577
BOT_USERNAME = '@HOZ7_BOT'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyD3w0ZtC-GOvOVVlUxb_l0ayRAVsar64FI')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://greenpo-1.onrender.com')

# إعدادات الملفات
UPLOAD_DIR = 'uploaded_files'
USERS_FILE = 'users.json'
ACTIVE_PROCESSES_FILE = 'active_processes.json'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# تخزين العمليات النشطة والمحادثات
active_processes = {}
ai_sessions = {}

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

# تهيئة Gemini AI مع النموذج المحدد
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-2.0-flash')
    GEMINI_AVAILABLE = True
    logging.info("Gemini AI initialized successfully")
except Exception as e:
    logging.error(f"Failed to initialize Gemini AI: {e}")
    GEMINI_AVAILABLE = False

# إنشاء تطبيق Flask لنقطة التحقق
app = Flask(__name__)

# تحميل بيانات المستخدمين من الملف المحلي
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading users: {e}")
            return {}
    return {}

# حفظ بيانات المستخدمين في الملف المحلي
def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        logging.error(f"Failed to save users: {e}")

# تحميل العمليات النشطة من الملف المحلي
def load_active_processes():
    if os.path.exists(ACTIVE_PROCESSES_FILE):
        try:
            with open(ACTIVE_PROCESSES_FILE, 'r') as f:
                data = json.load(f)
                return data
        except Exception as e:
            logging.error(f"Error loading processes: {e}")
            return {}
    return {}

# حفظ العمليات النشطة في الملف المحلي
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

# تحميل البيانات
users = load_users()
active_processes = load_active_processes()

# دالة لحفظ جميع البيانات
def save_all_data():
    save_users(users)
    save_active_processes(active_processes)
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
    return "حالة البوت: نشط 🟢", 200

@app.route('/test')
def test_bot():
    try:
        bot_info = bot.get_me()
        return f"البوت نشط: {bot_info.first_name} ({bot_info.username})", 200
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

# استخدام المنفذ من متغير البيئة أو 10000 افتراضيًا
port = int(os.environ.get('PORT', 10000))

def run_flask():
    # استخدام Waitress كخادم إنتاج بدلاً من خادم تطوير Flask
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
    users = load_users()  # تحديث بيانات المستخدمين
    
    if str(user_id) == str(ADMIN_ID):
        return True
    
    if str(user_id) in users:
        user_data = users[str(user_id)]
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

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"
        
        logging.info(f"Received /start command from user {user_id} ({username})")
        
        # التحقق من رابط الدعوة
        if len(message.text.split()) > 1:
            referral_code = message.text.split()[1]
            if referral_code.startswith('ref_'):
                referrer_id = referral_code.split('_')[1]
                
                # تحديث عدد referrals للمستخدم الذي قام بالدعوة
                if referrer_id in users:
                    users[referrer_id]['referrals'] = users[referrer_id].get('referrals', 0) + 1
                    
                    # منح 5 محاولات مجانية إذا وصل إلى 10 referrals
                    if users[referrer_id].get('referrals', 0) >= 10:
                        users[referrer_id]['free_attempts'] = users[referrer_id].get('free_attempts', 0) + 5
                        users[referrer_id]['referrals'] = 0  # إعادة الضبط
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
                'joined_date': time.strftime("%Y-%m-%d %H:%M:%S")
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

# باقي الدوال والأوامر (معالجو الأوامر الأخرى)
# ... [يتم الحفاظ على نفس كود المعالجين الآخرين] ...

# معالجة أمر /help
@bot.message_handler(commands=['help'])
def help_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_user_authorized(user_id):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا البوت")
        return
    
    help_text = f"""
شروط الاستخدام

1. يسمح فقط بملفات البايثون py
2. الحد الأقصى لحجم الملف 20MB
3. وقت التنفيذ الأقصى 30 ثانية
4. يمنع رفع ملفات تحتوي على أكواد ضارة

للتواصل والدعم
{BOT_USERNAME}
"""
    bot.send_message(chat_id, help_text, reply_markup=create_main_keyboard())

# إعداد Webhook
def setup_webhook():
    try:
        # حذف أي Webhook موجود مسبقاً
        bot.remove_webhook()
        time.sleep(1)
        
        # تعيين Webhook جديد
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
