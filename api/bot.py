# api/bot.py

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CallbackContext
import datetime
import os
import re
import pytz
import json
import redis.asyncio as redis # برای Redis

from flask import Flask, request, jsonify # برای Webhook

# --- پیکربندی ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "5992329338:AAFeMzENjcxAATji5mpDcgLNZg7VjfFfv9U") 

# آدرس اتصال به Redis: باید به عنوان متغیر محیطی در Vercel تنظیم شود.
REDIS_URL = os.getenv("REDIS_URL") 

# شناسه کانال مبدا (taghvimghafasi): باید به عنوان متغیر محیطی در Vercel تنظیم شود.
# این رو برای فوروارد کردن پیام از کانال نیاز داریم.
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1001886988651")) 

# File ID گیف پیش‌فرض: باید به عنوان متغیر محیطی در Vercel تنظیم شود.
FALLBACK_GIF_FILE_ID = os.getenv("FALLBACK_GIF_FILE_ID", "AAMCBAADGQECA_NgaDYn12DAX8o5DZdL_PjivicNsPQAApMYAAISe7lRlJGAmFWt294BAAdtAAM2BA")

# منطقه زمانی تهران
TEHRAN_TZ = pytz.timezone('Asia/Tehran')

# --- اتصال به Redis (یک بار در شروع برنامه) ---
redis_client = None # ابتدا None قرار می‌دهیم
if REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL)
        print("Redis client initialized.")
    except Exception as e:
        print(f"Error initializing Redis client: {e}")
else:
    print("Warning: REDIS_URL not set. Redis storage will not be available.")

# --- مقداردهی اولیه Application ربات (فقط یک بار) ---
# این بخش رو به صورت گلوبال تعریف می‌کنیم و مطمئن می‌شیم فقط یک بار ساخته میشه
application = None # ابتدا None قرار می‌دهیم
if TOKEN: # فقط اگر توکن داریم، application رو می‌سازیم
    try:
        application = Application.builder().token(TOKEN).build()
        application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post_handler))
        application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, group_message_handler))
        print("Telegram Application handlers added.")
    except Exception as e:
        print(f"Error initializing Telegram Application: {e}")
else:
    print("Error: TELEGRAM_BOT_TOKEN not set. Telegram Application cannot be initialized.")


# --- توابع برای ذخیره و بازیابی File ID و Message ID گیف با Redis ---
# ... (این توابع بدون تغییر می‌مانند) ...
async def save_gif_info(file_id: str, message_id: int):
    """File ID و Message ID گیف را در Redis ذخیره می‌کند."""
    if not redis_client:
        print("Error: Redis client is not initialized. Cannot save GIF info.")
        return

    key = datetime.date.today().isoformat() # کلید برای گیف امروز (مثال: "2023-10-27")
    value = json.dumps({"file_id": file_id, "message_id": message_id}) # ذخیره به صورت رشته JSON
    
    try:
        # ذخیره با زمان انقضا (TTL) 7 روز برای پاکسازی خودکار
        await redis_client.set(key, value, ex=60 * 60 * 24 * 7) 
        print(f"GIF with File ID: {file_id} and Message ID: {message_id} saved to Redis for key {key}.")
    except Exception as e:
        print(f"Error saving to Redis: {e}")

async def load_gif_info() -> tuple[str, int] | None:
    """File ID و Message ID گیف را از Redis برای امروز بازیابی می‌کند."""
    if not redis_client:
        print("Error: Redis client is not initialized. Cannot load GIF info.")
        return None

    key = datetime.date.today().isoformat()
    
    try:
        value = await redis_client.get(key)
        if value:
            gif_data = json.loads(value) # از رشته JSON به دیکشنری تبدیل می‌کنیم
            print(f"اطلاعات گیف از Redis برای کلید {key} بارگذاری شد.")
            return gif_data.get("file_id"), gif_data.get("message_id")
        
        print(f"هیچ اطلاعات گیف معتبری در Redis برای کلید {key} امروز پیدا نشد.")
        return None
    except Exception as e:
        print(f"خطا در بارگذاری از Redis: {e}")
    return None


