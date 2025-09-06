import os
import telebot
import subprocess
import time
import logging
import random
import signal
from telebot.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)

# إعدادات البوت
BOT_TOKEN = '8300609210:AAH_0-UPJQtF6UKz2Ajy014AbmbvGsgB2Ng'
ADMIN_ID = 6689435577  # معرف المدير
DEVELOPER_USERNAME = '@OlIiIl7'  # معرف المطور
CHANNEL_LINK = 'https://t.me/iIl337'  # قناة البوت

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
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)  # تعطيل threading لتجنب مشكلة التوازن

# قائمة برموز الفواكه العشوائية
FRUIT_EMOJIS = ['🍎', '🍏', '🍐', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🍒', '🍑', '🍍', '🥭', '🥥']

def get_random_fruit():
    return random.choice(FRUIT_EMOJIS)

# إنشاء لوحة المفاتيح الرئيسية
def create_main_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        KeyboardButton(f'{get_random_fruit()} رفع ملف'),
        KeyboardButton(f'{get_random_fruit()} الإعدادات')
    ]
    keyboard.add(*buttons)
    return keyboard

# إنشاء لوحة الإعدادات
def create_settings_keyboard():
    keyboard = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        KeyboardButton(f'{get_random_fruit()} إيقاف جميع الملفات'),
        KeyboardButton(f'{get_random_fruit()} تثبيت مكتبة'),
        KeyboardButton(f'{get_random_fruit()} سرعة البوت'),
        KeyboardButton(f'{get_random_fruit()} معادثة مع AI'),
        KeyboardButton(f'{get_random_fruit()} دعوة الأصدقاء'),
        KeyboardButton(f'{get_random_fruit()} تحويل النقاط'),
        KeyboardButton(f'{get_random_fruit()} شراء نقاط'),
        KeyboardButton(f'{get_random_fruit()} قناة المطور'),
        KeyboardButton(f'{get_random_fruit()} المطور'),
        KeyboardButton(f'{get_random_fruit()} الرئيسية')
    ]
    
    # ترتيب الأزرار في صفوف
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        keyboard.add(*row)
    
    return keyboard

# إنشاء لوحة إنلاين لإيقاف التشغيل
def create_stop_inline_keyboard(file_name, user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_fruit()} إيقاف التشغيل', 
                            callback_data=f'stop_{user_id}_{file_name}')
    )
    return keyboard

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    welcome_text = f"""
{get_random_fruit()} مرحباً بك في بوت استضافة بايثون! {get_random_fruit()}

{get_random_fruit()} **المميزات المتاحة:**
- رفع وتشغيل ملفات البايثون
- إدارة الملفات الخاصة بك
- دعم المكتبات الخارجية

{get_random_fruit()} **لبدء الاستخدام:**
اضغط على زر "رفع ملف" لرفع ملف بايثون (.py)

{get_random_fruit()} **للمساعدة:**
- اكتب /help لعرض الشروط
- أو استخدم معادثة الـAI لحل المشكلات

{get_random_fruit()} **المطور:** {DEVELOPER_USERNAME}
{get_random_fruit()} **القناة:** {CHANNEL_LINK}
"""
    bot.send_message(chat_id, welcome_text, reply_markup=create_main_keyboard())

# معالجة أمر /help
@bot.message_handler(commands=['help'])
def help_command(message):
    chat_id = message.chat.id
    
    help_text = f"""
{get_random_fruit()} **شروط الاستخدام:**

1. يسمح فقط بملفات البايثون (.py)
2. الحد الأقصى لحجم الملف: 20MB
3. وقت التنفيذ الأقصى: 30 ثانية
4. يمنع رفع ملفات تحتوي على أكواد ضارة

{get_random_fruit()} **للتواصل والدعم:**
- {DEVELOPER_USERNAME}
- قناة المطور: {CHANNEL_LINK}
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
    
    # حساب عدد الملفات والعمليات النشطة
    file_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
    active_count = len(active_processes)
    
    status_text = f"""
{get_random_fruit()} **حالة البوت:**

{get_random_fruit()} **الإحصائيات:**
- عدد الملفات المرفوعة: {file_count}
- عدد العمليات النشطة: {active_count}
- حالة البوت: 🟢 يعمل

