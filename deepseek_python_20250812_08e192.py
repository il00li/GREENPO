import telebot
from telebot import types
import requests
import json
from datetime import datetime
import time
import random
import string
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = "8110119856:AAEMbomUhyXXrR8Y-YvmTJR4jmDP1-y-tQo"
PIXABAY_API_KEY = "51444506-bffefcaf12816bd85a20222d1"
ICONFINDER_API_KEY = "7K3SAYeDJcF2F7OsiUe6hAvobN0mZ485PY8iXllJktLihGgipDUFudsKahNiyHiG"
LUMNI_API_KEY = "lumni-b06d12ba02329efb74404de07e20b434aff295de34419f35c56eb3e200f05a71"
ADMIN_ID = 7251748706

# Initialize bot
bot = telebot.TeleBot(TOKEN)

# Database simulation
users_db = {}
subscription_db = {}
banned_users = set()
bot_status = True
bot_status_message = "البوت متوقف حاليًا للصيانة. نعتذر للإزعاج وسنعود قريبًا."
paid_mode = False
referral_codes = {}

# Channels for mandatory subscription
REQUIRED_CHANNELS = ["@crazys7", "@AWU87"]
RESULTS_CHANNEL = "@AWU87"

# Helper functions
def generate_referral_code(user_id):
    """Generate a unique referral code for the user"""
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    referral_codes[code] = user_id
    return code

def is_user_subscribed(user_id):
    try:
        # Always allow admin
        if user_id == ADMIN_ID:
            return True
            
        for channel in REQUIRED_CHANNELS:
            chat_id = channel.strip("@")
            try:
                member = bot.get_chat_member(chat_id, user_id)
                if member.status not in ["member", "administrator", "creator"]:
                    logger.warning(f"User {user_id} not subscribed to {channel}")
                    return False
            except Exception as e:
                logger.error(f"Error checking subscription for {channel}: {e}")
                return False
        return True
    except Exception as e:
        logger.error(f"General error in subscription check: {e}")
        return False

def get_pixabay_videos(query):
    base_url = "https://pixabay.com/api/videos/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "per_page": 10
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("hits", [])
        
        # Format results for consistency
        formatted = []
        for item in results:
            if "videos" in item and "medium" in item["videos"]:
                formatted.append({
                    "id": item.get("id"),
                    "url": item["videos"]["medium"]["url"],
                    "title": item.get("tags", query),
                    "type": "video",
                    "source": "Pixabay"
                })
        return formatted
    except Exception as e:
        logger.error(f"Pixabay API error: {e}")
        return []

