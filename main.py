import os
import re
import sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pytz

try:
    import libsql_experimental as libsql
    HAS_LIBSQL = True
except ImportError:
    HAS_LIBSQL = False

# نگاشت جامع کلیدها به نام‌های فارسی در سایت TGJU
SYMBOL_MAP = {
    # طلا، سکه و حباب‌ها
    "سکه امامی": ["coin_emami"],
    "حباب سکه امامی": ["bubble_emami"],
    "سکه بهار آزادی": ["coin_azadi"],
    "حباب سکه بهار آزادی": ["bubble_azadi"],
    "نیم سکه": ["coin_half"],
    "حباب نیم‌سکه": ["bubble_half"],
    "ربع سکه": ["coin_quarter"],
    "حباب ربع‌سکه": ["bubble_quarter"],
    "سکه گرمی": ["coin_gram"],
    "حباب سکه گرمی": ["bubble_gram"],
    "طلای ۱۸ عیار": ["gold_18k"],
    "طلای ۲۴ عیار": ["gold_24k"],
    "طلای دست دوم": ["gold_used"],
    "مثقال طلا": ["gold_mesghal"],
    "مثقال بدون حباب": ["mesghal_no_bubble"],
    "انس طلا": ["gold_ounce"],
    "گرم نقره ۹۹۹": ["silver_gram"],
    "آبشده نقدی": ["abshedeh_cash"],
    "آبشده معاملاتی": ["abshedeh_trade"],
    
    # صندوق‌های طلا
    "صندوق طلای عیار": ["fund_ayar", "etf_ayar"],
    "صندوق طلای لوتوس": ["fund_lotus", "etf_lotus"],
    "صندوق طلای گوهر": ["fund_gohar", "etf_gohar"],
    "صندوق طلای مثقال": ["fund_mesghal", "etf_mesghal"],
    "صندوق طلای کهربا": ["fund_kahreba", "etf_kahroba"],
    "صندوق طلای ناب": ["fund_nab", "etf_nab"],
    "صندوق طلای ریتون": ["fund_riton", "etf_reyton"],
    "صندوق طلای تابش": ["fund_tabesh", "etf_tabesh"],
    "صندوق طلای زروان": ["fund_zarvan", "etf_zarvan"],
    
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

    # شاخص‌ها (ستون ارزش + تبدیل میلیون/هزار)
    "شاخص کل": ["bourse_total"],
    "شاخص کل هم‌وزن": ["bourse_equal"],
    "شاخص کل هم وزن": ["bourse_equal"],
    "شاخص فرابورس": ["fara_total"],
    "بازار اول فرابورس": ["ifb_market1", "fara_m1"],
    "بازار دوم فرابورس": ["ifb_market2", "fara_m2"],
    "شاخص بازار اول": ["bourse_market1", "bourse_m1"],
    "شاخص بازار دوم": ["bourse_market2", "bourse_m2"],
    "شاخص ۳۰ شرکت بزرگ": ["bourse_30"],
    "شاخص ۳۰ شرکت": ["bourse_30"],
    "شاخص ۵۰ شرکت فعال‌تر": ["bourse_50"],
    "شاخص قیمت ۵۰ شرکت": ["bourse_p50"],
    "شاخص قیمت هم‌وزن": ["bourse_pequal"],
    "شاخص قیمت وزنی ارزشی": ["bourse_pweighted"],
    "داوجونز": ["dow_jones"],
    "اس‌اندپی ۵۰۰": ["sp500"],
    "اس اند پی 500": ["sp500"],
    "نزدک": ["nasdaq"],
    "اس‌ام‌آی سوئیس": ["smi_swiss"],
    "اس ام آی سوئیس": ["smi_swiss"],
    "نیفتی ۵۰": ["nifty_50", "nifty50"],
    "فتسی بریتانیا": ["ftse_100", "ftse100"],
    "دکس آلمان": ["dax"],
    "کک فرانسه": ["cac_40"],
    "نیکی ژاپن": ["nikkei_225", "nikkei225"],
    "شانگهای چین": ["shanghai_composite", "shanghai"],
    "آیبکس اسپانیا": ["ibex_35", "ibex35"],
    "اس‌اندپی کانادا": ["tsx_canada"]
}

