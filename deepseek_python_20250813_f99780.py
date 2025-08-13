import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
import os
import time

# تهيئة البيانات الأساسية
TOKEN = "8110119856:AAEMbomUhyXXrR8Y-YvmTJR4jmDP1-y-tQo"
MANAGER_ID = 7251748706
CHANNELS = ["@crazys7", "@AWU87"]
ICONSCOUT_API_KEY = "8dl0PoAXaQD2t0mjPwdfjUQ02DRLJGej"
UPLOAD_CHANNEL = "@AWU87"

# ملف لحفظ البيانات
DATA_FILE = "bot_data.json"

# تهيئة البيانات الافتراضية
default_data = {
    "users": [],
    "banned": [],
    "search_count": 0,
    "download_count": 0,
    "active_users": set(),
    "bot_active": True,
    "stop_message": "البوت متوقف حاليًا. يرجى المحاولة لاحقًا.",
    "paid_mode": False,
    "paid_users": []
}

# تحميل البيانات أو إنشاء جديدة
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
            # تحويل القوائم إلى مجموعات عند الحاجة
            data['active_users'] = set(data.get('active_users', []))
            return data
    return default_data.copy()

def save_data(data):
    # تحويل المجموعات إلى قوائم قبل الحفظ
    data_to_save = data.copy()
    data_to_save['active_users'] = list(data['active_users'])
    with open(DATA_FILE, 'w') as f:
        json.dump(data_to_save, f)

# تهيئة البوت
bot = telebot.TeleBot(TOKEN)
bot_data = load_data()

# ============ وظائف المساعدة ============
def is_subscribed(user_id):
    try:
        for channel in CHANNELS:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False

def notify_admin(user):
    try:
        msg = f"👤 مستخدم جديد:\nالاسم: {user.first_name}\nالمعرف: @{user.username}"
        bot.send_message(MANAGER_ID, msg)
    except Exception as e:
        print(f"Error notifying admin: {e}")

def search_iconscout(query, asset_type):
    url = "https://api.iconscout.com/v3/search"
    headers = {"Authorization": f"Bearer {ICONSCOUT_API_KEY}"}
    params = {
        "query": query,
        "product": "illustrations" if asset_type == "illustrations" else "icons",
        "per_page": 30
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('response', {}).get('items', [])
    except Exception as e:
        print(f"Search error: {e}")
        return []

# ============ لوحات المفاتيح ============
def subscription_keyboard():
    markup = InlineKeyboardMarkup()
    for channel in CHANNELS:
        markup.add(InlineKeyboardButton(f"✅ {channel}", url=f"https://t.me/{channel[1:]}"))
    markup.add(InlineKeyboardButton("🔍 تحقق", callback_data="check_subscription"))
    return markup

def main_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✦ انقر للبحث ✦", callback_data="search_menu"))
    markup.add(InlineKeyboardButton("『📊』الإحصائيات", callback_data="stats"))
    return markup

def search_menu_keyboard():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎨 رسومات توضيحية", callback_data="search_illustrations"))
    markup.add(InlineKeyboardButton("🧩 أيقونات", callback_data="search_icons"))
    return markup

def result_navigation_keyboard(current_index, total, asset_id):
    markup = InlineKeyboardMarkup()
    row = []
    if current_index > 0:
        row.append(InlineKeyboardButton("««", callback_data=f"prev_{current_index-1}"))
    if current_index < total - 1:
        row.append(InlineKeyboardButton("»»", callback_data=f"next_{current_index+1}"))
    if row:
        markup.row(*row)
    markup.add(InlineKeyboardButton("◤تحميل◥", callback_data=f"download_{asset_id}"))
    return markup

def admin_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🚫 حظر عضو", callback_data="ban_user"),
        InlineKeyboardButton("✅ إلغاء الحظر", callback_data="unban_user"),
        InlineKeyboardButton("🔄 تحويل إلى مدفوع", callback_data="set_paid"),
        InlineKeyboardButton("⛔ إيقاف الاشتراك عن الجميع", callback_data="disable_paid"),
        InlineKeyboardButton("🛑 إيقاف البوت", callback_data="stop_bot"),
        InlineKeyboardButton("🔄 تشغيل البوت", callback_data="start_bot"),
        InlineKeyboardButton("⚙️ إعدادات خاصة", callback_data="settings_menu")
    ]
    markup.add(*buttons)
    return markup

