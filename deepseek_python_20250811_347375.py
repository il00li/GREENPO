import telebot
from telebot import types
import requests
import json
from datetime import datetime
import time

# Configuration
TOKEN = "8110119856:AAEMbomUhyXXrR8Y-YvmTJR4jmDP1-y-tQo"
PIXABAY_API_KEY = "51444506-bffefcaf12816bd85a20222d1"
ICONFINDER_API_KEY = "YOUR_ICONFINDER_API_KEY"  # Replace with actual key
ADMIN_ID = 7251748706

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# Database simulation (in a real bot, use a proper database)
users_db = {}
subscription_db = {}
banned_users = set()
bot_status = True
bot_status_message = "البوت متوقف حاليًا للصيانة. نعتذر للإزعاج وسنعود قريبًا."
paid_mode = False

# Channels for mandatory subscription
REQUIRED_CHANNELS = ["@crazys7", "@AWU87"]
RESULTS_CHANNEL = "@AWU87"

# Helper functions
def is_user_subscribed(user_id):
    try:
        for channel in REQUIRED_CHANNELS:
            status = bot.get_chat_member(channel.strip("@"), user_id).status
            if status not in ["member", "administrator", "creator"]:
                return False
        return True
    except:
        return False

def get_pixabay_results(query, media_type):
    base_url = "https://pixabay.com/api/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "per_page": 50
    }
    
    if media_type == "image":
        params["image_type"] = "photo"
    elif media_type == "video":
        params["video_type"] = "all"
    
    response = requests.get(base_url, params=params)
    return response.json().get("hits", [])

def get_icons(query):
    # This is a placeholder - replace with actual IconFinder API implementation
    return [{"url": f"https://example.com/icon_{i}.png", "id": i} for i in range(1, 6)]

def get_illustrations(query):
    # This is a placeholder - replace with actual ManyPixels API implementation
    return [{"url": f"https://example.com/illustration_{i}.png", "id": i} for i in range(1, 6)]

