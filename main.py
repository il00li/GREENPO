import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import json
from flask import Flask, request
import os
import time
from urllib.parse import quote

app = Flask(__name__)

# تكوين البوت
TOKEN = "8110119856:AAFncvfDROX9zMk6QNBl1n-l5hX62zowAw4"
ADMIN_ID = 7251748706
CHANNELS = ["@crazys7", "@AWU87"]
LUMMI_API_KEY = "lummi-b06d12ba02329efb74404de07e20b434aff295de34419f35c56eb3e200f05a71"
WEBHOOK_URL = "https://greenpo.onrender.com/webhook"

bot = telebot.TeleBot(TOKEN)

# تخزين البيانات
users_data = {}
search_results = {}
bot_status = "active"
paid_mode = False
stop_message = "البوت متوقف حاليًا للصيانة. الرجاء المحاولة لاحقًا."

# تخزين حالات المستخدمين
user_states = {}

# وظائف مساعدة
def check_subscription(user_id):
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except Exception as e:
            print(f"Error checking subscription: {e}")
            return False
    return True

def lummi_search(search_type, query):
    url = "https://api.lummi.ai/api/v1/search"
    headers = {
        "Authorization": f"Bearer {LUMMI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # بناء الاستعلام بشكل صحيح
    type_map = {
        "Illustrations": "type:illustration",
        "3D Models": "type:3d_model",
        "Styles": "type:style"
    }
    
    full_query = f"{type_map.get(search_type, '')} AND {query}" if query else type_map.get(search_type, '')
    
    payload = {
        "query": full_query,
        "page": 1,
        "per_page": 10
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get("hits", [])
        else:
            print(f"Lummi API error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Lummi search exception: {e}")
        return []

def create_main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("✦ انقر للبحث ✦", callback_data="search_menu"),
        InlineKeyboardButton("𓆩عن المطور𓆪", callback_data="about_dev"),
        InlineKeyboardButton("『📊』الإحصائيات", callback_data="stats")
    )
    if ADMIN_ID == 7251748706:
        markup.add(InlineKeyboardButton("👨‍💼 لوحة الإدارة", callback_data="admin_panel"))
    return markup

def create_search_menu():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🎨 رسومات توضيحية", callback_data="search_Illustrations"),
        InlineKeyboardButton("🧊 نماذج ثلاثية الأبعاد", callback_data="search_3D Models"),
        InlineKeyboardButton("🖌️ أنماط مرئية مخصصة", callback_data="search_Styles")
    )
    return markup

def create_results_nav(user_id, index):
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton("««", callback_data=f"prev_{user_id}_{index}"),
        InlineKeyboardButton("◤تحميل◥", callback_data=f"download_{user_id}_{index}"),
        InlineKeyboardButton("»»", callback_data=f"next_{user_id}_{index}")
    )
    return markup

def create_admin_panel():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🚫 حظر عضو", callback_data="ban_member"),
        InlineKeyboardButton("✅ إلغاء الحظر", callback_data="unban_member"),
        InlineKeyboardButton("🔄 تحويل إلى مدفوع", callback_data="toggle_paid"),
        InlineKeyboardButton("⛔ إيقاف الاشتراك عن الجميع", callback_data="disable_all_subs"),
        InlineKeyboardButton("🛑 إيقاف البوت", callback_data="stop_bot"),
        InlineKeyboardButton("🔄 تشغيل البوت", callback_data="start_bot"),
        InlineKeyboardButton("🔙 رجوع", callback_data="back_main")
    )
    return markup

