import os
import re
import sqlite3
from datetime import datetime
import pandas as pd
import requests
from bs4 import BeautifulSoup

# ==========================================
# ۱. تنظیمات و تعریف لیست دقیق ۱۲۶ شاخص
# ==========================================

TARGET_ITEMS = [
    # ۱. طلا، سکه، حباب و صندوق‌ها (۳۱ مورد)
    {"key": "gold_18k", "title": "طلای ۱۸ عیار", "slugs": ["geram18", "gold_18k"], "type": "gold"},
    {"key": "gold_24k", "title": "طلای ۲۴ عیار", "slugs": ["geram24", "gold_24k"], "type": "gold"},
    {"key": "gold_used", "title": "طلای دست دوم", "slugs": ["gold_mini_size", "gold_used"], "type": "gold"},
    {"key": "silver_gram", "title": "گرم نقره ۹۹۹", "slugs": ["silver_999", "silver_gram"], "type": "gold"},
    {"key": "gold_mesghal", "title": "مثقال طلا", "slugs": ["mesghal", "gold_mesghal"], "type": "gold"},
    {"key": "abshedeh_cash", "title": "آبشده نقدی", "slugs": ["abshedeh_cash"], "type": "gold"},
    {"key": "abshedeh_trade", "title": "آبشده معاملاتی", "slugs": ["abshedeh_trade"], "type": "gold"},
    {"key": "mesghal_no_bubble", "title": "مثقال بدون حباب", "slugs": ["mesghal_no_bubble"], "type": "gold"},
    {"key": "coin_emami", "title": "سکه امامی", "slugs": ["sekee", "coin_emami"], "type": "coin"},
    {"key": "coin_azadi", "title": "سکه بهار آزادی", "slugs": ["bahar", "coin_azadi"], "type": "coin"},
    {"key": "coin_half", "title": "نیم‌سکه", "slugs": ["nim", "coin_half"], "type": "coin"},
    {"key": "coin_quarter", "title": "ربع‌سکه", "slugs": ["rob", "coin_quarter"], "type": "coin"},
    {"key": "coin_gram", "title": "سکه گرمی", "slugs": ["gerami", "coin_gram"], "type": "coin"},
    {"key": "gold_ounce", "title": "انس طلا", "slugs": ["ons", "gold_ounce"], "type": "gold"},
    {"key": "silver_ounce", "title": "انس نقره", "slugs": ["silver-ons", "silver_ounce"], "type": "gold"},
    {"key": "platinum_ounce", "title": "انس پلاتین", "slugs": ["platinum-ons", "platinum_ounce"], "type": "gold"},
    {"key": "palladium_ounce", "title": "انس پالادیوم", "slugs": ["palladium-ons", "palladium_ounce"], "type": "gold"},
    {"key": "bubble_emami", "title": "حباب سکه امامی", "slugs": ["bubble_emami"], "type": "bubble"},
    {"key": "bubble_azadi", "title": "حباب سکه بهار آزادی", "slugs": ["bubble_azadi"], "type": "bubble"},
    {"key": "bubble_half", "title": "حباب نیم‌سکه", "slugs": ["bubble_half"], "type": "bubble"},
    {"key": "bubble_quarter", "title": "حباب ربع‌سکه", "slugs": ["bubble_quarter"], "type": "bubble"},
    {"key": "bubble_gram", "title": "حباب سکه گرمی", "slugs": ["bubble_gram"], "type": "bubble"},
    {"key": "etf_kahroba", "title": "صندوق طلای کهربا", "slugs": ["etf_kahroba", "kahroba"], "type": "etf"},
    {"key": "etf_zarvan", "title": "صندوق طلای زروان", "slugs": ["etf_zarvan", "zarvan"], "type": "etf"},
    {"key": "etf_reyton", "title": "صندوق طلای ریتون", "slugs": ["etf_reyton", "reyton"], "type": "etf"},
    {"key": "etf_nab", "title": "صندوق طلای ناب", "slugs": ["etf_nab", "nab"], "type": "etf"},
    {"key": "etf_tabesh", "title": "صندوق طلای تابش", "slugs": ["etf_tabesh", "tabesh"], "type": "etf"},
    {"key": "etf_ayar", "title": "صندوق طلای عیار", "slugs": ["etf_ayar", "ayar"], "type": "etf"},
    {"key": "etf_lotus", "title": "صندوق طلای لوتوس", "slugs": ["etf_lotus", "lotus"], "type": "etf"},
    {"key": "etf_mesghal", "title": "صندوق طلای مثقال", "slugs": ["etf_mesghal"], "type": "etf"},
    {"key": "etf_gohar", "title": "صندوق طلای گوهر", "slugs": ["etf_gohar", "gohar"], "type": "etf"},

    # ۲. ارزها (۳۶ مورد)
    {"key": "usd", "title": "دلار", "slugs": ["price_dollar_rl", "usd"], "type": "currency"},
    {"key": "eur", "title": "یورو", "slugs": ["price_eur", "eur"], "type": "currency"},
    {"key": "aed", "title": "درهم امارات", "slugs": ["price_aed", "aed"], "type": "currency"},
    {"key": "gbp", "title": "پوند انگلیس", "slugs": ["price_gbp", "gbp"], "type": "currency"},
    {"key": "try", "title": "لیر ترکیه", "slugs": ["price_try", "try"], "type": "currency"},
    {"key": "chf", "title": "فرانک سوئیس", "slugs": ["price_chf", "chf"], "type": "currency"},
    {"key": "cny", "title": "یوان چین", "slugs": ["price_cny", "cny"], "type": "currency"},
    {"key": "jpy", "title": "ین ژاپن", "slugs": ["price_jpy", "jpy"], "type": "currency"},
    {"key": "krw", "title": "وون کره جنوبی", "slugs": ["price_krw", "krw"], "type": "currency"},
    {"key": "cad", "title": "دلار کانادا", "slugs": ["price_cad", "cad"], "type": "currency"},
    {"key": "aud", "title": "دلار استرالیا", "slugs": ["price_aud", "aud"], "type": "currency"},
    {"key": "dkk", "title": "کرون دانمارک", "slugs": ["price_dkk", "dkk"], "type": "currency"},
    {"key": "sek", "title": "کرون سوئد", "slugs": ["price_sek", "sek"], "type": "currency"},
    {"key": "nok", "title": "کرون نروژ", "slugs": ["price_nok", "nok"], "type": "currency"},
    {"key": "sar", "title": "ریال عربستان", "slugs": ["price_sar", "sar"], "type": "currency"},
    {"key": "qar", "title": "ریال قطر", "slugs": ["price_qar", "qar"], "type": "currency"},
    {"key": "omr", "title": "ریال عمان", "slugs": ["price_omr", "omr"], "type": "currency"},
    {"key": "kwd", "title": "دینار کویت", "slugs": ["price_kwd", "kwd"], "type": "currency"},
    {"key": "bhd", "title": "دینار بحرین", "slugs": ["price_bhd", "bhd"], "type": "currency"},
    {"key": "myr", "title": "رینگیت مالزی", "slugs": ["price_myr", "myr"], "type": "currency"},
    {"key": "thb", "title": "بات تایلند", "slugs": ["price_thb", "thb"], "type": "currency"},
    {"key": "hkd", "title": "دلار هنگ‌کنگ", "slugs": ["price_hkd", "hkd"], "type": "currency"},
    {"key": "rub", "title": "روبل روسیه", "slugs": ["price_rub", "rub"], "type": "currency"},
    {"key": "azn", "title": "منات آذربایجان", "slugs": ["price_azn", "azn"], "type": "currency"},
    {"key": "amd", "title": "درام ارمنستان", "slugs": ["price_amd", "amd"], "type": "currency"},
    {"key": "gel", "title": "لاری گرجستان", "slugs": ["price_gel", "gel"], "type": "currency"},
    {"key": "kgs", "title": "سوم قرقیزستان", "slugs": ["price_kgs", "kgs"], "type": "currency"},
    {"key": "tjs", "title": "سامانی تاجیکستان", "slugs": ["price_tjs", "tjs"], "type": "currency"},
    {"key": "tmt", "title": "منات ترکمنستان", "slugs": ["price_tmt", "tmt"], "type": "currency"},
    {"key": "nzd", "title": "دلار نیوزیلند", "slugs": ["price_nzd", "nzd"], "type": "currency"},
    {"key": "sgd", "title": "دلار سنگاپور", "slugs": ["price_sgd", "sgd"], "type": "currency"},
    {"key": "inr", "title": "روپیه هند", "slugs": ["price_inr", "inr"], "type": "currency"},
    {"key": "pkr", "title": "روپیه پاکستان", "slugs": ["price_pkr", "pkr"], "type": "currency"},
    {"key": "iqd", "title": "دینار عراق", "slugs": ["price_iqd", "iqd"], "type": "currency"},
    {"key": "syp", "title": "لیر سوریه", "slugs": ["price_syp", "syp"], "type": "currency"},
    {"key": "afn", "title": "افغانی", "slugs": ["price_afn", "afn"], "type": "currency"},

    # ۳. شاخص‌های بورس ایران (۱۲ مورد)
    {"key": "bourse_total", "title": "شاخص کل", "slugs": ["bourse_total", "index_bourse"], "type": "bourse_iran"},
    {"key": "bourse_equal", "title": "شاخص کل هم‌وزن", "slugs": ["bourse_equal"], "type": "bourse_iran"},
    {"key": "fara_total", "title": "شاخص فرابورس", "slugs": ["fara_total"], "type": "bourse_iran"},
    {"key": "fara_m1", "title": "بازار اول فرابورس", "slugs": ["fara_m1"], "type": "bourse_iran"},
    {"key": "fara_m2", "title": "بازار دوم فرابورس", "slugs": ["fara_m2"], "type": "bourse_iran"},
    {"key": "bourse_m1", "title": "شاخص بازار اول", "slugs": ["bourse_market1"], "type": "bourse_iran"},
    {"key": "bourse_m2", "title": "شاخص بازار دوم", "slugs": ["bourse_market2"], "type": "bourse_iran"},
    {"key": "bourse_30", "title": "شاخص ۳۰ شرکت بزرگ", "slugs": ["bourse_30"], "type": "bourse_iran"},
    {"key": "bourse_50", "title": "شاخص ۵۰ شرکت فعال‌تر", "slugs": ["bourse_50"], "type": "bourse_iran"},
    {"key": "bourse_p50", "title": "شاخص قیمت ۵۰ شرکت", "slugs": ["bourse_p50"], "type": "bourse_iran"},
    {"key": "bourse_pequal", "title": "شاخص قیمت هم‌وزن", "slugs": ["bourse_pequal"], "type": "bourse_iran"},
    {"key": "bourse_pweighted", "title": "شاخص قیمت وزنی ارزشی", "slugs": ["bourse_pweighted"], "type": "bourse_iran"},

    # ۴. شاخص‌های بورس جهانی (۱۲ مورد)
    {"key": "dow_jones", "title": "داوجونز", "slugs": ["dow_jones"], "type": "bourse_global"},
    {"key": "sp500", "title": "اس‌اندپی ۵۰۰", "slugs": ["sp500", "sp_500"], "type": "bourse_global"},
    {"key": "nasdaq", "title": "نزدک", "slugs": ["nasdaq"], "type": "bourse_global"},
    {"key": "smi_swiss", "title": "اس‌ام‌آی سوئیس", "slugs": ["smi"], "type": "bourse_global"},
    {"key": "nifty50", "title": "نیفتی ۵۰", "slugs": ["nifty50"], "type": "bourse_global"},
    {"key": "ftse100", "title": "فتسی بریتانیا", "slugs": ["ftse100"], "type": "bourse_global"},
    {"key": "dax", "title": "دکس آلمان", "slugs": ["dax"], "type": "bourse_global"},
    {"key": "cac_40", "title": "کک فرانسه", "slugs": ["cac_40"], "type": "bourse_global"},
    {"key": "nikkei225", "title": "نیکی ژاپن", "slugs": ["nikkei225"], "type": "bourse_global"},
    {"key": "shanghai", "title": "شانگهای چین", "slugs": ["shanghai"], "type": "bourse_global"},
    {"key": "ibex35", "title": "آیبکس اسپانیا", "slugs": ["ibex35"], "type": "bourse_global"},
    {"key": "tsx_canada", "title": "اس‌اندپی کانادا", "slugs": ["tsx"], "type": "bourse_global"},

    # ۵. ارزهای دیجیتال (۱۷ مورد)
    {"key": "btc", "title": "بیت‌کوین", "slugs": ["crypto-bitcoin", "btc"], "type": "crypto"},
    {"key": "eth", "title": "اتریوم", "slugs": ["crypto-ethereum", "eth"], "type": "crypto"},
    {"key": "ltc", "title": "لایت‌کوین", "slugs": ["crypto-litecoin", "ltc"], "type": "crypto"},
    {"key": "bch", "title": "بیت‌کوین کش", "slugs": ["crypto-bitcoin-cash", "bch"], "type": "crypto"},
    {"key": "usdt", "title": "تتر", "slugs": ["crypto-tether", "usdt"], "type": "crypto"},
    {"key": "trx", "title": "ترون", "slugs": ["crypto-tron", "trx"], "type": "crypto"},
    {"key": "bnb", "title": "بایننس کوین", "slugs": ["crypto-binancecoin", "bnb"], "type": "crypto"},
    {"key": "xlm", "title": "استلار", "slugs": ["crypto-stellar", "xlm"], "type": "crypto"},
    {"key": "xrp", "title": "ریپل", "slugs": ["crypto-ripple", "xrp"], "type": "crypto"},
    {"key": "doge", "title": "دوج کوین", "slugs": ["crypto-dogecoin", "doge"], "type": "crypto"},
    {"key": "dash", "title": "دش", "slugs": ["crypto-dash", "dash"], "type": "crypto"},
    {"key": "ada", "title": "کاردانو", "slugs": ["crypto-cardano", "ada"], "type": "crypto"},
    {"key": "dot", "title": "پولکادات", "slugs": ["crypto-polkadot", "dot"], "type": "crypto"},
    {"key": "sol", "title": "سولانا", "slugs": ["crypto-solana", "sol"], "type": "crypto"},
    {"key": "avax", "title": "آوالانچ", "slugs": ["crypto-avalanche", "avax"], "type": "crypto"},
    {"key": "shib", "title": "شیبا اینو", "slugs": ["crypto-shiba-inu", "shib"], "type": "crypto"},
    {"key": "ton", "title": "تون‌کوین", "slugs": ["crypto-toncoin", "ton"], "type": "crypto"},

    # ۶. انرژی (۶ مورد)
    {"key": "oil_crude", "title": "نفت سبک", "slugs": ["oil_crude"], "type": "commodity"},
    {"key": "oil_brent", "title": "نفت برنت", "slugs": ["oil_brent"], "type": "commodity"},
    {"key": "oil_opec", "title": "نفت اوپک", "slugs": ["oil_opec"], "type": "commodity"},
    {"key": "gasoline", "title": "بنزین (RBOB)", "slugs": ["gasoline"], "type": "commodity"},
    {"key": "natural_gas", "title": "گاز طبیعی", "slugs": ["natural_gas"], "type": "commodity"},
    {"key": "coal", "title": "زغال‌سنگ", "slugs": ["coal"], "type": "commodity"},

    # ۷. فلزات پایه (۶ مورد)
    {"key": "aluminum", "title": "آلومینیوم", "slugs": ["aluminum"], "type": "commodity"},
    {"key": "nickel", "title": "نیکل", "slugs": ["nickel"], "type": "commodity"},
    {"key": "lead", "title": "سرب", "slugs": ["lead"], "type": "commodity"},
    {"key": "zinc", "title": "روی", "slugs": ["zinc"], "type": "commodity"},
    {"key": "copper", "title": "مس", "slugs": ["copper"], "type": "commodity"},
    {"key": "tin", "title": "قلع", "slugs": ["tin"], "type": "commodity"},

    # ۸. کشاورزی (۶ مورد)
    {"key": "cotton", "title": "پنبه", "slugs": ["cotton"], "type": "commodity"},
    {"key": "sugar", "title": "شکر", "slugs": ["sugar"], "type": "commodity"},
    {"key": "soybeans", "title": "سویا", "slugs": ["soybeans"], "type": "commodity"},
    {"key": "wheat", "title": "گندم", "slugs": ["wheat"], "type": "commodity"},
    {"key": "corn", "title": "ذرت", "slugs": ["corn"], "type": "commodity"},
    {"key": "rice", "title": "برنج", "slugs": ["rice"], "type": "commodity"},
]


