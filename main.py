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

def clean_title(text: str) -> str:
    """حذف کاراکترهای نیم‌فاصله/فاصله اضافه برای مقایسه دقیق عنوان ردیف با کلیدهای SYMBOL_MAP"""
    if not text:
        return ""
    return text.replace('\u200c', ' ').replace('\u200f', '').strip()
    
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

    try:
        res = requests.get("https://www.tgju.org", headers=HEADERS, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            for table in soup.find_all("table"):
                price_col_idx, change_col_idx = 1, 2
                header_tr = table.find("tr")
                header_cells = header_tr.find_all(["th", "td"]) if header_tr else []

                # رد کردن فرم‌های محاسبه‌گر/دراپ‌داون‌ها که جدول قیمت واقعی نیستند
                if not is_real_data_table(table, header_cells):
                    continue

                # پیدا کردن دقیق ایندکس ستون "ارزش" یا "قیمت" در هدر جدول
                for idx, c in enumerate(header_cells):
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
                    # امتحان می‌کنیم (برای مواردی که سایت پسوند/پیشوند اضافه دارد)
                    if not matched_fa:
                        matched_fa = next(
                            (t for t in sorted_targets if clean_title(t) in row_title),
                            None
                        )
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

                        for skey in symbol_keys:
                            scraped_data.append({
                                "symbol_key": skey,
                                "title_fa": matched_fa,
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

    return list(unique_data.values())

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
    
    for item in data_list:
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
    print(f"تعداد {len(data_list)} شاخص در جدول market_prices بروزرسانی شد.", flush=True)

if __name__ == "__main__":
    data = scrape_homepage_data()
    if data:
        update_database(data)