# معالجة الأوامر
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    global bot_status
    if bot_status == "stopped" and user_id != ADMIN_ID:
        bot.send_message(user_id, stop_message)
        return
        
    if users_data.get(user_id, {}).get("banned", False):
        bot.send_message(user_id, "⛔ تم حظرك من استخدام البوت")
        return
        
    if not check_subscription(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ @crazys7", url="https://t.me/crazys7"))
        markup.add(InlineKeyboardButton("✅ @AWU87", url="https://t.me/AWU87"))
        markup.add(InlineKeyboardButton("🔍 تحقق", callback_data="check_subs"))
        bot.send_message(user_id, "(¬‿¬)ノ\n♨️| اشترك في القنوات للتمكن من استخدام البوت", reply_markup=markup)
    else:
        if user_id not in users_data:
            users_data[user_id] = {"searches": 0, "downloads": 0}
            # إرسال إشعار للمدير
            try:
                bot.send_message(ADMIN_ID, f"مستخدم جديد:\n👤 {message.from_user.first_name}\n🆔 @{message.from_user.username}")
            except:
                pass
        bot.send_message(user_id, "مرحبًا! اختر أحد الخيارات:", reply_markup=create_main_menu())

# معالجة الرسائل النصية (للبحث)
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    user_id = message.from_user.id
    
    # التحقق من حالة البوت والحظر
    if bot_status == "stopped" and user_id != ADMIN_ID:
        return
    if users_data.get(user_id, {}).get("banned", False):
        return
    
    # إذا كان المستخدم في حالة انتظار كلمة بحث
    if user_id in user_states and user_states[user_id] == "waiting_for_search":
        # استرجاع نوع البحث المحفوظ
        search_type = users_data[user_id].get("current_search_type")
        
        if search_type:
            # إجراء البحث
            query = message.text
            results = lummi_search(search_type, query)
            
            if not results:
                bot.send_message(message.chat.id, "⚠️ لم يتم العثور على نتائج للبحث: " + query)
                return
                
            # تحديث الإحصائيات
            if user_id not in users_data:
                users_data[user_id] = {"searches": 0, "downloads": 0}
            users_data[user_id]["searches"] = users_data.get(user_id, {}).get("searches", 0) + 1
            
            # حفظ النتائج
            search_results[user_id] = {
                "type": search_type,
                "query": query,
                "results": results,
                "index": 0
            }
            
            # إرسال أول نتيجة
            send_result(user_id, message.chat.id, None, 0)
            
            # إعادة تعيين حالة المستخدم
            user_states[user_id] = None
        else:
            bot.send_message(message.chat.id, "حدث خطأ، يرجى المحاولة مرة أخرى")

# معالجة الكول باك
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    global bot_status, paid_mode
    # التحقق من حالة البوت
    if bot_status == "stopped" and user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, stop_message, show_alert=True)
        return
        
    # التحقق من الحظر
    if users_data.get(user_id, {}).get("banned", False):
        bot.answer_callback_query(call.id, "⛔ تم حظرك من استخدام البوت", show_alert=True)
        return
        
    # التحقق من الاشتراك
    if call.data != "check_subs" and not check_subscription(user_id):
        bot.answer_callback_query(call.id, "يجب الاشتراك في القنوات أولاً", show_alert=True)
        return
    
    # معالجة الأحداث
    if call.data == "check_subs":
        if check_subscription(user_id):
            try:
                bot.delete_message(chat_id, message_id)
            except:
                pass
            bot.send_message(chat_id, "تم الاشتراك بنجاح! اختر خيارًا:", reply_markup=create_main_menu())
            if user_id not in users_data:
                users_data[user_id] = {"searches": 0, "downloads": 0}
                try:
                    bot.send_message(ADMIN_ID, f"مستخدم جديد:\n👤 {call.from_user.first_name}\n🆔 @{call.from_user.username}")
                except:
                    pass
        else:
            bot.answer_callback_query(call.id, "لم تشترك في جميع القنوات بعد!", show_alert=True)
            
    elif call.data == "search_menu":
        try:
            bot.edit_message_text("اختر نوع البحث:", chat_id, message_id, reply_markup=create_search_menu())
        except:
            pass
        
    elif call.data.startswith("search_"):
        search_type = call.data.split("_", 1)[1]
        
        # حفظ نوع البحث الحالي للمستخدم
        if user_id not in users_data:
            users_data[user_id] = {}
        users_data[user_id]["current_search_type"] = search_type
        
        # تعيين حالة المستخدم لانتظار كلمة البحث
        user_states[user_id] = "waiting_for_search"
        
        # طلب كلمة البحث من المستخدم
        try:
            bot.edit_message_text(f"أرسل كلمة البحث لـ {search_type}:", chat_id, message_id)
        except:
            bot.send_message(chat_id, f"أرسل كلمة البحث لـ {search_type}:")
        
    elif call.data.startswith(("prev_", "next_", "download_")):
        parts = call.data.split("_")
        action = parts[0]
        target_user = int(parts[1])
        index = int(parts[2])
        
        if user_id != target_user:
            bot.answer_callback_query(call.id, "هذا الإجراء ليس لك", show_alert=True)
            return
            
        data = search_results.get(user_id, {})
        if not data:
            bot.answer_callback_query(call.id, "لا توجد نتائج متاحة", show_alert=True)
            return
            
        results = data.get("results", [])
        if not results:
            bot.answer_callback_query(call.id, "لا توجد نتائج متاحة", show_alert=True)
            return
            
        new_index = index
        
        if action == "prev":
            new_index = (index - 1) % len(results)
        elif action == "next":
            new_index = (index + 1) % len(results)
        elif action == "download":
            download_media(user_id, index)
            bot.answer_callback_query(call.id, "✅ تم التحميل بنجاح!")
            try:
                bot.edit_message_reply_markup(chat_id, message_id, reply_markup=None)
            except:
                pass
            return
            
        search_results[user_id]["index"] = new_index
        send_result(user_id, chat_id, message_id, new_index)
        
    elif call.data == "about_dev":
        dev_info = """
𓆩عن المطور𓆪

👤 الاسم: Ili
🆔 المعرف: @Ili8_8ill

💼 المهارات:
- تطوير بوتات التليجرام
- برمجة الويب
- الذكاء الاصطناعي

📢 القنوات:
- @crazys7
- @AWU87

رؤية مستقبلية: تقديم أفضل الحلول التقنية للمجتمع العربي
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
        try:
            bot.edit_message_text(dev_info, chat_id, message_id, reply_markup=markup)
        except:
            bot.send_message(chat_id, dev_info, reply_markup=markup)
        
    elif call.data == "stats":
        total_users = len(users_data)
        total_searches = sum([u.get("searches", 0) for u in users_data.values()])
        total_downloads = sum([u.get("downloads", 0) for u in users_data.values()])
        active_users = sum([1 for u in users_data.values() if u.get("searches", 0) > 0])
        
        stats_text = f"""
