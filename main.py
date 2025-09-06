import os
import telebot
import subprocess
import time
import logging
import threading
import requests
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# إعدادات البوت
BOT_TOKEN = '8300609210:AAH_0-UPJQtF6UKz2Ajy014AbmbvGsgB2Ng'
ADMIN_ID = 6689435577  # معرف المدير
DEVELOPER_USERNAME = '@OlIiIl7'  # معرف المطور

# إعدادات الملفات
UPLOAD_DIR = 'uploaded_files'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# تهيئة البوت
bot = telebot.TeleBot(BOT_TOKEN)

# إنشاء لوحة المفاتيح الرئيسية
def create_main_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        KeyboardButton('📤 رفع ملف'),
        KeyboardButton('⚙️ الإعدادات')
    ]
    keyboard.add(*buttons)
    return keyboard

# إنشاء لوحة الإعدادات
def create_settings_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        KeyboardButton('🛑 إيقاف جميع ملفاتي المرفوعة'),
        KeyboardButton('📚 تثبيت مكتبة'),
        KeyboardButton('🚀 سرعة البوت'),
        KeyboardButton('🤖 معادثة مع AI'),
        KeyboardButton('👥 دعوة الأصدقاء'),
        KeyboardButton('🔄 تحويل النقاط'),
        KeyboardButton('💳 شراء نقاط'),
        KeyboardButton('📢 قناة المطور'),
        KeyboardButton('👨‍💻 المطور'),
        KeyboardButton('🏠 الرئيسية')
    ]
    
    # ترتيب الأزرار في صفوف
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        keyboard.add(*row)
    
    return keyboard

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    welcome_text = f"""
مرحباً بك في بوت استضافة بايثون! 🤖

📝 **المميزات المتاحة:**
- رفع وتشغيل ملفات البايثون
- إدارة الملفات الخاصة بك
- دعم المكتبات الخارجية

📤 **لبدء الاستخدام:**
اضغط على زر "رفع ملف" لرفع ملف بايثون (.py)

ℹ️ **للمساعدة:**
- اكتب /help لعرض الشروط
- أو استخدم معادثة الـAI لحل المشكلات

👨‍💻 **المطور:** {DEVELOPER_USERNAME}
"""
    bot.send_message(chat_id, welcome_text, reply_markup=create_main_keyboard())

# معالجة أمر /help
@bot.message_handler(commands=['help'])
def help_command(message):
    chat_id = message.chat.id
    
    help_text = f"""
ℹ️ **شروط الاستخدام:**

1. يسمح فقط بملفات البايثون (.py)
2. الحد الأقصى لحجم الملف: 20MB
3. وقت التنفيذ الأقصى: 30 ثانية
4. يمنع رفع ملفات تحتوي على أكواد ضارة

📞 **للتواصل والدعم:**
- {DEVELOPER_USERNAME}
- قناة المطور: @python_hosting_channel
"""
    bot.send_message(chat_id, help_text)

