import os,re,json,sqlite3
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pytz,jdatetime
from playwright.sync_api import sync_playwright

try:
    import libsql_experimental as libsql
    HAS_LIBSQL=True
except ImportError:
    HAS_LIBSQL=False

SYMBOL_MAP={
"سکه امامی":["coin_emami"],"سکه بهار آزادی":["coin_azadi"],"نیم سکه":["coin_half"],"ربع سکه":["coin_quarter"],"سکه گرمی":["coin_gram"],
"طلای ۱۸ عیار":["gold_18k"],"طلای ۲۴ عیار":["gold_24k"],"طلای دست دوم":["gold_used"],"مثقال طلا":["gold_mesghal"],"انس طلا":["gold_ounce"],
"گرم نقره ۹۹۹":["silver_gram"],"آبشده نقدی":["abshedeh_cash"],"آبشده معاملاتی":["abshedeh_trade"],"انس نقره":["silver_ounce"],
"انس پلاتین":["platinum_ounce"],"انس پالادیوم":["palladium_ounce"],"مثقال / بدون حباب":["mesghal_no_bubble"],"مثقال بدون حباب":["mesghal_no_bubble"],
"حباب سکه امامی":["bubble_emami"],"حباب سکه بهار آزادی":["bubble_azadi"],"حباب نیم سکه":["bubble_half"],"حباب ربع سکه":["bubble_quarter"],"حباب سکه گرمی":["bubble_gram"],
"صندوق طلای عیار":["fund_ayar"],"صندوق طلای لوتوس":["fund_lotus"],"صندوق طلای گوهر":["fund_gohar"],"صندوق طلای مثقال":["fund_mesghal"],
"صندوق طلای کهربا":["fund_kahreba"],"صندوق طلای ناب":["fund_nab"],"صندوق طلای ریتون":["fund_riton"],"صندوق طلای تابش":["fund_tabesh"],"صندوق طلای زروان":["fund_zarvan"],
"دلار":["usd"],"یورو":["eur"],"درهم امارات":["aed"],"پوند انگلیس":["gbp"],"لیر ترکیه":["try"],"فرانک سوئیس":["chf"],"یوان چین":["cny"],"ین ژاپن":["jpy"],
"وون کره جنوبی":["krw"],"دلار کانادا":["cad"],"دلار استرالیا":["aud"],"افغانی":["afn"],"درام ارمنستان":["amd"],"منات آذربایجان":["azn"],"دینار بحرین":["bhd"],
"کرون دانمارک":["dkk"],"لاری گرجستان":["gel"],"دلار هنگ‌کنگ":["hkd"],"روپیه هند":["inr"],"دینار عراق":["iqd"],"سوم قرقیزستان":["kgs"],"دینار کویت":["kwd"],
"رینگیت مالزی":["myr"],"کرون نروژ":["nok"],"دلار نیوزیلند":["nzd"],"ریال عمان":["omr"],"روپیه پاکستان":["pkr"],"ریال قطر":["qar"],"روبل روسیه":["rub"],
"ریال عربستان":["sar"],"کرون سوئد":["sek"],"دلار سنگاپور":["sgd"],"لیر سوریه":["syp"],"بات تایلند":["thb"],"سامانی تاجیکستان":["tjs"],"منات ترکمنستان":["tmt"],
"بیت‌کوین":["btc"],"بیت کوین":["btc"],"اتریوم":["eth"],"تتر":["usdt"],"ترون":["trx"],"کاردانو":["ada"],"سولانا":["sol"],"دوج کوین":["doge"],"شیبا اینو":["shib"],
"تون‌کوین":["ton"],"ریپل":["xrp"],"لایت‌کوین":["ltc"],"بیت‌کوین کش":["bch"],"پولکادات":["dot"],"آوالانچ":["avax"],"استلار":["xlm"],"دش":["dash"],"بایننس کوین":["bnb"],
"پنبه":["cotton"],"شکر":["sugar"],"سویا":["soybeans"],"گندم":["wheat"],"ذرت":["corn"],"برنج":["rice"],"آلومینیوم":["aluminum"],"نیکل":["nickel"],"سرب":["lead"],"روی":["zinc"],
"مس":["copper"],"قلع":["tin"],"نفت سبک":["oil_crude"],"نفت برنت":["oil_brent"],"نفت اوپک":["oil_opec"],"بنزین (RBOB)":["gasoline"],"گاز طبیعی":["natural_gas"],"زغال سنگ":["coal"],
"بازار اول فرابورس":["ifb_market1"],"بازار دوم فرابورس":["ifb_market2"],"شاخص بازار اول":["bourse_market1"],"شاخص بازار دوم":["bourse_market2"],
"شاخص قیمت هم‌وزن":["bourse_pequal"],"شاخص قیمت وزنی ارزشی":["bourse_pweighted"],"داوجونز":["dow_jones"],"نزدک":["nasdaq"],"اس‌ام‌آی سوئیس":["smi_swiss"],
"اس ام آی سوئیس":["smi_swiss"],"نیفتی ۵۰":["nifty_50"],"نیفتی 50":["nifty_50"],"فتسی بریتانیا":["ftse_100"],"دکس آلمان":["dax"],"کک فرانسه":["cac_40"],
"نیکی ژاپن":["nikkei_225"],"شانگهای چین":["shanghai_composite"],"آیبکس اسپانیا":["ibex_35"]}

