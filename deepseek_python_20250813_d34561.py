import os
import logging
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import InputPeerChannel

# تكوين البوت
TOKEN = "7966976239:AAHLSZafl8E_j1GNT0TfTuRjZRfNAXMvzDs"
API_ID = 23656977
API_HASH = "49d3f43531a92b3f5bc403766313ca1e"
DEVELOPER = "@Ili8_8ill"

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# قاعدة البيانات
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    phone = Column(String)
    session_str = Column(String)
    groups = relationship("Group", back_populates="user")

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    group_id = Column(String)
    title = Column(String)
    access_hash = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship("User", back_populates="groups")

class Stats(Base):
    __tablename__ = 'stats'
    id = Column(Integer, primary_key=True)
    total_posts = Column(Integer, default=0)
    user_posts = Column(Integer, default=0)
    total_users = Column(Integer, default=0)
    total_groups = Column(Integer, default=0)

# تهيئة قاعدة البيانات
engine = create_engine('sqlite:///bot_database.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db_session = Session()

# وظائف لواجهة المستخدم
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("═════ تسجيل | LOGIN ═════", callback_data='login')],
        [
            InlineKeyboardButton("بدء النشر", callback_data='start_posting'),
            InlineKeyboardButton("اضف سوبر", callback_data='add_groups')
        ],
        [
            InlineKeyboardButton("مساعدة", callback_data='help'),
            InlineKeyboardButton("احصائيات", callback_data='stats')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    keyboard = [[InlineKeyboardButton("رجوع", callback_data='back')]]
    return InlineKeyboardMarkup(keyboard)

def intervals_keyboard():
    keyboard = [
        [InlineKeyboardButton("2 دقائق", callback_data='interval_2')],
        [InlineKeyboardButton("5 دقائق", callback_data='interval_5')],
        [InlineKeyboardButton("10 دقائق", callback_data='interval_10')],
        [InlineKeyboardButton("20 دقيقة", callback_data='interval_20')],
        [InlineKeyboardButton("30 دقيقة", callback_data='interval_30')],
        [InlineKeyboardButton("60 دقيقة", callback_data='interval_60')],
        [InlineKeyboardButton("120 دقيقة", callback_data='interval_120')],
        [InlineKeyboardButton("رجوع", callback_data='back')]
    ]
    return InlineKeyboardMarkup(keyboard)

# وظائف البوت الأساسية
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        'مرحباً! اختر من القائمة:',
        reply_markup=main_menu_keyboard()
    )

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    if query.data == 'back':
        query.edit_message_text(
            'القائمة الرئيسية:',
            reply_markup=main_menu_keyboard()
        )
    
    elif query.data == 'login':
        context.user_data['step'] = 'login_phone'
        query.edit_message_text(
            'أرسل رقم هاتفك مع رمز الدولة، مثال: +966123456789',
            reply_markup=back_keyboard()
        )
    
    elif query.data == 'add_groups':
        session = db_session()
        user = session.query(User).filter(User.telegram_id == query.from_user.id).first()
        
        if not user or not user.session_str:
            query.edit_message_text(
                'يجب تسجيل الدخول أولاً!',
                reply_markup=back_keyboard()
            )
            return
        
        context.user_data['step'] = 'adding_groups'
        query.edit_message_text(
            'جاري جلب مجموعاتك...',
            reply_markup=back_keyboard()
        )
        
        # جلب المجموعات باستخدام Telethon
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        groups = loop.run_until_complete(get_user_groups(user.session_str))
        loop.close()
        
        if not groups:
            query.edit_message_text('لم يتم العثور على مجموعات!', reply_markup=back_keyboard())
            return
        
        # حفظ المجموعات في قاعدة البيانات
        added_count = 0
        for group_id, access_hash, title in groups:
            existing_group = session.query(Group).filter(
                Group.group_id == str(group_id),
                Group.user_id == user.id
            ).first()
            
            if not existing_group:
                new_group = Group(
                    group_id=str(group_id),
                    access_hash=str(access_hash),
                    title=title,
                    user_id=user.id
                )
                session.add(new_group)
                added_count += 1
        
        session.commit()
        
        # تحديث الإحصائيات
        stats = session.query(Stats).first()
        if not stats:
            stats = Stats()
            session.add(stats)
        stats.total_groups += added_count
        session.commit()
        
        query.edit_message_text(
            f'تمت إضافة {added_count} مجموعة جديدة!',
            reply_markup=back_keyboard()
        )
    
    elif query.data == 'start_posting':
        query.edit_message_text(
            'اختر الفترة الزمنية بين النشر:',
            reply_markup=intervals_keyboard()
        )
    
    elif query.data.startswith('interval_'):
        minutes = int(query.data.split('_')[1])
        context.user_data['posting_interval'] = minutes
        context.user_data['step'] = 'posting_message'
        query.edit_message_text(
            f'تم اختيار النشر كل {minutes} دقيقة\nأرسل الرسالة التي تريد نشرها:',
            reply_markup=back_keyboard()
        )
    
    elif query.data == 'help':
        help_text = (
            "🎯 دليل استخدام البوت:\n\n"
            "1. تسجيل الدخول: أضف رقم هاتفك للاتصال بحسابك\n"
            "2. إضافة سوبر: اختر المجموعات التي تريد النشر فيها\n"
            "3. بدء النشر: اختر الفترة الزمنية وأرسل الرسالة\n\n"
            "⚠️ تحذيرات:\n"
            "- لا تشارك رمز التحقق مع أحد\n"
            "- البوت لا يخزن أي بيانات شخصية\n\n"
            f"المطور: {DEVELOPER}"
        )
        query.edit_message_text(help_text, reply_markup=back_keyboard())
    
    elif query.data == 'stats':
        session = db_session()
        stats = session.query(Stats).first()
        if not stats:
            stats = Stats()
            session.add(stats)
            session.commit()
        
        text = (
            f"📊 إحصائيات البوت:\n\n"
            f"• إجمالي المنشورات: {stats.total_posts}\n"
            f"• منشوراتك: {stats.user_posts}\n"
            f"• عدد المستخدمين: {stats.total_users}\n"
            f"• عدد المجموعات: {stats.total_groups}"
        )
        query.edit_message_text(text, reply_markup=back_keyboard())