def get_icons(query):
    headers = {"Authorization": f"Bearer {ICONFINDER_API_KEY}"}
    params = {"query": query, "count": 10}
    
    try:
        response = requests.get("https://api.iconfinder.com/v4/icons/search", 
                                headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        icons = []
        for icon in data.get("icons", []):
            if icon.get("raster_sizes"):
                # Get the largest available size
                sizes = icon["raster_sizes"]
                sizes.sort(key=lambda x: x.get("size", 0), reverse=True)
                
                for size in sizes:
                    if size.get("formats"):
                        for fmt in size["formats"]:
                            if fmt.get("preview_url"):
                                icons.append({
                                    "id": icon["icon_id"],
                                    "url": fmt["preview_url"],
                                    "title": icon.get("name", query),
                                    "type": "icon",
                                    "source": "IconFinder"
                                })
                                break
                        if icons and icons[-1]["id"] == icon["icon_id"]:
                            break
        
        return icons
    except Exception as e:
        logger.error(f"IconFinder API error: {e}")
        return []

def get_lumni_content(query, content_type):
    """Get content from Lumni API"""
    # This is a simplified implementation - in a real scenario, use actual API endpoints
    # For demonstration purposes, we'll generate sample content
    results = []
    content_types = {
        "image": "صورة",
        "illustration": "رسم توضيحي",
        "3d": "نموذج ثلاثي الأبعاد"
    }
    
    try:
        # Simulating API call delay
        time.sleep(1)
        
        for i in range(1, 6):
            results.append({
                "id": i,
                "url": f"https://source.unsplash.com/600x400/?{query.replace(' ', ',')}-{i}",
                "title": f"{content_types.get(content_type, content_type)}: {query} #{i}",
                "type": content_type,
                "source": "Lumni"
            })
        
        return results
    except Exception as e:
        logger.error(f"Lumni content error: {e}")
        return []

def save_user_action(user_id, action):
    if user_id not in users_db:
        users_db[user_id] = {
            "join_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "actions": [],
            "search_count": 0,
            "download_count": 0,
            "username": bot.get_chat(user_id).username or str(user_id),
            "referral_code": generate_referral_code(user_id),
            "referrals": 0
        }
    
    # Admin always has subscription
    if user_id == ADMIN_ID and user_id not in subscription_db:
        subscription_db[user_id] = "مدى الحياة (مدير)"
    
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

def has_subscription(user_id):
    # Admin always has access
    if user_id == ADMIN_ID:
        return True
    return user_id in subscription_db or (paid_mode and user_id in subscription_db)

def get_user_referral_link(user_id):
    if user_id in users_db:
        code = users_db[user_id]["referral_code"]
        return f"https://t.me/{bot.get_me().username}?start={code}"
    return ""

def get_arabic_type(media_type):
    """Get Arabic name for media type"""
    types_map = {
        "video": "فيديو",
        "icon": "أيقونة",
        "image": "صورة",
        "illustration": "رسم توضيحي",
        "3d": "نموذج ثلاثي الأبعاد"
    }
    return types_map.get(media_type, media_type)

# Start command and subscription check with admin override
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # Admin override for maintenance mode
    if not bot_status and not is_admin(user_id):
        bot.send_message(message.chat.id, bot_status_message)
        return
    
    # Check for referral code
    referral_code = None
    if len(message.text.split()) > 1:
        referral_code = message.text.split()[1]
    
    # Process referral
    if referral_code and referral_code in referral_codes:
        referrer_id = referral_codes[referral_code]
        if referrer_id != user_id:  # Prevent self-referral
            if referrer_id not in users_db:
                users_db[referrer_id] = {"referrals": 0}
            users_db[referrer_id]["referrals"] = users_db[referrer_id].get("referrals", 0) + 1
            # If referrals reach 5, activate subscription
            if users_db[referrer_id]["referrals"] >= 5:
                subscription_db[referrer_id] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                bot.send_message(referrer_id, "🎉 مبروك! لقد حصلت على اشتراك مجاني لمدة شهر بعد دعوة 5 أصدقاء.")
    
    if user_id in banned_users:
        bot.send_message(message.chat.id, "⚠️ تم حظرك من استخدام البوت.")
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
        show_main_menu(message.chat.id, user_id)

def show_main_menu(chat_id, user_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="✦ انقر للبحث ✦", callback_data="search_menu"))
    keyboard.add(types.InlineKeyboardButton(text="𓆩عن المطور𓆪", callback_data="about_dev"))
    keyboard.add(types.InlineKeyboardButton(text="『📊』", callback_data="stats"))
    
    # Show referral link if paid mode is active
    if paid_mode:
        referral_link = get_user_referral_link(user_id)
        keyboard.add(types.InlineKeyboardButton(text="🔗 رابط الدعوة الخاص بك", callback_data="referral_link"))
    
    if is_admin(user_id):
        keyboard.add(types.InlineKeyboardButton(text="👨‍💻 لوحة التحكم", callback_data="admin_menu"))
    
    bot.send_message(chat_id, "اختر من القائمة:", reply_markup=keyboard)

