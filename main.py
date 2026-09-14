import os
import re
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pytz
import jdatetime

try:
    import libsql_experimental as libsql
    HAS_LIBSQL = True
except ImportError:
    HAS_LIBSQL = False

# نگاشت نام‌های فارسی به symbol_key موجود در دیتابیس اصلی
SYMBOL_MAP = {
    # طلا و سکه
    "سکه امامی": "coin_emami",
    "سکه بهار آزادی": "coin_azadi",
    "نیم سکه": "coin_half",
    "ربع سکه": "coin_quarter",
    "سکه گرمی": "coin_gram",
    "طلای ۱۸ عیار": "gold_18k",
    "طلای ۲۴ عیار": "gold_24k",
    "طلای دست دوم": "gold_used",
    "مثقال طلا": "gold_mesghal",
    "انس طلا": "gold_ounce",
    "گرم نقره ۹۹۹": "silver_gram",
    "آبشده نقدی": "abshedeh_cash",
    "آبشده معاملاتی": "abshedeh_trade",
    
    # ارزها
    "دلار": "usd",
    "یورو": "eur",
    "درهم امارات": "aed",
    "پوند انگلیس": "gbp",
    "لیر ترکیه": "try",
    "فرانک سوئیس": "chf",
    "یوان چین": "cny",
    "ین ژاپن": "jpy",
    "وون کره جنوبی": "krw",
    "دلار کانادا": "cad",
    "دلار استرالیا": "aud",
    "افغانی": "afn",
    "درام ارمنستان": "amd",
    "منات آذربایجان": "azn",
    "دینار بحرین": "bhd",
    "کرون دانمارک": "dkk",
    "لاری گرجستان": "gel",
    "دلار هنگ‌کنگ": "hkd",
    "روپیه هند": "inr",
    "دینار عراق": "iqd",
    "سوم قرقیزستان": "kgs",
    "دینار کویت": "kwd",
    "رینگیت مالزی": "myr",
    "کرون نروژ": "nok",
    "دلار نیوزیلند": "nzd",
    "ریال عمان": "omr",
    "روپیه پاکستان": "pkr",
    "ریال قطر": "qar",
    "روبل روسیه": "rub",
    "ریال عربستان": "sar",
    "کرون سوئد": "sek",
    "دلار سنگاپور": "sgd",
    "لیر سوریه": "syp",
    "بات تایلند": "thb",
    "سامانی تاجیکستان": "tjs",
    "منات ترکمنستان": "tmt",

    # کریپتو
    "بیت‌کوین": "btc",
    "بیت کوین": "btc",
    "اتریوم": "eth",
    "تتر": "usdt",
    "ترون": "trx",
    "کاردانو": "ada",
    "سولانا": "sol",
    "دوج کوین": "doge",
    "شیبا اینو": "shib",
    "تون‌کوین": "ton",
    "ریپل": "xrp",
    "لایت‌کوین": "ltc",
    "بیت‌کوین کش": "bch",
    "پولکادات": "dot",
    "آوالانچ": "avax",
    "استلار": "xlm",
    "دش": "dash",
    "بایننس کوین": "bnb",

    # صندوق‌های طلا
    "صندوق طلای عیار": "fund_ayar",
    "صندوق طلای لوتوس": "fund_lotus",
    "صندوق طلای گوهر": "fund_gohar",
    "صندوق طلای مثقال": "fund_mesghal",
    "صندوق طلای کهربا": "fund_kahreba",
    "صندوق طلای ناب": "fund_nab",
    "صندوق طلای ریتون": "fund_riton",
    "صندوق طلای تابش": "fund_tabesh",
    "صندوق طلای زروان": "fund_zarvan",

    # نفت
    "نفت برنت": "oil_brent",
    "نفت سبک": "oil_crude",
    "نفت اوپک": "oil_opec"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def to_english_digits(text: str) -> str:
    if not text:
        return ""
    text = text.replace('−', '-').replace('–', '-').replace(',', '').replace('،', '')
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"
    translation = str.maketrans(persian_digits + arabic_digits, english_digits * 2)
    return text.translate(translation)

def get_tehran_timestamp():
    tehran_tz = pytz.timezone('Asia/Tehran')
    now_tehran = datetime.now(tehran_tz)
    return now_tehran.strftime("%Y-%m-%d %H:%M:%S")

def parse_price(cell_tag) -> str:
    if cell_tag is None:
        return "-"
    text = cell_tag if isinstance(cell_tag, str) else cell_tag.get_text(strip=True)
    clean_text = to_english_digits(text)
    match = re.search(r'(\d+(?:\.\d+)?)', clean_text)
    if match:
        val = int(float(match.group(1))) if float(match.group(1)).is_integer() else float(match.group(1))
        return f"{val:,}"
    return "-"

def parse_percentage(cell_tag) -> str:
    if cell_tag is None:
        return "0%"
    
    is_negative = False
    text = cell_tag if isinstance(cell_tag, str) else cell_tag.get_text(strip=True)

    if not isinstance(cell_tag, str):
        classes = list(cell_tag.get("class", []))
        for child in cell_tag.find_all(True):
            classes.extend(child.get("class", []))
        if cell_tag.parent:
            classes.extend(cell_tag.parent.get("class", []))

        class_str = " ".join([str(c) for c in classes]).lower()
        style_str = str(cell_tag.get("style", "")).lower()
        negative_keywords = ["low", "drop", "red", "danger", "down", "minus", "decrease"]
        if any(kw in class_str for kw in negative_keywords) or "color: red" in style_str or "color:#f" in style_str:
            is_negative = True

    if "-" in text or "−" in text or "🔻" in text:
        is_negative = True

    clean_text = to_english_digits(text)
    pct_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', clean_text) or re.findall(r'%\s*(\d+(?:\.\d+)?)', clean_text)
    val = float(pct_matches[0]) if pct_matches else 0.0

    prefix = "-" if is_negative and val > 0 else ""
    return f"{prefix}{val}%"

def scrape_homepage_data():
    print("در حال استخراج داده‌ها از tgju.org ...", flush=True)
    scraped_data = []
    sorted_targets = sorted(SYMBOL_MAP.keys(), key=len, reverse=True)
    
    try:
        res = requests.get("https://www.tgju.org", headers=HEADERS, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            for table in soup.find_all("table"):
                price_col_idx, change_col_idx = -1, -1
                header_tr = table.find("tr")
                if header_tr:
                    cols = header_tr.find_all(["th", "td"])
                    for idx, col in enumerate(cols):
                        col_txt = col.get_text()
                        if "قیمت" in col_txt or "نرخ" in col_txt or "زنده" in col_txt:
                            price_col_idx = idx
                        elif "تغییر" in col_txt:
                            change_col_idx = idx

                for row in table.find_all("tr"):
                    cols = row.find_all(["td", "th"])
                    if not cols or len(cols) < 2:
                        continue
                    
                    row_title = cols[0].get_text(strip=True)
                    if "حباب" in row_title:
                        continue
                    
                    matched_fa_title = next((t for t in sorted_targets if t in row_title or t in row.get_text()), None)
                    if matched_fa_title:
                        symbol_key = SYMBOL_MAP[matched_fa_title]
                        price_str = parse_price(cols[price_col_idx]) if price_col_idx != -1 and len(cols) > price_col_idx else parse_price(cols[1])
                        
                        change_str = "0%"
                        if change_col_idx != -1 and len(cols) > change_col_idx:
                            change_str = parse_percentage(cols[change_col_idx])
                        else:
                            for cell in cols[2:]:
                                if "%" in cell.get_text() or "(" in cell.get_text():
                                    change_str = parse_percentage(cell)
                                    break
                        
                        scraped_data.append({
                            "symbol_key": symbol_key,
                            "title_fa": matched_fa_title,
                            "price": price_str,
                            "change_percent": change_str,
                            "updated_at": get_tehran_timestamp()
                        })
    except Exception as e:
        print(f"خطا در استخراج: {e}", flush=True)

    unique_data = {item["symbol_key"]: item for item in scraped_data}
    return list(unique_data.values())

def get_db_connection():
    turso_url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    turso_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    
    if turso_url and turso_token and HAS_LIBSQL:
        # استفاده از پروتکل HTTPS برای نوشتن مستقیم در دیتابیس ابری Turso
        if turso_url.startswith("libsql://"):
            turso_url = turso_url.replace("libsql://", "https://")
        elif not turso_url.startswith("https://"):
            turso_url = f"https://{turso_url}"
            
        print(f"اتصال مستقیم به دیتابیس ابری Turso ({turso_url}) ...", flush=True)
        return libsql.connect(database=turso_url, auth_token=turso_token)
    else:
        print("اتصال به SQLite محلی ...", flush=True)
        return sqlite3.connect("market_database.db")

def update_database(data_list):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # اطمینان از وجود جدول اصلی market_prices
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_prices (
            symbol_key TEXT PRIMARY KEY,
            title_fa TEXT,
            price TEXT,
            change_amount TEXT DEFAULT '0',
            change_percent TEXT,
            updated_at TEXT
        )
    """)
    
    for item in data_list:
        cursor.execute("""
            INSERT INTO market_prices (symbol_key, title_fa, price, change_percent, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(symbol_key) DO UPDATE SET
                price = excluded.price,
                change_percent = excluded.change_percent,
                updated_at = excluded.updated_at
        """, (
            item["symbol_key"],
            item["title_fa"],
            item["price"],
            item["change_percent"],
            item["updated_at"]
        ))
    
    conn.commit()
    conn.close()
    print(f"تعداد {len(data_list)} کلید در جدول market_prices بروزرسانی شد.", flush=True)

if __name__ == "__main__":
    print("--- شروع اسکریپت بروزرسانی market_prices ---", flush=True)
    data = scrape_homepage_data()
    if data:
        update_database(data)
    else:
        print("داده‌ای دریافت نشد.", flush=True)
    print("--- پایان ---", flush=True)
