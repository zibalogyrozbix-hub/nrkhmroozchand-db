import os
import re
import sys
import json
import time
import requests
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
import jdatetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or os.environ.get('BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL_ID') or os.environ.get('CHANNEL_ID')

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

# --- تنظیمات اجرا (با متغیر محیطی قابل تغییر) ---
# فایل ذخیره آخرین قیمت‌های منتشرشده برای چک معقول‌بودن
STATE_FILE = os.environ.get("STATE_FILE", "last_market.json")
# حداکثر تغییر مجاز نسبت به پست قبلی (۰.۱۰ = ۱۰٪)
MAX_MOVE_RATIO = float(os.environ.get("MAX_MOVE_RATIO", "0.10"))
# FORCE_POST=1 چک معقول‌بودن را نادیده می‌گیرد (مثلاً بعد از تعطیلات طولانی)
FORCE_POST = os.environ.get("FORCE_POST", "").strip() == "1"
# MARKET_CLOSED=1 پست را به‌صورت «آخرین معامله» برچسب می‌زند (برای تعطیلات رسمی)
FORCE_MARKET_CLOSED = os.environ.get("MARKET_CLOSED", "").strip() == "1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

SYMBOL_MAP = {
    "سکه امامی": ["coin_emami"],
    "طلای ۱۸ عیار": ["gold_18k"],
    "انس طلا": ["gold_ounce"],
    "دلار": ["usd"],
    "بیتکوین": ["btc"],
    "بیت کوین": ["btc"],
    "نفت برنت": ["oil_brent"]
}

TOMAN_SYMBOLS = {"coin_emami", "gold_18k", "usd"}
USD_UNIT_SYMBOLS = {"gold_ounce", "oil_brent", "btc"}
UNIT_INDEX_SYMBOLS = {"bourse_total"}

# نمادهایی که بدون آن‌ها پست منتشر نمی‌شود
REQUIRED_SYMBOLS = ["usd", "coin_emami", "gold_18k", "gold_ounce", "btc", "oil_brent", "bourse_total"]


class FatalError(Exception):
    """خطایی که باید اجرا را با کد خروج ۱ متوقف کند."""


def mask_secrets(text) -> str:
    """توکن ربات را از هر متنی که قرار است چاپ شود حذف می‌کند."""
    text = str(text)
    if TELEGRAM_BOT_TOKEN:
        text = text.replace(TELEGRAM_BOT_TOKEN, "***")
    return re.sub(r'bot\d+:[\w-]+', 'bot***', text)


def log(msg) -> None:
    print(mask_secrets(msg), flush=True)


def get_unit(symbol_key: str) -> str:
    if symbol_key in TOMAN_SYMBOLS:
        return "تومان"
    elif symbol_key in USD_UNIT_SYMBOLS:
        return "دلار"
    elif symbol_key in UNIT_INDEX_SYMBOLS:
        return "واحد"
    return ""


def fetch_rendered_html(url: str, wait_selector: str, extra_wait: float = 1.0, attempts: int = 2) -> str | None:
    """
    صفحه را رندر می‌کند و به‌جای sleep کور، منتظر ظاهر شدن خود ردیف‌های جدول می‌ماند.
    """
    for attempt in range(1, attempts + 1):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(user_agent=HEADERS["User-Agent"])
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    try:
                        page.wait_for_selector(wait_selector, state="attached", timeout=20000)
                    except PlaywrightTimeoutError:
                        log(f"⚠️ سلکتور «{wait_selector}» پیدا نشد؛ تلاش با سلکتور عمومی جدول ({url})")
                        page.wait_for_selector("table tr td", state="attached", timeout=5000)
                    # اگر متن «در حال بارگذاری» هنوز هست، صبر کن تا برود
                    try:
                        page.wait_for_function(
                            "() => !document.body.innerText.includes('در حال بارگذاری')",
                            timeout=8000,
                        )
                    except PlaywrightTimeoutError:
                        pass
                    page.wait_for_timeout(int(extra_wait * 1000))
                    return page.content()
                finally:
                    browser.close()
        except Exception as e:
            log(f"❌ خطا در رندر صفحه ({url}) تلاش {attempt}/{attempts}: {e}")
            if attempt < attempts:
                time.sleep(2)
    return None