def settings_keyboard():
    markup = InlineKeyboardMarkup()
    buttons = [
        InlineKeyboardButton("حالة البوت", callback_data="bot_status"),
        InlineKeyboardButton("عدد المحظورين", callback_data="banned_count"),
        InlineKeyboardButton("حالة الوضع المدفوع", callback_data="paid_status"),
        InlineKeyboardButton("رسالة التوقف", callback_data="stop_message")
    ]
    for btn in buttons:
        markup.add(btn)
    return markup

# ============ معالجة الأوامر ============
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    # التحقق من حالة البوت
    if not bot_data['bot_active']:
        bot.reply_to(message, bot_data['stop_message'])
        return
    
    # التحقق من الحظر
    if user_id in bot_data['banned']:
        bot.reply_to(message, "❌ تم حظرك من استخدام البوت.")
        return
    
    # تسجيل المستخدم
    if user_id not in bot_data['users']:
        bot_data['users'].append(user_id)
        save_data(bot_data)
    
    # التحقق من الاشتراك
    if is_subscribed(user_id):
        bot.send_message(
            user_id,
            "مرحبًا بك! اختر أحد الخيارات:",
            reply_markup=main_keyboard()
        )
        # إضافة إلى المستخدمين النشطين
        bot_data['active_users'].add(user_id)
        save_data(bot_data)
        # إشعار المدير
        notify_admin(message.from_user)
    else:
        bot.send_message(
            user_id,
            "(¬‿¬)ノ\n♨️| اشترك في القنوات للتمكن من استخدام البوت",
            reply_markup=subscription_keyboard()
        )

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id == MANAGER_ID:
        bot.send_message(
            message.chat.id,
            "لوحة إدارة البوت:",
            reply_markup=admin_keyboard()
        )

# ============ معالجة الكواليس ============
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    # التحقق الأساسي
    if not bot_data['bot_active']:
        bot.answer_callback_query(call.id, bot_data['stop_message'], show_alert=True)
        return
        
    if user_id in bot_data['banned']:
        bot.answer_callback_query(call.id, "❌ تم حظرك من استخدام البوت.", show_alert=True)
        return
    
    # التحقق من الاشتراك
    if not is_subscribed(user_id) and not data.startswith(('check_', 'prev_', 'next_', 'download_')):
        bot.answer_callback_query(call.id, "❌ يجب الاشتراك في القنوات أولاً!", show_alert=True)
        return
    
    # معالجة الكواليس
    if data == "check_subscription":
        if is_subscribed(user_id):
            bot.edit_message_text(
                chat_id=user_id,
                message_id=call.message.message_id,
                text="مرحبًا بك! اختر أحد الخيارات:",
                reply_markup=main_keyboard()
            )
            bot_data['active_users'].add(user_id)
            save_data(bot_data)
            notify_admin(call.from_user)
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك في جميع القنوات بعد!", show_alert=True)
    
    elif data == "search_menu":
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text="اختر نوع الوسائط:",
            reply_markup=search_menu_keyboard()
        )
    
    elif data == "stats":
        stats_text = (
            f"📊 إحصائيات البوت:\n\n"
            f"👥 المستخدمون الإجماليون: {len(bot_data['users'])}\n"
            f"🔍 عمليات البحث: {bot_data['search_count']}\n"
            f"📥 التحميلات: {bot_data['download_count']}\n"
            f"👤 المشتركون النشطون: {len(bot_data['active_users'])}"
        )
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=stats_text
        )
    
    elif data.startswith("search_"):
        asset_type = data.split('_')[1]
        msg = bot.send_message(user_id, "أرسل كلمة البحث:")
        bot.register_next_step_handler(msg, process_search, asset_type)
    
    elif data.startswith(("prev_", "next_")):
        direction, index = data.split('_')
        show_result(user_id, call.message.message_id, int(index))
    
    elif data.startswith("download_"):
        asset_id = data.split('_')[1]
        download_asset(user_id, call.message, asset_id)
    
    # إدارة البوت
    elif data == "ban_user":
        msg = bot.send_message(user_id, "أرسل ID المستخدم لحظره:")
        bot.register_next_step_handler(msg, ban_user)
    
    elif data == "unban_user":
        msg = bot.send_message(user_id, "أرسل ID المستخدم لإلغاء حظره:")
        bot.register_next_step_handler(msg, unban_user)
    
    elif data == "settings_menu":
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text="الإعدادات الخاصة:",
            reply_markup=settings_keyboard()
        )
    
    elif data == "bot_status":
        status = "🟢 نشط" if bot_data['bot_active'] else "🔴 متوقف"
        bot.answer_callback_query(call.id, f"حالة البوت: {status}")
    
    elif data == "banned_count":
        count = len(bot_data['banned'])
        bot.answer_callback_query(call.id, f"عدد المحظورين: {count}")
    
    elif data == "paid_status":
        status = "🟢 مفعل" if bot_data['paid_mode'] else "🔴 معطل"
        bot.answer_callback_query(call.id, f"الوضع المدفوع: {status}")

