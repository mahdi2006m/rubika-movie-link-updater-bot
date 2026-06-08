"""
ماژول اصلی ربات اتوماسیون روبیکا - مدیریت فیلم‌ها
این ماژول مسئولیت‌های زیر را بر عهده دارد:
- جستجو و ویرایش اطلاعات فیلم‌ها در دیتابیس
- به‌روزرسانی خودکار لینک‌های دانلود
- مدیریت خطاها و فیلم‌های ناموفق
- ارائه منوی تعاملی برای ادمین
"""

import asyncio
import re
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from scrapers.scraper_exception import MovieNotFoundError, MultipleSearchResultsError
from rubpy import BotClient
from rubpy.bot import filters
from utils import ex_update_movie_links, ex_update_movie_links_multiple
from rubpy.bot.models import (
    Update,
    Keypad,
    KeypadRow,
    Button,
)
from rubpy.bot.enums import ButtonTypeEnum, ChatKeypadTypeEnum
import queue
from database import (
    update_movie_full,
    search_movies_smart,
    delete_movie,
    get_all_movies,
    get_movie_full,
    add_failed_movie,
    update_movie_index,
    get_all_failed_movies,
    clear_all_failed_movies,
    delete_failed_movie_by_movie_id
)

import logging
log = logging.getLogger("BOT")
log.setLevel(logging.INFO)

notification_queue = queue.Queue()
load_dotenv()

bot = BotClient(os.getenv("BOT_TOKEN"))
client_chat_guid = os.getenv("CLIENT_CHAT_GUID")
admin_chat_guid = os.getenv("ADMIN_CHAT_GUID")

from functools import wraps


def admin_only(func):
    """
    دکوراتور برای محدود کردن دسترسی هندلرها به ادمین.

    این دکوراتور بررسی می‌کند که آیا کاربر ارسال‌کننده پیام، ادمین است یا خیر.
    در صورت عدم تطابق، پیام خطا ارسال شده و اجرا متوقف می‌شود.

    Args:
        func: تابع اصلی که باید محافظت شود.

    Returns:
        wrapper: تابع داخلی که منطق بررسی دسترسی را اجرا می‌کند.
    """

    @wraps(func)
    async def wrapper(bot, update, *args, **kwargs):
        sender = getattr(update, 'author_guid', None) or getattr(update, 'chat_id', None)

        if sender != admin_chat_guid:
            try:
                await update.reply("⛔️ دسترسی محدود. این ربات فقط برای ادمین فعال است.", parse_mode="Markdown")
            except:
                pass
            return

        try:
            await func(bot, update, *args, **kwargs)
        except Exception as e:
            log.error(f"❌ Error in {func.__name__}: {e}")

        return

    return wrapper


user_states = {}

row1 = KeypadRow(buttons=[Button(id="start", button_text="/start", type=ButtonTypeEnum.SIMPLE)])
row2 = KeypadRow(buttons=[Button(id="update", button_text="اپدیت لینک ها", type=ButtonTypeEnum.SIMPLE)])
row3 = KeypadRow(buttons=[Button(id="search", button_text="جستوجوی فیلم", type=ButtonTypeEnum.SIMPLE)])
row4 = KeypadRow(buttons=[Button(id="edit", button_text="/edit همه لینک ها", type=ButtonTypeEnum.SIMPLE)])
row5 = KeypadRow(buttons=[Button(id="failed", button_text="🚨 فیلم‌های ناموفق", type=ButtonTypeEnum.SIMPLE)])
keypad = Keypad(rows=[row1, row2, row3, row4, row5], resize_keyboard=True)


def make_results_keyboard(results_count: int, page: int = 0, per_page: int = 5) -> Keypad:
    """
    ساخت کیبورد پویا برای نمایش نتایج جستجو با قابلیت صفحه‌بندی.

    Args:
        results_count (int): تعداد کل نتایج جستجو.
        page (int, optional): شماره صفحه فعلی. پیش‌فرض 0.
        per_page (int, optional): تعداد آیتم در هر صفحه. پیش‌فرض 5.

    Returns:
        Keypad: آبجکت کیبورد شامل دکمه‌های انتخاب، ناوبری و عملیات.
    """
    rows = []
    start = page * per_page
    end = min(start + per_page, results_count)

    if start < end:
        btns = [Button(id=f"sel_{i + start}", button_text=f"{i + start + 1}", type=ButtonTypeEnum.SIMPLE)
                for i in range(end - start)]
        rows.append(KeypadRow(buttons=btns))

    nav_btns = []
    if page > 0:
        nav_btns.append(Button(id="prev_page", button_text="◀️ صفحه قبل", type=ButtonTypeEnum.SIMPLE))
    if end < results_count:
        nav_btns.append(Button(id="next_page", button_text="صفحه بعد ▶️", type=ButtonTypeEnum.SIMPLE))
    if nav_btns:
        rows.append(KeypadRow(buttons=nav_btns))

    rows.append(KeypadRow(buttons=[
        Button(id="back_search", button_text="🔙 بازگشت", type=ButtonTypeEnum.SIMPLE),
        Button(id="cancel_search", button_text="❌ انصراف", type=ButtonTypeEnum.SIMPLE)
    ]))

    return Keypad(rows=rows, resize_keyboard=True)