COMMODITIES={"cotton","sugar","soybeans","wheat","corn","rice","aluminum","nickel","lead","zinc","copper","tin","oil_crude","oil_brent","oil_opec","gasoline","natural_gas","coal"}
INDICES={"bourse_total","ifb_market1","ifb_market2","bourse_market1","bourse_market2","bourse_pequal","bourse_pweighted","dow_jones","nasdaq","smi_swiss","nifty_50","ftse_100","dax","cac_40","nikkei_225","shanghai_composite","ibex_35"}
CRYPTO={"btc","eth","usdt","trx","ada","sol","doge","shib","ton","xrp","ltc","bch","dot","avax","xlm","dash","bnb"}

TOMAN_PRICE_SYMBOLS={
"coin_emami","coin_azadi","coin_half","coin_quarter","coin_gram","gold_18k","gold_24k","gold_used","gold_mesghal","silver_gram",
"abshedeh_cash","abshedeh_trade","mesghal_no_bubble","bubble_emami","bubble_azadi","bubble_half","bubble_quarter","bubble_gram",
"fund_ayar","fund_lotus","fund_gohar","fund_mesghal","fund_kahreba","fund_nab","fund_riton","fund_tabesh","fund_zarvan",
"usd","eur","aed","gbp","try","chf","cny","jpy","krw","cad","aud","afn","amd","azn","bhd","dkk","gel","hkd","inr","iqd","kgs","kwd","myr","nok","nzd","omr","pkr","qar","rub","sar","sek","sgd","syp","thb","tjs","tmt",
"btc","eth","usdt","trx","ada","sol","doge","shib","ton","xrp","ltc","bch","dot","avax","xlm","dash","bnb"}

SANITY_DIGIT_DIFF_THRESHOLD=3
SANITY_PERCENT_WARN_THRESHOLD=50.0
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

def _to_float(v):
    if v is None or v=="-": return None
    try: return float(str(v).replace(",","").replace("٬","").strip())
    except (ValueError,TypeError): return None

def _digit_count(v): return len(str(int(abs(v))))

def fetch_rendered_html(url,extra_wait=3.0):
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url,wait_until="domcontentloaded",timeout=30000)
            try: page.locator("text='در حال بارگذاری...'").first.wait_for(state="detached",timeout=8000)
            except Exception: pass
            page.wait_for_timeout(int(extra_wait*1000))
            html=page.content(); browser.close(); return html
    except Exception as e:
        print(f"خطا در رندر صفحه با Playwright ({url}): {e}",flush=True); return None

_TITLE_DIGIT_TRANSLATION=str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789")

def clean_title(text):
    if not text:return ""
    text=text.replace("\u200c"," ").replace("\u200f","").replace("ي","ی").replace("ك","ک").translate(_TITLE_DIGIT_TRANSLATION)
    return re.sub(r"\s+"," ",text).strip()

def get_cell_text(tag):
    if tag is None:return ""
    return tag if isinstance(tag,str) else tag.get_text(" ",strip=True)

def to_english_digits(text):
    if not text:return ""
    text=text.replace("−","-").replace("–","-").replace(",","").replace("،","").replace("٬","")
    return text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))

def format_number_with_comma(v):
    if v is None:return "-"
    if isinstance(v,int) or (isinstance(v,float) and v.is_integer()):return f"{int(v):,}"
    return f"{v:,.2f}".rstrip("0").rstrip(".")