# ============ وظائف البحث والنتائج ============
def process_search(message, asset_type):
    user_id = message.from_user.id
    query = message.text
    
    # زيادة عداد البحث
    bot_data['search_count'] += 1
    save_data(bot_data)
    
    # البحث في IconScout
    results = search_iconscout(query, asset_type)
    
    if not results:
        bot.send_message(user_id, "⚠️ لم يتم العثور على نتائج")
        return
    
    # حفظ النتائج مؤقتاً
    if not hasattr(bot, 'user_results'):
        bot.user_results = {}
    bot.user_results[user_id] = results
    
    # عرض أول نتيجة
    show_result(user_id, message.message_id + 1, 0)

def show_result(user_id, message_id, index):
    results = bot.user_results.get(user_id, [])
    
    if not results or index < 0 or index >= len(results):
        bot.send_message(user_id, "❌ خطأ في عرض النتائج")
        return
    
    asset = results[index]
    caption = asset.get('name', '')
    image_url = asset.get('urls', {}).get('raw', '') or asset.get('thumbnails', {}).get('large', '')
    
    if not image_url:
        bot.send_message(user_id, "❌ لا يمكن تحميل الصورة")
        return
    
    try:
        # إرسال الصورة مع أزرار التنقل
        bot.send_photo(
            chat_id=user_id,
            photo=image_url,
            caption=caption,
            reply_markup=result_navigation_keyboard(index, len(results), asset['id'])
        )
        # حذف الرسالة السابقة
        bot.delete_message(user_id, message_id)
    except Exception as e:
        print(f"Error sending photo: {e}")
        bot.send_message(user_id, "❌ حدث خطأ أثناء عرض النتائج")

def download_asset(user_id, message, asset_id):
    results = bot.user_results.get(user_id, [])
    asset = next((a for a in results if a['id'] == asset_id), None)
    
    if not asset:
        bot.answer_callback_query(message.id, "❌ لم يتم العثور على الأصل")
        return
    
    # زيادة عداد التحميل
    bot_data['download_count'] += 1
    save_data(bot_data)
    
    # إرسال إلى القناة
    try:
        image_url = asset.get('urls', {}).get('raw', '') or asset.get('thumbnails', {}).get('large', '')
        caption = f"تحميل بواسطة: @{message.from_user.username}\n\n{asset.get('name', '')}"
        
        # إرسال إلى القناة
        bot.send_photo(
            chat_id=UPLOAD_CHANNEL,
            photo=image_url,
            caption=caption
        )
        
        # تحديث واجهة المستخدم
        bot.edit_message_reply_markup(
            chat_id=user_id,
            message_id=message.message_id,
            reply_markup=None
        )
        bot.answer_callback_query(message.id, "✅ تم التحميل بنجاح! أرسل /start للبحث مجدداً")
    except Exception as e:
        print(f"Error uploading: {e}")
        bot.answer_callback_query(message.id, "❌ فشل التحميل")

# ============ وظائف الإدارة ============
def ban_user(message):
    try:
        user_id = int(message.text)
        if user_id not in bot_data['banned']:
            bot_data['banned'].append(user_id)
            save_data(bot_data)
            bot.reply_to(message, f"✅ تم حظر المستخدم {user_id}")
        else:
            bot.reply_to(message, "❌ المستخدم محظور بالفعل")
    except ValueError:
        bot.reply_to(message, "❌ ID غير صالح")

def unban_user(message):
    try:
        user_id = int(message.text)
        if user_id in bot_data['banned']:
            bot_data['banned'].remove(user_id)
            save_data(bot_data)
            bot.reply_to(message, f"✅ تم إلغاء حظر المستخدم {user_id}")
        else:
            bot.reply_to(message, "❌ المستخدم غير محظور")
    except ValueError:
        bot.reply_to(message, "❌ ID غير صالح")

# ============ تشغيل البوت ============
if __name__ == "__main__":
    print("Bot is running...")
    while True:
        try:
            bot.polling(none_stop=True, interval=3)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)