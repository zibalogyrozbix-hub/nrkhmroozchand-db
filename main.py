import os
import re
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pytz
import jdatetime

# بررسی و بارگذاری کتابخانه Turso
try:
    import libsql_experimental as libsql
    HAS_LIBSQL = True
except ImportError:
    HAS_LIBSQL = False

DAILY_TARGET_ASSETS = [
    "بیت‌کوین", "بیت کوین", "اتریوم", "لایت‌کوین", "بیت‌کوین کش", "تتر", "ترون", "بایننس کوین", 
    "استلار", "ریپل", "دوج کوین", "دش", "کاردانو", "پولکادات", "سولانا", "آوالانچ", "شیبا اینو", 
    "تون‌کوین", "نفت سبک", "نفت برنت", "نفت اوپک", "بنزین (RBOB)", "گاز طبیعی", "زغال سنگ", 
    "آلومینیوم", "نیکل", "سرب", "روی", "مس", "قلع", "پنبه", "شکر", "سویا", "گندم", "ذرت", "برنج", 
    "دلار", "یورو", "درهم امارات", "پوند انگلیس", "لیر ترکیه", "فرانک سوئیس", "یوان چین", 
    "ین ژاپن", "وون کره جنوبی", "دلار کانادا", "دلار استرالیا", "سکه امامی", "سکه بهار آزادی", 
    "نیم سکه", "ربع سکه", "سکه گرمی", "انس طلا", "انس نقره", "انس پلاتین", "انس پالادیوم", 
    "طلای ۱۸ عیار", "طلای ۲۴ عیار", "طلای دست دوم", "گرم نقره ۹۹۹", "مثقال طلا", "آبشده نقدی", 
    "آبشده معاملاتی", "صندوق طلای عیار", "صندوق طلای لوتوس", "صندوق طلای مثقال", "صندوق طلای گوهر"
]

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

def get_tehran_jalali_datetime():
    tehran_tz = pytz.timezone('Asia/Tehran')
    now_tehran = datetime.now(tehran_tz)
    jalali_datetime = jdatetime.datetime.fromgregorian(datetime=now_tehran)
    return jalali_datetime.strftime("%Y/%m/%d"), jalali_datetime.strftime("%H:%M:%S")

def parse_price(cell_tag) -> float:
    if cell_tag is None:
        return 0.0
    text = cell_tag if isinstance(cell_tag, str) else cell_tag.get_text(strip=True)
    clean_text = to_english_digits(text)
    match = re.search(r'(\d+(?:\.\d+)?)', clean_text)
    return float(match.group(1)) if match else 0.0

def parse_percentage(cell_tag) -> float:
    if cell_tag is None:
        return 0.0
    
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
    if not val:
        num_match = re.search(r'[-+]?(\d+(?:\.\d+)?)', clean_text)
        val = float(num_match.group(1)) if num_match else 0.0

    return -val if is_negative and val < 500 else (val if val < 500 else 0.0)

def scrape_homepage_data():
    print("در حال استخراج داده‌ها از صفحه اصلی www.tgju.org ...", flush=True)
    scraped_data = []
    sorted_targets = sorted(DAILY_TARGET_ASSETS, key=len, reverse=True)
    
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
                    if "حباب" in row_title or "حباب" in row.get_text():
                        continue
                    
                    matched_asset = next((t for t in sorted_targets if t in row_title or t in row.get_text()), None)
                    if matched_asset:
                        price_val = parse_price(cols[price_col_idx]) if price_col_idx != -1 and len(cols) > price_col_idx else parse_price(cols[1])
                        
                        change_pct = 0.0
                        if change_col_idx != -1 and len(cols) > change_col_idx:
                            change_pct = parse_percentage(cols[change_col_idx])
                        else:
                            for cell in cols[2:]:
                                if "%" in cell.get_text() or "(" in cell.get_text():
                                    change_pct = parse_percentage(cell)
                                    break
                        
                        jalali_date, tehran_time = get_tehran_jalali_datetime()
                        scraped_data.append({
                            "asset_name": matched_asset,
                            "price": price_val,
                            "change_percent": change_pct,
                            "jalali_date": jalali_date,
                            "tehran_time": tehran_time
                        })
    except Exception as e:
        print(f"خطا در دریافت اطلاعات: {e}", flush=True)

    unique_data = {item["asset_name"]: item for item in scraped_data}
    return list(unique_data.values())

def get_db_connection():
    """اتصال به دیتابیس ابری Turso در صورت وجود Secrets، یا دیتابیس محلی"""
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN")
    
    if turso_url and turso_token and HAS_LIBSQL:
        print("در حال اتصال به دیتابیس ابری Turso ...", flush=True)
        if not (turso_url.startswith("libsql://") or turso_url.startswith("https://")):
            turso_url = f"libsql://{turso_url}"
        return libsql.connect(database=turso_url, auth_token=turso_token)
    else:
        print("کلیدهای Turso یافت نشد؛ در حال اتصال به SQLite محلی ...", flush=True)
        return sqlite3.connect("market_database.db")

def update_database(data_list):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_data (
            asset_name TEXT PRIMARY KEY,
            price REAL,
            change_percent REAL,
            jalali_date TEXT,
            tehran_time TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    for item in data_list:
        cursor.execute("""
            INSERT INTO market_data (asset_name, price, change_percent, jalali_date, tehran_time, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(asset_name) DO UPDATE SET
                price = excluded.price,
                change_percent = excluded.change_percent,
                jalali_date = excluded.jalali_date,
                tehran_time = excluded.tehran_time,
                updated_at = CURRENT_TIMESTAMP
        """, (
            item["asset_name"],
            item["price"],
            item["change_percent"],
            item["jalali_date"],
            item["tehran_time"]
        ))
    
    conn.commit()
    conn.close()
    print(f"تعداد {len(data_list)} شاخص با موفقیت در دیتابیس Turso بروزرسانی شد.", flush=True)

if __name__ == "__main__":
    print("--- شروع اجرای فرایند استخراج و به‌روزرسانی دیتابیس ---", flush=True)
    market_data = scrape_homepage_data()
    if market_data:
        update_database(market_data)
    else:
        print("هیچ داده‌ای دریافت نشد.", flush=True)
    print("--- پایان فرایند ---", flush=True)