_TITLE_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

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
    val = float(num_str) if "." in num_str else int(num_str)
    
    if is_index or "میلیون" in raw_text or "میلیون" in clean_text:
        if "میلیون" in raw_text:
            val = val * 1_000_000
    elif "هزار" in raw_text:
        val = val * 1_000

    return format_number_with_comma(val), float(val)

# ---------------------------------------------------------------------------
# تشخیص جهت تغییر: فقط کلاس‌ها/رنگ‌های «دقیق» و علامت عددی؛
# اگر چیزی قطعی نبود، نتیجه «نامشخص» (None) است، نه سبز.
# ---------------------------------------------------------------------------
UP_CLASSES = {"high", "up", "green", "success", "plus", "positive", "text-success", "text-green"}
DOWN_CLASSES = {"low", "down", "red", "danger", "minus", "negative", "drop", "text-danger", "text-red"}
UP_COLORS = {"green", "#0f0", "#00ff00", "#22c55e", "#16a34a", "#4ade80"}
DOWN_COLORS = {"red", "#f00", "#ff0000", "#ef4444", "#dc2626", "#f87171"}

# منفی: «-2.1» یا «2.1-» (در متن راست‌به‌چپ)؛ تیره بین دو عدد (بازه) حساب نمی‌شود
_NEG_TEXT = re.compile(r'(?<![\w.])[-−–]\s*\d|\d\s*[-−–](?![\w])')
_POS_TEXT = re.compile(r'(?<![\w.])\+\s*\d|\d\s*\+(?!\d)')


def detect_direction(cell_tag) -> str | None:
    """'up' | 'down' | None (نامشخص)."""
    if cell_tag is None:
        return None
    text = get_cell_text(cell_tag)

    neg = bool(_NEG_TEXT.search(text)) or any(m in text for m in ("🔻", "▼"))
    pos = bool(_POS_TEXT.search(text)) or any(m in text for m in ("🔺", "▲"))
    if neg and not pos:
        return "down"
    if pos and not neg:
        return "up"
    if neg and pos:
        return None

    if isinstance(cell_tag, str):
        return None

    # کلاس‌ها: فقط خود سلول و فرزندانش، و فقط تطبیق دقیق توکن (نه زیررشته)
    class_tokens = set()
    colors = set()
    for node in [cell_tag] + cell_tag.find_all(True):
        class_tokens.update(str(c).lower() for c in (node.get("class") or []))
        for m in re.finditer(r'(?:^|;)\s*color\s*:\s*([^;]+)', str(node.get("style", "")).lower()):
            colors.add(m.group(1).strip())

    down = bool(class_tokens & DOWN_CLASSES) or bool(colors & DOWN_COLORS)
    up = bool(class_tokens & UP_CLASSES) or bool(colors & UP_COLORS)
    if down and not up:
        return "down"
    if up and not down:
        return "up"
    return None


def parse_changes(change_cell, price_val: float) -> tuple[str, str, float, str]:
    """
    خروجی: (مقدار تغییر, درصد تغییر, درصد علامت‌دار, direction)
    direction یکی از: up / down / flat / unknown
    """
    if change_cell is None:
        return "0", "0%", 0.0, "unknown"

    raw_text = get_cell_text(change_cell)
    clean_text = to_english_digits(raw_text).replace("٫", ".")

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
    if pct_val > 100:
        log(f"⚠️ درصد تغییر غیرعادی ({pct_val:.2f}) نادیده گرفته شد؛ جهت «نامشخص» می‌شود.")
        return "0", "0%", 0.0, "unknown"

    if pct_val == 0:
        return "0", "0%", 0.0, "flat"

    direction = detect_direction(change_cell)
    if direction is None:
        log(f"⚠️ جهت تغییر تشخیص داده نشد (متن سلول: {raw_text!r}) → نامشخص")
        return "0", "0%", 0.0, "unknown"

    signed_pct = -pct_val if direction == "down" else pct_val
    amt_str = f"-{format_number_with_comma(amt_val)}" if direction == "down" and amt_val != 0 else format_number_with_comma(amt_val)
    pct_str = f"{signed_pct:.2f}%"
    return amt_str, pct_str, signed_pct, direction


