"""
ماژول ابزارهای کمکی (Utils) - پردازش پیام‌ها و مدیریت اسکریپرها
این ماژول مسئولیت‌های زیر را بر عهده دارد:
- استخراج اطلاعات فیلم از پیام‌های کانال (دو فرمت Type1 و Type2)
- تشخیص نوع پیام و اعتبارسنجی ساختار آن
- کش کردن و پیمایش پیام‌های کانال
- جایگزینی لینک‌های قدیمی با لینک‌های جدید در متن پیام‌ها
- مدیریت اسکریپرهای Playwright برای دریافت لینک‌های دانلود
- پیاده‌سازی مکانیزم Retry برای خطاهای شبکه و تایم‌اوت
"""

import time
import asyncio
import os
import re
import logging
from typing import Dict, List, Any, Optional
from database import (
    create_full_movie_type1,
    create_full_movie_type2,
    update_movie_links
)
from rubpy import utils
from templates import *
from scrapers.scraper_sample import (
    SampleMovieScraper,
    PlaywrightTimeoutError,
    MovieNotFoundError,
    MultipleSearchResultsError
)
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
headless_mode = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"


def my_captcha(sas) -> str:
    return "2"


def extract_message_type1_info(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    استخراج اطلاعات کامل فیلم از پیام‌های نوع ۱ (ساختار کیفیت‌محور چندگانه).

    این تابع پیام‌هایی را پردازش می‌کند که شامل چندین کیفیت و دو نسخه
    (زیرنویس/دوبله) هستند. خروجی به‌صورت ساختاریافته و گروه‌بندی‌شده برمی‌گردد.

    ساختار خروجی:
    {
      "movie_name": str,
      "source": str,  # 'scraper'
      "is_anime": bool,
      "online_watchable": bool,
      "versions": {
        "original": [{"quality": str, "links": List[str], "subtitle_link": List[str]}],
        "dubbed": [{"quality": str, "links": List[str]}]
      }
    }

    Args:
        message (Dict[str, Any]): دیکشنری حاوی متن و متادیتای پیام روبیکا.

    Returns:
        Dict[str, Any]: دیکشنری ساختاریافته حاوی اطلاعات استخراج‌شده فیلم.

    Raises:
        ValueError: در صورتی که هیچ نسخه‌ای (اصلی یا دوبله) استخراج نشود.
    """
    # TODO: طبق الگو خود تغییرش دهید
    text = message.get('text')
    meta_parts = message.get('metadata', {}).get('meta_data_parts', [])

    # بررسی وضعیت پخش آنلاین
    online_watchable = 'پخش آنلاین' in text

    # بررسی و استخراج نام فیلم و وضعیت انیمیشن
    movie_name = None
    is_anime = False
    if "(انیمیشن)" in text:
        is_anime = True
        text = text.replace("(انیمیشن)", "")

    m = re.search(r"فیلم\s+(.+?)\s*[🎭🍿]", text)
    if m:
        movie_name = m.group(1).strip()

    # محاسبه بازه کاراکتری هر خط برای نگاشت دقیق لینک‌ها
    lines = text.splitlines(keepends=True)
    line_spans = []
    idx = 0
    for line in lines:
        line_spans.append((idx, idx + len(line) - 1))
        idx += len(line)

    def get_line_index(char_index: int) -> Optional[int]:
        """تعیین شماره خط بر اساس اندیس کاراکتر در متن اصلی."""
        for i, (s, e) in enumerate(line_spans):
            if s <= char_index <= e:
                return i
        return None

    # یافتن الگوهای نسخه (کیفیت + نوع)
    version_pattern = re.compile(r"کیفیت\s*:?\s*(\d+)\s*p?\s+(زیرنویس|دوبله)")
    versions_raw = []
    for match in version_pattern.finditer(text):
        quality = match.group(1)
        vtype = match.group(2)
        line_idx = get_line_index(match.start())
        vtype = 'original' if vtype == 'زیرنویس' else 'dubbed'
        versions_raw.append({
            "quality": quality,
            "type": vtype,
            "line_idx": line_idx,
            "links": [],
            "subtitle_links": []
        })

    # پردازش لینک‌ها از متادیتا و تخصیص به نسخه‌های مربوطه
    source = None
    if meta_parts:
        for part in meta_parts:
            if part.get("type") != "Link":
                continue
            url = part.get("link", {}).get("hyperlink_data", {}).get("url")
            if not url:
                continue

            # TODO: اگه بیش از 1 اسکرپر داری
            # تشخیص منبع لینک
            if 'example1' in url and not source:
                source = "scraper1"
            elif not source and 'example2' in url:
                source = "scraper2"

            link_start = part["from_index"]
            link_end = link_start + part["length"]
            covered_text = text[link_start:link_end]

            # تشخیص لینک زیرنویس بر اساس متن یا پسوند فایل
            is_sub = False
            if re.search(r'(دانلود|لینک)\s+زیرنویس', covered_text):
                is_sub = True
            elif url.split('?')[-1].endswith('.srt') or '.str' in url:
                is_sub = True

            link_line = get_line_index(link_start)
            if link_line is None:
                continue

            # تخصیص لینک به نسخه مناسب (هم‌خط یا خط بعد)
            for ver in versions_raw:
                if ver["line_idx"] == link_line:
                    if is_sub and ver["type"] == "original":
                        ver["subtitle_links"].append(url)
                    else:
                        ver["links"].append(url)
                    break
                elif (ver["line_idx"] is not None and link_line == ver["line_idx"] + 1):
                    line_text = text[line_spans[link_line][0]:line_spans[link_line][1] + 1]
                    if "کیفیت" not in line_text:
                        if is_sub and ver["type"] == "original":
                            ver["subtitle_links"].append(url)
                        else:
                            ver["links"].append(url)
                        break

    # ساخت و مرتب‌سازی خروجی نهایی
    original_list = [{"quality": v["quality"], "links": v["links"], "subtitle_link": v["subtitle_links"]}
                     for v in versions_raw if v["type"] == "original"]
    dubbed_list = [{"quality": v["quality"], "links": v["links"]}
                   for v in versions_raw if v["type"] == "dubbed"]

    original_list.sort(key=lambda x: int(x["quality"]))
    dubbed_list.sort(key=lambda x: int(x["quality"]))

    return {
        "movie_name": movie_name,
        "source": source,
        "is_anime": is_anime,
        "online_watchable": online_watchable,
        "versions": {"original": original_list, "dubbed": dubbed_list}
    }


def extract_message_type2_info(message: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    استخراج اطلاعات ساده فیلم از پیام‌های نوع ۲ (تک‌کیفیتی).

    این تابع برای پیام‌هایی طراحی شده که فقط یک کیفیت و یک لینک دانلود دارند.

    Args:
        message (Dict[str, Any]): دیکشنری حاوی متن و متادیتای پیام روبیکا.

    Returns:
        Dict[str, Optional[str]]: دیکشنری شامل:
            - movie_name: نام فیلم (یا None)
            - quality: کیفیت (یا None)
            - source: منبع لینک ('scraper')
            - download_link: URL لینک دانلود (یا None)
    """
    # TODO: طبق الگوی خودتان تغییرش دهید
    text = message.get("text", "")
    metadata = message.get("metadata", {})

    # استخراج کیفیت
    quality_match = re.search(r'کیفیت\s+(\d+)', text)
    quality = quality_match.group(1) if quality_match else None

    # استخراج نام فیلم
    movie_match = re.search(r'فیلم\s+(.+?)(?:\s*[🎭🍿])', text)
    movie_name = movie_match.group(1).strip() if movie_match else None

    # استخراج لینک دانلود از متادیتا
    download_link = None
    meta_parts = metadata.get("meta_data_parts", [])
    for part in meta_parts:
        if part.get("type") == "Link":
            link_data = part.get("link", {}).get("hyperlink_data", {})
            download_link = link_data.get("url")
            if download_link:
                break

    # TODO: اگه بیش از 1 اسکرپر داری
    source = "scraper2" if 'example2' in (download_link or '') else "scraper1" if 'example' in (
            download_link or '') else None

    return {
        "movie_name": movie_name,
        "quality": quality,
        "source": source,
        "download_link": download_link
    }


def is_cinema_download_message(message: Dict[str, Any]) -> bool:
    """
    بررسی اینکه آیا پیام مربوط به دانلود مستقیم فیلم سینمایی است یا خیر.

    معیارهای تشخیص:
    - وجود متن و متادیتا
    - وجود عبارت "دانلود مستقیم با نرم" و عدم وجود "قسمت" (برای حذف سریال‌ها)
    - وجود حداقل یک لینک در بخش متادیتا

    Args:
        message (Dict[str, Any]): دیکشنری پیام.

    Returns:
        bool: True اگر پیام یک پست دانلود فیلم سینمایی باشد، در غیر این صورت False.
    """
    if message.get('text') and message.get('metadata'):
        text = message.get('text')
        meta_data_parts = message.get('metadata').get('meta_data_parts', [])

        has_link_in_meta = any(
            part.get('type') == 'Link' and part.get('link')
            for part in meta_data_parts
        )

        if ('دانلود مستقیم با نرم' in (text or '') and
                'قسمت' not in (text or '') and
                has_link_in_meta):
            return True
    return False


def check_type_message(message: Dict[str, Any]) -> Optional[int]:
    """
    تشخیص نوع ساختار پیام (۱: چندکیفیتی، ۲: تک‌کیفیتی).

    این تابع با بررسی کلمات کلیدی در اطراف لینک‌های متادیتا،
    نوع پیام را برای انتخاب تابع استخراج مناسب تعیین می‌کند.

    Args:
        message (Dict[str, Any]): دیکشنری پیام.

    Returns:
        Optional[int]: 
            - 1: پیام نوع اول (کیفیت‌های متعدد، زیرنویس/دوبله)
            - 2: پیام نوع دوم (تک‌کیفیت، لینک مستقیم)
            - None: پیام نامعتبر یا ناشناس
    """
    text = message.get('text')
    metadata = message.get('metadata') or {}
    meta_data_parts = metadata.get('meta_data_parts', [])

    if not meta_data_parts:
        return None

    quality_checker = ['زیرنویس', 'دوبله', 'دانلود زیرنویس']
    amd_checker = ['لینک دانلود', 'ADM', 'مستقیم']

    for meta_part in meta_data_parts:
        if meta_part.get('link'):
            from_index = meta_part.get('from_index')
            length = meta_part.get('length')
            # استخراج متن اطراف لینک برای تحلیل محتوا
            temp_text = text[from_index - 10:length + from_index - 3]

            if any(keyword in temp_text for keyword in quality_checker):
                return 1
            elif any(keyword in temp_text for keyword in amd_checker):
                return 2
    return None


def chach_all_message_in_channel(client, channel_guid: str,
                                 last_message_in_channel_guid: str = '0',
                                 limit: str = '25') -> List[Dict]:
    """
    دریافت و کش کردن تمام پیام‌های یک کانال به‌صورت پیمایشی (Pagination).

    این تابع با استفاده از حلقه while و پارامتر has_continue، تمام پیام‌های کانال
    را تا رسیدن به ابتدای تاریخچه دریافت می‌کند.

    Args:
        client: کلاینت روبیکا (حالت sync).
        channel_guid (str): شناسه یکتای کانال مقصد.
        last_message_in_channel_guid (str, optional): آخرین پیام دریافت‌شده برای ادامه پیمایش. پیش‌فرض '0'.
        limit (str, optional): تعداد پیام در هر درخواست. پیش‌فرض '25'.

    Returns:
        List[Dict]: لیست دیکشنری‌های حاوی اطلاعات تمام پیام‌های کانال.
    """
    all_messages = []

    # درخواست اولیه
    channel_messages = client.get_messages(channel_guid, last_message_in_channel_guid, limit)
    messages_dict = channel_messages.to_dict
    messages_list = messages_dict.get('messages')
    all_messages.extend(messages_list)

    new_max_id = messages_dict.get('new_max_id')
    has_continue = messages_dict.get('has_continue')

    # حلقه پیمایش تا انتهای کانال
    while has_continue:
        channel_messages = client.get_messages(channel_guid, new_max_id, limit)
        messages_dict = channel_messages.to_dict
        messages_list = messages_dict.get('messages')
        all_messages.extend(messages_list)
        new_max_id = messages_dict.get('new_max_id')
        has_continue = messages_dict.get('has_continue')

    return all_messages


def add_movies_in_message(message: Dict, channel_guid: str) -> Optional[str]:
    """
    پردازش یک پیام و افزودن فیلم(های) موجود در آن به دیتابیس.

    این تابع ابتدا نوع پیام را تشخیص داده، سپس اطلاعات را استخراج و
    با توجه به نوع پیام، رکورد مناسب را در دیتابیس ایجاد می‌کند.

    Args:
        message (Dict): دیکشنری پیام دریافتی از کانال.
        channel_guid (str): شناسه کانال مبدأ.

    Returns:
        Optional[str]: شناسه فیلم ایجادشده در دیتابیس، یا None در صورت عدم موفقیت.

    Raises:
        ValueError: اگر استخراج اطلاعات پیام نوع ۱ با شکست مواجه شود.
    """
    if is_cinema_download_message(message):
        # TODO: اگه بیش از یک قالب پیام دارید
        message_type = check_type_message(message)

        if message_type == 1:
            message_info = extract_message_type1_info(message)
            versions = message_info.get("versions")

            # اعتبارسنجی: حداقل یک نسخه باید وجود داشته باشد
            if len(versions.get('original', [])) == 0 and len(versions.get('dubbed', [])) == 0:
                raise ValueError("استخراج اطلاعات پیام با مشکل رو به رو شد...")

            movie_id = create_full_movie_type1(message_info, channel_guid, message.get('message_id'))
            return movie_id

        elif message_type == 2:
            message_info = extract_message_type2_info(message)
            movie_id = create_full_movie_type2(message_info, channel_guid, message.get('message_id'))
            return movie_id
    return None


async def get_last_message_in_channel(client, channel_guid: str, limit: int) -> Dict:
    """
    دریافت آخرین پیام منتشرشده در کانال (به‌صورت ناهمگام).

    Args:
        client: کلاینت روبیکا (حالت async).
        channel_guid (str): شناسه کانال.
        limit (int): محدوده جستجو برای یافتن آخرین پیام.

    Returns:
        Dict: دیکشنری حاوی اطلاعات آخرین پیام.
    """
    mess = await client.get_messages(channel_guid, max_id='0', limit=str(limit), sort='FromMax')
    messages = mess.to_dict
    # دسترسی به پیام در ایندکس limit (آخرین پیام در لیست مرتب‌شده)
    message = messages.get('messages')[int(limit)]
    return message


def get_text_type1(movie_info: Dict[str, Any], text: str) -> str:
    """
    تولید متن نهایی برای پیام‌های نوع ۱ با جایگزینی لینک‌های دانلود و زیرنویس.

    این تابع متن اصلی پیام را پیمایش کرده و لینک‌های جدید را در قالب
    Hyperlink و Bold روبیکا جایگزین پلاس‌هولدرهای قدیمی می‌کند.

    Args:
        movie_info (Dict[str, Any]): اطلاعات کامل فیلم شامل لینک‌های جدید.
        text (str): متن اصلی پیام در کانال.

    Returns:
        str: متن اصلاح‌شده با لینک‌های به‌روز و فرمت‌بندی Markdown.
    """
    movie = movie_info
    lines = text.splitlines()
    new_lines = []

    for line in lines:
        modified_line = line

        # 🔹 جایگزینی لینک دانلود فیلم بر اساس کیفیت و نوع
        for rel_type, rel_data in movie['releases'].items():
            qualities = rel_data.get('qualities', {})
            text_rel = 'دوبله' if rel_type == 'dubbed' else 'زیرنویس'

            for quality, q_info in qualities.items():
                placeholder = f"کیفیت {quality} {text_rel}"
                if placeholder in modified_line:
                    download_link = q_info.get('download_link', '').strip()
                    if download_link:
                        modified_line = modified_line.replace(
                            placeholder,
                            utils.Bold(utils.Hyperlink(placeholder, link=download_link))
                        )

        # 🔹 جایگزینی لینک زیرنویس
        if "دانلود زیرنویس" in modified_line:
            sub_link = None
            for rel_type, rel_data in movie['releases'].items():
                for quality, q_info in rel_data.get('qualities', {}).items():
                    subtitles = q_info.get('subtitles', [])
                    if subtitles and isinstance(subtitles, list) and len(subtitles) > 0:
                        potential_link = subtitles[0].get('download_link', '').strip()
                        if potential_link:
                            sub_link = potential_link
                            break
                if sub_link:
                    break

            if sub_link:
                modified_line = modified_line.replace(
                    "دانلود زیرنویس",
                    utils.Bold(utils.Hyperlink('دانلود زیرنویس', link=sub_link))
                )

        # 🎯 تشخیص هوشمند خطوط کیفیت برای فیلتر کردن یا حفظ آن‌ها
        is_quality_line = (
                ("کیفیت" in line and ("دوبله" in line or "زیرنویس" in line))
                or "دانلود زیرنویس" in line
        )

        if is_quality_line:
            # فقط خطوطی که لینک دریافت کردند اضافه می‌شوند
            if modified_line != line:
                new_lines.append(modified_line)
        else:
            # فرمت‌بندی خطوط توضیحات و ثابت
            if 'لینک دانلود مستقیم با نرم افزار ADM' in modified_line:
                modified_line = modified_line.replace(
                    'لینک دانلود مستقیم با نرم افزار ADM',
                    utils.Bold("لینک دانلود مستقیم با نرم افزار ADM")
                )
            if "MXPLAYR" in modified_line:
                modified_line = modified_line.replace("MXPLAYR", utils.Bold("MXPLAYR"))
            new_lines.append(modified_line)

    return "\n".join(new_lines)


def get_text_type2(movie_info: Dict[str, Any]) -> str:
    """
    تولید متن نهایی برای پیام‌های نوع ۲ با جایگزینی لینک دانلود.

    در این نوع پیام، اولویت با نسخه دوبله است و متن از تمپلیت ثابت تولید می‌شود.

    Args:
        movie_info (Dict[str, Any]): اطلاعات کامل فیلم.

    Returns:
        str: متن نهایی فرمت‌بندی‌شده برای ارسال در کانال.
    """
    movie = movie_info
    text = text_type2  # تمپلیت ثابت از ماژول templates

    releases = movie.get('releases', {})

    # اولویت‌بندی: دوبله > زیرنویس
    if 'dubbed' in releases:
        rel_type = 'dubbed'
    elif 'original' in releases:
        rel_type = 'original'
    else:
        return text

    qualities = releases.get(rel_type, {}).get('qualities', {})
    title = movie.get('title')

    # جایگزینی پلاس‌هولدرهای تمپلیت
    text = text.replace('title', title)

    download_link = None
    for key, val in qualities.items():
        text = text.replace('quality', f"{key}")
        download_link = val.get('download_link')

    if download_link:
        # ایجاد لینک هایپرلینک با فرمت صحیح روبیکا
        new_text = text.replace(
            'download_link',
            utils.Bold(utils.Hyperlink('لینک دانلود مستقیم با نرم افزار ADM', link=download_link))
        )
        return new_text
    return text


def change_movie_text_and_replace_link(client, movie: Dict[str, Any]) -> None:
    """
    ویرایش پیام اصلی در کانال با متن به‌روز و لینک‌های جدید.

    این تابع پیام قدیمی را از کانال خوانده، متن آن را با توابع get_text_type*
    بازنویسی کرده و با متد edit_message به‌روزرسانی می‌کند.

    Args:
        client: کلاینت روبیکا.
        movie (Dict[str, Any]): اطلاعات فیلم شامل chat_id و message_id.

    Note:
        از time.sleep برای رعایت Rate Limit روبیکا استفاده شده است.
    """
    message = client.get_messages_by_id(movie.get('chat_id'), movie.get('message_id'))
    message = message.to_dict.get('messages')[0]
    message_text = message.get('text')
    # TODO: اگه بیش از یک نوع قالب پیام دارید
    message_type = movie['message_type']

    # انتخاب تابع تولید متن بر اساس نوع پیام
    if message_type == 1:
        new_text = get_text_type1(movie, message_text)
    else:
        new_text = get_text_type2(movie)

    # ارسال درخواست ویرایش پیام
    client.edit_message(movie.get('chat_id'), movie.get('message_id'), new_text, 'markdown')
    time.sleep(1)


# -------------------------------------------------------------------
# توابع کمکی اسکریپر و مدیریت خطا
# -------------------------------------------------------------------
async def retry_on_timeout(
        func,
        max_retries: int = 5,
        delay: int = 5,
        *args,
        **kwargs
) -> Any:
    """
    اجرای مجدد یک تابع Async در صورت بروز خطاهای موقتی مانند Timeout.

    این تابع برای افزایش پایداری عملیات‌های شبکه‌ای و اسکرپینگ طراحی شده است.
    در صورت بروز PlaywrightTimeoutError یا سایر خطاهای قابل Retry،
    تابع تا تعداد مشخصی مجدداً اجرا خواهد شد.

    از آنجا که نسخه جدید اسکریپر به‌صورت Async پیاده‌سازی شده است،
    این تابع نیز به‌صورت Async عمل کرده و بین تلاش‌ها از
    asyncio.sleep استفاده می‌کند تا Event Loop بلاک نشود.

    رفتار خطاها:
    - PlaywrightTimeoutError → Retry
    - Exceptionهای عمومی → Retry
    - MovieNotFoundError → بدون Retry مجدداً Raise می‌شود
    - MultipleSearchResultsError → بدون Retry مجدداً Raise می‌شود

    Args:
        func: تابع Async که باید اجرا شود.
        max_retries (int, optional):
            حداکثر تعداد تلاش‌ها.
            پیش‌فرض 5.
        delay (int, optional):
            زمان انتظار بین هر تلاش بر حسب ثانیه.
            پیش‌فرض 5.
        *args:
            آرگومان‌های موقعیتی تابع.
        **kwargs:
            آرگومان‌های کلیدی تابع.

    Returns:
        Any:
            مقدار بازگشتی تابع در صورت موفقیت.

    Raises:
        MovieNotFoundError:
            اگر فیلم پیدا نشود.
        MultipleSearchResultsError:
            اگر جستجو چندین نتیجه مبهم داشته باشد.
        Exception:
            آخرین خطای رخ‌داده پس از اتمام تمام تلاش‌ها.

    Example:
        async def fetch_movie():
            return await get_new_links(movie)

        result = await retry_on_timeout(
            fetch_movie,
            max_retries=3,
            delay=10
        )
    """
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except PlaywrightTimeoutError as e:
            logger.warning(f"⚠️ تلاش {attempt}/{max_retries} با خطای Timeout مواجه شد.")
            last_exception = e
            await asyncio.sleep(delay)
        except (MultipleSearchResultsError, MovieNotFoundError):
            raise
        except Exception as e:
            logger.warning(f"⚠️ تلاش {attempt}/{max_retries} با خطای {e} مواجه شد.")
            last_exception = e
            await asyncio.sleep(delay)
    raise last_exception


async def _extract_links(scraper, full_movie: Dict, m: Dict, search_page) -> Dict:
    """
    تابع داخلی برای استخراج لینک‌های دانلود از صفحه جستجوی اسکریپر.

    این تابع برای هر کیفیت و هر نوع انتشار (اصلی/دوبله)، لینک دانلود
    و وضعیت زیرنویس را از اسکریپر دریافت کرده و در دیکشنری خروجی ذخیره می‌کند.

    Args:
        scraper: نمونه فعال‌شده SampleMovieScraper.
        full_movie (Dict): اطلاعات فیلم از دیتابیس.
        m (Dict): دیکشنری موقت برای ذخیره نتایج.
        search_page: آبجکت صفحه جستجو در اسکریپر.

    Returns:
        Dict: دیکشنری تو در تو حاوی لینک‌های استخراج‌شده.
    """
    for rel_type, rel_data in full_movie["releases"].items():
        qualities = rel_data.get("qualities", {})
        m_qu = {}
        for quality, q_info in qualities.items():
            has_sub = len(q_info.get("subtitles", [])) > 0
            link_info = await scraper.get_download_link(
                search_page,
                quality,
                rel_type,
                has_sub
            )
            m_qu[quality] = link_info
        m[rel_type] = m_qu
    return m


async def get_new_links(full_movie: Dict) -> Dict:
    """
    دریافت لینک‌های دانلود جدید برای یک فیلم با استفاده از اسکریپر.

    این تابع یک نشست جدید اسکریپر ایجاد کرده، لاگین می‌کند، فیلم را جستجو
    و لینک‌های دانلود را برای تمام کیفیت‌ها استخراج می‌نماید.

    Args:
        full_movie (Dict): اطلاعات کامل فیلم از دیتابیس.

    Returns:
        Dict: دیکشنری با ساختار { "نام فیلم": { "original/dubbed": { "quality": link_info } } }
    """
    result = {}
    m = {}
    # TODO: با اسکرپر خودتون جایگزین کنید
    if full_movie.get("source", "") == "scraper1":
        scraper1 = SampleMovieScraper(
            headless=headless_mode,
            storage_state_path=os.getenv("SCRAPER_AUTH_PATH", "auth.json")
        )
        async with scraper1:
            await scraper1.login(os.getenv("SCRAPER_USERNAME", "user"), os.getenv("SCRAPER_PASSWORD", "pass"))
            search_page = await scraper1.search_movie(full_movie)
            m = await _extract_links(scraper1, full_movie, m, search_page)
            result[full_movie['title']] = m
        return result
    else:
        scraper2 = SampleMovieScraper(
            headless=headless_mode,
            storage_state_path=os.getenv("SCRAPER_AUTH_PATH", "auth.json")
        )
        async with scraper2:
            await scraper2.login(os.getenv("SCRAPER_USERNAME", "user"), os.getenv("SCRAPER_PASSWORD", "pass"))
            search_page = await scraper2.search_movie(full_movie)
            m = await _extract_links(scraper2, full_movie, m, search_page)
            result[full_movie['title']] = m
        return result


async def ex_update_movie_links(full_movie: Dict) -> None:
    """
    تابع اصلی به‌روزرسانی لینک‌های یک فیلم (حالت عادی).

    این تابع با استفاده از مکانیزم retry_on_timeout، لینک‌های جدید را دریافت
    و در دیتابیس ذخیره می‌کند.

    Args:
        full_movie (Dict): اطلاعات فیلم برای به‌روزرسانی.
    """
    logger.info(f"{full_movie['title']} شروع به گرفتن لینک‌های جدید")

    async def temp():
        return await get_new_links(full_movie)

    movie_link = await retry_on_timeout(temp)
    success = await asyncio.to_thread(update_movie_links, full_movie, movie_link)

    logger.info(f"{full_movie['title']} با {'موفقیت به‌روزرسانی' if success else 'شکست مواجه'} شد...")


async def get_link_multiple_result(full_movie: Dict, index: int) -> Dict:
    """
    دریافت لینک‌های دانلود جدید با انتخاب دستی نتیجه از لیست جستجو.

    این تابع زمانی استفاده می‌شود که جستجوی خودکار چندین نتیجه داشته باشد
    و ادمین ایندکس نتیجه صحیح را مشخص کرده باشد.

    Args:
        full_movie (Dict): اطلاعات فیلم.
        index (int): ایندکس نتیجه انتخاب‌شده در صفحه جستجو.

    Returns:
        Dict: دیکشنری حاوی لینک‌های استخراج‌شده.
    """
    result = {}
    m = {}
    # TODO: با اسکرپر خودتون جایگزین کنید
    if full_movie.get("source", "") == "scraper1":
        scraper1 = SampleMovieScraper(
            headless=headless_mode,
            storage_state_path=os.getenv("SCRAPER_AUTH_PATH", "auth.json")
        )
        async with scraper1:
            await scraper1.login(os.getenv("SCRAPER_USERNAME", "user"), os.getenv("SCRAPER_PASSWORD", "pass"))
            try:
                search_page = await scraper1.search_movie(full_movie)
                m = await _extract_links(scraper1, full_movie, m, search_page)
            except MultipleSearchResultsError:
                # در صورت چندنتیجه‌ای بودن، از ایندکس انتخاب‌شده استفاده می‌شود
                search_page = await scraper1.select_search_result(full_movie, index)
                m = await _extract_links(scraper1, full_movie, m, search_page)
            result[full_movie['title']] = m
        return result
    else:
        scraper2 = SampleMovieScraper(
            headless=headless_mode,
            storage_state_path=os.getenv("SCRAPER_AUTH_PATH", "auth.json")
        )
        async with scraper2:
            await scraper2.login(os.getenv("SCRAPER_USERNAME", "user"), os.getenv("SCRAPER_PASSWORD", "pass"))
            try:
                search_page = await scraper2.search_movie(full_movie)
                m = await _extract_links(scraper2, full_movie, m, search_page)
            except MultipleSearchResultsError:
                # در صورت چندنتیجه‌ای بودن، از ایندکس انتخاب‌شده استفاده می‌شود
                search_page = await scraper2.select_search_result(full_movie, index)
                m = await _extract_links(scraper2, full_movie, m, search_page)
            result[full_movie['title']] = m
        return result


async def ex_update_movie_links_multiple(full_movie: Dict, index: int) -> None:
    """
    تابع اصلی به‌روزرسانی لینک‌های یک فیلم (حالت چندنتیجه‌ای).

    Args:
        full_movie (Dict): اطلاعات فیلم.
        index (int): ایندکس نتیجه انتخاب‌شده برای رفع ابهام جستجو.
    """
    logger.info(f"{full_movie['title']} شروع به گرفتن لینک‌های جدید (چندگانه)")
    movie_link = await retry_on_timeout(get_link_multiple_result, full_movie=full_movie, index=index)
    await asyncio.to_thread(update_movie_links, full_movie, movie_link)
