import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import logging
import urllib.parse
from flask import Flask, request, abort

# تهيئة نظام التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = '8110119856:AAFe3EnW8vFAzb_mE_zduxfmSjdC9Gwu-D8'
ICONFINDER_API_KEY = 'X0vjEUN6KRlxbp2DoUkyHeM0VOmxY91rA6BbU5j3Xu6wDodwS0McmilLPBWDUcJ1'
PIXABAY_API_KEY = '51444506-bffefcaf12816bd85a20222d1'
ADMIN_ID = 7251748706  # معرف المدير
CHANNEL_ID = '@AWU87'  # القناة لإرسال المحتوى المحمل
WEBHOOK_URL = 'https://greenpo.onrender.com/webhook'  # تحديث رابط الويب هووك

app = Flask(__name__)
bot = telebot.TeleBot(TOKEN)

# قنوات الاشتراك الإجباري
REQUIRED_CHANNELS = ['@crazys7', '@AWU87']

# ذاكرة مؤقتة لتخزين نتائج البحث لكل مستخدم
user_data = {}
new_users = set()  # لتتبع المستخدمين الجدد

# ألوان الرسوم التوضيحية مع رموزها وقيمها HEX
COLORS = {
    "🤍": "FFFFFF",  # أبيض
    "🖤": "000000",  # أسود
    "🤎": "795548",  # بني
    "💜": "9C27B0",  # بنفسجي
    "💙": "2196F3",  # أزرق
    "💚": "4CAF50",  # أخضر
    "💛": "FFEB3B",  # أصفر
    "🧡": "FF9800",  # برتقالي
    "❤️": "F44336",  # أحمر
    "🩷": "F48FB1",  # وردي
    "🩵": "80DEEA",  # أزرق فاتح
    "🩶": "9E9E9E",  # رمادي
}

def is_valid_url(url):
    """التحقق من صحة عنوان URL"""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def set_webhook():
    """تعيين ويب هوك للبوت"""
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        logger.info("تم تعيين ويب هوك بنجاح")
    except Exception as e:
        logger.error(f"خطأ في تعيين ويب هوك: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    """معالجة التحديثات الواردة من تلجرام"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        abort(403)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # التحقق من المستخدم الجديد
    if user_id not in new_users:
        new_users.add(user_id)
        notify_admin(user_id, message.from_user.username)
    
    # التحقق من الاشتراك في القنوات
    not_subscribed = check_subscription(user_id)
    
    if not_subscribed:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("تحقق من الاشتراك", callback_data="check_subscription"))
        msg = bot.send_message(chat_id, "يجب الاشتراك في القنوات التالية اولا:\n" + "\n".join(not_subscribed), reply_markup=markup)
        # حفظ معرف الرسالة الرئيسية للمستخدم
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['main_message_id'] = msg.message_id
    else:
        show_main_menu(chat_id, user_id)

def notify_admin(user_id, username):
    """إرسال إشعار للمدير عند انضمام مستخدم جديد"""
    try:
        username = f"@{username}" if username else "بدون معرف"
        message = "مستخدم جديد انضم للبوت:\n\n"
        message += f"ID: {user_id}\n"
        message += f"Username: {username}"
        bot.send_message(ADMIN_ID, message)
    except Exception as e:
        logger.error(f"خطأ في إرسال إشعار للمدير: {e}")

def check_subscription(user_id):
    not_subscribed = []
    for channel in REQUIRED_CHANNELS:
        try:
            # الحصول على حالة المستخدم في القناة
            chat_member = bot.get_chat_member(chat_id=channel, user_id=user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                not_subscribed.append(channel)
        except Exception as e:
            logger.error(f"خطأ في التحقق من الاشتراك: {e}")
            not_subscribed.append(channel)
    return not_subscribed

def show_main_menu(chat_id, user_id):
    # إعادة ضبط بيانات المستخدم
    if user_id not in user_data:
        user_data[user_id] = {}
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 بدء البحث", callback_data="search"))
    markup.add(InlineKeyboardButton("👤 عن المطور", callback_data="about_dev"))
    
    welcome_msg = "ICONFINDBOT\nابحث عن أيقونات ورسومات"
    
    # إذا كانت هناك رسالة سابقة، نقوم بتعديلها بدلاً من إرسال رسالة جديدة
    if 'main_message_id' in user_data[user_id]:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data[user_id]['main_message_id'],
                text=welcome_msg,
                reply_markup=markup
            )
            return
        except Exception as e:
            logger.error(f"خطأ في تعديل القائمة الرئيسية: {e}")
            # إذا فشل التعديل، نرسل رسالة جديدة
            msg = bot.send_message(chat_id, welcome_msg, reply_markup=markup)
            user_data[user_id]['main_message_id'] = msg.message_id
    else:
        # إرسال رسالة جديدة
        msg = bot.send_message(chat_id, welcome_msg, reply_markup=markup)
        user_data[user_id]['main_message_id'] = msg.message_id

