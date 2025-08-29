import os
import telebot
import asyncio
import time
import re
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, ChannelInvalidError, ChannelPrivateError
from telethon.tl.functions.channels import InviteToChannelRequest, GetParticipantsRequest
from telethon.tl.types import InputPeerUser, ChannelParticipantsSearch
from telethon.tl.functions.channels import GetFullChannelRequest

# بيانات API
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '8300609210:AAGHCu5Un2UDMEnxy4Oh-QCY1_kVDm3S6Ro'

# إعدادات البوت
ADMIN_ID = 6689435577  # ايدي المدير

# إنشاء كائن البوت
bot = telebot.TeleBot(BOT_TOKEN)

# تخزين بيانات المستخدمين المؤقتة
user_sessions = {}
pull_sessions = {}

# إنشاء مجلد الجلسات إذا لم يكن موجوداً
if not os.path.exists('sessions'):
    os.makedirs('sessions')

# معالج أمر البدء
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.from_user.id == ADMIN_ID:
        show_main_menu(message.chat.id)
    else:
        bot.send_message(message.chat.id, "أنت لست مسؤولاً عن هذا البوت.")

# عرض القائمة الرئيسية
def show_main_menu(chat_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("تسجيل الدخول", callback_data='register'),
        telebot.types.InlineKeyboardButton("بدء السحب", callback_data='start_pull'),
        telebot.types.InlineKeyboardButton("إعدادات", callback_data='settings')
    )
    bot.send_message(chat_id, "القائمة الرئيسية:", reply_markup=markup)

# معالج الأزرار
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    
    if user_id != ADMIN_ID:
        bot.answer_callback_query(call.id, "أنت لست مسؤولاً عن هذا البوت.")
        return
        
    if call.data == 'register':
        user_sessions[user_id] = {'step': 'request_phone'}
        bot.send_message(call.message.chat.id, 'يرجى إرسال رقم هاتفك مع رمز الدولة (مثال: +1234567890)')
    
    elif call.data == 'start_pull':
        # التحقق من وجود جلسة مسجلة مسبقاً
        if not os.path.exists(f'sessions/{user_id}.session'):
            bot.send_message(call.message.chat.id, 'يجب تسجيل الدخول أولاً!')
            return
            
        pull_sessions[user_id] = {'step': 'ask_member_count'}
        bot.send_message(call.message.chat.id, 'كم عدد الأعضاء الذين تريد سحبهم؟')
    
    elif call.data == 'settings':
        show_settings_menu(call.message.chat.id)
    
    elif call.data == 'back_to_main':
        show_main_menu(call.message.chat.id)
    
    bot.answer_callback_query(call.id)

# عرض قائمة الإعدادات
def show_settings_menu(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("تغيير التأخير بين الإضافات", callback_data='change_delay'),
        telebot.types.InlineKeyboardButton("عرض الإحصائيات", callback_data='show_stats'),
        telebot.types.InlineKeyboardButton("العودة", callback_data='back_to_main')
    )
    bot.send_message(chat_id, "قائمة الإعدادات:", reply_markup=markup)

# معالجة الرسائل النصية
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        bot.send_message(message.chat.id, "أنت لست مسؤولاً عن هذا البوت.")
        return
    
    # معالجة عملية تسجيل الدخول
    if user_id in user_sessions:
        handle_login_process(message)
    
    # معالجة عملية سحب الأعضاء
    elif user_id in pull_sessions:
        handle_pull_process(message)

