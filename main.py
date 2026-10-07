import os
import re
import json
import sqlite3
import time
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
    "بیتکوین": ["btc"],
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

    # کالاهای اساسی و انرژی
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
    "نفت اپک": ["oil_opec"],
    "نفت اُپک": ["oil_opec"],
    "نفت اُوپک": ["oil_opec"],
    "سبد نفتی اوپک": ["oil_opec"],
    "بنزین (RBOB)": ["gasoline"],
    "گاز طبیعی": ["natural_gas"],
    "زغال سنگ": ["coal"],

    # شاخص‌های بورس و جهانی
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

COMMODITIES = {"cotton", "sugar", "soybeans", "wheat", "corn", "rice", "aluminum", "nickel", "lead", "zinc", "copper", "tin", "oil_crude", "oil_brent", "oil_opec", "gasoline", "natural_gas", "coal"}
BOURSE_KEYS = ("bourse_total", "bourse_market1", "bourse_market2", "bourse_equal_total", "bourse_pequal", "bourse_pweighted", "ifb_total", "ifb_market1", "ifb_market2")
INDICES = {"bourse_total", "bourse_equal_total", "ifb_total", "ifb_market1", "ifb_market2", "bourse_market1", "bourse_market2", "bourse_pequal", "bourse_pweighted", "dow_jones", "nasdaq", "smi_swiss", "nifty_50", "ftse_100", "dax", "cac_40", "nikkei_225", "shanghai_composite", "ibex_35"}
CRYPTO = {"btc", "eth", "usdt", "trx", "ada", "sol", "doge", "shib", "ton", "xrp", "ltc", "bch", "dot", "avax", "xlm", "dash", "bnb"}

# نمادهایی که قیمت آن‌ها از ریال به تومان (تقسیم بر ۱۰) تبدیل می‌شود
TOMAN_SYMBOLS = {
    # طلا، سکه و صندوق‌ها
    "coin_emami", "coin_azadi", "coin_half", "coin_quarter", "coin_gram",
    "gold_18k", "gold_24k", "gold_used", "gold_mesghal", "silver_gram",
    "abshedeh_cash", "abshedeh_trade", "mesghal_no_bubble", "bubble_emami",
    "bubble_azadi", "bubble_half", "bubble_quarter", "bubble_gram",
    "fund_ayar", "fund_lotus", "fund_gohar", "fund_mesghal", "fund_kahreba",
    "fund_nab", "fund_riton", "fund_tabesh", "fund_zarvan",

    # ارزهای سنتی
    "usd", "eur", "aed", "gbp", "try", "chf", "cny", "jpy", "krw", "cad",
    "aud", "afn", "amd", "azn", "bhd", "dkk", "gel", "hkd", "inr", "iqd",
    "kgs", "kwd", "myr", "nok", "nzd", "omr", "pkr", "qar", "rub", "sar",
    "sek", "sgd", "syp", "thb", "tjs", "tmt",

    # ارزهای دیجیتال
    "btc", "eth", "usdt", "trx", "ada", "sol", "doge", "shib", "ton",
    "xrp", "ltc", "bch", "dot", "avax", "xlm", "dash", "bnb"
}

# دسته‌بندی واحد شمارش شاخص‌ها
USD_UNIT_SYMBOLS = {
    "gold_ounce", "silver_ounce", "platinum_ounce", "palladium_ounce",
    "cotton", "sugar", "soybeans", "wheat", "corn", "rice",
    "aluminum", "nickel", "lead", "zinc", "copper", "tin",
    "oil_crude", "oil_brent", "oil_opec", "gasoline", "natural_gas", "coal"
}

UNIT_INDEX_SYMBOLS = {
    "bourse_total", "bourse_equal_total", "ifb_total", "ifb_market1", "ifb_market2", "bourse_market1", "bourse_market2",
    "bourse_pequal", "bourse_pweighted", "dow_jones", "nasdaq", "smi_swiss",
    "nifty_50", "ftse_100", "dax", "cac_40", "nikkei_225", "shanghai_composite", "ibex_35"
}

def get_unit(symbol_key: str) -> str:
    if symbol_key in TOMAN_SYMBOLS:
        return "تومان"
    elif symbol_key in USD_UNIT_SYMBOLS:
        return "دلار"
    elif symbol_key in UNIT_INDEX_SYMBOLS:
        return "واحد"
    return ""

FREE_MARKET_CURRENCY_KEYS = {
    "usd", "eur", "aed", "gbp", "try", "chf", "cny", "jpy", "krw", "cad",
    "aud", "afn", "amd", "azn", "bhd", "dkk", "gel", "hkd", "inr", "iqd",
    "kgs", "kwd", "myr", "nok", "nzd", "omr", "pkr", "qar", "rub", "sar",
    "sek", "sgd", "syp", "thb", "tjs", "tmt",
}

SANITY_DIGIT_DIFF_THRESHOLD = 3
SANITY_PERCENT_WARN_THRESHOLD = 50.0

# نمادهای حیاتی: اگر مقدار قبلی‌شان «ساعت‌دار» ثبت شده بود و مقدار جدید بدون ساعت (مثلاً فقط «۱۱ مهر»)
# و با قیمتی متفاوت آمد، احتمال کش‌بودن/ناقص‌بودن صفحه هست و مقدار قبلی نگه داشته می‌شود.
HOLD_CRITICAL_KEYS = {"usd", "eur", "gold_18k", "coin_emami", "silver_gram", "btc"}
HOLD_MAX_HOURS = 6.0  # بیش از این مدت نگه نمی‌داریم تا سیستم برای همیشه قفل نشود

_RELATIVE_TIME_WORDS = ("همین الان", "همین الآن", "چند ثانیه", "لحظاتی", "دقایقی", "دقیقه", "ساعت", "ثانیه")

def has_time_info(raw_time) -> bool:
    """آیا متن ستون زمان ردیف، ساعت واقعی (HH:MM) یا زمان نسبی («X دقیقه پیش») دارد؟ «۱۱ مهر» ندارد."""
    if not raw_time:
        return False
    text = to_english_digits(str(raw_time))
    if re.search(r'(?<!\d)\d{1,2}:\d{2}', text):
        return True
    return any(w in text for w in _RELATIVE_TIME_WORDS)

def _to_float(price_str) -> float | None:
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

# --- انتظار هوشمند برای تازه‌شدن جدول قیمت‌ها ---
# صفحهٔ اصلی tgju گاهی ابتدا اعداد کش‌شدهٔ قدیمی (مثلاً ۴۵ دقیقه قبل) را نشان می‌دهد و چند ثانیه بعد
# اعداد زنده جایگزین می‌شوند. به‌جای مکث ثابت، زمان ردیف «دلار» جدول ارز آزاد را پایش می‌کنیم.
FRESH_TARGET_MINUTES = 15.0       # ردیف دلار تا این فاصله از «اکنون» تازه حساب می‌شود
FRESH_POLL_SECONDS = 1.5          # فاصلهٔ نمونه‌برداری از صفحه
FRESH_STABLE_SECONDS = 12.0       # اگر زمان ردیف این‌قدر تغییر نکرد، قدیمیِ واقعی (بازار ساکن) فرض می‌شود
FRESH_MAX_SECONDS = 25.0          # سقف کل انتظار