def make_edit_menu_keyboard() -> Keypad:
    """
    ساخت کیبورد منوی ویرایش فیلم.

    Returns:
        Keypad: آبجکت کیبورد شامل گزینه‌های ویرایش عنوان، تگ‌ها، منبع، ذخیره و حذف.
    """
    return Keypad(rows=[
        KeypadRow(buttons=[Button(id="edit_title", button_text="✏️ ویرایش عنوان", type=ButtonTypeEnum.SIMPLE)]),
        KeypadRow(buttons=[Button(id="edit_tags", button_text="🏷️ ویرایش تگ‌ها", type=ButtonTypeEnum.SIMPLE)]),
        KeypadRow(buttons=[
            Button(id="toggle_source", button_text="🔄 تغییر منبع", type=ButtonTypeEnum.SIMPLE),
        ]),
        KeypadRow(buttons=[
            Button(id="save_changes", button_text="💾 ذخیره تغییرات", type=ButtonTypeEnum.SIMPLE),
            Button(id="delete_movie", button_text="🗑️ حذف فیلم", type=ButtonTypeEnum.SIMPLE)
        ]),
        KeypadRow(buttons=[Button(id="back_to_search", button_text="🔙 بازگشت به جستجو", type=ButtonTypeEnum.SIMPLE)])
    ], resize_keyboard=True)


state_filter = filters.states("any_state", match_mode="exact", scope="user", auto_clear=False)


async def clear_user_search_data(user_guid: str) -> None:
    """
    پاک‌سازی داده‌های موقت و وضعیت‌های کاربر از حافظه.

    این تابع کلیدهای مرتبط با جستجو، ویرایش و لیست ناموفق‌ها را از دیکشنری user_states حذف می‌کند.

    Args:
        user_guid (str): شناسه منحصر‌به‌فرد کاربر (چت یا نویسنده).
    """
    if user_guid in user_states:
        user_states[user_guid].pop('search_cache', None)
        user_states[user_guid].pop('editing_movie', None)
        user_states[user_guid].pop('failed_cache', None)
        user_states[user_guid].pop('selected_failed', None)
        if not user_states[user_guid]:
            del user_states[user_guid]


async def make_start_keypad(bot: BotClient, update: Update) -> None:
    """
    به‌روزرسانی کیبورد چت به حالت اولیه (منوی اصلی).

    Args:
        bot (BotClient): کلاینت ربات.
        update (Update): آبجکت آپدیت دریافتی.
    """
    await bot.edit_chat_keypad(update.chat_id, keypad_type=ChatKeypadTypeEnum.NEW, keypad=keypad)


@bot.on_update(filters.commands("start"))
@admin_only
async def handle_start(bot, update: Update) -> None:
    """
    هندلر دستور /start - نمایش پیام خوش‌آمدگویی و راهنما.

    این تابع پیام راهنما را برای کاربر ارسال کرده، کیبورد اصلی را تنظیم می‌کند
    و وضعیت‌های قبلی کاربر را پاک‌سازی می‌نماید.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت حاوی اطلاعات پیام.
    """
    await update.reply(
        "سلام! چطور مطوری...\n"
        "🔍 دکمه `search movie` → جستجوی فیلم\n"
        "🔄 `/update` → به‌روزرسانی لینک فیلم‌ها\n"
        "✏️ `/edit` → ویرایش و جایگزینی لینک‌های کانال با دیتابیس\n"
        "🔢 `/index <شماره>` → انتخاب گزینه از لیست\n"
        "سوالی بود بپرس گلم💕",
        parse_mode="Markdown"
    )
    await make_start_keypad(bot, update)
    await state_filter.clear_state_for(update)
    await clear_user_search_data(update.chat_id)