def save_user_action(user_id, action):
    if user_id not in users_db:
        users_db[user_id] = {
            "join_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "actions": [],
            "search_count": 0,
            "download_count": 0
        }
    users_db[user_id]["actions"].append({
        "action": action,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    if action == "search":
        users_db[user_id]["search_count"] += 1
    elif action == "download":
        users_db[user_id]["download_count"] += 1

def is_admin(user_id):
    return user_id == ADMIN_ID

# Start command and subscription check
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not bot_status:
        bot.send_message(message.chat.id, bot_status_message)
        return
    
    user_id = message.from_user.id
    
    if user_id in banned_users:
        bot.send_message(message.chat.id, "⚠️ تم حظرك من استخدام البوت.")
        return
    
    if paid_mode and user_id not in subscription_db:
        bot.send_message(message.chat.id, "🔒 البوت الآن في الوضع المدفوع. يمكنك الحصول على اشتراك عن طريق دعوة 5 أعضاء أو التواصل مع المطور.")
        return
    
    save_user_action(user_id, "start")
    
    if not is_user_subscribed(user_id):
        welcome_msg = "(¬‿¬)ノ\n♨️| اشترك في القنوات للتمكن من استخدام البوت"
        keyboard = types.InlineKeyboardMarkup()
        
        for channel in REQUIRED_CHANNELS:
            keyboard.add(types.InlineKeyboardButton(text=f"اشترك في {channel}", url=f"https://t.me/{channel.strip('@')}"))
        
        keyboard.add(types.InlineKeyboardButton(text="تحقق من الاشتراك", callback_data="check_subscription"))
        
        bot.send_message(message.chat.id, welcome_msg, reply_markup=keyboard)
    else:
        show_main_menu(message.chat.id)

def show_main_menu(chat_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="✦ انقر للبحث ✦", callback_data="search_menu"))
    keyboard.add(types.InlineKeyboardButton(text="𓆩عن المطور𓆪", callback_data="about_dev"))
    keyboard.add(types.InlineKeyboardButton(text="『📊』", callback_data="stats"))
    
    bot.send_message(chat_id, "اختر من القائمة:", reply_markup=keyboard)

# Callback query handler
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    
    if not bot_status:
        bot.answer_callback_query(call.id, bot_status_message, show_alert=True)
        return
    
    if user_id in banned_users:
        bot.answer_callback_query(call.id, "⚠️ تم حظرك من استخدام البوت.", show_alert=True)
        return
    
    if paid_mode and user_id not in subscription_db:
        bot.answer_callback_query(call.id, "🔒 البوت الآن في الوضع المدفوع. يمكنك الحصول على اشتراك عن طريق دعوة 5 أعضاء أو التواصل مع المطور.", show_alert=True)
        return
    
    if call.data == "check_subscription":
        if is_user_subscribed(user_id):
            bot.answer_callback_query(call.id, "✔️ تم التحقق من اشتراكك! يمكنك الآن استخدام البوت.", show_alert=True)
            show_main_menu(call.message.chat.id)
        else:
            bot.answer_callback_query(call.id, "❌ لم يتم العثور على اشتراكك في جميع القنوات المطلوبة.", show_alert=True)
    
    elif call.data == "search_menu":
        show_search_menu(call.message.chat.id)
    
    elif call.data == "about_dev":
        show_about_dev(call.message.chat.id)
    
    elif call.data == "stats":
        show_stats(call.message.chat.id, user_id)
    
    elif call.data in ["image", "video", "icon", "illustration"]:
        msg = bot.send_message(call.message.chat.id, f"أدخل كلمة البحث للحصول على {call.data}:")
        bot.register_next_step_handler(msg, process_search_query, call.data)
    
    elif call.data.startswith("result_"):
        parts = call.data.split("_")
        media_type = parts[1]
        index = int(parts[2])
        query = parts[3]
        
        show_result(call.message.chat.id, media_type, query, index)
    
    elif call.data.startswith("download_"):
        parts = call.data.split("_")
        media_type = parts[1]
        url = parts[2]
        query = parts[3]
        
        # Send to results channel
        bot.send_message(RESULTS_CHANNEL, f"تحميل جديد:\nالنوع: {media_type}\nالكلمة: {query}\nالرابط: {url}")
        
        # Update user stats
        save_user_action(user_id, "download")
        
        # Edit original message to remove buttons
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        
        bot.send_message(call.message.chat.id, "تم التحميل بنجاح! إذا كنت تريد بحث جديد، أرسل /start")
    
    elif call.data == "back_to_main":
        show_main_menu(call.message.chat.id)
    
    # Admin functions
    elif call.data == "admin_menu":
        if is_admin(user_id):
            show_admin_menu(call.message.chat.id)
    
    elif call.data == "ban_user":
        msg = bot.send_message(call.message.chat.id, "أدخل معرف المستخدم لحظره:")
        bot.register_next_step_handler(msg, process_ban_user)
    
    elif call.data == "unban_user":
        msg = bot.send_message(call.message.chat.id, "أدخل معرف المستخدم لإلغاء حظره:")
        bot.register_next_step_handler(msg, process_unban_user)
    
    elif call.data == "toggle_paid_mode":
        toggle_paid_mode(call.message.chat.id)
    
    elif call.data == "activate_subscription":
        msg = bot.send_message(call.message.chat.id, "أدخل معرف المستخدم لتفعيل الاشتراك له:")
        bot.register_next_step_handler(msg, process_activate_subscription)
    
    elif call.data == "deactivate_subscription":
        msg = bot.send_message(call.message.chat.id, "أدخل معرف المستخدم لإلغاء اشتراكه:")
        bot.register_next_step_handler(msg, process_deactivate_subscription)
    
    elif call.data == "deactivate_all_subs":
        deactivate_all_subscriptions(call.message.chat.id)
    
    elif call.data == "toggle_bot_status":
        toggle_bot_status(call.message.chat.id)
    
    elif call.data == "set_status_message":
        msg = bot.send_message(call.message.chat.id, "أدخل الرسالة الجديدة التي تظهر عندما يكون البوت متوقفًا:")
        bot.register_next_step_handler(msg, process_status_message)

def show_search_menu(chat_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="فيديو", callback_data="video"))
    keyboard.add(types.InlineKeyboardButton(text="صور", callback_data="image"))
    keyboard.add(types.InlineKeyboardButton(text="أيقونات", callback_data="icon"))
    keyboard.add(types.InlineKeyboardButton(text="رسومات", callback_data="illustration"))
    keyboard.add(types.InlineKeyboardButton(text="رجوع", callback_data="back_to_main"))
    
    bot.send_message(chat_id, "اختر نوع البحث:", reply_markup=keyboard)