def parse_price_value(raw_text,is_index=False):
    if not raw_text or raw_text.strip()=="-":return "-",0.0
    clean=to_english_digits(raw_text); m=re.search(r"(\d+(?:\.\d+)?)",clean)
    if not m:return "-",0.0
    v=float(m.group(1)) if "." in m.group(1) else int(m.group(1))
    if is_index or "میلیون" in raw_text or "میلیون" in clean:
        if "میلیون" in raw_text or "میلیون" in clean:v*=1_000_000
    elif "هزار" in raw_text:v*=1_000
    return format_number_with_comma(v),v

def is_cell_red(cell):
    if not cell:return False
    text=get_cell_text(cell)
    if "-" in text or "−" in text or "🔻" in text:return True
    if not isinstance(cell,str):
        classes=list(cell.get("class",[]))
        for child in cell.find_all(True):classes.extend(child.get("class",[]))
        if cell.parent:classes.extend(cell.parent.get("class",[]))
        cs=" ".join(map(str,classes)).lower(); ss=str(cell.get("style","")).lower()
        if any(k in cs for k in ["low","drop","red","danger","down","minus"]) or "color: red" in ss or "color:#f" in ss:return True
    return False

def parse_change_components(cell):
    if not cell:return 0.0,0.0,False
    raw=to_english_digits(get_cell_text(cell)); neg=is_cell_red(cell)
    pm=re.search(r"\(([^)]*)\)",raw); pct=0.0
    if pm:
        m=re.search(r"(\d+(?:\.\d+)?)",pm.group(1))
        if m:pct=float(m.group(1))
    no_pct=re.sub(r"\([^)]*\)","",raw); am=re.search(r"(\d+(?:\.\d+)?)",no_pct)
    return (float(am.group(1)) if am else 0.0),pct,neg

def parse_changes(cell,price_val):
    amt,pct,neg=parse_change_components(cell)
    if pct==0 and price_val>0 and amt>0:pct=amt/price_val*100
    if abs(pct)>100:amt=pct=0.0
    return (("-" if neg and amt else "")+format_number_with_comma(amt) if amt else "0"),(f"{'-' if neg and pct else ''}{pct:.2f}%" if pct else "0%")

def calculate_crypto_change_toman(cell,price_rial,price_usd):
    amt_usd,pct,neg=parse_change_components(cell)
    if not amt_usd or price_rial<=0 or price_usd<=0:
        return "0",(f"{'-' if neg and pct else ''}{pct:.2f}%" if pct else "0%")
    change_toman=amt_usd*(price_rial/price_usd)/10
    if neg:change_toman=-abs(change_toman)
    return format_number_with_comma(change_toman),(f"{'-' if neg and pct else ''}{pct:.2f}%" if pct else "0%")

def find_header_col(headers,patterns):
    for i,c in enumerate(headers):
        h=get_cell_text(c).replace(" ","").replace("\u200c","").replace("\u200f","")
        for p in patterns:
            if p.replace(" ","") in h:return i
    return -1

def is_real_data_table(table,headers):
    if table.find(["input","select","button"]) is not None:return False
    h=" ".join(get_cell_text(c) for c in headers)
    return any(k in h for k in ["قیمت زنده","قیمت","ارزش"]) and "تغییر" in h

