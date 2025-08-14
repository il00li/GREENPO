# bot.py
# ------------------------------------------------------
# بوت أدوات المصممين — aiogram v3 + SQLite (async)
# ------------------------------------------------------
# الميزات:
# - اشتراك إجباري في قناتين (@crazys7 و @AWU87)
# - نظام دعوات: يجب دعوة 5 مستخدمين عبر رابط مخصص
# - أزرار inline فقط
# - إرسال الوسائط مباشرة من مجلدات محلية بدون روابط
# - إحصائيات عامة وشخصية + تتبع أكثر الأدوات استخدامًا
# - تخزين البيانات في SQLite (async via aiosqlite)
# ------------------------------------------------------

import asyncio
import logging
import os
import random
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    InputFile,
)
import aiosqlite

# -------------------- الإعدادات --------------------
@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "7966976239:AAHxFIEorKNvnucpzH7L-i-5VKA_EEZxWd0")  # يُفضّل عبر متغير بيئة
    FORCE_CHANNELS: tuple[str, str] = ("@crazys7", "@AWU87")
    REQUIRED_INVITES: int = 5
    DEVELOPER: str = "@Ili8_8ill"
    MEDIA_ROOT: Path = Path("media")

cfg = Config()

# مسارات التصنيفات
MEDIA_CATEGORIES = {
    "photos": {"label": "🖼 صور فوتوغرافية", "dir": cfg.MEDIA_ROOT / "photos", "send_as": "photo"},
    "icons": {"label": "🧩 أيقونات", "dir": cfg.MEDIA_ROOT / "icons", "send_as": "photo"},
    "fonts": {"label": "🅰️ خطوط", "dir": cfg.MEDIA_ROOT / "fonts", "send_as": "document"},
    "psd": {"label": "📁 ملفات PSD", "dir": cfg.MEDIA_ROOT / "psd", "send_as": "document"},
    "ui": {"label": "🧪 واجهات UI", "dir": cfg.MEDIA_ROOT / "ui", "send_as": "document_or_photo"},
    "illustrations": {"label": "🎨 رسومات توضيحية", "dir": cfg.MEDIA_ROOT / "illustrations", "send_as": "photo"},
}

# الامتدادات المصورة
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

DB_PATH = "design_tools_bot.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("design_bot")

