# api/bot.py

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CallbackContext
import datetime
import os
import re
import pytz
import json
import redis.asyncio as redis 

from flask import Flask, request, jsonify 

# --- پیکربندی ---
# توکن ربات: همچنان توصیه می‌شود به عنوان متغیر محیطی تنظیم شود.
# اگرچه می‌توانید مقدار پیش‌فرض را برای تست محلی نگه دارید، اما برای Production توصیه نمی‌شود.
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 

# آدرس اتصال به Redis: باید به عنوان متغیر محیطی در Vercel تنظیم شود.
REDIS_URL = os.getenv("REDIS_URL") 

# شناسه کانال مبدا (taghvimghafasi): باید به عنوان متغیر محیطی در Vercel تنظیم شود.
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1001886988651")) 

# File ID گیف پیش‌فرض: باید به عنوان متغیر محیطی در Vercel تنظیم شود.
FALLBACK_GIF_FILE_ID = os.getenv("FALLBACK_GIF_FILE_ID", "AAMCBAADGQECA_NgaDYn12DAX8o5DZdL_PjivicNsPQAApMYAAISe7lRlJGAmFWt294BAAdtAAM2BA")

# منطقه زمانی تهران
TEHRAN_TZ = pytz.timezone('Asia/Tehran')

# --- اتصال به Redis (یک بار در شروع برنامه - گلوبال) ---
# این بخش یک بار وقتی ماژول بارگذاری می‌شود اجرا می‌شود
redis_client = None 
if REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL)
        print("Redis client initialized.")
    except Exception as e:
        print(f"Error initializing Redis client globally: {e}")
else:
    print("Warning: REDIS_URL not set. Redis storage will not be available.")

# --- Telegram Application (مقداردهی اولیه گلوبال و فقط یک بار) ---
# این بخش هم یک بار وقتی ماژول بارگذاری می‌شود اجرا می‌شود
application = None 
if TOKEN: 
    try:
        application = Application.builder().token(TOKEN).build()
        print("Telegram Application builder called.") # لاگ برای دیباگ
    except Exception as e:
        print(f"Error building Telegram Application globally: {e}")
        # اگر در اینجا خطا بدهد، application = None باقی می‌ماند
else:
    print("Error: TELEGRAM_BOT_TOKEN not set. Telegram Application cannot be built globally.")


# --- توابع برای ذخیره و بازیابی File ID و Message ID گیف با Redis ---
# (این توابع بدون تغییر می‌مانند)
async def save_gif_info(file_id: str, message_id: int):
    """File ID و Message ID گیف را در Redis ذخیره می‌کند."""
    if not redis_client:
        print("Error: Redis client is not initialized. Cannot save GIF info.")
        return

    key = datetime.date.today().isoformat() 
    value = json.dumps({"file_id": file_id, "message_id": message_id}) 
    
    try:
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
            gif_data = json.loads(value) 
            print(f"اطلاعات گیف از Redis برای کلید {key} بارگذاری شد.")
            return gif_data.get("file_id"), gif_data.get("message_id")
        
        print(f"هیچ اطلاعات گیف معتبری در Redis برای کلید {key} امروز پیدا نشد.")
        return None
    except Exception as e:
        print(f"Error loading from Redis: {e}")
    return None

# --- هندلر برای پیام‌های جدید در کانال (برای ذخیره گیف روزانه) ---
# (این تابع بدون تغییر می‌ماند)
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
# (این تابع بدون تغییر می‌ماند)
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
    # اینجا application از سطح گلوبال استفاده می‌شود
    if application is None:
        print("Error: Telegram Application was not initialized globally. Check TOKEN environment variable.")
        return jsonify({"status": "error", "message": "Bot application not initialized"}), 500

    try:
        req_body = request.get_json(force=True)
        update = Update.de_json(req_body, application.bot)
        await application.process_update(update)
        print("Update processed successfully.")
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        print(f"Error processing Webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