def show_about_dev(chat_id):
    about_text = """
🔧 المطوّر @Ili8_8ill

شاب يمني دخل عالم البرمجة والبوتات في تيليجرام وهو مليان شغف وحماس. بدأ يتعلّم خطوة خطوة، من الصفر، وكل يوم يزيد خبرته من خلال التجربة والمشاريع الصغيرة اللي لها فايدة حقيقية.

ما شاء الله عليه، يتميّز بـ:  
• حبّه للاستكشاف والتعلّم بنفسه  
• قدرته على بناء بوتات بسيطة تخدم الناس  
• استخدامه لأدوات مثل BotFather وPython  
• تقبّله للنقد وسعيه للتطوير المستمر


📢 القنوات اللي يشتغل فيها:  
@crazys7 – @AWU87


🌟 رؤيته:  
ماشي في طريق البرمجة من الأساسيات نحو الاحتراف، بخطوات ثابتة وطموح كبير إنه يصنع بوتات تخدم الناس وتضيف قيمة حقيقية.


📬 للتواصل:  
تابع حسابه: @Ili8_8ill
"""
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="رجوع", callback_data="back_to_main"))
    
    bot.send_message(chat_id, about_text, reply_markup=keyboard)

def show_stats(chat_id, user_id):
    total_users = len(users_db)
    total_searches = sum(user["search_count"] for user in users_db.values())
    total_downloads = sum(user["download_count"] for user in users_db.values())
    
    user_stats = users_db.get(user_id, {})
    user_searches = user_stats.get("search_count", 0)
    user_downloads = user_stats.get("download_count", 0)
    
    stats_text = f"""
📊 الإحصائيات العامة:
- عدد المستخدمين: {total_users}
- عدد عمليات البحث: {total_searches}
- عدد التحميلات: {total_downloads}

📊 إحصائياتك الخاصة:
- عمليات البحث: {user_searches}
- التحميلات: {user_downloads}
"""
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="رجوع", callback_data="back_to_main"))
    
    bot.send_message(chat_id, stats_text, reply_markup=keyboard)

def process_search_query(message, media_type):
    query = message.text
    user_id = message.from_user.id
    
    save_user_action(user_id, "search")
    
    if media_type == "image":
        results = get_pixabay_results(query, "image")
    elif media_type == "video":
        results = get_pixabay_results(query, "video")
    elif media_type == "icon":
        results = get_icons(query)
    elif media_type == "illustration":
        results = get_illustrations(query)
    
    if not results:
        bot.send_message(message.chat.id, "⚠️ لم يتم العثور على نتائج. حاول بكلمة بحث أخرى.")
        return
    
    # Store results in user's session (in a real bot, use proper session management)
    users_db[user_id]["current_results"] = results
    users_db[user_id]["current_query"] = query
    users_db[user_id]["current_media_type"] = media_type
    
    show_result(message.chat.id, media_type, query, 0)

def show_result(chat_id, media_type, query, index):
    user_id = chat_id  # Assuming chat_id is user_id in private chats
    results = users_db.get(user_id, {}).get("current_results", [])
    
    if not results or index < 0 or index >= len(results):
        bot.send_message(chat_id, "⚠️ لا توجد نتائج متاحة.")
        return
    
    item = results[index]
    url = item.get("url") or item.get("webformatURL") or item.get("videos", {}).get("medium", {}).get("url")
    
    if not url:
        bot.send_message(chat_id, "⚠️ حدث خطأ في عرض النتيجة.")
        return
    
    keyboard = types.InlineKeyboardMarkup()
    
    # Navigation buttons
    row = []
    if index > 0:
        row.append(types.InlineKeyboardButton(text="«« السابق", callback_data=f"result_{media_type}_{index-1}_{query}"))
    if index < len(results) - 1:
        row.append(types.InlineKeyboardButton(text="التالي »»", callback_data=f"result_{media_type}_{index+1}_{query}"))
    if row:
        keyboard.row(*row)
    
    # Download button
    keyboard.add(types.InlineKeyboardButton(text="◤تحميل◥", callback_data=f"download_{media_type}_{url}_{query}"))
    
    # Send media based on type
    if media_type == "video":
        bot.send_video(chat_id, url, reply_markup=keyboard)
    else:
        bot.send_photo(chat_id, url, reply_markup=keyboard)