async def get_user_groups(session_str):
    client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
    await client.connect()
    
    groups = []
    async for dialog in client.iter_dialogs():
        if dialog.is_group or dialog.is_channel:
            if dialog.entity.access_hash:
                groups.append((
                    dialog.entity.id,
                    dialog.entity.access_hash,
                    dialog.name
                ))
    
    await client.disconnect()
    return groups

def message_handler(update: Update, context: CallbackContext):
    user_data = context.user_data
    user_id = update.message.from_user.id
    message_text = update.message.text
    
    if 'step' not in user_data:
        return
    
    if user_data['step'] == 'login_phone':
        # التحقق من صحة رقم الهاتف
        if not message_text.startswith('+'):
            update.message.reply_text(
                'رقم الهاتف يجب أن يبدأ بـ +',
                reply_markup=back_keyboard()
            )
            return
        
        phone = message_text
        user_data['phone'] = phone
        
        # إنشاء جلسة Telethon
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        client.connect()
        
        try:
            if not loop.run_until_complete(client.is_user_authorized()):
                loop.run_until_complete(client.send_code_request(phone))
                user_data['client'] = client
                user_data['step'] = 'login_code'
                update.message.reply_text(
                    'تم إرسال رمز التحقق إلى حسابك\nأرسل الرمز الآن:',
                    reply_markup=back_keyboard()
                )
            else:
                session_str = client.session.save()
                save_user_session(user_id, phone, session_str)
                update.message.reply_text(
                    'تم تسجيل الدخول بنجاح!',
                    reply_markup=main_menu_keyboard()
                )
                client.disconnect()
        except Exception as e:
            logger.error(f"Error in login: {e}")
            update.message.reply_text(
                'حدث خطأ! حاول مرة أخرى',
                reply_markup=back_keyboard()
            )
        finally:
            loop.close()
    
    elif user_data['step'] == 'login_code':
        code = message_text.strip()
        phone = user_data['phone']
        client = user_data['client']
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(client.sign_in(phone=phone, code=code))
            session_str = client.session.save()
            save_user_session(user_id, phone, session_str)
            update.message.reply_text(
                'تم تسجيل الدخول بنجاح!',
                reply_markup=main_menu_keyboard()
            )
            user_data.clear()
        except Exception as e:
            logger.error(f"Error in code verification: {e}")
            update.message.reply_text(
                'رمز خاطئ! حاول مرة أخرى',
                reply_markup=back_keyboard()
            )
        finally:
            client.disconnect()
            loop.close()
    
    elif user_data['step'] == 'posting_message':
        user_data['post_message'] = message_text
        interval = user_data['posting_interval']
        
        # بدء النشر الدوري
        if 'job' in context.user_data:
            context.user_data['job'].schedule_removal()
        
        context.user_data['job'] = context.job_queue.run_repeating(
            post_to_groups,
            interval=interval * 60,
            first=0,
            context={
                'user_id': user_id,
                'message': message_text
            }
        )
        
        update.message.reply_text(
            f'تم بدء النشر كل {interval} دقيقة!',
            reply_markup=main_menu_keyboard()
        )
        user_data.clear()

def save_user_session(user_id, phone, session_str):
    session = db_session()
    user = session.query(User).filter(User.telegram_id == user_id).first()
    
    if not user:
        user = User(telegram_id=user_id, phone=phone, session_str=session_str)
        session.add(user)
        
        # تحديث الإحصائيات
        stats = session.query(Stats).first()
        if not stats:
            stats = Stats()
            session.add(stats)
        stats.total_users += 1
    else:
        user.session_str = session_str
    
    session.commit()

def post_to_groups(context: CallbackContext):
    job = context.job
    user_id = job.context['user_id']
    message = job.context['message']
    
    session = db_session()
    user = session.query(User).filter(User.telegram_id == user_id).first()
    
    if not user or not user.session_str:
        return
    
    groups = session.query(Group).filter(Group.user_id == user.id).all()
    
    if not groups:
        return
    
    # إرسال الرسالة باستخدام Telethon
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(StringSession(user.session_str), API_ID, API_HASH)
    client.connect()
    
    success_count = 0
    for group in groups:
        try:
            entity = InputPeerChannel(
                int(group.group_id),
                int(group.access_hash)
            )
            loop.run_until_complete(client.send_message(entity, message))
            success_count += 1
        except Exception as e:
            logger.error(f"Error posting to {group.title}: {e}")
    
    client.disconnect()
    loop.close()
    
    # تحديث الإحصائيات
    if success_count > 0:
        stats = session.query(Stats).first()
        if not stats:
            stats = Stats()
            session.add(stats)
        stats.total_posts += success_count
        stats.user_posts += success_count
        session.commit()

def error_handler(update: Update, context: CallbackContext):
    logger.error(f'Update {update} caused error: {context.error}')
    if update and update.message:
        update.message.reply_text(
            'حدث خطأ غير متوقع!',
            reply_markup=main_menu_keyboard()
        )

def main():
    # تهيئة الإحصائيات
    session = db_session()
    if not session.query(Stats).first():
        session.add(Stats())
        session.commit()
    
    # بدء البوت
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
    dp.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()