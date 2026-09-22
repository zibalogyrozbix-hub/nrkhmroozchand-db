import os
import re
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pytz
import jdatetime
from playwright.sync_api import sync_playwright

try:
    import libsql_experimental as libsql
    HAS_LIBSQL = True
except ImportError:
    HAS_LIBSQL = False

# نگاشت کامل کلیه کلیدهای اصلی و تکراری دیتابیس
SYMBOL_MAP = {
    # طلا، سکه و صندوق‌ها
    "سکه امامی": ["coin_emami"],
    "سکه بهار آزادی": ["coin_azadi"],
    "نیم سکه": ["coin_half"],
    "ربع سکه": ["coin_quarter"],
    "سکه گرمی": ["coin_gram"],
    "طلای ۱۸ عیار": ["gold_18k"],
    "طلای ۲۴ عیار": ["gold_24k"],
    "طلای دست دوم": ["gold_used"],
    "مثقال طلا": ["gold_mesghal"],
    "انس طلا": ["gold_ounce"],
    "گرم نقره ۹۹۹": ["silver_gram"],
    "آبشده نقدی": ["abshedeh_cash"],
    "آبشده معاملاتی": ["abshedeh_trade"],
    "انس نقره": ["silver_ounce"],
    "انس پلاتین": ["platinum_ounce"],
    "انس پالادیوم": ["palladium_ounce"],
    "مثقال / بدون حباب": ["mesghal_no_bubble"],
    "مثقال بدون حباب": ["mesghal_no_bubble"],
    "حباب سکه امامی": ["bubble_emami"],
    "حباب سکه بهار آزادی": ["bubble_azadi"],
    "حباب نیم سکه": ["bubble_half"],
    "حباب ربع سکه": ["bubble_quarter"],
    "حباب سکه گرمی": ["bubble_gram"],
    "صندوق طلای عیار": ["fund_ayar"],
    "صندوق طلای لوتوس": ["fund_lotus"],
    "صندوق طلای گوهر": ["fund_gohar"],
    "صندوق طلای مثقال": ["fund_mesghal"],
    "صندوق طلای کهربا": ["fund_kahreba"],
    "صندوق طلای ناب": ["fund_nab"],
    "صندوق طلای ریتون": ["fund_riton"],
    "صندوق طلای تابش": ["fund_tabesh"],
    "صندوق طلای زروان": ["fund_zarvan"],
    
    # ارزهای سنتی
    "دلار": ["usd"],
    "یورو": ["eur"],
    "درهم امارات": ["aed"],
    "پوند انگلیس": ["gbp"],
    "لیر ترکیه": ["try"],
    "فرانک سوئیس": ["chf"],
    "یوان چین": ["cny"],
    "ین ژاپن": ["jpy"],
    "وون کره جنوبی": ["krw"],
    "دلار کانادا": ["cad"],
    "دلار استرالیا": ["aud"],
    "افغانی": ["afn"],
    "درام ارمنستان": ["amd"],
    "منات آذربایجان": ["azn"],
    "دینار بحرین": ["bhd"],
    "کرون دانمارک": ["dkk"],
    "لاری گرجستان": ["gel"],
    "دلار هنگ‌کنگ": ["hkd"],
    "روپیه هند": ["inr"],
    "دینار عراق": ["iqd"],
    "سوم قرقیزستان": ["kgs"],
    "دینار کویت": ["kwd"],
    "رینگیت مالزی": ["myr"],
    "کرون نروژ": ["nok"],
    "دلار نیوزیلند": ["nzd"],
    "ریال عمان": ["omr"],
    "روپیه پاکستان": ["pkr"],
    "ریال قطر": ["qar"],
    "روبل روسیه": ["rub"],
    "ریال عربستان": ["sar"],
    "کرون سوئد": ["sek"],
    "دلار سنگاپور": ["sgd"],
    "لیر سوریه": ["syp"],
    "بات تایلند": ["thb"],
    "سامانی تاجیکستان": ["tjs"],
    "منات ترکمنستان": ["tmt"],

    # ارزهای دیجیتال (فقط قیمت ریالی)
    "بیت‌کوین": ["btc"],
    "بیت کوین": ["btc"],
    "اتریوم": ["eth"],
    "تتر": ["usdt"],
    "ترون": ["trx"],
    "کاردانو": ["ada"],
    "سولانا": ["sol"],
    "دوج کوین": ["doge"],
    "شیبا اینو": ["shib"],
    "تون‌کوین": ["ton"],
    "ریپل": ["xrp"],
    "لایت‌کوین": ["ltc"],
    "بیت‌کوین کش": ["bch"],
    "پولکادات": ["dot"],
    "آوالانچ": ["avax"],
    "استلار": ["xlm"],
    "دش": ["dash"],
    "بایننس کوین": ["bnb"],

    # کالاهای اساسی و انرژی (ستون قیمت / دلار)
    "پنبه": ["cotton"],
    "شکر": ["sugar"],
    "سویا": ["soybeans"],
    "گندم": ["wheat"],
    "ذرت": ["corn"],
    "برنج": ["rice"],
    "آلومینیوم": ["aluminum"],
    "نیکل": ["nickel"],
    "سرب": ["lead"],
    "روی": ["zinc"],
    "مس": ["copper"],
    "قلع": ["tin"],
    "نفت سبک": ["oil_crude"],
    "نفت برنت": ["oil_brent"],
    "نفت اوپک": ["oil_opec"],
    "بنزین (RBOB)": ["gasoline"],
    "گاز طبیعی": ["natural_gas"],
    "زغال سنگ": ["coal"],

    # شاخص‌های بورس و جهانی (ستون ارزش + تبدیل میلیون و هزار)
    # توجه: "شاخص کل" دیگر از جدول صفحه اصلی خوانده نمی‌شود، چون آنجا وجود
    # ندارد؛ به‌صورت اختصاصی از https://www.tgju.org/profile/gc30 گرفته
    # می‌شود (به تابع fetch_bourse_total_index نگاه کنید).
    "بازار اول فرابورس": ["ifb_market1"],
    "بازار دوم فرابورس": ["ifb_market2"],
    "شاخص بازار اول": ["bourse_market1"],
    "شاخص بازار دوم": ["bourse_market2"],
    "شاخص قیمت هم‌وزن": ["bourse_pequal"],
    "شاخص قیمت وزنی ارزشی": ["bourse_pweighted"],
    "داوجونز": ["dow_jones"],
    "نزدک": ["nasdaq"],
    "اس‌ام‌آی سوئیس": ["smi_swiss"],
    "اس ام آی سوئیس": ["smi_swiss"],
    "نیفتی ۵۰": ["nifty_50"],
    "نیفتی 50": ["nifty_50"],
    "فتسی بریتانیا": ["ftse_100"],
    "دکس آلمان": ["dax"],
    "کک فرانسه": ["cac_40"],
    "نیکی ژاپن": ["nikkei_225"],
    "شانگهای چین": ["shanghai_composite"],
    "آیبکس اسپانیا": ["ibex_35"]
}

