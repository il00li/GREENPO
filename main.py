import os
import logging
import asyncio
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
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
from telethon.tl.types import InputPeerChannel, Channel

# تكوين البوت
TOKEN = "8110119856:AAGW43nAU_yO7PF7CQ096kKDlWb-Eab7IP4"
API_ID = 23656977
API_HASH = "49d3f43531a92b3f5bc403766313ca1e"
DEVELOPER = "@Ili8_8ill"
WEBHOOK_URL = "https://greenpo.onrender.com"  # استبدل مع رابطك
PORT = int(os.environ.get('PORT', 5000))

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# قنوات الاشتراك الإجباري
REQUIRED_CHANNELS = [-1001234567890, -1000987654321]  # استبدل بروابط قنواتك

# قاعدة البيانات
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    phone = Column(String)
    session_str = Column(String)
    is_verified = Column(Boolean, default=False)
    invited_users = Column(Integer, default=0)
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
engine = create_engine('sqlite:///bot_database.db', pool_pre_ping=True)
Base.metadata.create_all(engine)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

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

def verification_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ التحقق من الاشتراك", callback_data='check_subscription')],
        [InlineKeyboardButton("📣 دعوة الأصدقاء", callback_data='invite_friends')],
        [InlineKeyboardButton("👤 التواصل مع المدير", url=f"https://t.me/{DEVELOPER}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def invite_keyboard(user_id):
    invite_link = f"https://t.me/{context.bot.username}?start={user_id}"
    keyboard = [
        [InlineKeyboardButton("📤 مشاركة رابط الدعوة", url=f"https://t.me/share/url?url={invite_link}")],
        [InlineKeyboardButton("🔍 التحقق من الدعوات", callback_data='check_invites')],
        [InlineKeyboardButton("👤 التواصل مع المدير", url=f"https://t.me/{DEVELOPER}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# وظائف مساعدة
def get_db_session():
    return Session()

def save_user_session(user_id, phone, session_str):
    session = get_db_session()
    try:
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
            user.phone = phone
        
        session.commit()
        return user
    except Exception as e:
        logger.error(f"Error saving user session: {e}")
        session.rollback()
    finally:
        Session.remove()

async def get_user_groups(session_str):
    try:
        async with TelegramClient(StringSession(session_str), API_ID, API_HASH) as client:
            groups = []
            async for dialog in client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    if hasattr(dialog.entity, 'access_hash'):
                        groups.append((
                            dialog.entity.id,
                            dialog.entity.access_hash,
                            dialog.name
                        ))
            return groups
    except Exception as e:
        logger.error(f"Error getting user groups: {e}")
        return []

async def is_user_subscribed(user_id, session_str):
    try:
        async with TelegramClient(StringSession(session_str), API_ID, API_HASH) as client:
            for channel_id in REQUIRED_CHANNELS:
                try:
                    channel = await client.get_entity(Channel(channel_id))
                    participant = await client.get_participants(channel, user_id)
                    if not participant:
                        return False
                except Exception as e:
                    logger.error(f"Error checking subscription for channel {channel_id}: {e}")
                    return False
            return True
    except Exception as e:
        logger.error(f"Error in subscription check: {e}")
        return False

# وظائف البوت الأساسية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_db_session()
    try:
        user_id = update.effective_user.id
        
        # التحقق من رابط الدعوة
        if context.args and context.args[0].isdigit():
            inviter_id = int(context.args[0])
            if inviter_id != user_id:
                inviter = session.query(User).filter(User.telegram_id == inviter_id).first()
                if inviter:
                    inviter.invited_users += 1
                    session.commit()
        
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        if user and user.is_verified:
            await update.message.reply_text(
                'مرحباً! اختر من القائمة:',
                reply_markup=main_menu_keyboard()
            )
        else:
            # عرض شروط الاشتراك
            channels_text = "\n".join([f"🔹 https://t.me/c/{str(abs(ch))[4:]}" for ch in REQUIRED_CHANNELS])
            await update.message.reply_text(
                f"👋 أهلاً بك!\n\n"
                f"📌 لاستخدام البوت يجب عليك:\n"
                f"1. الاشتراك في القنوات التالية:\n{channels_text}\n"
                f"2. دعوة 5 أصدقاء على الأقل\n\n"
                f"بعد إتمام الخطوات اضغط على زر التحقق",
                reply_markup=verification_keyboard()
            )
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text("حدث خطأ! يرجى المحاولة لاحقاً")
    finally:
        Session.remove()

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    session = get_db_session()
    try:
        user_id = query.from_user.id
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        if query.data == 'back':
            await query.edit_message_text(
                'القائمة الرئيسية:',
                reply_markup=main_menu_keyboard()
            )
        
        elif query.data == 'login':
            if user and user.is_verified:
                context.user_data['step'] = 'login_phone'
                await query.edit_message_text(
                    'أرسل رقم هاتفك مع رمز الدولة، مثال: +966123456789',
                    reply_markup=back_keyboard()
                )
            else:
                await query.edit_message_text(
                    "يجب عليك إكمال متطلبات الاشتراك أولاً!",
                    reply_markup=verification_keyboard()
                )
        
        elif query.data == 'check_subscription':
            if not user or not user.session_str:
                await query.edit_message_text(
                    "يجب تسجيل الدخول أولاً!",
                    reply_markup=back_keyboard()
                )
                return
            
            subscribed = await is_user_subscribed(user_id, user.session_str)
            if subscribed:
                if user.invited_users >= 5:
                    user.is_verified = True
                    session.commit()
                    await query.edit_message_text(
                        "✅ تم التحقق بنجاح!\n\nيمكنك الآن استخدام البوت",
                        reply_markup=main_menu_keyboard()
                    )
                else:
                    await query.edit_message_text(
                        f"❌ لم تكمل الشروط!\n\n"
                        f"عدد الدعوات المطلوبة: 5\n"
                        f"عدد دعواتك الحالية: {user.invited_users}\n\n"
                        f"يرجى دعوة المزيد من الأصدقاء",
                        reply_markup=invite_keyboard(user_id)
                    )
            else:
                await query.edit_message_text(
                    "❌ لم تشترك في القنوات المطلوبة!\n\n"
                    "يرجى الاشتراك في جميع القنوات ثم الضغط على زر التحقق",
                    reply_markup=verification_keyboard()
                )
        
        elif query.data == 'invite_friends':
            await query.edit_message_text(
                f"📣 دعوة الأصدقاء:\n\n"
                f"لإكمال متطلبات الاشتراك، يجب دعوة 5 أصدقاء\n"
                f"عدد دعواتك الحالية: {user.invited_users if user else 0}\n\n"
                f"استخدم الرابط التالي لدعوة الأصدقاء:",
                reply_markup=invite_keyboard(user_id)
            )
        
        elif query.data == 'add_groups':
            if not user or not user.is_verified:
                await query.edit_message_text(
                    "يجب عليك إكمال متطلبات الاشتراك أولاً!",
                    reply_markup=verification_keyboard()
                )
                return
                
            if not user.session_str:
                await query.edit_message_text(
                    'يجب تسجيل الدخول أولاً!',
                    reply_markup=back_keyboard()
                )
                return
            
            context.user_data['step'] = 'adding_groups'
            await query.edit_message_text(
                'جاري جلب مجموعاتك...',
                reply_markup=back_keyboard()
            )
            
            # جلب المجموعات باستخدام Telethon
            groups = await get_user_groups(user.session_str)
            
            if not groups:
                await query.edit_message_text('لم يتم العثور على مجموعات!', reply_markup=back_keyboard())
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
            
            await query.edit_message_text(
                f'تمت إضافة {added_count} مجموعة جديدة!',
                reply_markup=back_keyboard()
            )
        
        elif query.data == 'start_posting':
            if not user or not user.is_verified:
                await query.edit_message_text(
                    "يجب عليك إكمال متطلبات الاشتراك أولاً!",
                    reply_markup=verification_keyboard()
                )
                return
                
            await query.edit_message_text(
                'اختر الفترة الزمنية بين النشر:',
                reply_markup=intervals_keyboard()
            )
        
        elif query.data.startswith('interval_'):
            minutes = int(query.data.split('_')[1])
            context.user_data['posting_interval'] = minutes
            context.user_data['step'] = 'posting_message'
            await query.edit_message_text(
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
            await query.edit_message_text(help_text, reply_markup=back_keyboard())
        
        elif query.data == 'stats':
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
            await query.edit_message_text(text, reply_markup=back_keyboard())
    
    except Exception as e:
        logger.error(f"Error in button handler: {e}")
        await query.edit_message_text("حدث خطأ! يرجى المحاولة لاحقاً")
    finally:
        Session.remove()

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_db_session()
    try:
        user_data = context.user_data
        user_id = update.message.from_user.id
        message_text = update.message.text
        
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        # التحقق من الاشتراك
        if not user or not user.is_verified:
            await update.message.reply_text(
                "يجب عليك إكمال متطلبات الاشتراك أولاً!",
                reply_markup=verification_keyboard()
            )
            return
        
        if 'step' not in user_data:
            return
        
        if user_data['step'] == 'login_phone':
            # التحقق من صحة رقم الهاتف
            if not message_text.startswith('+'):
                await update.message.reply_text(
                    'رقم الهاتف يجب أن يبدأ بـ +',
                    reply_markup=back_keyboard()
                )
                return
            
            phone = message_text
            user_data['phone'] = phone
            
            # إنشاء جلسة Telethon
            async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
                if not await client.is_user_authorized():
                    await client.send_code_request(phone)
                    user_data['phone_code_hash'] = client.phone_code_hash
                    user_data['step'] = 'login_code'
                    await update.message.reply_text(
                        'تم إرسال رمز التحقق إلى حسابك\nأرسل الرمز الآن:',
                        reply_markup=back_keyboard()
                    )
                else:
                    session_str = client.session.save()
                    save_user_session(user_id, phone, session_str)
                    await update.message.reply_text(
                        'تم تسجيل الدخول بنجاح!',
                        reply_markup=main_menu_keyboard()
                    )
        
        elif user_data['step'] == 'login_code':
            code = message_text.strip()
            phone = user_data['phone']
            phone_code_hash = user_data.get('phone_code_hash', '')
            
            async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
                try:
                    await client.sign_in(
                        phone=phone, 
                        code=code,
                        phone_code_hash=phone_code_hash
                    )
                    session_str = client.session.save()
                    save_user_session(user_id, phone, session_str)
                    await update.message.reply_text(
                        'تم تسجيل الدخول بنجاح!',
                        reply_markup=main_menu_keyboard()
                    )
                    user_data.clear()
                except Exception as e:
                    logger.error(f"Error in code verification: {e}")
                    await update.message.reply_text(
                        'رمز خاطئ! حاول مرة أخرى',
                        reply_markup=back_keyboard()
                    )
        
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
                user_id=user_id,
                data=message_text
            )
            
            await update.message.reply_text(
                f'تم بدء النشر كل {interval} دقيقة!',
                reply_markup=main_menu_keyboard()
            )
            user_data.clear()
    
    except Exception as e:
        logger.error(f"Error in message handler: {e}")
        await update.message.reply_text("حدث خطأ! يرجى المحاولة لاحقاً")
    finally:
        Session.remove()

async def post_to_groups(context: ContextTypes.DEFAULT_TYPE):
    session = get_db_session()
    try:
        user_id = context.job.user_id
        message = context.job.data
        
        user = session.query(User).filter(User.telegram_id == user_id).first()
        
        if not user or not user.session_str:
            return
        
        groups = session.query(Group).filter(Group.user_id == user.id).all()
        
        if not groups:
            return
        
        # إرسال الرسالة باستخدام Telethon
        async with TelegramClient(StringSession(user.session_str), API_ID, API_HASH) as client:
            success_count = 0
            for group in groups:
                try:
                    entity = InputPeerChannel(
                        int(group.group_id),
                        int(group.access_hash)
                    )
                    await client.send_message(entity, message)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error posting to {group.title}: {e}")
        
        # تحديث الإحصائيات
        if success_count > 0:
            stats = session.query(Stats).first()
            if not stats:
                stats = Stats()
                session.add(stats)
            stats.total_posts += success_count
            stats.user_posts += success_count
            session.commit()
    
    except Exception as e:
        logger.error(f"Error in posting job: {e}")
    finally:
        Session.remove()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'Update {update} caused error: {context.error}')
    if update and isinstance(update, Update) and update.message:
        await update.message.reply_text(
            'حدث خطأ غير متوقع!',
            reply_markup=main_menu_keyboard()
        )

def main() -> None:
    # تهيئة الإحصائيات
    session = get_db_session()
    try:
        if not session.query(Stats).first():
            session.add(Stats())
            session.commit()
    finally:
        Session.remove()
    
    # بدء البوت
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
        secret_token='WEBHOOK_SECRET'
    )

if __name__ == '__main__':
    main()