# معالجة عملية تسجيل الدخول
def handle_login_process(message):
    user_id = message.from_user.id
    text = message.text
    
    if user_sessions[user_id]['step'] == 'request_phone':
        # التحقق من صحة رقم الهاتف
        if not re.match(r'^\+\d{10,15}$', text):
            bot.send_message(message.chat.id, 'رقم الهاتف غير صحيح. يرجى إدخال رقم هاتف صحيح مع رمز الدولة (مثال: +1234567890)')
            return
            
        phone = text
        user_sessions[user_id]['phone'] = phone
        user_sessions[user_id]['step'] = 'request_code'
        
        # إنشاء وتخزين عميل Telethon
        client = TelegramClient(f'sessions/{user_id}', API_ID, API_HASH)
        user_sessions[user_id]['client'] = client
        
        # استخدام asyncio لتشغيل الكود غير المتزامن
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(client.connect())
            sent_code = loop.run_until_complete(client.send_code_request(phone))
            user_sessions[user_id]['phone_code_hash'] = sent_code.phone_code_hash
            
            bot.send_message(message.chat.id, 'تم إرسال رمز التحقق إلى هاتفك. يرجى إدخاله:')
        except Exception as e:
            bot.send_message(message.chat.id, f'حدث خطأ: {str(e)}')
            del user_sessions[user_id]
        finally:
            loop.close()
    
    elif user_sessions[user_id]['step'] == 'request_code':
        # معالجة رمز التحقق
        code = text.strip()
        if not code.isdigit():
            bot.send_message(message.chat.id, 'رمز التحقق يجب أن يكون أرقاماً فقط. يرجى إدخاله مرة أخرى:')
            return
            
        client = user_sessions[user_id]['client']
        phone_code_hash = user_sessions[user_id]['phone_code_hash']
        phone = user_sessions[user_id]['phone']
        
        # استخدام asyncio لتشغيل الكود غير المتزامن
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # محاولة تسجيل الدخول
            loop.run_until_complete(client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            ))
            
            # نجاح التسجيل
            bot.send_message(message.chat.id, 'تم تسجيل الدخول بنجاح!')
            loop.run_until_complete(client.disconnect())
            
            # مسح بيانات الجلسة المؤقتة
            del user_sessions[user_id]
            
            show_main_menu(message.chat.id)
            
        except SessionPasswordNeededError:
            # إذا كانت هناك حاجة إلى كلمة مرور ثنائية
            user_sessions[user_id]['step'] = 'request_2fa'
            bot.send_message(message.chat.id, 'يرجى إدخال كلمة المرور الثنائية:')
        
        except Exception as e:
            bot.send_message(message.chat.id, f'حدث خطأ أثناء التحقق: {str(e)}')
            try:
                loop.run_until_complete(client.disconnect())
            except:
                pass
            del user_sessions[user_id]
        finally:
            loop.close()
    
    elif user_sessions[user_id]['step'] == 'request_2fa':
        # معالجة كلمة المرور الثنائية
        password = text
        client = user_sessions[user_id]['client']
        
        # استخدام asyncio لتشغيل الكود غير المتزامن
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(client.sign_in(password=password))
            bot.send_message(message.chat.id, 'تم تسجيل الدخول بنجاح!')
            loop.run_until_complete(client.disconnect())
            del user_sessions[user_id]
            
            show_main_menu(message.chat.id)
            
        except Exception as e:
            bot.send_message(message.chat.id, f'حدث خطأ في كلمة المرور: {str(e)}')
            try:
                loop.run_until_complete(client.disconnect())
            except:
                pass
            del user_sessions[user_id]
        finally:
            loop.close()

# معالجة عملية سحب الأعضاء
def handle_pull_process(message):
    user_id = message.from_user.id
    text = message.text
    
    if pull_sessions[user_id]['step'] == 'ask_member_count':
        try:
            member_count = int(text)
            if member_count <= 0:
                bot.send_message(message.chat.id, 'يرجى إدخال عدد صحيح موجب.')
                return
                
            pull_sessions[user_id]['member_count'] = member_count
            pull_sessions[user_id]['step'] = 'ask_source'
            bot.send_message(message.chat.id, 'أرسل رابط أو معرف المصدر (القناة/المجموعة):')
        except ValueError:
            bot.send_message(message.chat.id, 'يرجى إدخال رقم صحيح.')
    
    elif pull_sessions[user_id]['step'] == 'ask_source':
        pull_sessions[user_id]['source'] = text
        pull_sessions[user_id]['step'] = 'ask_target'
        bot.send_message(message.chat.id, 'أرسل رابط أو معرف الهدف (القناة/المجموعة):')
    
    elif pull_sessions[user_id]['step'] == 'ask_target':
        pull_sessions[user_id]['target'] = text
        bot.send_message(message.chat.id, 'جاري بدء عملية السحب...')
        
        # بدء عملية السحب
        start_pulling(user_id, message.chat.id)

