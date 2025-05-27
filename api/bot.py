from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CallbackContext
import datetime
import os
import re
import pytz # برای مدیریت مناطق زمانی
import json # برای ذخیره File ID گیف دانلود شده

# --- پیکربندی ---
# توکن ربات خود را از BotFather دریافت کرده و به عنوان متغیر محیطی (توصیه شده) تنظیم کنید.
TOKEN = os.getenv("5992329338:AAFeMzENjcxAATji5mpDcgLNZg7VjfFfv9U") 
if not TOKEN:
    print("خطا: متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است.")
    print("لطفاً توکن ربات خود را از BotFather دریافت کرده و به عنوان متغیر محیطی تنظیم کنید.")
    exit()

# شناسه کانال مبدا که گیف‌ها در آن پست می‌شوند.
# (مثال: -1001234567890)
# دقت کنید که برای کانال، باید ID عددی کامل را وارد کنید، نه username.
# اگر username کانال 'taghvimghafasi' است و public است، می‌توانید با `@taghvimghafasi` هم کار کنید،
# اما استفاده از ID عددی امن‌تر است.
# برای یافتن ID عددی: ربات را ادمین کانال کنید، یک پیام در کانال بفرستید،
# به آدرس https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates بروید
# و ID عددی (با -100 شروع می‌شود) را از JSON کپی کنید.
CHANNEL_ID = '@taghvimghafasi' # ⚠️ حتماً این را با ID واقعی کانال خود جایگزین کنید!

# File ID گیف پیش‌فرض.
# برای دریافت File ID: گیف مورد نظر را به ربات خود (یا به BotFather) بفرستید.
# سپس از getUpdates (مانند بالا) پیام ارسالی خود را بررسی کنید و "file_id" را کپی کنید.
FALLBACK_GIF_FILE_ID = "BAACAgIAAxkBA..." # ⚠️ حتماً این را با File ID گیف پیش‌فرض خود جایگزین کنید!

# مسیر فایل برای ذخیره File ID گیف دانلود شده
GIF_FILE_ID_STORAGE = "daily_gif_id.json"

# منطقه زمانی تهران
TEHRAN_TZ = pytz.timezone('Asia/Tehran')

# --- توابع کمکی برای ذخیره و بازیابی File ID گیف ---
def save_gif_file_id(file_id: str, message_id: int):
    """File ID و Message ID گیف را در یک فایل JSON ذخیره می‌کند."""
    data = {
        "file_id": file_id,
        "message_id": message_id,
        "date": datetime.date.today().isoformat() # تاریخ ذخیره‌سازی
    }
    with open(GIF_FILE_ID_STORAGE, "w") as f:
        json.dump(data, f)
    print(f"گیف با File ID: {file_id} و Message ID: {message_id} ذخیره شد.")

def load_gif_file_id() -> tuple[str, int] | None:
    """File ID و Message ID گیف را از فایل JSON بازیابی می‌کند."""
    if not os.path.exists(GIF_FILE_ID_STORAGE):
        return None
    with open(GIF_FILE_ID_STORAGE, "r") as f:
        data = json.load(f)
    
    # بررسی می‌کنیم که آیا گیف مربوط به امروز است یا خیر
    if data.get("date") == datetime.date.today().isoformat():
        return data.get("file_id"), data.get("message_id")
    else:
        # اگر گیف برای روز قبل است، آن را حذف می‌کنیم تا ربات در روز جدید دوباره گیف را پیدا کند
        os.remove(GIF_FILE_ID_STORAGE)
        return None

