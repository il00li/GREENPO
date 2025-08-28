from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import (
    FloodWait, UserPrivacyRestricted, PeerIdInvalid,
    ChannelInvalid, ChannelPrivate, UserNotParticipant,
    SessionPasswordNeeded, PhoneCodeInvalid, UsernameNotOccupied,
    UsernameInvalid, ChatAdminRequired, UserAlreadyParticipant
)
import asyncio
import sqlite3
import re
from datetime import datetime, date

# بيانات الحساب
API_ID = 23656977
API_HASH = "49d3f43531a92b3f5bc403766313ca1e"
BOT_TOKEN = "8300609210:AAGHCu5Un2UDMEnxy4Oh-QCY1_kVDm3S6Ro"

# إعدادات المدير
ADMIN_ID = 6689435577  # ضع رقمك هنا

# تهيئة العميل
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# حالة المستخدمين
user_states = {}
user_data = {}

# قاعدة البيانات
def init_db():
    conn = sqlite3.connect('bot_data.db')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, 
        value TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS stats (
        date TEXT PRIMARY KEY, 
        added INTEGER DEFAULT 0, 
        failed INTEGER DEFAULT 0
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY,
        title TEXT,
        username TEXT
    )''')
    
    # الإعدادات الافتراضية
    defaults = [
        ('daily_limit', '50'),
        ('delay', '30'),
        ('source_group', ''),
        ('target_group', '')
    ]
    cur.executemany("INSERT OR IGNORE INTO settings VALUES (?, ?)", defaults)
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect('bot_data.db')
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else None

def update_setting(key, value):
    conn = sqlite3.connect('bot_data.db')
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def update_stats(added=0, failed=0):
    today = str(date.today())
    conn = sqlite3.connect('bot_data.db')
    cur = conn.cursor()
    cur.execute("UPDATE stats SET added = added + ?, failed = failed + ? WHERE date=?", (added, failed, today))
    if cur.rowcount == 0:
        cur.execute("INSERT INTO stats VALUES (?, ?, ?)", (today, added, failed))
    conn.commit()
    conn.close()

def get_today_stats():
    today = str(date.today())
    conn = sqlite3.connect('bot_data.db')
    cur = conn.cursor()
    cur.execute("SELECT added, failed FROM stats WHERE date=?", (today,))
    result = cur.fetchone()
    conn.close()
    return result or (0, 0)

def save_group(chat_id, title, username):
    conn = sqlite3.connect('bot_data.db')
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO groups VALUES (?, ?, ?)", (chat_id, title, username))
    conn.commit()
    conn.close()

def get_group(chat_id):
    conn = sqlite3.connect('bot_data.db')
    cur = conn.cursor()
    cur.execute("SELECT title, username FROM groups WHERE id=?", (chat_id,))
    result = cur.fetchone()
    conn.close()
    return result

# لوحة التحكم
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🌍 وضع المستخدمين", callback_data="mode"),
         InlineKeyboardButton("🛠 الإعدادات", callback_data="settings")],
        [InlineKeyboardButton("📊 التحقق من الحالة", callback_data="status"),
         InlineKeyboardButton("🚀 إضافة أعضاء", callback_data="start_add")],
        [InlineKeyboardButton("📈 إحصائية اليوم", callback_data="stats"),
         InlineKeyboardButton("🗑 مسح الإحصائية", callback_data="clear_stats")],
        [InlineKeyboardButton("❓ المساعدة", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def settings_keyboard():
    daily_limit = get_setting('daily_limit')
    delay = get_setting('delay')
    source_group = get_setting('source_group')
    target_group = get_setting('target_group')
    
    source_title = "غير محدد"
    target_title = "غير محدد"
    
    if source_group:
        group_info = get_group(int(source_group))
        if group_info:
            source_title = group_info[0] or group_info[1] or source_group
    
    if target_group:
        group_info = get_group(int(target_group))
        if group_info:
            target_title = group_info[0] or group_info[1] or target_group
    
    keyboard = [
        [InlineKeyboardButton(f"🌗 الحد اليومي: {daily_limit}", callback_data="set_daily_limit")],
        [InlineKeyboardButton(f"🌘 وقت التأخير: {delay} ثانية", callback_data="set_delay")],
        [InlineKeyboardButton(f"🌑 مجموعة المصدر: {source_title[:20]}", callback_data="set_source_group")],
        [InlineKeyboardButton(f"🌒 مجموعة الهدف: {target_title[:20]}", callback_data="set_target_group")],
        [InlineKeyboardButton("🔙 الرجوع", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def confirm_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ تأكيد", callback_data="confirm_add")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔙 الرجوع", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# معالجة الأوامر
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("⛔ ليس لديك صلاحية استخدام هذا البوت")
        return
        
    init_db()
    await message.reply_text(
        "🌍 مرحباً! أنا بوت مساعد لإدارة الأعضاء\n\n"
        "🚀 اختر من الأزرار أدناه:",
        reply_markup=main_keyboard()
    )

@app.on_message(filters.command("id") & filters.private)
async def get_id_command(client, message):
    if message.from_user.id != ADMIN_ID:
        return
        
    chat_id = message.chat.id
    reply = message.reply_to_message
    if reply and reply.forward_from_chat:
        chat_id = reply.forward_from_chat.id
        title = reply.forward_from_chat.title
        await message.reply_text(f"🌐 مجموعة: {title}\n🆔 المعرف: `{chat_id}`")
    else:
        await message.reply_text(f"🆔 معرف هذه الدردشة: `{chat_id}`")

# معالجة الأزرار
@app.on_callback_query()
async def handle_callback(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id != ADMIN_ID:
        await callback_query.answer("⛔ ليس لديك صلاحية")
        return

    data = callback_query.data
    
    if data == "settings":
        await callback_query.edit_message_text("🛠 الإعدادات:", reply_markup=settings_keyboard())
    
    elif data == "start_add":
        added, failed = get_today_stats()
        daily_limit = int(get_setting('daily_limit'))
        
        if added >= daily_limit:
            await callback_query.answer(f"⚡ وصلت للحد اليومي ({daily_limit})", show_alert=True)
            return
            
        source_group = get_setting('source_group')
        target_group = get_setting('target_group')
        
        if not source_group or not target_group:
            await callback_query.answer("❌ يرجى تحديد مجموعة المصدر والهدف أولاً", show_alert=True)
            return
            
        source_info = get_group(int(source_group))
        target_info = get_group(int(target_group))
        
        source_name = source_info[0] if source_info else source_group
        target_name = target_info[0] if target_info else target_group
        
        await callback_query.edit_message_text(
            f"**🚀 معلومات الإضافة:**\n\n"
            f"🌗 الحد اليومي: `{daily_limit}`\n"
            f"📊 المضاف اليوم: `{added}`\n"
            f"🌘 المتبقي: `{daily_limit - added}`\n\n"
            f"🌑 المصدر: `{source_name}`\n"
            f"🌒 الهدف: `{target_name}`\n\n"
            "هل تريد البدء في الإضافة؟",
            reply_markup=confirm_keyboard()
        )
    
    elif data == "confirm_add":
        await callback_query.edit_message_text("🌕 جاري البدء في عملية الإضافة...")
        await add_members_process(callback_query.message)
    
    elif data == "status":
        added, failed = get_today_stats()
        daily_limit = int(get_setting('daily_limit'))
        await callback_query.answer(f"📊 المضاف: {added}/{daily_limit}\n❌ الفاشل: {failed}", show_alert=True)
    
    elif data == "stats":
        added, failed = get_today_stats()
        daily_limit = int(get_setting('daily_limit'))
        await callback_query.edit_message_text(
            f"**📈 إحصائية اليوم:**\n\n"
            f"✅ النجاح: `{added}`\n"
            f"❌ الفشل: `{failed}`\n"
            f"🌗 الحد اليومي: `{daily_limit}`\n"
            f"🌘 المتبقي: `{daily_limit - added}`",
            reply_markup=main_keyboard()
        )
    
    elif data == "clear_stats":
        update_stats(added=-get_today_stats()[0], failed=-get_today_stats()[1])
        await callback_query.answer("🗑 تم مسح الإحصائية", show_alert=True)
        await callback_query.edit_message_text(
            "✅ تم مسح إحصائية اليوم",
            reply_markup=main_keyboard()
        )
    
    elif data == "back_main":
        if user_id in user_states:
            del user_states[user_id]
        await callback_query.edit_message_text(
            "🌍 القائمة الرئيسية:",
            reply_markup=main_keyboard()
        )
    
    elif data == "help":
        help_text = """
        **❓ دليل الاستخدام:**

        🌍 وضع المستخدمين - تحديد مصدر المستخدمين
        🛠 الإعدادات - ضبط إعدادات البوت
        📊 التحقق - معرفة الحالة الحالية
        🚀 الإضافة - بدء عملية إضافة الأعضاء
        📈 الإحصائية - عرض إحصائيات اليوم
        🗑 مسح الإحصائية - مسح إحصائية اليوم
        ❓ المساعدة - عرض هذه الرسالة

        **🌐 كيفية الحصول على معرف مجموعة:**
        1. أضف البوت إلى المجموعة
        2. أعط البوت صلاحية المشرف
        3. أرسل /id في المجموعة
        4. أو أعد توجيه رسالة من المجموعة إلى البوت
        """
        await callback_query.edit_message_text(help_text, reply_markup=main_keyboard())
    
    elif data.startswith("set_"):
        setting_type = data.split("_", 1)[1]
        user_states[user_id] = f"set_{setting_type}"
        
        if setting_type == "daily_limit":
            await callback_query.edit_message_text(
                "🌗 أرسل الحد اليومي الجديد (رقم):",
                reply_markup=back_keyboard()
            )
        elif setting_type == "delay":
            await callback_query.edit_message_text(
                "🌘 أرسل وقت التأخير الجديد بالثواني (رقم):",
                reply_markup=back_keyboard()
            )
        elif setting_type == "source_group":
            await callback_query.edit_message_text(
                "🌑 أرسل معرف مجموعة المصدر:\n\n"
                "🌐 يمكنك استخدام:\n"
                "• معرف المجموعة الرقمي (مثل -1001234567890)\n"
                "• معرف المجموعة (مثل @groupname)\n"
                "• أعد توجيه رسالة من المجموعة",
                reply_markup=back_keyboard()
            )
        elif setting_type == "target_group":
            await callback_query.edit_message_text(
                "🌒 أرسل معرف مجموعة الهدف:\n\n"
                "🌐 يمكنك استخدام:\n"
                "• معرف المجموعة الرقمي (مثل -1001234567890)\n"
                "• معرف المجموعة (مثل @groupname)\n"
                "• أعد توجيه رسالة من المجموعة",
                reply_markup=back_keyboard()
            )
    
    await callback_query.answer()

# معالجة الرسائل
@app.on_message(filters.private & filters.text & filters.user(ADMIN_ID))
async def handle_messages(client, message):
    user_id = message.from_user.id
    text = message.text
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    try:
        if state == "set_daily_limit":
            if text.isdigit():
                limit = int(text)
                if limit < 1 or limit > 200:
                    await message.reply_text("❌ الحد اليومي يجب أن يكون بين 1 و 200", reply_markup=back_keyboard())
                    return
                
                update_setting('daily_limit', text)
                del user_states[user_id]
                await message.reply_text(f"✅ تم تحديث الحد اليومي إلى {text}", reply_markup=main_keyboard())
            else:
                await message.reply_text("❌ يرجى إرسال رقم صحيح", reply_markup=back_keyboard())
        
        elif state == "set_delay":
            if text.isdigit():
                delay = int(text)
                if delay < 1 or delay > 300:
                    await message.reply_text("❌ وقت التأخير يجب أن يكون بين 1 و 300 ثانية", reply_markup=back_keyboard())
                    return
                
                update_setting('delay', text)
                del user_states[user_id]
                await message.reply_text(f"✅ تم تحديث وقت التأخير إلى {text} ثانية", reply_markup=main_keyboard())
            else:
                await message.reply_text("❌ يرجى إرسال رقم صحيح", reply_markup=back_keyboard())
        
        elif state in ["set_source_group", "set_target_group"]:
            chat_id = None
            chat_title = None
            
            # محاولة الحصول على المعرف من الرسالة
            if text.startswith('-100') and text[1:].isdigit():
                chat_id = int(text)
            elif text.startswith('@'):
                try:
                    chat = await client.get_chat(text)
                    chat_id = chat.id
                    chat_title = chat.title
                except (UsernameNotOccupied, UsernameInvalid, PeerIdInvalid):
                    await message.reply_text("❌ معرف المجموعة غير صحيح", reply_markup=back_keyboard())
                    return
            
            if chat_id is None:
                await message.reply_text("❌ يرجى إرسال معرف مجموعة صحيح", reply_markup=back_keyboard())
                return
            
            # حفظ المجموعة في قاعدة البيانات
            if chat_title:
                save_group(chat_id, chat_title, text if text.startswith('@') else None)
            
            # تحديث الإعداد
            setting_key = 'source_group' if state == 'set_source_group' else 'target_group'
            update_setting(setting_key, str(chat_id))
            
            del user_states[user_id]
            setting_name = "المصدر" if state == 'set_source_group' else "الهدف"
            await message.reply_text(f"✅ تم تحديث مجموعة {setting_name} إلى {chat_title or chat_id}", reply_markup=main_keyboard())
    
    except Exception as e:
        await message.reply_text(f"❌ حدث خطأ: {str(e)}", reply_markup=back_keyboard())

# معالجة الرسائل المُعاد توجيهها
@app.on_message(filters.private & filters.forwarded & filters.user(ADMIN_ID))
async def handle_forwarded_messages(client, message):
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if not message.forward_from_chat:
        await message.reply_text("❌ يرجى إعادة توجيه رسالة من مجموعة صحيحة", reply_markup=back_keyboard())
        return
    
    chat = message.forward_from_chat
    if chat.type not in ["group", "supergroup", "channel"]:
        await message.reply_text("❌ يرجى إعادة توجيه رسالة من مجموعة أو قناة", reply_markup=back_keyboard())
        return
    
    try:
        # حفظ المجموعة في قاعدة البيانات
        save_group(chat.id, chat.title, chat.username)
        
        # تحديث الإعداد
        if state == "set_source_group":
            update_setting('source_group', str(chat.id))
            setting_name = "المصدر"
        elif state == "set_target_group":
            update_setting('target_group', str(chat.id))
            setting_name = "الهدف"
        else:
            return
        
        del user_states[user_id]
        await message.reply_text(f"✅ تم تحديث مجموعة {setting_name} إلى {chat.title}", reply_markup=main_keyboard())
    
    except Exception as e:
        await message.reply_text(f"❌ حدث خطأ: {str(e)}", reply_markup=back_keyboard())

# عملية الإضافة
async def add_members_process(message):
    try:
        source_id = get_setting('source_group')
        target_id = get_setting('target_group')
        delay = int(get_setting('delay'))
        daily_limit = int(get_setting('daily_limit'))
        
        if not source_id or not target_id:
            await message.edit_text("❌ يرجى تحديد مجموعة المصدر والهدف أولاً", reply_markup=main_keyboard())
            return
        
        added_today, failed_today = get_today_stats()
        remaining = daily_limit - added_today
        
        if remaining <= 0:
            await message.edit_text("⚡ وصلت للحد اليومي", reply_markup=main_keyboard())
            return
        
        # جلب الأعضاء من مجموعة المصدر
        await message.edit_text("🌑 جاري جلب الأعضاء من مجموعة المصدر...")
        
        members = []
        try:
            async for member in app.get_chat_members(int(source_id)):
                if not member.user.is_bot and member.user.status not in ["left", "kicked", "restricted"]:
                    members.append(member.user)
                    if len(members) >= remaining:  # لا تتجاوز الحد اليومي
                        break
        except (ChatAdminRequired, ChannelPrivate, ChannelInvalid):
            await message.edit_text("❌ ليس لدي صلاحية لجلب الأعضاء من مجموعة المصدر", reply_markup=main_keyboard())
            return
        
        if not members:
            await message.edit_text("❌ لم أجد أعضاء في مجموعة المصدر", reply_markup=main_keyboard())
            return
        
        # بدء عملية الإضافة
        success = 0
        failed = 0
        
        for i, user in enumerate(members):
            if success >= remaining:
                break
                
            try:
                # محاولة إضافة العضو
                await app.add_chat_members(int(target_id), user.id)
                success += 1
                update_stats(added=1)
                
                # تحديث الرسالة كل 5 أعضاء
                if i % 5 == 0:
                    await message.edit_text(
                        f"**🚀 جاري الإضافة...**\n\n"
                        f"✅ النجاح: `{success}`\n"
                        f"❌ الفشل: `{failed}`\n"
                        f"🌗 المتبقي: `{remaining - success}`\n\n"
                        f"🌘 التأخير: `{delay}` ثانية"
                    )
                
                await asyncio.sleep(delay)
                
            except UserPrivacyRestricted:
                failed += 1
                update_stats(failed=1)
            except UserAlreadyParticipant:
                # العضو موجود بالفعل، لا نحتاج إلى إضافته
                pass
            except FloodWait as e:
                await message.edit_text(f"⏳ تم حظر البوت من الإضافة لمدة {e.value} ثانية. جاري الانتظار...")
                await asyncio.sleep(e.value)
            except Exception as e:
                failed += 1
                update_stats(failed=1)
        
        # تقرير النتائج
        await message.edit_text(
            f"**🎉 تم الانتهاء**\n\n"
            f"✅ النجاح: `{success}`\n"
            f"❌ الفشل: `{failed}`\n"
            f"🌗 المضاف اليوم: `{added_today + success}`\n"
            f"🌘 المتبقي اليوم: `{daily_limit - (added_today + success)}`",
            reply_markup=main_keyboard()
        )
        
    except Exception as e:
        await message.edit_text(f"❌ حدث خطأ غير متوقع: {str(e)}", reply_markup=main_keyboard())

# التشغيل الرئيسي
if __name__ == "__main__":
    print("🔥 البوت يعمل...")
    app.run()
    idle()
