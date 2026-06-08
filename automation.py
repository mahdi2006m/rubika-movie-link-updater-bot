"""
ماژول اصلی موتور اتوماسیون (Automation Engine)
این ماژول مسئولیت‌های زیر را بر عهده دارد:
- اجرای چرخه‌های زمان‌بندی‌شده اتوماسیون (Fetch → Update → Edit)
- مدیریت اتصال به کلاینت روبیکا و بررسی وضعیت آن
- ارسال نوتیفیکیشن‌های وضعیت به ادمین از طریق صف ربات
- مدیریت خطاها، آمار اجرایی و توقف ایمن (Graceful Shutdown)
- پیکربندی متمرکز پارامترها از طریق متغیرهای محیطی

چرخه اجرایی:
1. مرحله Fetch: دریافت پیام‌های جدید کانال و ذخیره در دیتابیس
2. مرحله Update: به‌روزرسانی لینک‌های دانلود فیلم‌ها از طریق اسکریپر
3. مرحله Edit: ویرایش پیام‌های کانال با لینک‌های جدید
"""

import threading
import time
import logging
import signal
import os
import asyncio
import queue
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

from database import get_all_movies, get_movie_full, add_failed_movie, init_db
from utils import (
    chach_all_message_in_channel, add_movies_in_message,
    change_movie_text_and_replace_link, ex_update_movie_links,
    ex_update_movie_links_multiple
)
from client import client, channel_guid
from scrapers.scraper_sample import MovieNotFoundError, MultipleSearchResultsError
from dotenv import load_dotenv

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
channel_guid = os.getenv("CHANNEL_GUID")

load_dotenv()

try:
    from bot import notification_queue, admin_chat_guid
except ImportError:
    notification_queue = None
    admin_chat_guid = os.getenv("ADMIN_CHAT_GUID")
    log.warning("⚠️ Could not import notification_queue from bot.py")


class Config:
    """
    کلاس پیکربندی متمرکز برای پارامترهای اتوماسیون.

    این کلاس مقادیر پیش‌فرض را از متغیرهای محیطی خوانده و در صورت عدم وجود،
    از مقادیر سخت‌کد شده استفاده می‌کند. تمام مقادیر به صورت float ذخیره می‌شوند.

    Attributes:
        CYCLE_INTERVAL_HOURS (float): فاصله زمانی بین اجرای چرخه‌های کامل اتوماسیون (ساعت).
        SKIP_RECENT_UPDATE_HOURS (float): حداقل فاصله زمانی برای به‌روزرسانی مجدد یک فیلم (ساعت).
        DELAY_BETWEEN_MOVIES (float): زمان تأخیر بین پردازش هر فیلم برای رعایت Rate Limit (ثانیه).
        DELAY_BETWEEN_STAGES (float): زمان تأخیر بین مراحل مختلف چرخه اتوماسیون (ثانیه).
    """

    CYCLE_INTERVAL_HOURS: float = float(os.getenv("AUTO_CYCLE_HOURS", 18.0))
    SKIP_RECENT_UPDATE_HOURS: float = float(os.getenv("SKIP_RECENT_UPDATE_HOURS", 10))
    DELAY_BETWEEN_MOVIES: float = float(os.getenv("DELAY_BETWEEN_MOVIES", 1.0))
    DELAY_BETWEEN_STAGES: float = float(os.getenv("DELAY_BETWEEN_STAGES", 5.0))


if not log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%H:%M:%S')
    )
    log.addHandler(handler)