# ==========================================
# ۲. توابع پردازش عدد و متن
# ==========================================

def convert_persian_to_english_digits(text: str) -> str:
    if not text:
        return ""
    p_digits = "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩"
    e_digits = "01234567890123456789"
    trans = str.maketrans(p_digits, e_digits)
    return str(text).translate(trans)


def parse_numeric_value(text: str) -> float:
    if not text:
        return 0.0

    text_en = convert_persian_to_english_digits(str(text)).strip()
    multiplier = 1.0

    if "میلیارد" in text_en:
        multiplier = 1_000_000_000.0
        text_en = text_en.replace("میلیارد", "")
    elif "میلیون" in text_en:
        multiplier = 1_000_000.0
        text_en = text_en.replace("میلیون", "")
    elif "هزار" in text_en:
        multiplier = 1_000.0
        text_en = text_en.replace("هزار", "")

    cleaned = re.sub(r"[^0-9.-]", "", text_en)
    try:
        val = float(cleaned)
        return val * multiplier
    except ValueError:
        return 0.0


def format_final_price(val: float, item_type: str) -> str:
    if val == 0.0:
        return "-"

    if item_type == "commodity":
        if val == int(val):
            return f"{int(val):,} دلار"
        return f"{val:,.2f} دلار"

    if val == int(val):
        return f"{int(val):,}"
    return f"{val:,.2f}"


