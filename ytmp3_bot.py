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

def clean_filename(title: str) -> str:
    if not title:
        return "youtube_audio"
    cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:100] if len(cleaned) > 100 else cleaned or "youtube_audio"


async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Send a YouTube link.\n"
        "Choose quality → bot will retry up to 3 times if something fails."
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
        [InlineKeyboardButton("High (best, ~12–20+ MB / 10 min)", callback_data="quality_high")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Choose quality:\n"
        "• Low → smallest, good for speech\n"
        "• Medium → best balance\n"
        "• High → maximum quality (may be large)",
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

    # We'll keep the URL a bit longer in case of retry
    # context.user_data['pending_url'] = url   # still keep it

    await query.edit_message_text(f"Downloading ({quality.replace('quality_', '').capitalize()}) … attempt 1/{MAX_RETRIES}")

    success = await download_and_send(query.message, url, quality, context, attempt=1)

    if not success:
        # Show retry button
        keyboard = [[InlineKeyboardButton("🔄 Try again", callback_data=f"retry_{quality}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Download or send failed.\n"
            "Temporary problem (network / YouTube / Telegram)?",
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

    attempt = 2  # first retry = attempt 2
    await query.edit_message_text(f"Retrying ({quality.capitalize()}) … attempt {attempt}/{MAX_RETRIES}")

    await download_and_send(query.message, url, f"quality_{quality}", context, attempt=attempt)


async def download_and_send(message, url: str, quality_data: str, context: CallbackContext, attempt: int = 1) -> bool:
    """Core download + send logic with retry support"""
    unique_id = uuid.uuid4().hex[:10]
    audio_path = f"temp_audio_{unique_id}.m4a"
    video_title = "YouTube Audio"

    try:
        if quality_data == "quality_low":
            fmt = 'bestaudio[abr<=64]/bestaudio[abr<=80]/bestaudio[ext=m4a]/bestaudio'
        elif quality_data == "quality_medium":
            fmt = 'bestaudio[abr<=128]/bestaudio[abr<=160]/bestaudio[ext=m4a]/bestaudio'
        else:
            fmt = 'bestaudio/best'

        ydl_opts = {
            'format': fmt,
            'outtmpl': audio_path,
            'quiet': False,
            'no_warnings': False,
            'continuedl': True,
            'retries': 10,
            'fragment_retries': 10,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'YouTube Audio')
            ydl.download([url])

        if not os.path.exists(audio_path):
            raise Exception("File missing after download")

        os.sync()

        file_size_bytes = os.path.getsize(audio_path)
        file_size_mb = file_size_bytes / (1024 * 1024)

        cleaned_title = clean_filename(video_title)
        safe_filename = f"{cleaned_title}.m4a"

        if file_size_mb <= MAX_SAFE_AUDIO_MB:
            await message.reply_audio(
                audio=open(audio_path, 'rb'),
                title=cleaned_title,
                performer="Downloaded via bot",
                filename=safe_filename
            )
        else:
            await message.reply_document(
                document=open(audio_path, 'rb'),
                caption=f"{cleaned_title} ({file_size_mb:.1f} MB)",
                filename=safe_filename
            )

        await message.reply_text(f"Success! Quality: {quality_data.replace('quality_', '').capitalize()}")
        return True

    except Exception as e:
        logger.error(f"Attempt {attempt} failed: {e}", exc_info=True)

        if attempt < MAX_RETRIES:
            await asyncio.sleep(3)  # small delay before retry
            next_attempt = attempt + 1
            await message.reply_text(
                f"Attempt {attempt} failed. Retrying ({next_attempt}/{MAX_RETRIES})…"
            )
            return await download_and_send(message, url, quality_data, context, attempt=next_attempt)
        else:
            await message.reply_text(
                "All retry attempts failed.\n"
                "Possible reasons: YouTube block, network issue, or file too large.\n"
                "Try again later or different link."
            )
            return False

    finally:
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except:
                pass


def main() -> None:
    TOKEN = "your-token-here"

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    application.add_handler(CallbackQueryHandler(
        button_callback,
        pattern="^quality_"
    ))
    application.add_handler(CallbackQueryHandler(
        retry_callback,
        pattern="^retry_"
    ))

    print("Bot starting...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
