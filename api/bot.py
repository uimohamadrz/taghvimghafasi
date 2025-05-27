import datetime
import os
import re
import pytz
import json
import redis.asyncio as redis # استفاده از redis.asyncio برای پشتیبانی از await/async

from flask import Flask, request, jsonify

# --- پیکربندی ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 

# آدرس اتصال به Redis: باید به عنوان متغیر محیطی در Vercel تنظیم شود.
# این معمولاً یک URL است که از ارائه‌دهنده Redis (مثلاً Upstash) دریافت می‌کنید.
REDIS_URL = os.getenv("REDIS_URL") 

# شناسه کانال مبدا
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1001234567890")) 

# File ID گیف پیش‌فرض
FALLBACK_GIF_FILE_ID = os.getenv("FALLBACK_GIF_FILE_ID", "BAACAgIAAxkBA...")

# منطقه زمانی تهران
TEHRAN_TZ = pytz.timezone('Asia/Tehran')

# --- اتصال به Redis (یک بار در شروع برنامه) ---
# این اتصال باید در سطح گلوبال تعریف شود تا در تمام توابع قابل دسترسی باشد.
# از pool_prefill برای افزایش کارایی در محیط Serverless استفاده می‌شود.
if REDIS_URL:
    redis_client = redis.from_url(REDIS_URL)
    print("Redis client initialized.")
else:
    redis_client = None
    print("Warning: REDIS_URL not set. Redis storage will not be available.")

# --- توابع برای ذخیره و بازیابی File ID گیف با Redis ---
async def save_gif_info(file_id: str, message_id: int):
    """File ID و Message ID گیف را در Redis ذخیره می‌کند."""
    if not redis_client:
        print("Error: Redis client is not initialized. Cannot save GIF info.")
        return

    key = datetime.date.today().isoformat() # کلید برای گیف امروز (مثال: "2023-10-27")
    value = json.dumps({"file_id": file_id, "message_id": message_id}) # ذخیره به صورت رشته JSON
    
    try:
        await redis_client.set(key, value)
        # می‌توانید یک TTL (زمان انقضا) هم برای کلید تنظیم کنید تا مثلاً بعد از چند روز حذف شود.
        # await redis_client.expire(key, 60 * 60 * 24 * 7) # مثال: انقضا بعد از 7 روز
        print(f"گیف با File ID: {file_id} و Message ID: {message_id} در Redis برای کلید {key} ذخیره شد.")
    except Exception as e:
        print(f"خطا در ذخیره در Redis: {e}")

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

# --- Telegram Bot Handlers ---
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
            await save_gif_info(file_id_to_save, message.message_id)
            print(f"New media saved from channel at {message_time_tehran.strftime('%H:%M')}.")
        else:
            print(f"Message was within the time range, but neither GIF nor video: {message_time_tehran.strftime('%H:%M')}")
    else:
        print(f"Message from channel, but outside the specified time range: {message_time_tehran.strftime('%H:%M')}")

async def group_message_handler(update: Update, context: CallbackContext) -> None:
    message = update.message

    if not message or message.chat.type not in ["group", "supergroup"]:
        print("Command received outside of a group.") 
        return

    if message.text and ("امروز چندمه" in message.text or "امروز چه روزیه" in message.text):
        print(f"Command '{message.text}' received in group {message.chat.title}.")
        stored_gif_info = await load_gif_info()

        if stored_gif_info:
            file_id, message_id_to_forward = stored_gif_info
            try:
                await context.bot.forward_message(
                    chat_id=message.chat_id,         
                    from_chat_id=CHANNEL_ID,         
                    message_id=message_id_to_forward 
                )
                print(f"Original GIF forwarded to group {message.chat.title}.")
            except Exception as e:
                print(f"Error forwarding original GIF (Message ID: {message_id_to_forward}): {e}. Sending fallback GIF.")
                await context.bot.send_animation(
                    chat_id=message.chat_id,
                    animation=FALLBACK_GIF_FILE_ID,
                    caption="متاسفانه گیف امروز پیدا نشد یا قابل فوروارد نبود، این گیف پیش‌فرض است."
                )
        else:
            print("No GIF saved for today. Sending fallback GIF.")
            await context.bot.send_animation(
                chat_id=message.chat_id,
                animation=FALLBACK_GIF_FILE_ID,
                caption="امروز گیفی در بازه 00:00 تا 00:01 در کانال پیدا نشد، این گیف پیش‌فرض است."
            )
    else:
        print(f"Irrelevant text message received: '{message.text}'")


# --- Setup Flask application for Webhook ---
app = Flask(__name__)

# Initialize the Telegram bot Application
application = Application.builder().token(TOKEN).build()
application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, channel_post_handler))
application.add_handler(MessageHandler(filters.TEXT & filters.GROUP, group_message_handler))

# Webhook entry point
@app.route("/", methods=["POST"])
async def telegram_webhook():
    if not application:
        print("Error: Bot Application not initialized.")
        return jsonify({"status": "Bot not initialized"}), 500

    try:
        req_body = request.get_json(force=True)
        update = Update.de_json(req_body, application.bot)
        await application.process_update(update)
        print("Update processed successfully.")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error processing Webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