def parse_percent_cell(cell) -> tuple[str, float, str]:
    """
    برای سلولی که مستقیماً درصد است (صفحهٔ شاخص بورس).
    خروجی: (رشتهٔ درصد نرمال‌شده, درصد علامت‌دار, direction)
    """
    if cell is None:
        return "0%", 0.0, "unknown"
    text = to_english_digits(get_cell_text(cell)).replace("٫", ".")
    m = re.search(r'(\d+(?:\.\d+)?)', text)
    if not m:
        return "0%", 0.0, "unknown"
    pct = float(m.group(1))
    if pct > 100:
        return "0%", 0.0, "unknown"
    if pct == 0:
        return "0%", 0.0, "flat"
    direction = detect_direction(cell)
    if direction is None:
        log(f"⚠️ جهت درصد تغییر شاخص تشخیص داده نشد ({get_cell_text(cell)!r}) → نامشخص")
        return "0%", 0.0, "unknown"
    signed = -pct if direction == "down" else pct
    return f"{signed:.2f}%", signed, direction

# فقط تطبیق دقیق عنوان (بعد از نرمال‌سازی). تطبیق زیررشته‌ای عمداً حذف شده تا
# «دلار کانادا» یا «بیتکوین کش» جای نماد اصلی ننشیند.
EXACT_TITLES = {clean_title(fa): (fa, keys) for fa, keys in SYMBOL_MAP.items()}


def scrape_homepage_data():
    scraped_data = []
    near_misses = set()
    updated_at = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

    try:
        log("در حال استخراج زنده داده‌ها از tgju.org...")
        html = fetch_rendered_html(
            "https://www.tgju.org",
            wait_selector="#currency-overview-content table tr td",
            extra_wait=1.0,
        )

        if html:
            soup = BeautifulSoup(html, "html.parser")
            currency_container = soup.find(id="currency-overview-content")
            currency_table_ids = {id(t) for t in currency_container.find_all("table")} if currency_container else None
            if currency_table_ids is None:
                log("⚠️ کانتینر currency-overview-content پیدا نشد؛ محدودسازی جدول دلار غیرفعال است.")

            for table in soup.find_all("table"):
                header_tr = table.find("tr")
                header_cells = header_tr.find_all(["th", "td"]) if header_tr else []

                price_col_idx, change_col_idx = 1, 2
                for idx, c in enumerate(header_cells):
                    if idx == 0: continue
                    c_txt = get_cell_text(c)
                    if "ارزش" in c_txt or any(k in c_txt for k in ["قیمت", "قیمت زنده"]):
                        price_col_idx = idx
                    elif "تغییر" in c_txt:
                        change_col_idx = idx

                for row in table.find_all("tr"):
                    cols = row.find_all(["td", "th"])
                    if not cols or len(cols) < 2:
                        continue

                    row_title = clean_title(get_cell_text(cols[0]))
                    entry = EXACT_TITLES.get(row_title)
                    if not entry:
                        if row_title and len(row_title) < 60 and any(t in row_title for t in EXACT_TITLES):
                            near_misses.add(row_title)
                        continue

                    matched_fa, symbol_keys = entry
                    primary_key = symbol_keys[0]

                    # دلار فقط از جدول بازار ارز (در صورت وجود کانتینر)
                    if primary_key == "usd" and currency_table_ids is not None and id(table) not in currency_table_ids:
                        continue

                    price_cell = cols[price_col_idx] if len(cols) > price_col_idx else cols[1]
                    price_str, price_num = parse_price_value(get_cell_text(price_cell))

                    change_cell = cols[change_col_idx] if len(cols) > change_col_idx else None
                    change_amt, change_pct, change_num, direction = parse_changes(change_cell, price_num)

                    if primary_key in TOMAN_SYMBOLS and price_num:
                        price_num = price_num / 10
                        price_str = format_number_with_comma(price_num)

                    for skey in symbol_keys:
                        scraped_data.append({
                            "symbol_key": skey,
                            "title_fa": matched_fa,
                            "price": price_str,
                            "unit": get_unit(skey),
                            "price_num": price_num,
                            "change_percent": change_pct,
                            "change_num": change_num,
                            "direction": direction,
                            "updated_at": updated_at
                        })
    except Exception as e:
        log(f"❌ خطا در استخراج داده‌های اصلی: {e}")

    unique_data = {}
    for item in scraped_data:
        key = item["symbol_key"]
        if key not in unique_data or unique_data[key]["price"] == "-":
            unique_data[key] = item
        else:
            old, new = unique_data[key]["price_num"], item["price_num"]
            if old and new and abs(new - old) / old > 0.02:
                log(f"⚠️ چند ردیف متفاوت برای {key} پیدا شد ({old} در برابر {new})؛ اولی نگه داشته شد.")

    missing = [k for k in REQUIRED_SYMBOLS if k != "bourse_total" and k not in unique_data]
    if missing and near_misses:
        log(f"ℹ️ ردیف‌های مشابه که عمداً نادیده گرفته شدند: {sorted(near_misses)[:8]}")

    return unique_data


