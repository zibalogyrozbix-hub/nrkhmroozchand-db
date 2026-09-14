import os
import re
import datetime
import requests
from bs4 import BeautifulSoup
import libsql_experimental as libsql

# کلیدهای دیتابیس و نگاشت نام‌های فارسی به symbol_key
ASSET_MAP = {
    # ارزهای دیجیتال
    "بیت‌کوین": "btc", "اتریوم": "eth", "لایت‌کوین": "ltc", "بیت‌کوین کش": "bch",
    "تتر": "usdt", "ترون": "trx", "بایننس کوین": "bnb", "استلار": "xlm",
    "ریپل": "xrp", "دوج کوین": "doge", "دش": "dash", "کاردانو": "ada",
    "پولکادات": "dot", "سولانا": "sol", "آوالانچ": "avax", "شیبا اینو": "shib", "تون‌کوین": "ton",

    # نفت، انرژی و کالاهای اساسی
    "نفت سبک": "oil_crude", "نفت برنت": "oil_brent", "نفت اوپک": "oil_opec",
    "بنزین (RBOB)": "gasoline", "گاز طبیعی": "natural_gas", "زغال سنگ": "coal",
    "آلومینیوم": "aluminum", "نیکل": "nickel", "سرب": "lead", "روی": "zinc",
    "مس": "copper", "قلع": "tin", "پنبه": "cotton", "شکر": "sugar",
    "سویا": "soybeans", "گندم": "wheat", "ذرت": "corn", "برنج": "rice",

    # ارزها
    "دلار": "usd", "یورو": "eur", "درهم امارات": "aed", "پوند انگلیس": "gbp",
    "لیر ترکیه": "try", "فرانک سوئیس": "chf", "یوان چین": "cny", "ین ژاپن": "jpy",
    "وون کره جنوبی": "krw", "دلار کانادا": "cad", "دلار استرالیا": "aud", "کرون دانمارک": "dkk",
    "کرون سوئد": "sek", "کرون نروژ": "nok", "ریال عربستان": "sar", "ریال قطر": "qar",
    "ریال عمان": "omr", "دینار کویت": "kwd", "دینار بحرین": "bhd", "رینگیت مالزی": "myr",
    "بات تایلند": "thb", "دلار هنگ کنگ": "hkd", "روبل روسیه": "rub", "منات آذربایجان": "azn",
    "درام ارمنستان": "amd", "لاری گرجستان": "gel", "سوم قرقیزستان": "kgs", "سامانی تاجیکستان": "tjs",
    "منات ترکمنستان": "tmt", "دلار نیوزیلند": "nzd", "دلار سنگاپور": "sgd", "روپیه هند": "inr",
    "روپیه پاکستان": "pkr", "دینار عراق": "iqd", "لیر سوریه": "syp", "افغانی": "afn",

    # بورس و شاخص‌های جهانی
    "شاخص کل": "bourse_total", "شاخص کل هم وزن": "bourse_equal_weight", "شاخص فرابورس": "ifb_total",
    "بازار اول فرابورس": "ifb_market1", "بازار دوم فرابورس": "ifb_market2", "شاخص بازار اول": "bourse_market1",
    "شاخص بازار دوم": "bourse_market2", "شاخص 30 شرکت بزرگ": "top_30_companies", "شاخص 50 شرکت فعالتر": "active_50_companies",
    "شاخص قیمت 50 شرکت": "price_50_companies", "شاخص قیمت هم وزن": "price_equal_weight", "شاخص قیمت وزنی ارزشی": "price_weighted",
    "داوجونز": "dow_jones", "اس اند پی 500": "sp_500", "نزدک": "nasdaq", "اس ام آی سوئیس": "smi_swiss",
    "نیفتی 50": "nifty_50", "فتسی بریتانیا": "ftse_100", "دکس آلمان": "dax", "کک فرانسه": "cac_40",
    "نیکی ژاپن": "nikkei_225", "شانگهای چین": "shanghai_composite", "آیبکس اسپانیا": "ibex_35", "اس اند پی کانادا": "sp_tsx",

    # طلا، سکه و صندوق‌های طلا
    "سکه امامی": "coin_emami", "سکه بهار آزادی": "coin_azadi", "نیم سکه": "coin_half",
    "ربع سکه": "coin_quarter", "سکه گرمی": "coin_gram", "حباب سکه امامی": "bubble_emami",
    "حباب سکه بهار آزادی": "bubble_azadi", "حباب نیم سکه": "bubble_half", "حباب ربع سکه": "bubble_quarter",
    "حباب سکه گرمی": "bubble_gram", "صندوق طلای کهربا": "fund_kahreba", "صندوق طلای زروان": "fund_zarvan",
    "صندوق طلای ریتون": "fund_riton", "صندوق طلای ناب": "fund_nab", "صندوق طلای تابش": "fund_tabesh",
    "صندوق طلای عیار": "fund_ayar", "صندوق طلای لوتوس": "fund_lotus", "صندوق طلای مثقال": "fund_mesghal",
    "صندوق طلای گوهر": "fund_gohar", "انس طلا": "gold_ounce", "انس نقره": "silver_ounce",
    "انس پلاتین": "platinum_ounce", "انس پالادیوم": "palladium_ounce", "طلای 18 عیار": "gold_18k",
    "طلای 24 عیار": "gold_24k", "طلای دست دوم": "gold_used", "گرم نقره 999": "silver_gram_999",
    "مثقال طلا": "gold_mesghal", "آبشده نقدی": "abshedeh_cash", "آبشده معاملاتی": "abshedeh_trade", "مثقال بدون حباب": "mesghal_nobubble"
}

def fetch_tgju_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = "https://www.tgju.org/"
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    extracted_data = {}

    # جستجو در تمامی سطرها و جدول‌های صفحه اصلی TGJU
    for row in soup.find_all('tr'):
        text = row.get_text(separator=' ', strip=True)
        for title_fa, symbol_key in ASSET_MAP.items():
            if title_fa in text and symbol_key not in extracted_data:
                cols = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                if len(cols) >= 2:
                    price = cols[1] if len(cols) > 1 else ""
                    change_amount = cols[2] if len(cols) > 2 else ""
                    change_percent = cols[3] if len(cols) > 3 else ""
                    
                    extracted_data[symbol_key] = {
                        "title_fa": title_fa,
                        "price": price,
                        "change_amount": change_amount,
                        "change_percent": change_percent
                    }

    return extracted_data

def update_turso_db(data):
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN")

    if not turso_url or not turso_token:
        raise ValueError("دسترسی به متغیرهای TURSO_DATABASE_URL یا TURSO_AUTH_TOKEN یافت نشد.")

    conn = libsql.connect(turso_url, auth_token=turso_token)
    cursor = conn.cursor()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for symbol_key, item in data.items():
        cursor.execute("""
            INSERT OR REPLACE INTO market_prices (symbol_key, title_fa, price, change_amount, change_percent, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            symbol_key,
            item["title_fa"],
            item["price"],
            item["change_amount"],
            item["change_percent"],
            now_str
        ))

    conn.commit()
    conn.close()
    print(f"تعداد {len(data)} دارایی با موفقیت در دیتابیس Turso بروزرسانی شدند.")

if __name__ == "__main__":
    market_data = fetch_tgju_data()
    if market_data:
        update_turso_db(market_data)
    else:
        print("هیچ داده‌ای یافت نشد.")
