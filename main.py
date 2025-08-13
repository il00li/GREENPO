import os
import logging
import asyncio
import re
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text, event
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import Engine
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import InputPeerChannel, Channel, User as TelethonUser

# ===== إعدادات البيئة =====
TOKEN = os.getenv('TOKEN', '7966976239:AAHLSZafl8E_j1GNT0TfTuRjZRfNAXMvzDs')
API_ID = int(os.getenv('API_ID', '23656977'))
API_HASH = os.getenv('API_HASH', '49d3f43531a92b3f5bc403766313ca1e')
DEVELOPER = os.getenv('DEVELOPER', '@Ili8_8ill')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://greenpo.onrender.com')
PORT = int(os.getenv('PORT', '5000'))
REQUIRED_CHANNELS = list(map(int, os.getenv('REQUIRED_CHANNELS', '-1001234567890,-1000987654321').split(',')))
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'SECRET_TOKEN')

# ===== إعدادات التسجيل =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== قاعدة البيانات =====
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    phone = Column(String(20))
    session_str = Column(Text)
    is_verified = Column(Boolean, default=False)
    invited_users = Column(Integer, default=0)
    groups = relationship("Group", back_populates="user")

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    group_id = Column(String(50), index=True)
    title = Column(String(255))
    access_hash = Column(String(100))
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship("User", back_populates="groups")

class Stats(Base):
    __tablename__ = 'stats'
    id = Column(Integer, primary_key=True)
    total_posts = Column(Integer, default=0)
    user_posts = Column(Integer, default=0)
    total_users = Column(Integer, default=0)
    total_groups = Column(Integer, default=0)

# تحسين أداء قاعدة البيانات
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

engine = create_engine('sqlite:///bot_database.db?check_same_thread=False', pool_pre_ping=True)
Base.metadata.create_all(engine)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# ===== وظائف لوحة المفاتيح =====
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("═════ تسجيل | LOGIN ═════", callback_data='login')],
        [
            InlineKeyboardButton("بدء النشر", callback_data='start_posting'),
            InlineKeyboardButton("اضف سوبر", callback_data='add_groups')
        ],
        [
            InlineKeyboardButton("مساعدة", callback_data='help'),
            InlineKeyboardButton("احصائيات", callback_data='stats')
        ]
    ])

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='back')]])

def intervals_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("2 دقائق", callback_data='interval_2')],
        [InlineKeyboardButton("5 دقائق", callback_data='interval_5')],
        [InlineKeyboardButton("10 دقائق", callback_data='interval_10')],
        [InlineKeyboardButton("20 دقيقة", callback_data='interval_20')],
        [InlineKeyboardButton("30 دقيقة", callback_data='interval_30')],
        [InlineKeyboardButton("60 دقيقة", callback_data='interval_60')],
        [InlineKeyboardButton("120 دقيقة", callback_data='interval_120')],
        [InlineKeyboardButton("رجوع", callback_data='back')]
    ])

def verification_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ التحقق من الاشتراك", callback_data='check_subscription')],
        [InlineKeyboardButton("📣 دعوة الأصدقاء", callback_data='invite_friends')],
        [InlineKeyboardButton("👤 التواصل مع المدير", url=f"https://t.me/{DEVELOPER.replace('@', '')}")]
    ])

def invite_keyboard(user_id):
    invite_link = f"https://t.me/share/url?url=/start%20{user_id}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 مشاركة رابط الدعوة", url=invite_link)],
        [InlineKeyboardButton("🔍 التحقق من الدعوات", callback_data='check_invites')],
        [InlineKeyboardButton("👤 التواصل مع المدير", url=f"https://t.me/{DEVELOPER.replace('@', '')}")]
    ])

# ===== وظائف مساعدة =====
def get_db_session():
    return Session()

async def get_user_groups(session_str):
    try:
        async with TelegramClient(StringSession(session_str), API_ID, API_HASH) as client:
            groups = []
            async for dialog in client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    if hasattr(dialog.entity, 'access_hash') and dialog.entity.access_hash:
                        groups.append((
                            dialog.entity.id,
                            dialog.entity.access_hash,
                            dialog.name
                        ))
            return groups
    except Exception as e:
        logger.error(f"Telethon groups error: {e}")
        return []

