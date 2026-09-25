import os
import re
import json
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
    "بنزین (RBOB)": ["gasoline"],
    "گاز طبیعی": ["natural_gas"],
    "زغال سنگ": ["coal"],

    # شاخص‌های بورس و جهانی
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

COMMODITIES = {"cotton", "sugar", "soybeans", "wheat", "corn", "rice", "aluminum", "nickel", "lead", "zinc", "copper", "tin", "oil_crude", "oil_brent", "oil_opec", "gasoline", "natural_gas", "coal"}
INDICES = {"bourse_total", "ifb_market1", "ifb_market2", "bourse_market1", "bourse_market2", "bourse_pequal", "bourse_pweighted", "dow_jones", "nasdaq", "smi_swiss", "nifty_50", "ftse_100", "dax", "cac_40", "nikkei_225", "shanghai_composite", "ibex_35"}
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
    "bourse_total", "ifb_market1", "ifb_market2", "bourse_market1", "bourse_market2",
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

SANITY_DIGIT_DIFF_THRESHOLD = 3
SANITY_PERCENT_WARN_THRESHOLD = 50.0

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

def fetch_rendered_html(url: str, extra_wait: float = 3.0) -> str | None:
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
    if not text:
        return ""
    text = text.replace('\u200c', ' ').replace('\u200f', '')
    text = text.replace('ي', 'ی').replace('ك', 'ک')
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

def scrape_homepage_data():
    print("در حال دریافت داده‌ها از tgju.org ...", flush=True)
    scraped_data = []
    sorted_targets = sorted(SYMBOL_MAP.keys(), key=len, reverse=True)
    tehran_tz = pytz.timezone('Asia/Tehran')
    updated_at = datetime.now(tehran_tz).strftime("%Y-%m-%d %H:%M:%S")

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

                seen_header_texts.append(" ".join(get_cell_text(c) for c in header_cells))

                if not is_real_data_table(table, header_cells):
                    continue

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

                        # تبدیل قیمت از ریال به تومان برای نمادهای مشخص‌شده
                        if primary_key in TOMAN_SYMBOLS and price_num:
                            price_num = price_num / 10
                            price_str = format_number_with_comma(price_num)

                        display_title = matched_fa
                        if primary_key in COMMODITIES and "(دلار)" not in display_title:
                            display_title = f"{display_title} (دلار)"

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
                                "updated_at": updated_at
                            })
    except Exception as e:
        print(f"خطا در استخراج: {e}", flush=True)

    unique_data = {}
    for item in scraped_data:
        key = item["symbol_key"]
        if key not in unique_data or unique_data[key]["price"] == "-":
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


def fetch_bourse_total_index():
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
                    if i + 1 < len(cells):
                        return get_cell_text(cells[i + 1])
                    elif i - 1 >= 0:
                        return get_cell_text(cells[i - 1])
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
            print("هشدار: مقدار «نرخ فعلی» برای شاخص کل (gc30) پیدا نشد.", flush=True)
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
            "unit": get_unit("bourse_total"),
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


def write_data_json(accepted):
    """ساخت/به‌روزرسانی snapshot استاتیک data.json از داده‌های پذیرفته‌شده"""
    json_path = "data.json"
    temp_path = f"{json_path}.tmp"
    try:
        sorted_json_data = sorted(accepted, key=lambda x: x.get("title_fa", ""))
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
    conn = None

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

        for row in cursor.execute(
            "SELECT symbol_key, title_fa, price, unit, change_amount, change_percent, updated_at FROM market_prices"
        ).fetchall():
            existing_rows[row[0]] = {
                "symbol_key": row[0],
                "title_fa": row[1],
                "price": row[2],
                "unit": row[3],
                "change_amount": row[4],
                "change_percent": row[5],
                "updated_at": row[6],
            }
    except Exception as e:
        print(f"⚠️ هشدار: عدم امکان برقراری ارتباط با دیتابیس جهت خواندن مقادیر قبلی ({e}) — پردازش ادامه می‌یابد.", flush=True)

    accepted = []
    rejected_anomalies = []

    for item in data_list:
        old = existing_rows.get(item["symbol_key"])
        old_val = _to_float(old["price"]) if old else None
        new_val = _to_float(item["price"])

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

        accepted.append(item)

    complete_snapshot = dict(existing_rows)
    for item in accepted:
        complete_snapshot[item["symbol_key"]] = item
    write_data_json(list(complete_snapshot.values()))

    if conn:
        try:
            for item in accepted:
                cursor.execute("""
                    INSERT INTO market_prices (symbol_key, title_fa, price, unit, change_amount, change_percent, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol_key) DO UPDATE SET
                        title_fa = excluded.title_fa,
                        price = excluded.price,
                        unit = excluded.unit,
                        change_amount = excluded.change_amount,
                        change_percent = excluded.change_percent,
                        updated_at = excluded.updated_at
                """, (
                    item["symbol_key"],
                    item["title_fa"],
                    item["price"],
                    item["unit"],
                    item["change_amount"],
                    item["change_percent"],
                    item["updated_at"]
                ))

            conn.commit()
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

    if rejected_anomalies:
        print(f"\n🚫 {len(rejected_anomalies)} مورد به دلیل جهش رقمی مشکوک رد شدند.", flush=True)

    expected_roster = {sk for keys in SYMBOL_MAP.values() for sk in keys} | {"bourse_total"}
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

if __name__ == "__main__":
    try:
        data = scrape_homepage_data()

        bourse_total_item = fetch_bourse_total_index()
        if bourse_total_item:
            data.append(bourse_total_item)

        if data:
            update_database(data)
        else:
            print("⚠️ هیچ داده‌ای در این اجرا استخراج نشد.", flush=True)
    except Exception as e:
        print(f"❌ خطای غیرمنتظره در اجرای اسکریپت: {e}", flush=True)
