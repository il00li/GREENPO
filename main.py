import os
import logging
import asyncio
import re
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy.ext.declarative import declarative_base
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
from telethon.tl.functions.channels import GetFullChannelRequest

# ===== إعدادات البيئة =====
TOKEN = os.getenv('TOKEN', '7966976239:AAHLSZafl8E_j1GNT0TfTuRjZRfNAXMvzDs')
API_ID = int(os.getenv('API_ID', '23656977'))
API_HASH = os.getenv('API_HASH', '49d3f43531a92b3f5bc403766313ca1e')
DEVELOPER = os.getenv('DEVELOPER', '@Ili8_8ill')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://greenpo.onrender.com')
PORT = int(os.getenv('PORT', '5000'))
REQUIRED_CHANNELS = os.getenv('REQUIRED_CHANNELS', 't.me/crazys7,t.me/AWU87').split(',')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'SECRET_TOKEN')
INVITES_REQUIRED = 5  # عدد الدعوات المطلوبة

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
    has_subscribed = Column(Boolean, default=False)  # هل اشترك في القنوات؟
    invited_users = Column(Integer, default=0)       # عدد المستخدمين الذين دعاهم
    is_verified = Column(Boolean, default=False)     # هل اكتملت جميع الشروط؟
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

engine = create_engine('sqlite:///bot_database.db', pool_pre_ping=True)
Base.metadata.create_all(engine)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# ===== وظائف لوحة المفاتيح =====
def get_main_menu_keyboard(user):
    """لوحة المفاتيح الرئيسية تظهر فقط عند استيفاء جميع الشروط"""
    if user and user.is_verified:
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
    return None

def get_subscription_keyboard():
    """لوحة مفاتيح للتحقق من الاشتراك"""
    buttons = []
    for channel in REQUIRED_CHANNELS:
        channel_name = channel.split('/')[-1] if '/' in channel else channel
        buttons.append([InlineKeyboardButton(f"اشترك في {channel_name}", url=channel)])
    buttons.append([InlineKeyboardButton("✅ التحقق من الاشتراك", callback_data='check_subscription')])
    return InlineKeyboardMarkup(buttons)

def get_invitation_keyboard(user_id):
    """لوحة مفاتيح لدعوة الأصدقاء"""
    invite_link = f"https://t.me/share/url?url=/start%20{user_id}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 دعوة الأصدقاء", url=invite_link)],
        [InlineKeyboardButton("🔍 عدد الدعوات", callback_data='check_invites')],
        [InlineKeyboardButton("👤 تواصل مع المدير", url=f"https://t.me/{DEVELOPER.replace('@', '')}")]
    ])