@bot.callback_query_handler(func=lambda call: call.data == "check_subscription")
def verify_subscription(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    not_subscribed = check_subscription(user_id)
    
    if not_subscribed:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("تحقق من الاشتراك", callback_data="check_subscription"))
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text="يجب الاشتراك في القنوات التالية اولا:\n" + "\n".join(not_subscribed),
                reply_markup=markup
            )
        except Exception as e:
            logger.error(f"خطأ في تعديل رسالة الاشتراك: {e}")
    else:
        show_main_menu(chat_id, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "search")
def show_content_types(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # إعادة ضبط بيانات البحث
    if user_id not in user_data:
        user_data[user_id] = {}
    
    # إخفاء الرسالة السابقة
    try:
        bot.answer_callback_query(call.id)
    except:
        pass
    
    markup = InlineKeyboardMarkup(row_width=1)
    # إضافة خيارات البحث
    markup.add(
        InlineKeyboardButton("🎨 رسوم توضيحية", callback_data="choose_color"),
        InlineKeyboardButton("📹 فيديوهات", callback_data="type_videos"),
        InlineKeyboardButton("🖼️ أيقونات", callback_data="type_icons")
    )
    # إضافة زر الرجوع للقائمة الرئيسية
    markup.add(InlineKeyboardButton("🏠 رجوع للقائمة الرئيسية", callback_data="back_to_main"))
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="اختر نوع المحتوى:",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"خطأ في عرض انواع المحتوى: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "choose_color")
def show_color_picker(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    # إعادة ضبط بيانات البحث
    if user_id not in user_data:
        user_data[user_id] = {}
    
    # إنشاء لوحة الألوان
    markup = InlineKeyboardMarkup(row_width=4)
    
    # الصف الأول
    row1 = [
        InlineKeyboardButton("🤍", callback_data="color_FFFFFF"),
        InlineKeyboardButton("🖤", callback_data="color_000000"),
        InlineKeyboardButton("🤎", callback_data="color_795548"),
        InlineKeyboardButton("💜", callback_data="color_9C27B0")
    ]
    
    # الصف الثاني
    row2 = [
        InlineKeyboardButton("💙", callback_data="color_2196F3"),
        InlineKeyboardButton("💚", callback_data="color_4CAF50"),
        InlineKeyboardButton("💛", callback_data="color_FFEB3B"),
        InlineKeyboardButton("🧡", callback_data="color_FF9800")
    ]
    
    # الصف الثالث
    row3 = [
        InlineKeyboardButton("❤️", callback_data="color_F44336"),
        InlineKeyboardButton("🩷", callback_data="color_F48FB1"),
        InlineKeyboardButton("🩵", callback_data="color_80DEEA"),
        InlineKeyboardButton("🩶", callback_data="color_9E9E9E")
    ]
    
    markup.add(*row1)
    markup.add(*row2)
    markup.add(*row3)
    markup.add(InlineKeyboardButton("🔙 رجوع", callback_data="back_to_content_types"))
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="اختر لونًا للرسوم التوضيحية:",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"خطأ في عرض خيارات الألوان: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("color_"))
def handle_color_selection(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    color_code = call.data.split("_")[1]
    
    # تخزين اللون المختار
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['color'] = color_code
    
    # تحديد رمز الإيموجي للون المختار
    for emoji, code in COLORS.items():
        if code == color_code:
            selected_emoji = emoji
            break
    else:
        selected_emoji = "🎨"
    
    # طلب كلمة البحث
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("الغاء البحث", callback_data="cancel_search"))
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"{selected_emoji} تم اختيار اللون\nالآن ارسل كلمة البحث:",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"خطأ في طلب كلمة البحث: {e}")
    
    # حفظ معرف الرسالة للاستخدام لاحقاً
    user_data[user_id]['search_message_id'] = call.message.message_id
    # تسجيل الخطوة التالية
    bot.register_next_step_handler(call.message, process_search_term, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_content_types")
def back_to_content_types(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    show_content_types(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def request_search_term(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    content_type = call.data.split("_")[1]
    
    # تخزين نوع المحتوى المختار
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['content_type'] = content_type
    
    # طلب كلمة البحث مع زر إلغاء
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("الغاء البحث", callback_data="cancel_search"))
    
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="ارسل كلمة البحث:",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"خطأ في طلب كلمة البحث: {e}")
    
    # حفظ معرف الرسالة للاستخدام لاحقاً
    user_data[user_id]['search_message_id'] = call.message.message_id
    # تسجيل الخطوة التالية
    bot.register_next_step_handler(call.message, process_search_term, user_id)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_search")
def cancel_search(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    show_main_menu(chat_id, user_id)

def process_search_term(message, user_id):
    chat_id = message.chat.id
    search_term = message.text
    
    # حذف رسالة إدخال المستخدم
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception as e:
        logger.error(f"خطأ في حذف رسالة المستخدم: {e}")
    
    # استرجاع نوع المحتوى
    if user_id not in user_data or 'content_type' not in user_data[user_id]:
        show_main_menu(chat_id, user_id)
        return
    
    content_type = user_data[user_id]['content_type']
    
    # تحديث الرسالة السابقة لإظهار حالة التحميل
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=user_data[user_id]['search_message_id'],
            text="جاري البحث في قاعدة البيانات...",
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"خطأ في عرض رسالة التحميل: {e}")
    
    # تحديد مصدر البحث بناءً على النوع
    if content_type == "videos":
        # البحث في Pixabay للفيديوهات
        results = search_pixabay(search_term, content_type)
    elif content_type == "icons":
        # البحث في Iconfinder لأنواع المحتوى الأخرى
        results = search_iconfinder(search_term, content_type)
    else:
        # البحث في unDraw للرسوم التوضيحية
        color = user_data[user_id].get('color', '00C897')  # لون افتراضي
        results = search_undraw(search_term, color)
    
    if not results or len(results) == 0:
        # عرض خيارات عند عدم وجود نتائج
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("بحث جديد", callback_data="search"))
        markup.add(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main"))
        
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data[user_id]['search_message_id'],
                text=f"لم يتم العثور على نتائج لكلمة: {search_term}\nيرجى المحاولة بكلمات أخرى",
                reply_markup=markup
            )
        except Exception as e:
            logger.error(f"خطأ في عرض رسالة عدم وجود نتائج: {e}")
        return
    
    # حفظ النتائج
    user_data[user_id]['search_term'] = search_term
    user_data[user_id]['search_results'] = results
    user_data[user_id]['current_index'] = 0
    user_data[user_id]['source'] = "pixabay" if content_type == "videos" else ("undraw" if 'color' in user_data[user_id] else "iconfinder")
    
    # عرض النتيجة الأولى في نفس رسالة "جاري البحث"
    show_result(chat_id, user_id, message_id=user_data[user_id]['search_message_id'])

def search_undraw(query, color="00C897"):
    """البحث في unDraw API للرسوم التوضيحية الملونة"""
    base_url = "https://api.undraw.co/search/illustrations"
    params = {'query': query}
    
    try:
        logger.info(f"البحث في unDraw عن: {query} باللون {color}")
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        illustrations = data.get('illustrations', [])
        logger.info(f"تم العثور على {len(illustrations)} نتيجة")
        
        # إرجاع فقط النتائج التي تحتوي على صور صالحة
        valid_results = []
        for illus in illustrations:
            image_url = illus.get('image')
            if image_url and is_valid_url(image_url):
                # إضافة اللون المختار إلى رابط الصورة
                colored_url = f"{image_url}?color={color}"
                illus['previewURL'] = colored_url
                illus['download_url'] = colored_url
                valid_results.append(illus)
        
        logger.info(f"عدد النتائج الصالحة: {len(valid_results)}")
        return valid_results
    except Exception as e:
        logger.error(f"خطأ في واجهة unDraw: {e}")
        return None

def search_iconfinder(query, content_type):
    base_url = "https://api.iconfinder.com/v4/icons/search"
    headers = {
        'Authorization': f'Bearer {ICONFINDER_API_KEY}',
        'Accept': 'application/json'
    }
    
    # تعيين النمط (style) حسب نوع المحتوى
    style = None
    if content_type == "icons":
        style = "glyph"
    
    params = {
        'query': query,
        'count': 50,
        'premium': 'false',
        'license': 'free'
    }
    
    # إضافة النمط إذا كان محددًا
    if style:
        params['style'] = style
    
    try:
        logger.info(f"البحث في Iconfinder عن: {query} ({content_type})")
        response = requests.get(base_url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        icons = data.get('icons', [])
        logger.info(f"تم العثور على {len(icons)} نتيجة")
        
        # إرجاع فقط النتائج المجانية التي تحتوي على صور صالحة
        valid_results = []
        for icon in icons:
            preview_url = get_best_icon_url(icon)
            if preview_url and is_valid_url(preview_url) and icon.get('is_premium', False) is False:
                # إضافة رابط التنزيل للمحتوى الأصلي
                icon['download_url'] = get_download_url(icon)
                valid_results.append(icon)
        
        logger.info(f"عدد النتائج المجانية الصالحة: {len(valid_results)}")
        return valid_results
    except Exception as e:
        logger.error(f"خطأ في واجهة Iconfinder: {e}")
        return None

def search_pixabay(query, content_type):
    base_url = "https://pixabay.com/api/videos/"
    params = {
        'key': PIXABAY_API_KEY,
        'q': query,
        'per_page': 50,
        'lang': 'en'
    }
    
    try:
        logger.info(f"البحث في Pixabay عن: {query} (videos)")
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        hits = data.get('hits', [])
        logger.info(f"تم العثور على {len(hits)} نتيجة")
        
        # إرجاع فقط النتائج المجانية التي تحتوي على فيديو صالح
        valid_results = []
        for hit in hits:
            if 'videos' in hit and 'medium' in hit['videos']:
                video_url = hit['videos']['medium']['url']
                if is_valid_url(video_url) and hit.get('type', '') == 'video':
                    # إضافة رابط التنزيل للمحتوى الأصلي
                    hit['download_url'] = hit['videos']['large']['url'] if 'large' in hit['videos'] else video_url
                    valid_results.append(hit)
        
        logger.info(f"عدد النتائج المجانية الصالحة: {len(valid_results)}")
        return valid_results
    except Exception as e:
        logger.error(f"خطأ في واجهة Pixabay: {e}")
        return None

def get_best_icon_url(icon):
    """الحصول على أفضل رابط للصورة من أيقونة Iconfinder"""
    # نبحث عن أكبر حجم نقطي
    if icon.get('raster_sizes') and len(icon['raster_sizes']) > 0:
        # نرتب الأحجام حسب الدقة (نريد الأكبر)
        sizes = sorted(icon['raster_sizes'], key=lambda x: x['size_width'], reverse=True)
        # نأخذ أعلى دقة
        return sizes[0]['formats'][0]['preview_url']
    
    # إذا لم يكن هناك raster_sizes، نبحث في vector_sizes
    if icon.get('vector_sizes') and len(icon['vector_sizes']) > 0:
        # نرتب الأحجام حسب الدقة (نريد الأكبر) - لكن المتجهات ليس لها دقة بالمعنى النقطي، نأخذ الأول
        return icon['vector_sizes'][0]['formats'][0]['preview_url']
    
    # خيار أخير: استخدام الرابط الأساسي
    return icon.get('preview_url')

def get_download_url(icon):
    """الحصول على رابط التنزيل الأصلي للأيقونة"""
    # نبحث عن رابط تنزيل متاح
    if icon.get('raster_sizes') and len(icon['raster_sizes']) > 0:
        sizes = sorted(icon['raster_sizes'], key=lambda x: x['size_width'], reverse=True)
        return sizes[0]['formats'][0]['download_url']
    
    if icon.get('vector_sizes') and len(icon['vector_sizes']) > 0:
        return icon['vector_sizes'][0]['formats'][0]['download_url']
    
    return icon.get('preview_url')

def show_result(chat_id, user_id, message_id=None):
    if user_id not in user_data or 'search_results' not in user_data[user_id]:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data[user_id].get('search_message_id', 0),
                text="انتهت جلسة البحث، ابدأ بحثاً جديداً"
            )
        except:
            pass
        return
    
    results = user_data[user_id]['search_results']
    current_index = user_data[user_id]['current_index']
    search_term = user_data[user_id].get('search_term', '')
    source = user_data[user_id].get('source', 'iconfinder')
    
    if current_index < 0 or current_index >= len(results):
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=user_data[user_id].get('last_message_id', 0),
                text="نهاية النتائج"
            )
        except:
            pass
        return
    
    item = results[current_index]
    
    # بناء الرسالة
    caption = f"البحث: {search_term}\n"
    caption += f"النتيجة {current_index+1} من {len(results)}\n"
    
    # بناء أزرار التنقل
    markup = InlineKeyboardMarkup()
    row_buttons = []
    if current_index > 0:
        row_buttons.append(InlineKeyboardButton("السابق", callback_data=f"nav_prev"))
    if current_index < len(results) - 1:
        row_buttons.append(InlineKeyboardButton("التالي", callback_data=f"nav_next"))
    
    if row_buttons:
        markup.row(*row_buttons)
    
    markup.add(InlineKeyboardButton("⬇️ تحميل", callback_data="download"))
    markup.add(InlineKeyboardButton("🔍 بحث جديد", callback_data="search"))
    
    # إرسال النتيجة حسب المصدر
    try:
        if source == "iconfinder":
            # الحصول على أفضل صورة متاحة
            image_url = get_best_icon_url(item)
            
            if not image_url or not is_valid_url(image_url):
                logger.error(f"رابط الصورة غير صالح: {image_url}")
                raise ValueError("رابط الصورة غير صالح")
            
            # محاولة تعديل الرسالة الحالية
            if message_id:
                try:
                    bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id,
                        media=telebot.types.InputMediaPhoto(
                            media=image_url,
                            caption=caption
                        ),
                        reply_markup=markup
                    )
                    user_data[user_id]['last_message_id'] = message_id
                    return
                except Exception as e:
                    logger.error(f"فشل في تعديل رسالة الصورة: {e}")
            
            # إرسال رسالة جديدة
            msg = bot.send_photo(chat_id, image_url, caption=caption, reply_markup=markup)
            user_data[user_id]['last_message_id'] = msg.message_id
        elif source == "pixabay":
            if 'videos' not in item or 'medium' not in item['videos']:
                logger.error("بيانات الفيديو غير مكتملة")
                raise ValueError("بيانات الفيديو غير مكتملة")
                
            video_url = item['videos']['medium']['url']
            
            if not is_valid_url(video_url):
                logger.error(f"رابط الفيديو غير صالح: {video_url}")
                raise ValueError("رابط الفيديو غير صالح")
            
            # محاولة تعديل الرسالة الحالية
            if message_id:
                try:
                    bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id,
                        media=telebot.types.InputMediaVideo(
                            media=video_url,
                            caption=caption
                        ),
                        reply_markup=markup
                    )
                    user_data[user_id]['last_message_id'] = message_id
                    return
                except Exception as e:
                    logger.error(f"فشل في تعديل رسالة الفيديو: {e}")
            
            # إرسال رسالة جديدة
            msg = bot.send_video(chat_id, video_url, caption=caption, reply_markup=markup)
            user_data[user_id]['last_message_id'] = msg.message_id
        elif source == "undraw":
            # للرسوم من unDraw
            image_url = item.get('previewURL')
            
            if not image_url or not is_valid_url(image_url):
                logger.error(f"رابط الصورة غير صالح: {image_url}")
                raise ValueError("رابط الصورة غير صالح")
            
            # محاولة تعديل الرسالة الحالية
            if message_id:
                try:
                    bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=message_id,
                        media=telebot.types.InputMediaPhoto(
                            media=image_url,
                            caption=caption
                        ),
                        reply_markup=markup
                    )
                    user_data[user_id]['last_message_id'] = message_id
                    return
                except Exception as e:
                    logger.error(f"فشل في تعديل رسالة الصورة: {e}")
            
            # إرسال رسالة جديدة
            msg = bot.send_photo(chat_id, image_url, caption=caption, reply_markup=markup)
            user_data[user_id]['last_message_id'] = msg.message_id
            
    except Exception as e:
        logger.error(f"خطأ في عرض النتيجة: {e}")
        # المحاولة مع نتيجة أخرى
        user_data[user_id]['current_index'] += 1
        if user_data[user_id]['current_index'] < len(results):
            show_result(chat_id, user_id, message_id)
        else:
            show_no_results(chat_id, user_id)

