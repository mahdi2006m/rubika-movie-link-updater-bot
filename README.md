# 📚 README | بات اتوماتیک دانلود فیلم روبیکا

![Python](https://img.shields.io/badge/Python-3.14%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-Automation-purple)
![SQLite](https://img.shields.io/badge/SQLite-Database-blue)
![Windows](https://img.shields.io/badge/Windows-Supported-success)
![Linux](https://img.shields.io/badge/Linux-Supported-success)
![License](https://img.shields.io/badge/License-MIT-green)

> **سیستم یکپارچه برای استخراج، ذخیره‌سازی و به‌روزرسانی خودکار لینک‌های دانلود فیلم در کانال‌ روبیکا**

---

## 📋 فهرست محتویات

- **[🎯 معرّفی پروژه](#-معرّفی-پروژه)**
- **[⚡ راه‌اندازی سریع](#-راه‌اندازی-سریع)**
- **[✨ ویژگی‌های اصلی](#-ویژگی‌های-اصلی)**
- **[🏗️ معماری سیستم](#-معماری-سیستم)**
- **[🔍 اسکریپرها چگونه کار می‌کنند؟](#-اسکریپرها-چگونه-کار-میکنند)** 
- **[📦 راهنمای نصب](#-راهنمای-نصب)**
- **[🚀 راه‌اندازی](#-راه‌اندازی)**
- **[📖 راهنمای استفاده](#-راهنمای-استفاده)**
- **[⚠️ مدیریت خطاها](#-مدیریت-خطاها)**
- **[🔧 تنظیمات پیشرفته](#-تنظیمات-پیشرفته)**
- **[📝 ساختار دیتابیس](#-ساختار-دیتابیس)**
- **[🤝 مشارکت و توسعه](#-مشارکت-و-توسعه)**
- **[📜 لایسنس](#-لایسنس)**

---

## 🎯 معرّفی پروژه

این پروژه یک **بات اتوماتیک** برای اپدیت لینک های دانلود فیلم‌ سینمایی در پلتفرم **روبیکا** است.

### 🔹 هدف اصلی:
تجمیع پیام‌های دانلود فیلم از کانال‌ مورد نظر، پردازش اطلاعات، ذخیره در دیتابیس و به‌روزرسانی خودکار لینک‌های دانلود با استفاده از اسکریپرهای Playwright.

### 🎭 موارد استفاده:
- ✅ جمع‌آوری اطلاعات فیلم از یک کانال روبیکا
- ✅ ذخیره‌سازی متمرکز اطلاعات فیلم و لینک‌ها
- ✅ به‌روزرسانی خودکار لینک‌های دانلود
- ✅ مدیریت چندین سایت منبع
- ✅ پشتیبانی از کیفیت‌های مختلف و نسخه‌های دوبله/زیرنویس

---

## ⚡ راه‌اندازی سریع

برای استفاده از پروژه کافی است مراحل زیر را انجام دهید:

1. پروژه را Clone کنید.
2. وابستگی‌ها را نصب کنید.
3. فایل `.env` را پیکربندی کنید.
4. یک اسکریپر اختصاصی برای سایت مقصد خود پیاده‌سازی کنید.
5. فایل main.py را اجرا کنید.

پس از این مراحل، چرخه‌های خودکار به‌صورت زمان‌بندی‌شده اجرا خواهند شد.

---

## ✨ ویژگی‌های اصلی

### 🤖 اتوماسیون هوشمند
- **پردازش خودکار پیام‌ها**: تشخیص و استخراج اطلاعات از دو فرمت پیام مختلف
- **جستجوی اسکریپر**: یافتن خودکار فیلم در سایت‌های مقصد
- **مدیریت خطا**: راجع‌سازی خودکار و مدیریت حالات مختلف

### 📊 ذخیره‌سازی داده‌ها
- **دیتابیس SQLite**: ذخیره‌سازی ایمن و سریع اطلاعات
- **ساختار فلت**: نگاشت کامل میان فیلم و لینک‌های دانلود
- **تاریخچه تغییرات**: ثبت زمان به‌روزرسانی‌ها

### 🔐 قابلیت اطمینان
- **Thread-safe**: اجرای امن‌ترد‌های موازی
- **Graceful Shutdown**: توقف ایمن و تمیز برنامه
- **لاگ‌گیری یکپارچه**: ثبت جزئیات تمام عملیات

### 🎛️ کنترل دستی و پنل ادمین
- **دستورات ربات**: تعامل نزدیک با ادمین از طریق روبیکا
  - `/get` - دریافت اطلاعات فیلم
  - `/edit` - ویرایش اطلاعات
  - `/update` - اپدیت لینک ها در دیابیس
  - `/search` - جستوجوی حرفه ای فیلم های ذخیره شده داخل دیتابیس و تغییر اطلاعات
  - `/failed` - مدیریت و مشاهده خطا ها

### 🔍 سیستم اسکریپرها

- پشتیبانی از چندین اسکریپر مستقل
- امکان توسعه و افزودن سایت‌های جدید
- مدیریت خطاها در سطح هر اسکریپر
- قابلیت تغییر اسکریپر بدون تغییر هسته پروژه

---

## 🏗️ معماری سیستم

### 🔄 جریان‌های کاری (Workflows)

```
┌─────────────────────────────────────────────────────────┐
│                    MAIN ORCHESTRATOR                    │
│                 (main.py - Thread اصلی)                 │
└────────────────┬──────────────────────────────┬─────────┘
                 │                              │
         ┌───────▼────────┐         ┌───────────▼──────────┐
         │ AUTOMATION     │         │   RUBPY CLIENT       │
         │ ENGINE         │         │   (Async - Daemon)   │
         │ (Thread)       │         │                      │
         │                │         │ • Listen to channels │
         │ • Timer-based  │         │ • Cache messages     │
         │   jobs         │         │ • Extract metadata   │
         │ • Link refresh │         │ • Add to database    │
         │ • Maintenance  │         │                      │
         └────────────────┘         └──────────────────────┘
                 │                              │
         ┌───────▼──────────────────────────────▼─────────┐
         │             DATABASE (SQLite)                  │
         │  • Movies (فیلم‌ها)                            │
         │  • Releases (نسخه‌های دوبله/زیرنویس)          │
         │  • Qualities (کیفیت‌ها)                        │
         │  • Subtitles (زیرنویس‌ها)                      │
         │  • Failed_Movie (پیام‌های کانال)               │
         └────────────────────────────────────────────────┘
                        │
        ┌───────────────┴────────────────┐
        │                                │
   ┌────▼──────────┐         ┌───────────▼─────────┐
   │  SCRAPER      │         │   BOT HANDLER       │
   │  (Playwright) │         │   (Inline Commands) │
   │               │         │                     │
   │ • Search      │         │ • /get              │
   │ • Login       │         │ • /edit             │
   │ • Extract     │         │ • /code             │
   │   links       │         │ • Admin controls    │
   └───────────────┘         └─────────────────────┘
```

### 🔄 چرخه کامل سیستم
1. موتور اتوماسیون در زمان تعیین‌شده اجرا می‌شود.
2. کلاینت روبیکا پیام‌های جدید کانال را دریافت می‌کند.
3. اطلاعات فیلم از پیام استخراج می‌شود.
4. داده‌ها در دیتابیس ذخیره می‌شوند.
5. اسکریپر فیلم را در سایت مقصد جستجو می‌کند.
6. لینک‌های دانلود و اطلاعات موردنیاز استخراج می‌شوند.
7. دیتابیس با اطلاعات جدید به‌روزرسانی می‌شود.
8. کلاینت پیام فیلم در کانال ویرایش و بروزرسانی می‌شود.
9. نتیجه عملیات در لاگ‌ها ثبت می‌شود.
10. چرخه در بازه زمانی بعدی مجدداً تکرار می‌شود.


### 📁 ساختار پروژه

```
project/
├── main.py                    # 🎯 نقطه ورود اصلی
├── database.py                # 💾 مدیریت دیتابیس SQLite
├── bot.py                     # 🤖 ربات روبیکا و دستورات
├── client.py                  # 📡 کلاینت(تبچی) روبیکا (Listen)
├── automation.py              # ⚙️ موتور اتوماسیون
├── utils.py                   # 🛠️ توابع کمکی
├── templates.py               # 📝 قالب‌های پیام
├── scrapers/
│   ├── scraper_sample.py      # 🔍 مثال ساده ای از اسکرپر
│   ├── scraper_errors.py      # ⚠️ خطا های مدیریتی
│   └── [دیگر اسکریپرها]
├── logs/
│   └── app.log                # 📋 لاگ‌های برنامه
├── auth/
│   └── scraper_auth.json      # 🔑 فایل ذخیره سشن(نشست) اسکرپر
├── .env                       # 🔐 متغیرهای محیطی
├── requirements.txt           # 📦 وابستگی‌های Python
└── README.md                  # 📚 این فایل
```

---
## 🚨 **توجه**
>
> این پروژه فقط زیرساخت مدیریت، ذخیره‌سازی و به‌روزرسانی لینک‌ها را فراهم می‌کند.
>
> اسکریپر موجود در مسیر `scrapers/scraper_sample.py` صرفاً یک نمونه نمایشی (Template) است و **به‌صورت پیش‌فرض کار نمی‌کند**. قبل از اجرای پروژه باید حداقل یک اسکریپر اختصاصی برای سایت موردنظر خود ایجاد و پیاده‌سازی کنید.
>
> تمامی بخش‌های مربوط به ورود به سایت، جستجوی فیلم، مدیریت نتایج و استخراج لینک‌های دانلود باید توسط توسعه‌دهنده تکمیل شوند. در غیر این صورت امکان دریافت یا به‌روزرسانی لینک‌های دانلود وجود نخواهد داشت.
>
> هر سایت ساختار HTML و مکانیزم احراز هویت مخصوص خود را دارد؛ بنابراین معمولاً برای هر سایت باید یک اسکریپر جداگانه پیاده‌سازی شود.

---

## 🔍 اسکریپرها چگونه کار می‌کنند؟

اسکریپرها مسئول ارتباط با سایت منبع و استخراج لینک‌های دانلود هستند.

این پروژه هیچ اسکریپر آماده‌ای برای سایت‌های واقعی ارائه نمی‌دهد و هر توسعه‌دهنده باید اسکریپر مخصوص سایت خود را پیاده‌سازی کند.

هر اسکریپر معمولاً وظایف زیر را بر عهده دارد:

- ورود به سایت (Login)
- جستجوی فیلم
- مدیریت نتایج چندگانه
- استخراج لینک دانلود کیفیت‌های مختلف و زیرنویس ها
- مدیریت خطاهای سایت

جریان کاری اسکریپر:

Movie
↓
Search Movie
↓
Movie Page
↓
Extract Download Links
↓
Save To Database
↓
Update Channel Message

---

## 📦 راهنمای نصب

### 🪟 **نصب روی Windows**

#### **مرحله 1: نصب Python**

```powershell
# دانلود نسخه آخر Python از https://www.python.org/downloads/
# در هنگام نصب فعال کنید: ✓ Add Python to PATH

# تأیید نصب
python --version
pip --version
```

#### **مرحله 2: Clone و Setup پروژه**

```powershell
# 1. فولدر کاری را انتخاب کنید
cd D:\projects\  # یا هر مسیری دیگر

# 2. Clone کنید
git clone https://github.com/mahdi2006m/rubika-movie-link-updater-bot.git
cd rubika-movie-link-updater-bot

# 3. محیط مجازی
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# اگر خطای execution policy داشتید:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 4. نصب وابستگی‌ها
pip install --upgrade pip
pip install -r requirements.txt
```

#### **مرحله 3: پیکربندی**

```powershell
# 1. فایل .env را ایجاد کنید
copy .env.example .env

# 2. فایل را در Notepad ویرایش کنید
notepad .env

3. ایجاد فولدر های لازم
mkdir auth data logs

```

#### **مرحله 4: نصب Playwright Browsers**

```bash
# در صورت نیاز (برای اولین بار)
playwright install chromium
```

#### **مرحله 5: تست اولیه**

```powershell
# اجرای برنامه
python main.py

# انتظار ببرید برای لاگ موفقیت:
# 🚀 شروع راه‌اندازی یکپارچه ربات و اتوماسیون...
# ✅ دیتابیس آماده است.
# ✅ موتور اتوماسیون در پس‌زمینه فعال شد.
```

---

### 🐧 **نصب روی Linux/Ubuntu**

#### **مرحله 1: نصب وابستگی‌های سیستم**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y \
    python3.14 \
    python3.14-venv \
    python3.14-dev \
    build-essential \
    libssl-dev \
    libffi-dev \
    git \
    curl

# CentOS/RHEL
sudo dnf install -y python3.11 python3.11-devel gcc openssl-devel libffi-devel

# Alpine Linux (برای Docker)
apk add --no-cache python3 py3-pip build-base libffi-dev openssl-dev
```

#### **مرحله 2: Clone و Setup**

```bash
# 1. فولدر کاری
mkdir -p ~/projects
cd ~/projects

# 2. Clone
git clone https://github.com/mahdi2006m/rubika-movie-link-updater-bot.git
cd rubika-movie-link-updater-bot

# 3. محیط مجازی
python3.14 -m venv .venv
source .venv/bin/activate

# 4. نصب وابستگی‌ها
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

#### **مرحله 3: پیکربندی**

```bash
# 1. کپی .env
cp .env.example .env

# 2. ویرایش
nano .env
# یا
vim .env

3. ایجاد دایکتوری های لازم
mkdir auth data logs
```

#### **مرحله 4: اجرای پس‌زمینه (Systemd)**

```bash
# 1. فایل service را ایجاد کنید
sudo nano /etc/systemd/system/rubika-movie-link-updater-bot.service
```

```ini
[Unit]
Description=Rubika Movie Link Updater Bot - Rubika Downloader
After=network.target
StartLimitInterval=200
StartLimitBurst=5

[Service]
Type=simple
User=pi                          # یا username خود
WorkingDirectory=/home/pi/rubika-movie-link-updater-bot
Environment="PATH=/home/pi/rubika-movie-link-updater-bot/venv/bin"
ExecStart=/home/pi/rubika-movie-link-updater-bot/venv/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# 2. فعال‌سازی
sudo systemctl daemon-reload
sudo systemctl enable rubika-movie-link-updater-bot
sudo systemctl start rubika-movie-link-updater-bot

# 3. مشاهده وضعیت
sudo systemctl status rubika-movie-link-updater-bot

# 4. مشاهده لاگ
sudo journalctl -u rubika-movie-link-updater-bot -f
```

#### **مرحله 5: نصب Playwright Browsers**

```bash
# در صورت نیاز (برای اولین بار)
python -m playwright install chromium
```

---

## 🚀 راه‌اندازی

### ✅ پیکربندی اولیه (.env)

```bash
# ================================
# 🔑 TOKENS & SESSIONS
# ================================
BOT_TOKEN="Your_bot_token"                                # توکن ربات دریافت شده از @BotFather
CLIENT_SESSION_NAME="Your_session_name"                   # فایل ذخیره سشن(نشست) روبیکا

# ================================
# 🆔 GUIDs (روبیکا)
# ================================
CLIENT_CHAT_GUID="Chat_guid_between_bot_and_client"       # guid چته بات و کلایت(تبچی)
ADMIN_CHAT_GUID="Chat_guid_between_bot_and_admin"         # guid چته بات و ادمین
CHANNEL_GUID="Channel_guid_in_client"                     # guid چنل مورد نظر
BOT_GUID="Your_bot_guid"                                  # guid بات
MY_USER_GUID="Your_client_guid"                           # guid کلاینت(تبجی)

# ================================
# 🗄️ DATABASE
# ================================
DB_PATH="./data/your_DB_name.db"                          # اسم دیتابیس

# ================================
# 🔐 SCRAPER CREDENTIALS
# ================================
SCRAPER_USERNAME="username"                               # نام کاربری برای ورود به سایت
SCRAPER_PASSWORD="password"                               # رمز عبور برای ورود به سایت

# ================================
# 🌐 SCRAPER SETTINGS
# ================================
PLAYWRIGHT_HEADLESS=false                                 # آیا مرورگر در پشت صحنه باز بشه؟
PLAYWRIGHT_CHANNEL="chromium"                               # میتونه هر مرورگری باشه
SCRAPER_AUTH_PATH="./auth/scraper_auth.json"              # آدرس ذخیره شدن سشن(نشست) سایت
SCRAPER_BASE_URL="https://scraper.com"                    # آدرس سایت

# ================================
# ⚙️ AUTOMATION SETTINGS
# ================================
AUTO_CYCLE_HOURS=15.0                                      # فاصله زمانی بین هر چرخه (به ساعت)
SKIP_RECENT_UPDATE_HOURS=10.0                             # نادیده گرفتن فیلم‌های آپدیت‌شده در X ساعت گذشته
DELAY_BETWEEN_MOVIES=3.0                                   # فاصله اپدیت بین هر فیلم (به ثانیه)
DELAY_BETWEEN_STAGES=5.0                                  # فاصله بین هر مرحله (به ثانیه)

# ================================
# 📊 LOGGING
# ================================
LOG_LEVEL=INFO                                             # لول لاگ ها
LOG_FILE_PATH=./logs/log.log                               # ادرس لاگ گیری
```

### 🎯 اجرای اول

#### **Windows:**
```powershell
.\venv\Scripts\activate
python main.py
```

#### **Linux:**
```bash
source venv/bin/activate
python main.py
```

### 📊 مشاهده لاگ‌ها

```bash
# Windows
type logs\log.log

# Linux
tail -f logs/log.log

# یا در Real-time
python -m tail -f logs/log.log
```

---
## 📖 راهنمای استفاده

### 🤖 دستورات ربات

برای استفاده از دستورات مدیریتی، ادمین باید از طریق چت اختصاصی ربات اقدام کند.

### 1️⃣ `/get`

استخراج فیلم‌های موجود در کانال و ذخیره آن‌ها در دیتابیس.

```text
/get
```

**کاربردها:**

* دریافت فیلم‌های جدید کانال
* همگام‌سازی دیتابیس با محتوای کانال
* بازیابی اطلاعات در صورت خالی بودن دیتابیس

---

### 2️⃣ `/update`

اجرای دستی فرآیند به‌روزرسانی لینک‌های دانلود.

```text
/update
```

**کاربردها:**

* اجرای فوری چرخه آپدیت
* دریافت مجدد لینک‌های دانلود از سایت مقصد
* بروزرسانی اطلاعات ذخیره‌شده در دیتابیس

---

### 3️⃣ `/edit`

ویرایش اطلاعات یک فیلم ذخیره‌شده.

```text
/edit
```

**کاربردها:**

* اصلاح اطلاعات اشتباه
* ویرایش لینک‌ها
* بازسازی پیام فیلم در کانال

---

### 4️⃣ `/search`

جستجوی پیشرفته در میان فیلم‌های ذخیره‌شده.

```text
/search
```

**کاربردها:**

* پیدا کردن فیلم‌ها
* مشاهده اطلاعات ذخیره‌شده
* ویرایش سریع رکوردها

---

### 5️⃣ `/failed`

مدیریت فیلم‌های ناموفق.

```text
/failed
```

**کاربردها:**

* مشاهده فیلم‌های دارای خطا
* انتخاب نتیجه صحیح در جستجوهای چندگانه
* بررسی علت خطاها


---

### 🔄 جریان کاری خودکار

#### **1. شنوایی کانال (Listening)**
```
بات با شروع هر چرخه کانال را چک می‌کند
↓
پیام‌های جدید را استخراج می‌کند
↓
فرمت را تشخیص می‌دهد (Type1 یا Type2)
↓
اطلاعات را استخراج می‌کند
↓
به دیتابیس اضافه می‌کند
```

#### **2. بروزرسانی خودکار (Auto-Update)**
```
هر X(خودتان داخل .env تعریف میکنید) ساعت:
├─ تمام فیلم‌ها را بررسی می‌کند
├─ اسکریپر را اجرا می‌کند
├─ لینک‌های جدید را دریافت می‌کند
├─ پیام‌های اصلی را در کانال ویرایش می‌کند
└─ لاگ‌ها را ذخیره می‌کند
```

---

## ⚠️ مدیریت خطاها

### 🔴 خطاهای شایع و حل‌های آن

#### **1. خطای `ModuleNotFoundError`**
```
❌ ModuleNotFoundError: No module named 'rubpy'
```

**حل:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
# اگر باز هم حل نشد:
pip install --force-reinstall rubpy
```

---

#### **2. خطای `Playwright TimeoutError`**
```
❌ PlaywrightTimeoutError: page.goto: Timeout 30000ms exceeded
```

**علل و حل:**
```
علت 1: سایت منبع پاسخ نمی‌دهد
→ بررسی وضعیت سایت

علت 2: اتصال اینترنت ضعیف
→ تکرار برنامه خودکار است (Max Retries: 5)

علت 3: بلاکه شدن IP
→ تغییر IP یا استفاده از VPN

علت 4: نیاز به کپچا
→ کپچا Solver اضافه کنید
```

---

#### **3. خطای `LoginError`**
```
❌ LoginError: نام کاربری یا رمز عبور اشتباه است
```

**حل:**
```
✓ نام کاربری و رمز را در .env چک کنید
✓ بررسی کنید که ورود دستی موفق است
✓ اگر 2FA فعال است، کپچا solver اضافه کنید
✓ صفحه لاگین سایت تغییر کرده باشد → به‌روزرسانی اسکریپر لازم است
```

---

#### **4. خطای `MovieNotFoundError`**
```
❌ MovieNotFoundError: فیلم 'Inception' یافت نشد
```

**حل:**
```
✓ تگ های فیلم را جابجا کنید
✓ بررسی کنید نام فیلم در پایگاه سایت منبع وجود دارد
```

---

#### **5. خطای `MultipleSearchResultsError`**
```
❌ MultipleSearchResultsError: جستوجوی فیلم 'Mortal Combat' نتایج زیر رو داشت:
1. Mortal Combat II
2. Mortal Combat
```

**حل:**
```
✓ اگر در آپدیت دستی بود تا 5 دقیقه وقت دارین تا گرینه مدنظر رو وارد کنید در غیر این صورت در "فیلم های ناموفق" ذخیره میشه و بعد میتونید گزینه مد نظر رو وارد کنید.
✓ اگر در چرخه بود می‌توانید بعد از پایان چرخه گزینه مدنظر را تنظیم کنید تا در چرخه بعدی درست بشه
```

---

### 📊 ارتباط جداول دیتابیس

```text
Movies
│
├── Releases
│   │
│   └── Quality
│       │
│       └── Subtitles
│
└── Failed_Movies
```

هر فیلم می‌تواند چند نسخه مختلف (مانند دوبله یا زبان اصلی) داشته باشد.

هر نسخه می‌تواند شامل چند کیفیت دانلود مختلف باشد.

هر کیفیت می‌تواند دارای یک یا چند زیرنویس باشد.

فیلم‌هایی که در فرآیند جستجو یا دریافت لینک با خطا مواجه شوند در جدول `failed_movies` ذخیره می‌شوند تا بعداً قابل بررسی و اصلاح باشند.


---

### 📊 جدول خطاها و حل‌ها

| خطا | علت | حل |
|-----|------|-----|
| `ConnectionError` | عدم اتصال اینترنت | بررسی اتصال |
| `PermissionError` | مشکل دسترسی فایل | `chmod 755 .` (Linux) |
| `HTTPError 403` | بلاکه‌شدن IP | تغییر IP / VPN |
| `JSONDecodeError` | فرمت پیام نامعتبر | بررسی فرمت پیام |
| `KeyError` | کلید در dict یافت نشد | `defaults` استفاده کنید |

---

## 🔧 تنظیمات پیشرفته

### ⚙️ تنظیمات Playwright

```python
# scrapers/scraper_sample.py میں تغییرات

def start(self):
    self.playwright = sync_playwright().start()
    
    # تنظیمات مرورگر
    self.browser = self.playwright.chromium.launch(
        headless=self.headless,
        args=[
            '--no-sandbox',                    # برای Linux Server
            '--disable-setuid-sandbox',        # امنیت بیشتر
            '--disable-dev-shm-usage',         # عدم استفاده از /dev/shm
            '--disable-gpu',                   # خاموش GPU
            '--start-maximized',               # بزرگ‌ترین اندازه
            '--disable-web-resources',         # تسریع بارگذاری
        ]
    )
    
    # تنظیمات Context
    self.context = self.browser.new_context(
        # لود Storage State (کوکی‌های لاگین)
        storage_state=self.storage_state_path if os.path.exists(self.storage_state_path) else None,
        # تنظیمات صفحه
        viewport={'width': 1920, 'height': 1080},
        # User Agent جعلی
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        # Proxy (اختیاری)
        proxy={"server": "http://proxy.example.com:8080"} if USE_PROXY else None,
        # Timeout پیش‌فرض
        timeout=self.timeout
    )
    
    self.page = self.context.new_page()
```

---

### 🔄 سفارشی‌سازی Retry Logic

```python
# utils.py میں

def retry_on_timeout(func, max_retries=10, delay=10, backoff=1.5):
    """
    Exponential backoff retry mechanism
    """
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"تلاش {attempt}/{max_retries}")
            return func()
        except PlaywrightTimeoutError as e:
            if attempt == max_retries:
                raise
            wait_time = delay * (backoff ** (attempt - 1))
            logger.warning(f"⏳ {wait_time:.0f} ثانیه صبر...")
            time.sleep(wait_time)
```

---

## 📝 ساختار دیتابیس

### 🗂️ جداول اصلی

#### **1. Full_Movies**
```sql
CREATE TABLE IF NOT EXISTS movies
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        tags TEXT DEFAULT '[]',
        chat_id TEXT NOT NULL,
        message_id TEXT NOT NULL,
        source Text,
        "index" INTEGER,
        is_anime INTEGER DEFAULT 0,
        message_type INTEGER,
        online_watchable INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (title, tags)
    );
```

#### **2. Releases**
```sql
CREATE TABLE IF NOT EXISTS releases
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        language_type TEXT NOT NULL
            CHECK (language_type IN ('original', 'dubbed')),
        UNIQUE (movie_id, language_type),
        FOREIGN KEY (movie_id) REFERENCES movies (id) ON DELETE CASCADE
    );
```

#### **3. Qualities**
```sql
CREATE TABLE IF NOT EXISTS quality
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        release_id INTEGER NOT NULL,
        quality TEXT NOT NULL
            CHECK (quality IN ('480p', '720p', '1080p', '4K')),
        download_link TEXT NOT NULL,
        UNIQUE (release_id, quality),
        FOREIGN KEY (release_id) REFERENCES releases (id) ON DELETE CASCADE
    );
```

#### **4. Subtitles**
```sql
CREATE TABLE IF NOT EXISTS subtitles
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quality_id INTEGER NOT NULL,
        download_link TEXT NOT NULL,
        UNIQUE (quality_id, download_link),
        FOREIGN KEY (quality_id) REFERENCES quality (id) ON DELETE CASCADE
    );
```

#### **5. Failed Movies**
```sql
CREATE TABLE IF NOT EXISTS failed_movies
    (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        search_query TEXT,
        source TEXT,
        error TEXT,
        attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (title, movie_id),
        FOREIGN KEY (movie_id) REFERENCES movies (id) ON DELETE CASCADE
    );
```





---

## 🛠️ توسعه پروژه

### 🐛 گزارش باگ

برای گزارش باگ‌ها، یک **Issue** باز کنید:
```
Title: [BUG] توصیف کوتاه
Description: توصیف دقیق، مراحل تکرار، و لاگ‌های خطا
```

### 🎯 ارسال PR

```bash
# 1. Fork کنید
git clone https://github.com/mahdi2006m/rubika-movie-link-updater-bot.git
cd rubika-movie-link-updater

# 2. شاخه جدید
git checkout -b feature/your-feature-name

# 3. کامیت کنید
git commit -m "✨ توصیف تغییر"

# 4. Push کنید
git push origin feature/your-feature-name

# 5. PR بسازید در GitHub
```

### 📖 ایجاد اسکریپر جدید

```python
# scrapers/scraper_newsite.py

from scrapers.scraper_sample import SampleMovieScraper
from scrapers.scraper_errors import *

class NewSiteScraper(SampleMovieScraper):
    BASE_URL = "https://newsite.com"
    
    def login(self, username, password, **kwargs):
        """پیاده‌سازی لاگین برای سایت جدید"""
        # کدهای شخصی‌سازی شده
        pass
    
    def search_movie(self, full_movie):
        """جستجوی فیلم در سایت جدید"""
        pass

    def Multiple_search_movie_result(self, full_movie):
        """جستجوی فیلم در سایت جدید"""
        pass
    
    def get_download_link(self, search_page, quality, release, has_sub=False):
        """استخراج لینک برای سایت جدید"""
        pass
```

---

## 📜 لایسنس

```
MIT License

Copyright (c) 2024 Cinema Bot Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

[متن کامل در LICENSE فایل]
```

---

## 📞 تماس و پشتیبانی

- 👤 **توسعه‌دهنده**: [@mahdi2006m](https://github.com/mahdi2006m)
- 💬 **Issues**: [GitHub Issues](https://github.com/mahdi2006m/rubika-movie-link-updater-bot/issues)
- 📧 **Email**: developer@example.com (اگر موجود باشد)

---

## 🙏 تشکر

این پروژه از استفاده از کتابخانه‌های عالی بهره‌می‌برد:
- **Rubpy** - کلاینت روبیکا
- **Playwright** - Automation مرورگر
- **SQLite** - دیتابیس
- **Python Community** - جامعه پایتون

---

<div align="center">

**⭐ اگر این پروژه مفید بود، لطفاً ستاره بدهید! ⭐**

</div>