# Callback query handler with admin override
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    
    # Admin override for maintenance mode
    if not bot_status and not is_admin(user_id):
        bot.answer_callback_query(call.id, bot_status_message, show_alert=True)
        return
    
    if user_id in banned_users:
        bot.answer_callback_query(call.id, "⚠️ تم حظرك من استخدام البوت.", show_alert=True)
        return
    
    if paid_mode and not has_subscription(user_id):
        # Show referral options
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(text="📨 دعوة الأصدقاء", callback_data="referral_info"))
        keyboard.add(types.InlineKeyboardButton(text="💳 شراء اشتراك", url=f"https://t.me/Ili8_8ill"))
        
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, 
                         "🔒 البوت الآن في الوضع المدفوع.\n\n"
                         "يمكنك الحصول على اشتراك عن طريق:\n"
                         "1. دعوة 5 أصدقاء للحصول على اشتراك مجاني\n"
                         "2. شراء اشتراك شهري من المطور",
                         reply_markup=keyboard)
        return
    
    # Edit message instead of sending new one
    try:
        if call.data == "check_subscription":
            if is_user_subscribed(user_id):
                bot.answer_callback_query(call.id, "✔️ تم التحقق من اشتراكك! يمكنك الآن استخدام البوت.", show_alert=True)
                try:
                    bot.delete_message(call.message.chat.id, call.message.message_id)
                except:
                    pass
                show_main_menu(call.message.chat.id, user_id)
            else:
                bot.answer_callback_query(call.id, "❌ لم يتم العثور على اشتراكك في جميع القنوات المطلوبة.", show_alert=True)
        
        elif call.data == "search_menu":
            bot.edit_message_text("اختر نوع البحث:", 
                                  call.message.chat.id, 
                                  call.message.message_id,
                                  reply_markup=show_search_menu())
        
        elif call.data == "about_dev":
            bot.edit_message_text(about_dev_text(), 
                                  call.message.chat.id, 
                                  call.message.message_id,
                                  reply_markup=about_dev_keyboard(),
                                  parse_mode="HTML")
        
        elif call.data == "stats":
            bot.edit_message_text(get_stats_text(user_id), 
                                  call.message.chat.id, 
                                  call.message.message_id,
                                  reply_markup=stats_keyboard(),
                                  parse_mode="HTML")
        
        elif call.data in ["video", "icon", "image", "illustration", "3d"]:
            bot.edit_message_text(f"أدخل كلمة البحث للحصول على {get_arabic_type(call.data)}:", 
                                  call.message.chat.id, 
                                  call.message.message_id,
                                  reply_markup=None)
            
            # Register the next step handler
            bot.register_next_step_handler(call.message, process_search_query, call.data)
        
        elif call.data.startswith("result_"):
            parts = call.data.split("_")
            media_type = parts[1]
            index = int(parts[2])
            query = parts[3]
            
            show_result(call.message, media_type, query, index, user_id)
        
        elif call.data.startswith("download_"):
            parts = call.data.split("_")
            media_type = parts[1]
            url = parts[2]
            query = parts[3]
            
            # Send to results channel
            user_info = users_db.get(user_id, {})
            username = user_info.get("username", user_id)
            bot.send_message(RESULTS_CHANNEL, f"📥 تحميل جديد\nالنوع: {get_arabic_type(media_type)}\nالكلمة: {query}\nالمستخدم: @{username}\nالرابط: {url}")
            
            # Update user stats
            save_user_action(user_id, "download")
            
            # Edit original message to remove buttons
            bot.edit_message_reply_markup(chat_id=call.message.chat.id, 
                                          message_id=call.message.message_id, 
                                          reply_markup=None)
            
            bot.answer_callback_query(call.id, "✅ تم التحميل بنجاح!", show_alert=True)
        
        elif call.data == "back_to_main":
            bot.edit_message_text("اختر من القائمة:", 
                                  call.message.chat.id, 
                                  call.message.message_id,
                                  reply_markup=main_menu_keyboard(user_id))
        
        elif call.data == "admin_menu":
            if is_admin(user_id):
                bot.edit_message_text("👨‍💻 قائمة المدير:", 
                                      call.message.chat.id, 
                                      call.message.message_id,
                                      reply_markup=admin_menu_keyboard())
            else:
                bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية الوصول لهذه القائمة!", show_alert=True)
        
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
        
        elif call.data == "user_stats":
            show_all_user_stats(call.message.chat.id)
        
        elif call.data == "referral_link":
            referral_link = get_user_referral_link(user_id)
            bot.answer_callback_query(call.id, f"رابط الدعوة الخاص بك:\n{referral_link}", show_alert=True)
        
        elif call.data == "referral_info":
            bot.edit_message_text(
                "📨 نظام الدعوة:\n\n"
                f"رابط الدعوة الخاص بك:\n{get_user_referral_link(user_id)}\n\n"
                "عندما ينضم 5 أصدقاء عبر رابطك، ستحصل على اشتراك مجاني لمدة شهر!",
                call.message.chat.id, 
                call.message.message_id,
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")
                )
            )
            
    except Exception as e:
        logger.error(f"Error handling callback: {e}")
        bot.answer_callback_query(call.id, "⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.", show_alert=True)

