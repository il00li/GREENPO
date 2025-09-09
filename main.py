import os
import telebot
import subprocess
import time
import logging
import json
import google.generativeai as genai
from flask import Flask, request
from waitress import serve
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import signal
import requests
import re
import sys
import importlib

# إعدادات البوت
BOT_TOKEN = '8268382565:AAFs5Qk0vogI_9RKnf3PhZWNcS8Sdyupj3A'
ADMIN_ID = 6689435577
BOT_USERNAME = '@HOZ7_BOT'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyD3w0ZtC-GOvOVVlUxb_l0ayRAVsar64FI')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://greenpo-1.onrender.com')
CHANNEL_ID = os.getenv('CHANNEL_ID', '-1003091756917')

# إعدادات الملفات
UPLOAD_DIR = 'uploaded_files'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# تخزين العمليات النشطة والمحادثات
active_processes = {}
ai_sessions = {}
user_sessions = {}

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

# التحقق من المكتبات المستخدمة في الملف
def check_file_libraries(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
        # البحث عن عبارات الاستيراد
        import_patterns = [
            r'import\s+([\w]+)',  # import library
            r'from\s+([\w\.]+)\s+import'  # from library import
        ]
        
        used_libraries = set()
        for pattern in import_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                # استخراج اسم المكتبة الأساسي (أول جزء قبل النقطة)
                lib_name = match.split('.')[0]
                # تجاهل المكتبات القياسية والمدمجة
                if (lib_name not in ['os', 'sys', 'time', 'json', 'math', 'random', 
                                   're', 'datetime', 'threading', 'subprocess', 
                                   'logging', 'signal', 'atexit', 'base64', 'io']) and \
                   (not lib_name.startswith('_')):
                    used_libraries.add(lib_name)
        
        return list(used_libraries)
    except Exception as e:
        logging.error(f"Error checking file libraries: {e}")
        return []

# تثبيت المكتبات المطلوبة
def install_required_libraries(libraries):
    success = True
    installed = []
    failed = []
    
    for lib in libraries:
        try:
            # محاولة استيراد المكتبة للتحقق من تثبيتها
            try:
                importlib.import_module(lib)
                installed.append(lib)
                continue
            except ImportError:
                pass
            
            # تثبيت المكتبة
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])
            installed.append(lib)
            logging.info(f"Successfully installed library: {lib}")
                
        except subprocess.CalledProcessError:
            logging.error(f"Failed to install library: {lib}")
            failed.append(lib)
            success = False
        except Exception as e:
            logging.error(f"Error installing library {lib}: {e}")
            failed.append(lib)
            success = False
    
    return success, installed, failed

# معالجة إشارات النظام
def signal_handler(sig, frame):
    logging.info("Received termination signal, saving data...")
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

# استخدام المنفذ من متغير البيئة
port = int(os.environ.get('PORT', 10000))

# إنشاء لوحة إنلاين رئيسية
def create_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton('📤 رفع ملف', callback_data='upload_file'),
        InlineKeyboardButton('⚙️ الإعدادات', callback_data='settings_menu'),
        InlineKeyboardButton('🤖 محادثة AI', callback_data='ai_chat'),
        InlineKeyboardButton('📊 حالة البوت', callback_data='bot_status'),
        InlineKeyboardButton('📚 إدارة المكتبات', callback_data='manage_libs')
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
        InlineKeyboardButton('📊 إحصائيات', callback_data='stats'),
        InlineKeyboardButton('🔧 إعدادات متقدمة', callback_data='advanced_settings'),
        InlineKeyboardButton('🔙 رجوع', callback_data='main_menu')
    ]
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    return keyboard

# إنشاء لوحة إنلاين لإدارة المكتبات
def create_manage_libs_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton('📥 تثبيت مكتبة', callback_data='install_lib'),
        InlineKeyboardButton('📤 إزالة مكتبة', callback_data='uninstall_lib'),
        InlineKeyboardButton('📋 قائمة المكتبات', callback_data='list_libs'),
        InlineKeyboardButton('🔙 رجوع', callback_data='main_menu')
    ]
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    return keyboard