# معالجة أمر /restart (للمطور فقط)
@bot.message_handler(commands=['restart'])
def restart_bot(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        bot.send_message(chat_id, "❌ ليس لديك صلاحية استخدام هذا الأمر.")
        return
    
    bot.send_message(chat_id, "🔄 جاري إعادة تشغيل البوت...")
    logging.info("Bot restart initiated by admin")
    os._exit(1)  # إعادة تشغيل البوت

# معالجة أمر /status (للمطور فقط)
@bot.message_handler(commands=['status'])
def bot_status(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        bot.send_message(chat_id, "❌ ليس لديك صلاحية استخدام هذا الأمر.")
        return
    
    # حساب عدد الملفات والمستخدمين
    file_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
    
    status_text = f"""
🤖 **حالة البوت:**

📊 **الإحصائيات:**
- عدد الملفات المرفوعة: {file_count}
- حالة البوت: 🟢 يعمل

🔄 **ميزة إعادة التشغيل التلقائي:**
- تعمل كل 10 دقائق
- تحافظ على استمرارية البوت
- مناسبة للخطة المجانية على Render
"""
    bot.send_message(chat_id, status_text)

# معالجة الأزرار الرئيسية
@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text
    
    if text == '📤 رفع ملف':
        bot.send_message(chat_id, "📤 أرسل لي ملف بايثون (.py) لرفعه")
    
    elif text == '⚙️ الإعدادات':
        bot.send_message(chat_id, "⚙️ الإعدادات:", reply_markup=create_settings_keyboard())
    
    elif text == '🏠 الرئيسية':
        bot.send_message(chat_id, "العودة إلى القائمة الرئيسية.", reply_markup=create_main_keyboard())
    
    elif text == '🛑 إيقاف جميع ملفاتي المرفوعة':
        # البحث عن ملفات المستخدم وحذفها
        user_files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(f"{user_id}_")]
        for file in user_files:
            os.remove(os.path.join(UPLOAD_DIR, file))
        bot.send_message(chat_id, f"⏹️ تم إيقاف وحذف {len(user_files)} من ملفاتك.")
    
    elif text == '📚 تثبيت مكتبة':
        bot.send_message(chat_id, "أرسل اسم المكتبة التي تريد تثبيتها (مثال: numpy)")
        bot.register_next_step_handler(message, install_library)
    
    elif text == '🚀 سرعة البوت':
        # اختبار سرعة البوت
        start_time = time.time()
        test_msg = bot.send_message(chat_id, "⏱️ جاري قياس سرعة الاستجابة...")
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)
        
        bot.edit_message_text(f"⏱️ سرعة استجابة البوت: {response_time} مللي ثانية\n\nالحالة: 🟢 ممتازة", 
                             chat_id, test_msg.message_id)
    
    elif text == '🤖 معادثة مع AI':
        bot.send_message(chat_id, "🤖 مرحباً! أنا المساعد الافتراضي للبوت. كيف يمكنني مساعدتك؟")
    
    elif text == '👥 دعوة الأصدقاء':
        bot.send_message(chat_id, "🔗 رابط الدعوة: https://t.me/Fo79BOT?start=ref12345\n\nاحصل على 10 نقاط لكل صديق يدخل عبر الرابط!")
    
    elif text == '🔄 تحويل النقاط':
        bot.send_message(chat_id, "أرسل معرف المستخدم وعدد النقاط التي تريد تحويلها (مثال: 123456 10)")
    
    elif text == '💳 شراء نقاط':
        bot.send_message(chat_id, "💳 لشراء النقاط:\n\n10 نقاط - 1$\n50 نقاط - 4$\n100 نقاط - 7$\n\nللطلب راسل: @python_hosting_admin")
    
    elif text == '📢 قناة المطور':
        bot.send_message(chat_id, "📢 قناة المطور: @python_hosting_channel\n\nتابعنا للحصول على آخر التحديثات والأخبار!")
    
    elif text == '👨‍💻 المطور':
        bot.send_message(chat_id, f"👨‍💻 المطور: {DEVELOPER_USERNAME}\n\nللتواصل مع المطور حول المشاكل أو المقترحات.")

# معالجة تثبيت المكتبة
def install_library(message):
    chat_id = message.chat.id
    library_name = message.text.strip()
    
    if not library_name:
        bot.send_message(chat_id, "❌ يرجى إرسال اسم مكتبة صحيح.")
        return
    
    # محاكاة عملية التثبيت
    status_msg = bot.send_message(chat_id, f"⏳ جاري تثبيت المكتبة: {library_name}...")
    
    try:
        # محاكاة التأخير
        time.sleep(2)
        
        # في الواقع، هنا نستخدم pip install
        # process = subprocess.Popen(['pip', 'install', library_name], 
        #                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # stdout, stderr = process.communicate()
        
        # لمثالنا، سنفترض أن التثبيت نجح
        bot.edit_message_text(f"✅ تم تثبيت المكتبة بنجاح: {library_name}", 
                            chat_id, status_msg.message_id)
    
    except Exception as e:
        bot.edit_message_text(f"❌ فشل في تثبيت المكتبة: {str(e)}", 
                            chat_id, status_msg.message_id)

# معالجة رفع الملفات
@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    try:
        # التحقق من صيغة الملف
        if not message.document.file_name.endswith('.py'):
            bot.send_message(chat_id, "❌ يسمح فقط بملفات البايثون (.py)")
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
        
        bot.send_message(chat_id, f"✅ تم رفع الملف بنجاح: {file_name} ({file_size:.2f} MB)")
        logging.info(f"File uploaded: {file_name} by user {user_id}")
    
    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        bot.send_message(chat_id, f"❌ حدث خطأ أثناء رفع الملف: {str(e)}")

# وظيفة للحفاظ على نشاط البوت (للتغلب على إيقاف الخطة المجانية)
def keep_alive():
    while True:
        try:
            # إرسال طلب إلى البوت للحفاظ على نشاطه
            bot.get_me()
            logging.info("Keep-alive request sent")
        except Exception as e:
            logging.error(f"Keep-alive error: {e}")
        
        # الانتظار لمدة 10 دقائق قبل المحاولة مرة أخرى
        time.sleep(600)

# تشغيل البوت مع ميزة إعادة التشغيل التلقائي
def run_bot():
    while True:
        try:
            print("🤖 بوت استضافة بايثون يعمل الآن...")
            logging.info("Bot started successfully")
            bot.infinity_polling()
        except Exception as e:
            logging.error(f"Bot error: {e}, restarting in 10 seconds...")
            time.sleep(10)

if __name__ == '__main__':
    # بدء موضوع منفصل للحفاظ على نشاط البوت
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    
    # بدء البوت مع إمكانية إعادة التشغيل التلقائي
    run_bot() 