# این ۷ شاخص از صفحه اصلی tgju.org قابل استخراج نبودند (داده‌شان دیگر آنجا
# وجود ندارد - عملاً به shakhesban.com منتقل شده) و طبق درخواست کاربر کاملاً
# از پروژه حذف شدند تا دیگر فراخوانی نشوند: بورس هم‌وزن، شاخص فرابورس،
# ۳۰ شرکت بزرگ، ۵۰ شرکت فعال‌تر، شاخص قیمت ۵۰ شرکت، اس‌اندپی ۵۰۰، اس‌اندپی کانادا.

COMMODITIES = {"cotton", "sugar", "soybeans", "wheat", "corn", "rice", "aluminum", "nickel", "lead", "zinc", "copper", "tin", "oil_crude", "oil_brent", "oil_opec", "gasoline", "natural_gas", "coal"}
INDICES = {"bourse_total", "ifb_market1", "ifb_market2", "bourse_market1", "bourse_market2", "bourse_pequal", "bourse_pweighted", "dow_jones", "nasdaq", "smi_swiss", "nifty_50", "ftse_100", "dax", "cac_40", "nikkei_225", "shanghai_composite", "ibex_35"}
CRYPTO = {"btc", "eth", "usdt", "trx", "ada", "sol", "doge", "shib", "ton", "xrp", "ltc", "bch", "dot", "avax", "xlm", "dash", "bnb"}

# ---------------------------------------------------------------------------
# لایهٔ دفاعی در برابر تغییرات ناگهانی/نامعلوم سایت مرجع
# ---------------------------------------------------------------------------
# هر سه باگ واقعی‌ای که تا امروز در این پروژه پیدا و رفع شد (عدد غول‌آسای
# به‌هم‌چسبیده، نرخ برابری دلار/لیر به‌جای نرخ دلار، و گیر کردن طلای ۱۸ عیار)
# یک ویژگی مشترک داشتند: مقدار «اشتباه» با مقدار «قبلی و درست» از نظر اندازه
# (تعداد رقم) خیلی متفاوت بود. این‌جا به‌جای این‌که هر بار منتظر بمانیم کاربر
# خودش با چشم متوجه یک عدد عجیب در دیتابیس شود، قبل از نوشتن هر مقدار جدید،
# آن را با آخرین مقدار معتبرِ همان نماد مقایسه می‌کنیم. این کار هیچ درخواست
# شبکه‌ای اضافه‌ای نمی‌خواهد (فقط یک SELECT روی همان دیتابیسی که داریم بهش
# وصل می‌شویم) و هیچ ستون/جدولی هم به market_prices اضافه نمی‌کند.
#
# اگر تعداد رقم‌های عدد جدید با عدد قبلی بیش از این مقدار فرق کند (یعنی چند
# مرتبه بزرگ‌تر/کوچک‌تر شده - دقیقاً الگوی هر سه باگ قبلی)، مقدار جدید
# مشکوک تلقی می‌شود: به‌جای بازنویسی، مقدار قبلی حفظ می‌شود و در گزارش
# پایانی اجرا فلگ می‌شود تا شما دستی بررسی کنید. نوسان‌های واقعی و حتی
# شدید بازار (که در ارز/طلا/کریپتوی ایران واقعاً پیش می‌آید) تعداد رقم‌ها را
# عوض نمی‌کنند، پس این آستانه false-positive روی نوسان طبیعی نمی‌دهد.
SANITY_DIGIT_DIFF_THRESHOLD = 3

# درصد تغییری که فقط برای اطلاع/گزارش (نه جلوگیری از ثبت) چاپ می‌شود؛ چون
# جهش‌های درصدی بزرگ ولی هم‌رقم (مثلا نوسان سیاسی ناگهانی دلار) می‌توانند
# کاملاً واقعی باشند و نباید مسدود شوند.
SANITY_PERCENT_WARN_THRESHOLD = 50.0

def _to_float(price_str) -> float | None:
    """یک عدد فرمت‌شدهٔ همین دیتابیس (مثلا '2,313,000') را به float تبدیل
    می‌کند. برای مقادیر غیرعددی مثل '-' مقدار None برمی‌گرداند."""
    if not price_str or price_str == "-":
        return None
    try:
        return float(str(price_str).replace(",", "").strip())
    except (ValueError, TypeError):
        return None

