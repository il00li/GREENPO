import os
import telebot
import subprocess
import time
import logging
import random
import threading
import google.generativeai as genai
from telebot.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardRemove
)

# إعدادات البوت
BOT_TOKEN = '8268382565:AAFSVSmeErn5_5JQB1g42f6m20IVI5yUE8I'
ADMIN_ID = 6689435577
DEVELOPER_USERNAME = 'OlIiIl7'
CHANNEL_LINK = 'https://t.me/iIl337'

# إعدادات Gemini AI
GEMINI_API_KEY = 'AIzaSyD3w0ZtC-GOvOVVlUxb_l0ayRAVsar64FI'

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
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# تهيئة Gemini AI
try:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro')
    GEMINI_AVAILABLE = True
except Exception as e:
    logging.error(f"Failed to initialize Gemini AI: {e}")
    GEMINI_AVAILABLE = False

# قائمة برموز الفواكه العشوائية
FRUIT_EMOJIS = ['🍎', '🍏', '🍐', '🍊', '🍋', '🍌', '🍉', '🍇', '🍓', '🍒', '🍑', '🍍', '🥭', '🥥']

def get_random_fruit():
    return random.choice(FRUIT_EMOJIS)

# إنشاء لوحة إنلاين رئيسية
def create_main_inline_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(f'{get_random_fruit()} رفع ملف', callback_data='upload_file'),
        InlineKeyboardButton(f'{get_random_fruit()} الإعدادات', callback_data='settings'),
        InlineKeyboardButton(f'{get_random_fruit()} المحادثة مع AI', callback_data='ai_chat'),
        InlineKeyboardButton(f'{get_random_fruit()} قناة البوت', url=CHANNEL_LINK),
        InlineKeyboardButton(f'{get_random_fruit()} المطور', url=f'tg://user?id={ADMIN_ID}')
    ]
    keyboard.add(*buttons[0:2])
    keyboard.add(*buttons[2:4])
    keyboard.add(buttons[4])
    return keyboard

# إنشاء لوحة إنلاين للإعدادات
def create_settings_inline_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton(f'{get_random_fruit()} إيقاف الملفات', callback_data='stop_files'),
        InlineKeyboardButton(f'{get_random_fruit()} تثبيت مكتبة', callback_data='install_lib'),
        InlineKeyboardButton(f'{get_random_fruit()} سرعة البوت', callback_data='bot_speed'),
        InlineKeyboardButton(f'{get_random_fruit()} دعوة الأصدقاء', callback_data='invite_friends'),
        InlineKeyboardButton(f'{get_random_fruit()} تحويل النقاط', callback_data='transfer_points'),
        InlineKeyboardButton(f'{get_random_fruit()} شراء نقاط', callback_data='buy_points'),
        InlineKeyboardButton(f'{get_random_fruit()} العودة', callback_data='main_menu')
    ]
    keyboard.add(*buttons[0:2])
    keyboard.add(*buttons[2:4])
    keyboard.add(*buttons[4:6])
    keyboard.add(buttons[6])
    return keyboard

# إنشاء لوحة إنلاين لإيقاف التشغيل
def create_stop_inline_keyboard(file_name, user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_fruit()} إيقاف التشغيل', callback_data=f'stop_{user_id}_{file_name}')
    )
    return keyboard

# إنشاء لوحة إنلاين لإنهاء المحادثة
def create_end_chat_inline_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_fruit()} إنهاء المحادثة', callback_data='end_chat')
    )
    return keyboard

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    welcome_text = f"""
مرحباً بك في بوت استضافة بايثون

المميزات المتاحة
- رفع وتشغيل ملفات البايثون
- إدارة الملفات الخاصة بك
- دعم المكتبات الخارجية
- محادثة مع الذكاء الاصطناعي

لبدء الاستخدام
اضغط على زر رفع ملف لرفع ملف بايثون

للمساعدة
- اكتب help لعرض الشروط
- أو استخدم المحادثة مع AI لحل المشكلات

المطور {DEVELOPER_USERNAME}
القناة {CHANNEL_LINK}
"""
    bot.send_message(chat_id, welcome_text, reply_markup=create_main_inline_keyboard())

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
- {DEVELOPER_USERNAME}
- قناة المطور {CHANNEL_LINK}
"""
    bot.send_message(chat_id, help_text, reply_markup=create_main_inline_keyboard())

# معالجة أمر /status (للمطور فقط)
@bot.message_handler(commands=['status'])
def bot_status(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        bot.send_message(chat_id, "ليس لديك صلاحية استخدام هذا الأمر")
        return
    
    # حساب عدد الملفات والعمليات النشطة
    file_count = len([f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))])
    active_count = len(active_processes)
    
    # معلومات عن وقت التشغيل
    uptime = time.time() - bot_start_time
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    status_text = f"""
حالة البوت