# إنشاء لوحة إنلاين لإيقاف التشغيل
def create_stop_inline_keyboard(file_name, user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton('🛑 إيقاف التشغيل', callback_data=f'stop_{user_id}_{file_name}'),
        InlineKeyboardButton('🔙 رجوع', callback_data='main_menu')
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
    return True

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"
        
        logging.info(f"Received /start command from user {user_id} ({username})")
        
        welcome_text = f"""
مرحباً بك في بوت استضافة الملفات {BOT_USERNAME}

🎯 هذا البوت مخصص لاستضافة وتشغيل جميع ملفات البايثون

المميزات المتاحة:
- رفع وتشغيل أي ملف بايثون
- دعم جميع المكتبات (سيتم تثبيتها تلقائياً)
- إدارة الملفات الخاصة بك
- محادثة مع الذكاء الاصطناعي للمساعدة
- إدارة المكتبات المثبتة

لبدء الاستخدام:
اضغط على زر "رفع ملف" لرفع ملف بايثون

للمساعدة:
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

# معالجة أمر /help
@bot.message_handler(commands=['help'])
def help_command(message):
    chat_id = message.chat.id
    help_text = f"""
شروط الاستخدام

1. يسمح بملفات البايثون فقط (py)
2. الحد الأقصى لحجم الملف 20MB
3. وقت التنفيذ الأقصى 5 دقائق
4. يمنع رفع ملفات تحتوي على أكواد ضارة
5. يدعم البوت جميع مكتبات بايثون

❌ المحظورات:
- انتهاك الخصوصية
- الاختراق
- الأنشطة غير القانونية

للتواصل والدعم:
{BOT_USERNAME}
"""
    bot.send_message(chat_id, help_text, reply_markup=create_main_keyboard())

# معالجة أمر /install (لتثبيت مكتبة)
@bot.message_handler(commands=['install'])
def install_library_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(chat_id, "استخدام خاطئ: /install <اسم المكتبة>")
            return
        
        lib_name = parts[1]
        
        # محاولة تثبيت المكتبة
        success, installed, failed = install_required_libraries([lib_name])
        
        if success:
            bot.send_message(chat_id, f"✅ تم تثبيت المكتبة بنجاح: {lib_name}")
        else:
            bot.send_message(chat_id, f"❌ فشل تثبيت المكتبة: {lib_name}")
    
    except Exception as e:
        logging.error(f"Error in install command: {e}")
        bot.send_message(chat_id, f"حدث خطأ: {str(e)}")

# معالجة رفع الملفات
@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    try:
        # التحقق من صيغة الملف
        if not message.document.file_name.endswith('.py'):
            bot.send_message(chat_id, "يسمح فقط بملفات البايثون py", reply_markup=create_back_keyboard())
            return
        
        # تحميل الملف
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_name = message.document.file_name
        
        # حفظ الملف
        file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
        
        # التحقق من المكتبات المستخدمة في الملف
        used_libraries = check_file_libraries(file_path)
        
        # إذا كان الملف يستخدم مكتبات، نقوم بتثبيتها
        if used_libraries:
            libs_msg = bot.send_message(chat_id, f"🔍 обнаружено {len(used_libraries)} مكتبة في الملف... جاري التثبيت")
            
            success, installed, failed = install_required_libraries(used_libraries)
            
            if failed:
                # إرسال تحذير ولكن المتابعة في التنفيذ
                warning_msg = f"""
⚠️ فشل تثبيت بعض المكتبات: {', '.join(failed)}
سيتم محاولة تشغيل الملف على أي حال.
"""
                bot.edit_message_text(
                    warning_msg,
                    chat_id,
                    libs_msg.message_id
                )
            else:
                bot.edit_message_text(
                    f"✅ تم تثبيت المكتبات بنجاح: {', '.join(installed)}",
                    chat_id,
                    libs_msg.message_id
                )
        
        # إرسال الملف إلى القناة
        send_file_to_channel(file_path, user_id, file_name)
        
        # حساب حجم الملف
        file_size = len(downloaded_file) / (1024 * 1024)  # MB
        
        # إرسال رسالة التأكيد
        confirm_msg = bot.send_message(
            chat_id, 
            f"تم رفع الملف بنجاح: {file_name} ({file_size:.2f} MB)\n\nجاري التشغيل...",
            reply_markup=create_back_keyboard()
        )
        
        # تشغيل الملف في عملية منفصلة
        process = subprocess.Popen(
            [sys.executable, file_path],
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
            'file_name': file_name,
            'user_id': user_id
        }
        
        # الانتظار ثم جمع النتائج
        time.sleep(2)
        
        # التحقق مما إذا كانت العملية لا تزال تعمل
        if process.poll() is None:
            # العملية لا تزال تعمل، إرسال رسالة مع زر الإيقاف
            status_text = f"""
تم بدء تشغيل الملف
الاسم: {file_name}
الحجم: {file_size:.2f} MB
الحالة: يعمل
وقت البدء: {time.strftime('%Y-%m-%d %H:%M:%S')}

📚 المكتبات المستخدمة: {', '.join(used_libraries) if used_libraries else 'لا توجد'}

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
            
            # إذا فشل التشغيل، لا نحفظ الملف ونرسل رسالة خطأ
            if process.returncode != 0:
                error_msg = f"""
❌ فشل تشغيل الملف: {file_name}

📋 التفاصيل:
{stderr[-1000:] if stderr else 'لا توجد تفاصيل عن الخطأ'}

الملف يحتوي على أخطاء ولم يتم حفظه.
"""
                bot.edit_message_text(
                    error_msg, 
                    chat_id, 
                    confirm_msg.message_id,
                    reply_markup=create_back_keyboard()
                )
                
                # حذف الملف المعطوب
                os.remove(file_path)
                
                # إزالة العملية من القائمة النشطة
                if process_key in active_processes:
                    del active_processes[process_key]
                
                return
            
            # إعداد النتيجة
            result = f"""
✅ تم تشغيل الملف بنجاح

الملف: {file_name}
الحجم: {file_size:.2f} MB
وقت التنفيذ: {execution_time:.2f} ثانية
المكتبات المستخدمة: {', '.join(used_libraries) if used_libraries else 'لا توجد'}
"""
            
            if stdout:
                result += f"\n📤 الناتج:\n{stdout[-1000:]}\n"
                
            if stderr:
                result += f"\n⚠️ التحذيرات:\n{stderr[-1000:]}\n"
                
            if not stdout and not stderr:
                result += "\nتم التشغيل بنجاح بدون ناتج.\n"
            
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
        
        logging.info(f"File uploaded and started: {file_name} by user {user_id}")
    
    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        bot.send_message(
            chat_id, 
            f"حدث خطأ أثناء رفع الملف: {str(e)}",
            reply_markup=create_back_keyboard()
        )

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
                "أرسل لي ملف بايثون (py) لرفعه وتشغيله",
                chat_id,
                message_id,
                reply_markup=create_back_keyboard()
            )
        
        elif data == 'settings_menu':
            settings_text = """
الإعدادات المتاحة

- إيقاف الملفات النشطة
- عرض إحصائيات البوت
- الإعدادات المتقدمة
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
                "مرحباً! أنا مساعد الذكاء الاصطناعي. كيف يمكنني مساعدتك؟\n\nأرسل رسالتك وسأرد عليك.",
                chat_id,
                message_id,
                reply_markup=create_end_chat_inline_keyboard()
            )
        
        elif data == 'bot_status':
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
        
        elif data == 'manage_libs':
            libs_text = """