def show_no_results(chat_id, user_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 بحث جديد", callback_data="search"))
    markup.add(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main"))
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=user_data[user_id].get('search_message_id', 0),
            text="لم يتم العثور على أي نتائج، يرجى المحاولة بكلمات أخرى",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"خطأ في عرض رسالة عدم وجود نتائج: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("nav_"))
def navigate_results(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    action = call.data.split("_")[1]
    
    if user_id not in user_data or 'search_results' not in user_data[user_id]:
        bot.answer_callback_query(call.id, "انتهت جلسة البحث، ابدأ بحثاً جديداً")
        return
    
    # تحديث الفهرس
    if action == 'prev':
        user_data[user_id]['current_index'] -= 1
    elif action == 'next':
        user_data[user_id]['current_index'] += 1
    
    # حفظ معرف الرسالة الحالية (التي نضغط عليها)
    user_data[user_id]['last_message_id'] = call.message.message_id
    
    # عرض النتيجة الجديدة في نفس الرسالة
    show_result(chat_id, user_id, message_id=call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data == "download")
def download_content(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    current_index = user_data[user_id]['current_index']
    source = user_data[user_id].get('source', 'iconfinder')
    
    # إزالة أزرار التنقل
    try:
        bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"خطأ في ازالة الازرار: {e}")
    
    # إظهار رسالة تأكيد
    bot.answer_callback_query(call.id, "تم التحميل بنجاح!", show_alert=False)
    
    # إرسال الملف الأصلي
    try:
        item = user_data[user_id]['search_results'][current_index]
        download_url = item.get('download_url')
        
        if not download_url or not is_valid_url(download_url):
            logger.error("رابط التحميل غير صالح")
            return
        
        if source == "iconfinder" or source == "undraw":
            # إرسال الصورة للمستخدم
            bot.send_photo(chat_id, download_url)
            
            # إرسال الصورة إلى القناة مع معلومات إضافية
            caption = f"تم التحميل بواسطة: @{call.from_user.username if call.from_user.username else call.from_user.first_name}\n"
            caption += f"البحث: {user_data[user_id]['search_term']}"
            bot.send_photo(CHANNEL_ID, download_url, caption=caption)
            
        elif source == "pixabay":
            # إرسال الفيديو للمستخدم
            bot.send_video(chat_id, download_url)
            
            # إرسال الفيديو إلى القناة مع معلومات إضافية
            caption = f"تم التحميل بواسطة: @{call.from_user.username if call.from_user.username else call.from_user.first_name}\n"
            caption += f"البحث: {user_data[user_id]['search_term']}"
            bot.send_video(CHANNEL_ID, download_url, caption=caption)
            
    except Exception as e:
        logger.error(f"خطأ في إرسال الملف: {e}")
    
    # إظهار خيارات جديدة في رسالة منفصلة
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔍 بحث جديد", callback_data="search"))
    markup.add(InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back_to_main"))
    
    bot.send_message(chat_id, "تم تحميل المحتوى بنجاح!\nماذا تريد أن تفعل الآن؟", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "about_dev")
def show_dev_info(call):
    dev_info = """
<b>عن المطور</b>
👤 @Ili8_8ill

مطور مبتدئ في عالم بوتات تيليجرام، بدأ رحلته بشغف كبير لتعلم البرمجة وصناعة أدوات ذكية تساعد المستخدمين وتضيف قيمة للمجتمعات الرقمية. يسعى لتطوير مهاراته يومًا بعد يوم من خلال التجربة، التعلم، والمشاركة في مشاريع بسيطة لكنها فعالة.

<b>ما يميزه في هذه المرحلة:</b>
- حب الاستكشاف والتعلم الذاتي
- بناء بوتات بسيطة بمهام محددة
- استخدام أدوات مثل BotFather و Python
- الانفتاح على النقد والتطوير المستمر

<b>القنوات المرتبطة:</b>
@crazys7 - @AWU87

<b>رؤية المطور:</b>
الانطلاق من الأساسيات نحو الاحتراف، خطوة بخطوة، مع طموح لصناعة بوتات تلبي احتياجات حقيقية وتحدث فرقًا.

<b>للتواصل:</b>
تابع الحساب @Ili8_8ill
    """
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🏠 رجوع", callback_data="back_to_main"))
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=dev_info,
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"خطأ في عرض معلومات المطور: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def return_to_main(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    show_main_menu(chat_id, user_id)

if __name__ == '__main__':
    logger.info("بدء تشغيل البوت...")
    set_webhook()
    app.run(host='0.0.0.0', port=10000)