# Menu functions
def show_search_menu():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text="🎥 فيديو", callback_data="video"),
        types.InlineKeyboardButton(text="🛠 أيقونات", callback_data="icon")
    )
    keyboard.add(
        types.InlineKeyboardButton(text="🖼 صور", callback_data="image"),
        types.InlineKeyboardButton(text="🎨 رسوم توضيحية", callback_data="illustration"),
        types.InlineKeyboardButton(text="🧊 نماذج 3D", callback_data="3d")
    )
    keyboard.add(types.InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main"))
    return keyboard

def about_dev_text():
    return """
<strong>🔧 المطور: @Ili8_8ill</strong>

شاب يمني دخل عالم البرمجة والبوتات في تيليجرام وهو مليان شغف وحماس. بدأ يتعلّم خطوة خطوة، من الصفر، وكل يوم يزيد خبرته من خلال التجربة والمشاريع الصغيرة اللي لها فايدة حقيقية.

<strong>ما شاء الله عليه، يتميّز بـ:</strong>  
• حبّه للاستكشاف والتعلّم بنفسه  
• قدرته على بناء بوتات بسيطة تخدم الناس  
• استخدامه لأدوات مثل BotFather وPython  
• تقبّله للنقد وسعيه للتطوير المستمر

<strong>📢 القنوات اللي يشتغل فيها:</strong>  
@crazys7 – @AWU87

<strong>🌟 رؤيته:</strong>  
ماشي في طريق البرمجة من الأساسيات نحو الاحتراف، بخطوات ثابتة وطموح كبير إنه يصنع بوتات تخدم الناس وتضيف قيمة حقيقية.

<strong>📬 للتواصل:</strong>  
تابع حسابه: @Ili8_8ill
"""

def about_dev_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main"))
    return keyboard

def get_stats_text(user_id):
    total_users = len(users_db)
    total_searches = sum(user.get("search_count", 0) for user in users_db.values())
    total_downloads = sum(user.get("download_count", 0) for user in users_db.values())
    
    user_stats = users_db.get(user_id, {})
    user_searches = user_stats.get("search_count", 0)
    user_downloads = user_stats.get("download_count", 0)
    referrals = user_stats.get("referrals", 0)
    
    stats_text = f"""
📊 <strong>الإحصائيات العامة:</strong>
- عدد المستخدمين: {total_users}
- عدد عمليات البحث: {total_searches}
- عدد التحميلات: {total_downloads}

📊 <strong>إحصائياتك الخاصة:</strong>
- عمليات البحث: {user_searches}
- التحميلات: {user_downloads}
- عدد الدعوات: {referrals}
"""
    
    if paid_mode and not has_subscription(user_id):
        stats_text += f"\n🔒 تحتاج إلى دعوة {5 - referrals} أصدقاء للحصول على اشتراك مجاني"
    
    return stats_text

def stats_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main"))
    return keyboard

def main_menu_keyboard(user_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="✦ انقر للبحث ✦", callback_data="search_menu"))
    keyboard.add(types.InlineKeyboardButton(text="𓆩عن المطور𓆪", callback_data="about_dev"))
    keyboard.add(types.InlineKeyboardButton(text="『📊』", callback_data="stats"))
    
    if paid_mode:
        keyboard.add(types.InlineKeyboardButton(text="🔗 رابط الدعوة الخاص بك", callback_data="referral_link"))
    
    if is_admin(user_id):
        keyboard.add(types.InlineKeyboardButton(text="👨‍💻 لوحة التحكم", callback_data="admin_menu"))
    
    return keyboard