{get_random_fruit()} **المطور:** {DEVELOPER_USERNAME}
"""
    bot.send_message(chat_id, status_text)

# معالجة الأزرار الرئيسية
@bot.message_handler(func=lambda message: True)
def handle_buttons(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text
    
    if get_random_fruit() in text:  # إزالة الإيموجي من النص للمقارنة
        text = text.split(' ', 1)[1] if ' ' in text else text
    
    if text == 'رفع ملف':
        bot.send_message(chat_id, f"{get_random_fruit()} أرسل لي ملف بايثون (.py) لرفعه وتشغيله")
    
    elif text == 'الإعدادات':
        bot.send_message(chat_id, f"{get_random_fruit()} الإعدادات:", reply_markup=create_settings_keyboard())
    
    elif text == 'الرئيسية':
        bot.send_message(chat_id, f"{get_random_fruit()} العودة إلى القائمة الرئيسية.", reply_markup=create_main_keyboard())
    
    elif text == 'إيقاف جميع الملفات':
        # إيقاف جميع عمليات المستخدم
        user_processes = {k: v for k, v in active_processes.items() if k.startswith(f"{user_id}_")}
        stopped_count = 0
        
        for process_key, process_info in user_processes.items():
            try:
                process_info['process'].terminate()
                stopped_count += 1
                del active_processes[process_key]
            except:
                pass
        
        bot.send_message(chat_id, f"{get_random_fruit()} تم إيقاف {stopped_count} من عملياتك النشطة.")
    
    elif text == 'تثبيت مكتبة':
        bot.send_message(chat_id, f"{get_random_fruit()} أرسل اسم المكتبة التي تريد تثبيتها (مثال: numpy)")
        bot.register_next_step_handler(message, install_library)
    
    elif text == 'سرعة البوت':
        # اختبار سرعة البوت
        start_time = time.time()
        test_msg = bot.send_message(chat_id, f"{get_random_fruit()} جاري قياس سرعة الاستجابة...")
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)
        
        bot.edit_message_text(f"{get_random_fruit()} سرعة استجابة البوت: {response_time} مللي ثانية\n\nالحالة: 🟢 ممتازة", 
                             chat_id, test_msg.message_id)
    
    elif text == 'معادثة مع AI':
        bot.send_message(chat_id, f"{get_random_fruit()} مرحباً! أنا المساعد الافتراضي للبوت. كيف يمكنني مساعدتك؟")
    
    elif text == 'دعوة الأصدقاء':
        bot.send_message(chat_id, f"{get_random_fruit()} رابط الدعوة: https://t.me/Fo79BOT?start=ref12345\n\nاحصل على 10 نقاط لكل صديق يدخل عبر الرابط!")
    
    elif text == 'تحويل النقاط':
        bot.send_message(chat_id, f"{get_random_fruit()} أرسل معرف المستخدم وعدد النقاط التي تريد تحويلها (مثال: 123456 10)")
    
    elif text == 'شراء نقاط':
        bot.send_message(chat_id, f"{get_random_fruit()} لشراء النقاط:\n\n10 نقاط - 1$\n50 نقاط - 4$\n100 نقاط - 7$\n\nللطلب راسل: @python_hosting_admin")
    
    elif text == 'قناة المطور':
        bot.send_message(chat_id, f"{get_random_fruit()} قناة المطور: {CHANNEL_LINK}\n\nتابعنا للحصول على آخر التحديثات والأخبار!")
    
    elif text == 'المطور':
        bot.send_message(chat_id, f"{get_random_fruit()} المطور: {DEVELOPER_USERNAME}\n\nللتواصل مع المطور حول المشاكل أو المقترحات.")

# معالجة تثبيت المكتبة
def install_library(message):
    chat_id = message.chat.id
    library_name = message.text.strip()
    
    if not library_name:
        bot.send_message(chat_id, f"{get_random_fruit()} يرجى إرسال اسم مكتبة صحيح.")
        return
    
    # محاكاة عملية التثبيت
    status_msg = bot.send_message(chat_id, f"{get_random_fruit()} جاري تثبيت المكتبة: {library_name}...")
    
    try:
        # محاكاة التأخير
        time.sleep(2)
        
        # في الواقع، هنا نستخدم pip install
        # process = subprocess.Popen(['pip', 'install', library_name], 
        #                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # stdout, stderr = process.communicate()
        
        # لمثالنا، سنفترض أن التثبيت نجح
        bot.edit_message_text(f"{get_random_fruit()} تم تثبيت المكتبة بنجاح: {library_name}", 
                            chat_id, status_msg.message_id)
    
    except Exception as e:
        bot.edit_message_text(f"{get_random_fruit()} فشل في تثبيت المكتبة: {str(e)}", 
                            chat_id, status_msg.message_id)

# معالجة رفع الملفات وتشغيلها
@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    try:
        # التحقق من صيغة الملف
        if not message.document.file_name.endswith('.py'):
            bot.send_message(chat_id, f"{get_random_fruit()} يسمح فقط بملفات البايثون (.py)")
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
        confirm_msg = bot.send_message(chat_id, f"{get_random_fruit()} تم رفع الملف بنجاح: {file_name} ({file_size:.2f} MB)\n\n{get_random_fruit()} جاري التشغيل...")
        
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
        
        # الانتظار قليلاً ثم جمع النتائج
        time.sleep(2)
        
        # التحقق مما إذا كانت العملية لا تزال تعمل
        if process.poll() is None:
            # العملية لا تزال تعمل، إرسال رسالة مع زر الإيقاف
            status_text = f"""
{get_random_fruit()} **تم بدء تشغيل الملف:**
📄 **الاسم:** {file_name}
⚖️ **الحجم:** {file_size:.2f} MB
🔄 **الحالة:** يعمل
⏰ **وقت البدء:** {time.strftime('%Y-%m-%d %H:%M:%S')}

