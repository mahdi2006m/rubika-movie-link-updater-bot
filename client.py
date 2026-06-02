"""
ماژول کلاینت ربات اتوماسیون روبیکا - مدیریت پیام‌های کانال
این ماژول مسئولیت‌های زیر را بر عهده دارد:
- کش کردن و استخراج فیلم‌ها از پیام‌های کانال
- افزودن فیلم‌های جدید به دیتابیس
- جایگزینی لینک‌های قدیمی با لینک‌های به‌روز در پیام‌ها
- مدیریت دستورات متنی ادمین (/get, /edit, /code, /index)
"""

from rubpy import Client, filters
from rubpy.bot.models import Update
from database import *
from utils import chach_all_message_in_channel, add_movies_in_message, change_movie_text_and_replace_link
import logging
import os
from dotenv import load_dotenv

import sys
import io

# تنظیم انکودینگ استاندارد برای خروجی‌های کنسول (پشتیبانی از کاراکترهای فارسی)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


load_dotenv()

# پیکربندی سیستم لاگ‌گیری
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(lineno)d - %(funcName)s- %(message)s ',
                    filename='client.log',  # ذخیره لاگ‌ها در فایل client.log
                    filemode='a',  # حالت الحاق (append) برای حفظ لاگ‌های قبلی
                    encoding='utf-8')
logging.getLogger('rubpy').setLevel(logging.WARNING)  # کاهش سطح لاگ‌های کتابخانه rubpy
logging.getLogger('asyncio').setLevel(logging.WARNING)  # کاهش سطح لاگ‌های asyncio
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

client = Client(os.getenv("CLIENT_SESSION_NAME"))

# بارگذاری متغیرهای محیطی مربوط به شناسه‌های کانال و کاربران
org_channel_guid = os.getenv("ORG_CHANNEL_GUID")
my_guid = os.getenv("MY_USER_GUID")
bot_guid = os.getenv("BOT_GUID")
channel_guid = os.getenv("CHANNEL_GUID")


# -------------------------------------------------------------------
# متدهای جداگانه برای هر دستور
# -------------------------------------------------------------------
def handle_get(update: Update) -> None:
    """
    هندلر دستور /get - استخراج و ذخیره فیلم‌ها از پیام‌های کانال.

    این تابع تمام پیام‌های کانال را اسکن کرده، اطلاعات فیلم‌ها را استخراج می‌کند
    و آن‌ها را در دیتابیس ذخیره می‌نماید.

    Args:
        update (Update): آبجکت آپدیت حاوی اطلاعات دستور دریافتی.

    Note:
        خطاهای رخ‌داده در سطح هر پیام لاگ می‌شوند اما اجرای کلی متوقف نمی‌شود.
    """
    try:
        log.info('فیلم ها دارن بارگزاری میشن...')
        # دریافت و کش کردن تمام پیام‌های کانال
        all_messages = chach_all_message_in_channel(client, channel_guid, '0')
        
        for message in all_messages:
            try:
                # پردازش و افزودن فیلم‌های موجود در هر پیام به دیتابیس
                add_movies_in_message(message, channel_guid)
            except Exception as e:
                log.info(f'ذخیره فیلم ها با خطای: {e}')
        
        log.info('فیلم ها با موفقیت داخل دیتا بیس ذخیره شدن')
    except Exception as e:
        log.info(f'ذخیره فیلم ها با خطای: {e}')


def handle_change(update: Update) -> None:
    """
    هندلر دستور /edit - به‌روزرسانی و جایگزینی لینک‌های فیلم‌ها در کانال.

    این تابع تمام فیلم‌های دیتابیس را پیمایش کرده و برای هر کدام،
    متن پیام اصلی در کانال را با لینک‌های جدید جایگزین می‌کند.

    Args:
        update (Update): آبجکت آپدیت حاوی اطلاعات دستور دریافتی.

    Note:
        در صورت بروز خطا برای یک فیلم خاص، فرآیند برای فیلم‌های بعدی ادامه می‌یابد.
    """
    try:
        log.info("تغییر شروع شد...")
        all_movies = get_all_movies()
        
        for movie in all_movies:
            movie_full = get_movie_full(movie['id'])
            try:
                # جایگزینی متن و لینک‌های فیلم در پیام کانال
                change_movie_text_and_replace_link(client, movie_full)
            except Exception as e:
                log.error(f"تغییر پیام {movie['id']}==>{movie['title']} با مشکل {e} رو به رو شد!")
        
        log.info(" لینک ها با موفقیت تغییر کردن")
    except Exception as e:
        log.error(f"تغییر لینک ها با مشکل {e} رو به رو شد!")


def handle_code(update: Update, text: str) -> None:
    """
    هندلر دستور /code - ذخیره کد کپچا در فایل متنی.

    این تابع کد دریافتی از دستور ادمین را استخراج کرده و در فایل
    `captcha_code.txt` ذخیره می‌کند تا توسط فرآیندهای دیگر قابل خواندن باشد.

    Args:
        update (Update): آبجکت آپدیت حاوی اطلاعات دستور.
        text (str): متن کامل پیام دریافتی شامل دستور /code.
    """
    # استخراج کد از متن دستور
    code = text.replace("/code", "").strip()
    
    # نوشتن کد در فایل
    with open("captcha_code.txt", "w") as f:
        f.write(code)
    
    log.info(f"کد {code} دریافت شد...")


# -------------------------------------------------------------------
# نقطهٔ ورودی اصلی که بین دستورها پخش می‌کنه (Dispatcher)
# -------------------------------------------------------------------
@client.on_message_updates(filters.text)
def dispatcher(update: Update) -> None:
    """
    تابع دیسپاچر اصلی - مسیریابی پیام‌های متنی به هندلرهای مربوطه.

    این تابع به‌عنوان نقطه ورودی برای تمام آپدیت‌های متنی عمل می‌کند و بر اساس
    محتوای پیام، آن را به تابع پردازش‌گر مناسب هدایت می‌نماید.

    دستورات پشتیبانی‌شده:
        - /get : استخراج و ذخیره فیلم‌ها از کانال
        - /edit : به‌روزرسانی لینک‌های فیلم‌ها در پیام‌های کانال
        - /code <value> : ذخیره کد کپچا

    Args:
        update (Update): آبجکت آپدیت حاوی پیام متنی دریافتی.

    Note:
        خط مربوط به بررسی bot_guid کامنت شده است. در صورت نیاز می‌توان آن را
        برای محدود کردن پاسخ‌دهی فقط به ربات خاص، فعال کرد.
    """
    # if update.object_guid != bot_guid:
    #     return

    text = update.text.strip()
    
    if text.startswith("/get"):
        handle_get(update)
    elif "/edit" in text:
        handle_change(update)
    elif text.startswith("/code"):
        handle_code(update, text)