def scrape_homepage_data():
    print("در حال دریافت داده‌ها از tgju.org ...",flush=True)
    out=[]; targets=sorted(SYMBOL_MAP,key=len,reverse=True); tz=pytz.timezone("Asia/Tehran")
    updated_at=datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S"); seen=[]; unknown=set()
    try:
        html=fetch_rendered_html("https://www.tgju.org",3.0)
        if html:
            soup=BeautifulSoup(html,"html.parser")
            for table in soup.find_all("table"):
                pidx,cidx=1,2; htr=table.find("tr"); headers=htr.find_all(["th","td"]) if htr else []
                seen.append(" ".join(get_cell_text(c) for c in headers))
                if not is_real_data_table(table,headers):continue
                for i,c in enumerate(headers):
                    if i==0:continue
                    t=get_cell_text(c)
                    if "ارزش" in t:pidx=i
                    elif any(k in t for k in ["قیمت","قیمت زنده","قیمت (ریال)"]) and pidx==1:pidx=i
                    elif "تغییر" in t:cidx=i
                crypto_usd_idx=find_header_col(headers,["قیمت/دلار","قیمت / دلار","قیمت دلار","قیمت (دلار)","دلار","$"])
                for row in table.find_all("tr"):
                    cols=row.find_all(["td","th"])
                    if len(cols)<2:continue
                    title=clean_title(get_cell_text(cols[0]))
                    match=next((t for t in targets if clean_title(t)==title),None)
                    if not match and "/" not in title:match=next((t for t in targets if clean_title(t) in title),None)
                    if not match:
                        if row is not htr and "/" not in title and len(title)>=2:unknown.add(title)
                        continue
                    keys=SYMBOL_MAP[match]; key=keys[0]
                    price_cell=cols[pidx] if len(cols)>pidx else cols[1]
                    if key in CRYPTO:price_cell=cols[1]
                    elif key in COMMODITIES:
                        ui=find_header_col(headers,["قیمت/دلار","قیمت ($)","قیمت$","دلار"])
                        if ui!=-1 and ui<len(cols):price_cell=cols[ui]
                        else:
                            for c in cols[1:]:
                                if "$" in get_cell_text(c) or "دلار" in get_cell_text(c):price_cell=c;break
                    elif key in INDICES:
                        vi=find_header_col(headers,["ارزش"])
                        if vi!=-1 and vi<len(cols):price_cell=cols[vi]
                        else:
                            found=False
                            for i,c in enumerate(cols):
                                txt=get_cell_text(c); ht=get_cell_text(headers[i]) if i<len(headers) else ""
                                if txt and txt!="-" and any(ch.isdigit() for ch in txt) and ("ارزش" in ht or "قیمت" in ht or i==pidx):
                                    price_cell=c;found=True;break
                            if not found and len(cols)>pidx:price_cell=cols[pidx]
                    price_raw,price_rial=parse_price_value(get_cell_text(price_cell),key in INDICES)
                    usd=None
                    if key in CRYPTO:
                        if crypto_usd_idx!=-1 and crypto_usd_idx<len(cols):_,usd=parse_price_value(get_cell_text(cols[crypto_usd_idx]))
                        if not usd:
                            for i,c in enumerate(cols[2:],2):
                                if i<len(headers) and ("دلار" in clean_title(get_cell_text(headers[i])) or "$" in get_cell_text(headers[i])):
                                    _,cand=parse_price_value(get_cell_text(c))
                                    if cand>0:usd=cand;break
                    if key in TOMAN_PRICE_SYMBOLS:price=format_number_with_comma(price_rial/10)
                    else:price=price_raw
                    change_cell=cols[cidx] if len(cols)>cidx else None
                    if key in CRYPTO:change_amt,change_pct=calculate_crypto_change_toman(change_cell,price_rial,usd or 0)
                    else:change_amt,change_pct=parse_changes(change_cell,price_rial/10 if key in TOMAN_PRICE_SYMBOLS else price_rial)
                    display=match+(" (دلار)" if key in COMMODITIES and "(دلار)" not in match else "")
                    for skey in keys:
                        out.append({"symbol_key":skey,"title_fa":display,"price":price,"change_amount":change_amt,"change_percent":change_pct,"updated_at":updated_at})
    except Exception as e:print(f"خطا در استخراج: {e}",flush=True)
    unique={}
    for x in out:
        if x["symbol_key"] not in unique or unique[x["symbol_key"]]["price"]=="-":unique[x["symbol_key"]]=x
    if seen and not any(k in " ".join(seen) for k in ["قیمت زنده","آخرین قیمت","قیمت / دلار","ارزش","تغییر"]):
        print("🚨 هشدار جدی: هیچ‌کدام از سرستون‌های شناخته‌شده در هیچ جدولی روی صفحه پیدا نشد.",flush=True)
    if unknown:print(f"\n💡 {len(unknown)} عنوان ردیف ناشناخته پیدا شد: {' | '.join(sorted(unknown)[:15])}",flush=True)
    return list(unique.values())