def _extract_free_usd_row_time(html: str) -> str | None:
    """متن ستون «زمان» ردیف «دلار» در جدول «ارز آزاد»؛ اگر جدول/ردیف پیدا نشد None."""
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        header_tr = table.find("tr")
        header_cells = header_tr.find_all(["th", "td"]) if header_tr else []
        if not header_cells:
            continue
        first = clean_title(get_cell_text(header_cells[0]))
        if not any(lbl in first for lbl in ("ارز آزاد", "ارز ازاد")):
            continue
        if any(bad in first for bad in ("مبادله", "دولتی", "نیما", "حواله", "سنا", "مرکز")):
            continue
        time_idx = find_header_col(header_cells, ["زمان", "ساعت", "تاریخ", "تایم", "بروزرسانی"])
        if time_idx == -1:
            continue
        for row in table.find_all("tr"):
            cols = row.find_all(["td", "th"])
            if len(cols) > time_idx and clean_title(get_cell_text(cols[0])) == "دلار":
                return get_cell_text(cols[time_idx])
    return None

def _wait_until_usd_fresh(page) -> None:
    """
    تا وقتی زمان ردیف «دلار» (ارز آزاد) به کمتر از FRESH_TARGET_MINUTES از «اکنون» نرسیده صبر می‌کند.
    خروج زودهنگام: تازه شد | زمان ردیف ساعت ندارد (مثلاً «۱۱ مهر») | زمان ردیف FRESH_STABLE_SECONDS تغییر نکرد | سقف زمانی.
    """
    tz = pytz.timezone('Asia/Tehran')
    start = time.monotonic()
    last_text, last_change = None, start
    while True:
        try:
            raw = _extract_free_usd_row_time(page.content())
        except Exception:
            return
        now_m = time.monotonic()
        if raw is not None:
            if raw != last_text:
                last_text, last_change = raw, now_m
            if not has_time_info(raw):
                return
            diff = parse_row_time_diff_minutes(raw, datetime.now(tz))
            if diff is None or diff <= FRESH_TARGET_MINUTES:
                if now_m - start > 0.5:
                    print(f"✅ ردیف دلار پس از {now_m - start:.1f} ثانیه تازه شد (زمان ردیف: {raw}).", flush=True)
                return
            if now_m - last_change >= FRESH_STABLE_SECONDS:
                print(f"ℹ️ زمان ردیف دلار ({raw}) {FRESH_STABLE_SECONDS:.0f} ثانیه تغییر نکرد؛ ادامه بدون انتظار بیشتر.", flush=True)
                return
        if now_m - start >= FRESH_MAX_SECONDS:
            print(f"⚠️ تا سقف {FRESH_MAX_SECONDS:.0f} ثانیه ردیف دلار تازه نشد (زمان ردیف: {raw}).", flush=True)
            return
        page.wait_for_timeout(int(FRESH_POLL_SECONDS * 1000))

def fetch_rendered_html(url: str, extra_wait: float = 3.0, wait_for_fresh: bool = False, wait_for_selector: str | None = None) -> str | None:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            try:
                loading_el = page.locator("text='در حال بارگذاری...'").first
                loading_el.wait_for(state="detached", timeout=8000)
            except Exception:
                pass

            if wait_for_selector:
                try:
                    page.wait_for_selector(wait_for_selector, timeout=15000)
                except Exception:
                    pass

            page.wait_for_timeout(int(extra_wait * 1000))
            if wait_for_fresh:
                _wait_until_usd_fresh(page)
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
    if not text:
        return ""
    text = text.replace('\u200c', ' ').replace('\u200f', '')
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    text = text.translate(_TITLE_DIGIT_TRANSLATION)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
    
def get_cell_text(tag) -> str:
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
    if 0 < abs(val) < 0.01:
        return f"{val:,.6f}".rstrip('0').rstrip('.')
    return f"{val:,.2f}".rstrip('0').rstrip('.')

def parse_price_value(raw_text: str, is_index: bool = False) -> tuple[str, float]:
    if not raw_text or raw_text.strip() == "-" or raw_text.strip() == "":
        return "-", 0.0
    
    clean_text = to_english_digits(raw_text)
    match = re.search(r'(\d+(?:\.\d+)?)', clean_text)
    if not match:
        return "-", 0.0

    num_str = match.group(1)
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

def parse_changes(change_cell, price_val: float) -> tuple[str, str, float]:
    if not change_cell:
        return "0", "0%", 0.0
    
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

    if abs(pct_val) > 100:
        pct_val = 0.0
        amt_val = 0.0

    signed_amt = -amt_val if is_red else amt_val

    if is_red:
        amt_str = f"-{format_number_with_comma(amt_val)}" if amt_val != 0 else "0"
        pct_str = f"-{pct_val:.2f}%".rstrip('0').rstrip('.%') + "%" if pct_val != 0 else "0%"
    else:
        amt_str = format_number_with_comma(amt_val)
        pct_str = f"{pct_val:.2f}%".rstrip('0').rstrip('.%') + "%" if pct_val != 0 else "0%"

    return amt_str, pct_str, signed_amt

def format_signed_amount(signed_val: float) -> str:
    """فرمت مقدار تغییر علامت‌دار هم‌سبک parse_changes: «0»، «1,234» یا «-1,234»."""
    if not signed_val:
        return "0"
    text = format_number_with_comma(abs(signed_val))
    return f"-{text}" if signed_val < 0 else text

def find_header_col(header_cells, target_patterns) -> int:
    for idx, c in enumerate(header_cells):
        h_norm = get_cell_text(c).replace(" ", "").replace("\u200c", "")
        for pat in target_patterns:
            if pat.replace(" ", "") in h_norm:
                return idx
    return -1

def is_real_data_table(table, header_cells) -> bool:
    if table.find(["input", "select", "button"]) is not None:
        return False

    header_text = " ".join(get_cell_text(c) for c in header_cells)
    has_price_col = any(k in header_text for k in ["قیمت زنده", "قیمت", "ارزش"])
    has_change_col = "تغییر" in header_text
    return has_price_col and has_change_col

