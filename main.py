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
import base64

# إعدادات البوت
BOT_TOKEN = os.getenv('BOT_TOKEN', '8268382565:AAEWFoh0hUKZ0V70mPWzltWxRdZiUbjj-xM')
ADMIN_ID = 6689435577
BOT_USERNAME = '@HOZ7_BOT'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyD3w0ZtC-GOvOVVlUxb_l0ayRAVsar64FI')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://greenpo-1.onrender.com')
CHANNEL_ID = os.getenv('CHANNEL_ID', '-1003091756917')  # معرف القناة

# إعدادات الملفات
UPLOAD_DIR = 'uploaded_files'
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

# تحميل بيانات المستخدمين من القناة
def load_users():
    users = {}
    try:
        # استخدام طريقة بديلة للحصول على الرسائل من القناة
        # (لاحظ أن pyTelegramBotAPI لا يدعم get_chat_history مباشرة)
        # سنستخدم أسلوباً بديلاً لتخزين البيانات
        pass
    except Exception as e:
        logging.error(f"Failed to load users from channel: {e}")
    
    return users

# حفظ بيانات المستخدمين في القناة
def save_user_to_channel(user_id, user_data):
    try:
        user_message = f"USER_DATA:{json.dumps({user_id: user_data})}"
        bot.send_message(CHANNEL_ID, user_message, disable_notification=True)
        return True
    except Exception as e:
        logging.error(f"Failed to save user to channel: {e}")
        return False

# تحميل بيانات المستخدم من القناة
def load_user_from_channel(user_id):
    try:
        # هذه وظيفة تحتاج إلى تنفيذ أكثر تعقيداً للحصول على البيانات من القناة
        # في الإصدار الحالي، سنستخدم تخزيناً محلياً كبديل
        return None
    except Exception as e:
        logging.error(f"Failed to load user from channel: {e}")
        return None

# حفظ معلومات الملف في القناة
def save_file_info_to_channel(user_id, file_name, file_data):
    try:
        file_message = f"FILE_DATA:{json.dumps({f'{user_id}_{file_name}': file_data})}"
        bot.send_message(CHANNEL_ID, file_message, disable_notification=True)
        return True
    except Exception as e:
        logging.error(f"Failed to save file info to channel: {e}")
        return False

# حفظ معلومات العملية في القناة
def save_process_info_to_channel(process_key, process_data):
    try:
        process_message = f"PROCESS_DATA:{json.dumps({process_key: process_data})}"
        bot.send_message(CHANNEL_ID, process_message, disable_notification=True)
        return True
    except Exception as e:
        logging.error(f"Failed to save process info to channel: {e}")
        return False

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
    # في هذا الإصدار المبسط، سنعتبر جميع المستخدمين مصرحين
    # يمكن تطوير هذه الوظيفة لاحقاً
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
مرحباً بك في بوت استضافة بايثون {BOT_USERNAME}

المميزات المتاحة
- رفع وتشغيل ملفات البايثون
- إدارة الملفات الخاصة بك
- دعم المكتبات الخارجية
- محادثة مع الذكاء الاصطناعي

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
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(chat_id, "استخدام خاطئ: /ban <user_id> [سبب الحظر]")
            return
        
        target_user_id = parts[1]
        ban_reason = ' '.join(parts[2:]) if len(parts) > 2 else "غير محدد"
        
        # حفظ بيانات الحظر في القناة
        ban_data = {
            'user_id': target_user_id,
            'banned_by': user_id,
            'ban_reason': ban_reason,
            'ban_date': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        save_process_info_to_channel(f"BAN_{target_user_id}", ban_data)
        
        # إرسال رسالة للمستخدم المحظور
        try:
            bot.send_message(
                target_user_id, 
                f"⛔ تم حظر حسابك من استخدام البوت.\n\nالسبب: {ban_reason}\n\nللمزيد من المعلومات، تواصل مع المدير."
            )
        except:
            pass
        
        # إرسال تأكيد للمدير
        bot.send_message(
            chat_id, 
            f"✅ تم حظر المستخدم: {target_user_id}\nالسبب: {ban_reason}"
        )
    
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
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(chat_id, "استخدام خاطئ: /unban <user_id>")
            return
        
        target_user_id = parts[1]
        
        # حفظ بيانات إلغاء الحظر في القناة
        unban_data = {
            'user_id': target_user_id,
            'unbanned_by': user_id,
            'unban_date': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        save_process_info_to_channel(f"UNBAN_{target_user_id}", unban_data)
        
        # إرسال رسالة للمستخدم الذي تم إلغاء حظره
        try:
            bot.send_message(target_user_id, "✅ تم إلغاء حظر حسابك. يمكنك الآن استخدام البوت مرة أخرى.")
        except:
            pass
        
        # إرسال تأكيد للمدير
        bot.send_message(chat_id, f"✅ تم إلغاء حظر المستخدم: {target_user_id}")
    
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
        
        # إرسال تأكيد للمدير
        bot.send_message(
            chat_id, 
            f"✅ تم إيقاف {stopped_count} من عمليات المستخدم: {target_user_id}"
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
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(chat_id, "استخدام خاطئ: /restartuser <user_id>")
            return
        
        target_user_id = parts[1]
        
        # البحث عن ملفات المستخدم وإعادة تشغيلها
        # (هذه الوظيفة تحتاج إلى تطوير أكثر في الإصدارات القادمة)
        bot.send_message(
            chat_id, 
            f"⏳ جاري البحث عن ملفات المستخدم {target_user_id} وإعادة تشغيلها..."
        )
    
    except Exception as e:
        logging.error(f"Error in restartuser command: {e}")
        bot.send_message(chat_id, f"حدث خطأ: {str(e)}")

# معالجة أمر /botstats (للمدير فقط)
@bot.message_handler(commands=['botstats'])
def bot_stats_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if str(user_id) != str(ADMIN_ID):
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    file_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
    active_count = len(active_processes)
    
    stats_text = f"""
📊 إحصائيات البوت

الملفات المرفوعة: {file_count}
العمليات النشطة: {active_count}
"""
    bot.send_message(chat_id, stats_text)

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
        
        # إرسال الملف إلى القناة
        file_sent = send_file_to_channel(file_path, user_id, file_name)
        
        # حفظ معلومات الملف في القناة
        file_data = {
            'user_id': user_id,
            'file_name': file_name,
            'file_size': len(downloaded_file),
            'upload_time': time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_file_info_to_channel(user_id, file_name, file_data)
        
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
            'file_name': file_name,
            'user_id': user_id
        }
        
        # حفظ معلومات العملية في القناة
        process_data = {
            'user_id': user_id,
            'file_name': file_name,
            'start_time': time.time(),
            'chat_id': chat_id
        }
        save_process_info_to_channel(process_key, process_data)
        
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
                    
                    bot.answer_callback_query(call.id, "تم إيقاف التشغيل")
                    
                except Exception as e:
                    bot.answer_callback_query(call.id, f"خطأ في الإيقاف: {str(e)}")
            else:
                bot.answer_callback_query(call.id, "العملية غير نشطة أو تم إيقافها مسبقاً")
        
        # الرد على callback query لإزالة حالة التحميل
        bot.answer_callback_query(call.id)
    
    except Exception as e:
        logging.error(f"Error in callback query: {e}")
        bot.answer_callback_query(call.id, "حدث خطأ أثناء معالجة طلبك")

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