BOURSE_URL = "https://www.tgju.org/profile/gc30"
# اگر عنوان صفحه یکی از این‌ها را داشت، شاخص مورد نظر ما نیست
BOURSE_TITLE_REJECT = ("هم وزن", "فرابورس")


def fetch_bourse_total_index():
    updated_at = datetime.now(TEHRAN_TZ).strftime("%Y-%m-%d %H:%M:%S")

    try:
        log("در حال استخراج شاخص بورس از صفحه اختصاصی...")
        html = fetch_rendered_html(BOURSE_URL, wait_selector="table tr td", extra_wait=1.0)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        # اطمینان از اینکه صفحه واقعاً «شاخص کل» است
        page_title = clean_title(soup.title.get_text(" ", strip=True)) if soup.title else ""
        h1 = soup.find("h1")
        h1_text = clean_title(get_cell_text(h1)) if h1 else ""
        combined = f"{page_title} | {h1_text}"
        if "شاخص کل" not in combined or any(bad in combined for bad in BOURSE_TITLE_REJECT):
            log(f"⛔ صفحهٔ {BOURSE_URL} شاخص کل بورس نیست. عنوان: {combined!r}")
            return None

        raw_price = None
        pct_cell_daily = None      # «درصد تغییر نسبت به روز گذشته»
        pct_cell_plain = None      # دقیقاً «درصد تغییر»
        seen_labels = []

        for row in soup.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = clean_title(get_cell_text(cells[0]))
            val_cell = cells[1]
            val_text = get_cell_text(val_cell)
            seen_labels.append(label)

            # فقط «نرخ فعلی»؛ قیمت بازگشایی (کهنه) هرگز جایگزین نمی‌شود
            if "نرخ فعلی" in label:
                if raw_price is None and val_text:
                    raw_price = val_text
            elif "درصد تغییر نسبت به روز گذشته" in label:
                if pct_cell_daily is None:
                    pct_cell_daily = val_cell
            elif label == "درصد تغییر":
                if pct_cell_plain is None:
                    pct_cell_plain = val_cell

        if not raw_price:
            log(f"⛔ «نرخ فعلی» در صفحهٔ شاخص پیدا نشد. برچسب‌های دیده‌شده: {seen_labels[:15]}")
            return None

        price_str, price_num = parse_price_value(raw_price, is_index=True)
        if price_num <= 0:
            log(f"⛔ قیمت شاخص نامعتبر است: {raw_price!r}")
            return None

        pct_cell = pct_cell_daily if pct_cell_daily is not None else pct_cell_plain
        if pct_cell is None:
            log("⚠️ ردیف درصد تغییر روزانهٔ شاخص پیدا نشد → جهت نامشخص")
        change_pct_str, change_num, direction = parse_percent_cell(pct_cell)

        return {
            "symbol_key": "bourse_total",
            "title_fa": "شاخص کل",
            "price": price_str,
            "unit": get_unit("bourse_total"),
            "price_num": price_num,
            "change_percent": change_pct_str,
            "change_num": change_num,
            "direction": direction,
            "updated_at": updated_at
        }
    except Exception as e:
        log(f"❌ خطا در استخراج شاخص کل بورس: {e}")
        return None

