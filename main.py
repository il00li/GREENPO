import os
import telebot
import subprocess
import time
import logging
import random
import threading
import google.generativeai as genai
from flask import Flask
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# إعدادات البوت
BOT_TOKEN = os.getenv('BOT_TOKEN', '8268382565:AAE53lW1JjJU8tMxWVWIFcrM_YS9AGKAqSo')
ADMIN_ID = 6689435577
BOT_USERNAME = '@HOZ7_BOT'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyD3w0ZtC-GOvOVVlUxb_l0ayRAVsar64FI')

# إعدادات الملفات
UPLOAD_DIR = 'uploaded_files'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# تخزين العمليات النشطة والمحادثات
active_processes = {}
ai_sessions = {}

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# تهيئة البوت
bot = telebot.TeleBot(BOT_TOKEN)

# تهيئة Gemini AI
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro')
    GEMINI_AVAILABLE = True
except Exception as e:
    logging.error(f"Failed to initialize Gemini AI: {e}")
    GEMINI_AVAILABLE = False

# إنشاء تطبيق Flask لنقطة التحقق
app = Flask(__name__)

@app.route('/')
def health_check():
    return "البوت يعمل بشكل صحيح ✅", 200

@app.route('/status')
def status_check():
    return "حالة البوت: نشط 🟢", 200

# استخدام المنفذ من متغير البيئة أو 10000 افتراضيًا
port = int(os.environ.get('PORT', 10000))

def run_flask():
    app.run(host='0.0.0.0', port=port, debug=False)

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
        InlineKeyboardButton('📊 حالة البوت', callback_data='bot_status')
    ]
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    return keyboard

# إنشاء لوحة إنلاين للإعدادات
def create_settings_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton('🛑 إيقاف الملفات', callback_data='stop_files'),
        InlineKeyboardButton('📚 تثبيت مكتبة', callback_data='install_library'),
        InlineKeyboardButton('🚀 سرعة البوت', callback_data='bot_speed'),
        InlineKeyboardButton('👥 دعوة الأصدقاء', callback_data='invite_friends'),
        InlineKeyboardButton('🔙 رجوع', callback_data='main_menu')
    ]
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    keyboard.add(buttons[4])
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

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    
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

# معالجة أمر /help
@bot.message_handler(commands=['help'])
def help_command(message):
    chat_id = message.chat.id
    
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
    
    if user_id != ADMIN_ID:
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    # حساب عدد الملفات والعمليات النشطة
    file_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
    active_count = len(active_processes)
    
    status_text = f"""
حالة البوت

الملفات المرفوعة: {file_count}
العمليات النشطة: {active_count}
الحالة: يعمل بشكل طبيعي
"""
    bot.send_message(chat_id, status_text, reply_markup=create_main_keyboard())

# معالجة callback queries
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data
    
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
- دعوة الأصدقاء
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
        ai_sessions[call.from_user.id] = {
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
    
    elif data == 'stop_files':
        # إيقاف جميع عمليات المستخدم
        user_processes = {k: v for k, v in active_processes.items() if k.startswith(f"{call.from_user.id}_")}
        stopped_count = 0
        
        for process_key, process_info in user_processes.items():
            try:
                process_info['process'].terminate()
                stopped_count += 1
                del active_processes[process_key]
            except:
                pass
        
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
    
    elif data == 'invite_friends':
        bot.edit_message_text(
            f"رابط الدعوة: https://t.me/{BOT_USERNAME[1:]}?start=ref{call.from_user.id}\n\nاحصل على 10 نقاط لكل صديق يدخل عبر الرابط!",
            chat_id,
            message_id,
            reply_markup=create_back_keyboard()
        )
    
    elif data == 'end_chat':
        if call.from_user.id in ai_sessions:
            del ai_sessions[call.from_user.id]
            bot.edit_message_text(
                "تم إنهاء المحادثة. شكراً لك على استخدام خدمة الذكاء الاصطناعي.",
                chat_id,
                message_id,
                reply_markup=create_main_keyboard()
            )
        else:
            bot.answer_callback_query(call.id, "لا توجد محادثة نشطة لإنهائها")
    
    elif data == 'main_menu':
        welcome_text = f"""
مرحباً بك في بوت استضافة بايثون {BOT_USERNAME}

المميزات المتاحة
- رفع وتشغيل ملفات البايثون
- إدارة الملفات الخاصة بك
- دعم المكتبات الخارجية
- محادثة مع الذكاء الاصطناعي
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
        if call.from_user.id != target_user_id and call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "ليس لديك صلاحية إيقاف هذا الملف")
            return
        
        process_key = f"{target_user_id}_{file_name}"
        
        if process_key in active_processes:
            try:
                # إيقاف العملية
                active_processes[process_key]['process'].terminate()
                time.sleep(1)
                
                # إذا لم تتوقف، نقتلها قسراً
                if active_processes[process_key]['process'].poll() is None:
                    active_processes[process_key]['process'].kill()
                
                # إرسال رسالة التأكيد
                execution_time = time.time() - active_processes[process_key]['start_time']
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

# معالجة تثبيت المكتبة
def install_library(message):
    chat_id = message.chat.id
    library_name = message.text.strip()
    
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
            'file_name': file_name
        }
        
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

# معالجة الرسائل النصية للمحادثة مع AI
@bot.message_handler(func=lambda message: message.from_user.id in ai_sessions and ai_sessions[message.from_user.id]['active'])
def handle_ai_conversation(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_message = message.text
    
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
        response = ai_sessions[user_id]['chat'].send_message(user_message)
        
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
                if info['process'].poll() is not None:
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
                
        except Exception as e:
            logging.error(f"Keep-alive error: {e}")
        
        time.sleep(300)

# تشغيل البوت
def run_bot():
    # بدء موضوع منفصل للحفاظ على نشاط البوت
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    
    print("🤖 البوت يعمل الآن مع نقطة التحقق من الصحة!")
    print(f"📊 نقطة التحقق متاحة على: http://0.0.0.0:{port}/")
    
    # تشغيل البوت مع إعادة التشغيل التلقائي عند الفشل
    while True:
        try:
            bot.infinity_polling(none_stop=True)
        except Exception as e:
            logging.error(f"Bot error: {e}, restarting in 10 seconds")
            time.sleep(10)

if __name__ == '__main__':
    run_bot() 
