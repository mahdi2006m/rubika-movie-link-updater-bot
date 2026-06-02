"""
ماژول نمونه اسکریپر فیلم (Sample Movie Scraper) - الگوی پیاده‌سازی
این فایل یک کلاس پایه (Template) برای اسکریپرهای فیلم ارائه می‌دهد که:
- رابط برنامه‌نویسی (Interface) استاندارد برای استخراج لینک دانلود را تعریف می‌کند
- با استفاده از Playwright (همگام) پیاده‌سازی شده اما قابل جایگزینی با Selenium/Requests است
- شامل شبیه‌سازی (Mock) سناریوهای مختلف برای تست بدون نیاز به سایت واقعی است

🎯 راهنمای سریع برای توسعه‌دهندگان:
─────────────────────────────────────────────────────────
1️⃣ این کلاس را برای سایت مورد نظر خود Fork کنید
2️⃣ متدهای زیر را با منطق واقعی سایت هدف بازنویسی کنید:
   • login()        → احراز هویت و ذخیره Session/Cookie
   • search_movie() → جستجوی فیلم و مدیریت نتایج چندگانه
   • get_download_link() → استخراج لینک دانلود از صفحه فیلم
3️⃣ خطاهای اختصاصی (MovieNotFoundError, ...) را در مکان‌های مناسب raise کنید
4️⃣ از Context Manager (__enter__/__exit__) برای مدیریت منابع مرورگر استفاده کنید

🔧 ساختار پیشنهادی برای اسکریپر واقعی:
─────────────────────────────────────────────────────────
class MySiteScraper(SampleMovieScraper):
    BASE_URL = "https://mysite.com"

    def login(self, username, password, **kwargs):
        # پیاده‌سازی واقعی لاگین با Playwright/Selenium
        self.page.goto(f"{self.BASE_URL}/login")
        self.page.fill("#username", username)
        self.page.fill("#password", password)
        self.page.click("#login-btn")
        self.page.wait_for_load_state("networkidle")
        self.logged_in = True

    def search_movie(self, full_movie: dict):
        # جستجوی فیلم و بازگرداندن صفحه نتیجه
        query = full_movie.get('title') or full_movie.get('tags', [''])[0]
        self.page.goto(f"{self.BASE_URL}/search?q={query}")

        # مدیریت نتایج چندگانه
        results = self.page.query_selector_all(".movie-result")
        if len(results) == 0:
            raise MovieNotFoundError(query)
        elif len(results) > 1:
            titles = [r.text_content() for r in results[:5]]
            raise MultipleSearchResultsError(titles, query)

        return self.page  # یا آبجکت حاوی اطلاعات صفحه

    def get_download_link(self, search_page, quality, release, has_sub=False):
        # استخراج لینک دانلود بر اساس کیفیت و نوع انتشار
        # بازگرداندن دیکشنری با کلیدهای 'link' و 'sub_link'
        ...
"""

import time
import logging
from typing import Optional, Dict, Any, Callable

from playwright.sync_api import (
    sync_playwright,
    Playwright,
    Page,
    Browser,
    BrowserContext,
    TimeoutError as PlaywrightTimeoutError,
)
from database import update_movie_index
from scraper_errors import (
    MovieNotFoundError,
    MultipleSearchResultsError,
    LoginError,
    PlaywrightTimeoutError as PWTimeoutError
)

logger = logging.getLogger(__name__)