async def is_user_subscribed(user_id, session_str):
    try:
        async with TelegramClient(StringSession(session_str), API_ID, API_HASH) as client:
            for channel_id in REQUIRED_CHANNELS:
                try:
                    entity = await client.get_entity(Channel(channel_id))
                    participants = await client.get_participants(entity, limit=100)
                    if not any(p.id == user_id for p in participants):
                        return False
                except Exception as e:
                    logger.error(f"Channel check error: {e}")
                    return False
            return True
    except Exception as e:
        logger.error(f"Telethon subscription error: {e}")
        return False

def save_user_session(user_id, phone, session_str):
    session = get_db_session()
    try:
        user = session.query(User).filter(User.telegram_id == user_id).first()
        stats = session.query(Stats).first() or Stats()
        
        if not user:
            user = User(telegram_id=user_id, phone=phone, session_str=session_str)
            session.add(user)
            stats.total_users += 1
        else:
            user.session_str = session_str
            user.phone = phone
        
        if not stats.id:
            session.add(stats)
        
        session.commit()
        return user
    except Exception as e:
        logger.error(f"Database save error: {e}")
        session.rollback()
        return None
    finally:
        Session.remove()

# ===== معالجات الأحداث =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        session = get_db_session()
        
        # تتبع الدعوات
        if context.args and context.args[0].isdigit():
            inviter_id = int(context.args[0])
            if inviter_id != user_id:
                inviter = session.query(User).filter(User.telegram_id == inviter_id).first()
                if inviter:
                    inviter.invited_users += 1
                    session.commit()
                    await update.message.reply_text("✅ شكراً لدعوتك صديق! تمت إضافة نقطة دعوة لحسابك.")
        
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        if user and user.is_verified:
            await update.message.reply_text('مرحباً! اختر من القائمة:', reply_markup=main_menu_keyboard())
        else:
            channels_list = "\n".join([f"🔹 https://t.me/c/{abs(channel_id)}" for channel_id in REQUIRED_CHANNELS])
            await update.message.reply_text(
                f"👋 أهلاً بك في بوت النشر التلقائي!\n\n"
                f"📌 لاستخدام البوت يجب عليك:\n"
                f"1. الاشتراك في قنواتنا:\n{channels_list}\n"
                f"2. دعوة 5 أصدقاء على الأقل\n\n"
                f"بعد الانتهاء اضغط على زر التحقق",
                reply_markup=verification_keyboard()
            )
    except Exception as e:
        logger.error(f"Start command error: {e}")
        await update.message.reply_text("حدث خطأ غير متوقع، يرجى المحاولة لاحقاً")
    finally:
        Session.remove()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        user_id = query.from_user.id
        session = get_db_session()
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        # التحكم في الأزرار
        if query.data == 'back':
            await query.edit_message_text('القائمة الرئيسية:', reply_markup=main_menu_keyboard())
        
        elif query.data == 'login':
            if user and user.is_verified:
                context.user_data['step'] = 'login_phone'
                await query.edit_message_text('أرسل رقم هاتفك مع رمز الدولة (مثال: +966123456789):', reply_markup=back_keyboard())
            else:
                await query.edit_message_text("يجب إكمال متطلبات الاشتراك أولاً!", reply_markup=verification_keyboard())
        
        elif query.data == 'check_subscription':
            if not user or not user.session_str:
                await query.edit_message_text("يجب تسجيل الدخول أولاً!", reply_markup=back_keyboard())
                return
            
            await query.edit_message_text("🔍 جاري التحقق من الاشتراك...")
            subscribed = await is_user_subscribed(user_id, user.session_str)
            
            if subscribed:
                if user.invited_users >= 5:
                    user.is_verified = True
                    session.commit()
                    await query.edit_message_text("✅ تم التحقق بنجاح! يمكنك الآن استخدام البوت", reply_markup=main_menu_keyboard())
                else:
                    await query.edit_message_text(
                        f"❌ لم تكمل الشروط!\nالدعوات المطلوبة: 5\nدعواتك الحالية: {user.invited_users}",
                        reply_markup=invite_keyboard(user_id)
                    )
            else:
                await query.edit_message_text("❌ لم تشترك في القنوات المطلوبة!", reply_markup=verification_keyboard())
        
        elif query.data == 'invite_friends':
            await query.edit_message_text(
                f"📣 دعوة الأصدقاء:\nالدعوات المطلوبة: 5\nدعواتك الحالية: {user.invited_users if user else 0}",
                reply_markup=invite_keyboard(user_id)
            )
        
        elif query.data == 'add_groups':
            if not user or not user.is_verified:
                await query.edit_message_text("يجب إكمال متطلبات الاشتراك أولاً!", reply_markup=verification_keyboard())
                return
                
            if not user.session_str:
                await query.edit_message_text('يجب تسجيل الدخول أولاً!', reply_markup=back_keyboard())
                return
            
            await query.edit_message_text('⏳ جاري جلب مجموعاتك...')
            groups = await get_user_groups(user.session_str)
            
            if not groups:
                await query.edit_message_text('❌ لم يتم العثور على مجموعات!', reply_markup=back_keyboard())
                return
            
            # حفظ المجموعات
            added_count = 0
            for group_id, access_hash, title in groups:
                existing = session.query(Group).filter(Group.group_id == str(group_id), Group.user_id == user.id).first()
                if not existing:
                    session.add(Group(
                        group_id=str(group_id),
                        access_hash=str(access_hash),
                        title=title,
                        user_id=user.id
                    ))
                    added_count += 1
            
            stats = session.query(Stats).first() or Stats()
            stats.total_groups += added_count
            if not stats.id:
                session.add(stats)
            
            session.commit()
            await query.edit_message_text(f'✅ تمت إضافة {added_count} مجموعة جديدة!', reply_markup=back_keyboard())
        
        elif query.data == 'start_posting':
            if not user or not user.is_verified:
                await query.edit_message_text("يجب إكمال متطلبات الاشتراك أولاً!", reply_markup=verification_keyboard())
                return
                
            await query.edit_message_text('⏱ اختر الفترة الزمنية بين النشر:', reply_markup=intervals_keyboard())
        
        elif query.data.startswith('interval_'):
            minutes = int(query.data.split('_')[1])
            context.user_data['posting_interval'] = minutes
            context.user_data['step'] = 'posting_message'
            await query.edit_message_text(
                f'⏱ تم اختيار النشر كل {minutes} دقيقة\nأرسل الرسالة الآن:',
                reply_markup=back_keyboard()
            )
        
        elif query.data == 'help':
            help_text = (
                "🎯 دليل الاستخدام:\n\n"
                "1. تسجيل الدخول: أضف رقم هاتفك\n"
                "2. إضافة سوبر: اختر المجموعات\n"
                "3. بدء النشر: اختر الفترة وأرسل الرسالة\n\n"
                "⚠️ تحذيرات:\n"
                "- لا تشارك رمز التحقق\n"
                "- البوت لا يخزن بيانات شخصية\n\n"
                f"المطور: {DEVELOPER}"
            )
            await query.edit_message_text(help_text, reply_markup=back_keyboard())
        
        elif query.data == 'stats':
            stats = session.query(Stats).first() or Stats()
            text = (
                f"📊 الإحصائيات:\n\n"
                f"• إجمالي المنشورات: {stats.total_posts}\n"
                f"• منشوراتك: {stats.user_posts}\n"
                f"• المستخدمين: {stats.total_users}\n"
                f"• المجموعات: {stats.total_groups}"
            )
            await query.edit_message_text(text, reply_markup=back_keyboard())
    
    except Exception as e:
        logger.error(f"Button handler error: {e}")
        await query.edit_message_text("حدث خطأ، يرجى المحاولة لاحقاً")
    finally:
        Session.remove()

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        message_text = update.message.text
        user_data = context.user_data
        
        session = get_db_session()
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        # التحقق من الاشتراك
        if not user or not user.is_verified:
            await update.message.reply_text("يجب إكمال متطلبات الاشتراك أولاً!", reply_markup=verification_keyboard())
            return
        
        if 'step' not in user_data:
            return
        
        if user_data['step'] == 'login_phone':
            if not re.match(r'^\+\d{8,15}$', message_text):
                await update.message.reply_text('❌ رقم غير صحيح! مثال صحيح: +966123456789', reply_markup=back_keyboard())
                return
            
            user_data['phone'] = message_text
            async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
                if not await client.is_user_authorized():
                    await client.send_code_request(message_text)
                    user_data['phone_code_hash'] = client.phone_code_hash
                    user_data['step'] = 'login_code'
                    await update.message.reply_text('📩 تم إرسال الرمز، أرسله الآن:', reply_markup=back_keyboard())
                else:
                    session_str = client.session.save()
                    save_user_session(user_id, message_text, session_str)
                    await update.message.reply_text('✅ تم التسجيل بنجاح!', reply_markup=main_menu_keyboard())
        
        elif user_data['step'] == 'login_code':
            if not re.match(r'^\d{5}$', message_text):
                await update.message.reply_text('❌ رمز غير صحيح! يجب أن يكون 5 أرقام', reply_markup=back_keyboard())
                return
            
            async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
                try:
                    await client.sign_in(
                        phone=user_data['phone'],
                        code=message_text,
                        phone_code_hash=user_data.get('phone_code_hash', '')
                    )
                    session_str = client.session.save()
                    save_user_session(user_id, user_data['phone'], session_str)
                    await update.message.reply_text('✅ تم التسجيل بنجاح!', reply_markup=main_menu_keyboard())
                    user_data.clear()
                except Exception as e:
                    logger.error(f"Login error: {e}")
                    await update.message.reply_text('❌ فشل التسجيل، حاول مرة أخرى', reply_markup=back_keyboard())
        
        elif user_data['step'] == 'posting_message':
            interval = user_data['posting_interval']
            
            # إيقاف أي نشر سابق
            if 'job' in context.user_data:
                context.user_data['job'].schedule_removal()
            
            # بدء النشر الجديد
            context.user_data['job'] = context.job_queue.run_repeating(
                post_to_groups,
                interval=interval * 60,
                first=10,
                user_id=user_id,
                data=message_text
            )
            
            await update.message.reply_text(
                f'✅ تم بدء النشر كل {interval} دقيقة!',
                reply_markup=main_menu_keyboard()
            )
            user_data.clear()
    
    except Exception as e:
        logger.error(f"Message handler error: {e}")
        await update.message.reply_text("حدث خطأ، يرجى المحاولة لاحقاً")
    finally:
        Session.remove()

