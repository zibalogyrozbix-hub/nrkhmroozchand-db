import time
from datetime import datetime, time as dtime
import pytz
import subprocess

# دریافت تابع اسکرپ از فایل اول بدون تغییر در سورس آن
# نام اسکریپت اول شما هرچه هست، به‌جای scraper قرار دهید (بدون py.)
from main import scrape_homepage_data

TEHRAN_TZ = pytz.timezone('Asia/Tehran')

def trigger_project_2():
    """
    اجرای پروژه دوم پس از مشاهده اولین تغییر
    """
    print("\n🚀 اولین تغییر قیمت در بازه ۱۰ تا ۱۱:۲۰ مشاهده شد!")
    print("در حال فراخوانی پروژه دوم...")
    
    # نحوه اجرا بر اساس نوع پروژه دوم شما:
    # ۱) اگر پروژه دوم یک فایل پایتون مجزاست:
    subprocess.run(["python", "project2.py"])
    
    # ۲) اگر پروژه دوم با API یا Webhook کار می‌کند (نمونه):
    # requests.post("https://your-api-endpoint.com/trigger")


def extract_price_map(data_list: list) -> dict:
    """
    تبدیل خروجی اسکرپر به یک دیکشنری ساده از (نماد -> قیمت) برای مقایسه سریع
    """
    return {
        item['symbol_key']: item['price'] 
        for item in data_list 
        if item.get('price') and item['price'] != '-'
    }


def start_monitoring(check_interval_seconds: int = 20):
    """
    حلقه پایش قیمت‌ها در بازه ۱۰:۰۰ تا ۱۱:۲۰ به وقت تهران
    """
    print("⏳ ماژول پایش قیمت‌ها فعال شد...")
    last_prices = None

    while True:
        now = datetime.now(TEHRAN_TZ)
        current_time = now.time()

        start_window = dtime(10, 0, 0)   # ۱۰:۰۰:۰۰
        end_window = dtime(11, 20, 0)   # ۱۱:۲۰:۰۰

        # ۱. اگر هنوز ۱۰ صبح نشده است
        if current_time < start_window:
            seconds_to_wait = 30
            print(f"[{now.strftime('%H:%M:%S')}] هنوز زمان بازه (۱۰:۰۰) نرسیده است. صبر به مدت {seconds_to_wait} ثانیه...")
            time.sleep(seconds_to_wait)
            continue

        # ۲. اگر از ۱۱:۲۰ گذشته است
        if current_time > end_window:
            print(f"[{now.strftime('%H:%M:%S')}] بازه زمانی تعیین‌شده (۱۰:۰۰ تا ۱۱:۲۰) به پایان رسید. خروج.")
            break

        # ۳. اجرای پایش در بازه ۱۰:۰۰ تا ۱۱:۲۰
        print(f"\n[{now.strftime('%H:%M:%S')}] در حال دریافت و بررسی قیمت‌ها...")
        scraped_data = scrape_homepage_data()
        current_prices = extract_price_map(scraped_data)

        if not current_prices:
            print("⚠️ داده‌ای در این مرحله استخراج نشد. بررسی مجدد در دور بعدی...")
            time.sleep(check_interval_seconds)
            continue

        # اگر اولین اجرا در این بازه است، قیمت‌ها به عنوان مبنا ذخیره می‌شوند
        if last_prices is None:
            last_prices = current_prices
            print("✅ قیمت‌های پایه اولیه ثبت شدند. در انتظار مشاهده اولین تغییر...")
        else:
            # مقایسه قیمت‌های جدید با قیمت‌های نوبت قبل
            changed_symbol = None
            old_val = ""
            new_val = ""

            for symbol, price in current_prices.items():
                if symbol in last_prices and last_prices[symbol] != price:
                    changed_symbol = symbol
                    old_val = last_prices[symbol]
                    new_val = price
                    break  # پیدا شدن اولین تغییر

            if changed_symbol:
                print(f"🔔 تغییر قیمت یافت شد! | نماد: {changed_symbol} | قیمت قبلی: {old_val} | قیمت جدید: {new_val}")
                trigger_project_2()
                break  # خروج کامل از برنامه پس از تریگر موفق

            print("ℹ️ تغییری نسبت به نوبت قبل مشاهده نشد.")

        time.sleep(check_interval_seconds)


if __name__ == "__main__":
    # بر بر حسب ثانیه، فاصله زمان بین هر بار اسکرپ (مثلا هر ۲۰ ثانیه یک‌بار)
    start_monitoring(check_interval_seconds=20)