def fetch_bourse_total_index():
    tz=pytz.timezone("Asia/Tehran"); updated_at=datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    price_labels=["نرخ فعلی","نرخ لحظه ای","قیمت لحظه ای"]; amount_labels=["میزان تغییر نسبت به روز گذشته","میزان تغییر"]; percent_labels=["درصد تغییر نسبت به روز گذشته","درصد تغییر"]
    def find_value(soup,labels):
        for row in soup.find_all("tr"):
            cells=row.find_all(["th","td"])
            if len(cells)<2:continue
            for i,c in enumerate(cells):
                if any(lbl in clean_title(get_cell_text(c)) for lbl in labels):
                    if i+1<len(cells):return get_cell_text(cells[i+1])
                    if i: return get_cell_text(cells[i-1])
        for item in soup.select("li,div"):
            spans=item.find_all(["span","div","td"],recursive=False)
            if len(spans)>=2 and any(lbl in clean_title(get_cell_text(spans[0])) for lbl in labels):return get_cell_text(spans[1])
        return None
    try:
        html=fetch_rendered_html("https://www.tgju.org/profile/gc30",2.0)
        if not html:return None
        soup=BeautifulSoup(html,"html.parser"); raw_price=find_value(soup,price_labels); raw_amt=find_value(soup,amount_labels); raw_pct=find_value(soup,percent_labels)
        if raw_price is None:
            print("هشدار: مقدار «نرخ فعلی» برای شاخص کل (gc30) پیدا نشد.",flush=True);return None
        price,_=parse_price_value(raw_price,True); change_amt="0"
        if raw_amt is not None:
            s=to_english_digits(raw_amt);m=re.search(r"(-?\d+(?:\.\d+)?)",s)
            if m:
                v=abs(float(m.group(1)));v=-v if "-" in s or "کاهش" in raw_amt else v;change_amt=format_number_with_comma(v)
        change_pct="0%"
        if raw_pct is not None:
            s=to_english_digits(raw_pct);m=re.search(r"(-?\d+(?:\.\d+)?)",s)
            if m:
                v=abs(float(m.group(1)));v=-v if "-" in s or "کاهش" in raw_pct else v;change_pct=f"{v:.2f}%"
        return {"symbol_key":"bourse_total","title_fa":"شاخص کل","price":price,"change_amount":change_amt,"change_percent":change_pct,"updated_at":updated_at}
    except Exception as e:print(f"خطا در استخراج شاخص کل بورس از gc30: {e}",flush=True);return None

def get_db_connection():
    url=os.environ.get("TURSO_DATABASE_URL","").strip();token=os.environ.get("TURSO_AUTH_TOKEN","").strip()
    if url and token and HAS_LIBSQL:
        if url.startswith("libsql://"):url=url.replace("libsql://","https://")
        elif not url.startswith("https://"):url="https://"+url
        print(f"اتصال مستقیم به دیتابیس Turso ({url}) ...",flush=True);return libsql.connect(database=url,auth_token=token)
    print("اتصال به SQLite محلی ...",flush=True);return sqlite3.connect("market_database.db")

def write_data_json(data):
    path="data.json";tmp=path+".tmp"
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(sorted(data,key=lambda x:x.get("title_fa","")),f,ensure_ascii=False,indent=2);f.write("\n")
        os.replace(tmp,path);print(f"فایل {path} با موفقیت ایجاد/بروزرسانی شد ({len(data)} رکورد).",flush=True);return True
    except Exception as e:
        try:
            if os.path.exists(tmp):os.remove(tmp)
        except OSError:pass
        print(f"خطا در ایجاد فایل {path}: {e}",flush=True);return False

