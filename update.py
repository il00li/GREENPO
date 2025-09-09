import os
import telebot
import subprocess
import time
import logging
import json
import base64
import random
from flask import Flask, request
from waitress import serve
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import re

# إعدادات البوت
BOT_TOKEN = '7282947584:AAFABsn9XzpWfpcm8BfnjtkpFUdMLTeARDg'
ADMIN_ID = 6689435577
BOT_USERNAME = '@HOZ7_BOT'
CHANNEL_ID = '-1003091756917'  # معرف القناة

# إعدادات الملفات
UPLOAD_DIR = 'uploaded_files'
os.makedirs(UPLOAD_DIR, exist_ok=True)

# قائمة الرموز التعبيرية العشوائية
RANDOM_EMOJIS = ['🦜', '🦚', '🐸', '🐊', '🐢', '🦎', '🐍', '🐲', '🐉', '🦕', '🐛', '🪲', '💐', '🦠', '🌲', '🌳', '🌵', '🌴', '🌾', '🌿', '🌱', '☘️', '🍀', '🪴', '🍃']

# تخزين العمليات النشطة
active_processes = {}
saved_files = {}
user_states = {}  # لتتبع حالة المستخدم

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

# إنشاء تطبيق Flask
app = Flask(__name__)

# الحصول على رمز تعبيري عشوائي
def get_random_emoji():
    return random.choice(RANDOM_EMOJIS)

# إرسال ملف إلى القناة
def send_file_to_channel(file_path, user_id, file_name):
    try:
        if CHANNEL_ID:
            with open(file_path, 'rb') as file:
                bot.send_document(
                    CHANNEL_ID, 
                    file, 
                    caption=f"FILE_DATA:{user_id}:{file_name}:{int(time.time())}"
                )
            return True
    except Exception as e:
        logging.error(f"Failed to send file to channel: {e}")
    return False

# حفظ معلومات الملف محلياً
def save_file_info(user_id, file_name, file_path):
    try:
        with open(file_path, 'rb') as file:
            file_content = file.read()
        
        file_key = f"{user_id}_{file_name}"
        saved_files[file_key] = {
            'user_id': user_id,
            'file_name': file_name,
            'file_content': base64.b64encode(file_content).decode('utf-8'),
            'saved_time': time.time()
        }
        
        # حفظ المعلومات في ملف JSON للموثوقية
        with open('saved_files.json', 'w') as f:
            json.dump(saved_files, f)
            
        return True
    except Exception as e:
        logging.error(f"Failed to save file info: {e}")
        return False

# استعادة الملفات المحفوظة
def restore_saved_files():
    try:
        # محاولة تحميل الملفات من JSON
        if os.path.exists('saved_files.json'):
            with open('saved_files.json', 'r') as f:
                loaded_files = json.load(f)
                
            for file_key, file_info in loaded_files.items():
                try:
                    # فك تشفير المحتوى
                    file_content = base64.b64decode(file_info['file_content'])
                    file_path = os.path.join(UPLOAD_DIR, f"{file_info['user_id']}_{file_info['file_name']}")
                    
                    # حفظ الملف
                    with open(file_path, 'wb') as f:
                        f.write(file_content)
                    
                    # إضافة إلى القائمة النشطة
                    saved_files[file_key] = file_info
                    logging.info(f"Restored file: {file_info['file_name']}")
                    
                except Exception as e:
                    logging.error(f"Failed to restore file {file_key}: {e}")
        
        # محاولة استعادة الملفات من القناة
        try:
            # الحصول على آخر 100 رسالة من القناة
            messages = bot.get_chat_history(CHANNEL_ID, limit=100)
            
            for message in messages:
                if message.caption and message.caption.startswith("FILE_DATA:"):
                    parts = message.caption.split(":")
                    if len(parts) >= 4:
                        user_id = parts[1]
                        file_name = parts[2]
                        file_key = f"{user_id}_{file_name}"
                        
                        if file_key not in saved_files:
                            # تحميل الملف من الرسالة
                            file_info = bot.get_file(message.document.file_id)
                            downloaded_file = bot.download_file(file_info.file_path)
                            
                            # حفظ الملف محلياً
                            file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
                            with open(file_path, 'wb') as f:
                                f.write(downloaded_file)
                            
                            # حفظ المعلومات
                            save_file_info(user_id, file_name, file_path)
                            logging.info(f"Restored file from channel: {file_name}")
                            
        except Exception as e:
            logging.error(f"Failed to restore files from channel: {e}")
            
    except Exception as e:
        logging.error(f"Error in restore_saved_files: {e}")