إدارة المكتبات

يمكنك تثبيت أو إزالة أي مكتبة بايثون
"""
            bot.edit_message_text(
                libs_text,
                chat_id,
                message_id,
                reply_markup=create_manage_libs_keyboard()
            )
        
        elif data == 'install_lib':
            user_sessions[user_id] = {'action': 'install_lib'}
            bot.edit_message_text(
                "أرسل اسم المكتبة التي تريد تثبيتها",
                chat_id,
                message_id,
                reply_markup=create_back_keyboard()
            )
        
        elif data == 'main_menu':
            welcome_text = f"""
مرحباً بك في بوت استضافة الملفات {BOT_USERNAME}

🎯 هذا البوت مخصص لاستضافة وتشغيل جميع ملفات البايثون

المميزات المتاحة:
- رفع وتشغيل أي ملف بايثون
- دعم جميع المكتبات (سيتم تثبيتها تلقائياً)
- إدارة الملفات الخاصة بك
- محادثة مع الذكاء الاصطناعي للمساعدة
- إدارة المكتبات المثبتة
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
                        f"تم إيقاف الملف: {file_name}\nوقت التشغيل: {execution_time:.2f} ثانية",
                        chat_id,
                        message_id,
                        reply_markup=create_back_keyboard()
                    )
                    
                    # إزالة العملية من القائمة النشطة
                    del active_processes[process_key]
                    
                    bot.answer_callback_query(call.id, "تم إيقاف التشغيل")
                    
                except Exception as e:
                    bot.answer_callback_query(call.id, f"خطأ في الإيقاف: {str(e)}")
            else:
                bot.answer_callback_query(call.id, "الملف غير نشط أو تم إيقافه مسبقاً")
        
        # الرد على callback query لإزالة حالة التحميل
        bot.answer_callback_query(call.id)
    
    except Exception as e:
        logging.error(f"Error in callback query: {e}")
        bot.answer_callback_query(call.id, "حدث خطأ أثناء معالجة طلبك")

# معالجة الرسائل النصية
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text
    
    # إذا كانت المحادثة نشطة مع AI
    if user_id in ai_sessions and ai_sessions[user_id]['active']:
        try:
            # إرسال الرسالة إلى AI
            response = ai_sessions[user_id]['chat'].send_message(text)
            bot.send_message(chat_id, response.text, reply_markup=create_end_chat_inline_keyboard())
        except Exception as e:
            logging.error(f"Error in AI chat: {e}")
            bot.send_message(chat_id, "عذراً، حدث خطأ في خدمة الذكاء الاصطناعي. يرجى المحاولة لاحقاً.")
    
    # إذا كان المستخدم يريد تثبيت مكتبة
    elif user_id in user_sessions and user_sessions[user_id]['action'] == 'install_lib':
        try:
            # محاولة تثبيت المكتبة
            success, installed, failed = install_required_libraries([text])
            
            if success:
                bot.send_message(chat_id, f"✅ تم تثبيت المكتبة بنجاح: {text}")
            else:
                bot.send_message(chat_id, f"❌ فشل تثبيت المكتبة: {text}")
            
            # مسح حالة المستخدم
            del user_sessions[user_id]
            
        except Exception as e:
            logging.error(f"Error installing library: {e}")
            bot.send_message(chat_id, f"حدث خطأ أثناء تثبيت المكتبة: {str(e)}")
    
    else:
        # إذا لم تكن محادثة AI، عرض القائمة الرئيسية
        bot.send_message(chat_id, "مرحباً! اختر خياراً من القائمة:", reply_markup=create_main_keyboard())

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

# تشغيل البوت مع إعداد Webhook
def run_bot():
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
