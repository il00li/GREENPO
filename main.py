import logging
import sqlite3
import asyncio
import aiohttp
import json
import requests
import os
import uuid
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.error import BadRequest, Forbidden
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import base64
import re

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# التوكنات والمفاتيح
BOT_TOKEN = "8300609210:AAENBlzLuiMv_N7WY3XAp-9Ux1p2fr4vTpA"
ADMIN_ID = 6689435577
CHANNEL_USERNAME = "iIl337"  # بدون @
GITHUB_TOKEN = "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"
GITHUB_REPO = "telegram-bot-deploy"
RENDER_TOKEN = "rnd_giDks7sFiBMBA74sOAV4E2xD01TX"
RENDER_SERVICE_ID = "telegram-bot-service"
GEMINI_API_KEY = "AIzaSyD3w0ZtC-GOvOVVlUxb_l0ayRAVsar64FI"

# حالة البوت
BOT_MAINTENANCE = False
POINTS_SYSTEM = True

# إعداد قاعدة البيانات
def setup_database():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        points INTEGER DEFAULT 0,
        invited_by INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول الملفات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        file_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        file_name TEXT,
        github_url TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # جدول روابط الدعوة
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS referral_links (
        link_id TEXT PRIMARY KEY,
        user_id INTEGER,
        uses INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # جدول المحادثات مع الذكاء الاصطناعي
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ai_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        chat_history TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # جدول الإشعارات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        message TEXT,
        sent_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

# إضافة مستخدم جديد
def add_user(user_id, username, first_name, last_name):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, points)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, 0))
    
    conn.commit()
    conn.close()

# الحصول على بيانات المستخدم
def get_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    conn.close()
    
    if user:
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, user))
    return None

# تحديث نقاط المستخدم
def update_user_points(user_id, points_change):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (points_change, user_id))
    
    conn.commit()
    conn.close()

# الحصول على جميع المستخدمين
def get_all_users():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id FROM users WHERE is_banned = 0')
    users = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return users