# إنشاء لوحة إنلاين رئيسية
def create_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} رفع ملف', callback_data='upload_file'),
        InlineKeyboardButton(f'{get_random_emoji()} الإعدادات', callback_data='settings_menu')
    )
    return keyboard

# إنشاء لوحة إنلاين للإعدادات
def create_settings_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} صنع ملف', callback_data='create_file'),
        InlineKeyboardButton(f'{get_random_emoji()} الملفات المحفوظة', callback_data='saved_files'),
        InlineKeyboardButton(f'{get_random_emoji()} استبدال ملف', callback_data='replace_file'),
        InlineKeyboardButton(f'{get_random_emoji()} حذف ملف', callback_data='delete_file'),
        InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='main_menu')
    )
    return keyboard

# إنشاء لوحة إنلاين لتشغيل الملف
def create_run_inline_keyboard(file_name, user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} تشغيل الملف', callback_data=f'run_{user_id}_{file_name}')
    )
    return keyboard

# إنشاء لوحة إنلاين لإيقاف التشغيل
def create_stop_inline_keyboard(file_name, user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f'{get_random_emoji()} إيقاف التشغيل', callback_data=f'stop_{user_id}_{file_name}')
    )
    return keyboard

# إنشاء لوحة إنلاين للملفات المحفوظة
def create_saved_files_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    user_files = {k: v for k, v in saved_files.items() if str(v['user_id']) == str(user_id)}
    
    if not user_files:
        keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} لا توجد ملفات محفوظة', callback_data='none'))
    else:
        for i, (file_key, file_info) in enumerate(list(user_files.items())[:10]):  # عرض أول 10 ملفات فقط
            keyboard.add(InlineKeyboardButton(
                f"{get_random_emoji()} {file_info['file_name']}", 
                callback_data=f"run_{file_info['user_id']}_{file_info['file_name']}"
            ))
    
    keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='settings_menu'))
    return keyboard

# إنشاء لوحة إنلاين لاستبدال الملف
def create_replace_files_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    user_files = {k: v for k, v in saved_files.items() if str(v['user_id']) == str(user_id)}
    
    if not user_files:
        keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} لا توجد ملفات محفوظة', callback_data='none'))
    else:
        for i, (file_key, file_info) in enumerate(list(user_files.items())[:10]):  # عرض أول 10 ملفات فقط
            keyboard.add(InlineKeyboardButton(
                f"{get_random_emoji()} {file_info['file_name']}", 
                callback_data=f"replace_{file_info['user_id']}_{file_info['file_name']}"
            ))
    
    keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='settings_menu'))
    return keyboard

# إنشاء لوحة إنلاين لحذف الملف
def create_delete_files_keyboard(user_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    user_files = {k: v for k, v in saved_files.items() if str(v['user_id']) == str(user_id)}
    
    if not user_files:
        keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} لا توجد ملفات محفوظة', callback_data='none'))
    else:
        for i, (file_key, file_info) in enumerate(list(user_files.items())[:10]):  # عرض أول 10 ملفات فقط
            keyboard.add(InlineKeyboardButton(
                f"{get_random_emoji()} {file_info['file_name']}", 
                callback_data=f"delete_{file_info['user_id']}_{file_info['file_name']}"
            ))
    
    keyboard.add(InlineKeyboardButton(f'{get_random_emoji()} رجوع', callback_data='settings_menu'))
    return keyboard

# معالجة أمر /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        chat_id = message.chat.id
        user_id = message.from_user.id
        
        welcome_text = f"""
{get_random_emoji()} مرحباً بك في بوت استضافة الملفات {BOT_USERNAME}

{get_random_emoji()} المميزات المتاحة:
{get_random_emoji()} رفع ملفات بايثون وتشغيلها
{get_random_emoji()} صنع ملفات بايثون من الأكواد
{get_random_emoji()} حفظ الملفات الناجحة وإعادة تشغيلها تلقائياً

{get_random_emoji()} اختر أحد الخيارات:
"""
        bot.send_message(chat_id, welcome_text, reply_markup=create_main_keyboard())
        logging.info(f"Welcome message sent to user {user_id}")
        
    except Exception as e:
        logging.error(f"Error in /start command: {e}")

