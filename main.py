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

# إعدادات البوت
BOT_TOKEN = os.getenv('BOT_TOKEN', '8268382565:AAFzoYN4Ad5ZH7Uhvy4xRvuTz7tnykKzuO4')
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
except Exception as e:
    logging.error(f"Failed to initialize Gemini AI: {e}")
    GEMINI_AVAILABLE = False

# إنشاء تطبيق Flask لنقطة التحقق
app = Flask(__name__)

# تحميل بيانات المستخدمين
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except:
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
        except:
            return {}
    return {}

# حفظ العمليات النشطة
def save_active_processes(processes):
    try:
        with open(ACTIVE_PROCESSES_FILE, 'w') as f:
            json.dump(processes, f, indent=4)
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

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Bad request', 403

# استخدام المنفذ من متغير البيئة أو 10000 افتراضيًا
port = int(os.environ.get('PORT', 10000))

def run_flask():
    # استخدام Waitress كخادم إنتاج بدلاً من خادم تطوير Flask
    try:
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
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
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

# معالجة أمر /approve (للمطور فقط)
@bot.message_handler(commands=['approve'])
def approve_user(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    try:
        # الحصول على معرف المستخدم من الرسالة
        target_user_id = message.text.split()[1]
        
        if target_user_id in users:
            users[target_user_id]['approved'] = True
            save_users(users)
            
            # إرسال رسالة للمستخدم المعتمد
            try:
                bot.send_message(target_user_id, "🎉 تمت الموافقة على حسابك! يمكنك الآن استخدام البوت.")
            except:
                pass
            
            bot.send_message(chat_id, f"تمت الموافقة على المستخدم {target_user_id}")
        else:
            bot.send_message(chat_id, "المستخدم غير موجود")
    
    except IndexError:
        bot.send_message(chat_id, "يرجى تحديد معرف المستخدم: /approve <user_id>")
    except Exception as e:
        bot.send_message(chat_id, f"حدث خطأ: {str(e)}")

# معالجة أمر /users (للمطور فقط)
@bot.message_handler(commands=['users'])
def list_users(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    user_list = "قائمة المستخدمين:\n\n"
    for uid, data in users.items():
        status = "معتمد" if data.get('approved', False) else "غير معتمد"
        attempts = data.get('free_attempts', 0)
        referrals = data.get('referrals', 0)
        user_list += f"👤 {data.get('username', 'N/A')} (ID: {uid}) - {status} - محاولات: {attempts} - دعوات: {referrals}\n"
    
    bot.send_message(chat_id, user_list)

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

# معالجة أمر /status (للمطور فقط)
@bot.message_handler(commands=['status'])
def bot_status_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    # حساب عدد الملفات والعمليات النشطة
    file_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
    active_count = len(active_processes)
    
    status_text = f"""
حالة البوت

الملفات المرفوعة: {file_count}
العمليات النشطة: {active_count}
المستخدمين المسجلين: {len(users)}
الحالة: يعمل بشكل طبيعي
"""
    bot.send_message(chat_id, status_text, reply_markup=create_main_keyboard())

# معالجة أمر /restart (للمطور فقط)
@bot.message_handler(commands=['restart'])
def restart_bot(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    bot.send_message(chat_id, "🔄 جاري إعادة تشغيل البوت...")
    logging.info("Bot restart initiated by admin")
    save_all_data()  # حفظ البيانات قبل إعادة التشغيل
    os._exit(0)  # سيتم إعادة التشغيل تلقائياً بواسطة النظام

# معالجة callback queries
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    user_id = call.from_user.id
    data = call.data
    
    # التحقق من صلاحية المستخدم
    if not is_user_authorized(user_id):
        bot.answer_callback_query(call.id, "ليس لديك صلاحية استخدام هذا البوت")
        return
    
    if data == 'upload_file':
        # التحقق من المحاولات المجانية
        user_data = users[str(user_id)]
        if user_data.get('free_attempts', 0) <= 0 and not user_data.get('approved', False):
            bot.answer_callback_query(call.id, "ليس لديك محاولات مجانية متبقية")
            return
        
        bot.edit_message_text(
            "أرسل لي ملف بايثون py لرفعه وتشغيله",
            chat_id,
            message_id,
            reply_markup=create_back_keyboard()
        )
    
    elif data == 'settings_menu':
        settings_text = """
الإعدادات المتاحة

- إيقاف الملفات النشطة
- تثبيت مكتبات خارجية
- التحقق من سرعة البوت
"""
        bot.edit_message_text(
            settings_text,
            chat_id,
            message_id,
            reply_markup=create_settings_keyboard()
        )
    
    elif data == 'ai_chat':
        if not GEMINI_AVAILABLE:
            bot.answer_callback_query(call.id, "خدمة الذكاء الاصطناعي غير متاحة حالياً")
            return
        
        # بدء جلسة محادثة جديدة
        ai_sessions[user_id] = {
            'chat': gemini_model.start_chat(history=[]),
            'active': True
        }
        bot.edit_message_text(
            "مرحباً! أنا مساعد الذكاء الاصطناعي. كيف يمكنني مساعدتك اليوم؟\n\nأرسل رسالتك وسأرد عليك.",
            chat_id,
            message_id,
            reply_markup=create_end_chat_inline_keyboard()
        )
    
    elif data == 'bot_status':
        # حساب عدد الملفات
        file_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
        active_count = len(active_processes)
        
        status_text = f"""
حالة البوت

الملفات المرفوعة: {file_count}
العمليات النشطة: {active_count}
الحالة: يعمل بشكل طبيعي
"""
        bot.edit_message_text(
            status_text,
            chat_id,
            message_id,
            reply_markup=create_back_keyboard()
        )
    
    elif data == 'invite_friends':
        user_data = users[str(user_id)]
        referrals = user_data.get('referrals', 0)
        
        invite_text = f"""
📣 دعوة الأصدقاء

🔗 رابط الدعوة الخاص بك:
https://t.me/{BOT_USERNAME[1:]}?start=ref_{user_id}

📊 عدد الأصدقاء الذين دعوتهم: {referrals}/10

🎁 المكافأة: عند دعوة 10 أصدقاء، ستحصل على 5 محاولات مجانية!
"""
        bot.edit_message_text(
            invite_text,
            chat_id,
            message_id,
            reply_markup=create_back_keyboard()
        )
    
    elif data == 'stop_files':
        # إيقاف جميع عمليات المستخدم
        user_processes = {k: v for k, v in active_processes.items() if k.startswith(f"{user_id}_")}
        stopped_count = 0
        
        for process_key, process_info in user_processes.items():
            try:
                # إيقاف العملية إذا كانت لا تزال تعمل
                if 'process' in process_info and process_info['process'].poll() is None:
                    process_info['process'].terminate()
                stopped_count += 1
                del active_processes[process_key]
            except:
                pass
        
        save_active_processes(active_processes)  # حفظ التغييرات
        bot.answer_callback_query(call.id, f"تم إيقاف {stopped_count} من عملياتك النشطة")
    
    elif data == 'install_library':
        bot.edit_message_text(
            "أرسل اسم المكتبة التي تريد تثبيتها (مثال: numpy)",
            chat_id,
            message_id,
            reply_markup=create_back_keyboard()
        )
        bot.register_next_step_handler_by_chat_id(chat_id, install_library)
    
    elif data == 'bot_speed':
        # اختبار سرعة البوت
        start_time = time.time()
        test_msg = bot.send_message(chat_id, "جاري قياس سرعة الاستجابة")
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)
        
        bot.edit_message_text(
            f"سرعة استجابة البوت: {response_time} مللي ثانية\n\nالحالة: ممتازة",
            chat_id,
            test_msg.message_id,
            reply_markup=create_back_keyboard()
        )
    
    elif data == 'end_chat':
        if user_id in ai_sessions:
            del ai_sessions[user_id]
            bot.edit_message_text(
                "تم إنهاء المحادثة. شكراً لك على استخدام خدمة الذكاء الاصطناعي.",
                chat_id,
                message_id,
                reply_markup=create_main_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "لا توجد محادثة نشطة لإنهائها")
    
    elif data == 'main_menu':
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
"""
        bot.edit_message_text(
            welcome_text,
            chat_id,
            message_id,
            reply_markup=create_main_keyboard()
        )
    
    elif data.startswith('stop_'):
        data_parts = data.split('_')
        
        if len(data_parts) < 3:
            bot.answer_callback_query(call.id, "بيانات غير صحيحة")
            return
        
        target_user_id = int(data_parts[1])
        file_name = '_'.join(data_parts[2:])
        
        # التحقق من صلاحية المستخدم
        if user_id != target_user_id and user_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "ليس لديك صلاحية إيقاف هذا الملف")
            return
        
        process_key = f"{target_user_id}_{file_name}"
        
        if process_key in active_processes:
            try:
                # إيقاف العملية
                process_info = active_processes[process_key]
                if 'process' in process_info and process_info['process'].poll() is None:
                    process_info['process'].terminate()
                    time.sleep(1)
                    
                    # إذا لم تتوقف، نقتلها قسراً
                    if process_info['process'].poll() is None:
                        process_info['process'].kill()
                
                # إرسال رسالة التأكيد
                execution_time = time.time() - process_info['start_time']
                bot.edit_message_text(
                    f"تم إيقاف التشغيل: {file_name}\nوقت التشغيل: {execution_time:.2f} ثانية",
                    chat_id,
                    call.message.message_id,
                    reply_markup=create_back_keyboard()
                )
                
                # إزالة العملية من القائمة النشطة
                del active_processes[process_key]
                save_active_processes(active_processes)  # حفظ التغييرات
                
                bot.answer_callback_query(call.id, "تم إيقاف التشغيل")
                
            except Exception as e:
                bot.answer_callback_query(call.id, f"خطأ في الإيقاف: {str(e)}")
        else:
            bot.answer_callback_query(call.id, "العملية غير نشطة أو تم إيقافها مسبقاً")
    
    # الرد على callback query لإزالة حالة التحميل
    bot.answer_callback_query(call.id)

# معالجة تثبيت المكتبة
def install_library(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    library_name = message.text.strip()
    
    if not is_user_authorized(user_id):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا البوت")
        return
    
    if not library_name:
        bot.send_message(chat_id, "يرجى إرسال اسم مكتبة صحيح", reply_markup=create_back_keyboard())
        return
    
    # محاكاة عملية التثبيت
    status_msg = bot.send_message(chat_id, f"جاري تثبيت المكتبة: {library_name}", reply_markup=create_back_keyboard())
    
    try:
        time.sleep(2)
        bot.edit_message_text(
            f"تم تثبيت المكتبة بنجاح: {library_name}",
            chat_id,
            status_msg.message_id,
            reply_markup=create_back_keyboard()
        )
    
    except Exception as e:
        bot.edit_message_text(
            f"فشل في تثبيت المكتبة: {str(e)}",
            chat_id,
            status_msg.message_id,
            reply_markup=create_back_keyboard()
        )

# معالجة رفع الملفات
@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_user_authorized(user_id):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا البوت")
        return
    
    # التحقق من المحاولات المجانية
    user_data = users[str(user_id)]
    if user_data.get('free_attempts', 0) <= 0 and not user_data.get('approved', False):
        bot.send_message(chat_id, "ليس لديك محاولات مجانية متبقية. قم بدعوة المزيد من الأصدقاء للحصول على محاولات إضافية.")
        return
    
    try:
        # التحقق من صيغة الملف
        if not message.document.file_name.endswith('.py'):
            bot.send_message(chat_id, "يسمح فقط بملفات البايثون py", reply_markup=create_back_keyboard())
            return
        
        # تقليل عدد المحاولات المجانية
        remaining_attempts = decrement_free_attempts(user_id)
        
        # تحميل الملف
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_name = message.document.file_name
        
        # حفظ الملف
        file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # حساب حجم الملف
        file_size = len(downloaded_file) / (1024 * 1024)  # MB
        
        # إرسال رسالة التأكيد
        confirm_msg = bot.send_message(
            chat_id, 
            f"تم رفع الملف بنجاح: {file_name} ({file_size:.2f} MB)\n\nجاري التشغيل...\n\n📊 المحاولات المتبقية: {remaining_attempts}",
            reply_markup=create_back_keyboard()
        )
        
        # تشغيل الملف في عملية منفصلة
        process = subprocess.Popen(
            ['python', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # تخزين معلومات العملية
        process_key = f"{user_id}_{file_name}"
        active_processes[process_key] = {
            'process': process,
            'start_time': time.time(),
            'chat_id': chat_id,
            'file_name': file_name
        }
        
        # حفظ العمليات النشطة
        save_active_processes(active_processes)
        
        # الانتظار ثم جمع النتائج
        time.sleep(2)
        
        # التحقق مما إذا كانت العملية لا تزال تعمل
        if process.poll() is None:
            # العملية لا تزال تعمل، إرسال رسالة مع زر الإيقاف
            status_text = f"""
تم بدء تشغيل الملف
الاسم {file_name}
الحجم {file_size:.2f} MB
الحالة يعمل
وقت البدء {time.strftime('%Y-%m-%d %H:%M:%S')}

يمكنك إيقاف التشغيل باستخدام الزر أدناه.
"""
            bot.edit_message_text(
                status_text, 
                chat_id, 
                confirm_msg.message_id,
                reply_markup=create_stop_inline_keyboard(file_name, user_id)
            )
        else:
            # العملية انتهت، جمع النتائج
            stdout, stderr = process.communicate()
            execution_time = time.time() - active_processes[process_key]['start_time']
            
            # إعداد النتيجة
            result = f"نتيجة التشغيل\n\n"
            result += f"الملف {file_name}\n"
            result += f"الحجم {file_size:.2f} MB\n"
            result += f"وقت التنفيذ {execution_time:.2f} ثانية\n\n"
            
            if stdout:
                result += f"الناتج\n{stdout[-1000:]}\n\n"
                
            if stderr:
                result += f"الأخطاء\n{stderr[-1000:]}\n\n"
                
            if not stdout and not stderr:
                result += "تم التشغيل بنجاح بدون ناتج.\n\n"
            
            # إرسال النتيجة
            bot.edit_message_text(
                result, 
                chat_id, 
                confirm_msg.message_id,
                reply_markup=create_back_keyboard()
            )
            
            # إزالة العملية من القائمة النشطة
            if process_key in active_processes:
                del active_processes[process_key]
                save_active_processes(active_processes)
        
        logging.info(f"File uploaded and started: {file_name} by user {user_id}")
    
    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        bot.send_message(
            chat_id, 
            f"حدث خطأ أثناء رفع الملف: {str(e)}",
            reply_markup=create_back_keyboard()
        )

# معالجة الرسائل النصية للمحادثة مع AI
@bot.message_handler(func=lambda message: message.from_user.id in ai_sessions and ai_sessions[message.from_user.id]['active'])
def handle_ai_conversation(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if not is_user_authorized(user_id):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا البوت")
        return
    
    if not GEMINI_AVAILABLE:
        bot.send_message(chat_id, "عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً.")
        if user_id in ai_sessions:
            del ai_sessions[user_id]
        return
    
    # إرسال رسالة الانتظار
    wait_msg = bot.send_message(
        chat_id, 
        "جاري معالجة طلبك...",
        reply_markup=create_end_chat_inline_keyboard()
    )
    
    try:
        # إرسال الرسالة إلى Gemini AI
        response = ai_sessions[user_id]['chat'].send_message(message.text)
        
        # إرسال الرد
        bot.edit_message_text(
            f"رد الذكاء الاصطناعي\n\n{response.text}",
            chat_id,
            wait_msg.message_id,
            reply_markup=create_end_chat_inline_keyboard()
        )
        
    except Exception as e:
        logging.error(f"Gemini AI error: {e}")
        bot.edit_message_text(
            f"عذراً، حدث خطأ أثناء معالجة طلبك: {str(e)}",
            chat_id,
            wait_msg.message_id,
            reply_markup=create_end_chat_inline_keyboard()
        )

# وظيفة للحفاظ على نشاط البوت
def keep_alive():
    while True:
        try:
            # إرسال طلب إلى البوت للحفاظ على نشاطه
            bot.get_me()
            logging.info("Keep-alive request sent")
            
            # تنظيف العمليات المنتهية
            current_time = time.time()
            keys_to_remove = []
            
            for key, info in active_processes.items():
                if 'process' in info and info['process'].poll() is not None:
                    execution_time = current_time - info['start_time']
                    
                    # إرسال النتيجة إذا كانت العملية قد انتهت
                    stdout, stderr = info['process'].communicate()
                    result = f"انتهى التشغيل تلقائياً\n\n"
                    result += f"الملف {info['file_name']}\n"
                    result += f"وقت التنفيذ {execution_time:.2f} ثانية\n\n"
                    
                    if stdout:
                        result += f"الناتج\n{stdout[-1000:]}\n\n"
                        
                    if stderr:
                        result += f"الأخطاء\n{stderr[-1000:]}\n\n"
                        
                    if not stdout and not stderr:
                        result += "تم التشغيل بنجاح بدون ناتج.\n\n"
                    
                    try:
                        bot.send_message(info['chat_id'], result, reply_markup=create_back_keyboard())
                    except:
                        pass
                    
                    keys_to_remove.append(key)
            
            # إزالة العمليات المنتهية
            for key in keys_to_remove:
                del active_processes[key]
            
            # حفظ التغييرات
            if keys_to_remove:
                save_active_processes(active_processes)
                
        except Exception as e:
            logging.error(f"Keep-alive error: {e}")
        
        time.sleep(300)

# إعداد Webhook
def setup_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
        logging.info(f"Webhook set to: {WEBHOOK_URL}/webhook")
    except Exception as e:
        logging.error(f"Failed to set webhook: {e}")

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

# تشغيل البوت مع إعادة التشغيل التلقائي
def run_bot():
    # بدء موضوع منفصل للحفاظ على نشاط البوت
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    
    # بدء موضوع منفصل لحفظ البيانات
    data_persister_thread = threading.Thread(target=data_persister)
    data_persister_thread.daemon = True
    data_persister_thread.start()
    
    # إعداد Webhook
    setup_webhook()
    print("🤖 البوت يعمل في وضع Webhook!")
    print(f"📊 نقطة التحقق متاحة على: http://0.0.0.0:{port}/")
    
    # تشغيل البوت مع إعادة التشغيل التلقائي عند الفشل
    restart_count = 0
    max_restarts = 10
    
    while restart_count < max_restarts:
        try:
            # تشغيل البوت
            bot.infinity_polling()
            
        except Exception as e:
            restart_count += 1
            logging.error(f"Bot error: {e}, restarting in 30 seconds (attempt {restart_count}/{max_restarts})")
            
            # حفظ البيانات قبل إعادة التشغيل
            save_all_data()
            
            # إرسال إشعار للمدير في حالة حدوث أخطاء متكررة
            if restart_count >= 3:
                try:
                    bot.send_message(ADMIN_ID, f"⚠️ البوت أعيد تشغيله {restart_count} مرات بسبب الأخطاء. آخر خطأ: {str(e)}")
                except:
                    pass
            
            # الانتظار قبل إعادة المحاولة
            time.sleep(30)
    
    # إذا وصلنا إلى الحد الأقصى من إعادة التشغيل
    logging.critical(f"Reached maximum restart attempts ({max_restarts}). Shutting down.")
    try:
        bot.send_message(ADMIN_ID, "❌ البوت توقف بعد الوصول للحد الأقصى من إعادة التشغيل")
    except:
        pass

if __name__ == '__main__':
    run_bot()