def back_keyboard():
    """زر الرجوع"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data='back')]])

def intervals_keyboard():
    """لوحة مفاتيح لفترات النشر"""
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

# ===== وظائف مساعدة =====
def get_db_session():
    """الحصول على جلسة قاعدة بيانات"""
    return Session()

def save_user_session(user_id, phone, session_str):
    """حفظ جلسة المستخدم في قاعدة البيانات"""
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
        logger.error(f"خطأ في حفظ الجلسة: {e}")
        session.rollback()
        return None
    finally:
        Session.remove()

async def get_user_groups(session_str):
    """الحصول على مجموعات المستخدم"""
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
        logger.error(f"خطأ في جلب المجموعات: {e}")
        return []

async def is_user_subscribed(user_id, session_str):
    """التحقق من اشتراك المستخدم في القنوات المطلوبة"""
    try:
        async with TelegramClient(StringSession(session_str), API_ID, API_HASH) as client:
            for channel_link in REQUIRED_CHANNELS:
                try:
                    # استخراج معرف القناة من الرابط
                    channel_username = channel_link.split('/')[-1]
                    channel = await client.get_entity(channel_username)
                    
                    # التحقق من اشتراك المستخدم
                    participants = await client.get_participants(channel, aggressive=True)
                    participant_ids = [p.id for p in participants]
                    
                    if user_id not in participant_ids:
                        return False
                except Exception as e:
                    logger.error(f"خطأ في التحقق من القناة {channel_link}: {e}")
                    return False
            return True
    except Exception as e:
        logger.error(f"خطأ في التحقق من الاشتراك: {e}")
        return False

def check_user_access(user, feature_name):
    """التحقق من صلاحية المستخدم لاستخدام ميزة معينة"""
    if not user:
        return False, "لم يتم العثور على حسابك! ابدأ بالضغط على /start"
    
    if not user.has_subscribed:
        return False, f"يجب الاشتراك في القنوات المطلوبة أولاً لاستخدام {feature_name}"
    
    if not user.is_verified:
        invites_needed = INVITES_REQUIRED - user.invited_users
        return False, (
            f"يجب دعوة {invites_needed} أشخاص آخرين لاستخدام {feature_name}\n\n"
            f"عدد دعواتك الحالية: {user.invited_users}/{INVITES_REQUIRED}"
        )
    
    return True, ""

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
        
        # إنشاء حساب جديد إذا لم يكن موجوداً
        if not user:
            user = User(telegram_id=user_id)
            session.add(user)
            session.commit()
        
        # عرض الواجهة المناسبة حسب حالة المستخدم
        if user.is_verified:
            await update.message.reply_text(
                'مرحباً بك في البوت! اختر من القائمة:',
                reply_markup=get_main_menu_keyboard(user)
            )
        elif user.has_subscribed:
            invites_needed = INVITES_REQUIRED - user.invited_users
            await update.message.reply_text(
                f"✅ لقد أكملت متطلبات الاشتراك!\n\n"
                f"يجب دعوة {invites_needed} أشخاص آخرين لتفعيل حسابك\n"
                f"عدد دعواتك الحالية: {user.invited_users}/{INVITES_REQUIRED}",
                reply_markup=get_invitation_keyboard(user_id)
            )
        else:
            await update.message.reply_text(
                "👋 أهلاً بك في بوت النشر التلقائي!\n\n"
                "📌 لاستخدام البوت يجب عليك الاشتراك في القنوات التالية:",
                reply_markup=get_subscription_keyboard()
            )
    except Exception as e:
        logger.error(f"خطأ في الأمر /start: {e}")
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
        
        # معالجة الأزرار
        if query.data == 'back':
            if user and user.is_verified:
                await query.edit_message_text('القائمة الرئيسية:', reply_markup=get_main_menu_keyboard(user))
            else:
                await query.edit_message_text("استخدم /start للعودة للبداية")
        
        elif query.data == 'login':
            # التحقق من الصلاحية
            has_access, message = check_user_access(user, "تسجيل الدخول")
            if not has_access:
                await query.answer(message, show_alert=True)
                return
            
            context.user_data['step'] = 'login_phone'
            await query.edit_message_text('أرسل رقم هاتفك مع رمز الدولة (مثال: +966123456789):', reply_markup=back_keyboard())
        
        elif query.data == 'check_subscription':
            if not user or not user.session_str:
                await query.answer("يجب تسجيل الدخول أولاً!", show_alert=True)
                return
            
            await query.edit_message_text("🔍 جاري التحقق من اشتراكك...")
            subscribed = await is_user_subscribed(user_id, user.session_str)
            
            if subscribed:
                user.has_subscribed = True
                
                # التحقق من اكتمال الدعوات
                if user.invited_users >= INVITES_REQUIRED:
                    user.is_verified = True
                    await query.edit_message_text(
                        "✅ تم التحقق بنجاح! يمكنك الآن استخدام جميع ميزات البوت",
                        reply_markup=get_main_menu_keyboard(user)
                    )
                else:
                    invites_needed = INVITES_REQUIRED - user.invited_users
                    await query.edit_message_text(
                        f"✅ تم التحقق من اشتراكك!\n\n"
                        f"يجب دعوة {invites_needed} أشخاص آخرين لتفعيل حسابك\n"
                        f"عدد دعواتك الحالية: {user.invited_users}/{INVITES_REQUIRED}",
                        reply_markup=get_invitation_keyboard(user_id)
                    )
                
                session.commit()
            else:
                await query.edit_message_text(
                    "❌ لم تشترك في جميع القنوات المطلوبة!\n\n"
                    "يرجى الاشتراك في القنوات التالية ثم المحاولة مرة أخرى:",
                    reply_markup=get_subscription_keyboard()
                )
        
        elif query.data == 'add_groups':
            # التحقق من الصلاحية
            has_access, message = check_user_access(user, "إضافة مجموعات")
            if not has_access:
                await query.answer(message, show_alert=True)
                return
            
            if not user.session_str:
                await query.answer("يجب تسجيل الدخول أولاً!", show_alert=True)
                return
            
            await query.edit_message_text('⏳ جاري جلب مجموعاتك...')
            groups = await get_user_groups(user.session_str)
            
            if not groups:
                await query.edit_message_text('❌ لم يتم العثور على مجموعات!', reply_markup=back_keyboard())
                return
            
            # حفظ المجموعات
            added_count = 0
            for group_id, access_hash, title in groups:
                existing = session.query(Group).filter(
                    Group.group_id == str(group_id),
                    Group.user_id == user.id
                ).first()
                
                if not existing:
                    session.add(Group(
                        group_id=str(group_id),
                        access_hash=str(access_hash),
                        title=title,
                        user_id=user.id
                    ))
                    added_count += 1
            
            # تحديث الإحصائيات
            stats = session.query(Stats).first() or Stats()
            stats.total_groups += added_count
            if not stats.id:
                session.add(stats)
            
            session.commit()
            await query.edit_message_text(f'✅ تمت إضافة {added_count} مجموعة جديدة!', reply_markup=back_keyboard())
        
        elif query.data == 'start_posting':
            # التحقق من الصلاحية
            has_access, message = check_user_access(user, "بدء النشر")
            if not has_access:
                await query.answer(message, show_alert=True)
                return
            
            await query.edit_message_text('⏱ اختر الفترة الزمنية بين النشر:', reply_markup=intervals_keyboard())
        
        elif query.data.startswith('interval_'):
            # التحقق من الصلاحية
            has_access, message = check_user_access(user, "بدء النشر")
            if not has_access:
                await query.answer(message, show_alert=True)
                return
            
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
                "1. الاشتراك في القنوات المطلوبة\n"
                "2. دعوة 5 أصدقاء\n"
                "3. تسجيل الدخول باستخدام رقم الهاتف\n"
                "4. إضافة المجموعات المراد النشر فيها\n"
                "5. بدء النشر التلقائي\n\n"
                "⚠️ تحذيرات:\n"
                "- لا تشارك رمز التحقق مع أحد\n"
                "- تأكد من اشتراكك في القنوات المطلوبة\n\n"
                f"المطور: {DEVELOPER}"
            )
            await query.edit_message_text(help_text, reply_markup=back_keyboard())
        
        elif query.data == 'stats':
            # التحقق من الصلاحية
            has_access, message = check_user_access(user, "الإحصائيات")
            if not has_access:
                await query.answer(message, show_alert=True)
                return
            
            stats = session.query(Stats).first() or Stats()
            user_stats = f"عدد مجموعاتك: {len(user.groups)}" if user else ""
            
            text = (
                f"📊 إحصائيات البوت:\n\n"
                f"• إجمالي المنشورات: {stats.total_posts}\n"
                f"• المنشورات من حسابك: {stats.user_posts}\n"
                f"• إجمالي المستخدمين: {stats.total_users}\n"
                f"• إجمالي المجموعات: {stats.total_groups}\n\n"
                f"{user_stats}"
            )
            await query.edit_message_text(text, reply_markup=back_keyboard())
        
        elif query.data == 'check_invites':
            if user:
                invites_needed = INVITES_REQUIRED - user.invited_users
                await query.answer(f"عدد دعواتك: {user.invited_users}/{INVITES_REQUIRED}\nما زال ينقصك: {invites_needed}", show_alert=True)
            else:
                await query.answer("لم يتم العثور على حسابك! ابدأ بالضغط على /start", show_alert=True)
    
    except Exception as e:
        logger.error(f"خطأ في معالج الأزرار: {e}")
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
        
        # التحقق من الصلاحية للاستمرار
        if 'step' in user_data and user_data['step'] not in ['login_phone', 'login_code']:
            has_access, error_msg = check_user_access(user, "هذه الميزة")
            if not has_access:
                await update.message.reply_text(error_msg)
                return
        
        if 'step' not in user_data:
            return
        
        if user_data['step'] == 'login_phone':
            # التحقق من صحة رقم الهاتف
            if not re.match(r'^\+\d{8,15}$', message_text):
                await update.message.reply_text('❌ رقم غير صحيح! مثال صحيح: +966123456789', reply_markup=back_keyboard())
                return
            
            user_data['phone'] = message_text
            async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
                if not await client.is_user_authorized():
                    await client.send_code_request(message_text)
                    user_data['phone_code_hash'] = client.phone_code_hash
                    user_data['step'] = 'login_code'
                    await update.message.reply_text('📩 تم إرسال رمز التحقق، أرسله الآن:', reply_markup=back_keyboard())
                else:
                    session_str = client.session.save()
                    save_user_session(user_id, message_text, session_str)
                    await update.message.reply_text('✅ تم تسجيل الدخول بنجاح!', reply_markup=get_main_menu_keyboard(user))
        
        elif user_data['step'] == 'login_code':
            # التحقق من صحة الرمز
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
                    user = save_user_session(user_id, user_data['phone'], session_str)
                    await update.message.reply_text('✅ تم تسجيل الدخول بنجاح!', reply_markup=get_main_menu_keyboard(user))
                    user_data.clear()
                except Exception as e:
                    logger.error(f"خطأ في تسجيل الدخول: {e}")
                    await update.message.reply_text('❌ فشل التسجيل، يرجى المحاولة مرة أخرى', reply_markup=back_keyboard())
        
        elif user_data['step'] == 'posting_message':
            # التحقق من الصلاحية
            has_access, error_msg = check_user_access(user, "النشر التلقائي")
            if not has_access:
                await update.message.reply_text(error_msg)
                return
            
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
                reply_markup=get_main_menu_keyboard(user)
            )
            user_data.clear()
    
    except Exception as e:
        logger.error(f"خطأ في معالج الرسائل: {e}")
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
                    logger.error(f"خطأ في النشر بمجموعة {group.title}: {e}")
            
            # تحديث الإحصائيات
            if success_count > 0:
                stats = session.query(Stats).first() or Stats()
                stats.total_posts += success_count
                stats.user_posts += success_count
                if not stats.id:
                    session.add(stats)
                session.commit()
                logger.info(f"تم النشر في {success_count} مجموعات للمستخدم {user_id}")
    
    except Exception as e:
        logger.error(f"خطأ في مهمة النشر: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'خطأ: {context.error}')
    if update and isinstance(update, Update) and update.message:
        await update.message.reply_text('حدث خطأ غير متوقع! ابدأ من جديد بالضغط على /start')

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