# Admin functions
def show_admin_menu(chat_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="حظر عضو", callback_data="ban_user"))
    keyboard.add(types.InlineKeyboardButton(text="إلغاء حظر عضو", callback_data="unban_user"))
    keyboard.add(types.InlineKeyboardButton(text="تفعيل/إيقاف الوضع المدفوع", callback_data="toggle_paid_mode"))
    keyboard.add(types.InlineKeyboardButton(text="تفعيل اشتراك لعضو", callback_data="activate_subscription"))
    keyboard.add(types.InlineKeyboardButton(text="إلغاء اشتراك عضو", callback_data="deactivate_subscription"))
    keyboard.add(types.InlineKeyboardButton(text="إلغاء كل الاشتراكات", callback_data="deactivate_all_subs"))
    keyboard.add(types.InlineKeyboardButton(text="إيقاف/تشغيل البوت", callback_data="toggle_bot_status"))
    keyboard.add(types.InlineKeyboardButton(text="تغيير رسالة إيقاف البوت", callback_data="set_status_message"))
    
    bot.send_message(chat_id, "👨‍💻 قائمة المدير:", reply_markup=keyboard)

def process_ban_user(message):
    try:
        user_id = int(message.text)
        banned_users.add(user_id)
        bot.send_message(message.chat.id, f"✅ تم حظر المستخدم {user_id} بنجاح.")
    except:
        bot.send_message(message.chat.id, "❌ خطأ في معرف المستخدم. يجب أن يكون رقمًا.")

def process_unban_user(message):
    try:
        user_id = int(message.text)
        if user_id in banned_users:
            banned_users.remove(user_id)
            bot.send_message(message.chat.id, f"✅ تم إلغاء حظر المستخدم {user_id} بنجاح.")
        else:
            bot.send_message(message.chat.id, f"❌ المستخدم {user_id} غير محظور.")
    except:
        bot.send_message(message.chat.id, "❌ خطأ في معرف المستخدم. يجب أن يكون رقمًا.")

def toggle_paid_mode(chat_id):
    global paid_mode
    paid_mode = not paid_mode
    status = "مفعّل" if paid_mode else "معطّل"
    bot.send_message(chat_id, f"✅ تم {status} الوضع المدفوع.")

def process_activate_subscription(message):
    try:
        user_id = int(message.text)
        subscription_db[user_id] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot.send_message(message.chat.id, f"✅ تم تفعيل الاشتراك للمستخدم {user_id}.")
    except:
        bot.send_message(message.chat.id, "❌ خطأ في معرف المستخدم. يجب أن يكون رقمًا.")

def process_deactivate_subscription(message):
    try:
        user_id = int(message.text)
        if user_id in subscription_db:
            del subscription_db[user_id]
            bot.send_message(message.chat.id, f"✅ تم إلغاء اشتراك المستخدم {user_id}.")
        else:
            bot.send_message(message.chat.id, f"❌ المستخدم {user_id} ليس لديه اشتراك مفعّل.")
    except:
        bot.send_message(message.chat.id, "❌ خطأ في معرف المستخدم. يجب أن يكون رقمًا.")

def deactivate_all_subscriptions(chat_id):
    subscription_db.clear()
    bot.send_message(chat_id, "✅ تم إلغاء كل الاشتراكات.")

def toggle_bot_status(chat_id):
    global bot_status
    bot_status = not bot_status
    status = "متوقف" if not bot_status else "يعمل"
    bot.send_message(chat_id, f"✅ تم تغيير حالة البوت إلى: {status}")

def process_status_message(message):
    global bot_status_message
    bot_status_message = message.text
    bot.send_message(message.chat.id, "✅ تم تحديث رسالة إيقاف البوت.")

# Admin command
@bot.message_handler(commands=['admin'])
def admin_command(message):
    if is_admin(message.from_user.id):
        show_admin_menu(message.chat.id)

# Start the bot
print("Bot is running...")
bot.infinity_polling()