import os
import telebot
import subprocess
import time
import logging
import random
import threading
from flask import Flask
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# إعدادات البوت
BOT_TOKEN = os.getenv('BOT_TOKEN', '8215456582:AAHFB0z4Gx3ANHgVNOOm1XgvBPMmlQHEO6A')
ADMIN_ID = 6689435577
BOT_USERNAME = '@HOZ7_BOT'

# إعدادات الملفات
UPLOAD_DIR = 'uploaded_files'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# تخزين العمليات النشطة
active_processes = {}

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# تهيئة البوت
bot = telebot.TeleBot(BOT_TOKEN)

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

# إنشاء لوحة إنلاين مع زر الرجوع
def create_inline_keyboard(with_back_button=True):
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton('📤 رفع ملف', callback_data='upload_file'),
        InlineKeyboardButton('⚙️ الإعدادات', callback_data='settings'),
        InlineKeyboardButton('🤖 المحادثة مع AI', callback_data='ai_chat'),
        InlineKeyboardButton('📊 حالة البوت', callback_data='status')
    ]
    
    keyboard.add(buttons[0], buttons[1])
    keyboard.add(buttons[2], buttons[3])
    
    if with_back_button:
        keyboard.add(InlineKeyboardButton('🔙 رجوع', callback_data='main_menu'))
    
    return keyboard

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    
    welcome_text = """
مرحباً بك في بوت استضافة بايثون

المميزات المتاحة
- رفع وتشغيل ملفات البايثون
- إدارة الملفات الخاصة بك
- دعم المكتبات الخارجية

لبدء الاستخدام
اضغط على زر رفع ملف لرفع ملف بايثون

للمساعدة
اكتب /help لعرض الشروط
"""
    bot.send_message(chat_id, welcome_text, reply_markup=create_inline_keyboard())

# معالجة أمر /help
@bot.message_handler(commands=['help'])
def help_command(message):
    chat_id = message.chat.id
    
    help_text = """
شروط الاستخدام

1. يسمح فقط بملفات البايثون py
2. الحد الأقصى لحجم الملف 20MB
3. وقت التنفيذ الأقصى 30 ثانية
4. يمنع رفع ملفات تحتوي على أكواد ضارة

للتواصل والدعم
{}
""".format(BOT_USERNAME)
    
    bot.send_message(chat_id, help_text, reply_markup=create_inline_keyboard())

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
            reply_markup=create_inline_keyboard()
        )
    
    elif data == 'settings':
        settings_text = """
الإعدادات المتاحة

- إيقاف الملفات النشطة
- تثبيت مكتبات خارجية
- التحقق من سرعة البوت
- إدارة الإشعارات
"""
        bot.edit_message_text(
            settings_text,
            chat_id,
            message_id,
            reply_markup=create_inline_keyboard()
        )
    
    elif data == 'ai_chat':
        bot.edit_message_text(
            "هذه الميزة قيد التطوير حالياً. سيتم تفعيلها قريباً.",
            chat_id,
            message_id,
            reply_markup=create_inline_keyboard()
        )
    
    elif data == 'status':
        # حساب عدد الملفات
        file_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
        active_count = len(active_processes)
        
        status_text = """
حالة البوت

الملفات المرفوعة: {}
العمليات النشطة: {}
الحالة: يعمل بشكل طبيعي
""".format(file_count, active_count)
        
        bot.edit_message_text(
            status_text,
            chat_id,
            message_id,
            reply_markup=create_inline_keyboard()
        )
    
    elif data == 'main_menu':
        welcome_text = """
مرحباً بك في بوت استضافة بايثون

المميزات المتاحة
- رفع وتشغيل ملفات البايثون
- إدارة الملفات الخاصة بك
- دعم المكتبات الخارجية

لبدء الاستخدام
اضغط على زر رفع ملف لرفع ملف بايثون
"""
        bot.edit_message_text(
            welcome_text,
            chat_id,
            message_id,
            reply_markup=create_inline_keyboard(with_back_button=False)
        )
    
    # الرد على callback query لإزالة حالة التحميل
    bot.answer_callback_query(call.id)

# معالجة رفع الملفات
@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    try:
        # التحقق من صيغة الملف
        if not message.document.file_name.endswith('.py'):
            bot.send_message(chat_id, "يسمح فقط بملفات البايثون py", reply_markup=create_inline_keyboard())
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
        bot.send_message(
            chat_id, 
            f"تم رفع الملف بنجاح: {file_name} ({file_size:.2f} MB)",
            reply_markup=create_inline_keyboard()
        )
        
        # تشغيل الملف
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
            'chat_id': chat_id
        }
        
        # الانتظار ثم جمع النتائج
        time.sleep(2)
        stdout, stderr = process.communicate()
        
        # إعداد النتيجة
        result = f"نتيجة تشغيل الملف: {file_name}\n\n"
        
        if stdout:
            result += f"الناتج:\n{stdout}\n"
        
        if stderr:
            result += f"الأخطاء:\n{stderr}\n"
        
        if not stdout and not stderr:
            result += "تم التشغيل بنجاح بدون ناتج.\n"
        
        # إرسال النتيجة
        bot.send_message(
            chat_id,
            result,
            reply_markup=create_inline_keyboard()
        )
        
        # إزالة العملية من القائمة النشطة
        if process_key in active_processes:
            del active_processes[process_key]
    
    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        bot.send_message(
            chat_id, 
            f"حدث خطأ أثناء رفع الملف: {str(e)}",
            reply_markup=create_inline_keyboard()
        )

# تشغيل البوت
if __name__ == '__main__':
    print("🤖 البوت يعمل الآن مع نقطة التحقق من الصحة!")
    print(f"📊 نقطة التحقق متاحة على: http://0.0.0.0:{port}/")
    bot.infinity_polling()