class SampleMovieScraper:
    """
    کلاس پایه اسکریپر فیلم - الگوی طراحی برای پیاده‌سازی اسکریپرهای واقعی.

    این کلاس با استفاده از الگوی Context Manager و رابط برنامه‌نویسی ثابت،
    امکان پیاده‌سازی اسکریپر برای سایت‌های مختلف را با حداقل تغییرات فراهم می‌کند.

    🔹 ویژگی‌های کلیدی:
    - پشتیبانی از Headless/Headed mode برای اجرا در سرور یا دیباگ محلی
    - ذخیره وضعیت احراز هویت (Storage State) برای جلوگیری از لاگین مکرر
    - مدیریت خودکار منابع مرورگر با __enter__/__exit__
    - لاگ‌گیری یکپارچه برای ردیابی عملیات و دیباگ

    🔹 چرخه حیات یک اسکریپر:
    ┌─────────────────────────────────────┐
    │ 1. with SampleMovieScraper() as s:  │
    │ 2. s.start()                        │ → راه‌اندازی مرورگر
    │ 3. s.login(...)                     │ → احراز هویت
    │ 4. page = s.search_movie(movie)     │ → جستجوی فیلم
    │ 5. links = s.get_download_link(...) │ → استخراج لینک
    │ 6. s.close()                        │ → آزادسازی منابع
    └─────────────────────────────────────┘

    ⚠️ نکته مهم برای توسعه‌دهندگان:
    این کلاس یک پیاده‌سازی Dummy است. برای استفاده در محیط واقعی،
    باید متدهای اصلی را با منطق تعامل با سایت هدف بازنویسی کنید.

    Attributes:
        headless (bool): اگر True باشد، مرورگر بدون رابط گرافیکی اجرا می‌شود.
        storage_state_path (str): مسیر فایل JSON برای ذخیره/بارگذاری Session مرورگر.
        logged_in (bool): وضعیت فعلی احراز هویت.
        playwright (Playwright, optional): نمونه Playwright فعال.
        browser (Browser, optional): نمونه مرورگر ایجادشده.
        context (BrowserContext, optional): زمینه مرورگر با کوکی‌ها و storage.
        page (Page, optional): صفحه اصلی برای تعامل با سایت.

    Example:
        >>> scraper = SampleMovieScraper(headless=True)
        >>> with scraper:
        ...     scraper.login("user", "pass")
        ...     page = scraper.search_movie({"title": "Inception"})
        ...     links = scraper.get_download_link(page, "1080", "original")
        ...     print(links['link'])
    """

    # ─────────────────────────────────────────────────────
    # ⚙️ پیکربندی و مقداردهی اولیه
    # ─────────────────────────────────────────────────────
    def __init__(
        self,
        headless: bool = True,
        storage_state_path: str = "auth.json",
        timeout: int = 30000,
        **kwargs
    ):
        """
        مقداردهی اولیه اسکریپر با تنظیمات پایه.

        این متد پیکربندی اولیه را انجام می‌دهد اما مرورگر را هنوز راه‌اندازی نمی‌کند.
        راه‌اندازی واقعی در متد `start()` و با ورود به Context Manager انجام می‌شود.

        Args:
            headless (bool, optional): اجرای مرورگر بدون رابط گرافیکی. پیش‌فرض True.
            storage_state_path (str, optional): مسیر فایل برای ذخیره Session. پیش‌فرض "auth.json".
            timeout (int, optional): تایم‌اوت عملیات‌های Playwright بر حسب میلی‌ثانیه. پیش‌فرض 30000.
            **kwargs: آرگومان‌های اضافی برای گسترش‌پذیری در کلاس‌های فرعی.

        Note:
            - فایل storage_state_path برای ذخیره کوکی‌ها و localStorage پس از لاگین موفق استفاده می‌شود.
            - در اجرای‌های مکرر، اگر این فایل وجود داشته باشد، مرورگر بدون نیاز به لاگین مجدد راه‌اندازی می‌شود.
        """
        self.headless = headless
        self.storage_state_path = storage_state_path
        self.timeout = timeout
        self.logged_in = False

        # متغیرهای داخلی برای مدیریت منابع Playwright
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # هویت‌های احراز هویت (در کلاس فرعی پر می‌شوند)
        self.username: Optional[str] = None
        self.password: Optional[str] = None

    # ─────────────────────────────────────────────────────
    # 🔄 مدیریت منابع با Context Manager
    # ─────────────────────────────────────────────────────
    def __enter__(self):
        """
        ورود به Context Manager - راه‌اندازی خودکار اسکریپر.

        این متد به‌طور خودکار `start()` را فراخوانی می‌کند تا اسکریپر
        برای استفاده آماده شود. امکان استفاده با دستور `with` را فراهم می‌کند.

        Returns:
            SampleMovieScraper: نمونه فعلی اسکریپر برای زنجیره‌سازی عملیات.

        Example:
            >>> with SampleMovieScraper() as scraper:
            ...     scraper.login("user", "pass")
            ...     # عملیات اسکراپینگ
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        خروج از Context Manager - پاک‌سازی خودکار منابع.

        این متد به‌طور خودکار `close()` را فراخوانی می‌کند تا منابع
        مرورگر و Playwright به‌درستی آزاد شوند، حتی در صورت بروز خطا.

        Args:
            exc_type: نوع استثنا (اگر رخ داده باشد).
            exc_val: مقدار استثنا.
            exc_tb: traceback استثنا.

        Returns:
            bool: False برای propagation خطاها به بیرون (رفتار پیش‌فرض).
        """
        self.close()
        # بازگرداندن False یعنی خطاها propagate شوند
        return False

    # ─────────────────────────────────────────────────────
    # 🚀 راه‌اندازی و بستن مرورگر
    # ─────────────────────────────────────────────────────
    def start(self) -> None:
        """
        راه‌اندازی مرورگر Playwright و آماده‌سازی زمینه اجرا.

        این متد:
        1. نمونه Playwright را ایجاد می‌کند
        2. مرورگر Chromium را با تنظیمات headless/headed راه‌اندازی می‌کند
        3. BrowserContext را با امکان ذخیره/بارگذاری storage_state پیکربندی می‌کند
        4. صفحه جدیدی برای تعامل با سایت باز می‌کند

        ⚠️ نکته برای پیاده‌سازی واقعی:
        در کلاس فرعی خود، می‌توانید:
        - از Firefox یا WebKit به جای Chromium استفاده کنید
        - Proxy، User-Agent یا سایر تنظیمات حریم خصوصی اضافه کنید
        - Extensionهای مورد نیاز را به context اضافه نمایید

        Raises:
            Exception: در صورت شکست در راه‌اندازی مرورگر.

        Example (پیاده‌سازی واقعی با Playwright):
            def start(self):
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(
                    headless=self.headless,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
                self.context = self.browser.new_context(
                    storage_state=self.storage_state_path if os.path.exists(self.storage_state_path) else None,
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
                )
                self.page = self.context.new_page()
                self.page.set_default_timeout(self.timeout)
        """
        logger.info("🚀 راه‌اندازی مرورگر نمونه (Dummy Mode)...")
        # در حالت Dummy، فقط لاگ می‌زنیم
        # در پیاده‌سازی واقعی، کدهای بالا را اینجا قرار دهید

    def close(self) -> None:
        """
        بستن مرورگر و آزادسازی تمام منابع مرتبط با Playwright.

        این متد باید حتماً پس از اتمام عملیات اسکراپینگ فراخوانی شود
        تا از نشت حافظه (Memory Leak) و باقی‌ماندن پروسه‌های مرورگر جلوگیری کند.

        ترتیب صحیح بستن منابع:
        1. بستن page (در صورت وجود)
        2. بستن context (حذف کوکی‌ها و storage موقت)
        3. بستن browser (خروج پروسه مرورگر)
        4. توقف playwright (پاک‌سازی نهایی)

        Note:
            استفاده از Context Manager (__enter__/__exit__) تضمین می‌کند
            که این متد حتی در صورت بروز خطا نیز فراخوانی می‌شود.

        Example (پیاده‌سازی واقعی):
            def close(self):
                if self.page:
                    self.page.close()
                if self.context:
                    self.context.close()
                if self.browser:
                    self.browser.close()
                if self.playwright:
                    self.playwright.stop()
                logger.info("✅ منابع مرورگر با موفقیت آزاد شدند")
        """
        logger.info("🛑 بستن مرورگر نمونه (Dummy Mode)...")
        # در حالت Dummy، فقط لاگ می‌زنیم
        # در پیاده‌سازی واقعی، کدهای بالا را اینجا قرار دهید

    # ─────────────────────────────────────────────────────
    # 🔐 احراز هویت (Login)
    # ─────────────────────────────────────────────────────
    def login(
        self,
        username: str,
        password: str,
        captcha_solver: Optional[Callable[[str], str]] = None
    ) -> bool:
        """
        انجام عملیات ورود (احراز هویت) به سایت منبع.

        این متد مسئولیت برقراری جلسه (Session) معتبر با سایت هدف را بر عهده دارد.
        پس از موفقیت، وضعیت `logged_in` روی True تنظیم شده و کوکی‌ها در
        `storage_state_path` ذخیره می‌شوند تا در اجرای‌های بعدی نیاز به
        لاگین مجدد نباشد.

        🔹 پارامترهای مهم:
        - captcha_solver: تابع اختیاری برای حل خودکار کپچا (در صورت نیاز سایت)

        🔹 رفتار مورد انتظار در پیاده‌سازی واقعی:
        1. پیمایش به صفحه لاگین سایت
        2. پر کردن فیلدهای username و password
        3. حل کپچا (در صورت وجود) با استفاده از captcha_solver
        4. کلیک روی دکمه ورود و انتظار برای لود صفحه اصلی
        5. بررسی موفقیت‌آمیز بودن لاگین (مثلاً با چک کردن وجود المان کاربر)
        6. ذخیره storage_state برای استفاده‌های بعدی

        Args:
            username (str): نام کاربری برای احراز هویت.
            password (str): رمز عبور مربوطه.
            captcha_solver (Callable, optional): تابعی که رشته کپچا را گرفته و حل‌شده را برمی‌گرداند.

        Returns:
            bool: True در صورت موفقیت در لاگین.

        Raises:
            LoginError: در صورت شکست در احراز هویت (رمز اشتباه، کپچا، مسدودی و...).

        Example (پیاده‌سازی واقعی با Playwright):
            def login(self, username, password, captcha_solver=None):
                self.page.goto(f"{self.BASE_URL}/login")

                # پر کردن فرم
                self.page.fill("#username-input", username)
                self.page.fill("#password-input", password)

                # مدیریت کپچا (در صورت وجود)
                if self.page.is_visible("#captcha-image"):
                    if not captcha_solver:
                        raise LoginError("کپچا نیاز است اما solver ارائه نشده")
                    captcha_text = self.page.locator("#captcha-image").screenshot()
                    solved = captcha_solver(captcha_text)
                    self.page.fill("#captcha-input", solved)

                # ارسال فرم و انتظار
                with self.page.expect_navigation():
                    self.page.click("#login-button")

                # بررسی موفقیت
                if not self.page.is_visible("#user-profile"):
                    raise LoginError("ورود ناموفق بود")

                # ذخیره session برای دفعات بعد
                self.context.storage_state(path=self.storage_state_path)
                self.logged_in = True
                return True
        """
        logger.info(f"🔐 تلاش برای ورود با کاربر: {username}")

        # شبیه‌سازی خطای لاگین برای تست
        if username == "invalid":
            raise LoginError("نام کاربری یا رمز عبور اشتباه است.")

        self.username = username
        self.password = password
        self.logged_in = True
        logger.info("✅ ورود موفقیت‌آمیز (شبیه‌سازی شده)")
        return True

    # ─────────────────────────────────────────────────────
    # 🔍 جستجوی فیلم
    # ─────────────────────────────────────────────────────
    def search_movie(self, full_movie: dict) -> Any:
        """
        جستجوی فیلم در سایت منبع بر اساس اطلاعات دیتابیس.

        این متد مسئولیت یافتن صفحه فیلم مورد نظر در سایت مقصد را بر عهده دارد.
        ورودی آن دیکشنری کامل فیلم از دیتابیس است و خروجی آن آبجکتی است
        که در متد `get_download_link` برای استخراج لینک استفاده می‌شود.

        🔹 استراتژی جستجوی پیشنهادی:
        1. اولویت با تگ دوم (معمولاً عنوان انگلیسی/دقیق‌تر)
        2. در صورت نبود، استفاده از تگ اول
        3. در نهایت استفاده از عنوان فارسی فیلم
        4. اعمال URL-encoding و حذف کاراکترهای خاص برای کوئری سالم

        🔹 مدیریت نتایج جستجو:
        - 0 نتیجه → raise MovieNotFoundError
        - 1 نتیجه → بازگرداندن صفحه/آبجکت آن فیلم
        - 2+ نتیجه → raise MultipleSearchResultsError با لیست عنوان‌ها

        Args:
            full_movie (dict): دیکشنری فیلم شامل کلیدهای:
                - 'title': عنوان اصلی فیلم
                - 'tags': لیست تگ‌ها (عنوان انگلیسی، سال، ژانر و...)
                - 'source': نام سایت منبع ('movielix' یا 'delfan')
                - 'index': ایندکس ذخیره‌شده برای رفع ابهام نتایج چندگانه (اختیاری)

        Returns:
            Any: آبجکتی که نماینده صفحه فیلم یافت‌شده است.
                 در پیاده‌سازی واقعی معمولاً یک Page یا Dict حاوی اطلاعات صفحه.

        Raises:
            MovieNotFoundError: اگر هیچ نتیجه‌ای برای کوئری یافت نشود.
            MultipleSearchResultsError: اگر چندین نتیجه مبهم یافت شود.
            PlaywrightTimeoutError: اگر عملیات جستجو بیش از حد طول بکشد.

        Example (پیاده‌سازی واقعی):
            def search_movie(self, full_movie: dict):
                # ساخت کوئری بهینه
                tags = full_movie.get('tags', [])
                query = tags[1] if len(tags) > 1 else (tags[0] if tags else full_movie['title'])
                query = urllib.parse.quote(query)

                # انجام جستجو
                self.page.goto(f"{self.BASE_URL}/search?q={query}")
                self.page.wait_for_selector(".results-container", timeout=10000)

                # استخراج نتایج
                results = self.page.query_selector_all(".movie-card")
                if not results:
                    raise MovieNotFoundError(query)

                if len(results) > 1:
                    titles = [r.locator(".title").text_content() for r in results[:10]]
                    raise MultipleSearchResultsError(titles, query)

                # کلیک روی نتیجه یگانه و انتظار برای لود صفحه فیلم
                with self.page.expect_navigation():
                    results[0].click()
                self.page.wait_for_load_state("networkidle")

                return self.page  # صفحه فیلم برای استخراج لینک
        """
        title = full_movie.get('title', '')
        logger.info(f"🔍 جستجوی فیلم: {title}")

        # ─────────────────────────────────────────────
        # 🎭 شبیه‌سازی سناریوهای مختلف برای تست
        # (این بخش در پیاده‌سازی واقعی حذف می‌شود)
        # ─────────────────────────────────────────────
        if "notfound" in title.lower():
            logger.warning(f"❌ شبیه‌سازی: فیلم '{title}' یافت نشد")
            raise MovieNotFoundError(title)

        if "multiple" in title.lower():
            logger.warning(f"⚠️ شبیه‌سازی: نتایج چندگانه برای '{title}'")
            fake_results = [f"{title} (2020)", f"{title} (2023)", f"{title} Remastered"]
            raise MultipleSearchResultsError(fake_results, title)

        # شبیه‌سازی تاخیر شبکه برای تست واقعی‌تر
        time.sleep(0.5)

        # در حالت Dummy، یک دیکشنری ساده برمی‌گردانیم
        # در پیاده‌سازی واقعی، آبجکت Page یا اطلاعات صفحه را برگردانید
        return {"page_id": "dummy_page_123", "movie_title": title}

    def select_search_result(self, movie: dict, index: int) -> Any:
        """
        انتخاب دستی نتیجه از لیست جستجوی چندگانه بر اساس ایندکس.

        این متد زمانی فراخوانی می‌شود که `search_movie` خطای
        `MultipleSearchResultsError` برگردانده باشد و ادمین ایندکس
        نتیجه صحیح را مشخص کرده باشد.

        🔹 جریان کاری پیشنهادی:
        1. انجام مجدد جستجو با همان کوئری
        2. دریافت لیست نتایج از صفحه
        3. اعتبارسنجی ایندکس (0 <= index < len(results))
        4. کلیک روی نتیجه انتخاب‌شده و انتظار برای لود صفحه فیلم
        5. (اختیاری) ذخیره ایندکس در دیتابیس برای استفاده‌های آینده

        Args:
            movie (dict): دیکشنری فیلم (همان ورودی search_movie).
            index (int): ایندکس نتیجه انتخاب‌شده توسط ادمین (0-based).

        Returns:
            Any: آبجکت نماینده صفحه فیلم انتخاب‌شده.

        Raises:
            IndexError: اگر ایندکس خارج از محدوده نتایج باشد.
            PlaywrightTimeoutError: اگر لود صفحه فیلم طول بکشد.

        Example (پیاده‌سازی واقعی):
            def select_search_result(self, movie: dict, index: int):
                # انجام مجدد جستجو
                tags = movie.get('tags', [])
                query = tags[1] if len(tags) > 1 else (tags[0] if tags else movie['title'])
                self.page.goto(f"{self.BASE_URL}/search?q={urllib.parse.quote(query)}")
                self.page.wait_for_selector(".movie-card")

                # دریافت و اعتبارسنجی نتایج
                results = self.page.query_selector_all(".movie-card")
                if not (0 <= index < len(results)):
                    raise IndexError(f"ایندکس {index} خارج از محدوده {len(results)} نتیجه")

                # کلیک روی نتیجه انتخاب‌شده
                selected = results[index]
                with self.page.expect_navigation():
                    selected.click()
                self.page.wait_for_load_state("networkidle")

                # ذخیره ایندکس برای دفعات بعد (اختیاری)
                update_movie_index(movie['id'], index)

                return self.page
        """
        movie_title = movie.get('title', 'Unknown')
        logger.info(f"🎯 انتخاب نتیجه شماره {index} برای فیلم: {movie_title}")

        # در حالت Dummy، فقط لاگ می‌زنیم و یک آبجکت ساختگی برمی‌گردانیم
        # در پیاده‌سازی واقعی، منطق بالا را اجرا کنید
        return {"page_id": f"dummy_page_{index}", "selected_index": index}

    # ─────────────────────────────────────────────────────
    # 🔗 استخراج لینک دانلود
    # ─────────────────────────────────────────────────────
    def get_download_link(
        self,
        search_page: Any,
        quality: str,
        release: str,
        has_sub: bool = False
    ) -> Dict[str, Optional[str]]:
        """
        استخراج لینک دانلود (و زیرنویس) برای کیفیت و نوع انتشار مشخص.

        این متد قلب اسکریپر است و مسئولیت یافتن لینک مستقیم دانلود
        فیلم با مشخصات درخواستی را در صفحه فیلم بر عهده دارد.

        🔹 پارامترهای ورودی:
        - quality: رشته کیفیت مورد نظر (مثلاً "480", "720", "1080")
        - release: نوع انتشار ("original" برای زیرنویس، "dubbed" برای دوبله)
        - has_sub: آیا برای نسخه original نیاز به لینک زیرنویس جداگانه هست؟

        🔹 خروجی مورد انتظار:
        دیکشنری با ساختار ثابت:
        {
            "link": "https://.../movie_720p.mp4",      # لینک دانلود فیلم (اجباری)
            "sub_link": "https://.../subtitle_720p.srt" # لینک زیرنویس (اختیاری)
        }

        🔹 استراتژی استخراج لینک پیشنهادی:
        1. یافتن تب/بخش مربوط به کیفیت مورد نظر در صفحه
        2. کلیک روی دکمه دانلود و انتظار برای ظاهر شدن لینک نهایی
        3. استخراج href از المان <a> یا intercept کردن درخواست شبکه
        4. (برای زیرنویس) جستجوی المان جداگانه یا پارامتر در همان لینک

        ⚠️ نکات فنی مهم:
        - برخی سایت‌ها لینک‌ها را با JavaScript و با تأخیر لود می‌کنند
        - ممکن است نیاز به intercept کردن درخواست‌های XHR/Fetch باشد
        - برخی لینک‌ها نیاز به Referer یا Cookie خاص دارند
        - لینک‌های دانلود ممکن است زمان‌دار (Expiring) باشند

        Args:
            search_page (Any): آبجکت صفحه فیلم (خروجی search_movie).
            quality (str): کیفیت مورد نظر برای دانلود.
            release (str): نوع انتشار ("original" یا "dubbed").
            has_sub (bool, optional): آیا نیاز به لینک زیرنویس جداگانه هست؟ پیش‌فرض False.

        Returns:
            Dict[str, Optional[str]]: دیکشنری حاوی:
                - 'link' (str): لینک مستقیم دانلود فیلم.
                - 'sub_link' (str|None): لینک زیرنویس (فقط برای release='original').

        Raises:
            PlaywrightTimeoutError: اگر المان دانلود در زمان مقرر ظاهر نشود.
            Exception: اگر ساختار صفحه با انتظار اسکریپر همخوانی نداشته باشد.

        Example (پیاده‌سازی واقعی با Playwright):
            def get_download_link(self, search_page, quality, release, has_sub=False):
                page = search_page  # در اینجا search_page همان Page است

                # انتخاب تب کیفیت مورد نظر
                quality_tab = page.locator(f".quality-btn[data-quality='{quality}']")
                quality_tab.click()
                page.wait_for_selector(".download-section", timeout=5000)

                # انتخاب نوع انتشار (دوبله/زیرنویس)
                release_selector = "dubbed" if release == "dubbed" else "subbed"
                release_btn = page.locator(f".release-type[data-type='{release_selector}']")
                release_btn.click()

                # انتظار برای ظاهر شدن لینک دانلود
                download_link_el = page.wait_for_selector(
                    "a.download-link",
                    state="visible",
                    timeout=10000
                )
                download_url = download_link_el.get_attribute("href")

                # استخراج لینک زیرنویس (در صورت نیاز)
                sub_url = None
                if has_sub and release == "original":
                    try:
                        sub_el = page.wait_for_selector(
                            "a.subtitle-link",
                            state="visible",
                            timeout=3000
                        )
                        sub_url = sub_el.get_attribute("href")
                    except PlaywrightTimeoutError:
                        logger.warning("⚠️ لینک زیرنویس یافت نشد")

                return {"link": download_url, "sub_link": sub_url}
        """
        logger.debug(
            f"🔗 دریافت لینک دانلود | کیفیت: {quality} | نوع: {release} | زیرنویس: {has_sub}"
        )

        # شبیه‌سازی تاخیر شبکه
        time.sleep(0.2)

        # ساخت لینک‌های Dummy برای تست
        dummy_link = f"https://example.com/download/{quality}_{release}.mp4"
        dummy_sub_link = (
            f"https://example.com/subtitles/{quality}_{release}.srt"
            if has_sub and release == "original"
            else None
        )

        return {
            "link": dummy_link,
            "sub_link": dummy_sub_link
        }
