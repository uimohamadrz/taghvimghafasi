import os
import time
import subprocess
import schedule
import telebot
import pytz
import jdatetime
from datetime import datetime

# --- CONFIGURATION ---
# Get sensitive data from Environment Variables (set in docker-compose)
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID', '@taghvimghafasi')
ADMIN_ID = os.getenv('ADMIN_ID')  # Pass as string from env, convert to int below

SCHEDULE_TIME = os.getenv('SCHEDULE_TIME', '20:30')


if not BOT_TOKEN:
    raise ValueError("Error: BOT_TOKEN is missing from environment variables.")

bot = telebot.TeleBot(BOT_TOKEN)

# --- PATH SETUP ---
# This gets the directory where main.py is located inside the container
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, 'fonts')
GIFS_DIR = os.path.join(BASE_DIR, 'gifs')
FONT_PATH = os.path.join(FONTS_DIR, 'IRANSans(FaNum)_Bold.ttf')
OUTPUT_MP4 = os.path.join(BASE_DIR, 'output.mp4')


def notify_admin(message: str):
    """Send logs to admin telegram."""
    if not ADMIN_ID:
        print(f"Admin ID not set. Log: {message}")
        return
    try:
        bot.send_message(int(ADMIN_ID), message)
    except Exception as e:
        print(f"Failed to notify admin: {e}")


def create_and_send_video():
    print(f"--- Job Started at {datetime.now()} UTC ---")

    # 1. Calculate Date (Tehran Time)
    tehran_tz = pytz.timezone('Asia/Tehran')
    now = datetime.now().astimezone(tehran_tz)

    today_jalali_dt = jdatetime.datetime.fromgregorian(datetime=now)
    today_jalali = today_jalali_dt.date()
    weekday_index = today_jalali_dt.weekday()

    weekdays = ['shanbe', '1shanbe', '2shanbe', '3shanbe', '4shanbe', '5shanbe', 'jome']
    weekday_name = weekdays[weekday_index]

    # Path to specific GIF
    gif_path = os.path.join(GIFS_DIR, f"{weekday_name}.gif")

    if not os.path.exists(gif_path):
        notify_admin(f"❌ Error: GIF not found at {gif_path}")
        return

    # Text Generation
    month_names_fa = {
        1: 'فروردین', 2: 'اردیبهشت', 3: 'خرداد', 4: 'تیر',
        5: 'مرداد', 6: 'شهریور', 7: 'مهر', 8: 'آبان',
        9: 'آذر', 10: 'دی', 11: 'بهمن', 12: 'اسفند'
    }
    text = f"امروز {today_jalali.day} {month_names_fa[today_jalali.month]}ه؟"

    # 2. FFmpeg Command
    input_width = 720
    input_height = 312

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", gif_path,
        "-vf", (
            f"fps=30,"
            f"drawtext=text='{text}':fontfile={FONT_PATH}:fontcolor=white:"
            f"fontsize=60:x=(w-text_w)/2:y=h-80:borderw=6:bordercolor=black,"
            f"scale={input_width}:{input_height}:flags=lanczos"
        ),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "23", "-an",
        "-movflags", "+faststart",
        OUTPUT_MP4
    ]

    notify_admin(f"🎬 Starting render for {today_jalali} ({weekday_name})")

    try:
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("Video rendered successfully.")
    except subprocess.CalledProcessError as e:
        notify_admin(f"❌ FFmpeg Error:\n{e}")
        return

    # 3. Send to Telegram
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            with open(OUTPUT_MP4, 'rb') as video:
                bot.send_animation(CHANNEL_ID, video)

            notify_admin("✅ Video sent successfully.")
            print("Video sent.")
            break
        except Exception as e:
            print(f"Retry {attempt} failed: {e}")
            time.sleep(30)
            if attempt == max_retries:
                notify_admin(f"⛔ Failed to send video after {max_retries} attempts.")

    # 4. Cleanup
    if os.path.exists(OUTPUT_MP4):
        os.remove(OUTPUT_MP4)


# --- SCHEDULER ---
if __name__ == "__main__":
    print(f"🤖 Bot is running. Schedule set for: {SCHEDULE_TIME} UTC")
    notify_admin(f"🤖 Bot Container Started. Schedule: {SCHEDULE_TIME} UTC.")

    # Use the constant here
    schedule.every().day.at(SCHEDULE_TIME).do(create_and_send_video)

    while True:
        schedule.run_pending()
        time.sleep(60)