# ==========================================
# ۳. کلاس اسکریپر اصلی
# ==========================================

class TGJUScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
        })
        self.raw_extracted_data = {}

    def fetch_all_pages(self):
        # آدرس‌های استاندارد و واقعی سایت TGJU جهت جلوگیری از خطای 404
        urls = [
            "https://www.tgju.org/",
            "https://www.tgju.org/gold-chart",
            "https://www.tgju.org/currency",
            "https://www.tgju.org/crypto",
            "https://www.tgju.org/bourse",
            "https://www.tgju.org/energy",
            "https://www.tgju.org/metal",
            "https://www.tgju.org/commodity",
        ]

        for url in urls:
            try:
                res = self.session.get(url, timeout=15)
                if res.status_code == 200:
                    self.parse_page_rows(res.text)
                else:
                    print(f"⚠️ وضعیت پاسخ غیرعادی برای {url}: کد {res.status_code}")
            except Exception as e:
                print(f"⚠️ خطا در دریافت صفحه {url}: {e}")

    def parse_page_rows(self, html_content):
        soup = BeautifulSoup(html_content, "html.parser")

        for row in soup.find_all("tr"):
            key = row.get("data-market-row") or row.get("data-key") or row.get("id")

            if not key:
                link = row.find("a", href=True)
                if link:
                    href = link["href"].strip("/")
                    key = href.split("/")[-1]

            if not key:
                continue

            key = key.lower().replace("-", "_")

            tds = row.find_all(["td", "th"])
            if not tds or len(tds) < 2:
                continue

            price_text = ""
            for td in tds:
                if "nf" in td.get("class", []) or td.find("span", class_="info-value"):
                    price_text = td.get_text(strip=True)
                    break

            if not price_text and len(tds) >= 2:
                price_text = tds[1].get_text(strip=True)

            change_amount_text = ""
            change_percent_text = ""
            is_negative = False

            for td in tds[2:]:
                txt = td.get_text(strip=True)
                classes = " ".join(td.get("class", []))

                if "low" in classes or "drop" in classes or "red" in classes or "-" in txt:
                    is_negative = True

                if "%" in txt:
                    change_percent_text = txt
                elif txt and re.search(r"\d", txt):
                    change_amount_text = txt

            self.raw_extracted_data[key] = {
                "raw_price": price_text,
                "change_amount_text": change_amount_text,
                "change_percent_text": change_percent_text,
                "is_negative": is_negative,
            }

    def process_and_structure_data(self):
        final_rows = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for item in TARGET_ITEMS:
            key = item["key"]
            title = item["title"]
            item_type = item["type"]
            slugs = item["slugs"]

            extracted_info = None
            for s in slugs:
                s_clean = s.lower().replace("-", "_")
                if s_clean in self.raw_extracted_data:
                    extracted_info = self.raw_extracted_data[s_clean]
                    break

            if not extracted_info:
                final_rows.append({
                    "symbol_key": key,
                    "title_fa": title,
                    "price": "-",
                    "change_amount": "0",
                    "change_percent": "0%",
                    "updated_at": now_str,
                })
                continue

            num_price = parse_numeric_value(extracted_info["raw_price"])
            formatted_price = format_final_price(num_price, item_type)

            raw_amount = convert_persian_to_english_digits(extracted_info.get("change_amount_text", ""))
            raw_percent = convert_persian_to_english_digits(extracted_info.get("change_percent_text", ""))
            is_neg = extracted_info["is_negative"]

            num_change_amount = parse_numeric_value(raw_amount)

            percent_match = re.search(r"([0-9.]+)", raw_percent)
            change_percent_val = percent_match.group(1) if percent_match else ""

            if is_neg:
                if num_change_amount > 0:
                    num_change_amount = -num_change_amount
                if change_percent_val and not change_percent_val.startswith("-"):
                    change_percent_val = f"-{change_percent_val}"
            else:
                num_change_amount = abs(num_change_amount)

            if num_change_amount == int(num_change_amount):
                formatted_change_amount = f"{int(num_change_amount):,}"
            else:
                formatted_change_amount = f"{num_change_amount:,.2f}"

            if change_percent_val:
                formatted_change_percent = f"{change_percent_val}%"
            else:
                formatted_change_percent = "0%"

            final_rows.append({
                "symbol_key": key,
                "title_fa": title,
                "price": formatted_price,
                "change_amount": formatted_change_amount,
                "change_percent": formatted_change_percent,
                "updated_at": now_str,
            })

        df = pd.DataFrame(final_rows)
        cols = ["symbol_key", "title_fa", "price", "change_amount", "change_percent", "updated_at"]
        return df[cols]