async def post_to_groups(context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = context.job.user_id
        message = context.job.data
        
        session = get_db_session()
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        if not user or not user.session_str:
            return
        
        groups = session.query(Group).filter(Group.user_id == user.id).all()
        
        if not groups:
            return
        
        # الإرسال باستخدام Telethon
        async with TelegramClient(StringSession(user.session_str), API_ID, API_HASH) as client:
            success_count = 0
            for group in groups:
                try:
                    await client.send_message(
                        InputPeerChannel(int(group.group_id), int(group.access_hash)),
                        message
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Posting error in {group.title}: {e}")
            
            # تحديث الإحصائيات
            if success_count > 0:
                stats = session.query(Stats).first() or Stats()
                stats.total_posts += success_count
                stats.user_posts += success_count
                if not stats.id:
                    session.add(stats)
                session.commit()
                logger.info(f"Posted to {success_count} groups for user {user_id}")
    
    except Exception as e:
        logger.error(f"Posting job error: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'Error: {context.error}')
    if update and isinstance(update, Update) and update.message:
        await update.message.reply_text('حدث خطأ غير متوقع!', reply_markup=main_menu_keyboard())

# ===== التشغيل الرئيسي =====
def main():
    # تهيئة البوت
    application = Application.builder().token(TOKEN).build()
    
    # تسجيل المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_error_handler(error_handler)
    
    # إعداد ويب هووك
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET
    )

if __name__ == '__main__':
    # تهيئة الإحصائيات
    session = Session()
    try:
        if not session.query(Stats).first():
            session.add(Stats())
            session.commit()
    finally:
        Session.remove()
    
    # بدء البوت
    main()