def parse_row_time_diff_minutes(raw_time_str: str, tehran_now: datetime) -> float | None:
    """
    فاصلهٔ (به دقیقه) زمان درج‌شده در ردیف جدول تا «اکنونِ تهران».
    خروجی None یعنی «قابل تشخیص نیست» (و در اعتبارسنجی نادیده گرفته می‌شود).
    پشتیبانی از: «همین الان/چند ثانیه پیش»، «X دقیقه/ساعت پیش»، «دیروز»،
    ساعت ساده (HH:MM[:SS])، و تاریخ شمسی/میلادی (به‌همراه یا بدون ساعت).
    """
    if not raw_time_str:
        return None
    text = to_english_digits(raw_time_str).strip()
    if not text or text == "-":
        return None

    if any(kw in text for kw in ["همین الان", "همین الآن", "چند ثانیه", "لحظاتی", "دقایقی"]):
        return 0.0

    m_rel = re.search(r'(\d+)\s*دقیقه', text)
    if m_rel:
        return float(m_rel.group(1))
    h_rel = re.search(r'(\d+)\s*ساعت', text)
    if h_rel:
        return float(h_rel.group(1)) * 60.0
    d_rel = re.search(r'(\d+)\s*روز', text)
    if d_rel:
        return float(d_rel.group(1)) * 1440.0
    if "دیروز" in text:
        return 1440.0

    # --- تاریخ (شمسی یا میلادی) ---
    row_date = None
    d_match = re.search(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})', text)
    if d_match:
        y, mo, d = (int(d_match.group(i)) for i in (1, 2, 3))
        try:
            if y < 1700:
                row_date = jdatetime.date(y, mo, d).togregorian()
            else:
                row_date = datetime(y, mo, d).date()
        except Exception:
            row_date = None

    # --- ساعت ---
    t_match = re.search(r'(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?(?!\d)', text)
    hour = minute = second = None
    if t_match:
        hour, minute = int(t_match.group(1)), int(t_match.group(2))
        second = int(t_match.group(3)) if t_match.group(3) else 0
        if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
            hour = minute = second = None

    today = tehran_now.date()

    if row_date is not None:
        if hour is None:
            # فقط تاریخ: اگر امروز باشد از ساعتش خبر نداریم؛ اگر قدیمی‌تر باشد قطعاً کهنه است
            days = (today - row_date).days
            return float(days * 1440) if days > 0 else None
        row_dt = tehran_now.tzinfo.localize(
            datetime(row_date.year, row_date.month, row_date.day, hour, minute, second)
        ) if hasattr(tehran_now.tzinfo, "localize") else tehran_now.replace(
            year=row_date.year, month=row_date.month, day=row_date.day,
            hour=hour, minute=minute, second=second, microsecond=0
        )
        diff_min = (tehran_now - row_dt).total_seconds() / 60.0
        return max(diff_min, 0.0)

    if hour is not None:
        row_dt = tehran_now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        diff_min = (tehran_now - row_dt).total_seconds() / 60.0
        # ساعتِ «چند دقیقه در آینده» = اختلاف جزئی ساعت سرور/سایت؛ نادیده
        if -10.0 <= diff_min < 0:
            return 0.0
        # ساعتی که از «اکنون» جلوتر است یعنی مربوط به دیروز بوده
        if diff_min < 0:
            diff_min += 1440.0
        return diff_min

    return None