# -------------------- قاعدة البيانات --------------------
INIT_SQL = r"""
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    referred_by INTEGER,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS referrals (
    referrer_id INTEGER,
    referred_id INTEGER UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    category TEXT,
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(INIT_SQL)
        await db.commit()

# -------------------- المساعدات --------------------
async def ensure_user(db: aiosqlite.Connection, user_id: int, referred_by: int | None):
    cur = await db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    row = await cur.fetchone()
    if row:
        return False  # user exists

    await db.execute("INSERT INTO users(user_id, referred_by) VALUES(?, ?)", (user_id, referred_by))
    if referred_by and referred_by != user_id:
        # سجّل الإحالة فقط إذا كان جديدًا
        await db.execute(
            "INSERT OR IGNORE INTO referrals(referrer_id, referred_id) VALUES(?, ?)",
            (referred_by, user_id),
        )
    await db.commit()
    return True

async def count_referrals(db: aiosqlite.Connection, user_id: int) -> int:
    cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user_id,))
    (count,) = await cur.fetchone()
    return int(count)

async def log_usage(db: aiosqlite.Connection, user_id: int, category: str):
    await db.execute("INSERT INTO usage_log(user_id, category) VALUES(?, ?)", (user_id, category))
    await db.commit()

async def top_category(db: aiosqlite.Connection) -> str | None:
    cur = await db.execute(
        "SELECT category, COUNT(*) c FROM usage_log GROUP BY category ORDER BY c DESC LIMIT 1"
    )
    row = await cur.fetchone()
    return row[0] if row else None

async def total_users(db: aiosqlite.Connection) -> int:
    cur = await db.execute("SELECT COUNT(*) FROM users")
    (count,) = await cur.fetchone()
    return int(count)

async def total_uses(db: aiosqlite.Connection) -> int:
    cur = await db.execute("SELECT COUNT(*) FROM usage_log")
    (count,) = await cur.fetchone()
    return int(count)

# -------------------- لوحات الأزرار --------------------

def start_gate_kb() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ @crazys7", url=f"https://t.me/{cfg.FORCE_CHANNELS[0][1:]}")
        ],
        [
            InlineKeyboardButton(text="✅ @AWU87", url=f"https://t.me/{cfg.FORCE_CHANNELS[1][1:]}")
        ],
        [InlineKeyboardButton(text="🔍 تحقق الاشتراك", callback_data="check_sub")],
        [InlineKeyboardButton(text="📢 رابط الدعوة", callback_data="invite_link")],
        [InlineKeyboardButton(text="🔄 تحقق الدعوات", callback_data="check_invites")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def main_menu_kb() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✦ أدوات التصميم ✦", callback_data="tools")],
        [
            InlineKeyboardButton(text="📚 مصادر مجانية", callback_data="sources"),
            InlineKeyboardButton(text="📊 إحصائيات", callback_data="stats"),
        ],
        [
            InlineKeyboardButton(text="👨‍💻 عن المطور", callback_data="about"),
            InlineKeyboardButton(text="🆘 مساعدة", callback_data="help"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tools_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=cfg_item["label"], callback_data=f"cat:{key}")]
        for key, cfg_item in MEDIA_CATEGORIES.items()
    ]
    rows.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def download_kb(category_key: str, file_name: str) -> InlineKeyboardMarkup:
    # زر ">تحميل<" يعيد إرسال نفس الملف لتسهيل الحفظ/إعادة الاستخدام
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◤تحميل◥", callback_data=f"dl:{category_key}:{file_name}")]]
    )

# -------------------- التحقق من الاشتراك --------------------
async def is_subscribed(bot: Bot, user_id: int) -> bool:
    async def check(channel: str) -> bool:
        try:
            m = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            return m.status in {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
        except Exception:
            return False
    a = await check(cfg.FORCE_CHANNELS[0])
    b = await check(cfg.FORCE_CHANNELS[1])
    return a and b

# -------------------- إرسال الوسائط --------------------

def pick_random_file(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    files = [p for p in directory.iterdir() if p.is_file() and not p.name.startswith('.')]
    return random.choice(files) if files else None

async def send_media(bot: Bot, msg: Message | CallbackQuery, category_key: str, user_id: int, db: aiosqlite.Connection):
    conf = MEDIA_CATEGORIES[category_key]
    fpath = pick_random_file(conf["dir"])
    if not fpath:
        text = "⚠️ لا توجد ملفات في هذا التصنيف بعد. ضع ملفاتك داخل المجلد: \n<code>{}</code>".format(conf["dir"].as_posix())
        if isinstance(msg, Message):
            await msg.answer(text, parse_mode=ParseMode.HTML)
        else:
            await msg.message.answer(text, parse_mode=ParseMode.HTML)
        return

    await log_usage(db, user_id, category_key)

    ext = fpath.suffix.lower()
    send_as = conf["send_as"]

    # تحديد طريقة الإرسال
    if send_as == "photo" or (send_as == "document_or_photo" and ext in IMAGE_EXTS):
        # صورة
        input_file = InputFile(fpath)
        if isinstance(msg, Message):
            await msg.answer_photo(photo=input_file, caption=f"{conf['label']}\n<code>{fpath.name}</code>", parse_mode=ParseMode.HTML, reply_markup=download_kb(category_key, fpath.name))
        else:
            await msg.message.answer_photo(photo=input_file, caption=f"{conf['label']}\n<code>{fpath.name}</code>", parse_mode=ParseMode.HTML, reply_markup=download_kb(category_key, fpath.name))
    else:
        # ملف (خطوط/PSD/الخ)
        input_file = InputFile(fpath)
        if isinstance(msg, Message):
            await msg.answer_document(document=input_file, caption=f"{conf['label']}\n<code>{fpath.name}</code>", parse_mode=ParseMode.HTML, reply_markup=download_kb(category_key, fpath.name))
        else:
            await msg.message.answer_document(document=input_file, caption=f"{conf['label']}\n<code>{fpath.name}</code>", parse_mode=ParseMode.HTML, reply_markup=download_kb(category_key, fpath.name))

# -------------------- النصوص الثابتة --------------------
WELCOME = (
    "🎨 مرحبًا بك في <b>بوت أدوات المصممين</b>!\n\n"
    "للاستخدام، يجب أولًا:\n"
    "1️⃣ الاشتراك في القنوات التالية 👇\n"
    "2️⃣ دعوة <b>5 أشخاص</b> للبوت عبر رابطك الخاص"
)

SOURCES_TXT = (
    "📚 <b>المصادر المعتمدة</b> (دون روابط):\n\n"
    "• Unsplash — صور فوتوغرافية\n"
    "• GraphicBurger — أيقونات\n"
    "• FontSpace — خطوط\n"
    "• Free Design Resources — ملفات PSD\n"
    "• UIdeck — واجهات UI\n"
    "• Unsplash Illustrations — رسومات توضيحية"
)

ABOUT_TXT = (
    "✏️ <b>المطوّر:</b> @Ili8_8ill\n\n"
    "مصمم جرافيك شغوف بتقديم أدوات مجانية للمصممين.\n"
    "هدفه بناء مجتمع إبداعي يخدم الجميع."
)

HELP_TXT = (
    "📘 <b>طريقة الاستخدام</b>:\n"
    "• اشترك في القنوات المطلوبة\n"
    "• ادعُ 5 أشخاص عبر رابطك\n"
    "• استمتع بأدوات التصميم المجانية\n\n"
    "⚠️ <b>التحذيرات</b>:\n"
    "• لا تستخدم المحتوى لأغراض تجارية بدون ترخيص\n"
    "• لا تحذف القنوات بعد الاشتراك\n\n"
    "👨‍💻 <b>الدعم الفني:</b> @Ili8_8ill"
)

# -------------------- البوت --------------------
async def main():
    if not cfg.BOT_TOKEN or cfg.BOT_TOKEN == "PUT-YOUR-TOKEN-HERE":
        raise RuntimeError("يرجى ضبط متغير البيئة BOT_TOKEN برمز البوت الصحيح.")

    await init_db()

    bot = Bot(token=cfg.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    me = await bot.get_me()
    bot_username = me.username

    # --------- /start ---------
    @dp.message(CommandStart())
    async def on_start(message: Message):
        # احفظ المستخدم + عدّ الإحالة لو كان جديدًا
        referred_by = None
        if message.text and len(message.text.split()) > 1:
            payload = message.text.split(maxsplit=1)[1]
            try:
                referred_by = int(payload)
            except Exception:
                referred_by = None

        async with aiosqlite.connect(DB_PATH) as db:
            is_new = await ensure_user(db, message.from_user.id, referred_by)
            # عرض البوابة
            await message.answer(WELCOME, reply_markup=start_gate_kb())

    # --------- أزرار البوابة ---------
    @dp.callback_query(F.data == "check_sub")
    async def on_check_sub(call: CallbackQuery):
        ok = await is_subscribed(bot, call.from_user.id)
        async with aiosqlite.connect(DB_PATH) as db:
            invites = await count_referrals(db, call.from_user.id)
        if ok and invites >= cfg.REQUIRED_INVITES:
            await call.message.edit_text("✅ تم التحقق من الاشتراك والدعوات.\nاستمتع بالأدوات!", reply_markup=main_menu_kb())
        else:
            text = (
                "🔔 لم يكتمل الشرطان بعد:\n"
                f"• الاشتراك في {cfg.FORCE_CHANNELS[0]} و {cfg.FORCE_CHANNELS[1]} — {'✅' if ok else '❌'}\n"
                f"• الدعوات: {invites}/{cfg.REQUIRED_INVITES}"
            )
            await call.answer()
            await call.message.edit_text(text, reply_markup=start_gate_kb())

    @dp.callback_query(F.data == "invite_link")
    async def on_invite_link(call: CallbackQuery):
        link = f"https://t.me/{bot_username}?start={call.from_user.id}"
        await call.answer()
        await call.message.edit_text(
            f"📢 رابط دعوتك الخاص:\n<code>{link}</code>\n\nشارك الرابط لدعوة أصدقائك.",
            reply_markup=start_gate_kb()
        )

    @dp.callback_query(F.data == "check_invites")
    async def on_check_invites(call: CallbackQuery):
        async with aiosqlite.connect(DB_PATH) as db:
            invites = await count_referrals(db, call.from_user.id)
        await call.answer()
        await call.message.edit_text(
            f"👥 عدد الأشخاص الذين دعوتهم: <b>{invites}</b>\nالمطلوب: <b>{cfg.REQUIRED_INVITES}</b>",
            reply_markup=start_gate_kb()
        )

    # --------- القائمة الرئيسية ---------
    @dp.callback_query(F.data == "back_home")
    async def on_back_home(call: CallbackQuery):
        await call.message.edit_text("[✦ أدوات التصميم ✦] — اختر مما يلي:", reply_markup=main_menu_kb())

    @dp.callback_query(F.data == "tools")
    async def on_tools(call: CallbackQuery):
        # تحقّق من الشروط قبل فتح الأدوات
        ok = await is_subscribed(bot, call.from_user.id)
        async with aiosqlite.connect(DB_PATH) as db:
            invites = await count_referrals(db, call.from_user.id)
        if not (ok and invites >= cfg.REQUIRED_INVITES):
            await call.answer("أكمل الاشتراك والدعوات أولًا.", show_alert=True)
            return
        await call.message.edit_text("✦ أدوات التصميم ✦", reply_markup=tools_menu_kb())

    @dp.callback_query(F.data == "sources")
    async def on_sources(call: CallbackQuery):
        await call.message.edit_text(SOURCES_TXT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="back_home")]]))

    @dp.callback_query(F.data == "about")
    async def on_about(call: CallbackQuery):
        await call.message.edit_text(ABOUT_TXT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="back_home")]]))

    @dp.callback_query(F.data == "help")
    async def on_help(call: CallbackQuery):
        await call.message.edit_text(HELP_TXT, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="back_home")]]))

    @dp.callback_query(F.data == "stats")
    async def on_stats(call: CallbackQuery):
        async with aiosqlite.connect(DB_PATH) as db:
            invites = await count_referrals(db, call.from_user.id)
            t_users = await total_users(db)
            t_uses = await total_uses(db)
            top_cat = await top_category(db) or "—"
        per_user_msg = f"• عدد من دعوتهم: <b>{invites}</b>"
        global_msg = f"• إجمالي المستخدمين: <b>{t_users}</b>\n• إجمالي استخدام الأدوات: <b>{t_uses}</b>\n• أكثر أداة استخدامًا: <b>{MEDIA_CATEGORIES.get(top_cat, {'label':'—'})['label'] if top_cat in MEDIA_CATEGORIES else top_cat}</b>"
        await call.message.edit_text(
            "📊 <b>إحصائيات</b>\n\n" + per_user_msg + "\n" + global_msg,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="back_home")]])
        )

    # --------- اختيار تصنيف وسائط ---------
    @dp.callback_query(F.data.startswith("cat:"))
    async def on_cat(call: CallbackQuery):
        category_key = call.data.split(":", 1)[1]
        if category_key not in MEDIA_CATEGORIES:
            await call.answer("تصنيف غير معروف.", show_alert=True)
            return
        # تحقق البوابة
        ok = await is_subscribed(bot, call.from_user.id)
        async with aiosqlite.connect(DB_PATH) as db:
            invites = await count_referrals(db, call.from_user.id)
            if not (ok and invites >= cfg.REQUIRED_INVITES):
                await call.answer("أكمل الاشتراك والدعوات أولًا.", show_alert=True)
                return
            await send_media(bot, call, category_key, call.from_user.id, db)

    # --------- زر التحميل (إعادة إرسال) ---------
    @dp.callback_query(F.data.startswith("dl:"))
    async def on_download(call: CallbackQuery):
        _, category_key, file_name = call.data.split(":", 2)
        conf = MEDIA_CATEGORIES.get(category_key)
        if not conf:
            await call.answer("تصنيف غير معروف.", show_alert=True)
            return
        fpath = conf["dir"] / file_name
        if not fpath.exists():
            await call.answer("الملف لم يعد موجودًا.", show_alert=True)
            return
        # إعادة الإرسال كما هو لتسهيل الحفظ
        ext = fpath.suffix.lower()
        input_file = InputFile(fpath)
        if ext in IMAGE_EXTS:
            await call.message.answer_photo(photo=input_file, caption=f"إعادة إرسال\n<code>{fpath.name}</code>", parse_mode=ParseMode.HTML)
        else:
            await call.message.answer_document(document=input_file, caption=f"إعادة إرسال\n<code>{fpath.name}</code>", parse_mode=ParseMode.HTML)
        await call.answer("تم.")

    # --------- التشغيل ---------
    logger.info("Bot @%s جاهز.", bot_username)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")
 