@bot.on_update(filters.commands("search") | filters.button(button_id="search"))
@admin_only
async def cmd_search(bot, update: Update) -> None:
    """
    هندلر شروع جستجوی فیلم (از طریق دستور یا دکمه).

    اگر کوئری در دستور موجود باشد، مستقیماً جستجو اجرا می‌شود؛
    در غیر این صورت از کاربر درخواست ورودی می‌کند و وضعیت را تنظیم می‌نماید.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
    """
    text = update.new_message.text.strip()
    q = None

    if text.startswith("/search"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            q = parts[1].strip()

    if not q:
        await update.reply("🔍 عنوان فیلم رو بفرست:\nمثال: `جنگ ستارگان` یا `star wars`\nبرای لغو: `/cancel`",
                           parse_mode="Markdown")
        await state_filter.set_state_for(update, "search_waiting_query")
        return

    await run_search(bot, update, q)


@bot.on_update(filters.text, filters.states("search_waiting_query"))
@admin_only
async def input_search_query(bot, update: Update) -> None:
    """
    دریافت و اعتبارسنجی ورودی متنی کاربر برای جستجو.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت حاوی متن پیام.
    """
    txt = update.new_message.text.strip()
    if txt.lower() in ['/cancel', 'انصراف', 'لغو']:
        await state_filter.clear_state_for(update)
        await make_start_keypad(bot, update)
        await update.reply("✅ لغو شد.", parse_mode="Markdown")
        return
    if len(txt) < 2:
        await update.reply("⚠️ حداقل ۲ کاراکتر وارد کن.", parse_mode="Markdown")
        return
    await run_search(bot, update, txt)


async def run_search(bot, update: Update, query: str, page: int = 0) -> None:
    """
    اجرای منطق جستجو در دیتابیس و نمایش نتایج.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
        query (str): رشته جستجو.
        page (int, optional): شماره صفحه برای صفحه‌بندی. پیش‌فرض 0.
    """
    guid = update.chat_id
    results = await asyncio.to_thread(search_movies_smart, query, limit=20)
    if not results:
        await update.reply(f"❌ نتیجه‌ای برای «{query}» پیدا نشد.", parse_mode="Markdown")
        await state_filter.clear_state_for(update)
        await make_start_keypad(bot, update)
        return
    user_states.setdefault(guid, {})['search_cache'] = {'q': query, 'res': results, 'page': page, 'pp': 5}
    await show_search_page(bot, update, results, page)
    await state_filter.set_state_for(update, "search_selecting")


async def show_search_page(bot, update: Update, results: list, page: int) -> None:
    """
    نمایش صفحه فعلی از نتایج جستجو به همراه کیبورد تعاملی.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
        results (list): لیست دیکشنری‌های حاوی اطلاعات فیلم.
        page (int): شماره صفحه فعلی.
    """
    guid = update.chat_id
    cache = user_states[guid]['search_cache']
    s, e = page * cache['pp'], min((page + 1) * cache['pp'], len(results))
    txt = f"✅ {len(results)} نتیجه برای «{cache['q']}» (صفحه {page + 1}):\n\n"
    for i in range(s, e):
        m = results[i]
        tags = " | ".join(m['tags'][:2])
        txt += f"{i + 1}. {m['title']}\n   {tags}\n\n"
    await update.reply(txt + "🔢 عدد گزینه رو بفرست:", chat_keypad=make_results_keyboard(len(results), page),
                       chat_keypad_type=ChatKeypadTypeEnum.NEW, parse_mode="Markdown")


@bot.on_update(filters.text, filters.states("search_selecting"))
@admin_only
async def select_result(bot, update: Update) -> None:
    """
    پردازش انتخاب کاربر از لیست نتایج جستجو یا ناوبری صفحات.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
    """
    guid = update.chat_id
    cache = user_states.get(guid, {}).get('search_cache')
    txt = update.new_message.text.strip()
    if not cache:
        await state_filter.clear_state_for(update)
        await make_start_keypad(bot, update)
        await update.reply("❌ جلسه منقضی شد. `/search` بزن.", parse_mode="Markdown")
        return
    if txt == "صفحه بعد ▶️": return await show_search_page(bot, update, cache['res'], cache['page'] + 1)
    if txt == "◀️ صفحه قبل": return await show_search_page(bot, update, cache['res'], max(0, cache['page'] - 1))
    if txt == "❌ انصراف":
        user_states.pop(guid, None)
        await state_filter.clear_state_for(update)
        await make_start_keypad(bot, update)
        return await update.reply("✅ لغو شد.", parse_mode="Markdown")
    if txt.isdigit():
        idx = int(txt) - 1
        global_idx = cache['page'] * cache['pp'] + idx
        if 0 <= global_idx < len(cache['res']):
            movie = cache['res'][global_idx].copy()
            user_states.setdefault(guid, {})['editing_movie'] = movie
            await start_edit_menu(bot, update, movie)
            await state_filter.set_state_for(update, "edit_menu")
            return
    await update.reply("⚠️ فقط عدد گزینه رو بفرست.", parse_mode="Markdown")


async def start_edit_menu(bot, update: Update, movie: dict) -> None:
    """
    نمایش منوی ویرایش برای فیلم انتخاب‌شده و تنظیم وضعیت کاربر.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
        movie (dict): دیکشنری حاوی اطلاعات کامل فیلم.
    """
    guid = getattr(update, 'author_guid', None) or getattr(update, 'chat_id', 'unknown')
    src = "🎬 scraper1" if movie.get('source') == 'scraper1' else "🍿 scraper2"
    txt = (f"📋 ویرایش فیلم:\n🆔 کد: {movie['id']}\n🎬 {movie['title']}\n"
           f"🏷️ {', '.join(movie.get('tags', [])) or 'بدون تگ'}\n🌐 {src}\n"
           f"{'✅ انیمیشن | ' if movie.get('is_anime') else ''}"
           f"{'📺 پخش آنلاین' if movie.get('online_watchable') else '📥 دانلود فقط'}\n\n💡 گزینه رو انتخاب کن:")

    await update.reply(txt, chat_keypad=make_edit_menu_keyboard(), chat_keypad_type=ChatKeypadTypeEnum.NEW,
                       parse_mode="Markdown")
    await state_filter.set_state_for(update, "edit_menu")
    log.info(f"✅ منوی ویرایش نمایش داده شد | State: edit_menu | کاربر: {guid}")


@bot.on_update(filters.text, filters.states("edit_menu"))
@admin_only
async def handle_edit_menu(bot, update: Update) -> None:
    """
    پردازش ورودی‌های منوی ویرایش فیلم (ویرایش فیلدها، ذخیره، حذف).

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
    """
    try:
        guid = getattr(update, 'author_guid', None) or getattr(update, 'chat_id', 'unknown')
        txt = update.new_message.text.strip()
        log.info(f"🔍 [edit_menu] دریافت متن: '{txt}' | کاربر: {guid}")

        movie = user_states.get(guid, {}).get('editing_movie')
        if not movie:
            log.warning("⚠️ [edit_menu] فیلم در کش پیدا نشد")
            await update.reply("❌ خطا: اطلاعات فیلم پیدا نشد. لطفاً `/search` بزنید.", parse_mode="Markdown")
            await state_filter.clear_state_for(update)
            await make_start_keypad(bot, update)
            return

        if "ذخیره تغییرات" in txt or "save" in txt.lower():
            log.info("💾 [edit_menu] ذخیره تغییرات فعال شد")
            updates = {k: movie[k] for k in ['title', 'tags', 'source', 'is_anime', 'online_watchable'] if k in movie}
            try:
                ok = update_movie_full(movie['id'], updates)
                if ok:
                    await update.reply("✅ تغییرات با موفقیت در دیتابیس ذخیره شد! 🎉", parse_mode="Markdown")
                else:
                    await update.reply("⚠️ تغییری برای ذخیره وجود نداشت یا خطای دیتابیس رخ داد.", parse_mode="Markdown")
            except Exception as db_err:
                log.error(f"❌ خطای دیتابیس در ذخیره: {db_err}")
                await update.reply("❌ خطا در ارتباط با دیتابیس. لاگ ترمینال رو چک کن.", parse_mode="Markdown")

            user_states.pop(guid, None)
            await state_filter.clear_state_for(update)
            await make_start_keypad(bot, update)
            return

        if "ویرایش عنوان" in txt:
            await update.reply("عنوان جدید رو بفرست:\nبرای لغو: `/cancel`", parse_mode="Markdown")
            user_states[guid]['edit_field'] = 'title'
            return await state_filter.set_state_for(update, "edit_waiting_input")

        if "ویرایش تگ" in txt:
            await update.reply("تگ‌ها رو با کاما جدا کن:\nمثال: `اکشن, 2024`\nبرای لغو: `/cancel`",
                               parse_mode="Markdown")
            user_states[guid]['edit_field'] = 'tags'
            return await state_filter.set_state_for(update, "edit_waiting_input")

        if "تغییر منبع" in txt:
            movie['source'] = 'scraper1' if movie.get('source') == 'scraper1' else 'scraper2'
            await update.reply(f"✅ منبع تغییر کرد: {movie['source']}", parse_mode="Markdown")
            return await start_edit_menu(bot, update, movie)

        if "حذف فیلم" in txt:
            await update.reply("⚠️ برای تأیید حذف بنویس: `بله`\nبرای لغو هر دکمه دیگه رو بزن.", parse_mode="Markdown")
            return await state_filter.set_state_for(update, "edit_confirm_delete")

        if "بازگشت" in txt or "search" in txt.lower():
            user_states.pop(guid, None)
            await state_filter.clear_state_for(update)
            await make_start_keypad(bot, update)
            return await cmd_search(bot, update)

        log.warning(f"⚠️ [edit_menu] گزینه نامعتبر شناسایی شد: '{txt}'")
        await update.reply("⚠️ گزینه نامعتبر. لطفاً از دکمه‌های منو استفاده کن.", parse_mode="Markdown")

    except Exception as e:
        log.error(f"❌ خطای غیرمنتظره در handle_edit_menu: {str(e)}")
        await update.reply("⚠️ خطای داخلی رخ داد. لاگ ترمینال رو بررسی کن.", parse_mode="Markdown")


async def update_edit_feedback(bot, update: Update, movie: dict, msg: str) -> None:
    """
    ارسال پیام بازخورد و بازگشت به منوی ویرایش.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
        movie (dict): اطلاعات فیلم.
        msg (str): پیام بازخورد برای نمایش به کاربر.
    """
    await update.reply(f"✅ {msg}", parse_mode="Markdown")
    await start_edit_menu(bot, update, movie)


@bot.on_update(filters.text, filters.states("edit_waiting_input"))
@admin_only
async def edit_text_input(bot, update: Update) -> None:
    """
    دریافت و اعمال ورودی متنی برای ویرایش فیلدهای فیلم.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
    """
    guid = update.chat_id
    txt = update.new_message.text.strip()
    if txt.lower() in ['/cancel', 'انصراف', 'لغو']:
        await state_filter.clear_state_for(update)
        await make_start_keypad(bot, update)
        movie = user_states.get(guid, {}).get('editing_movie')
        return await start_edit_menu(bot, update, movie)

    movie = user_states[guid].get('editing_movie')
    field = user_states[guid].get('edit_field')
    if not movie or not field: return await update.reply("❌ خطای داخلی.", parse_mode="Markdown")

    if field == 'title':
        if len(txt) < 3: return await update.reply("⚠️ عنوان کوتاه است.", parse_mode="Markdown")
        movie['title'] = txt
    elif field == 'tags':
        tags = [t.strip() for t in re.split(r'[,،/|]', txt) if t.strip()]
        if not tags: return await update.reply("⚠️ حداقل یک تگ وارد کن.", parse_mode="Markdown")
        movie['tags'] = tags

    await state_filter.clear_state_for(update)
    await make_start_keypad(bot, update)
    await update.reply(f"✅ {field} به‌روز شد. برای ذخیره نهایی «💾 ذخیره تغییرات» رو بزن.", parse_mode="Markdown")
    await start_edit_menu(bot, update, movie)


@bot.on_update(filters.text, filters.states("edit_confirm_delete"))
@admin_only
async def confirm_delete(bot, update: Update) -> None:
    """
    تأیید یا لغو عملیات حذف فیلم.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
    """
    guid = update.chat_id
    movie = user_states.get(guid, {}).get('editing_movie')
    if update.new_message.text.strip().lower() in ['بله', 'حذف کن', 'آره']:
        ok = await asyncio.to_thread(delete_movie, movie['id']) if movie else False
        user_states.pop(guid, None)
        await state_filter.clear_state_for(update)
        await make_start_keypad(bot, update)
        return await update.reply("🗑️ حذف شد!" if ok else "❌ خطا در حذف.", parse_mode="Markdown")
    user_states.pop(guid, None)
    await state_filter.clear_state_for(update)
    await make_start_keypad(bot, update)
    await update.reply("✅ حذف لغو شد.", parse_mode="Markdown")


@bot.on_update(filters.commands(["get", "edit"]))
@admin_only
async def transfer_message(bot, update: Update) -> None:
    """
    هندلر دستور انتقال پیام به چت کلاینت (برای عملیات ویرایش دسته‌ای).

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
    """
    await bot.send_message(client_chat_guid, f"/edit")
    u = await update.reply("شروع شد...", parse_mode="Markdown")
    all_movie = await asyncio.to_thread(get_all_movies)
    for i in all_movie:
        await asyncio.sleep(1)
    await bot.send_message(u.chat_id, f'تمام شد', reply_to_message_id=u.message_id)


@bot.on_update(filters.commands("update") | filters.button(button_id="update"))
@admin_only
async def handle_update(bot, update) -> None:
    """
    هندلر اصلی به‌روزرسانی لینک‌های تمام فیلم‌های دیتابیس.

    این تابع فیلم‌ها را بررسی کرده، در صورت نیاز اسکریپر را اجرا می‌کند
    و خطاها را در جدول failed_movies ثبت می‌نماید.

    Args:
        bot: کلاینت ربات.
        update: آبجکت آپدیت.
    """
    new_message = await update.reply("آپدیت شروع شد...", parse_mode="Markdown")
    all_movies = await asyncio.to_thread(get_all_movies)
    all_movies.reverse()

    for movie in all_movies:
        update_at = movie['updated_at']
        last_update_time = datetime.strptime(update_at, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) - last_update_time < timedelta(minutes=40):
            continue

        full_movie = get_movie_full(movie['id'])
        tags = full_movie.get('tags', [])
        query_search = tags[1] if len(tags) > 1 else (tags[0] if tags else full_movie.get('title', ''))

        try:
            await ex_update_movie_links(full_movie)

        except MovieNotFoundError as e:
            await bot.send_message(new_message.chat_id, f"🔎 **جستجو با تگ:** `{query_search}`\n\n❌ {str(e)}",
                                   reply_to_message_id=new_message.message_id, parse_mode="Markdown")
            await asyncio.to_thread(add_failed_movie, title=full_movie['title'],
                             error=f"اسم ارور: {type(e).__name__}\n {str(e)}\nمنبع: {full_movie['source']}",
                             movie_id=full_movie.get('id'),
                             search_query=query_search, source=full_movie.get('source'))
            continue

        except MultipleSearchResultsError as e:
            await asyncio.to_thread(add_failed_movie, title=full_movie['title'],
                             error=f"اسم ارور: {type(e).__name__}\n {str(e)}\nمنبع: {full_movie['source']}",
                             movie_id=full_movie.get('id'),
                             search_query=query_search, source=full_movie.get('source'))
            if full_movie['index'] is None:
                await bot.send_message(new_message.chat_id,
                                       f"🔎 **جستجو با تگ:** `{query_search}`\n\n⚠️ {str(e)}\n\nگزینه فیلم مد نظر رو از داخل لیست بفرست.\nبه این شکل `/index i` (i : گزینه مد نظر)",
                                       reply_to_message_id=new_message.message_id, parse_mode="Markdown")

                await state_filter.set_state_for(update, "wait_for_index")
                index = None
                for i in range(300):
                    if os.path.exists("index.txt"):
                        with open("index.txt", "r") as f:
                            index = f.read().strip()
                            if index:
                                break
                    await asyncio.sleep(1)

                if index is None:
                    await bot.send_message(new_message.chat_id, f"از این فیلم رد شد...",
                                           reply_to_message_id=new_message.message_id)
                    await asyncio.to_thread(add_failed_movie, title=full_movie['title'], error=f"{type(e).__name__}",
                                     movie_id=full_movie.get('id'),
                                     search_query=query_search, source=full_movie.get('source'))
                    await state_filter.clear_state_for(update)
                    continue
                else:
                    index = int(index)
                    await asyncio.to_thread(update_movie_index, movie['id'], index)
                    os.remove("index.txt")
            else:
                index = full_movie['index']
                await bot.send_message(new_message.chat_id,
                                       f"🔎 **جستجو با تگ:** `{query_search}`\n\n✅ با گزینه ذخیره شده {index + 1} ادامه میده.",
                                       reply_to_message_id=new_message.message_id, parse_mode="Markdown")

            try:
                await ex_update_movie_links_mult(full_movie, index)
            except Exception as e:
                await bot.send_message(new_message.chat_id,
                                       f"🔎 **جستجو با تگ:** `{query_search}`\n\n❌ با خطای ناشناخته {str(e)} رو به رو شد",
                                       reply_to_message_id=new_message.message_id, parse_mode="Markdown")
                await asyncio.to_thread(add_failed_movie, title=full_movie['title'],
                                 error=f"اسم ارور: {type(e).__name__}\n {str(e)}\nمنبع: {full_movie['source']}",
                                 movie_id=full_movie.get('id'),
                                 search_query=query_search, source=full_movie.get('source'))
            continue

        except Exception as e:
            await bot.send_message(new_message.chat_id, f"🔎 **جستجو با تگ:** `{query_search}`\n\n❌ خطا: {str(e)}",
                                   reply_to_message_id=new_message.message_id, parse_mode="Markdown")
            await asyncio.to_thread(add_failed_movie, title=full_movie['title'],
                             error=f"اسم ارور: {type(e).__name__}\n {str(e)}\nمنبع: {full_movie['source']}",
                             movie_id=full_movie.get('id'),
                             search_query=query_search, source=full_movie.get('source'))
            continue

        await asyncio.sleep(1)
    await update.reply("آپدیت تمام شد...", parse_mode="Markdown")


@bot.on_update(filters.commands("index"), filters.states("wait_for_index"))
@admin_only
async def handle_index(bot, update: Update) -> None:
    """
    هندلر دستور /index برای ذخیره ایندکس انتخابی کاربر در حالت انتظار.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
    """
    text = update.new_message.text
    if "/index" not in text:
        return
    index_str = text.replace("/index", "").strip()
    if not index_str.isdigit():
        await update.reply("لطفاً یک شماره معتبر وارد کنید. مثال: index 3/", parse_mode="Markdown")
        return
    index = int(index_str) - 1
    with open("index.txt", 'w') as f:
        f.write(str(index))
    await update.reply(f"گزینه {index + 1} ذخیره شد.", parse_mode="Markdown")


def make_failed_list_keyboard(count: int):
    rows = []
    btns = [Button(id=f"fail_{i + 1}", button_text=f"{i + 1}", type=ButtonTypeEnum.SIMPLE) for i in
            range(min(count, 10))]
    for i in range(0, len(btns), 5):
        rows.append(KeypadRow(buttons=btns[i:i + 5]))

    rows.append(KeypadRow(buttons=[
        Button(id="clear_failed", button_text="🗑️ پاک کردن لیست", type=ButtonTypeEnum.SIMPLE),
        Button(id="back_failed", button_text="🔙 بازگشت", type=ButtonTypeEnum.SIMPLE)
    ]))
    return Keypad(rows=rows, resize_keyboard=True)


@bot.on_update(filters.commands("failed") | filters.button(button_id="failed"))
@admin_only
async def cmd_failed(bot, update: Update) -> None:
    """
    نمایش لیست فیلم‌های ناموفق و تنظیم وضعیت برای انتخاب.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
    """
    await state_filter.clear_state_for(update)
    await clear_user_search_data(update.chat_id)

    failed_list = await asyncio.to_thread(get_all_failed_movies)
    if not failed_list:
        await update.reply("✅ هیچ فیلم ناموفقی در لیست وجود ندارد!", parse_mode="Markdown")
        await make_start_keypad(bot, update)
        return

    latest_failed = failed_list[:10]
    user_states.setdefault(update.chat_id, {})['failed_cache'] = latest_failed

    txt = "🚨 **لیست جدیدترین فیلم‌های ناموفق:**\n\n"
    for i, f in enumerate(latest_failed):
        err_type = f['error'].split(":::", 1)[0] if ":::" in f['error'] else f['error']
        txt += f"{i + 1}. **{f['title']}**\n   ❌ خطا: {err_type}\n\n"

    txt += "🔢 شماره فیلم مورد نظر را بفرستید:"
    await update.reply(txt, chat_keypad=make_failed_list_keyboard(len(latest_failed)),
                       chat_keypad_type=ChatKeypadTypeEnum.NEW, parse_mode="Markdown")
    await state_filter.set_state_for(update, "failed_selecting")


@bot.on_update(filters.text, filters.states("failed_selecting"))
@admin_only
async def select_failed_movie(bot, update: Update) -> None:
    """
    پردازش انتخاب کاربر از لیست فیلم‌های ناموفق.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
    """
    guid = update.chat_id
    txt = update.new_message.text.strip()
    cache = user_states.get(guid, {}).get('failed_cache')

    if txt in ["🔙 بازگشت", "❌ انصراف"]:
        await state_filter.clear_state_for(update)
        await clear_user_search_data(guid)
        await make_start_keypad(bot, update)
        return

    if txt == "🗑️ پاک کردن لیست":
        await asyncio.to_thread(clear_all_failed_movies)
        await update.reply("✅ لیست فیلم‌های ناموفق پاک شد.", parse_mode="Markdown")
        await state_filter.clear_state_for(update)
        await clear_user_search_data(guid)
        await make_start_keypad(bot, update)
        return

    if txt.isdigit():
        idx = int(txt) - 1
        if cache and 0 <= idx < len(cache):
            failed_item = cache[idx]
            user_states.setdefault(guid, {})['selected_failed'] = failed_item
            await show_failed_detail(bot, update, failed_item)
            await state_filter.set_state_for(update, "failed_detail")
            return

    await update.reply("⚠️ لطفاً فقط شماره گزینه را بفرستید یا از دکمه‌ها استفاده کنید.", parse_mode="Markdown")


async def show_failed_detail(bot, update: Update, failed_item: dict) -> None:
    """
    نمایش جزئیات خطا و کیبورد مربوطه برای فیلم ناموفق.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
        failed_item (dict): دیکشنری حاوی اطلاعات خطای فیلم.
    """
    err_parts = failed_item['error'].split(":::", 1)
    err_type = err_parts[0] if len(err_parts) > 0 else "Unknown"
    err_msg = err_parts[1] if len(err_parts) > 1 else failed_item['error']

    txt = f"📋 **جزئیات خطای فیلم:**\n"
    txt += f"🎬 **عنوان:** {failed_item['title']}\n"
    txt += f"❌ **نوع خطا:** {err_type}\n\n"

    if "MultipleSearchResultsError" in err_type:
        txt += f"⚠️ **توضیحات:**\n{err_msg}\n\n"
        txt += "🔢 **لطفاً ایندکس (شماره) گزینه مورد نظر خود را از لیست بالا وارد کنید تا ذخیره شود:**\n"
        txt += "(برای لغو `/cancel` را بفرستید)"
        keypad = Keypad(rows=[
            KeypadRow(buttons=[Button(id="cancel_failed", button_text="❌ انصراف", type=ButtonTypeEnum.SIMPLE)])
        ], resize_keyboard=True)

    elif "MovieNotFoundError" in err_type:
        txt += f"⚠️ **توضیحات:**\n{err_msg}\n\n"
        txt += "💡 **احتمالاً اسم فیلم را اشتباه وارد کرده‌اید یا فیلم در دیتابیس سایت منبع وجود ندارد.**\n"
        txt += "می‌توانید از بخش جستجو (`/search`) نام فیلم را اصلاح کنید."
        keypad = Keypad(rows=[
            KeypadRow(buttons=[
                Button(id="search_failed", button_text="🔍 جستجوی فیلم", type=ButtonTypeEnum.SIMPLE),
                Button(id="back_failed_list", button_text="🔙 بازگشت به لیست", type=ButtonTypeEnum.SIMPLE)
            ])
        ], resize_keyboard=True)

    elif "TimeoutError" in err_type or "PlaywrightTimeoutError" in err_type or "Timeout" in err_type:
        txt += f"⏳ **توضیحات:**\n{err_msg}\n\n"
        txt += "🔄 **خطای تایم‌اوت رخ داده است. لطفاً دوباره برای گرفتن لینک‌های این فیلم تلاش کنید.**\n"
        keypad = Keypad(rows=[
            KeypadRow(buttons=[
                Button(id="retry_failed", button_text="🔄 تلاش مجدد (آپدیت)", type=ButtonTypeEnum.SIMPLE),
                Button(id="back_failed_list", button_text="🔙 بازگشت به لیست", type=ButtonTypeEnum.SIMPLE)
            ])
        ], resize_keyboard=True)

    else:
        txt += f"⚠️ **توضیحات:**\n{err_msg}\n\n"
        keypad = Keypad(rows=[
            KeypadRow(
                buttons=[Button(id="back_failed_list", button_text="🔙 بازگشت به لیست", type=ButtonTypeEnum.SIMPLE)])
        ], resize_keyboard=True)

    await update.reply(txt, chat_keypad=keypad, chat_keypad_type=ChatKeypadTypeEnum.NEW, parse_mode="Markdown")


@bot.on_update(filters.text, filters.states("failed_detail"))
@admin_only
async def handle_failed_detail(bot, update: Update) -> None:
    """
    پردازش تعاملات کاربر در صفحه جزئیات فیلم ناموفق.

    Args:
        bot: کلاینت ربات.
        update (Update): آبجکت آپدیت.
    """
    guid = update.chat_id
    txt = update.new_message.text.strip()
    failed_item = user_states.get(guid, {}).get('selected_failed')

    if not failed_item:
        await state_filter.clear_state_for(update)
        await clear_user_search_data(guid)
        await make_start_keypad(bot, update)
        return

    err_parts = failed_item['error'].split(":::", 1)
    err_type = err_parts[0] if len(err_parts) > 0 else "Unknown"

    if txt in ["انصراف", "/cancel"]:
        await state_filter.clear_state_for(update)
        await cmd_failed(bot, update)
        return

    if "بازگشت به لیست" in txt:
        await state_filter.clear_state_for(update)
        await cmd_failed(bot, update)
        return

    if "جستجوی فیلم" in txt:
        await state_filter.clear_state_for(update)
        await cmd_search(bot, update)
        return

    if "تلاش مجدد (آپدیت)" in txt:
        await state_filter.clear_state_for(update)
        await update.reply("برای آپدیت مجدد، از دکمه آپدیت در منوی اصلی استفاده کنید.", parse_mode="Markdown")
        await make_start_keypad(bot, update)
        return

    if "MultipleSearchResultsError" in err_type:
        if txt.isdigit():
            index = int(txt) - 1
            await asyncio.to_thread(update_movie_index, failed_item['movie_id'], index)
            await asyncio.to_thread(delete_failed_movie_by_movie_id, failed_item['movie_id'])

            await update.reply(
                f"✅ ایندکس {index + 1} با موفقیت ذخیره شد و از لیست ناموفق‌ها حذف گردید.\nدر آپدیت بعدی با این ایندکس تلاش می‌شود.",
                parse_mode="Markdown")
            await state_filter.clear_state_for(update)
            await clear_user_search_data(guid)
            await make_start_keypad(bot, update)
            return
        else:
            await update.reply("⚠️ لطفاً فقط عدد ایندکس مورد نظر را وارد کنید.", parse_mode="Markdown")
            return

    await update.reply("⚠️ گزینه نامعتبر. لطفاً از دکمه‌ها استفاده کنید.", parse_mode="Markdown")


@bot.on_start()
async def start_notification_listener(bot_client):
    """
    راه‌اندازی تسک پس‌زمینه برای گوش‌دادن به صف نوتیفیکیشن‌ها.

    این تابع یک لوپ نامتناهی ایجاد می‌کند که پیام‌ها را از notification_queue
    دریافت کرده و به چت مقصد ارسال می‌نماید.

    Args:
        bot_client: کلاینت ربات برای ارسال پیام.
    """

    async def listener():
        log.info("👂 Listener started for notifications...")
        while True:
            try:
                # دریافت پیام از صف
                chat_id, msg = notification_queue.get(timeout=1)
                log.info(f"📩 Sending notification to {chat_id}: {msg[:50]}...")
                await bot_client.send_message(chat_id, msg)
                notification_queue.task_done()
            except queue.Empty:
                await asyncio.sleep(1)
            except Exception as e:
                log.error(f"❌ Error in notif queue: {e}")
                await asyncio.sleep(5)

    asyncio.create_task(listener())