def scrape_homepage_data():
    tehran_tz = pytz.timezone('Asia/Tehran')
    MAX_SCRAPE_RETRIES = 3
    RETRY_WAIT_SECONDS = 5.0
    MAX_ACCEPTABLE_TIME_DIFF_MINUTES = 45.0  # آستانه فاصله زمانی نامتعارف (۴۵ دقیقه)
    # فقط در این دو حالت «انتظار و تلاش مجدد» ارزش دارد (ردیف‌های کم‌معامله مثل
    # انس پلاتین یا سکه گرمی ممکن است به‌طور طبیعی بیش از ۴۵ دقیقه به‌روز نشوند):
    #  ۱) یکی از نمادهای حیاتی کهنه باشد
    #  ۲) درصد بالایی از کل ردیف‌ها کهنه باشد (نشانهٔ بارگذاری ناقص JS سایت)
    CRITICAL_KEYS = {"usd", "eur", "gold_18k", "coin_emami", "silver_gram", "btc"}
    CRITICAL_MAX_DIFF_MINUTES = 20.0  # آستانهٔ سخت‌گیرانه‌تر فقط برای نمادهای حیاتی (کش قدیمی ۴۰ تا ۴۵ دقیقه‌ای را هم می‌گیرد)
    SYSTEMIC_STALE_RATIO = 0.30
    MIN_ROWS_FOR_RATIO_CHECK = 10  # برای نمونهٔ خیلی کوچک، درصد معنی‌دار نیست

    sorted_targets = sorted(SYMBOL_MAP.keys(), key=len, reverse=True)
    FREE_MARKET_LABELS = ("ارز آزاد", "ارز ازاد")
    OFFICIAL_RATE_LABELS = ("نیمایی", "مبادله")
    NON_FREE_HEADER_WORDS = ("مبادله", "دولتی", "نیما", "حواله", "سنا", "مرکز")
    # آدرس پروفایل نرخ دلارِ بازار آزاد در tgju.org؛ دلار فقط با تأیید این لینک در ردیف، «قطعی» پذیرفته می‌شود
    FREE_USD_PROFILE_SLUG = "price_dollar_rl"
    TIME_HEADER_PATTERNS = ["زمان", "ساعت", "تاریخ", "تایم", "بروزرسانی", "زمان بروزرسانی"]

    def _currency_table_affinity(tbl):
        score = 0
        node, depth = tbl, 0
        while node is not None and depth < 6:
            attrs = getattr(node, "attrs", None)
            if attrs:
                blob = " ".join(
                    v if isinstance(v, str) else " ".join(v)
                    for v in attrs.values()
                )
                if any(lbl in blob for lbl in FREE_MARKET_LABELS):
                    score += 10
                if any(lbl in blob for lbl in OFFICIAL_RATE_LABELS):
                    score -= 10
            node = getattr(node, "parent", None)
            depth += 1
        return score

    best_attempt = None  # (score, scraped_data, seen_header_texts, unrecognized_titles)

    for attempt in range(1, MAX_SCRAPE_RETRIES + 1):
        print(f"در حال دریافت داده‌ها از tgju.org (تلاش {attempt} از {MAX_SCRAPE_RETRIES}) ...", flush=True)
        scraped_data = []
        seen_header_texts = []
        unrecognized_titles = set()

        try:
            html = fetch_rendered_html("https://www.tgju.org", extra_wait=3.0 * attempt, wait_for_fresh=True)
            # زمان مرجع «بعد از» رندر گرفته می‌شود، نه قبل از آن (رندر ~۱۵-۲۰ ثانیه طول می‌کشد)
            tehran_now = datetime.now(tehran_tz)
            updated_at = tehran_now.strftime("%Y-%m-%d %H:%M:%S")
            if html:
                soup = BeautifulSoup(html, "html.parser")

                # ریشهٔ باگ «دلار = 85,840 به‌جای 233,500»: تب‌های ارز کشورهای دیگر
                # هم ردیف «دلار» دارند. ارزهای آزاد فقط از کانتینر ایران پذیرفته می‌شوند.
                currency_container = soup.find(id="currency-overview-content")
                if currency_container is not None:
                    currency_tables = set(currency_container.find_all("table"))
                else:
                    currency_tables = None
                    print(
                        "⚠️ هشدار: کانتینر «currency-overview-content» پیدا نشد؛ محدودسازی ضدتداخل "
                        "ارزها غیرفعال است (فقط امتیاز affinity جدول اعمال می‌شود).",
                        flush=True,
                    )

                for table in soup.find_all("table"):
                    price_col_idx, change_col_idx = 1, 2
                    header_tr = table.find("tr")
                    header_cells = header_tr.find_all(["th", "td"]) if header_tr else []
                    table_currency_affinity = _currency_table_affinity(table)

                    seen_header_texts.append(" ".join(get_cell_text(c) for c in header_cells))

                    # قفل قطعی ارز آزاد: فقط جدولی که اولین سرستونش «ارز آزاد» است پذیرفته می‌شود.
                    # جدول‌های «ارز مبادله‌ای / دولتی»، «نرخ ارز نیما (حواله)» و مرکز مبادله رد می‌شوند.
                    header_first = clean_title(get_cell_text(header_cells[0])) if header_cells else ""
                    table_is_free_currency = (
                        any(lbl in header_first for lbl in FREE_MARKET_LABELS)
                        and not any(bad in header_first for bad in NON_FREE_HEADER_WORDS)
                    )

                    if not is_real_data_table(table, header_cells):
                        continue

                    time_col_idx = find_header_col(header_cells, TIME_HEADER_PATTERNS)

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

                        matched_fa = next(
                            (t for t in sorted_targets if clean_title(t) == row_title),
                            None
                        )
                        if not matched_fa and "/" not in row_title:
                            matched_fa = next(
                                (t for t in sorted_targets if clean_title(t) in row_title),
                                None
                            )

                        if not matched_fa and row is not header_tr and "/" not in row_title and len(row_title) >= 2:
                            unrecognized_titles.add(row_title)

                        if matched_fa:
                            symbol_keys = SYMBOL_MAP[matched_fa]
                            primary_key = symbol_keys[0]
                            if (
                                primary_key in FREE_MARKET_CURRENCY_KEYS
                                and currency_tables is not None
                                and table not in currency_tables
                            ):
                                matched_fa = None

                        usd_slug_bonus = 0
                        if matched_fa:
                            primary_key = SYMBOL_MAP[matched_fa][0]
                            if primary_key in FREE_MARKET_CURRENCY_KEYS:
                                if not table_is_free_currency:
                                    matched_fa = None
                                elif primary_key == "usd":
                                    # «دلار آمریکا» (نرخ دولتی) نباید با «دلار» اشتباه گرفته شود
                                    if row_title != clean_title("دلار"):
                                        matched_fa = None
                                    else:
                                        row_links = [a.get("href", "") for a in row.find_all("a", href=True)]
                                        if any(FREE_USD_PROFILE_SLUG in h for h in row_links):
                                            usd_slug_bonus = 100
                                        else:
                                            print(
                                                "⚠️ هشدار: ردیف «دلار» در جدول ارز آزاد پیدا شد ولی لینک "
                                                f"{FREE_USD_PROFILE_SLUG} در آن نبود (فقط با قفل سرستون پذیرفته شد).",
                                                flush=True,
                                            )

                        if matched_fa:
                            symbol_keys = SYMBOL_MAP[matched_fa]
                            primary_key = symbol_keys[0]

                            price_cell = cols[price_col_idx] if len(cols) > price_col_idx else cols[1]
                            
                            if primary_key in CRYPTO and len(cols) >= 3:
                                price_cell = cols[1]
                            elif primary_key in COMMODITIES:
                                usd_col = find_header_col(header_cells, ["قیمت/دلار", "قیمت ($)", "قیمت$"])
                                if usd_col != -1 and usd_col < len(cols):
                                    price_cell = cols[usd_col]
                                else:
                                    for c in cols[1:]:
                                        c_txt = get_cell_text(c)
                                        if "$" in c_txt or "دلار" in c_txt:
                                            price_cell = c
                                            break
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
                            change_amt, change_pct, change_num = parse_changes(change_cell, price_num)

                            # استخراج زمان و محاسبه فاصله با زمان تهران
                            raw_row_time = get_cell_text(cols[time_col_idx]) if (time_col_idx != -1 and len(cols) > time_col_idx) else ""
                            time_diff_min = parse_row_time_diff_minutes(raw_row_time, tehran_now)

                            # تبدیل قیمت از ریال به تومان برای نمادهای مشخص‌شده
                            if primary_key in TOMAN_SYMBOLS and price_num:
                                price_num = price_num / 10
                                price_str = format_number_with_comma(price_num)

                                # مقدار تغییر (change_amount) هم در همان جدول به ریال است و باید با قیمت
                                # هم‌واحد شود (درصد تغییر بدون واحد است و دست نمی‌خورد).
                                # رمزارزها مستثنی‌اند: تغییرشان بعداً از change_num خام × نرخ تومانی دلار
                                # ساخته می‌شود (پایین‌تر در همین تابع) و تقسیم بر ۱۰ آن را خراب می‌کند.
                                if primary_key not in CRYPTO:
                                    change_num = change_num / 10
                                    change_amt = format_signed_amount(change_num)

                            display_title = "نفت اوپک" if primary_key == "oil_opec" else matched_fa

                            for skey in symbol_keys:
                                scraped_data.append({
                                    "symbol_key": skey,
                                    "title_fa": display_title,
                                    "price": price_str,
                                    "unit": get_unit(skey),
                                    "price_num": price_num,
                                    "change_amount": change_amt,
                                    "change_percent": change_pct,
                                    "change_num": change_num,
                                    "updated_at": updated_at,
                                    "_affinity": table_currency_affinity + usd_slug_bonus,
                                    "_time_diff_min": time_diff_min,
                                    "row_time": raw_row_time
                                })
        except Exception as e:
            print(f"خطا در استخراج (تلاش {attempt}): {e}", flush=True)

        # ---------- اعتبارسنجی فاصله زمانی ----------
        timed = [i for i in scraped_data if i.get("_time_diff_min") is not None]
        stale_items = [i for i in timed if i["_time_diff_min"] > MAX_ACCEPTABLE_TIME_DIFF_MINUTES]
        critical_stale = [
            i for i in timed
            if i["symbol_key"] in CRITICAL_KEYS and i["_time_diff_min"] > CRITICAL_MAX_DIFF_MINUTES
        ]
        stale_ratio = (len(stale_items) / len(timed)) if timed else 0.0

        def _names(items):
            return " | ".join(dict.fromkeys(i.get("title_fa") or i["symbol_key"] for i in items))

        # نمرهٔ کیفیت این تلاش (کمتر = بهتر): بدون داده بدترین است
        score = (
            0 if scraped_data else 1,
            len(critical_stale),
            round(stale_ratio, 3),
            -len(scraped_data),
        )
        if best_attempt is None or score <= best_attempt[0]:
            best_attempt = (score, scraped_data, seen_header_texts, unrecognized_titles)

        if not timed and scraped_data:
            print("ℹ️ ستون زمان در هیچ جدولی پیدا/تفسیر نشد؛ اعتبارسنجی زمانی انجام نشد.", flush=True)
            break

        systemic_stale = len(timed) >= MIN_ROWS_FOR_RATIO_CHECK and stale_ratio >= SYSTEMIC_STALE_RATIO
        need_retry = (not scraped_data) or bool(critical_stale) or systemic_stale

        if need_retry and attempt < MAX_SCRAPE_RETRIES:
            reason = (
                f"نماد حیاتی کهنه: {_names(critical_stale)}" if critical_stale
                else f"{len(stale_items)} از {len(timed)} ردیف ({stale_ratio:.0%}) کهنه" if scraped_data
                else "هیچ داده‌ای استخراج نشد"
            )
            limit_shown = CRITICAL_MAX_DIFF_MINUTES if critical_stale else MAX_ACCEPTABLE_TIME_DIFF_MINUTES
            print(
                f"⚠ فاصله زمانی نامتعارف با تایم تهران (>{limit_shown:.0f} دقیقه) - {reason}. "
                f"{RETRY_WAIT_SECONDS:.0f} ثانیه صبر و تلاش مجدد...",
                flush=True,
            )
            time.sleep(RETRY_WAIT_SECONDS)
            continue

        if stale_items:
            print(
                f"ℹ️ {len(stale_items)} نماد ({_names(stale_items)}) بیش از "
                f"{MAX_ACCEPTABLE_TIME_DIFF_MINUTES:.0f} دقیقه از تایم تهران فاصله دارند "
                f"(احتمال تعطیلی بازار/کم‌معامله بودن). بهترین نتیجهٔ به‌دست‌آمده ثبت می‌شود.",
                flush=True,
            )
        break

    if best_attempt is not None:
        _, scraped_data, seen_header_texts, unrecognized_titles = best_attempt
    else:
        scraped_data, seen_header_texts, unrecognized_titles = [], [], set()

    unique_data = {}
    best_affinity = {}
    for item in scraped_data:
        key = item["symbol_key"]
        affinity = item.pop("_affinity", 0)
        item.pop("_time_diff_min", None)
        if key not in unique_data:
            unique_data[key] = item
            best_affinity[key] = affinity
        elif key in FREE_MARKET_CURRENCY_KEYS:
            if affinity > best_affinity.get(key, 0) or (unique_data[key]["price"] == "-" and item["price"] != "-"):
                unique_data[key] = item
                best_affinity[key] = affinity
        elif unique_data[key]["price"] == "-":
            unique_data[key] = item

    # ضرب مقدار تغییرات رمزارزها در نرخ تومانی دلار
    usd_item = unique_data.get("usd")
    usd_price_toman = _to_float(usd_item["price"]) if usd_item else None

    if usd_price_toman and usd_price_toman > 0:
        for item in unique_data.values():
            if item["symbol_key"] in CRYPTO:
                raw_change = item.get("change_num", 0.0)
                if raw_change != 0:
                    toman_change = raw_change * usd_price_toman
                    item["change_amount"] = format_number_with_comma(toman_change)

    if "usd" not in unique_data:
        print(
            "🚨 هشدار جدی: نرخ دلارِ بازار آزاد (جدول «ارز آزاد»، لینک price_dollar_rl) پیدا نشد؛ "
            "مقدار قبلی دلار در دیتابیس دست‌نخورده می‌ماند و تریگر پروژه دوم ارسال نمی‌شود.",
            flush=True,
        )

    for item in unique_data.values():
        item.pop("price_num", None)
        item.pop("change_num", None)

    known_header_keywords = ["قیمت زنده", "آخرین قیمت", "قیمت / دلار", "ارزش", "تغییر"]
    all_headers_text = " ".join(seen_header_texts)
    if seen_header_texts and not any(kw in all_headers_text for kw in known_header_keywords):
        print(
            "🚨 هشدار جدی: هیچ‌کدام از سرستون‌های شناخته‌شده در هیچ جدولی روی صفحه پیدا نشد.",
            flush=True,
        )

    if unrecognized_titles:
        sample = sorted(unrecognized_titles)[:15]
        print(
            f"\n💡 {len(unrecognized_titles)} عنوان ردیف ناشناخته پیدا شد: {' | '.join(sample)}",
            flush=True,
        )

    return list(unique_data.values())