def update_database(data_list):
    existing={};conn=None
    try:
        conn=get_db_connection();cur=conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS market_prices(symbol_key TEXT PRIMARY KEY,title_fa TEXT,price TEXT,change_amount TEXT,change_percent TEXT,updated_at TEXT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS market_meta(key TEXT PRIMARY KEY,value TEXT)""")
        migrated=cur.execute("SELECT value FROM market_meta WHERE key='price_unit'").fetchone()
        migrated=migrated and migrated[0]=="toman"
        for r in cur.execute("SELECT symbol_key,title_fa,price,change_amount,change_percent,updated_at FROM market_prices").fetchall():
            existing[r[0]]={"symbol_key":r[0],"title_fa":r[1],"price":r[2],"change_amount":r[3],"change_percent":r[4],"updated_at":r[5]}
        # دیتابیس اولیه طبق نسخه قدیمی ریالی بوده؛ فقط یک بار مهاجرت می‌شود.
        if not migrated:
            for k,r in existing.items():
                if k in TOMAN_PRICE_SYMBOLS:
                    v=_to_float(r["price"])
                    if v is not None:r["price"]=format_number_with_comma(v/10)
            cur.execute("INSERT OR REPLACE INTO market_meta(key,value) VALUES('price_unit','toman')")
            for k,r in existing.items():
                cur.execute("""UPDATE market_prices SET price=? WHERE symbol_key=?""",(r["price"],k))
            conn.commit()
    except Exception as e:
        print(f"⚠️ هشدار: عدم امکان برقراری ارتباط با دیتابیس جهت خواندن مقادیر قبلی ({e}) — پردازش ادامه می‌یابد.",flush=True)

    accepted=[];rejected=[]
    for item in data_list:
        old=existing.get(item["symbol_key"]);oldv=_to_float(old["price"]) if old else None;newv=_to_float(item["price"])
        if oldv is not None and newv is not None and oldv!=0:
            if abs(_digit_count(oldv)-_digit_count(newv))>=SANITY_DIGIT_DIFF_THRESHOLD:
                rejected.append({"symbol_key":item["symbol_key"],"title_fa":item["title_fa"],"old_price":old["price"],"new_price":item["price"]});continue
            pc=abs(newv-oldv)/abs(oldv)*100
            if pc>=SANITY_PERCENT_WARN_THRESHOLD:print(f"⚠️ هشدار: {item['symbol_key']} ({item['title_fa']}) با {pc:.0f}% تغییر کرده.",flush=True)
        accepted.append(item)

    snapshot=dict(existing)
    snapshot.update({x["symbol_key"]:x for x in accepted})
    write_data_json(list(snapshot.values()))

    if conn:
        try:
            for x in accepted:
                cur.execute("""INSERT INTO market_prices(symbol_key,title_fa,price,change_amount,change_percent,updated_at) VALUES(?,?,?,?,?,?)
                ON CONFLICT(symbol_key) DO UPDATE SET title_fa=excluded.title_fa,price=excluded.price,change_amount=excluded.change_amount,change_percent=excluded.change_percent,updated_at=excluded.updated_at""",
                (x["symbol_key"],x["title_fa"],x["price"],x["change_amount"],x["change_percent"],x["updated_at"]))
            conn.commit();print(f"تعداد {len(accepted)} شاخص در دیتابیس بروزرسانی شد.",flush=True)
        except Exception as e:print(f"❌ خطای دیتابیس (فایل data.json بدون مشکل تولید شد): {e}",flush=True)
        finally:
            try:conn.close()
            except Exception:pass
    else:print("ℹ️ دیتابیس در دسترس نبود اما data.json با موفقیت به‌روزرسانی شد.",flush=True)

    if rejected:print(f"\n🚫 {len(rejected)} مورد به دلیل جهش رقمی مشکوک رد شدند.",flush=True)
    expected={sk for keys in SYMBOL_MAP.values() for sk in keys}|{"bourse_total"};matched={x["symbol_key"] for x in accepted};missing=sorted(expected-matched)
    if missing:print(f"\n📋 {len(missing)} نماد در این اجرا پیدا نشدند: {', '.join(missing)}",flush=True)

    try:
        now=datetime.now(pytz.timezone("Asia/Tehran"));stale=[]
        for k,r in existing.items():
            if k in matched:continue
            try:
                dt=pytz.timezone("Asia/Tehran").localize(datetime.strptime(r["updated_at"],"%Y-%m-%d %H:%M:%S"));h=(now-dt).total_seconds()/3600
                if h>=48:stale.append((k,round(h)))
            except (ValueError,TypeError):continue
        if stale:
            stale.sort(key=lambda x:-x[1]);print("\n⏰ این نمادها بیش از 48 ساعت است بروزرسانی نشده‌اند (به‌احتمال زیاد الگوی match‌شان خراب شده):",flush=True)
            for k,h in stale:print(f"   - {k}: {h} ساعت قدیمی",flush=True)
    except Exception as e:print(f"هشدار: محاسبهٔ گزارش داده‌های قدیمی ممکن نشد: {e}",flush=True)

if __name__=="__main__":
    try:
        data=scrape_homepage_data();bourse=fetch_bourse_total_index()
        if bourse:data.append(bourse)
        if data:update_database(data)
        else:print("⚠️ هیچ داده‌ای در این اجرا استخراج نشد.",flush=True)
    except Exception as e:print(f"❌ خطای غیرمنتظره در اجرای اسکریپت: {e}",flush=True)