# معالجة رفع الملفات
@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    try:
        # التحقق من صيغة الملف
        if not message.document.file_name.endswith('.py'):
            bot.send_message(chat_id, f"{get_random_emoji()} يسمح فقط بملفات البايثون py")
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
        send_file_to_channel(file_path, user_id, file_name)
        
        # حفظ المعلومات محلياً
        save_file_info(user_id, file_name, file_path)
        
        # حساب حجم الملف
        file_size = len(downloaded_file) / (1024 * 1024)  # MB
        
        # إرسال رسالة التأكيد مع زر التشغيل
        bot.send_message(
            chat_id, 
            f"{get_random_emoji()} تم رفع الملف بنجاح: {file_name} ({file_size:.2f} MB)\n\n{get_random_emoji()} اضغط على زر التشغيل لتشغيل الملف",
            reply_markup=create_run_inline_keyboard(file_name, user_id)
        )
        
        logging.info(f"File uploaded: {file_name} by user {user_id}")
    
    except Exception as e:
        logging.error(f"Error uploading file: {str(e)}")
        bot.send_message(chat_id, f"{get_random_emoji()} حدث خطأ أثناء رفع الملف: {str(e)}")

# معالجة الرسائل النصية (لصنع الملفات)
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text
    
    # إذا كان المستخدم في وضع استبدال الملف
    if user_id in user_states and user_states[user_id].get('action') == 'waiting_replace_file':
        try:
            file_key = user_states[user_id]['file_key']
            file_info = saved_files[file_key]
            
            # إنشاء اسم للملف
            file_name = file_info['file_name']
            file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
            
            # حفظ الكود في ملف
            with open(file_path, 'w', encoding='utf-8') as new_file:
                new_file.write(text)
            
            # تحديث المعلومات المحفوظة
            save_file_info(user_id, file_name, file_path)
            
            # مسح حالة المستخدم
            del user_states[user_id]
            
            # إرسال رسالة التأكيد
            bot.send_message(
                chat_id,
                f"{get_random_emoji()} تم استبدال الملف بنجاح: {file_name}\n\n{get_random_emoji()} اضغط على زر التشغيل لتشغيل الملف",
                reply_markup=create_run_inline_keyboard(file_name, user_id)
            )
            
            logging.info(f"File replaced: {file_name} by user {user_id}")
            
        except Exception as e:
            logging.error(f"Error replacing file: {str(e)}")
            bot.send_message(chat_id, f"{get_random_emoji()} حدث خطأ أثناء استبدال الملف: {str(e)}")
    
    # إذا كان النص يحتوي على كود بايثون
    elif any(keyword in text for keyword in ['import', 'def ', 'class ', 'print(', '=']) or len(text) > 50:
        try:
            # إنشاء اسم للملف
            file_name = f"code_{int(time.time())}.py"
            file_path = os.path.join(UPLOAD_DIR, f"{user_id}_{file_name}")
            
            # حفظ الكود في ملف
            with open(file_path, 'w', encoding='utf-8') as new_file:
                new_file.write(text)
            
            # إرسال الملف إلى القناة
            send_file_to_channel(file_path, user_id, file_name)
            
            # حفظ المعلومات محلياً
            save_file_info(user_id, file_name, file_path)
            
            # إرسال الملف للمستخدم مع زر التشغيل
            with open(file_path, 'rb') as file:
                bot.send_document(
                    chat_id,
                    file,
                    caption=f"{get_random_emoji()} تم إنشاء الملف بنجاح: {file_name}\n\n{get_random_emoji()} اضغط على زر التشغيل لتشغيل الملف",
                    reply_markup=create_run_inline_keyboard(file_name, user_id)
                )
            
            logging.info(f"File created from text: {file_name} by user {user_id}")
            
        except Exception as e:
            logging.error(f"Error creating file from text: {str(e)}")
            bot.send_message(chat_id, f"{get_random_emoji()} حدث خطأ أثناء إنشاء الملف: {str(e)}")
    else:
        # إذا لم يكن النص يحتوي على كود بايثون، عرض القائمة الرئيسية
        bot.send_message(chat_id, f"{get_random_emoji()} مرحباً! اختر خياراً من القائمة:", reply_markup=create_main_keyboard())

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
                f"{get_random_emoji()} أرسل لي ملف بايثون (py) لرفعه",
                chat_id,
                message_id,
                reply_markup=create_main_keyboard()
            )
        
        elif data == 'settings_menu':
            bot.edit_message_text(
                f"{get_random_emoji()} الإعدادات:\n\n{get_random_emoji()} اختر أحد الخيارات:",
                chat_id,
                message_id,
                reply_markup=create_settings_keyboard()
            )
        
        elif data == 'create_file':
            bot.edit_message_text(
                f"{get_random_emoji()} أرسل لي كود بايثون وسأقوم بتحويله إلى ملف وتشغيله",
                chat_id,
                message_id,
                reply_markup=create_settings_keyboard()
            )
        
        elif data == 'saved_files':
            bot.edit_message_text(
                f"{get_random_emoji()} الملفات المحفوظة:\n\n{get_random_emoji()} اختر ملفاً لتشغيله:",
                chat_id,
                message_id,
                reply_markup=create_saved_files_keyboard(user_id)
            )
        
        elif data == 'replace_file':
            bot.edit_message_text(
                f"{get_random_emoji()} استبدال ملف:\n\n{get_random_emoji()} اختر الملف الذي تريد استبداله:",
                chat_id,
                message_id,
                reply_markup=create_replace_files_keyboard(user_id)
            )
        
        elif data == 'delete_file':
            bot.edit_message_text(
                f"{get_random_emoji()} حذف ملف:\n\n{get_random_emoji()} اختر الملف الذي تريد حذفه:",
                chat_id,
                message_id,
                reply_markup=create_delete_files_keyboard(user_id)
            )
        
        elif data == 'main_menu':
            bot.edit_message_text(
                f"{get_random_emoji()} مرحباً! اختر خياراً من القائمة:",
                chat_id,
                message_id,
                reply_markup=create_main_keyboard()
            )
        
        elif data.startswith('run_'):
            data_parts = data.split('_')
            
            if len(data_parts) < 3:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} بيانات غير صحيحة")
                return
            
            target_user_id = int(data_parts[1])
            file_name = '_'.join(data_parts[2:])
            
            # التحقق من صلاحية المستخدم
            if user_id != target_user_id and user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية تشغيل هذا الملف")
                return
            
            file_path = os.path.join(UPLOAD_DIR, f"{target_user_id}_{file_name}")
            
            if not os.path.exists(file_path):
                # محاولة استعادة الملف من القائمة المحفوظة
                file_key = f"{target_user_id}_{file_name}"
                if file_key in saved_files:
                    try:
                        # فك تشفير المحتوى
                        file_content = base64.b64decode(saved_files[file_key]['file_content'])
                        
                        # حفظ الملف
                        with open(file_path, 'wb') as f:
                            f.write(file_content)
                        
                        bot.answer_callback_query(call.id, f"{get_random_emoji()} تم استعادة الملف من النسخة الاحتياطية")
                    except Exception as e:
                        bot.answer_callback_query(call.id, f"{get_random_emoji()} فشل في استعادة الملف")
                        return
                else:
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} الملف غير موجود")
                    return
            
            # تشغيل الملف في عملية منفصلة
            process = subprocess.Popen(
                ['python', file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # تخزين معلومات العملية
            process_key = f"{target_user_id}_{file_name}"
            active_processes[process_key] = {
                'process': process,
                'start_time': time.time(),
                'chat_id': chat_id,
                'file_name': file_name,
                'user_id': target_user_id
            }
            
            # الانتظار ثم جمع النتائج
            time.sleep(2)
            
            # التحقق مما إذا كانت العملية لا تزال تعمل
            if process.poll() is None:
                # العملية لا تزال تعمل، إرسال رسالة مع زر الإيقاف
                status_text = f"""
{get_random_emoji()} تم بدء تشغيل الملف: {file_name}
{get_random_emoji()} الحالة: يعمل
{get_random_emoji()} وقت البدء: {time.strftime('%Y-%m-%d %H:%M:%S')}

{get_random_emoji()} يمكنك إيقاف التشغيل باستخدام الزر أدناه.
"""
                bot.edit_message_text(
                    status_text, 
                    chat_id, 
                    message_id,
                    reply_markup=create_stop_inline_keyboard(file_name, target_user_id)
                )
            else:
                # العملية انتهت، جمع النتائج
                stdout, stderr = process.communicate()
                execution_time = time.time() - active_processes[process_key]['start_time']
                
                # إعداد النتيجة
                result = f"""
{get_random_emoji()} تم تشغيل الملف: {file_name}
{get_random_emoji()} وقت التنفيذ: {execution_time:.2f} ثانية
"""
                
                if stdout:
                    result += f"\n{get_random_emoji()} الناتج:\n{stdout[-1000:]}\n"
                    
                if stderr:
                    result += f"\n{get_random_emoji()} الأخطاء:\n{stderr[-1000:]}\n"
                    
                if not stdout and not stderr:
                    result += f"\n{get_random_emoji()} تم التشغيل بنجاح بدون ناتج.\n"
                
                # إرسال النتيجة
                bot.edit_message_text(
                    result, 
                    chat_id, 
                    message_id
                )
                
                # إزالة العملية من القائمة النشطة
                if process_key in active_processes:
                    del active_processes[process_key]
            
            bot.answer_callback_query(call.id, f"{get_random_emoji()} تم تشغيل الملف")
        
        elif data.startswith('replace_'):
            data_parts = data.split('_')
            
            if len(data_parts) < 3:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} بيانات غير صحيحة")
                return
            
            target_user_id = int(data_parts[1])
            file_name = '_'.join(data_parts[2:])
            
            # التحقق من صلاحية المستخدم
            if user_id != target_user_id and user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية استبدال هذا الملف")
                return
            
            # حفظ حالة المستخدم
            file_key = f"{target_user_id}_{file_name}"
            user_states[user_id] = {
                'action': 'waiting_replace_file',
                'file_key': file_key
            }
            
            bot.edit_message_text(
                f"{get_random_emoji()} أرسل الكود الجديد لاستبدال الملف: {file_name}",
                chat_id,
                message_id
            )
            
            bot.answer_callback_query(call.id, f"{get_random_emoji()} جاهز لاستقبال الكود الجديد")
        
        elif data.startswith('delete_'):
            data_parts = data.split('_')
            
            if len(data_parts) < 3:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} بيانات غير صحيحة")
                return
            
            target_user_id = int(data_parts[1])
            file_name = '_'.join(data_parts[2:])
            
            # التحقق من صلاحية المستخدم
            if user_id != target_user_id and user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية حذف هذا الملف")
                return
            
            # حذف الملف
            file_key = f"{target_user_id}_{file_name}"
            file_path = os.path.join(UPLOAD_DIR, f"{target_user_id}_{file_name}")
            
            if file_key in saved_files:
                del saved_files[file_key]
                
                # تحديث ملف JSON
                with open('saved_files.json', 'w') as f:
                    json.dump(saved_files, f)
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            bot.edit_message_text(
                f"{get_random_emoji()} تم حذف الملف: {file_name}",
                chat_id,
                message_id,
                reply_markup=create_delete_files_keyboard(user_id)
            )
            
            bot.answer_callback_query(call.id, f"{get_random_emoji()} تم حذف الملف")
        
        elif data.startswith('stop_'):
            data_parts = data.split('_')
            
            if len(data_parts) < 3:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} بيانات غير صحيحة")
                return
            
            target_user_id = int(data_parts[1])
            file_name = '_'.join(data_parts[2:])
            
            # التحقق من صلاحية المستخدم
            if user_id != target_user_id and user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} ليس لديك صلاحية إيقاف هذا الملف")
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
                        f"{get_random_emoji()} تم إيقاف التشغيل: {file_name}\n{get_random_emoji()} وقت التشغيل: {execution_time:.2f} ثانية",
                        chat_id,
                        message_id
                    )
                    
                    # إزالة العملية من القائمة النشطة
                    del active_processes[process_key]
                    
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} تم إيقاف التشغيل")
                    
                except Exception as e:
                    bot.answer_callback_query(call.id, f"{get_random_emoji()} خطأ في الإيقاف: {str(e)}")
            else:
                bot.answer_callback_query(call.id, f"{get_random_emoji()} الملف غير نشط أو تم إيقافه مسبقاً")
        
        # الرد على callback query لإزالة حالة التحميل
        bot.answer_callback_query(call.id)
    
    except Exception as e:
        logging.error(f"Error in callback query: {e}")
        bot.answer_callback_query(call.id, f"{get_random_emoji()} حدث خطأ أثناء معالجة طلبك")

@app.route('/')
def health_check():
    return "البوت يعمل بشكل صحيح ✅", 200

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

# تشغيل البوت مع إعداد Webhook
def run_bot():
    try:
        # استعادة الملفات المحفوظة عند البدء
        restore_saved_files()
        
        # إعداد Webhook
        bot.remove_webhook()
        time.sleep(1)
        webhook_url = f"https://your-render-app.onrender.com/webhook"
        bot.set_webhook(url=webhook_url)
        logging.info(f"Webhook set to: {webhook_url}")
        
        # التحقق من حالة البوت
        bot_info = bot.get_me()
        logging.info(f"Bot is ready: {bot_info.first_name} ({bot_info.username})")
        
        # تشغيل خادم Flask
        serve(app, host='0.0.0.0', port=port)
        
    except Exception as e:
        logging.error(f"Failed to set webhook: {e}")
        print("❌ فشل إعداد Webhook، جاري استخدام Polling كحل بديل")
        
        # استخدام Polling كحل بديل
        bot.remove_webhook()
        time.sleep(1)
        bot.polling(none_stop=True)

if __name__ == '__main__':
    run_bot()