# بدء عملية سحب الأعضاء
def start_pulling(user_id, chat_id):
    try:
        # تحميل جلسة Telethon
        client = TelegramClient(f'sessions/{user_id}', API_ID, API_HASH)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(client.connect())
        
        if not loop.run_until_complete(client.is_user_authorized()):
            bot.send_message(chat_id, 'يجب تسجيل الدخول أولاً.')
            return
        
        # الحصول على معلومات المصدر
        try:
            source_entity = loop.run_until_complete(client.get_entity(pull_sessions[user_id]['source']))
        except (ValueError, ChannelInvalidError, ChannelPrivateError):
            bot.send_message(chat_id, 'المصرف غير صالح أو لا يمكن الوصول إليه.')
            loop.run_until_complete(client.disconnect())
            del pull_sessions[user_id]
            return
        
        # الحصول على معلومات الهدف
        try:
            target_entity = loop.run_until_complete(client.get_entity(pull_sessions[user_id]['target']))
        except (ValueError, ChannelInvalidError, ChannelPrivateError):
            bot.send_message(chat_id, 'الهدف غير صالح أو لا يمكن الوصول إليه.')
            loop.run_until_complete(client.disconnect())
            del pull_sessions[user_id]
            return
        
        # التحقق من صلاحية إضافة أعضاء إلى الهدف
        try:
            target_full = loop.run_until_complete(client(GetFullChannelRequest(target_entity)))
            if not target_full.chats[0].creator and not target_full.chats[0].admin_rights:
                bot.send_message(chat_id, 'ليس لديك صلاحية إضافة أعضاء إلى الهدف.')
                loop.run_until_complete(client.disconnect())
                del pull_sessions[user_id]
                return
        except:
            bot.send_message(chat_id, 'لا يمكن التحقق من صلاحيات الهدف.')
            loop.run_until_complete(client.disconnect())
            del pull_sessions[user_id]
            return
        
        # الحصول على أعضاء المصدر
        try:
            members = []
            offset = 0
            limit = 200
            
            while len(members) < pull_sessions[user_id]['member_count']:
                participants = loop.run_until_complete(client(GetParticipantsRequest(
                    source_entity,
                    ChannelParticipantsSearch(''),
                    offset,
                    limit,
                    hash=0
                )))
                
                if not participants.users:
                    break
                    
                members.extend(participants.users)
                offset += len(participants.users)
                
                if len(participants.users) < limit:
                    break
                    
        except Exception as e:
            bot.send_message(chat_id, f'حدث خطأ أثناء جلب الأعضاء: {str(e)}')
            loop.run_until_complete(client.disconnect())
            del pull_sessions[user_id]
            return
        
        if not members:
            bot.send_message(chat_id, 'لا يوجد أعضاء في المصدر أو لا يمكن الوصول إليهم.')
            loop.run_until_complete(client.disconnect())
            del pull_sessions[user_id]
            return
        
        # تحديد عدد الأعضاء المطلوب سحبهم
        member_count = min(pull_sessions[user_id]['member_count'], len(members))
        
        bot.send_message(chat_id, f'تم العثور على {len(members)} عضو. جاري سحب {member_count} عضو...')
        
        # سحب الأعضاء
        success_count = 0
        fail_count = 0
        
        for i, member in enumerate(members[:member_count]):
            try:
                # تخطي البوتات
                if member.bot:
                    fail_count += 1
                    continue
                
                # إضافة العضو إلى الهدف مع تأخير 20 ثانية
                if i > 0:
                    time.sleep(20)
                
                loop.run_until_complete(client(InviteToChannelRequest(
                    target_entity,
                    [member]
                )))
                
                success_count += 1
                if success_count % 10 == 0:  # إرسال تحديث كل 10 أعضاء
                    bot.send_message(chat_id, f'تم إضافة {success_count} عضو من أصل {member_count}')
                
            except FloodWaitError as e:
                # إذا كان هناك حظر، ننتظر المدة المطلوبة
                wait_time = e.seconds
                bot.send_message(chat_id, f'تم حظر البوت لمدة {wait_time} ثانية. جاري الانتظار...')
                time.sleep(wait_time)
                
                # إعادة المحاولة بعد انتهاء المدة
                try:
                    loop.run_until_complete(client(InviteToChannelRequest(
                        target_entity,
                        [member]
                    )))
                    
                    success_count += 1
                    if success_count % 10 == 0:
                        bot.send_message(chat_id, f'تم إضافة {success_count} عضو من أصل {member_count}')
                    
                except Exception as e:
                    fail_count += 1
                    bot.send_message(chat_id, f'فشل إضافة العضو: {member.first_name} - الخطأ: {str(e)}')
                
            except Exception as e:
                fail_count += 1
                # لا نرسل رسالة لكل خطأ لتجنب Flood
                if fail_count % 5 == 0:
                    bot.send_message(chat_id, f'فشل إضافة {fail_count} أعضاء حتى الآن')
        
        # إرسال تقرير النتائج
        bot.send_message(chat_id, f'تمت العملية بنجاح!\nالنجاح: {success_count}\nالفشل: {fail_count}')
        
        # إغلاق الاتصال
        loop.run_until_complete(client.disconnect())
        
        # مسح جلسة السحب
        del pull_sessions[user_id]
        
    except Exception as e:
        bot.send_message(chat_id, f'حدث خطأ أثناء عملية السحب: {str(e)}')
        if user_id in pull_sessions:
            del pull_sessions[user_id]

if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
