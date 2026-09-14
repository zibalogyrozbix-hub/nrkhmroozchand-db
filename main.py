import os
import re
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pytz
import jdatetime

# لیست تمام دارایی‌ها و شاخص‌های مورد نظر جهت رصد در صفحه اصلی
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

DB_NAME = "market_database.db"

def to_english_digits(text: str) -> str:
    """تبدیل ارقام فارسی و عربی به انگلیسی و استانداردسازی علامت‌های منفی"""
    if not text:
        return ""
    text = text.replace('−', '-').replace('–', '-').replace(',', '').replace('،', '')
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"
    translation = str.maketrans(persian_digits + arabic_digits, english_digits * 2)
    return text.translate(translation)

def get_tehran_jalali_datetime():
    """دریافت تاریخ شمسی و ساعت دقیق به وقت تهران"""
    tehran_tz = pytz.timezone('Asia/Tehran')
    now_tehran = datetime.now(tehran_tz)
    jalali_datetime = jdatetime.datetime.fromgregorian(datetime=now_tehran)
    
    jalali_date = jalali_datetime.strftime("%Y/%m/%d")
    tehran_time = jalali_datetime.strftime("%H:%M:%S")
    
    return jalali_date, tehran_time

def parse_price(cell_tag) -> float:
    """استخراج قیمت/نرخ عددی پاکسازی‌شده"""
    if cell_tag is None:
        return 0.0
    text = cell_tag if isinstance(cell_tag, str) else cell_tag.get_text(strip=True)
    clean_text = to_english_digits(text)
    
    match = re.search(r'(\d+(?:\.\d+)?)', clean_text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0

def parse_percentage(cell_tag) -> float:
    """استخراج درصد تغییرات با تشخیص رنگ قرمز (منفی) و سبز (مثبت)"""
    if cell_tag is None:
        return 0.0
    
    is_negative = False
    text = ""

    if isinstance(cell_tag, str):
        text = cell_tag
    else:
        text = cell_tag.get_text(strip=True)
        classes = []
        if cell_tag.get("class"):
            classes.extend(cell_tag.get("class"))
        for child in cell_tag.find_all(True):
            if child.get("class"):
                classes.extend(child.get("class"))
        if cell_tag.parent and cell_tag.parent.get("class"):
            classes.extend(cell_tag.parent.get("class"))

        class_str = " ".join([str(c) for c in classes]).lower()
        style_str = str(cell_tag.get("style", "")).lower()
        
        # شناسه کلاس‌ها و استایل‌های مربوط به افت قیمت (قرمز)
        negative_keywords = ["low", "drop", "red", "danger", "down", "minus", "decrease"]
        if any(kw in class_str for kw in negative_keywords) or "color: red" in style_str or "color:#f" in style_str or "color: #f" in style_str:
            is_negative = True

    if "-" in text or "−" in text or "🔻" in text:
        is_negative = True

    clean_text = to_english_digits(text)
    
    pct_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', clean_text)
    if not pct_matches:
        pct_matches = re.findall(r'%\s*(\d+(?:\.\d+)?)', clean_text)
    
    val = 0.0
    if pct_matches:
        val = float(pct_matches[0])
    else:
        num_match = re.search(r'[-+]?(\d+(?:\.\d+)?)', clean_text)
        if num_match:
            val = float(num_match.group(1))

    if val < 500:
        return -val if is_negative else val
    return 0.0

def scrape_homepage_data():
    """استخراج کامل شاخص‌ها مستقیماً و فقط از صفحه اصلی tgju.org"""
    print("در حال استخراج داده‌ها از صفحه اصلی www.tgju.org ...", flush=True)
    scraped_data = []
    sorted_targets = sorted(DAILY_TARGET_ASSETS, key=len, reverse=True)
    
    try:
        res = requests.get("https://www.tgju.org", headers=HEADERS, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            for table in soup.find_all("table"):
                price_col_idx = -1
                change_col_idx = -1
                
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
                    row_full_text = row.get_text()
                    
                    if "حباب" in row_title or "حباب" in row_full_text:
                        continue
                    
                    matched_asset = None
                    for target in sorted_targets:
                        if target in row_title or target in row_full_text:
                            matched_asset = target
                            break
                    
                    if matched_asset:
                        price_val = 0.0
                        change_pct = 0.0
                        
                        # استخراج قیمت
                        if price_col_idx != -1 and len(cols) > price_col_idx:
                            price_val = parse_price(cols[price_col_idx])
                        elif len(cols) >= 2:
                            price_val = parse_price(cols[1])
                            
                        # استخراج درصد تغییرات
                        if change_col_idx != -1 and len(cols) > change_col_idx:
                            change_pct = parse_percentage(cols[change_col_idx])
                        else:
                            for cell in cols[2:]:
                                cell_txt = cell.get_text()
                                if "%" in cell_txt or "(" in cell_txt:
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
        print(f"خطا در دریافت اطلاعات صفحه اصلی: {e}", flush=True)

    # حذف موارد تکراری و نگه‌داشتن اولین استخراج صحیح
    unique_data = {}
    for item in scraped_data:
        if item["asset_name"] not in unique_data:
            unique_data[item["asset_name"]] = item

    return list(unique_data.values())

def update_database(data_list):
    """ایجاد جدول و بازنویسی/به‌روزرسانی مقادیر جدید در دیتابیس SQLite"""
    print(f"در حال بازنویسی دیتابیس {DB_NAME} ...", flush=True)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # ساخت جدول در صورت عدم وجود
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
    
    # بازنویسی و جایگزینی داده‌های جدید (UPSERT)
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
    print(f"تعداد {len(data_list)} شاخص با موفقیت در دیتابیس بروزرسانی شد.", flush=True)

if __name__ == "__main__":
    print("--- شروع اجرای فرایند استخراج و به‌روزرسانی دیتابیس ---", flush=True)
    
    market_data = scrape_homepage_data()
    
    if market_data:
        update_database(market_data)
    else:
        print("هیچ داده‌ای دریافت نشد.", flush=True)
        
    print("--- پایان فرایند ---", flush=True)