class AutomationEngine:
    """
    موتور اصلی اتوماسیون برای مدیریت چرخه‌های دریافت، به‌روزرسانی و ویرایش فیلم‌ها.

    این کلاس مسئولیت‌های زیر را بر عهده دارد:
    - مدیریت وضعیت اجرای برنامه (running flag) و توقف ایمن
    - جمع‌آوری آمار اجرایی (تعداد فیلم‌های ذخیره‌شده، آپدیت‌شده، خطاها)
    - اجرای سه مرحله اصلی: Fetch → Update → Edit
    - ارسال نوتیفیکیشن به ادمین از طریق صف ربات
    - مدیریت سیگنال‌های سیستم برای Shutdown ایمن

    Attributes:
        running (bool): فلگ کنترل کننده حلقه اصلی اجرا.
        stats (Dict[str, int]): دیکشنری آمار اجرایی شامل کلیدهای saved, updated, edited, failed.
    """

    def __init__(self):
        """
        مقداردهی اولیه موتور اتوماسیون.

        تنظیم هندلرهای سیگنال برای مدیریت توقف ایمن و مقداردهی اولیه آمار.
        """
        self.running = True
        self.stats = {"saved": 0, "updated": 0, "edited": 0, "failed": 0}

        # ثبت هندلرهای سیگنال برای مدیریت graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame) -> None:
        """
        هندلر سیگنال‌های توقف (SIGINT/SIGTERM) برای خروج ایمن.

        این متد با تنظیم فلگ running به False، حلقه اصلی اجرا را متوقف می‌کند
        تا منابع به‌درستی آزاد شوند.

        Args:
            signum: شماره سیگنال دریافتی.
            frame: فریم فعلی اجرا (توسط سیستم عامل ارسال می‌شود).
        """
        log.info("🛑 دریافت سیگنال توقف. خروج ایمن...")
        self.running = False

    def _send_bot_notification(self, message: str) -> None:
        """
        ارسال پیام متنی به صف نوتیفیکیشن ربات برای اطلاع‌رسانی به ادمین.

        این متد پیام‌های وضعیت چرخه اتوماسیون (شروع، پایان، خطا) را از طریق
        notification_queue به ربات منتقل می‌کند تا برای ادمین ارسال شود.

        Args:
            message (str): متن پیام برای ارسال به ادمین (پشتیبانی از Markdown).

        Note:
            در صورت عدم ایمپورت صحیح notification_queue، خطا در لاگ ثبت می‌شود.
        """
        if notification_queue is None:
            log.error("❌ notification_queue is None! Check imports.")
            return

        try:
            log.info(f"📤 Putting message in queue for {admin_chat_guid}")
            notification_queue.put((admin_chat_guid, message))
            log.info("✅ Message put in queue successfully.")
        except Exception as e:
            log.error(f"❌ Error putting message in queue: {e}")

    async def _wait_for_client_ready(self, timeout: int = 60) -> bool:
        """
        انتظار برای آماده‌ شدن کلاینت روبیکا قبل از شروع عملیات.

        این متد با فراخوانی متد get_me در حلقه، از اتصال موفق کلاینت
        به سرورهای روبیکا اطمینان حاصل می‌کند.

        Args:
            timeout (int, optional): حداکثر زمان انتظار به ثانیه. پیش‌فرض 60.

        Returns:
            bool: True اگر کلاینت آماده شود، False در صورت رسیدن به تایم‌اوت.
        """
        log.info("⏳ در انتظار آماده‌سازی کلاینت روبیکا...")
        start = time.time()

        while time.time() - start < timeout:
            try:
                if hasattr(client, 'get_me'):
                    await asyncio.to_thread(client.get_me)
                    log.info("✅ کلاینت روبیکا متصل و آماده است.")
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
        log.warning("⚠️ کلاینت پس از ۶۰ ثانیه متصل نشد. ادامه با ریسک...")
        return False

    def _should_skip_update(self, movie: Dict) -> bool:
        """
        بررسی اینکه آیا فیلم مورد نظر به‌تازگی آپدیت شده و باید از پردازش رد شود یا خیر.

        این متد با مقایسه زمان آخرین به‌روزرسانی فیلم با پیکربندی
        SKIP_RECENT_UPDATE_HOURS، تصمیم به پردازش یا رد فیلم می‌گیرد.

        Args:
            movie (Dict): دیکشنری اطلاعات فیلم از دیتابیس.

        Returns:
            bool: True اگر فیلم باید رد شود (به‌روز است)، False اگر نیاز به آپدیت دارد.
        """
        update_at = movie.get('updated_at')
        if not update_at: return False
        try:
            last = datetime.strptime(update_at, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - last) < timedelta(hours=Config.SKIP_RECENT_UPDATE_HOURS)
        except Exception:
            return False

    async def stage_fetch_and_save(self) -> None:
        """
        مرحله ۱: دریافت پیام‌های کانال و ذخیره فیلم‌ها در دیتابیس.

        این مرحله:
        1. اتصال کلاینت را بررسی می‌کند
        2. تمام پیام‌های کانال را با pagination دریافت می‌کند
        3. هر پیام را پردازش و فیلم‌های موجود را در دیتابیس ذخیره می‌کند
        4. آمار فیلم‌های پردازش‌شده را به‌روز می‌کند

        Note:
            خطاهای سطح پیام لاگ می‌شوند اما اجرای مرحله متوقف نمی‌شود.
        """
        log.info("📥 مرحله ۱: دریافت و ذخیره پیام‌ها...")
        self.stats["saved"] = 0
        if not await self._wait_for_client_ready():
            log.error("❌ مرحله ۱ لغو شد: کلاینت آماده نیست.")
            return

        try:
            messages = await asyncio.to_thread(
                chach_all_message_in_channel, client, channel_guid, '0'
            )
            log.info(f"📦 {len(messages)} پیام دریافت شد.")

            for msg in messages:
                if not self.running: break
                try:
                    add_movies_in_message(msg, channel_guid)
                    self.stats["saved"] += 1
                except Exception as e:
                    log.debug(f"خطا در پردازش پیام: {e}")

            log.info(f"✅ مرحله ۱: {self.stats['saved']} فیلم جدید/تکراری پردازش شد.")
        except Exception as e:
            log.error(f"❌ خطای بحرانی در مرحله ۱: {e}")
        await asyncio.sleep(Config.DELAY_BETWEEN_STAGES)

    async def stage_update_links(self) -> None:
        """
        مرحله ۲: به‌روزرسانی لینک‌های دانلود فیلم‌ها از طریق اسکریپر.

        این مرحله برای هر فیلم در دیتابیس:
        1. بررسی می‌کند که آیا زمان آپدیت آن رسیده است یا خیر
        2. با استفاده از اسکریپر، لینک‌های جدید دانلود را دریافت می‌کند
        3. خطاهای مختلف (NotFound, MultipleResults) را مدیریت و ثبت می‌کند
        4. در صورت وجود index ذخیره‌شده، جستجوی چندنتیجه‌ای را مدیریت می‌کند

        Note:
            فیلم‌های با خطا در جدول failed_movies ثبت می‌شوند.
        """
        log.info("🔄 مرحله ۲: به‌روزرسانی لینک‌های دانلود...")
        self.stats["updated"] = 0
        self.stats["failed"] = 0

        all_movies = await asyncio.to_thread(get_all_movies)
        all_movies.reverse()

        for movie in all_movies:
            if not self.running: break
            if self._should_skip_update(movie): continue
            if self._should_skip_update(movie): continue
            full_movie = get_movie_full(movie['id'])
            if not full_movie:
                continue

            tags = full_movie.get('tags', [])
            query = tags[1] if len(tags) > 1 else (tags[0] if tags else full_movie['title'])

            try:
                await ex_update_movie_links(full_movie)
                self.stats["updated"] += 1
                log.info(f"✅ {full_movie['title']} آپدیت شد.")

            except MovieNotFoundError as e:
                await asyncio.to_thread(add_failed_movie, title=full_movie['title'], error=f"{type(e).__name__}: {e}",
                                        movie_id=full_movie['id'], search_query=query, source=full_movie.get('source'))
                self.stats["failed"] += 1
                log.warning(f"❌ {full_movie['title']} یافت نشد.")

            except MultipleSearchResultsError as e:
                await asyncio.to_thread(add_failed_movie, title=full_movie['title'], error=f"{type(e).__name__}: {e}",
                                        movie_id=full_movie['id'], search_query=query, source=full_movie.get('source'))
                self.stats["failed"] += 1
                log.warning(f"⚠️ {full_movie['title']} نتایج متعدد داشت.")

                if full_movie.get('index') is not None:
                    try:
                        await ex_update_movie_links_multiple(full_movie, full_movie['index'])
                        self.stats["updated"] += 1
                        log.info(f"✅ {full_movie['title']} با ایندکس {full_movie['index']} آپدیت شد.")
                    except Exception as ex:
                        log.error(f"❌ خطا در آپدیت ایندکسی {full_movie['title']}: {ex}")

            except Exception as e:
                await asyncio.to_thread(add_failed_movie, title=full_movie['title'], error=f"{type(e).__name__}: {e}",
                                        movie_id=full_movie['id'], search_query=query, source=full_movie.get('source'))
                self.stats["failed"] += 1
                log.error(f"❌ خطای ناشناخته برای {full_movie['title']}: {e}")

            await asyncio.sleep(Config.DELAY_BETWEEN_MOVIES)

        log.info(f"✅ مرحله ۲: {self.stats['updated']} آپدیت موفق | {self.stats['failed']} خطا")
        await asyncio.sleep(Config.DELAY_BETWEEN_STAGES)

    async def stage_edit_messages(self):
        """
        این مرحله پس از به‌روزرسانی لینک‌ها در دیتابیس، متن پیام‌های اصلی
        در کانال را با لینک‌های جدید جایگزین می‌کند تا کاربران به لینک‌های
        سالم دسترسی داشته باشند.

        Note:
            بین هر ویرایش 1.5 ثانیه تأخیر برای رعایت محدودیت‌های روبیکا اعمال می‌شود.
        """
        log.info("✏️ مرحله ۳: ویرایش پیام‌های کانال...")
        self.stats["edited"] = 0

        if not await self._wait_for_client_ready():
            log.error("❌ مرحله ۳ لغو شد.")
            return

        try:
            all_movies = await asyncio.to_thread(get_all_movies)
            for movie in all_movies:
                if not self.running: break
                try:
                    full = await asyncio.to_thread(get_movie_full, movie['id'])
                    if full:
                        await asyncio.to_thread(change_movie_text_and_replace_link, client, full)
                        self.stats["edited"] += 1
                        await asyncio.sleep(1.5)
                except Exception as e:
                    log.error(f"خطا در ویرایش {movie.get('title')}: {e}")
            log.info(f"✅ مرحله ۳: {self.stats['edited']} پیام ویرایش شد.")
        except Exception as e:
            log.error(f"❌ خطای مرحله ۳: {e}")

    async def run_cycle(self) -> None:
        """
        اجرای یک چرخه کامل اتوماسیون (شامل ۳ مرحله + گزارش‌دهی).

        این متد:
        1. زمان شروع را ثبت و نوتیفیکیشن شروع را ارسال می‌کند
        2. سه مرحله Fetch → Update → Edit را به ترتیب اجرا می‌کند
        3. در پایان، گزارش آماری کامل را به ادمین ارسال می‌کند
        4. خطاهای بحرانی را مدیریت و گزارش می‌کند
        """
        start_time_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        log.info(f"🚀 شروع چرخه اتوماسیون | {start_time_str}")

        start_msg = (
            f"🚀 **شروع چرخه اتوماسیون**\n"
            f"⏰ زمان: {start_time_str}\n"
            f"🔄 در حال دریافت پیام‌ها و آپدیت لینک‌ها..."
        )
        self._send_bot_notification(start_msg)

        self.stats = {"saved": 0, "updated": 0, "edited": 0, "failed": 0}

        try:
            await self.stage_fetch_and_save()
            await self.stage_update_links()
            await self.stage_edit_messages()

            end_msg = (
                f"🎉 **چرخه اتوماسیون پایان یافت**\n"
                f"⏰ زمان: {datetime.now().strftime('%H:%M')}\n\n"
                f"📥 ذخیره شده: {self.stats['saved']}\n"
                f"🔄 آپدیت شده: {self.stats['updated']}\n"
                f"✏️ ویرایش شده: {self.stats['edited']}\n"
                f"❌ خطاها: {self.stats['failed']}"
            )
            log.info("🎉 چرخه با موفقیت پایان یافت.")
            self._send_bot_notification(end_msg)

        except Exception as e:
            error_msg = f"💥 **خطای بحرانی در اتوماسیون**\n⏰ زمان: {datetime.now().strftime('%H:%M')}\n❌ خطا: {str(e)}"
            log.error(f"💥 خطای بحرانی در چرخه اصلی: {e}")
            self._send_bot_notification(error_msg)

    async def run(self) -> None:
        """
        حلقه اصلی اجرای اتوماسیون (توسط ترد جداگانه فراخوانی می‌شود).

        این متد به‌صورت نامتناهی چرخه‌های اتوماسیون را اجرا کرده و بین
        هر چرخه به میزان Config.CYCLE_INTERVAL_HOURS می‌خوابد.
        توقف با تنظیم self.running = False انجام می‌شود.
        """
        log.info(f"⏰ اتوماسیون فعال شد | چرخه هر {Config.CYCLE_INTERVAL_HOURS} ساعت")
        while self.running:
            start_time = time.time()
            await self.run_cycle()
            elapsed = time.time() - start_time
            sleep_time = max(0, (Config.CYCLE_INTERVAL_HOURS * 3600) - elapsed)

            if self.running and sleep_time > 0:
                hours = sleep_time / 3600
                log.info(f"😴 حالت خواب: {hours:.2f} ساعت دیگر...")
                await asyncio.sleep(sleep_time)

                for _ in range(int(sleep_time / 60)):
                    if not self.running:
                        break
                    time.sleep(60)

_engine: Optional[AutomationEngine] = None


def start_automation() -> None:
    """
    راه‌اندازی موتور اتوماسیون در یک ترد جداگانه (Non-blocking).

    این تابع:
    1. دیتابیس را مقداردهی اولیه می‌کند
    2. نمونه‌ای از AutomationEngine ایجاد می‌کند
    3. متد run را در یک ترد Daemon اجرا می‌کند

    Note:
        ترد ایجاد شده Daemon است، یعنی با پایان برنامه اصلی متوقف می‌شود.
    """
    global _engine
    init_db()
    _engine = AutomationEngine()

    def run_async_loop():
        asyncio.run(_engine.run())

    threading.Thread(target=run_async_loop, daemon=True, name="AutoThread").start()
    log.info("🧵 ترد اتوماسیون راه‌اندازی شد")


def stop_automation() -> None:
    """
    توقف ایمن موتور اتوماسیون.

    این تابع با تنظیم فلگ running به False، حلقه اصلی اتوماسیون را
    متوقف می‌کند تا چرخه جاری تکمیل شده و منابع آزاد شوند.
    """
    global _engine
    if _engine:
        _engine.running = False
        log.info("🛑 اتوماسیون متوقف شد")