# ==========================================
# ۴. تابع ذخیره در Excel، SQLite و Turso
# ==========================================

def save_all_outputs(df: pd.DataFrame):
    # ۱. اکسل
    excel_file = "market_prices.xlsx"
    df.to_excel(excel_file, index=False, sheet_name="market_prices")
    print(f"📊 فایل اکسل ذخیره شد: {excel_file}")

    # ۲. دیتابیس لوکال SQLite
    db_file = "market_prices.db"
    with sqlite3.connect(db_file) as conn_local:
        df.to_sql("market_prices", conn_local, if_exists="replace", index=False)
    print(f"🗄️ دیتابیس لوکال SQLite بروزرسانی شد: {db_file}")

    # ۳. دیتابیس ابری Turso
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN")

    if turso_url and turso_token:
        print("🌐 در حال ارسال و بروزرسانی داده‌ها در دیتابیس ابری Turso...")
        try:
            try:
                import libsql
            except ImportError:
                import libsql_experimental as libsql

            conn_turso = libsql.connect(database=turso_url, auth_token=turso_token)
            cursor = conn_turso.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_prices (
                    symbol_key TEXT PRIMARY KEY,
                    title_fa TEXT,
                    price TEXT,
                    change_amount TEXT,
                    change_percent TEXT,
                    updated_at TEXT
                );
            """)

            for _, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO market_prices (symbol_key, title_fa, price, change_amount, change_percent, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol_key) DO UPDATE SET
                        title_fa = excluded.title_fa,
                        price = excluded.price,
                        change_amount = excluded.change_amount,
                        change_percent = excluded.change_percent,
                        updated_at = excluded.updated_at;
                """, (
                    str(row["symbol_key"]),
                    str(row["title_fa"]),
                    str(row["price"]),
                    str(row["change_amount"]),
                    str(row["change_percent"]),
                    str(row["updated_at"])
                ))

            conn_turso.commit()
            conn_turso.close()
            print("🚀 دیتابیس Turso با موفقیت در اینترنت بروزرسانی شد!")
        except Exception as e:
            print(f"❌ خطا در ارسال داده به Turso: {e}")
    else:
        print("ℹ️ کلیدهای Secrets برای Turso یافت نشدند (اجرای لوکال).")


if __name__ == "__main__":
    print("🚀 شروع فرآیند استخراج ۱۲۶ شاخص بازارهای مالی...")

    scraper = TGJUScraper()
    scraper.fetch_all_pages()
    df_result = scraper.process_and_structure_data()

    print(f"✅ تعداد کل شاخص‌های پردازش‌شده: {len(df_result)} از ۱۲۶")

    save_all_outputs(df_result)
