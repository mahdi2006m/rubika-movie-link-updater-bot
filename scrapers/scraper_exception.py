"""
ماژول خطاهای اختصاصی اسکریپر (Scraper Custom Exceptions)
این ماژول کلاس‌های استثنا (Exception) سفارشی را برای مدیریت خطاهای خاص
در فرآیند اسکراپینگ و تعامل با سایت‌های منبع تعریف می‌کند.

هدف از این خطاها:
- تفکیک خطاهای منطقی (مثل "فیلم یافت نشد") از خطاهای فنی (مثل Timeout)
- انتقال اطلاعات زمینه‌ای (مانند کوئری جستجو یا لیست نتایج) به لایه‌های بالاتر
- امکان مدیریت و واکنش متفاوت به هر نوع خطا در لایه‌های بالاتر (مثل ثبت در دیتابیس)
"""

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


class MovieNotFoundError(Exception):
    """
    استثنا برای زمانی که جستجوی فیلم در سایت منبع هیچ نتیجه‌ای برنگرداند.

    این خطا زمانی رخ می‌دهد که اسکریپر با استفاده از کوئری جستجو (عنوان یا تگ)
    به سایت منبع مراجعه کند، اما هیچ فیلمی با آن مشخصات پیدا نشود.

    Attributes:
        query_search (str): رشته جستجویی که منجر به این خطا شده است.

    Example:
        >>> try:
        ...     scraper.search_movie("فیلم_ناموجود_12345")
        ... except MovieNotFoundError as e:
        ...     print(f"جستجوی '{e.query_search}' ناموفق بود.")
    """

    def __init__(self, query_search: str):
        """
        مقداردهی اولیه استثنا با ذخیره کوئری جستجو.

        Args:
            query_search (str): عبارت جستجوشده که منجر به عدم یافتن فیلم شده است.
        """
        self.query_search = query_search
        super().__init__(f"Movie '{query_search}' not found.")


class MultipleSearchResultsError(Exception):
    """
    استثنا برای زمانی که جستجوی فیلم چندین نتیجه مبهم برگرداند.

    این خطا زمانی رخ می‌دهد که کوئری جستجو به جای یک نتیجه دقیق،
    چندین فیلم مشابه را برگرداند و اسکریپر نتواند به‌طور خودکار
    گزینه صحیح را تشخیص دهد. در این حالت نیاز به مداخله ادمین است.

    Attributes:
        titles (List[str]): لیست عنوان فیلم‌های یافت‌شده.
        query_search (str): رشته جستجویی که منجر به نتایج چندگانه شده است.

    Example:
        >>> try:
        ...     scraper.search_movie("جنگ ستارگان")
        ... except MultipleSearchResultsError as e:
        ...     print(f"برای '{e.query_search}' این نتایج یافت شد: {e.titles}")
        ...     # ادمین می‌تواند ایندکس صحیح را انتخاب کند
    """

    def __init__(self, titles: list, query_search: str):
        """
        مقداردهی اولیه استثنا با ذخیره لیست نتایج و کوئری جستجو.

        Args:
            titles (list): لیست رشته‌های عنوان فیلم‌های یافت‌شده.
            query_search (str): عبارت جستجوشده که منجر به نتایج چندگانه شده است.
        """
        self.titles = titles
        self.query_search = query_search
        super().__init__(f"Multiple results for '{query_search}': {titles}")


class LoginError(Exception):
    """
    استثنا برای خطاهای مربوط به فرآیند ورود (احراز هویت) به سایت منبع.

    این خطا زمانی رخ می‌دهد که اسکریپر نتواند با نام کاربری و رمز عبور
    ارائه‌شده به سایت منبع لاگین کند. دلایل احتمالی:
    - نام کاربری یا رمز عبور اشتباه
    - تغییر ساختار فرم لاگین در سایت مقصد
    - نیاز به حل کپچا یا تأیید دو مرحله‌ای
    - مسدود شدن اکانت یا IP

    Attributes:
        message (str, optional): پیام توضیحی اضافی درباره خطا.

    Example:
        >>> try:
        ...     scraper.login("user", "wrong_pass")
        ... except LoginError as e:
        ...     log.error(f"ورود به سایت منبع ناموفق بود: {e}")
    """
    # این کلاس از پیام پیش‌فرض Exception استفاده می‌کند
    # و می‌تواند در آینده برای ذخیره اطلاعات بیشتر گسترش یابد.
    pass