# حفظ ملف جديد
def save_file(user_id, file_name, github_url):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO files (user_id, file_name, github_url)
    VALUES (?, ?, ?)
    ''', (user_id, file_name, github_url))
    
    conn.commit()
    conn.close()

# الحصول على ملفات المستخدم
def get_user_files(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM files WHERE user_id = ?', (user_id,))
    files = cursor.fetchall()
    
    conn.close()
    return files

# إيقاف ملفات المستخدم
def stop_user_files(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE files SET is_active = 0 WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()

# حظر مستخدم
def ban_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
    cursor.execute('UPDATE files SET is_active = 0 WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()

# إلغاء حظر مستخدم
def unban_user(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()

# حفظ رابط الدعوة
def save_referral_link(link_id, user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('INSERT OR REPLACE INTO referral_links (link_id, user_id) VALUES (?, ?)', (link_id, user_id))
    
    conn.commit()
    conn.close()

# الحصول على رابط الدعوة
def get_referral_link(link_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM referral_links WHERE link_id = ?', (link_id,))
    link = cursor.fetchone()
    
    conn.close()
    return link

# زيادة عدد استخدامات رابط الدعوة
def increment_referral_uses(link_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE referral_links SET uses = uses + 1 WHERE link_id = ?', (link_id,))
    
    conn.commit()
    conn.close()

# حفظ محادثة الذكاء الاصطناعي
def save_ai_session(user_id, chat_history):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # تحقق إذا كانت هناك جلسة نشطة
    cursor.execute('SELECT session_id FROM ai_sessions WHERE user_id = ? AND is_active = 1', (user_id,))
    existing_session = cursor.fetchone()
    
    if existing_session:
        cursor.execute('UPDATE ai_sessions SET chat_history = ? WHERE session_id = ?', 
                      (json.dumps(chat_history), existing_session[0]))
    else:
        cursor.execute('INSERT INTO ai_sessions (user_id, chat_history) VALUES (?, ?)', 
                      (user_id, json.dumps(chat_history)))
    
    conn.commit()
    conn.close()

# الحصول على محادثة الذكاء الاصطناعي
def get_ai_session(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT chat_history FROM ai_sessions WHERE user_id = ? AND is_active = 1', (user_id,))
    session = cursor.fetchone()
    
    conn.close()
    
    if session and session[0]:
        return json.loads(session[0])
    return []

# إنهاء جلسة الذكاء الاصطناعي
def end_ai_session(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE ai_sessions SET is_active = 0 WHERE user_id = ? AND is_active = 1', (user_id,))
    
    conn.commit()
    conn.close()

# حفظ إشعار
def save_notification(admin_id, message):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('INSERT INTO notifications (admin_id, message) VALUES (?, ?)', (admin_id, message))
    notification_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return notification_id

# تحديث إحصاءات الإشعار
def update_notification_stats(notification_id, sent_count, failed_count):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    cursor.execute('UPDATE notifications SET sent_count = sent_count + ?, failed_count = failed_count + ? WHERE notification_id = ?', 
                  (sent_count, failed_count, notification_id))
    
    conn.commit()
    conn.close()

# التحقق من اشتراك المستخدم في القناة
async def is_user_subscribed(user_id, context):
    try:
        member = await context.bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status in ['member', 'administrator', 'creator']
    except (BadRequest, Forbidden) as e:
        logger.error(f"Error checking channel subscription: {e}")
        return False

# إنشاء لوحة المفاتيح الرئيسية
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📤 رفع ملف", callback_data='upload_file')],
        [InlineKeyboardButton("⚙️ إعدادات", callback_data='settings')],
        [InlineKeyboardButton("🤖 تحدث مع AI", callback_data='chat_with_ai')],
        [InlineKeyboardButton("⏹️ إيقاف ملفاتي", callback_data='stop_my_files')]
    ]
    return InlineKeyboardMarkup(keyboard)

# إنشاء لوحة إعدادات
def settings_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 صنع ملف", callback_data='create_file')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

# إنشاء لوحة إدارة المدير
def admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data='ban_user')],
        [InlineKeyboardButton("✅ إلغاء الحظر", callback_data='unban_user')],
        [InlineKeyboardButton("💎 تفعيل وضع النقاط", callback_data='enable_points')],
        [InlineKeyboardButton("🔕 إيقاف وضع النقاط", callback_data='disable_points')],
        [InlineKeyboardButton("📢 إرسال إشعار", callback_data='send_notification')],
        [InlineKeyboardButton("🔧 إيقاف البوت للصيانة", callback_data='maintenance_mode')],
        [InlineKeyboardButton("🔄 إعادة تشغيل البوت", callback_data='restart_bot')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

# إنشاء لوحة إنهاء المحادثة
def end_chat_keyboard():
    keyboard = [
        [InlineKeyboardButton("إنهاء المحادثة", callback_data='end_ai_chat')]
    ]
    return InlineKeyboardMarkup(keyboard)

# معالجة أمر البدء
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name or ""
    
    # إضافة المستخدم إلى قاعدة البيانات
    add_user(user_id, username, first_name, last_name)
    
    # التحقق من حالة البوت
    if BOT_MAINTENANCE and user_id != ADMIN_ID:
        await update.message.reply_text("⛔ البوت تحت الصيانة حالياً. يرجى المحاولة لاحقاً.")
        return
    
    # التحقق من وجود رابط دعوة
    if context.args and len(context.args) > 0:
        referral_id = context.args[0]
        referral = get_referral_link(referral_id)
        
        if referral and referral[1] != user_id:  # referral[1] هو user_id صاحب الرابط
            # منح النقطة لصاحب الرابط
            update_user_points(referral[1], 1)
            increment_referral_uses(referral_id)
            
            await update.message.reply_text(
                "✅ تمت إضافة نقطة لصاحب رابط الدعوة.\n\n"
                "شكراً لك على استخدام الرابط!"
            )
    
    # التحقق من اشتراك المستخدم في القناة
    if not await is_user_subscribed(user_id, context):
        await update.message.reply_text(
            f"👋 أهلاً بك {first_name}!\n\n"
            f"يجب عليك الاشتراك في قناتنا أولاً لاستخدام البوت:\n"
            f"https://t.me/{CHANNEL_USERNAME}\n\n"
            "بعد الاشتراك، أرسل /start مرة أخرى."
        )
        return
    
    # التحقق من حالة الحظر
    user = get_user(user_id)
    if user and user.get('is_banned', 0) == 1:
        await update.message.reply_text("⛔ تم حظرك من استخدام البوت.")
        return
    
    # عرض لوحة المفاتيح الرئيسية
    await update.message.reply_text(
        "مرحباً بك في بوت Fo79BOT! 👋\n\n"
        "اختر من الخيارات أدناه:",
        reply_markup=main_keyboard()
    )

# معالجة أمر المساعدة
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧾 دليل استخدام البوت:\n\n"
        "📤 رفع ملف - لرفع ملفات Python لتشغيلها\n"
        "⚙️ إعدادات - لإنشاء ملفات جديدة والتعديل عليها\n"
        "🤖 تحدث مع AI - للدردشة مع الذكاء الاصطناعي Gemini\n"
        "⏹️ إيقاف ملفاتي - لإيقاف جميع ملفاتك النشطة\n\n"
        "لبدء استخدام البوت، اضغط /start"
    )

# معالجة أمر الإدارة
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ ليس لديك صلاحية الوصول إلى هذه الأداة.")
        return
    
    await update.message.reply_text(
        "👑 لوحة تحكم المدير\n\n"
        "اختر الإجراء المطلوب:",
        reply_markup=admin_keyboard()
    )

# معالجة استدعاءات الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # التحقق من حالة البوت
    if BOT_MAINTENANCE and user_id != ADMIN_ID:
        await query.edit_message_text("⛔ البوت تحت الصيانة حالياً. يرجى المحاولة لاحقاً.")
        return
    
    # التحقق من اشتراك المستخدم في القناة
    if not await is_user_subscribed(user_id, context):
        await query.edit_message_text(
            f"يجب عليك الاشتراك في قناتنا أولاً:\n"
            f"https://t.me/{CHANNEL_USERNAME}\n\n"
            "بعد الاشتراك، أرسل /start مرة أخرى."
        )
        return
    
    # التحقق من حالة الحظر
    user = get_user(user_id)
    if user and user.get('is_banned', 0) == 1:
        await query.edit_message_text("⛔ تم حظرك من استخدام البوت.")
        return
    
    # معالجة الأزرار المختلفة
    if data == 'upload_file':
        await handle_upload_file(query, context)
    elif data == 'settings':
        await query.edit_message_text(
            "⚙️ إعدادات البوت\n\n"
            "اختر من الخيارات أدناه:",
            reply_markup=settings_keyboard()
        )
    elif data == 'create_file':
        await query.edit_message_text(
            "📝 أرسل كود Python الذي تريد تحويله إلى ملف.\n\n"
            "سيتم تحويل النص إلى ملف .py وإرساله لك."
        )
        context.user_data['awaiting_code'] = True
    elif data == 'chat_with_ai':
        await start_ai_chat(query, context)
    elif data == 'stop_my_files':
        await stop_user_files(query, context)
    elif data == 'back_to_main':
        await query.edit_message_text(
            "🏠 الرئيسية\n\n"
            "اختر من الخيارات أدناه:",
            reply_markup=main_keyboard()
        )
    elif data == 'end_ai_chat':
        await end_ai_chat(query, context)
    elif data.startswith('run_file:'):
        file_name = data.split(':', 1)[1]
        await run_file(query, context, file_name)
    elif user_id == ADMIN_ID:
        await handle_admin_actions(query, context, data)

# معالجة رفع الملف
async def handle_upload_file(query, context):
    user_id = query.from_user.id
    user = get_user(user_id)
    
    # التحقق من رصيد النقاط
    if POINTS_SYSTEM and user.get('points', 0) <= 0:
        # إنشاء رابط دعوة فريد
        referral_id = str(uuid.uuid4())[:8]
        save_referral_link(referral_id, user_id)
        
        referral_link = f"https://t.me/{(await context.bot.get_me()).username}?start={referral_id}"
        
        await query.edit_message_text(
            "⛔ ليس لديك نقاط كافية لرفع الملف.\n\n"
            "شارك رابط الدعوة هذا مع أصدقائك:\n"
            f"{referral_link}\n\n"
            "كل صديق يستخدم الرابط سيمنحك نقطة واحدة."
        )
        return
    
    await query.edit_message_text(
        "📤 أرسل ملف Python (.py) الذي تريد رفعه.\n\n"
        "سيتم خصم نقطة واحدة من رصيدك بعد الرفع الناجح."
    )
    context.user_data['awaiting_file'] = True

# بدء محادثة الذكاء الاصطناعي
async def start_ai_chat(query, context):
    user_id = query.from_user.id
    
    # إنشاء جلسة جديدة أو استرجاع الجلسة الحالية
    chat_history = get_ai_session(user_id)
    
    await query.edit_message_text(
        "🤖 بدأت جلسة المحادثة مع Gemini AI\n\n"
        "أرسل رسالتك الآن:\n\n"
        "لإنهاء المحادثة، اضغط على الزر في الأسفل.",
        reply_markup=end_chat_keyboard()
    )
    context.user_data['ai_chat_active'] = True

# إنهاء محادثة الذكاء الاصطناعي
async def end_ai_chat(query, context):
    user_id = query.from_user.id
    end_ai_session(user_id)
    
    if 'ai_chat_active' in context.user_data:
        del context.user_data['ai_chat_active']
    
    await query.edit_message_text(
        "تم إنهاء جلسة المحادثة مع AI.\n\n"
        "العودة إلى القائمة الرئيسية:",
        reply_markup=main_keyboard()
    )

# إيقاف ملفات المستخدم
async def stop_user_files(query, context):
    user_id = query.from_user.id
    stop_user_files(user_id)
    
    await query.edit_message_text(
        "✅ تم إيقاف جميع ملفاتك النشطة.\n\n"
        "العودة إلى القائمة الرئيسية:",
        reply_markup=main_keyboard()
    )

# تشغيل الملف
async def run_file(query, context, file_name):
    user_id = query.from_user.id
    user_files = get_user_files(user_id)
    file_exists = any(file[2] == file_name for file in user_files)  # file[2] هو file_name
    
    if not file_exists:
        await query.edit_message_text(
            "⛔ الملف غير موجود أو ليس لديك صلاحية لتشغيله.",
            reply_markup=main_keyboard()
        )
        return
    
    await query.edit_message_text("⏳ جاري تشغيل الملف على Render...")
    
    success = await run_file_on_render(file_name)
    
    if success:
        await query.edit_message_text(
            "✅ تم تشغيل الملف بنجاح على Render!\n\n"
            "سيتم تشغيل الملف في الخلفية.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
            ])
        )
    else:
        await query.edit_message_text(
            "⛔ فشل في تشغيل الملف على Render. يرجى المحاولة لاحقاً.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
            ])
        )

# معالجة إجراءات المدير
async def handle_admin_actions(query, context, action):
    if action == 'ban_user':
        await query.edit_message_text("أرسل معرف المستخدم الذي تريد حظره:")
        context.user_data['admin_action'] = 'ban_user'
    elif action == 'unban_user':
        await query.edit_message_text("أرسل معرف المستخدم الذي تريد إلغاء حظره:")
        context.user_data['admin_action'] = 'unban_user'
    elif action == 'enable_points':
        global POINTS_SYSTEM
        POINTS_SYSTEM = True
        await query.edit_message_text("✅ تم تفعيل نظام النقاط.")
    elif action == 'disable_points':
        POINTS_SYSTEM = False
        await query.edit_message_text("✅ تم إيقاف نظام النقاط.")
    elif action == 'send_notification':
        await query.edit_message_text("أرسل الرسالة التي تريد إرسالها لجميع المستخدمين:")
        context.user_data['admin_action'] = 'send_notification'
    elif action == 'maintenance_mode':
        global BOT_MAINTENANCE
        BOT_MAINTENANCE = True
        await query.edit_message_text("✅ تم تفعيل وضع الصيانة.")
    elif action == 'restart_bot':
        BOT_MAINTENANCE = False
        await query.edit_message_text("✅ تم إعادة تشغيل البوت وخروجه من وضع الصيانة.")

# معالجة الرسائل النصية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # التحقق من حالة البوت
    if BOT_MAINTENANCE and user_id != ADMIN_ID:
        await update.message.reply_text("⛔ البوت تحت الصيانة حالياً. يرجى المحاولة لاحقاً.")
        return
    
    # التحقق من إجراءات المدير
    if user_id == ADMIN_ID and 'admin_action' in context.user_data:
        action = context.user_data['admin_action']
        
        if action == 'ban_user':
            try:
                target_id = int(message_text)
                ban_user(target_id)
                await update.message.reply_text(f"✅ تم حظر المستخدم {target_id}.")
                del context.user_data['admin_action']
            except ValueError:
                await update.message.reply_text("⛔ معرف المستخدم غير صحيح.")
        
        elif action == 'unban_user':
            try:
                target_id = int(message_text)
                unban_user(target_id)
                await update.message.reply_text(f"✅ تم إلغاء حظر المستخدم {target_id}.")
                del context.user_data['admin_action']
            except ValueError:
                await update.message.reply_text("⛔ معرف المستخدم غير صحيح.")
        
        elif action == 'send_notification':
            notification_id = save_notification(user_id, message_text)
            
            users = get_all_users()
            success = 0
            failed = 0
            
            for target_id in users:
                try:
                    await context.bot.send_message(target_id, f"📢 إشعار من الإدارة:\n\n{message_text}")
                    success += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to send notification to {target_id}: {e}")
            
            update_notification_stats(notification_id, success, failed)
            await update.message.reply_text(f"✅ تم إرسال الإشعار:\n\nالنجاح: {success}\nفشل: {failed}")
            del context.user_data['admin_action']
        
        return
    
    # معالجة محادثة الذكاء الاصطناعي
    if 'ai_chat_active' in context.user_data and context.user_data['ai_chat_active']:
        await handle_ai_message(update, context)
        return
    
    # معالجة إنشاء الملف من النص
    if 'awaiting_code' in context.user_data and context.user_data['awaiting_code']:
        # تحويل النص إلى ملف Python
        file_name = f"user_{user_id}_{int(datetime.now().timestamp())}.py"
        
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(message_text)
        
        # رفع الملف إلى GitHub
        github_url = await upload_to_github(file_name, user_id)
        
        if github_url:
            # حفظ المعلومات في قاعدة البيانات
            save_file(user_id, file_name, github_url)
            
            # إرسال الملف للمستخدم
            with open(file_name, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    caption="✅ تم إنشاء ملف Python من النص الذي أرسلته.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("▶️ تشغيل الملف", callback_data=f'run_file:{file_name}')],
                        [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
                    ])
                )
        else:
            await update.message.reply_text(
                "⛔ فشل في رفع الملف إلى GitHub. يرجى المحاولة لاحقاً.",
                reply_markup=main_keyboard()
            )
        
        # حذف الملف المؤقت
        if os.path.exists(file_name):
            os.remove(file_name)
        
        del context.user_data['awaiting_code']
        return
    
    # الرد الافتراضي على الرسائل النصية
    await update.message.reply_text(
        "استخدم الأزرار أدناه للتفاعل مع البوت:",
        reply_markup=main_keyboard()
    )

# معالجة رسائل الذكاء الاصطناعي
async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text
    
    try:
        # تهيئة نموذج Gemini
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        
        # استرجاع تاريخ المحادثة
        chat_history = get_ai_session(user_id)
        
        # إعداد المحادثة
        chat = model.start_chat(history=chat_history)
        
        # إرسال الرسالة والحصول على الرد
        response = chat.send_message(
            message_text,
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        ai_response = response.text
        
        # حفظ المحادثة المحدثة
        updated_history = chat.history
        save_ai_session(user_id, updated_history)
        
        await update.message.reply_text(
            f"🤖 Gemini:\n\n{ai_response}",
            reply_markup=end_chat_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in AI chat: {e}")
        await update.message.reply_text(
            "⛔ حدث خطأ أثناء التواصل مع الذكاء الاصطناعي. يرجى المحاولة لاحقاً.",
            reply_markup=end_chat_keyboard()
        )

# معالجة استلام الملفات
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # التحقق من حالة انتظار الملف
    if 'awaiting_file' not in context.user_data or not context.user_data['awaiting_file']:
        await update.message.reply_text(
            "استخدم زر 'رفع ملف' أولاً لبدء عملية الرفع.",
            reply_markup=main_keyboard()
        )
        return
    
    document = update.message.document
    file_name = document.file_name
    
    # التحقق من أن الملف بصيغة Python
    if not file_name.endswith('.py'):
        await update.message.reply_text("⛔ يرجى رفع ملف Python فقط (امتداد .py).")
        return
    
    # خصم نقطة من رصيد المستخدم
    if POINTS_SYSTEM:
        update_user_points(user_id, -1)
    
    # تنزيل الملف
    file = await context.bot.get_file(document.file_id)
    await file.download_to_drive(file_name)
    
    # رفع الملف إلى GitHub
    github_url = await upload_to_github(file_name, user_id)
    
    if github_url:
        # حفظ معلومات الملف في قاعدة البيانات
        save_file(user_id, file_name, github_url)
        
        await update.message.reply_text(
            f"✅ تم رفع الملف بنجاح!\n\n"
            f"رابط GitHub: {github_url}\n\n"
            "يمكنك الآن تشغيل الملف باستخدام الزر أدناه:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ تشغيل الملف", callback_data=f'run_file:{file_name}')],
                [InlineKeyboardButton("🔙 رجوع", callback_data='back_to_main')]
            ])
        )
    else:
        # إعادة النقطة إذا فشل الرفع
        if POINTS_SYSTEM:
            update_user_points(user_id, 1)
        
        await update.message.reply_text(
            "⛔ فشل في رفع الملف إلى GitHub. يرجى المحاولة لاحقاً.",
            reply_markup=main_keyboard()
        )
    
    # حذف الملف المحلي
    if os.path.exists(file_name):
        os.remove(file_name)
    
    del context.user_data['awaiting_file']

# رفع الملف إلى GitHub
async def upload_to_github(file_name, user_id):
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # ترميز المحتوى إلى base64
        content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        # إعداد طلب GitHub API
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_name}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # التحقق من وجود الملف مسبقاً
        response = requests.get(url, headers=headers)
        sha = None
        if response.status_code == 200:
            sha = response.json().get('sha')
        
        data = {
            "message": f"Upload {file_name} by user {user_id}",
            "content": content_b64,
            "branch": "main"
        }
        
        if sha:
            data["sha"] = sha
        
        # رفع الملف
        response = requests.put(url, headers=headers, json=data)
        
        if response.status_code in [200, 201]:
            return f"https://github.com/{GITHUB_REPO}/blob/main/{file_name}"
        else:
            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error uploading to GitHub: {e}")
        return None

# تشغيل الملف على Render
async def run_file_on_render(file_name):
    try:
        url = f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/deploys"
        headers = {
            "Authorization": f"Bearer {RENDER_TOKEN}",
            "Content-Type": "application/json"
        }
        
        data = {
            "clearCache": True
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 201:
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Render API error: {response.status} - {error_text}")
                    return False
    except Exception as e:
        logger.error(f"Error deploying to Render: {e}")
        return False

# الدالة الرئيسية
def main():
    # إعداد قاعدة البيانات
    setup_database()
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة المعالجات
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("admin", admin_command))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # بدء البوت
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