def fetch_market_data():
    market_dict = scrape_homepage_data()
    bourse_item = fetch_bourse_total_index()
    if bourse_item:
        market_dict["bourse_total"] = bourse_item
    return market_dict

def get_asset_data(market, possible_keys):
    for key in possible_keys:
        clean_key = str(key).lower()
        if clean_key in market:
            return market[clean_key]
    return {}

def extract_price(item):
    if not item or not isinstance(item, dict):
        return None
    for field in ['price', 'p', 'current_price', 'val', 'value', 'last_price']:
        if field in item and item[field] is not None:
            return item[field]
    return None

def format_price(val):
    if val is None or val == "---" or val == "":
        return "---"
    return str(val)

def parse_change_info(item):
    if not item or not isinstance(item, dict):
        return {"pct": "0.0%", "status": "neutral", "emoji": "➖"}

    direction = item.get("direction", "unknown")
    if direction == "up":
        return {"pct": item.get("change_percent", "+0.0%"), "status": "bullish", "emoji": "🔺"}
    if direction == "down":
        return {"pct": item.get("change_percent", "-0.0%"), "status": "bearish", "emoji": "🔻"}
    if direction == "flat":
        return {"pct": "0.0%", "status": "neutral", "emoji": "➖"}
    # جهت نامشخص: نه سبز، نه قرمز
    return {"pct": "نامشخص", "status": "unknown", "emoji": "❔"}


# ---------------------------------------------------------------------------
# زمان بازار
# ---------------------------------------------------------------------------
def is_weekend_closed(now: datetime) -> bool:
    """پنجشنبه/جمعه یا تعطیلی دستی (MARKET_CLOSED=1). تعطیلات رسمی خودکار تشخیص داده نمی‌شوند."""
    return FORCE_MARKET_CLOSED or now.weekday() in (3, 4)


def is_bourse_session(now: datetime) -> bool:
    """جلسهٔ معاملاتی بورس: شنبه تا چهارشنبه، ۰۹:۰۰ تا ۱۲:۳۰."""
    if is_weekend_closed(now):
        return False
    return dtime(9, 0) <= now.time() <= dtime(12, 30)


def bourse_label(now: datetime) -> str:
    return "شاخص کل بورس" if is_bourse_session(now) else "شاخص کل بورس (پایانی)"


# ---------------------------------------------------------------------------
# اعتبارسنجی قبل از انتشار
# ---------------------------------------------------------------------------
def validate_market(market: dict) -> list[str]:
    problems = []
    unknown_dirs = 0
    for key in REQUIRED_SYMBOLS:
        item = market.get(key)
        if not item:
            problems.append(f"{key}: استخراج نشد")
            continue
        price_num = item.get("price_num")
        if item.get("price") in (None, "", "-") or not isinstance(price_num, (int, float)) or price_num <= 0:
            problems.append(f"{key}: قیمت نامعتبر ({item.get('price')!r})")
            continue
        if item.get("direction") == "unknown":
            unknown_dirs += 1
    if unknown_dirs > 3:
        problems.append(f"جهت تغییر {unknown_dirs} نماد نامشخص است (احتمال تغییر ساختار سایت)")
    return problems


def load_last_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        log(f"⚠️ خواندن {STATE_FILE} ناموفق بود (چک معقول‌بودن رد می‌شود): {e}")
        return {}


def save_last_state(market: dict, now: datetime) -> None:
    data = {k: market[k]["price_num"] for k in REQUIRED_SYMBOLS}
    data["_saved_at"] = now.isoformat()
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        log(f"⚠️ ذخیرهٔ {STATE_FILE} ناموفق بود: {e}")


def check_sanity(market: dict) -> list[str]:
    """مقایسه با آخرین پست منتشرشده؛ جهش بیش از MAX_MOVE_RATIO مشکوک است (مثلاً خطای /10)."""
    last = load_last_state()
    problems = []
    for key in REQUIRED_SYMBOLS:
        prev = last.get(key)
        cur = market[key]["price_num"]
        if isinstance(prev, (int, float)) and prev > 0:
            ratio = abs(cur - prev) / prev
            if ratio > MAX_MOVE_RATIO:
                problems.append(f"{key}: {prev:,.2f} → {cur:,.2f} ({ratio * 100:.1f}٪ تغییر نسبت به پست قبلی)")
    return problems