📊 إحصائيات البوت:

👥 المستخدمون الإجماليون: {total_users}
🔍 عمليات البحث: {total_searches}
📥 التحميلات: {total_downloads}
👤 المستخدمون النشطون: {active_users}
"""
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_main"))
        try:
            bot.edit_message_text(stats_text, chat_id, message_id, reply_markup=markup)
        except:
            bot.send_message(chat_id, stats_text, reply_markup=markup)
        
    elif call.data == "admin_panel" and user_id == ADMIN_ID:
        try:
            bot.edit_message_text("لوحة إدارة البوت:", chat_id, message_id, reply_markup=create_admin_panel())
        except:
            bot.send_message(chat_id, "لوحة إدارة البوت:", reply_markup=create_admin_panel())
        
    elif call.data == "back_main":
        try:
            bot.edit_message_text("القائمة الرئيسية:", chat_id, message_id, reply_markup=create_main_menu())
        except:
            bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=create_main_menu())
        
    # إدارة الأعضاء
    elif call.data in ["ban_member", "unban_member"] and user_id == ADMIN_ID:
        action = "حظر" if call.data == "ban_member" else "رفع الحظر"
        msg = bot.send_message(chat_id, f"أرسل ID المستخدم لـ {action}:")
        bot.register_next_step_handler(msg, process_member_action, action)
        
    # إدارة البوت
    elif call.data == "stop_bot" and user_id == ADMIN_ID:
        bot_status = "stopped"
        bot.answer_callback_query(call.id, "تم إيقاف البوت بنجاح", show_alert=True)
        
    elif call.data == "start_bot" and user_id == ADMIN_ID:
        bot_status = "active"
        bot.answer_callback_query(call.id, "تم تشغيل البوت بنجاح", show_alert=True)
        
    elif call.data == "toggle_paid" and user_id == ADMIN_ID:
        paid_mode = not paid_mode
        status = "مفعّل" if paid_mode else "معطّل"
        bot.answer_callback_query(call.id, f"الوضع المدفوع {status}", show_alert=True)
        
    elif call.data == "disable_all_subs" and user_id == ADMIN_ID:
        # كود لإلغاء كل الاشتراكات
        bot.answer_callback_query(call.id, "تم إيقاف الاشتراكات عن الجميع", show_alert=True)

def send_result(user_id, chat_id, message_id, index):
    data = search_results.get(user_id, {})
    results = data.get("results", [])
    
    if not results or index >= len(results):
        bot.send_message(chat_id, "⚠️ لا توجد نتائج متاحة")
        return
        
    item = results[index]
    media_url = item.get("media_url")
    caption = item.get("title", f"نتيجة البحث #{index+1}")
    
    markup = create_results_nav(user_id, index)
    
    # إرسال الوسائط مع معالجة الأخطاء
    try:
        if media_url and (media_url.endswith(('.jpg', '.jpeg', '.png')) and requests.head(media_url).status_code == 200:
            if message_id:
                try:
                    bot.delete_message(chat_id, message_id)
                except:
                    pass
            bot.send_photo(chat_id, media_url, caption=caption, reply_markup=markup)
        elif media_url and (media_url.endswith(('.mp4', '.mov')) and requests.head(media_url).status_code == 200:
            if message_id:
                try:
                    bot.delete_message(chat_id, message_id)
                except:
                    pass
            bot.send_video(chat_id, media_url, caption=caption, reply_markup=markup)
        else:
            if message_id:
                try:
                    bot.delete_message(chat_id, message_id)
                except:
                    pass
            bot.send_message(chat_id, f"{caption}\n{media_url}", reply_markup=markup)
    except Exception as e:
        print(f"Error sending result: {e}")
        bot.send_message(chat_id, f"⚠️ خطأ في عرض النتيجة: {e}")

def download_media(user_id, index):
    data = search_results.get(user_id, {})
    results = data.get("results", [])
    
    if not results or index >= len(results):
        return
        
    item = results[index]
    media_url = item.get("media_url")
    title = item.get("title", "محتوى بدون عنوان")
    
    if user_id not in users_data:
        users_data[user_id] = {"searches": 0, "downloads": 0}
    users_data[user_id]["downloads"] = users_data.get(user_id, {}).get("downloads", 0) + 1
    
    # إرسال إلى القناة
    try:
        user_info = bot.get_chat(user_id)
        username = user_info.username if user_info.username else f"ID: {user_id}"
    except:
        username = f"ID: {user_id}"
    
    caption = f"تم التحميل بواسطة: @{username}\nالعنوان: {title}"
    
    try:
        if media_url and (media_url.endswith(('.jpg', '.jpeg', '.png')) and requests.head(media_url).status_code == 200:
            bot.send_photo("@AWU87", media_url, caption=caption)
        elif media_url and (media_url.endswith(('.mp4', '.mov')) and requests.head(media_url).status_code == 200:
            bot.send_video("@AWU87", media_url, caption=caption)
        else:
            bot.send_message("@AWU87", f"{caption}\n{media_url}")
    except Exception as e:
        print(f"Error downloading media: {e}")

def process_member_action(message, action):
    try:
        target_id = int(message.text)
        if target_id in users_data:
            users_data[target_id]["banned"] = (action == "حظر")
            status = "تم الحظر" if action == "حظر" else "تم رفع الحظر"
            bot.send_message(message.chat.id, f"{status} للمستخدم {target_id}")
        else:
            bot.send_message(message.chat.id, "المستخدم غير موجود")
    except ValueError:
        bot.send_message(message.chat.id, "ID غير صحيح")

# إعداد ويب هووك
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return 'Invalid content type', 403

# إعداد ويب هووك عند التشغيل
def setup_webhook():
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        print(f"تم إعداد ويب هووك بنجاح: {WEBHOOK_URL}")
    except Exception as e:
        print(f"خطأ في إعداد ويب هووك: {e}")

# بدء البوت
if __name__ == '__main__':
    print("جاري تشغيل البوت...")
    setup_webhook()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