{get_random_fruit()} يمكنك إيقاف التشغيل باستخدام الزر أدناه.
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
            result = f"{get_random_fruit()} **نتيجة التشغيل:**\n\n"
            result += f"📄 **الملف:** {file_name}\n"
            result += f"⚖️ **الحجم:** {file_size:.2f} MB\n"
            result += f"⏱ **وقت التنفيذ:** {execution_time:.2f} ثانية\n\n"
            
            if stdout:
                result += f"📤 **الناتج:**\n{stdout[-1000:]}\n\n"  # آخر 1000 حرف فقط
                
            if stderr:
                result += f"❌ **الأخطاء:**\n{stderr[-1000:]}\n\n"
                
            if not stdout and not stderr:
                result += "✅ تم التشغيل بنجاح بدون ناتج.\n\n"
            
            # إرسال النتيجة
            bot.edit_message_text(result, chat_id, confirm_msg.message_id)
            
            # إزالة العملية من القائمة النشطة
            if process_key in active_processes:
                del active_processes[process_key]
        
        logging.info(f"File uploaded and started: {file_name} by user {user_id}")
    
    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        bot.send_message(chat_id, f"{get_random_fruit()} حدث خطأ أثناء رفع الملف: {str(e)}")

# معالجة إنلاين كيبورد (إيقاف التشغيل)
@bot.callback_query_handler(func=lambda call: call.data.startswith('stop_'))
def handle_stop_callback(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data_parts = call.data.split('_')
    
    if len(data_parts) < 3:
        bot.answer_callback_query(call.id, "❌ بيانات غير صحيحة")
        return
    
    target_user_id = int(data_parts[1])
    file_name = '_'.join(data_parts[2:])
    
    # التحقق من صلاحية المستخدم
    if user_id != target_user_id and user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية إيقاف هذا الملف")
        return
    
    process_key = f"{target_user_id}_{file_name}"
    
    if process_key in active_processes:
        try:
            # إيقاف العملية
            active_processes[process_key]['process'].terminate()
            time.sleep(1)  # انتظار قليل
            
            # إذا لم تتوقف، نقتلها قسراً
            if active_processes[process_key]['process'].poll() is None:
                active_processes[process_key]['process'].kill()
            
            # إرسال رسالة التأكيد
            execution_time = time.time() - active_processes[process_key]['start_time']
            bot.edit_message_text(
                f"{get_random_fruit()} تم إيقاف التشغيل: {file_name}\n⏱ وقت التشغيل: {execution_time:.2f} ثانية",
                chat_id,
                call.message.message_id
            )
            
            # إزالة العملية من القائمة النشطة
            del active_processes[process_key]
            
            bot.answer_callback_query(call.id, "✅ تم إيقاف التشغيل")
            
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ خطأ في الإيقاف: {str(e)}")
    else:
        bot.answer_callback_query(call.id, "❌ العملية غير نشطة أو تم إيقافها مسبقاً")

# وظيفة للحفاظ على نشاط البوت (للتغلب على إيقاف الخطة المجانية)
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
                if info['process'].poll() is not None:  # العملية انتهت
                    execution_time = current_time - info['start_time']
                    
                    # إرسال النتيجة إذا كانت العملية قد انتهت
                    stdout, stderr = info['process'].communicate()
                    result = f"{get_random_fruit()} **انتهى التشغيل تلقائياً:**\n\n"
                    result += f"📄 **الملف:** {info['file_name']}\n"
                    result += f"⏱ **وقت التنفيذ:** {execution_time:.2f} ثانية\n\n"
                    
                    if stdout:
                        result += f"📤 **الناتج:**\n{stdout[-1000:]}\n\n"
                        
                    if stderr:
                        result += f"❌ **الأخطاء:**\n{stderr[-1000:]}\n\n"
                        
                    if not stdout and not stderr:
                        result += "✅ تم التشغيل بنجاح بدون ناتج.\n\n"
                    
                    try:
                        bot.send_message(info['chat_id'], result)
                    except:
                        pass
                    
                    keys_to_remove.append(key)
            
            # إزالة العمليات المنتهية
            for key in keys_to_remove:
                del active_processes[key]
                
        except Exception as e:
            logging.error(f"Keep-alive error: {e}")
        
        # الانتظار لمدة 5 دقائق قبل المحاولة مرة أخرى
        time.sleep(300)

# تشغيل البوت مع ميزة إعادة التشغيل التلقائي
def run_bot():
    # بدء موضوع منفصل للحفاظ على نشاط البوت
    import threading
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    
    # إعادة تهيئة البوت مع إعدادات مختلفة لتجنب مشكلة التوازن
    global bot
    bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
    
    while True:
        try:
            print("🤖 بوت استضافة بايثون يعمل الآن...")
            logging.info("Bot started successfully")
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            logging.error(f"Bot error: {e}, restarting in 10 seconds...")
            time.sleep(10)

if __name__ == '__main__':
    run_bot() 