def _digit_count(value: float) -> int:
    return len(str(int(abs(value))))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_rendered_html(url: str, extra_wait: float = 3.0) -> str | None:
    """
    برخلاف requests.get که فقط HTML خام لحظه‌ی اول را می‌گیرد، این تابع با
    یک مرورگر headless واقعی (Playwright/Chromium) صفحه را کامل بارگذاری
    و اجرا می‌کند.

    دلیل وجودش: صفحات tgju.org در همان چند صدم ثانیه‌ی اول یک سری عدد
    «کش‌شده» را در HTML سمت سرور نمایش می‌دهند و بلافاصله بعد از لود، با
    جاوااسکریپت سمت کاربر (که requests اصلاً اجرایش نمی‌کند) آن اعداد را
    با مقادیر واقعی و به‌روز جایگزین می‌کنند و رنگشان هم تغییر می‌کند. قبلاً
    این تابع نبود و مستقیم از requests.get استفاده می‌شد، که همیشه همان
    عدد کش‌شده‌ی اولیه (نه عدد نهایی) را برمی‌گرداند. الگوی wait زیر
    (domcontentloaded + منتظرماندن برای محو شدن لایه‌ی بارگذاری + یک مکث
    اضافه) دقیقاً همان راهکاری است که در app.py (instant price) درست کار
    می‌کند.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # اگر صفحه یک لایه‌ی «در حال بارگذاری...» داشته باشد، منتظر محو
            # شدنش می‌مانیم؛ اگر نبود (خطا داد)، بی‌خیالش می‌شویم و ادامه می‌دهیم.
            try:
                loading_el = page.locator("text='در حال بارگذاری...'").first
                loading_el.wait_for(state="detached", timeout=8000)
            except Exception:
                pass

            # مکث اضافه تا جاوااسکریپت صفحه اعداد کش‌شده‌ی اولیه را با
            # مقادیر واقعی/به‌روز جایگزین کند (همان تاخیر عمدی app.py).
            page.wait_for_timeout(int(extra_wait * 1000))

            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"خطا در رندر صفحه با Playwright ({url}): {e}", flush=True)
        return None

_TITLE_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹" + "٠١٢٣٤٥٦٧٨٩",
    "0123456789" + "0123456789",
)

def clean_title(text: str) -> str:
    """
    عنوان ردیف را طوری یکسان‌سازی می‌کند که مقایسه با کلیدهای SYMBOL_MAP
    مستقل از تفاوت‌های ظاهریِ بی‌ربط باشد. این تابع علت اصلی مشکلاتی است که
    باعث می‌شد بعضی شاخص‌ها (مثلا طلای ۱۸ عیار) گاهی اصلاً به‌روزرسانی
    نشوند و دادهٔ قدیمی/نامرتبط در دیتابیس بماند، بدون این‌که خطای مشخصی هم
    چاپ شود؛ چون کد نه با خطا مواجه می‌شد و نه match پیدا می‌کرد، فقط آن
    نماد را «رد» می‌کرد.

    چهار نوع تفاوت ظاهری (که در سایت tgju.org به‌طور متناوب و غیرقابل‌پیش‌بینی
    رخ می‌دهند) اینجا یکسان‌سازی می‌شوند:

    ۱. نیم‌فاصله/RLM: قبلاً هم پوشش داده شده بود.
    ۲. حروف عربی/فارسی هم‌شکل با کد یونیکد متفاوت: مثلا «ي» عربی (U+064A)
       در برابر «ی» فارسی (U+06CC)، یا «ك» عربی (U+0643) در برابر «ک»
       فارسی (U+06A9). این دو کاملاً یکسان به نظر می‌رسند ولی از دید
       پایتون دو کاراکتر متفاوت‌اند و match را بی‌سروصدا خراب می‌کنند.
    ۳. ارقام فارسی/عربی در برابر ارقام لاتین: این دقیقاً همان علت واقعی
       گیر کردن «طلای ۱۸ عیار» بود. SYMBOL_MAP با رقم فارسی «۱۸» نوشته
       شده، ولی سایت گاهی همین ردیف را با رقم لاتین «طلای 18 عیار» رندر
       می‌کند (به‌نظر می‌رسد بسته به این‌که عدد به‌عنوان مقدار یا به‌عنوان
       بخشی از نام محصول در نظر گرفته شود، انتخاب سایت فرق می‌کند). همین
       مشکل بالقوه می‌تواند هر کلید دیگری با رقم داخل نامش (مثلا
       «گرم نقره ۹۹۹») را هم گاهی گرفتار کند.
    ۴. چند فاصلهٔ پیاپی: به یک فاصله تبدیل می‌شود.

    چون این نرمال‌سازی هم روی عنوان ردیف‌های واقعی سایت (در scrape_homepage_data
    و fetch_bourse_total_index) و هم روی خودِ کلیدهای SYMBOL_MAP (چون
    matched_fa هم با clean_title مقایسه می‌شود) اعمال می‌شود، کل این دسته
    از مشکلات را یک‌جا و برای همیشه (نه فقط برای طلای ۱۸ عیار) حل می‌کند،
    بدون نیاز به اضافه‌کردن دستی یک کلید تکراری برای هر نماد جدیدی که این
    مشکل را نشان می‌دهد.
    """
    if not text:
        return ""
    text = text.replace('\u200c', ' ').replace('\u200f', '')
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    text = text.translate(_TITLE_DIGIT_TRANSLATION)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
    
def get_cell_text(tag) -> str:
    """
    استخراج متن یک سلول با درج فاصله بین گره‌های تودرتو.
    نکته مهم: get_text(strip=True) بدون separator می‌تواند باعث بشود اعداد چند
    اسپن/عنصر تودرتو (مثلا مقدار اصلی + دیتای مخفی سری تاریخی/اسپارک‌لاین) بدون هیچ
    جداکننده‌ای به هم بچسبند و یک عدد غول‌آسا و بی‌معنی تولید شود
    (نمونه واقعی مشاهده‌شده در دیتابیس: سکه بهار آزادی).
    با گذاشتن separator=" " از این باگ جلوگیری می‌شود.
    """
    if tag is None:
        return ""
    if isinstance(tag, str):
        return tag
    return tag.get_text(" ", strip=True)

def to_english_digits(text: str) -> str:
    if not text:
        return ""
    text = text.replace('−', '-').replace('–', '-').replace(',', '').replace('،', '')
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"
    translation = str.maketrans(persian_digits + arabic_digits, english_digits * 2)
    return text.translate(translation)

def format_number_with_comma(val) -> str:
    if val is None:
        return "-"
    if isinstance(val, int) or (isinstance(val, float) and val.is_integer()):
        return f"{int(val):,}"
    return f"{val:,.2f}".rstrip('0').rstrip('.')

def parse_price_value(raw_text: str, is_index: bool = False) -> tuple[str, float]:
    """استخراج عدد قیمت و تبدیل کلمات میلیون/هزار به عدد کامل با فرمت ۳ رقمی"""
    if not raw_text or raw_text.strip() == "-" or raw_text.strip() == "":
        return "-", 0.0
    
    clean_text = to_english_digits(raw_text)
    match = re.search(r'(\d+(?:\.\d+)?)', clean_text)
    if not match:
        return "-", 0.0

    num_str = match.group(1)
    # برای اعداد صحیح بزرگ (مثل قیمت سکه/طلا به ریال) از int با دقت نامحدود
    # پایتون استفاده می‌کنیم تا هیچ رقمی به‌خاطر گرد شدن float از بین نرود.
    if "." not in num_str:
        val = int(num_str)
    else:
        val = float(num_str)
    
    if is_index or "میلیون" in raw_text or "میلیون" in clean_text:
        if "میلیون" in raw_text:
            val = val * 1_000_000
    elif "هزار" in raw_text:
        val = val * 1_000

    return format_number_with_comma(val), val

def is_cell_red(cell_tag) -> bool:
    """تشخیص قرمز بودن سلول تغییرات جهت اعمال علامت منفی"""
    if not cell_tag:
        return False
    text = get_cell_text(cell_tag)
    if "-" in text or "−" in text or "🔻" in text:
        return True
    
    if not isinstance(cell_tag, str):
        classes = list(cell_tag.get("class", []))
        for child in cell_tag.find_all(True):
            classes.extend(child.get("class", []))
        if cell_tag.parent:
            classes.extend(cell_tag.parent.get("class", []))
        
        class_str = " ".join([str(c) for c in classes]).lower()
        style_str = str(cell_tag.get("style", "")).lower()
        if any(kw in class_str for kw in ["low", "drop", "red", "danger", "down", "minus"]) or "color: red" in style_str or "color:#f" in style_str:
            return True
    return False

def parse_changes(change_cell, price_val: float) -> tuple[str, str]:
    """تفکیک change_amount و change_percent و اعمال منفی/مثبت بر اساس رنگ"""
    if not change_cell:
        return "0", "0%"
    
    raw_text = get_cell_text(change_cell)
    clean_text = to_english_digits(raw_text)
    is_red = is_cell_red(change_cell)

    pct_match = re.search(r'\(([^)]+)\)', clean_text)
    pct_val = None
    if pct_match:
        pct_num_match = re.search(r'(\d+(?:\.\d+)?)', pct_match.group(1))
        if pct_num_match:
            pct_val = float(pct_num_match.group(1))

    text_no_parentheses = re.sub(r'\([^)]*\)', '', clean_text)
    amt_match = re.search(r'(\d+(?:\.\d+)?)', text_no_parentheses)
    amt_val = float(amt_match.group(1)) if amt_match else 0.0

    if pct_val is None and price_val > 0 and amt_val > 0:
        pct_val = (amt_val / price_val) * 100

    pct_val = pct_val or 0.0

    # صحت‌سنجی: درصد تغییر روزانه بیش از ۱۰۰٪ تقریبا همیشه نشانه‌ی این است که
    # amt_val و price_val از دو ستون/واحد متفاوت (مثلا تومان و دلار، یا دو ردیف
    # مختلف) استخراج شده‌اند، نه یک تغییر روزانه واقعی. در این حالت به‌جای ثبت
    # عددی گمراه‌کننده (مثل -۱۵۳۰۴۳٪) آن را صفر می‌کنیم.
    if abs(pct_val) > 100:
        pct_val = 0.0
        amt_val = 0.0

    if is_red:
        amt_str = f"-{format_number_with_comma(amt_val)}" if amt_val != 0 else "0"
        pct_str = f"-{pct_val:.2f}%".rstrip('0').rstrip('.%') + "%" if pct_val != 0 else "0%"
    else:
        amt_str = format_number_with_comma(amt_val)
        pct_str = f"{pct_val:.2f}%".rstrip('0').rstrip('.%') + "%" if pct_val != 0 else "0%"

    return amt_str, pct_str

def find_header_col(header_cells, target_patterns) -> int:
    """
    پیدا کردن ایندکس ستون بر اساس متن سرستون (بدون توجه به فاصله‌های اضافه).
    برای مواردی که باید مطمئن باشیم دقیقاً از ستون درست («قیمت / دلار» برای
    کالاها، یا «ارزش» برای شاخص‌های بورسی) می‌خوانیم، نه از هر سلولی که
    تصادفاً عدد یا علامت $ دارد.
    """
    for idx, c in enumerate(header_cells):
        h_norm = get_cell_text(c).replace(" ", "").replace("\u200c", "")
        for pat in target_patterns:
            if pat.replace(" ", "") in h_norm:
                return idx
    return -1

def is_real_data_table(table, header_cells) -> bool:
    """
    فیلتر کردن جدول‌های غیرواقعی صفحه اصلی (فرم‌های محاسبه‌گر مثل «محاسبه‌گر
    قیمت طلا» یا «حباب سنج سکه»، دراپ‌داون انتخاب نوع سکه و ...).
    این جدول‌ها ظاهرا شبیه جدول قیمت هستند ولی سلول اول‌شان یک برچسب مثل
    «قیمت دلار (ریال):» است که چون شامل رشته «دلار» است به‌اشتباه با نماد
    دلار match می‌شود، و چون سلول قیمت واقعی ندارند یا حاوی <input>/<select>
    هستند مقدار نهایی «-» یا عددی نامعتبر می‌شود.
    """
    # اگر جدول حاوی عنصر ورودی/انتخاب باشد، قطعا یک فرم است نه جدول قیمت
    if table.find(["input", "select", "button"]) is not None:
        return False

    header_text = " ".join(get_cell_text(c) for c in header_cells)
    # جدول‌های واقعی قیمت روی صفحه اصلی همیشه هم ستون «قیمت زنده/ارزش» و هم
    # ستون «تغییر» را در هدر خود دارند
    has_price_col = any(k in header_text for k in ["قیمت زنده", "قیمت", "ارزش"])
    has_change_col = "تغییر" in header_text
    return has_price_col and has_change_col

def scrape_homepage_data():
    print("در حال دریافت داده‌ها از tgju.org ...", flush=True)
    scraped_data = []
    sorted_targets = sorted(SYMBOL_MAP.keys(), key=len, reverse=True)
    tehran_tz = pytz.timezone('Asia/Tehran')
    updated_at = datetime.now(tehran_tz).strftime("%Y-%m-%d %H:%M:%S")

    # برای دو هشدار زودهنگام در پایان تابع (بدون هیچ درخواست شبکه‌ای اضافه؛
    # فقط همون داده‌ای که داریم روی صفحه پردازش می‌کنیم را جمع می‌کنیم):
    seen_header_texts = []
    unrecognized_titles = set()

    try:
        html = fetch_rendered_html("https://www.tgju.org", extra_wait=3.0)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            
            for table in soup.find_all("table"):
                price_col_idx, change_col_idx = 1, 2
                header_tr = table.find("tr")
                header_cells = header_tr.find_all(["th", "td"]) if header_tr else []

                # برای هشدار اثر انگشت ساختاری، سرستون تمام جدول‌ها را جمع
                # می‌کنیم (حتی آن‌هایی که پایین‌تر رد می‌شوند)، وگرنه اگر
                # ساختار سایت آن‌قدر عوض شود که هیچ جدولی از فیلتر
                # is_real_data_table رد نشود، این هشدار هیچ‌وقت فعال نمی‌شد.
                seen_header_texts.append(" ".join(get_cell_text(c) for c in header_cells))

                # رد کردن فرم‌های محاسبه‌گر/دراپ‌داون‌ها که جدول قیمت واقعی نیستند
                if not is_real_data_table(table, header_cells):
                    continue

                # پیدا کردن دقیق ایندکس ستون "ارزش" یا "قیمت" در هدر جدول.
                # مهم: از ایندکس ۱ شروع می‌کنیم و ستون ۰ (که همیشه نام/عنوان
                # ردیف است) را کاملاً نادیده می‌گیریم. علتش این باگ واقعی بود:
                # در جدول سکه‌ها سرستون خود ستون اول literally «قیمت سکه» است؛
                # چون این متن هم شامل کلمه «قیمت» است، حلقه قبلی price_col_idx
                # را اشتباهاً روی ۰ (ستون نام سکه، نه عدد) قفل می‌کرد و چون
                # شرط بعدی price_col_idx==1 دیگر true نبود، تا پایان همان جدول
                # اصلاح نمی‌شد. نتیجه: ستون قیمت سکه‌ها همیشه «-» می‌شد در حالی
                # که change_amount (که column ایندکسش را از یک شرط جدا تشخیص
                # می‌دهد) درست بود.
                for idx, c in enumerate(header_cells):
                    if idx == 0:
                        continue
                    c_txt = get_cell_text(c)
                    if "ارزش" in c_txt:
                        price_col_idx = idx
                    elif any(k in c_txt for k in ["قیمت", "قیمت زنده", "قیمت (ریال)"]) and price_col_idx == 1:
                        price_col_idx = idx
                    elif "تغییر" in c_txt:
                        change_col_idx = idx

                for row in table.find_all("tr"):
                    cols = row.find_all(["td", "th"])
                    if not cols or len(cols) < 2:
                        continue

                    row_title = clean_title(get_cell_text(cols[0]))

                    # مهم: تطبیق فقط روی عنوان ردیف (ستون اول) انجام می‌شود، نه
                    # روی کل متن ردیف. تطبیق روی کل ردیف باعث می‌شد اگر یک ستون
                    # دیگر (مثلا یک دراپ‌داون یا برچسب) به‌طور اتفاقی حاوی اسم یک
                    # نماد دیگر باشد، آن ردیف به‌اشتباه match شود.
                    matched_fa = next(
                        (t for t in sorted_targets if clean_title(t) == row_title),
                        None
                    )
                    # اگر تطبیق دقیق پیدا نشد، به‌عنوان راه دوم substring را هم
                    # امتحان می‌کنیم (برای مواردی که سایت پسوند/پیشوند اضافه دارد).
                    # نکته مهم: این fallback را روی ردیف‌هایی که در عنوانشان "/"
                    # دارند اجرا نمی‌کنیم. علتش یک باگ واقعی است: در صفحه اصلی
                    # tgju.org یک جدول «نرخ جفت‌ارزها» هم وجود دارد (حتی اگر در
                    # یک تب مخفی/غیرفعال باشد، BeautifulSoup همچنان آن را در
                    # HTML می‌بیند) با ردیف‌هایی مثل «دلار / لیره ترکیه» یا
                    # «یورو / دلار». چون "دلار" و "یورو" هر دو substring این
                    # عنوان‌ها هستند، بدون این گارد fallback اشتباهاً آن‌ها را با
                    # نماد ساده دلار/یورو یکی می‌گرفت و عدد نرخ برابری بین دو ارز
                    # خارجی (مثلا ۴۸.۷۶ برای دلار/لیره) به‌جای نرخ واقعی ریالی
                    # ثبت می‌شد. هیچ‌کدام از کلیدهای SYMBOL_MAP (به‌جز «مثقال /
                    # بدون حباب» که با تطبیق دقیق بالا همین حالا هم درست کار
                    # می‌کند) به‌طور طبیعی «/» ندارند، پس این گارد بی‌خطر است.
                    if not matched_fa and "/" not in row_title:
                        matched_fa = next(
                            (t for t in sorted_targets if clean_title(t) in row_title),
                            None
                        )

                    # اگر این ردیف به هیچ نمادی match نشد ولی خودش هم یکی از
                    # ردیف‌های "شناخته‌شده و بی‌خطر" (مثل جفت‌ارزها که "/"
                    # دارند، یا خودِ ردیف سرستون که همیشه طبیعتاً match
                    # نمی‌شود) نبود، به‌عنوان یک نامزد بالقوهٔ «نماد جدید/تغییر
                    # نام‌یافته روی سایت» ثبتش می‌کنیم (فقط یک set().add ساده،
                    # بدون هیچ پردازش یا درخواست اضافه).
                    if not matched_fa and row is not header_tr and "/" not in row_title and len(row_title) >= 2:
                        unrecognized_titles.add(row_title)

                    if matched_fa:
                        symbol_keys = SYMBOL_MAP[matched_fa]
                        primary_key = symbol_keys[0]

                        price_cell = cols[price_col_idx] if len(cols) > price_col_idx else cols[1]
                        
                        # ۱. رمزارزها: انتخاب ستون قیمت ریالی
                        if primary_key in CRYPTO and len(cols) >= 3:
                            price_cell = cols[1]

                        # ۲. کالاهای اساسی/فلزات پایه/نفت و انرژی: قیمت را حتما
                        # از ستونی با سرستون دقیق «قیمت / دلار» می‌خوانیم، نه از
                        # هر سلولی که تصادفا نماد $ یا کلمه دلار داشته باشد.
                        elif primary_key in COMMODITIES:
                            usd_col = find_header_col(header_cells, ["قیمت/دلار", "قیمت ($)", "قیمت$"])
                            if usd_col != -1 and usd_col < len(cols):
                                price_cell = cols[usd_col]
                            else:
                                # راه دوم (fallback) اگر چنین سرستونی پیدا نشد
                                for c in cols[1:]:
                                    c_txt = get_cell_text(c)
                                    if "$" in c_txt or "دلار" in c_txt:
                                        price_cell = c
                                        break

                        # ۳. شاخص‌های بورس/فرابورس: قیمت را حتما از ستون «ارزش»
                        # می‌خوانیم و اعداد بزرگ/کلمات میلیون و هزار را دست
                        # نمی‌زنیم (فقط تبدیل عددی می‌شوند، حذف نمی‌شوند).
                        elif primary_key in INDICES:
                            value_col = find_header_col(header_cells, ["ارزش"])
                            if value_col != -1 and value_col < len(cols):
                                price_cell = cols[value_col]
                            else:
                                found_val = False
                                for idx, c in enumerate(cols):
                                    c_text = get_cell_text(c)
                                    if c_text and c_text != "-" and any(char.isdigit() for char in c_text):
                                        h_text = get_cell_text(header_cells[idx]) if idx < len(header_cells) else ""
                                        if "ارزش" in h_text or "قیمت" in h_text or idx == price_col_idx:
                                            price_cell = c
                                            found_val = True
                                            break
                                if not found_val and len(cols) > price_col_idx:
                                    price_cell = cols[price_col_idx]

                        price_str, price_num = parse_price_value(get_cell_text(price_cell), is_index=(primary_key in INDICES))
                        
                        change_cell = cols[change_col_idx] if len(cols) > change_col_idx else None
                        change_amt, change_pct = parse_changes(change_cell, price_num)

                        # برای شاخص‌های کالایی/فلزات پایه/نفت و انرژی که قیمت‌شان
                        # به دلار است، عبارت «(دلار)» به انتهای نام فارسی اضافه
                        # می‌شود تا با اعداد ریالی بقیه دیتابیس اشتباه گرفته نشود.
                        display_title = matched_fa
                        if primary_key in COMMODITIES and "(دلار)" not in display_title:
                            display_title = f"{display_title} (دلار)"

                        for skey in symbol_keys:
                            scraped_data.append({
                                "symbol_key": skey,
                                "title_fa": display_title,
                                "price": price_str,
                                "price_num": price_num,
                                "change_amount": change_amt,
                                "change_percent": change_pct,
                                "updated_at": updated_at
                            })
    except Exception as e:
        print(f"خطا در استخراج: {e}", flush=True)

    # به‌جای «آخرین match برنده است»، اگر برای یک نماد چند ردیف/جدول پیدا شد،
    # اولین مقداری که معتبر است (قیمت "-" نیست) را نگه می‌داریم و دیگر با یک
    # مقدار "-"/نامعتبر از جدول بعدی رویش نمی‌نویسیم.
    unique_data = {}
    for item in scraped_data:
        key = item["symbol_key"]
        if key not in unique_data or unique_data[key]["price"] == "-":
            unique_data[key] = item

    for item in unique_data.values():
        item.pop("price_num", None)

    # --- هشدار ۱: اثر انگشت ساختاری صفحه ---
    # اگر در کل صفحه حتی یکی از کلیدواژه‌های شناخته‌شدهٔ سرستون (که همین
    # امروز روی سایت دیده شدند) پیدا نشود، این یعنی به احتمال زیاد کل قالب
    # جدول‌های سایت عوض شده - نه فقط یک نماد. این یک هشدار سطح‌بالا و زودهنگام
    # است، جدا از فلگ‌های ریزتر داخل update_database.
    known_header_keywords = ["قیمت زنده", "آخرین قیمت", "قیمت / دلار", "ارزش", "تغییر"]
    all_headers_text = " ".join(seen_header_texts)
    if seen_header_texts and not any(kw in all_headers_text for kw in known_header_keywords):
        print(
            "🚨 هشدار جدی: هیچ‌کدام از سرستون‌های شناخته‌شده (قیمت زنده/آخرین "
            "قیمت/ارزش/تغییر) در هیچ جدولی روی صفحه پیدا نشد. به‌احتمال زیاد "
            "ساختار کلی صفحهٔ اصلی tgju.org تغییر کرده و کل منطق استخراج نیاز "
            "به بازبینی دارد.",
            flush=True,
        )

    # --- هشدار ۲: ردیف‌های ناشناخته (نامزد نماد جدید یا تغییرنام‌یافته) ---
    if unrecognized_titles:
        sample = sorted(unrecognized_titles)[:15]
        print(
            f"\n💡 {len(unrecognized_titles)} عنوان ردیف در جدول‌های واقعی صفحه دیده "
            f"شد که به هیچ‌کدام از کلیدهای SYMBOL_MAP فعلی match نشدند (شاید نماد "
            f"جدیدی باشد که سایت اضافه کرده، یا نام یک نماد موجود کمی تغییر کرده). "
            f"چند نمونه: {' | '.join(sample)}",
            flush=True,
        )

    return list(unique_data.values())


def fetch_bourse_total_index():
    """
    استخراج اختصاصی «شاخص کل» بورس از صفحه پروفایل
    https://www.tgju.org/profile/gc30 که یک جدول اطلاعات لحظه‌ای دارد؛ سلول
    مقابل عبارت «نرخ فعلی» به‌عنوان price، سلول مقابل «میزان تغییر نسبت به
    روز گذشته» به‌عنوان change_amount و سلول مقابل «درصد تغییر نسبت به روز
    گذشته» به‌عنوان change_percent در نظر گرفته می‌شود. چون عبارت‌های دقیق
    ممکن است کمی با نسخه فعلی سایت فرق داشته باشند، چند حالت مشابه هم بررسی
    می‌شود.
    """
    tehran_tz = pytz.timezone('Asia/Tehran')
    updated_at = datetime.now(tehran_tz).strftime("%Y-%m-%d %H:%M:%S")

    price_labels = ["نرخ فعلی", "نرخ لحظه ای", "قیمت لحظه ای"]
    amount_labels = ["میزان تغییر نسبت به روز گذشته", "میزان تغییر"]
    percent_labels = ["درصد تغییر نسبت به روز گذشته", "درصد تغییر"]

    def find_value_for_label(soup, labels):
        for row in soup.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            for i, c in enumerate(cells):
                c_txt = clean_title(get_cell_text(c))
                if any(lbl in c_txt for lbl in labels):
                    # مقدار معمولا در سلول بعدی است؛ اگر برچسب آخرین سلول
                    # بود، سلول قبلی را امتحان می‌کنیم.
                    if i + 1 < len(cells):
                        return get_cell_text(cells[i + 1])
                    elif i - 1 >= 0:
                        return get_cell_text(cells[i - 1])
        # راه دوم: بعضی صفحات پروفایل tgju به‌جای جدول از لیست/دیو استفاده
        # می‌کنند (کلاس‌های info-table). این حالت را هم پوشش می‌دهیم.
        for item in soup.select("li, div"):
            spans = item.find_all(["span", "div", "td"], recursive=False)
            if len(spans) >= 2:
                label_txt = clean_title(get_cell_text(spans[0]))
                if any(lbl in label_txt for lbl in labels):
                    return get_cell_text(spans[1])
        return None

    try:
        html = fetch_rendered_html("https://www.tgju.org/profile/gc30", extra_wait=2.0)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        raw_price = find_value_for_label(soup, price_labels)
        raw_amount = find_value_for_label(soup, amount_labels)
        raw_percent = find_value_for_label(soup, percent_labels)

        if raw_price is None:
            print("هشدار: مقدار «نرخ فعلی» برای شاخص کل (gc30) پیدا نشد؛ ممکن است عبارت سایت عوض شده باشد.", flush=True)
            return None

        price_str, price_num = parse_price_value(raw_price, is_index=True)

        change_amt = "0"
        if raw_amount is not None:
            amt_clean = to_english_digits(raw_amount)
            amt_match = re.search(r'(-?\d+(?:\.\d+)?)', amt_clean)
            if amt_match:
                is_neg = "-" in amt_clean or "کاهش" in raw_amount
                amt_val = abs(float(amt_match.group(1)))
                if is_neg:
                    amt_val = -amt_val
                change_amt = format_number_with_comma(amt_val)

        change_pct = "0%"
        if raw_percent is not None:
            pct_clean = to_english_digits(raw_percent)
            pct_match = re.search(r'(-?\d+(?:\.\d+)?)', pct_clean)
            if pct_match:
                is_neg = "-" in pct_clean or "کاهش" in raw_percent
                pct_val = abs(float(pct_match.group(1)))
                if is_neg:
                    pct_val = -pct_val
                change_pct = f"{pct_val:.2f}%"

        return {
            "symbol_key": "bourse_total",
            "title_fa": "شاخص کل",
            "price": price_str,
            "change_amount": change_amt,
            "change_percent": change_pct,
            "updated_at": updated_at
        }
    except Exception as e:
        print(f"خطا در استخراج شاخص کل بورس از gc30: {e}", flush=True)
        return None

def get_db_connection():
    turso_url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    turso_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    
    if turso_url and turso_token and HAS_LIBSQL:
        if turso_url.startswith("libsql://"):
            turso_url = turso_url.replace("libsql://", "https://")
        elif not turso_url.startswith("https://"):
            turso_url = f"https://{turso_url}"
        print(f"اتصال مستقیم به دیتابیس Turso ({turso_url}) ...", flush=True)
        return libsql.connect(database=turso_url, auth_token=turso_token)
    else:
        print("اتصال به SQLite محلی ...", flush=True)
        return sqlite3.connect("market_database.db")

def update_database(data_list):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_prices (
            symbol_key TEXT PRIMARY KEY,
            title_fa TEXT,
            price TEXT,
            change_amount TEXT,
            change_percent TEXT,
            updated_at TEXT
        )
    """)

    # یک SELECT سبک روی همون دیتابیسی که داریم بهش وصل می‌شیم (نه یک
    # درخواست شبکه‌ای جدید) تا بتونیم هر مقدار تازه را قبل از نوشتن با
    # آخرین مقدار معتبرش مقایسه کنیم.
    existing_rows = {}
    try:
        for row in cursor.execute("SELECT symbol_key, price, updated_at FROM market_prices").fetchall():
            existing_rows[row[0]] = {"price": row[1], "updated_at": row[2]}
    except Exception as e:
        print(f"هشدار: خواندن مقادیر قبلی برای صحت‌سنجی ممکن نشد ({e}) — همه‌چیز بدون مقایسه ثبت می‌شود.", flush=True)

    accepted = []
    rejected_anomalies = []

    for item in data_list:
        old = existing_rows.get(item["symbol_key"])
        old_val = _to_float(old["price"]) if old else None
        new_val = _to_float(item["price"])

        if old_val is not None and new_val is not None and old_val != 0:
            old_digits, new_digits = _digit_count(old_val), _digit_count(new_val)
            if abs(old_digits - new_digits) >= SANITY_DIGIT_DIFF_THRESHOLD:
                # جهش رقمی مشکوک (دقیقاً الگوی باگ‌های قبلی) - مقدار قبلی حفظ می‌شود
                rejected_anomalies.append({
                    "symbol_key": item["symbol_key"],
                    "title_fa": item["title_fa"],
                    "old_price": old["price"],
                    "new_price": item["price"],
                })
                continue

            percent_change = abs(new_val - old_val) / abs(old_val) * 100
            if percent_change >= SANITY_PERCENT_WARN_THRESHOLD:
                print(
                    f"⚠️ هشدار (فقط اطلاع‌رسانی، ثبت می‌شود): {item['symbol_key']} "
                    f"({item['title_fa']}) با {percent_change:.0f}% نسبت به مقدار قبلی "
                    f"({old['price']} -> {item['price']}) تغییر کرده.",
                    flush=True,
                )

        accepted.append(item)

    for item in accepted:
        cursor.execute("""
            INSERT INTO market_prices (symbol_key, title_fa, price, change_amount, change_percent, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol_key) DO UPDATE SET
                price = excluded.price,
                change_amount = excluded.change_amount,
                change_percent = excluded.change_percent,
                updated_at = excluded.updated_at
        """, (
            item["symbol_key"],
            item["title_fa"],
            item["price"],
            item["change_amount"],
            item["change_percent"],
            item["updated_at"]
        ))

    conn.commit()
    conn.close()

    print(f"تعداد {len(accepted)} شاخص در جدول market_prices بروزرسانی شد.", flush=True)

    if rejected_anomalies:
        print(
            f"\n🚫 {len(rejected_anomalies)} مورد به‌خاطر جهش رقمی مشکوک (تفاوت "
            f"{SANITY_DIGIT_DIFF_THRESHOLD} رقم یا بیشتر با مقدار قبلی) رد و بررسی نشدند "
            f"— مقدار قبلی دیتابیس دست‌نخورده ماند:",
            flush=True,
        )
        for a in rejected_anomalies:
            print(f"   - {a['symbol_key']} ({a['title_fa']}): {a['old_price']} -> {a['new_price']} [رد شد]", flush=True)

    # ---------------------------------------------------------------
    # گزارش پوشش: کدام نمادهای موردانتظار اصلاً در این اجرا استخراج
    # نشدند، و کدام‌ها مدتی طولانی است بروزرسانی نشده‌اند (یعنی به
    # احتمال زیاد الان هم match نمی‌شوند، حتی اگر قبلاً می‌شدند).
    # ---------------------------------------------------------------
    expected_roster = {sk for keys in SYMBOL_MAP.values() for sk in keys} | {"bourse_total"}
    matched_roster = {item["symbol_key"] for item in accepted}
    missing_this_run = sorted(expected_roster - matched_roster)
    if missing_this_run:
        print(
            f"\n📋 {len(missing_this_run)} نماد در این اجرا اصلاً پیدا/match نشدند "
            f"(مقدار قبلی‌شان در دیتابیس دست‌نخورده مانده): {', '.join(missing_this_run)}",
            flush=True,
        )

    STALE_HOURS = 48
    try:
        now = datetime.now(pytz.timezone('Asia/Tehran'))
        stale = []
        for symbol_key, row in existing_rows.items():
            if symbol_key in matched_roster:
                continue
            try:
                last_dt = pytz.timezone('Asia/Tehran').localize(datetime.strptime(row["updated_at"], "%Y-%m-%d %H:%M:%S"))
                hours_old = (now - last_dt).total_seconds() / 3600
                if hours_old >= STALE_HOURS:
                    stale.append((symbol_key, round(hours_old)))
            except (ValueError, TypeError):
                continue
        if stale:
            stale.sort(key=lambda x: -x[1])
            print(f"\n⏰ این نمادها بیش از {STALE_HOURS} ساعت است بروزرسانی نشده‌اند (به‌احتمال زیاد الگوی match‌شان خراب شده):", flush=True)
            for symbol_key, hours_old in stale:
                print(f"   - {symbol_key}: {hours_old} ساعت قدیمی", flush=True)
    except Exception as e:
        print(f"هشدار: محاسبهٔ گزارش داده‌های قدیمی ممکن نشد: {e}", flush=True)

if __name__ == "__main__":
    data = scrape_homepage_data()

    # «شاخص کل» دیگر در صفحه اصلی نیست؛ جداگانه از صفحه اختصاصی‌اش می‌گیریم.
    bourse_total_item = fetch_bourse_total_index()
    if bourse_total_item:
        data.append(bourse_total_item)
    else:
        print("توجه: شاخص کل بورس این بار به‌روزرسانی نشد (مقدار قبلی در دیتابیس باقی می‌ماند).", flush=True)

    if data:
        update_database(data)