def generate_graphic_html(market, now):
    shamsi_date = jdatetime.date.fromgregorian(date=now.date()).strftime("%Y/%m/%d")
    time_str = now.strftime("%H:%M")
    closed_suffix = " · 🕒 آخرین معامله" if is_weekend_closed(now) else ""
    bourse_name = bourse_label(now)

    usd = get_asset_data(market, ['usd'])
    gold = get_asset_data(market, ['gold_18k'])
    coin = get_asset_data(market, ['coin_emami'])
    btc = get_asset_data(market, ['btc'])
    ons = get_asset_data(market, ['gold_ounce'])
    bourse = get_asset_data(market, ['bourse_total'])

    usd_info = parse_change_info(usd)
    gold_info = parse_change_info(gold)
    coin_info = parse_change_info(coin)
    btc_info = parse_change_info(btc)
    ons_info = parse_change_info(ons)
    bourse_info = parse_change_info(bourse)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <style>
            @import url('https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css');
            
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Vazirmatn', sans-serif;
            }}
            body {{
                width: 1200px;
                height: 750px;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                color: #f8fafc;
                padding: 30px 35px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                overflow: hidden;
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 2px solid #334155;
                padding-bottom: 14px;
            }}
            .brand {{
                display: flex;
                align-items: center;
                gap: 12px;
            }}
            .live-dot {{
                width: 14px;
                height: 14px;
                background-color: #22c55e;
                border-radius: 50%;
                box-shadow: 0 0 12px #22c55e;
            }}
            .title {{
                font-size: 28px;
                font-weight: 800;
                color: #f1f5f9;
            }}
            .date-time {{
                font-size: 20px;
                color: #94a3b8;
                font-weight: 500;
                background: #0f172a;
                padding: 6px 18px;
                border-radius: 12px;
                border: 1px solid #334155;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 18px;
                margin-top: 10px;
            }}
            .card {{
                background: rgba(30, 41, 59, 0.7);
                border-radius: 20px;
                padding: 20px;
                border: 1px solid #334155;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                position: relative;
            }}
            .card.hero {{
                grid-column: span 3;
                background: linear-gradient(90deg, rgba(30,41,59,0.9) 0%, rgba(15,23,42,0.9) 100%);
                padding: 22px 35px;
                flex-direction: row;
                align-items: center;
            }}
            .card.bullish {{
                border-color: #22c55e;
                box-shadow: inset 0 0 15px rgba(34, 197, 94, 0.15), 0 4px 20px rgba(34, 197, 94, 0.1);
            }}
            .card.bearish {{
                border-color: #ef4444;
                box-shadow: inset 0 0 15px rgba(239, 68, 68, 0.15), 0 4px 20px rgba(239, 68, 68, 0.1);
            }}
            .asset-name {{
                font-size: 20px;
                color: #94a3b8;
                font-weight: 600;
            }}
            .hero .asset-name {{ font-size: 24px; color: #cbd5e1; }}

            .price-val {{
                font-size: 32px;
                font-weight: 900;
                color: #ffffff;
                margin: 8px 0;
            }}
            .hero .price-val {{ font-size: 42px; margin: 0; }}

            .unit-text {{
                font-size: 18px;
                color: #94a3b8;
                font-weight: 500;
            }}

            .badge {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 5px 14px;
                border-radius: 30px;
                font-size: 16px;
                font-weight: 700;
                width: fit-content;
            }}
            .badge.bullish {{ background: rgba(34, 197, 94, 0.2); color: #4ade80; }}
            .badge.bearish {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
            .badge.neutral {{ background: rgba(148, 163, 184, 0.2); color: #cbd5e1; }}
            .badge.unknown {{ background: rgba(250, 204, 21, 0.15); color: #facc15; }}

            .market-icon {{
                font-size: 32px;
                position: absolute;
                left: 20px;
                top: 20px;
            }}
            .hero .market-icon {{ position: static; font-size: 42px; }}

            .footer {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: #0f172a;
                padding: 14px 24px;
                border-radius: 14px;
                border: 1px solid #334155;
                font-size: 16px;
                color: #94a3b8;
                margin-top: 10px;
            }}
            .bot-id {{ color: #38bdf8; font-weight: 700; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="brand">
                <div class="live-dot"></div>
                <div class="title">نرخ امروز چند؟</div>
            </div>
            <div class="date-time">🗓 {shamsi_date} - ⏰ {time_str}{closed_suffix}</div>
        </div>

        <div class="grid">
            <!-- دلار -->
            <div class="card hero {usd_info['status']}">
                <div>
                    <div class="asset-name">💵 دلار بازار آزاد</div>
                    <div class="price-val">{format_price(extract_price(usd))} <span class="unit-text">تومان</span></div>
                </div>
                <div style="display:flex; align-items:center; gap:20px;">
                    <div class="badge {usd_info['status']}">
                        <span>{usd_info['pct']}</span>
                        <span>{usd_info['emoji']}</span>
                    </div>
                    <div class="market-icon">{usd_info['emoji']}</div>
                </div>
            </div>

            <!-- سکه امامی -->
            <div class="card {coin_info['status']}">
                <div class="market-icon">{coin_info['emoji']}</div>
                <div class="asset-name">🪙 سکه امامی</div>
                <div class="price-val">{format_price(extract_price(coin))} <span class="unit-text">تومان</span></div>
                <div class="badge {coin_info['status']}">
                    <span>{coin_info['pct']}</span>
                    <span>{coin_info['emoji']}</span>
                </div>
            </div>

            <!-- طلای ۱۸ عیار -->
            <div class="card {gold_info['status']}">
                <div class="market-icon">{gold_info['emoji']}</div>
                <div class="asset-name">🥇 طلای ۱۸ عیار</div>
                <div class="price-val">{format_price(extract_price(gold))} <span class="unit-text">تومان</span></div>
                <div class="badge {gold_info['status']}">
                    <span>{gold_info['pct']}</span>
                    <span>{gold_info['emoji']}</span>
                </div>
            </div>

            <!-- بیت کوین -->
            <div class="card {btc_info['status']}">
                <div class="market-icon">{btc_info['emoji']}</div>
                <div class="asset-name">🌐 بیت کوین</div>
                <div class="price-val">${format_price(extract_price(btc))} <span class="unit-text">دلار</span></div>
                <div class="badge {btc_info['status']}">
                    <span>{btc_info['pct']}</span>
                    <span>{btc_info['emoji']}</span>
                </div>
            </div>

            <!-- اونس طلا -->
            <div class="card {ons_info['status']}">
                <div class="market-icon">{ons_info['emoji']}</div>
                <div class="asset-name">🌍 اونس جهانی طلا</div>
                <div class="price-val">${format_price(extract_price(ons))} <span class="unit-text">دلار</span></div>
                <div class="badge {ons_info['status']}">
                    <span>{ons_info['pct']}</span>
                    <span>{ons_info['emoji']}</span>
                </div>
            </div>

            <!-- شاخص بورس -->
            <div class="card {bourse_info['status']}">
                <div class="market-icon">{bourse_info['emoji']}</div>
                <div class="asset-name">📊 {bourse_name}</div>
                <div class="price-val">{format_price(extract_price(bourse))} <span class="unit-text">واحد</span></div>
                <div class="badge {bourse_info['status']}">
                    <span>{bourse_info['pct']}</span>
                    <span>{bourse_info['emoji']}</span>
                </div>
            </div>
        </div>

        <div class="footer">
            <span> استعلام لحظه‌ای ارز و طلا و بورس در ربات تلگرام و بله</span>
            <span class="bot-id">@nerkhemroozchand_bot 🤖</span>
        </div>
    </body>
    </html>
    """
    return html_content

def render_graphic_image(html_content, output_path='market_graphic.png'):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 750})
        page.set_content(html_content)
        time.sleep(1.5)
        page.screenshot(path=output_path)
        browser.close()

def build_caption(market, now):
    shamsi_date = jdatetime.date.fromgregorian(date=now.date()).strftime("%Y/%m/%d")
    time_str = now.strftime("%H:%M")

    def line(key, label, unit):
        item = get_asset_data(market, [key])
        info = parse_change_info(item)
        return f"{info['emoji']} {label}: {format_price(extract_price(item))} {unit}"

    lines = [
        line('usd', "دلار", "تومان"),
        line('gold_18k', "طلای 18 عیار", "تومان"),
        line('coin_emami', "سکه امامی", "تومان"),
        line('gold_ounce', "اونس جهانی طلا", "دلار"),
        line('btc', "بیت کوین", "دلار"),
        line('oil_brent', "نفت برنت", "دلار"),
        line('bourse_total', bourse_label(now), "واحد"),
        "",
        f"🗓 {shamsi_date} - {time_str}",
    ]
    if is_weekend_closed(now):
        lines.append("🕒 بازار تعطیل است؛ نرخ‌ها مربوط به آخرین معامله است")
    lines += [
        "",
        "⭕️ استعلام نرخ لحظه‌ای طلا، دلار، رمزارز و بورس"
    ]
    return "\n".join(lines)


def send_photo_to_telegram(photo_path, caption):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        raise FatalError("توکن یا آیدی کانال تلگرام ست نشده است.")

    keyboard = json.dumps({
        "inline_keyboard": [
            [
                {"text": "🎯 تو پیش‌بینی کن!", "url": "https://t.me/pishbini_gheymat_bot"},
                {"text": "🔎 نرخ لحظه‌ای بگیر!", "url": "https://t.me/nerkhemroozchand_bot"}
            ]
        ]
    }, ensure_ascii=False)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    payload = {
        'chat_id': TELEGRAM_CHANNEL_ID,
        'caption': caption,
        'reply_markup': keyboard
    }

    log("در حال ارسال عکس به تلگرام...")
    try:
        with open(photo_path, 'rb') as photo:
            res = requests.post(url, data=payload, files={'photo': photo}, timeout=25)
    except requests.RequestException as e:
        # پیام استثنای requests شامل URL (و توکن) است؛ قبل از چاپ ماسک می‌شود
        raise FatalError(f"ارتباط با تلگرام ناموفق بود: {mask_secrets(e)}") from None

    if not res.ok:
        # به‌جای raise_for_status (که URL را در پیام دارد) بدنهٔ پاسخ تلگرام را نشان می‌دهیم
        raise FatalError(f"تلگرام خطا برگرداند (HTTP {res.status_code}): {mask_secrets(res.text)[:500]}")
    log("✅ با موفقیت به تلگرام ارسال شد.")


def run():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        raise FatalError("توکن یا آیدی کانال تلگرام ست نشده است.")

    # زمان فقط یک‌بار گرفته می‌شود و به تصویر و کپشن پاس داده می‌شود
    now = datetime.now(TEHRAN_TZ)

    log("۱. دریافت زنده داده‌ها از سایت اصلی...")
    market_data = fetch_market_data()

    problems = validate_market(market_data)
    if problems:
        raise FatalError("داده‌ها برای انتشار کامل/معتبر نیستند:\n  - " + "\n  - ".join(problems))

    sanity_problems = check_sanity(market_data)
    if sanity_problems:
        msg = "تغییر مشکوک نسبت به پست قبلی:\n  - " + "\n  - ".join(sanity_problems)
        if FORCE_POST:
            log("⚠️ " + msg + "\n  (FORCE_POST=1 → ادامه می‌دهیم)")
        else:
            raise FatalError(msg + "\n  اگر تغییر واقعی است با FORCE_POST=1 دوباره اجرا کنید.")

    log("۲. رندر تصویر گرافیکی...")
    html_code = generate_graphic_html(market_data, now)
    image_path = 'market_graphic.png'
    render_graphic_image(html_code, image_path)

    log("۳. ساخت کپشن و ارسال به پیام‌رسان‌ها...")
    caption = build_caption(market_data, now)
    send_photo_to_telegram(image_path, caption)

    # فقط بعد از ارسال موفق، مبنای چک معقول‌بودن پست بعدی به‌روز می‌شود
    save_last_state(market_data, now)


def main():
    try:
        run()
    except FatalError as e:
        log(f"⛔ {e}")
        sys.exit(1)
    except Exception as e:
        log(f"❌ خطای پیش‌بینی‌نشده: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