def admin_menu_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text="👤 حظر عضو", callback_data="ban_user"),
        types.InlineKeyboardButton(text="👤 إلغاء حظر عضو", callback_data="unban_user")
    )
    keyboard.add(
        types.InlineKeyboardButton(text="💰 تفعيل/إيقاف الوضع المدفوع", callback_data="toggle_paid_mode"),
        types.InlineKeyboardButton(text="📊 إحصائيات المستخدمين", callback_data="user_stats")
    )
    keyboard.add(
        types.InlineKeyboardButton(text="✅ تفعيل اشتراك لعضو", callback_data="activate_subscription"),
        types.InlineKeyboardButton(text="❌ إلغاء اشتراك عضو", callback_data="deactivate_subscription")
    )
    keyboard.add(
        types.InlineKeyboardButton(text="❌ إلغاء كل الاشتراكات", callback_data="deactivate_all_subs"),
        types.InlineKeyboardButton(text="🔧 إيقاف/تشغيل البوت", callback_data="toggle_bot_status")
    )
    keyboard.add(
        types.InlineKeyboardButton(text="📝 تغيير رسالة إيقاف البوت", callback_data="set_status_message"),
        types.InlineKeyboardButton(text="🔙 رجوع", callback_data="back_to_main")
    )
    return keyboard

# Search and results handling with robust error checking
def process_search_query(message, media_type):
    user_id = message.from_user.id
    query = message.text.strip()
    
    if not query:
        bot.reply_to(message, "⚠️ يرجى إدخال كلمة بحث صالحة.")
        return
    
    save_user_action(user_id, "search")
    
    try:
        if message.chat.type == "private":
            bot.delete_message(message.chat.id, message.message_id)
    except:
        pass
    
    # Send loading message
    loading_msg = bot.send_message(message.chat.id, f"🔍 جاري البحث عن {get_arabic_type(media_type)} لكلمة: {query}...")
    
    # Get results based on media type
    try:
        if media_type == "video":
            results = get_pixabay_videos(query)
        elif media_type == "icon":
            results = get_icons(query)
        else:  # All other types from Lumni
            results = get_lumni_content(query, media_type)
    except Exception as e:
        logger.error(f"Error during search: {e}")
        bot.edit_message_text("⚠️ حدث خطأ أثناء البحث. يرجى المحاولة مرة أخرى.", 
                             message.chat.id, 
                             loading_msg.message_id)
        return
    
    if not results:
        bot.edit_message_text("⚠️ لم يتم العثور على نتائج. حاول بكلمة بحث أخرى.", 
                             message.chat.id, 
                             loading_msg.message_id)
        return
    
    # Store results in user's session
    if user_id not in users_db:
        users_db[user_id] = {}
    users_db[user_id]["current_results"] = results
    users_db[user_id]["current_query"] = query
    users_db[user_id]["current_media_type"] = media_type
    users_db[user_id]["current_index"] = 0
    
    # Show first result
    show_result(loading_msg, 0, user_id)