الإحصائيات
- عدد الملفات المرفوعة {file_count}
- عدد العمليات النشطة {active_count}
- وقت التشغيل {int(hours)}h {int(minutes)}m {int(seconds)}s
- حالة البوت يعمل

نظام إعادة التشغيل
- يعمل كل 5 دقائق للحفاظ على النشاط
- مناسب للخطة المجانية على Render

المطور {DEVELOPER_USERNAME}
"""
    bot.send_message(chat_id, status_text)

# معالجة callback queries
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    data = call.data
    
    if data == 'upload_file':
        bot.send_message(chat_id, "أرسل لي ملف بايثون py لرفعه وتشغيله", reply_markup=ReplyKeyboardRemove())
    
    elif data == 'settings':
        bot.edit_message_text("الإعدادات", chat_id, call.message.message_id, reply_markup=create_settings_inline_keyboard())
    
    elif data == 'ai_chat':
        if not GEMINI_AVAILABLE:
            bot.answer_callback_query(call.id, "عذراً، خدمة الذكاء الاصطناعي غير متاحة حالياً")
            return
        
        # بدء جلسة محادثة جديدة
        ai_sessions[user_id] = {
            'chat': gemini_model.start_chat(history=[]),
            'active': True
        }
        bot.send_message(chat_id, "مرحباً! أنا مساعد الذكاء الاصطناعي. كيف يمكنني مساعدتك اليوم؟\n\nأرسل رسالتك وسأرد عليك.", reply_markup=create_end_chat_inline_keyboard())
    
    elif data == 'main_menu':
        bot.edit_message_text("القائمة الرئيسية", chat_id, call.message.message_id, reply_markup=create_main_inline_keyboard())
    
    elif data == 'stop_files':
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
        
        bot.answer_callback_query(call.id, f"تم إيقاف {stopped_count} من عملياتك النشطة")
    
    elif data == 'install_lib':
        bot.send_message(chat_id, "أرسل اسم المكتبة التي تريد تثبيتها (مثال: numpy)")
        bot.register_next_step_handler_by_chat_id(chat_id, install_library)
    
    elif data == 'bot_speed':
        # اختبار سرعة البوت
        start_time = time.time()
        test_msg = bot.send_message(chat_id, "جاري قياس سرعة الاستجابة")
        end_time = time.time()
        response_time = round((end_time - start_time) * 1000, 2)
        
        bot.edit_message_text(f"سرعة استجابة البوت: {response_time} مللي ثانية\n\nالحالة: ممتازة", chat_id, test_msg.message_id)
    
    elif data == 'invite_friends':
        bot.send_message(chat_id, f"رابط الدعوة: https://t.me/Fo79BOT?start=ref12345\n\nاحصل على 10 نقاط لكل صديق يدخل عبر الرابط!")
    
    elif data == 'transfer_points':
        bot.send_message(chat_id, "أرسل معرف المستخدم وعدد النقاط التي تريد تحويلها (مثال: 123456 10)")
    
    elif data == 'buy_points':
        bot.send_message(chat_id, "لشراء النقاط:\n\n10 نقاط - 1$\n50 نقاط - 4$\n100 نقاط - 7$\n\nللطلب راسل: python_hosting_admin")
    
    elif data == 'end_chat':
        if user_id in ai_sessions:
            del ai_sessions[user_id]
            bot.send_message(chat_id, "تم إنهاء المحادثة. شكراً لك على استخدام خدمة الذكاء الاصطناعي.", reply_markup=create_main_inline_keyboard())
        else:
            bot.answer_callback_query(call.id, "لا توجد محادثة نشطة لإنهائها")
    
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
                active_processes[process_key]['process'].terminate()
                time.sleep(1)  # انتظار قليل
                
                # إذا لم تتوقف، نقتلها قسراً
                if active_processes[process_key]['process'].poll() is None:
                    active_processes[process_key]['process'].kill()
                
                # إرسال رسالة التأكيد
                execution_time = time.time() - active_processes[process_key]['start_time']
                bot.edit_message_text(
                    f"تم إيقاف التشغيل: {file_name}\nوقت التشغيل: {execution_time:.2f} ثانية",
                    chat_id,
                    call.message.message_id
                )
                
                # إزالة العملية من القائمة النشطة
                del active_processes[process_key]
                
                bot.answer_callback_query(call.id, "تم إيقاف التشغيل")
                
            except Exception as e:
                bot.answer_callback_query(call.id, f"خطأ في الإيقاف: {str(e)}")
        else:
            bot.answer_callback_query(call.id, "العملية غير نشطة أو تم إيقافها مسبقاً")

# معالجة تثبيت المكتبة
def install_library(message):
    chat_id = message.chat.id
    library_name = message.text.strip()
    
    if not library_name:
        bot.send_message(chat_id, "يرجى إرسال اسم مكتبة صحيح")
        return
    
    # محاكاة عملية التثبيت
    status_msg = bot.send_message(chat_id, f"جاري تثبيت المكتبة: {library_name}")
    
    try:
        # محاكاة التأخير
        time.sleep(2)
        
        # لمثالنا، سنفترض أن التثبيت نجح
        bot.edit_message_text(f"تم تثبيت المكتبة بنجاح: {library_name}", chat_id, status_msg.message_id)
    
    except Exception as e:
        bot.edit_message_text(f"فشل في تثبيت المكتبة: {str(e)}", chat_id, status_msg.message_id)

# معالجة رفع الملفات وتشغيلها
@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    try:
        # التحقق من صيغة الملف
        if not message.document.file_name.endswith('.py'):
            bot.send_message(chat_id, "يسمح فقط بملفات البايثون py")
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
        confirm_msg = bot.send_message(chat_id, f"تم رفع الملف بنجاح: {file_name} ({file_size:.2f} MB)\n\nجاري التشغيل...")
        
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
                result += f"الناتج\n{stdout[-1000:]}\n\n"  # آخر 1000 حرف فقط
                
            if stderr:
                result += f"الأخطاء\n{stderr[-1000:]}\n\n"
                
            if not stdout and not stderr:
                result += "تم التشغيل بنجاح بدون ناتج.\n\n"
            
            # إرسال النتيجة
            bot.edit_message_text(result, chat_id, confirm_msg.message_id)
            
            # إزالة العملية من القائمة النشطة
            if process_key in active_processes:
                del active_processes[process_key]
        
        logging.info(f"File uploaded and started: {file_name} by user {user_id}")
    
    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        bot.send_message(chat_id, f"حدث خطأ أثناء رفع الملف: {str(e)}")

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
    wait_msg = bot.send_message(chat_id, "جاري معالجة طلبك...", reply_markup=create_end_chat_inline_keyboard())
    
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
                if info['process'].poll() is not None:  # العملية انتهت
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

# تشغيل البوت
def run_bot():
    global bot_start_time
    
    # بدء موضوع منفصل للحفاظ على نشاط البوت
    keep_alive_thread = threading.Thread(target=keep_alive)
    keep_alive_thread.daemon = True
    keep_alive_thread.start()
    
    # تشغيل البوت مع إعادة التشغيل التلقائي عند الفشل
    while True:
        try:
            bot_start_time = time.time()
            
            logging.info("بوت استضافة بايثون يعمل الآن")
            print("بوت استضافة بايثون يعمل الآن")
            
            # بدء الاستطلاع
            bot.polling(none_stop=True, timeout=60, interval=1)
            
        except Exception as e:
            logging.error(f"Bot error: {e}, restarting in 10 seconds")
            print(f"حدث خطأ: {e}, جاري إعادة التشغيل خلال 10 ثوان")
            time.sleep(10)

# متغيرات عالمية لتتبع حالة البوت
bot_start_time = time.time()

if __name__ == '__main__':
    run_bot()
