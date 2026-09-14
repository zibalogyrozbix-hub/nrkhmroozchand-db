import re
import requests
from bs4 import BeautifulSoup

def to_english_digits(text: str) -> str:
    text = text.replace('−', '-').replace('–', '-')
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    english_digits = "0123456789"
    translation = str.maketrans(persian_digits + arabic_digits, english_digits * 2)
    return text.translate(translation)

def parse_percentage(cell_tag) -> float:
    """استخراج دقیق درصد تغییرات بر اساس کلاس‌های رنگی (قرمز/سبز)، پرانتز و علائم منفی"""
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
        
        # تشخیص رنگ قرمز / افت قیمت از روی کلاس‌های HTML و استایل
        negative_keywords = ["low", "drop", "red", "danger", "down", "minus", "decrease"]
        if any(kw in class_str for kw in negative_keywords) or "color: red" in style_str or "color:#f" in style_str or "color: #f" in style_str:
            is_negative = True

    if "-" in text or "−" in text or "🔻" in text:
        is_negative = True

    clean_text = to_english_digits(text)
    
    # جستجوی درصد
    pct_matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', clean_text)
    if not pct_matches:
        pct_matches = re.findall(r'%\s*(\d+(?:\.\d+)?)', clean_text)
    
    if pct_matches:
        val = float(pct_matches[0])
        if val < 500:
            return -val if is_negative else val

    # استخراج عدد داخل پرانتز
    paren_match = re.search(r'\((.*?)\)', clean_text)
    if paren_match:
        inside = paren_match.group(1)
        num_match = re.search(r'(\d+(?:\.\d+)?)', inside)
        if num_match:
            val = float(num_match.group(1))
            if val < 500:
                return -val if is_negative else val

    num_match = re.search(r'[-+]?(\d+(?:\.\d+)?)', clean_text)
    if num_match:
        val = float(num_match.group(1))
        if val < 500:
            return -val if is_negative else val

    return 0.0

def scrape_daily_homepage_changes():
    print("در حال رصد تغییرات روزانه بازار از صفحه اصلی tgju.org...", flush=True)
    daily_results = {}
    sorted_targets = sorted(DAILY_TARGET_ASSETS, key=len, reverse=True)

    try:
        res = requests.get("https://www.tgju.org", headers=HEADERS, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            
            for table in soup.find_all("table"):
                table_text = table.get_text()
                table_container_text = table.parent.get_text() if table.parent else ""
                
                # ۱. نادیده گرفتن جدول «سکه / تک فروشی»
                if "تک فروشی" in table_text or "تک‌فروشی" in table_text or "تک فروشی" in table_container_text:
                    continue
                
                # ۲. نادیده گرفتن ویجت ماشین‌حساب سکه
                if "هزینه ضرب" in table_text or "قیمت دلار (ریال)" in table_text:
                    continue

                change_col_idx = -1
                header_tr = table.find("tr")
                if header_tr:
                    cols = header_tr.find_all(["th", "td"])
                    for idx, col in enumerate(cols):
                        col_title = col.get_text()
                        if "تغییر" in col_title or "درصد" in col_title:
                            change_col_idx = idx
                            break
                
                for row in table.find_all("tr"):
                    cols = row.find_all(["td", "th"])
                    if not cols:
                        continue
                    
                    row_title = cols[0].get_text(strip=True)
                    row_full_text = row.get_text()
                    
                    # نادیده گرفتن سطر‌های حباب یا محاسباتی
                    if "حباب" in row_title or "حباب" in row_full_text or "هزینه ضرب" in row_full_text:
                        continue
                    
                    matched_asset = None
                    for target in sorted_targets:
                        if target in row_title or target in row_full_text:
                            matched_asset = target
                            break
                    
                    if matched_asset and matched_asset not in daily_results:
                        target_cell = None
                        
                        if change_col_idx != -1 and len(cols) > change_col_idx:
                            target_cell = cols[change_col_idx]
                        else:
                            for cell in cols[1:]:
                                cell_txt = cell.get_text()
                                if "(" in cell_txt and "%" in cell_txt:
                                    target_cell = cell
                                    break
                        
                        if target_cell:
                            pct_val = parse_percentage(target_cell)
                            daily_results[matched_asset] = pct_val
    except Exception as e:
        print(f"خطا در دریافت اطلاعات صفحه اصلی: {e}", flush=True)
        
    return daily_results
