import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests

# تكوين الأساسيات
BOT_TOKEN = "8110119856:AAEMbomUhyXXrR8Y-YvmTJR4jmDP1-y-tQo"
ADMIN_ID = 7251748706
CHANNELS = ["@crazys7", "@AWU87"]
LUMMI_API_KEY = "lummi-b06d12ba02329efb74404de07e20b434aff295de34419f35c56eb3e200f05a71"

bot = telebot.TeleBot(BOT_TOKEN)

# تخزين مؤقت للبيانات
user_data = {}
search_results = {}
media_types = {
    'illustrations': 'Illustrations',
    '3d_models': '3D Models',
    'styles': 'Styles'
}

# ------ وظائف المساعدة ------
def check_subscription(user_id):
    try:
        for channel in CHANNELS:
            status = bot.get_chat_member(channel, user_id).status
            if status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except:
        return False

def notify_admin(user):
    msg = f"📥 مستخدم جديد تم تأكيد اشتراكه\n👤 الاسم: {user.first_name}\n🆔 المعرف: {user.id}"
    bot.send_message(ADMIN_ID, msg)

def get_lummi_results(media_type, page=1):
    url = f"https://api.lummi.ai/v1/media?type={media_type}&page={page}"
    headers = {"Authorization": f"Bearer {LUMMI_API_KEY}"}
    response = requests.get(url, headers=headers)
    return response.json().get('results', [])[:10]

def create_main_menu():
    markup = InlineKeyboardMarkup()
    markup.row_width = 2
    markup.add(
        InlineKeyboardButton("✦ انقر للبحث ✦", callback_data="search"),
        InlineKeyboardButton("𓆩عن المطور𓆪", callback_data="about_dev"),
        InlineKeyboardButton("『📊』الإحصائيات", callback_data="stats")
    )
    return markup

# ------ معالجة الأوامر ------
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ قناة @crazys7", url="https://t.me/crazys7"),
            InlineKeyboardButton("✅ قناة @AWU87", url="https://t.me/AWU87")
        )
        markup.add(InlineKeyboardButton("🔍 تحقق", callback_data="verify_sub"))
        bot.send_message(user_id, "(¬‿¬)ノ\n♨️| اشترك في القنوات للتمكن من استخدام البوت", reply_markup=markup)
    else:
        bot.send_message(user_id, "مرحباً! اختر أحد الخيارات:", reply_markup=create_main_menu())

# ------ معالجة Callbacks ------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data

    if data == "verify_sub":
        if check_subscription(user_id):
            notify_admin(call.from_user)
            bot.send_message(user_id, "✅ تم التحقق بنجاح! اختر خياراً:", reply_markup=create_main_menu())
        else:
            bot.answer_callback_query(call.id, "❌ لم تشترك في جميع القنوات بعد!", show_alert=True)

    elif data == "search":
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🎨 رسومات توضيحية", callback_data="type_illustrations"),
            InlineKeyboardButton("🧊 نماذج ثلاثية الأبعاد", callback_data="type_3d_models"),
            InlineKeyboardButton("🖌️ أنماط مرئية مخصصة", callback_data="type_styles")
        )
        bot.edit_message_text("اختر نوع الوسائط:", user_id, call.message.message_id, reply_markup=markup)

    elif data.startswith("type_"):
        media_type = data.split("_")[1]
        results = get_lummi_results(media_type)
        
        if results:
            search_results[user_id] = {
                'media_type': media_type,
                'results': results,
                'current_index': 0
            }
            show_media(user_id, call.message.message_id)
        else:
            bot.answer_callback_query(call.id, "⚠️ لم يتم العثور على نتائج!", show_alert=True)

    elif data in ["prev", "next"]:
        if user_id in search_results:
            index = search_results[user_id]['current_index']
            results = search_results[user_id]['results']
            
            if data == "prev" and index > 0:
                search_results[user_id]['current_index'] -= 1
            elif data == "next" and index < len(results) - 1:
                search_results[user_id]['current_index'] += 1
            
            show_media(user_id, call.message.message_id)

    elif data == "download":
        if user_id in search_results:
            media_data = search_results[user_id]['results'][search_results[user_id]['current_index']]
            media_url = media_data['url']
            caption = f"📥 تم التحميل بواسطة @{call.from_user.username}\n🆔: {user_id}"
            
            # إرسال الوسائط إلى القناة
            if media_data['type'] == 'image':
                bot.send_photo("@AWU87", media_url, caption=caption)
            elif media_data['type'] == 'video':
                bot.send_video("@AWU87", media_url, caption=caption)
            elif media_data['type'] == '3d':
                bot.send_document("@AWU87", media_url, caption=caption)
            
            # تعديل الرسالة الأصلية
            bot.edit_message_text(
                "✅ تم التحميل بنجاح!\nللبحث مجدداً أرسل /start",
                user_id,
                call.message.message_id,
                reply_markup=None
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
        bot.edit_message_text(dev_info, user_id, call.message.message_id, reply_markup=markup)

    elif data == "stats" or data == "back_menu":
        bot.edit_message_text("مرحباً! اختر أحد الخيارات:", user_id, call.message.message_id, reply_markup=create_main_menu())

def show_media(user_id, message_id):
    data = search_results[user_id]
    media = data['results'][data['current_index']]
    caption = f"🎨 {media_types[data['media_type']]}\nالصفحة: {data['current_index']+1}/{len(data['results'])}"
    
    markup = InlineKeyboardMarkup()
    row = []
    if data['current_index'] > 0:
        row.append(InlineKeyboardButton("«« السابق", callback_data="prev"))
    if data['current_index'] < len(data['results']) - 1:
        row.append(InlineKeyboardButton("»» التالي", callback_data="next"))
    markup.row(*row)
    markup.add(InlineKeyboardButton("◤ تحميل ◥", callback_data="download"))
    
    if media['type'] == 'image':
        bot.send_photo(user_id, media['url'], caption=caption, reply_markup=markup)
    elif media['type'] == 'video':
        bot.send_video(user_id, media['url'], caption=caption, reply_markup=markup)
    elif media['type'] == '3d':
        bot.send_document(user_id, media['url'], caption=caption, reply_markup=markup)
    
    bot.delete_message(user_id, message_id)

# بدء تشغيل البوت
bot.polling(none_stop=True)