def show_result(loading_msg, index, user_id):
    user_data = users_db.get(user_id, {})
    results = user_data.get("current_results", [])
    query = user_data.get("current_query", "")
    media_type = user_data.get("current_media_type", "")
    
    if not results or index < 0 or index >= len(results):
        bot.edit_message_text("⚠️ لا توجد نتائج متاحة.", 
                             loading_msg.chat.id, 
                             loading_msg.message_id)
        return
    
    item = results[index]
    url = item.get("url", "")
    title = item.get("title", f"النتيجة {index+1}")
    
    if not url:
        bot.edit_message_text("⚠️ حدث خطأ في عرض النتيجة.", 
                             loading_msg.chat.id, 
                             loading_msg.message_id)
        return
    
    keyboard = types.InlineKeyboardMarkup()
    
    # Navigation buttons
    row = []
    if index > 0:
        row.append(types.InlineKeyboardButton(text="«« السابق", callback_data=f"result_{media_type}_{index-1}_{query}"))
    row.append(types.InlineKeyboardButton(text=f"{index+1}/{len(results)}", callback_data="no_action"))
    if index < len(results) - 1:
        row.append(types.InlineKeyboardButton(text="التالي »»", callback_data=f"result_{media_type}_{index+1}_{query}"))
    if row:
        keyboard.row(*row)
    
    # Download button
    keyboard.add(types.InlineKeyboardButton(text="◤تحميل◥", callback_data=f"download_{media_type}_{url}_{query}"))
    keyboard.add(types.InlineKeyboardButton(text="🔙 رجوع إلى البحث", callback_data="search_menu"))
    
    # Edit message to show media
    try:
        if media_type == "video":
            bot.delete_message(loading_msg.chat.id, loading_msg.message_id)
            new_msg = bot.send_video(loading_msg.chat.id, url, caption=title, reply_markup=keyboard)
        else:
            bot.delete_message(loading_msg.chat.id, loading_msg.message_id)
            new_msg = bot.send_photo(loading_msg.chat.id, url, caption=title, reply_markup=keyboard)
        
        # Store the new message ID for future editing
        users_db[user_id]["current_message_id"] = new_msg.message_id
    except Exception as e:
        logger.error(f"Error showing media: {e}")
        try:
            bot.edit_message_text(f"✅ تم العثور على {len(results)} نتيجة. انقر لرؤية المحتوى:\n\n{title}\n{url}", 
                                 loading_msg.chat.id, 
                                 loading_msg.message_id,
                                 reply_markup=keyboard)
        except:
            bot.send_message(loading_msg.chat.id, f"✅ تم العثور على {len(results)} نتيجة. انقر لرؤية المحتوى:\n\n{title}\n{url}",
                            reply_markup=keyboard)

# Admin functions with improved logic
def process_ban_user(message):
    try:
        user_id = int(message.text)
        banned_users.add(user_id)
        bot.reply_to(message, f"✅ تم حظر المستخدم {user_id} بنجاح.")
    except:
        bot.reply_to(message, "❌ خطأ في معرف المستخدم. يجب أن يكون رقمًا.")

def process_unban_user(message):
    try:
        user_id = int(message.text)
        if user_id in banned_users:
            banned_users.remove(user_id)
            bot.reply_to(message, f"✅ تم إلغاء حظر المستخدم {user_id} بنجاح.")
        else:
            bot.reply_to(message, f"❌ المستخدم {user_id} غير محظور.")
    except:
        bot.reply_to(message, "❌ خطأ في معرف المستخدم. يجب أن يكون رقمًا.")

def toggle_paid_mode(chat_id):
    global paid_mode
    paid_mode = not paid_mode
    status = "مفعّل" if paid_mode else "معطّل"
    bot.send_message(chat_id, f"✅ تم {status} الوضع المدفوع.")