# --- هندلر برای پیام‌های جدید در کانال ---
async def channel_post_handler(update: Update, context: CallbackContext) -> None:
    message = update.channel_post # پیام‌هایی که در کانال پست می‌شوند

    # فقط اگر پیام از کانال مورد نظر ما باشد
    if message.chat.id == CHANNEL_ID:
        # زمان پیام را به وقت تهران تبدیل می‌کنیم
        message_time_tehran = message.date.astimezone(TEHRAN_TZ)
        current_time_tehran = datetime.datetime.now(TEHRAN_TZ)

        # بررسی می‌کنیم که پیام مربوط به امروز باشد و در بازه 00:00 تا 00:01 قرار گرفته باشد
        # و همچنین این پیام یک گیف یا ویدیو باشد (که در تلگرام به عنوان animation یا video شناخته می‌شوند)
        if (message_time_tehran.date() == current_time_tehran.date() and
            message_time_tehran.hour == 0 and
            message_time_tehran.minute >= 0 and message_time_tehran.minute <= 1):
            
            # اگر پیام گیف باشد (animation)
            if message.animation:
                file_id = message.animation.file_id
                save_gif_file_id(file_id, message.message_id)
                print(f"گیف جدید از کانال در {message_time_tehran.strftime('%H:%M')} ذخیره شد.")
            # اگر پیام ویدیو باشد (و می‌خواهید ویدیوها را هم بپذیرید)
            elif message.video:
                file_id = message.video.file_id
                save_gif_file_id(file_id, message.message_id)
                print(f"ویدیوی جدید از کانال در {message_time_tehran.strftime('%H:%M')} ذخیره شد.")
            # اگر می‌خواهید هر نوع فایلی را قبول کنید:
            # elif message.document: # برای فایل‌های عمومی
            #     file_id = message.document.file_id
            #     save_gif_file_id(file_id, message.message_id)
            #     print(f"فایل جدید از کانال در {message_time_tehran.strftime('%H:%M')} ذخیره شد.")
            else:
                print(f"پیام در بازه زمانی مورد نظر بود، اما نه گیف بود نه ویدیو: {message_time_tehran.strftime('%H:%M')}")
        else:
            print(f"پیام از کانال، اما خارج از بازه زمانی مورد نظر یا نوع نامناسب: {message_time_tehran.strftime('%H:%M')}")


# --- هندلر برای پاسخ به دستور "امروز چندمه؟" در گروه‌ها ---
async def group_message_handler(update: Update, context: CallbackContext) -> None:
    message = update.message

    # اطمینان حاصل کنید که دستور در یک گروه یا سوپرگروه صادر شده است
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply_text("این دستور فقط در گروه‌ها فعال است.")
        return

    # بررسی می‌کنیم که متن پیام شامل "امروز چندمه" یا "امروز چه روزیه" باشد
    if message.text and ("امروز چندمه" in message.text or "امروز چه روزیه" in message.text):
        # تلاش برای بارگذاری File ID گیف ذخیره شده برای امروز
        stored_gif_info = load_gif_file_id()

        if stored_gif_info:
            file_id, message_id_to_forward = stored_gif_info
            try:
                # فوروارد کردن گیف اصلی از کانال
                await context.bot.forward_message(
                    chat_id=message.chat_id,         # شناسه چت گروهی که دستور در آن صادر شده است
                    from_chat_id=CHANNEL_ID,         # شناسه کانالی که گیف از آن فوروارد می‌شود
                    message_id=message_id_to_forward # شناسه پیام گیف در کانال
                )
                print(f"گیف اصلی به گروه {message.chat.title} فوروارد شد.")
            except Exception as e:
                # اگر فوروارد کردن به هر دلیلی با مشکل مواجه شد (مثلاً پیام حذف شده بود)
                print(f"خطا در فوروارد گیف اصلی: {e}. ارسال گیف پیش‌فرض.")
                await context.bot.send_animation(
                    chat_id=message.chat_id,
                    animation=FALLBACK_GIF_FILE_ID,
                    caption="متاسفانه گیف امروز پیدا نشد یا قابل فوروارد نبود، این گیف پیش‌فرض است."
                )
        else:
            # اگر هیچ گیفی برای امروز ذخیره نشده بود، گیف پیش‌فرض را می‌فرستیم
            print("گیف امروز ذخیره نشده بود. ارسال گیف پیش‌فرض.")
            await context.bot.send_animation(
                chat_id=message.chat_id,
                animation=FALLBACK_GIF_FILE_ID,
                caption="امروز گیفی در بازه 00:00 تا 00:01 در کانال پیدا نشد، این گیف پیش‌فرض است."
            )

# --- تابع اصلی برای اجرای ربات ---
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    # هندلر برای دریافت پیام‌های جدید در کانال (از نوع channel_post)
    # این هندلر باید قبل از `group_message_handler` اضافه شود
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post_handler))

    # هندلر برای رصد پیام‌های متنی در گروه‌ها
    # ما از یک فیلتر کلی استفاده می‌کنیم و بررسی دقیق متن پیام را در خود هندلر انجام می‌دهیم.
    application.add_handler(MessageHandler(filters.TEXT & filters.GROUP, group_message_handler))

    print("ربات شروع به کار کرد! منتظر پیام‌ها...")
    # شروع پولینگ برای دریافت آپدیت‌ها
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()