_SHAKHESBAN_URL = "https://www.shakhesban.com/markets/index"

def _sb_norm(text: str) -> str:
    t = clean_title(text or "")
    t = re.sub(r'[\s()\[\]\-–—_/\\،,.:]+', '', t)
    return t

def _sb_key_for(name: str, market_type: str = "") -> str | None:
    n = _sb_norm(name)
    mt = _sb_norm(market_type)
    if not n.startswith("شاخص"):
        return None
    is_ifb = "فرابورس" in n or "فرابورس" in mt
    n = n.replace("فرابورس", "").replace("بورس", "")
    if n == "شاخصکل":
        return "ifb_total" if is_ifb else "bourse_total"
    if is_ifb:
        return {"شاخصبازاراول": "ifb_market1", "شاخصبازاردوم": "ifb_market2"}.get(n)
    return {
        "شاخصکلهموزن": "bourse_equal_total",
        "شاخصبازاراول": "bourse_market1",
        "شاخصبازاردوم": "bourse_market2",
        "شاخصقیمتهموزن": "bourse_pequal",
        "شاخصقیمتوزنیارزشی": "bourse_pweighted",
    }.get(n)

_SB_TITLES = {
    "bourse_total": "شاخص کل بورس",
    "bourse_market1": "شاخص بازار اول",
    "bourse_market2": "شاخص بازار دوم",
    "bourse_equal_total": "شاخص کل (هم وزن)",
    "bourse_pequal": "شاخص قیمت (هم وزن)",
    "bourse_pweighted": "شاخص قیمت (وزنی - ارزشی)",
    "ifb_total": "شاخص کل فرابورس",
    "ifb_market1": "شاخص بازار اول فرابورس",
    "ifb_market2": "شاخص بازار دوم فرابورس",
}

def _sb_number(text: str):
    """(عدد مطلق یا None, آیا علامت منفی صریح دارد)"""
    if not text:
        return None, False
    t = to_english_digits(text).replace('٬', '').replace('٫', '.').replace('٪', '').replace('%', '')
    t = t.replace('‎', '').replace('‏', '').replace('‪', '').replace('‬', '')
    m = re.search(r'([+\-])?\s*(\d+(?:\.\d+)?)', t)
    if not m:
        return None, False
    neg = (m.group(1) == '-') or bool(re.search(r'(\d\s*-)|(\(\s*\d)', t)) or "🔻" in text
    return float(m.group(2)), neg

def _sb_header_grid(rows):
    grid = []
    spans = {}
    for r_i, tr in enumerate(rows):
        line = []
        col = 0
        cells = tr.find_all(["th", "td"])
        ci = 0
        while ci < len(cells) or col in spans:
            if col in spans and spans[col][0] > 0:
                line.append(spans[col][1])
                spans[col] = (spans[col][0] - 1, spans[col][1])
                if spans[col][0] == 0:
                    del spans[col]
                col += 1
                continue
            if ci >= len(cells):
                break
            c = cells[ci]; ci += 1
            txt = clean_title(get_cell_text(c))
            try:
                cs = max(1, int(c.get("colspan", 1)))
                rs = max(1, int(c.get("rowspan", 1)))
            except Exception:
                cs, rs = 1, 1
            for _ in range(cs):
                line.append(txt)
                if rs > 1:
                    spans[col] = (rs - 1, txt)
                col += 1
        grid.append(line)
    return grid

