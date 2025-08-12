import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests

# تكوين الأساسيات - تم تحديث التوكن
BOT_TOKEN = "8110119856:AAHvN4ny7NpWsryAXucS9_rxjj5_bGQtohs"
ADMIN_ID = 7251748706
CHANNELS = ["@crazys7", "@AWU87"]
LUMMI_API_KEY = "lummi-b06d12ba02329efb74404de07e20b434aff295de34419f35c56eb3e200f05a71"

bot = telebot.TeleBot(BOT_TOKEN)

# تخزين مؤقت للبيانات
user_data = {}
search_results = {}
media_types = {
    'illustrations': '🎨 رسومات توضيحية',
    '3d_models': '🧊 نماذج ثلاثية الأبعاد',
    'styles': '🖌️ أنماط مرئية مخصصة'
}

# ------ وظائف المساعدة ------
def check_subscription(user_id):
    try:
        for channel in CHANNELS:
            status = bot.get_chat_member(channel.strip('@'), user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except Exception as e:
        print(f"خطأ في التحقق من الاشتراك: {e}")
        return False

def notify_admin(user):
    msg = f"📥 مستخدم جديد تم تأكيد اشتراكه\n👤 الاسم: {user.first_name}\n🆔 المعرف: {user.id}"
    bot.send_message(ADMIN_ID, msg)

def get_lummi_results(media_type, page=1):
    url = f"https://api.lummi.ai/v1/media?type={media_type}&page={page}"
    headers = {"Authorization": f"Bearer {LUMMI_API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get('results', [])[:10]
        print(f"خطأ في API: {response.status_code}")
        return []
    except Exception as e:
        print(f"خطأ في طلب Lummi: {e}")
        return []

def create_main_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✦ انقر للبحث ✦", callback_data="search"))
    markup.add(InlineKeyboardButton("𓆩عن المطور𓆪", callback_data="about_dev"))
    markup.add(InlineKeyboardButton("『📊』الإحصائيات", callback_data="stats"))
    return markup

def create_search_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎨 رسومات توضيحية", callback_data="type_illustrations"))
    markup.add(InlineKeyboardButton("🧊 نماذج ثلاثية الأبعاد", callback_data="type_3d_models"))
    markup.add(InlineKeyboardButton("🖌️ أنماط مرئية مخصصة", callback_data="type_styles"))
    return markup

def create_navigation_buttons(current_index, total_results):
    markup = InlineKeyboardMarkup()
    
    if current_index > 0:
        markup.add(InlineKeyboardButton("«« النتيجة السابقة", callback_data="prev"))
    
    if current_index < total_results - 1:
        markup.add(InlineKeyboardButton("»» النتيجة التالية", callback_data="next"))
    
    markup.add(InlineKeyboardButton("◤تحميل◥", callback_data="download"))
    return markup

# ------ معالجة الأوامر ------
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    if not check_subscription(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ قناة @crazys7", url="https://t.me/crazys7"))
        markup.add(InlineKeyboardButton("✅ قناة @AWU87", url="https://t.me/AWU87"))
        markup.add(InlineKeyboardButton("🔍 تحقق", callback_data="verify_sub"))
        
        bot.send_message(
            chat_id, 
            "(¬‿¬)ノ\n♨️| اشترك في القنوات للتمكن من استخدام البوت", 
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id, 
            "مرحباً بك! اختر أحد الخيارات:", 
            reply_markup=create_main_menu()
        )

# ------ معالجة Callbacks ------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data

    try:
        if data == "verify_sub":
            if check_subscription(user_id):
                notify_admin(call.from_user)
                bot.edit_message_text(
                    "✅ تم التحقق بنجاح! اختر خياراً:",
                    chat_id,
                    message_id,
                    reply_markup=create_main_menu()
                )
            else:
                bot.answer_callback_query(
                    call.id, 
                    "❌ لم تشترك في جميع القنوات بعد!", 
                    show_alert=True
                )

        elif data == "search":
            bot.edit_message_text(
                "اختر نوع الوسائط:",
                chat_id,
                message_id,
                reply_markup=create_search_menu()
            )

        elif data.startswith("type_"):
            media_type = data.split("_")[1]
            results = get_lummi_results(media_type)
            
            if results:
                search_results[user_id] = {
                    'media_type': media_type,
                    'results': results,
                    'current_index': 0
                }
                show_media(user_id, chat_id, message_id)
            else:
                bot.answer_callback_query(
                    call.id, 
                    "⚠️ لم يتم العثور على نتائج! الرجاء المحاولة لاحقاً", 
                    show_alert=True
                )
                bot.edit_message_text(
                    "مرحباً بك! اختر أحد الخيارات:",
                    chat_id,
                    message_id,
                    reply_markup=create_main_menu()
                )

        elif data in ["prev", "next"]:
            if user_id in search_results:
                data_dict = search_results[user_id]
                current_index = data_dict['current_index']
                results = data_dict['results']
                
                if data == "prev" and current_index > 0:
                    search_results[user_id]['current_index'] = current_index - 1
                elif data == "next" and current_index < len(results) - 1:
                    search_results[user_id]['current_index'] = current_index + 1
                
                show_media(user_id, chat_id, message_id)

        elif data == "download":
            if user_id in search_results:
                data_dict = search_results[user_id]
                media_data = data_dict['results'][data_dict['current_index']]
                media_url = media_data['url']
                caption = f"📥 تم التحميل بواسطة @{call.from_user.username}\n🆔: {user_id}"
                
                # إرسال الوسائط إلى القناة
                try:
                    if media_data['type'] == 'image':
                        bot.send_photo("@AWU87", media_url, caption=caption)
                    elif media_data['type'] == 'video':
                        bot.send_video("@AWU87", media_url, caption=caption)
                    elif media_data['type'] == '3d':
                        bot.send_document("@AWU87", media_url, caption=caption)
                except Exception as e:
                    print(f"خطأ في الإرسال للقناة: {e}")
                
                # إرسال تأكيد للمستخدم
                bot.edit_message_text(
                    "✅ تم التحميل بنجاح!\nللبحث مجدداً أرسل /start",
                    chat_id,
                    message_id
                )
                del search_results[user_id]

        elif data == "about_dev":
            dev_info = """
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
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_menu"))
            
            bot.edit_message_text(
                dev_info,
                chat_id,
                message_id,
                reply_markup=markup
            )

        elif data == "stats" or data == "back_menu":
            bot.edit_message_text(
                "مرحباً بك! اختر أحد الخيارات:",
                chat_id,
                message_id,
                reply_markup=create_main_menu()
            )
            
    except Exception as e:
        print(f"خطأ في معالجة الكallback: {e}")
        bot.answer_callback_query(
            call.id, 
            "❌ حدث خطأ! الرجاء المحاولة مرة أخرى", 
            show_alert=True
        )

def show_media(user_id, chat_id, message_id):
    try:
        data = search_results[user_id]
        media = data['results'][data['current_index']]
        current_index = data['current_index'] + 1
        total_results = len(data['results'])
        
        caption = f"{media_types[data['media_type']]}\nالنتيجة: {current_index}/{total_results}"
        markup = create_navigation_buttons(data['current_index'], total_results)
        
        if media['type'] == 'image':
            bot.send_photo(
                chat_id, 
                media['url'], 
                caption=caption, 
                reply_markup=markup
            )
        elif media['type'] == 'video':
            bot.send_video(
                chat_id, 
                media['url'], 
                caption=caption, 
                reply_markup=markup
            )
        elif media['type'] == '3d':
            bot.send_document(
                chat_id, 
                media['url'], 
                caption=caption, 
                reply_markup=markup
            )
        
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        print(f"خطأ في عرض الوسائط: {e}")
        bot.answer_callback_query(
            chat_id, 
            "❌ حدث خطأ في عرض النتائج! الرجاء المحاولة لاحقاً", 
            show_alert=True
        )

# بدء تشغيل البوت
if __name__ == '__main__':
    print("تم تشغيل البوت بنجاح!")
    bot.polling(none_stop=True)