COMMODITIES = {"cotton", "sugar", "soybeans", "wheat", "corn", "rice", "aluminum", "nickel", "lead", "zinc", "copper", "tin", "oil_crude", "oil_brent", "oil_opec", "gasoline", "natural_gas", "coal"}
INDICES = {"bourse_total", "bourse_equal", "fara_total", "ifb_market1", "fara_m1", "ifb_market2", "fara_m2", "bourse_market1", "bourse_m1", "bourse_market2", "bourse_m2", "bourse_30", "bourse_50", "bourse_p50", "bourse_pequal", "bourse_pweighted", "dow_jones", "sp500", "nasdaq", "smi_swiss", "nifty_50", "nifty50", "ftse_100", "ftse100", "dax", "cac_40", "nikkei_225", "nikkei225", "shanghai_composite", "shanghai", "ibex_35", "ibex35", "tsx_canada"}
CRYPTO = {"btc", "eth", "usdt", "trx", "ada", "sol", "doge", "shib", "ton", "xrp", "ltc", "bch", "dot", "avax", "xlm", "dash", "bnb"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def to_english_digits(text: str) -> str:
    if not text:
        return ""
    text = text.replace('−', '-').replace('–', '-').replace(',', '').replace('،', '')
    return text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

def format_number(val: float) -> str:
    if val is None:
        return "-"
    if val.is_integer():
        return f"{int(val):,}"
    return f"{val:,.2f}".rstrip('0').rstrip('.')

def parse_price_value(raw_text: str, is_index: bool = False) -> tuple[str, float]:
    if not raw_text or raw_text == "-":
        return "-", 0.0
    
    clean_text = to_english_digits(raw_text)
    match = re.search(r'(\d+(?:\.\d+)?)', clean_text)
    if not match:
        return "-", 0.0
    
    val = float(match.group(1))
    
    if is_index or "میلیون" in raw_text or "میلیون" in clean_text:
        if "میلیون" in raw_text:
            val *= 1_000_000
    elif "هزار" in raw_text:
        val *= 1_000

    return format_number(val), val

def is_cell_red(cell_tag) -> bool:
    if not cell_tag:
        return False
    text = cell_tag if isinstance(cell_tag, str) else cell_tag.get_text()
    if "-" in text or "−" in text or "🔻" in text:
        return True
    
    if not isinstance(cell_tag, str):
        classes = list(cell_tag.get("class", []))
        if cell_tag.parent:
            classes.extend(cell_tag.parent.get("class", []))
        class_str = " ".join([str(c) for c in classes]).lower()
        style_str = str(cell_tag.get("style", "")).lower()
        if any(kw in class_str for kw in ["low", "drop", "red", "danger", "down", "minus"]) or "color: red" in style_str:
            return True
    return False

def parse_changes(change_cell, price_val: float) -> tuple[str, str]:
    if not change_cell:
        return "0", "0%"
    
    raw_text = change_cell if isinstance(change_cell, str) else change_cell.get_text(strip=True)
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

    if is_red:
        amt_str = f"-{format_number(amt_val)}" if amt_val != 0 else "0"
        pct_str = f"-{pct_val:.2f}%".rstrip('0').rstrip('.%') + "%" if pct_val != 0 else "0%"
    else:
        amt_str = format_number(amt_val)
        pct_str = f"{pct_val:.2f}%".rstrip('0').rstrip('.%') + "%" if pct_val != 0 else "0%"

    return amt_str, pct_str

def scrape_homepage_data():
    print("در حال دریافت داده‌های به‌روز از tgju.org ...", flush=True)
    scraped_data = []
    sorted_targets = sorted(SYMBOL_MAP.keys(), key=len, reverse=True)
    tehran_tz = pytz.timezone('Asia/Tehran')
    updated_at = datetime.now(tehran_tz).strftime("%Y-%m-%d %H:%M:%S")

    try:
        res = requests.get("https://www.tgju.org", headers=HEADERS, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            for table in soup.find_all("table"):
                price_col_idx, change_col_idx = 1, 2
                header_tr = table.find("tr")
                if header_tr:
                    cols = [c.get_text() for c in header_tr.find_all(["th", "td"])]
                    for idx, c_txt in enumerate(cols):
                        if any(k in c_txt for k in ["قیمت", "قیمت زنده", "ارزش", "قیمت (ریال)"]):
                            price_col_idx = idx
                        elif "تغییر" in c_txt:
                            change_col_idx = idx

                for row in table.find_all("tr"):
                    cols = row.find_all(["td", "th"])
                    if not cols or len(cols) < 2:
                        continue
                    
                    row_title = cols[0].get_text(strip=True)

                    matched_fa = next((t for t in sorted_targets if t == row_title or t in row_title), None)
                    if matched_fa:
                        symbol_keys = SYMBOL_MAP[matched_fa]
                        primary_key = symbol_keys[0]

                        price_cell = cols[price_col_idx] if len(cols) > price_col_idx else cols[1]
                        
                        # قوانین اختصاصی ستون‌ها
                        if primary_key in CRYPTO and len(cols) >= 3:
                            price_cell = cols[1] # قیمت ریالی
                        elif primary_key in COMMODITIES:
                            for c in cols[1:]:
                                if "$" in c.get_text() or "دلار" in c.get_text():
                                    price_cell = c
                                    break
                        elif primary_key in INDICES or "bubble" in primary_key:
                            for idx, c in enumerate(cols):
                                c_text = c.get_text()
                                if "ارزش" in c_text or "قیمت" in c_text or idx == 1:
                                    price_cell = cols[idx]

                        price_str, price_num = parse_price_value(price_cell.get_text(strip=True), is_index=(primary_key in INDICES))
                        
                        change_cell = cols[change_col_idx] if len(cols) > change_col_idx else None
                        change_amt, change_pct = parse_changes(change_cell, price_num)

                        for skey in symbol_keys:
                            scraped_data.append({
                                "symbol_key": skey,
                                "title_fa": matched_fa,
                                "price": price_str,
                                "change_amount": change_amt,
                                "change_percent": change_pct,
                                "updated_at": updated_at
                            })
    except Exception as e:
        print(f"خطا در استخراج: {e}", flush=True)

    unique_data = {item["symbol_key"]: item for item in scraped_data}
    return list(unique_data.values())