def parse_shakhesban_indices(html: str, updated_at: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    results = {}
    for table in soup.find_all("table"):
        trs = table.find_all("tr")
        head_rows = [tr for tr in trs if tr.find("th") and not tr.find("td")]
        data_rows = [tr for tr in trs if tr.find("td")]
        if not data_rows:
            continue
        idx = {}
        if head_rows:
            grid = _sb_header_grid(head_rows)
            ncols = max((len(l) for l in grid), default=0)
            labels = []
            for c in range(ncols):
                parts = [l[c] for l in grid if c < len(l)]
                labels.append(" | ".join(parts))
            def pick(pred):
                cands = [i for i, lb in enumerate(labels) if pred(lb)]
                pref = [i for i in cands if "آخرین" in labels[i]]
                return (pref or cands or [None])[0]
            idx["name"] = pick(lambda lb: lb.strip().endswith("نام") or lb == "نام")
            idx["mtype"] = pick(lambda lb: "نوع بازار" in lb)
            idx["value"] = pick(lambda lb: "مقدار" in lb)
            idx["change"] = pick(lambda lb: "تغییر" in lb and "درصد" not in lb)
            idx["pct"] = pick(lambda lb: "درصد" in lb)
            idx["date"] = pick(lambda lb: "تاریخ" in lb)
        for tr in data_rows:
            cells = tr.find_all(["td", "th"])
            texts = [get_cell_text(c) for c in cells]
            name_i = idx.get("name") if idx.get("name") is not None and idx["name"] < len(cells) else 0
            name = texts[name_i] if texts else ""
            mt = texts[idx["mtype"]] if idx.get("mtype") is not None and idx["mtype"] < len(cells) else ""
            key = _sb_key_for(name, mt)
            if not key or key in results:
                continue
            def cell(k):
                i = idx.get(k)
                return (i, cells[i]) if i is not None and i < len(cells) else (None, None)
            vi, vc = cell("value"); ci_, cc = cell("change"); pi, pc = cell("pct"); di, dc = cell("date")
            if vc is None or cc is None or pc is None:
                # فالبک: سه سلول عددی اول بعد از نام
                nums = [(i, c) for i, c in enumerate(cells) if i != name_i and _sb_number(texts[i])[0] is not None and not re.search(r'\d{4}/\d{1,2}/\d{1,2}', to_english_digits(texts[i]))]
                if len(nums) < 3:
                    print(f"⚠️ شاخص‌بان: ساختار ردیف «{name}» قابل تشخیص نبود.", flush=True)
                    continue
                (vi, vc), (ci_, cc), (pi, pc) = nums[0], nums[1], nums[2]
            value, _ = _sb_number(get_cell_text(vc))
            chg, chg_neg = _sb_number(get_cell_text(cc))
            pct, pct_neg = _sb_number(get_cell_text(pc))
            if value is None or value <= 0:
                print(f"⚠️ شاخص‌بان: مقدار «{name}» نامعتبر است ({get_cell_text(vc)!r}).", flush=True)
                continue
            neg = chg_neg or pct_neg or (chg is not None and chg != 0 and is_cell_red(cc))
            if chg is None and pct is not None:
                chg = abs(value - value / (1 + (-pct if neg else pct) / 100.0))
            if chg is not None:
                signed = -abs(chg) if neg else abs(chg)
                prev = value - signed
                calc_pct = (signed / prev * 100.0) if prev else 0.0
                if pct is None:
                    pct_signed = calc_pct
                else:
                    pct_signed = -abs(pct) if neg else abs(pct)
                    if abs(pct_signed - calc_pct) > 0.05:
                        print(f"ℹ️ شاخص‌بان: درصد {name}: سایت {pct_signed:.2f} ≠ محاسبه‌شده {calc_pct:.2f}", flush=True)
            else:
                signed, pct_signed = 0.0, 0.0
            date_txt = get_cell_text(dc).strip() if dc is not None else ""
            chg_str = "0" if signed == 0 else format_number_with_comma(round(signed, 2))
            pct_str = "0%" if round(pct_signed, 2) == 0 else f"{pct_signed:.2f}%"
            results[key] = {
                "symbol_key": key,
                "title_fa": _SB_TITLES[key],
                "price": format_number_with_comma(value),
                "unit": get_unit(key),
                "change_amount": chg_str,
                "change_percent": pct_str,
                "updated_at": updated_at,
                "row_time": date_txt,
            }
    return [results[k] for k in BOURSE_KEYS if k in results]


def fetch_shakhesban_indices() -> list:
    tehran_tz = pytz.timezone('Asia/Tehran')
    for attempt in range(1, 4):
        try:
            updated_at = datetime.now(tehran_tz).strftime("%Y-%m-%d %H:%M:%S")
            html = fetch_rendered_html(_SHAKHESBAN_URL, extra_wait=2.0 * attempt, wait_for_selector="table tbody tr")
            if html:
                items = parse_shakhesban_indices(html, updated_at)
                if items:
                    missing = [k for k in BOURSE_KEYS if k not in {i["symbol_key"] for i in items}]
                    if missing:
                        print(f"⚠️ شاخص‌بان: شاخص‌های پیدا‌نشده (مقدار قبلی حفظ می‌شود): {', '.join(missing)}", flush=True)
                    return items
            print(f"⚠️ شاخص‌بان: تلاش {attempt} بدون نتیجه.", flush=True)
        except Exception as e:
            print(f"❌ خطا در شاخص‌بان (تلاش {attempt}): {e}", flush=True)
    return []

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


def write_data_json(accepted):
    """ساخت/به‌روزرسانی snapshot استاتیک data.json از داده‌های پذیرفته‌شده"""
    json_path = "data.json"
    temp_path = f"{json_path}.tmp"
    try:
        clean_items = [{k: v for k, v in x.items() if k != "row_time"} for x in accepted]
        sorted_json_data = sorted(clean_items, key=lambda x: x.get("title_fa", ""))
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(sorted_json_data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp_path, json_path)
        print(
            f"فایل {json_path} با موفقیت ایجاد/بروزرسانی شد ({len(sorted_json_data)} رکورد).",
            flush=True,
        )
        return True
    except Exception as e:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        print(f"خطا در ایجاد فایل {json_path}: {e}", flush=True)
        return False

def update_database(data_list):
    existing_rows = {}
    obsolete_keys = []
    conn = None
    db_committed = False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_prices (
                symbol_key TEXT PRIMARY KEY,
                title_fa TEXT,
                price TEXT,
                unit TEXT,
                change_amount TEXT,
                change_percent TEXT,
                updated_at TEXT
            )
        """)

        # در صورتی که جدول قبلاً بدون ستون unit ساخته شده باشد، ستون را اضافه می‌کند
        try:
            cursor.execute("ALTER TABLE market_prices ADD COLUMN unit TEXT")
        except Exception:
            pass

        # متن خام ستون «زمان» ردیف (برای تشخیص ساعت‌دار/بی‌ساعت بودن مقدار ذخیره‌شده)
        try:
            cursor.execute("ALTER TABLE market_prices ADD COLUMN row_time TEXT")
        except Exception:
            pass

        for row in cursor.execute(
            "SELECT symbol_key, title_fa, price, unit, change_amount, change_percent, updated_at, row_time FROM market_prices"
        ).fetchall():
            existing_rows[row[0]] = {
                "symbol_key": row[0],
                "title_fa": row[1],
                "price": row[2],
                "unit": row[3],
                "change_amount": row[4],
                "change_percent": row[5],
                "updated_at": row[6],
                "row_time": row[7],
            }

        obsolete_keys = sorted(k for k in existing_rows if k.startswith(("bourse_", "ifb_")) and k not in BOURSE_KEYS)
    except Exception as e:
        print(f"⚠️ هشدار: عدم امکان برقراری ارتباط با دیتابیس جهت خواندن مقادیر قبلی ({e}) — پردازش ادامه می‌یابد.", flush=True)

    # حذف شاخص‌های بورسی ایران که دیگر در منبع جدید (شاخص‌بان) نیستند
    if obsolete_keys:
        print(f"\n🗑️ حذف شاخص‌های بورسی منسوخ از دیتابیس و JSON: {', '.join(obsolete_keys)}", flush=True)
        for k in obsolete_keys:
            existing_rows.pop(k, None)
            try:
                cursor.execute("DELETE FROM market_prices WHERE symbol_key = ?", (k,))
            except Exception as e:
                print(f"⚠️ حذف {k} از دیتابیس ناموفق بود: {e}", flush=True)

    accepted = []
    rejected_anomalies = []
    held_back = []
    invalid_prices = []
    _tz = pytz.timezone('Asia/Tehran')

    for item in data_list:
        old = existing_rows.get(item["symbol_key"])
        old_val = _to_float(old["price"]) if old else None
        new_val = _to_float(item["price"])

        # قیمت نامعتبر ("-"، خالی، غیرعددی یا صفر/منفی) هرگز جایگزین مقدار قبلی نمی‌شود
        if new_val is None or new_val <= 0:
            invalid_prices.append({
                "symbol_key": item["symbol_key"],
                "title_fa": item["title_fa"],
                "old_price": old["price"] if old else "-",
                "new_price": item["price"],
            })
            continue

        if old_val is not None and new_val is not None and old_val != 0:
            old_digits, new_digits = _digit_count(old_val), _digit_count(new_val)
            if abs(old_digits - new_digits) >= SANITY_DIGIT_DIFF_THRESHOLD:
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
                    f"⚠️ هشدار: {item['symbol_key']} ({item['title_fa']}) با {percent_change:.0f}% تغییر کرده.",
                    flush=True,
                )

        # نگه‌داشتن مقدار قبلی: نماد حیاتی + قبلی ساعت‌دار + جدید بی‌ساعت + قیمت متفاوت + قبلی تازه
        if (
            item["symbol_key"] in HOLD_CRITICAL_KEYS
            and old
            and has_time_info(old.get("row_time"))
            and not has_time_info(item.get("row_time"))
            and item["price"] != old["price"]
        ):
            try:
                old_dt = _tz.localize(datetime.strptime(old["updated_at"], "%Y-%m-%d %H:%M:%S"))
                old_age_h = (datetime.now(_tz) - old_dt).total_seconds() / 3600
            except (ValueError, TypeError):
                old_age_h = None
            if old_age_h is not None and old_age_h <= HOLD_MAX_HOURS:
                held_back.append({
                    "symbol_key": item["symbol_key"],
                    "title_fa": item["title_fa"],
                    "old_price": old["price"],
                    "new_price": item["price"],
                    "new_time": item.get("row_time", ""),
                })
                continue

        # قیمت یکسان ولی بدون ساعت: وضعیت «ساعت‌دار» قبلی را حفظ می‌کنیم تا قفل نگه‌داشتن از بین نرود
        if (
            old
            and item["symbol_key"] in HOLD_CRITICAL_KEYS
            and has_time_info(old.get("row_time"))
            and not has_time_info(item.get("row_time"))
            and item["price"] == old["price"]
        ):
            item["row_time"] = old["row_time"]

        accepted.append(item)

    complete_snapshot = dict(existing_rows)
    for item in accepted:
        complete_snapshot[item["symbol_key"]] = item
    write_data_json(list(complete_snapshot.values()))

    if conn:
        try:
            for item in accepted:
                cursor.execute("""
                    INSERT INTO market_prices (symbol_key, title_fa, price, unit, change_amount, change_percent, updated_at, row_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol_key) DO UPDATE SET
                        title_fa = excluded.title_fa,
                        price = excluded.price,
                        unit = excluded.unit,
                        change_amount = excluded.change_amount,
                        change_percent = excluded.change_percent,
                        updated_at = excluded.updated_at,
                        row_time = excluded.row_time
                """, (
                    item["symbol_key"],
                    item["title_fa"],
                    item["price"],
                    item["unit"],
                    item["change_amount"],
                    item["change_percent"],
                    item["updated_at"],
                    item.get("row_time", "")
                ))

            conn.commit()
            db_committed = True
            print(f"تعداد {len(accepted)} شاخص در دیتابیس بروزرسانی شد.", flush=True)
        except Exception as e:
            print(f"❌ خطای دیتابیس (فایل data.json بدون مشکل تولید شد): {e}", flush=True)
        finally:
            try:
                conn.close()
            except Exception:
                pass
    else:
        print("ℹ️ دیتابیس در دسترس نبود اما data.json با موفقیت به‌روزرسانی شد.", flush=True)

    if invalid_prices:
        print(f"\n🚫 {len(invalid_prices)} نماد به‌دلیل قیمت نامعتبر ثبت نشد (مقدار قبلی حفظ شد):", flush=True)
        for v in invalid_prices:
            print(f"   - {v['symbol_key']} ({v['title_fa']}): قبلی {v['old_price']} <- دیده‌شده (نامعتبر) {v['new_price']!r}", flush=True)

    if held_back:
        print(f"\n⏸️ {len(held_back)} نماد حیاتی به‌دلیل «مقدار جدید بدون ساعت» نگه داشته شد (مقدار قبلی ساعت‌دار حفظ شد):", flush=True)
        for h in held_back:
            print(
                f"   - {h['symbol_key']} ({h['title_fa']}): نگه‌داشته {h['old_price']} <- دیده‌شده (نادیده) {h['new_price']} [زمان: {h['new_time'] or '-'}]",
                flush=True,
            )

    if rejected_anomalies:
        print(f"\n🚫 {len(rejected_anomalies)} مورد به دلیل جهش رقمی مشکوک رد شدند:", flush=True)
        for a in rejected_anomalies:
            print(
                f"   - {a['symbol_key']} ({a['title_fa']}): مقدار قبلی {a['old_price']} <- مقدار جدید (رد شد) {a['new_price']}",
                flush=True,
            )

    expected_roster = {sk for keys in SYMBOL_MAP.values() for sk in keys} | set(BOURSE_KEYS)
    matched_roster = {item["symbol_key"] for item in accepted}
    missing_this_run = sorted(expected_roster - matched_roster)
    if missing_this_run:
        print(f"\n📋 {len(missing_this_run)} نماد در این اجرا پیدا نشدند: {', '.join(missing_this_run)}", flush=True)

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

    return {
        "existing_rows": existing_rows,
        "accepted": accepted,
        "db_committed": db_committed,
    }

def detect_usd_change(update_result) -> bool:
    """
    تغییر قیمت دلار را با مقایسهٔ «قیمت قبلیِ ذخیره‌شده در دیتابیس» و «قیمت جدیدِ پذیرفته‌شده» تشخیص می‌دهد.
    (ران‌نر GitHub Actions در هر اجرا از نو ساخته می‌شود، پس ذخیره در فایل محلی ماندگار نیست.)
    فقط وقتی True برمی‌گردد که قیمت جدید در دیتابیس ثبت شده باشد، تا تریگر تکراری یا بی‌پایه ارسال نشود.
    """
    if not update_result:
        return False
    if not update_result.get("db_committed"):
        print("ℹ️ دیتابیس به‌روزرسانی نشد؛ تشخیص تغییر دلار انجام نمی‌شود.", flush=True)
        return False

    old_row = update_result["existing_rows"].get("usd")
    new_item = next((i for i in update_result["accepted"] if i["symbol_key"] == "usd"), None)

    if not new_item or new_item.get("price") in (None, "", "-"):
        print("⚠️ قیمت معتبر دلار در این اجرا پذیرفته نشد.", flush=True)
        return False
    if not old_row or old_row.get("price") in (None, "", "-"):
        print("ℹ️ قیمت قبلی دلار در دیتابیس نبود (اولین اجرا)؛ تریگر ارسال نمی‌شود.", flush=True)
        return False

    old_price, new_price = old_row["price"], new_item["price"]
    if old_price != new_price:
        print(f"🔄 تغییر قیمت دلار شناسایی شد! قبلی: {old_price} | جدید: {new_price}", flush=True)
        return True

    print(f"ℹ️ قیمت دلار تغییری نکرده است ({new_price}).", flush=True)
    return False

def _trigger_already_sent(day: str) -> bool:
    """
    آیا تریگر پروژه دوم برای این روز قبلاً با موفقیت ارسال شده؟
    اگر وضعیت قابل خواندن نباشد True برمی‌گرداند (محافظه‌کارانه) تا با خرابی دیتابیس،
    تریگر تکراری و پست‌های تکراری ارسال نشود.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS project2_triggers (trigger_date TEXT PRIMARY KEY)")
        row = cur.execute("SELECT 1 FROM project2_triggers WHERE trigger_date = ?", (day,)).fetchone()
        return row is not None
    except Exception as e:
        print(f"⚠️ خواندن وضعیت تریگر ممکن نشد ({e}) — برای جلوگیری از ارسال تکراری، تریگر ارسال نمی‌شود.", flush=True)
        return True
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _mark_trigger_sent(day: str) -> bool:
    """ثبت ارسال موفق تریگر امروز؛ در صورت خطا یک بار دیگر تلاش می‌کند."""
    for attempt in (1, 2):
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS project2_triggers (trigger_date TEXT PRIMARY KEY)")
            cur.execute("INSERT OR IGNORE INTO project2_triggers (trigger_date) VALUES (?)", (day,))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ ثبت وضعیت تریگر ممکن نشد (تلاش {attempt} از 2): {e}", flush=True)
        finally:
            try:
                conn.close()
            except Exception:
                pass
    return False


def _send_project_2_dispatch(reason: str) -> bool:
    """ارسال repository_dispatch به پروژه دوم. موفقیت = کد ۲۰۴."""
    REPO_OWNER = "Rozbix"
    REPO_NAME = "nerkhemroozchand-NEW"
    GITHUB_TOKEN = os.getenv("GH_PAT")

    if not GITHUB_TOKEN:
        print("❌ خطا: متغیر GH_PAT یافت نشد.", flush=True)
        return False

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/dispatches"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    # event_type ثابت می‌ماند تا workflow پروژه دوم نیازی به تغییر نداشته باشد؛ دلیل ارسال در client_payload است
    data = {"event_type": "usd_price_changed", "client_payload": {"reason": reason}}

    try:
        res = requests.post(url, json=data, headers=headers, timeout=15)
        if res.status_code == 204:
            print("✅ پروژه دوم با موفقیت تریگر شد.", flush=True)
            return True
        print(f"❌ خطا در ارسال درخواست: {res.status_code} - {res.text}", flush=True)
    except Exception as e:
        print(f"❌ خطای ارتباطی: {e}", flush=True)
    return False


def check_and_trigger_project_2(has_price_changed: bool):
    """
    تریگر پروژهٔ دوم (حداکثر یک بار در روز، به وقت تهران):
      ۱) اولین تغییر قیمت دلار در بازهٔ ۱۰:۰۰ تا ۱۱:۲۰ → تریگر فوری.
      ۲) اگر تا ۱۱:۲۰ تغییری نیامده بود → اولین اجرای بعد از ۱۱:۲۰ تریگر پیش‌فرض می‌فرستد
         (حتی بدون تغییر قیمت)، تا ساعت ۱۷:۰۰ که پایان پست‌های ساعتی است.
    """
    tehran_tz = pytz.timezone('Asia/Tehran')
    now = datetime.now(tehran_tz).time()

    start_time = datetime.strptime("10:00", "%H:%M").time()
    end_time = datetime.strptime("11:20", "%H:%M").time()
    cutoff_time = datetime.strptime("17:00", "%H:%M").time()

    if now < start_time:
        print(f"\nℹ️ زمان فعلی ({now.strftime('%H:%M')}) پیش از ۱۰:۰۰ است؛ تریگر پروژه دوم بررسی نمی‌شود.", flush=True)
        return

    if now > cutoff_time:
        print(f"\nℹ️ زمان فعلی ({now.strftime('%H:%M')}) پس از ۱۷:۰۰ است؛ تریگر پروژه دوم ارسال نمی‌شود.", flush=True)
        return

    in_change_window = now <= end_time

    if in_change_window and not has_price_changed:
        print("\nℹ️ در بازه ۱۰:۰۰ تا ۱۱:۲۰ هستیم اما تغییری در قیمت دلار رخ نداده است (در صورت نبود تغییر، بعد از ۱۱:۲۰ تریگر پیش‌فرض ارسال می‌شود).", flush=True)
        return

    if in_change_window:
        reason = "usd_price_changed"
        print("\n🚀 تغییر قیمت در بازه ۱۰:۰۰ تا ۱۱:۲۰ شناسایی شد. در حال ارسال دستور به پروژه دوم...", flush=True)
    else:
        reason = "default_after_1120"
        print("\n⏰ ساعت از ۱۱:۲۰ گذشته است؛ در صورت ارسال‌نشدن تریگر امروز، تریگر پیش‌فرض ارسال می‌شود...", flush=True)

    today_str = datetime.now(tehran_tz).strftime("%Y-%m-%d")
    if _trigger_already_sent(today_str):
        print("ℹ️ تریگر امروز قبلاً ارسال شده (یا وضعیتش نامشخص است)؛ دوباره ارسال نمی‌شود.", flush=True)
        return

    if _send_project_2_dispatch(reason):
        if not _mark_trigger_sent(today_str):
            print("🚨 هشدار: تریگر ارسال شد ولی ثبتش در دیتابیس ممکن نشد؛ اجرای بعدی ممکن است دوباره ارسال کند.", flush=True)


if __name__ == "__main__":
    try:
        data = scrape_homepage_data()

        data.extend(fetch_shakhesban_indices())

        if data:
            update_result = update_database(data)

            # تریگر پروژه دوم نباید جلوی دیپلوی را بگیرد؛ خطای آن جداگانه مهار می‌شود
            try:
                check_and_trigger_project_2(detect_usd_change(update_result))
            except Exception as e:
                print(f"❌ خطا در بررسی/تریگر پروژه دوم: {e}", flush=True)
        else:
            print("⚠️ هیچ داده‌ای در این اجرا استخراج نشد.", flush=True)
    except Exception as e:
        print(f"❌ خطای غیرمنتظره در اجرای اسکریپت: {e}", flush=True)
