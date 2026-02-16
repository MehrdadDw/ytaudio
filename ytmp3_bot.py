import os
import logging
import uuid
import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    CallbackContext
)
import yt_dlp

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MAX_SAFE_AUDIO_MB = 48.0
MAX_RETRIES = 3

# Absolute path to cookies file
COOKIES_PATH = '/root/ytmp3-bot/cookies.txt'


def clean_filename(title: str) -> str:
    if not title:
        return "youtube_audio"
    cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:100] if len(cleaned) > 100 else cleaned or "youtube_audio"


async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Send a YouTube link.\n"
        "Choose quality — the bot will retry up to 3 times if something fails."
    )


async def handle_link(update: Update, context: CallbackContext) -> None:
    text = update.message.text.strip()
    if not ('youtube.com' in text or 'youtu.be' in text):
        await update.message.reply_text("Please send a valid YouTube link.")
        return

    context.user_data['pending_url'] = text

    keyboard = [
        [
            InlineKeyboardButton("Low (~3–5 MB / 10 min)", callback_data="quality_low"),
            InlineKeyboardButton("Medium (~6–10 MB / 10 min)", callback_data="quality_medium"),
        ],
        [
            InlineKeyboardButton("High (best, ~12–20+ MB / 10 min)", callback_data="quality_high"),
            InlineKeyboardButton("Subtitles (.srt)", callback_data="quality_sub_en"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Choose an option:\n"
        "• Low → smallest size, good for speech\n"
        "• Medium → good balance\n"
        "• High → best quality (may be large)\n"
        "• Subtitles → English subtitles (.srt) if available",
        reply_markup=reply_markup
    )


async def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    quality = query.data
    url = context.user_data.get('pending_url')
    if not url:
        await query.edit_message_text("Link expired. Please send it again.")
        return

    await query.edit_message_text(f"Processing {quality.replace('quality_', '').capitalize()} …")

    if quality == "quality_sub_en":
        success = await download_and_send_subtitle(query.message, url, context)
    else:
        success = await download_and_send(query.message, url, quality, context, attempt=1)

    if not success:
        keyboard = [[InlineKeyboardButton("🔄 Try again", callback_data=f"retry_{quality}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Download or send failed.\n"
            "Temporary issue with YouTube, network, or Telegram?",
            reply_markup=reply_markup
        )


async def retry_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    _, quality = query.data.split("_", 1)
    url = context.user_data.get('pending_url')
    if not url:
        await query.edit_message_text("No link found. Send it again.")
        return

    attempt = 2
    await query.edit_message_text(f"Retrying {quality.capitalize()} … attempt {attempt}/{MAX_RETRIES}")

    if quality == "sub_en":
        success = await download_and_send_subtitle(query.message, url, context)
    else:
        success = await download_and_send(query.message, url, f"quality_{quality}", context, attempt=attempt)

    if not success:
        await query.edit_message_text("All retry attempts failed.")


async def download_and_send(message, url: str, quality_data: str, context: CallbackContext, attempt: int = 1) -> bool:
    unique_id = uuid.uuid4().hex[:10]
    audio_path = f"temp_audio_{unique_id}.%(ext)s"  # safer template

    try:
        # Prefer non-DASH http(s) streams when possible → often faster / less throttled
        if quality_data == "quality_low":
            fmt = 'bestaudio[ext=m4a][protocol^=http]/bestaudio[abr<=80][protocol^=http]/bestaudio[abr<=80]/bestaudio[ext=m4a]/bestaudio/best'
        elif quality_data == "quality_medium":
            fmt = 'bestaudio[ext=m4a][protocol^=http]/bestaudio[abr<=160][protocol^=http]/bestaudio[abr<=160]/bestaudio[ext=m4a]/bestaudio/best'
        else:  # high
            fmt = 'bestaudio[ext=m4a][protocol^=http]/bestaudio/best[protocol^=http]/bestaudio/best'

        ydl_opts = {
            'format': fmt,
            'outtmpl': audio_path,
            'quiet': False,
            'no_warnings': False,
            'continuedl': True,
            'retries': 10,
            'fragment_retries': 10,
            'noplaylist': True,
            'cookiefile': COOKIES_PATH,
            'sleep_requests': 3,
            'concurrent_fragment_downloads': 6,          # ← KEY CHANGE: download 6 fragments in parallel
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'YouTube Audio') or "YouTube Audio"
            logger.info(f"Selected format(s): {info.get('format_id', 'unknown')}")
            ydl.download([url])

        # yt-dlp might have chosen .webm or .m4a → find the actual file
        possible_exts = ['m4a', 'webm', 'opus', 'ogg']
        audio_file = None
        for ext in possible_exts:
            candidate = audio_path.replace('%(ext)s', ext)
            if os.path.exists(candidate):
                audio_file = candidate
                break

        if not audio_file:
            raise Exception("No audio file found after download")

        file_size_bytes = os.path.getsize(audio_file)
        file_size_mb = file_size_bytes / (1024 * 1024)

        cleaned_title = clean_filename(video_title)
        safe_filename = f"{cleaned_title}.m4a"   # we rename to .m4a even if opus/webm

        if file_size_mb <= MAX_SAFE_AUDIO_MB:
            await message.reply_audio(
                audio=open(audio_file, 'rb'),
                title=cleaned_title,
                performer="Downloaded via bot",
                filename=safe_filename
            )
        else:
            await message.reply_document(
                document=open(audio_file, 'rb'),
                caption=f"{cleaned_title} ({file_size_mb:.1f} MB)",
                filename=safe_filename
            )

        await message.reply_text(f"Success! Quality: {quality_data.replace('quality_', '').capitalize()}")
        return True

    except Exception as e:
        err_str = str(e).lower()
        logger.error(f"Attempt {attempt} failed: {e}", exc_info=True)

        if "sign in to confirm" in err_str or "not a bot" in err_str:
            await message.reply_text(
                "YouTube blocked the request (\"Sign in to confirm you’re not a bot\").\n"
                "Common on VPS/server IPs. Try again later or different link."
            )
        elif attempt < MAX_RETRIES:
            await asyncio.sleep(5)  # slightly longer backoff
            next_attempt = attempt + 1
            await message.reply_text(f"Attempt {attempt} failed. Retrying ({next_attempt}/{MAX_RETRIES})…")
            return await download_and_send(message, url, quality_data, context, attempt=next_attempt)
        else:
            await message.reply_text(
                "All retry attempts failed.\n"
                "Possible reasons: YouTube block, heavy throttling, network, or file too large.\n"
                "Try again later or different link."
            )
            return False

    finally:
        # Clean up all possible temp files
        for ext in ['m4a', 'webm', 'opus', 'part', 'f139', 'f251']:
            p = audio_path.replace('%(ext)s', ext)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass


# Subtitle function remains mostly unchanged (only added concurrent fragments)
async def download_and_send_subtitle(message, url: str, context: CallbackContext) -> bool:
    unique_id = uuid.uuid4().hex[:10]
    sub_path = f"temp_sub_{unique_id}.srt"
    video_title = "YouTube Video"

    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl_info:
            info = ydl_info.extract_info(url, download=False)
            video_title = info.get('title', 'YouTube Video') or video_title
            original_lang = info.get('language') or 'en'
            has_manual = bool(info.get('subtitles', {}))
            has_auto_orig = f"{original_lang}-orig" in info.get('automatic_captions', {})

        ydl_opts = {
            'skip_download': True,
            'writeautomaticsub': True,
            'writesubtitles': True,
            'convertsubs': 'srt',
            'subtitlesformat': 'srt/vtt/best',
            'outtmpl': sub_path[:-4],
            'quiet': False,
            'ignoreerrors': True,
            'sleep_subtitles': 5,
            'cookiefile': COOKIES_PATH,
            'sleep_requests': 3,
            'concurrent_fragment_downloads': 4,  # also helps subtitles sometimes
        }

        if has_auto_orig:
            ydl_opts['subtitleslangs'] = [f"{original_lang}-orig"]
            await message.reply_text("Downloading original auto-generated subtitles...")
        elif has_manual:
            ydl_opts['subtitleslangs'] = ['all']
            await message.reply_text("Downloading manual subtitles...")
        else:
            ydl_opts['subtitleslangs'] = ['en']
            await message.reply_text("No original/manual subtitles found. Trying English auto-generated...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        possible_files = [
            f for f in os.listdir('.') 
            if f.startswith(sub_path[:-8]) and f.endswith('.srt')
        ]

        if not possible_files:
            await message.reply_text("No subtitles (manual or auto) found for this video.")
            return False

        actual_sub_path = possible_files[0]
        os.rename(actual_sub_path, sub_path)

        cleaned_title = clean_filename(video_title)
        lang_note = " (original language - auto)" if "-orig" in actual_sub_path else ""
        safe_filename = f"{cleaned_title} - Subtitles{lang_note}.srt"

        await message.reply_document(
            document=open(sub_path, 'rb'),
            caption=f"Subtitles: {cleaned_title}{lang_note}\nFormat: SRT",
            filename=safe_filename
        )

        await message.reply_text("Subtitles sent!")
        return True

    except Exception as e:
        err_str = str(e).lower()
        logger.error(f"Subtitle error: {e}", exc_info=True)
        if "sign in to confirm" in err_str or "not a bot" in err_str:
            await message.reply_text(
                "YouTube blocked the subtitle request (\"Sign in to confirm...\").\n"
                "This happens on server/VPS IPs. Try again later."
            )
        elif "429" in err_str:
            await message.reply_text("YouTube is rate-limiting subtitle requests (429). Wait 10–60 minutes.")
        else:
            await message.reply_text("Failed to download subtitles. Try another link.")
        return False

    finally:
        paths = [sub_path]
        if 'actual_sub_path' in locals():
            paths.append(actual_sub_path)
        for p in paths:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass


def main() -> None:
    TOKEN = os.getenv("BOT_TOKEN")

    if not TOKEN:
        raise ValueError("Environment variable BOT_TOKEN is not set. Cannot start bot.")

    if len(TOKEN) < 35 or ':' not in TOKEN:
        raise ValueError("BOT_TOKEN looks invalid (too short or wrong format). Check your systemd service file.")

    logger.info("Starting bot with token from environment variable")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^quality_"))
    application.add_handler(CallbackQueryHandler(retry_callback, pattern="^retry_"))

    print("Bot starting...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