# --- هندلر برای پیام‌های جدید در کانال (برای ذخیره گیف روزانه) ---
# ... (این تابع بدون تغییر می‌ماند) ...
async def channel_post_handler(update: Update, context: CallbackContext) -> None:
    message = update.channel_post 

    if not message or message.chat.id != CHANNEL_ID:
        return

    message_time_tehran = message.date.astimezone(TEHRAN_TZ)
    current_time_tehran = datetime.datetime.now(TEHRAN_TZ)

    if (message_time_tehran.date() == current_time_tehran.date() and
        message_time_tehran.hour == 0 and
        message_time_tehran.minute >= 0 and message_time_tehran.minute <= 1):
        
        file_id_to_save = None
        if message.animation: 
            file_id_to_save = message.animation.file_id
        elif message.video: 
            file_id_to_save = message.video.file_id

        if file_id_to_save:
            existing_gif_info = await load_gif_info() 
            if existing_gif_info is None: 
                await save_gif_info(file_id_to_save, message.message_id)
                print(f"New media from channel saved at {message_time_tehran.strftime('%H:%M')}.")
            else:
                print(f"GIF already saved for today ({existing_gif_info[0]}). Skipping new save.")
        else:
            print(f"Message was within the time range, but neither GIF nor video: {message_time_tehran.strftime('%H:%M')}")
    else:
        print(f"Message from channel, but outside the specified time range: {message_time_tehran.strftime('%H:%M')}")

# --- هندلر برای پاسخ به دستور "امروز چندمه؟" در گروه‌ها ---
# ... (این تابع بدون تغییر می‌ماند) ...
async def group_message_handler(update: Update, context: CallbackContext) -> None:
    message = update.message

    if not message or message.chat.type not in ["group", "supergroup"]:
        print("Command received outside of a group.") 
        return

    if message.text:
        print(f"Received text (raw): {message.text}")
        print(f"Type of received text: {type(message.text)}")

    if message.text and ("امروز چندمه" in message.text or "امروز چه روزیه" in message.text):
        print(f"Command '{message.text}' received in group {message.chat.title}.")
        stored_gif_info = await load_gif_info() 

        if stored_gif_info:
            file_id, message_id_to_forward = stored_gif_info
            try:
                await context.bot.forward_message(
                    chat_id=message.chat.id,         
                    from_chat_id=CHANNEL_ID,         
                    message_id=message_id_to_forward 
                )
                print(f"Original GIF from channel forwarded to group {message.chat.title}.")
            except Exception as e:
                print(f"Error forwarding original GIF (Message ID: {message_id_to_forward}): {e}. Sending fallback GIF.")
                await context.bot.send_animation(
                    chat_id=message.chat.id,
                    animation=FALLBACK_GIF_FILE_ID,
                    caption="متاسفانه گیف امروز پیدا نشد یا قابل فوروارد نبود، این گیف پیش‌فرض است."
                )
        else:
            print("No GIF saved for today in Redis. Sending fallback GIF.")
            await context.bot.send_animation(
                chat_id=message.chat.id,
                animation=FALLBACK_GIF_FILE_ID,
                caption="امروز گیفی در بازه 00:00 تا 00:01 در کانال پیدا نشد، این گیف پیش‌فرض است."
            )
    else:
        print(f"Irrelevant text message received: '{message.text}'")


# --- Setup Flask application for Webhook ---
app = Flask(__name__)

# Webhook entry point
@app.route("/api/bot", methods=["POST"])
async def telegram_webhook():
    # این خطوط رو تغییر دادیم تا application فقط یک بار ساخته بشه
    global application # برای دسترسی به متغیر گلوبال application
    if application is None: # اگر هنوز ساخته نشده، بسازش
        if TOKEN:
            try:
                application = Application.builder().token(TOKEN).build()
                application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post_handler))
                application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, group_message_handler))
                print("Telegram Application initialized and handlers added (on first request).")
            except Exception as e:
                print(f"Error initializing Telegram Application on first request: {e}")
                return jsonify({"status": "error", "message": "Bot initialization failed"}), 500
        else:
            print("Error: TELEGRAM_BOT_TOKEN not set. Cannot initialize Telegram Application.")
            return jsonify({"status": "error", "message": "Bot token missing"}), 500

    try:
        req_body = request.get_json(force=True)
        update = Update.de_json(req_body, application.bot)
        await application.process_update(update)
        print("Update processed successfully.")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error processing Webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