def process_activate_subscription(message):
    try:
        user_id = int(message.text)
        subscription_db[user_id] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bot.reply_to(message, f"✅ تم تفعيل الاشتراك للمستخدم {user_id}.")
    except:
        bot.reply_to(message, "❌ خطأ في معرف المستخدم. يجب أن يكون رقمًا.")

def process_deactivate_subscription(message):
    try:
        user_id = int(message.text)
        if user_id in subscription_db:
            del subscription_db[user_id]
            bot.reply_to(message, f"✅ تم إلغاء اشتراك المستخدم {user_id}.")
        else:
            bot.reply_to(message, f"❌ المستخدم {user_id} ليس لديه اشتراك مفعّل.")
    except:
        bot.reply_to(message, "❌ خطأ في معرف المستخدم. يجب أن يكون رقمًا.")

def deactivate_all_subscriptions(chat_id):
    # Keep admin subscription
    admin_sub = subscription_db.get(ADMIN_ID)
    subscription_db.clear()
    if admin_sub:
        subscription_db[ADMIN_ID] = admin_sub
    bot.send_message(chat_id, "✅ تم إلغاء كل الاشتراكات (باستثناء المدير).")

def toggle_bot_status(chat_id):
    global bot_status
    bot_status = not bot_status
    status = "متوقف" if not bot_status else "يعمل"
    bot.send_message(chat_id, f"✅ تم تغيير حالة البوت إلى: {status}")
    
    # Admin control to restore service
    if bot_status and is_admin(chat_id):
        bot.send_message(chat_id, "✅ تم استئناف عمل البوت بشكل طبيعي.")

def process_status_message(message):
    global bot_status_message
    bot_status_message = message.text
    bot.reply_to(message, "✅ تم تحديث رسالة إيقاف البوت.")

def show_all_user_stats(chat_id):
    if not users_db:
        bot.send_message(chat_id, "❌ لا توجد بيانات مستخدمين حتى الآن.")
        return
    
    stats_text = "📊 <strong>إحصائيات جميع المستخدمين:</strong>\n\n"
    for user_id, data in users_db.items():
        username = data.get("username", user_id)
        searches = data.get("search_count", 0)
        downloads = data.get("download_count", 0)
        referrals = data.get("referrals", 0)
        join_date = data.get("join_date", "غير معروف")
        
        stats_text += f"<b>👤 @{username}</b>\n"
        stats_text += f"🔍 عمليات البحث: {searches}\n"
        stats_text += f"📥 التحميلات: {downloads}\n"
        stats_text += f"📨 الدعوات: {referrals}\n"
        stats_text += f"📅 تاريخ الانضمام: {join_date}\n"
        stats_text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    
    bot.send_message(chat_id, stats_text, parse_mode="HTML")

# Admin command with maintenance override
@bot.message_handler(commands=['admin'])
def admin_command(message):
    user_id = message.from_user.id
    if is_admin(user_id):
        # Admin can always access admin panel, even during maintenance
        show_admin_menu(message.chat.id)
    else:
        bot.reply_to(message, "❌ ليس لديك صلاحية الوصول لهذه القائمة!")

def show_admin_menu(chat_id):
    bot.send_message(chat_id, "👨‍💻 قائمة المدير:", reply_markup=admin_menu_keyboard())

# Emergency command to restore bot status
@bot.message_handler(commands=['restore'])
def restore_bot(message):
    user_id = message.from_user.id
    if is_admin(user_id):
        global bot_status
        bot_status = True
        bot.reply_to(message, "✅ تم استعادة حالة البوت إلى وضع التشغيل الطبيعي.")
    else:
        bot.reply_to(message, "❌ ليس لديك صلاحية تنفيذ هذا الأمر!")

# Start the bot
if __name__ == "__main__":
    logger.info("Starting bot...")
    try:
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        # Attempt to notify admin
        try:
            bot.send_message(ADMIN_ID, f"❌ البوت توقف بسبب خطأ:\n\n{e}")
        except:
            pass