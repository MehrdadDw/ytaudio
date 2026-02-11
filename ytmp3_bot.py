import os
import logging
import uuid
import re
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

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MAX_SAFE_AUDIO_MB = 48.0

def clean_filename(title: str) -> str:
    if not title:
        return "youtube_audio"
    cleaned = re.sub(r'[<>:"/\\|?*]', '', title)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if len(cleaned) > 100:
        cleaned = cleaned[:97] + "..."
    return cleaned or "youtube_audio"

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(
        "Send me a YouTube link.\n"
        "I'll offer Low / Medium / High audio quality options.\n"
        "Sizes are approximate — long videos may exceed 50 MB limit."
    )

async def handle_link(update: Update, context: CallbackContext) -> None:
    text = update.message.text.strip()
    if not ('youtube.com' in text or 'youtu.be' in text):
        await update.message.reply_text("Please send a valid YouTube link.")
        return

    # Store URL
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
        "Choose audio quality:\n\n"
        "• Low → smallest files, good for speech/podcasts\n"
        "• Medium → balanced quality/size, most videos stay under limit\n"
        "• High → maximum sound quality, may be sent as file if >50 MB",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    quality = query.data
    url = context.user_data.get('pending_url')
    if not url:
        await query.edit_message_text("Session expired. Send the link again.")
        return

    del context.user_data['pending_url']

    await query.edit_message_text(f"Downloading in {quality.replace('quality_', '').capitalize()} quality…")

    unique_id = uuid.uuid4().hex[:10]
    audio_path = f"temp_audio_{unique_id}.m4a"

    video_title = "YouTube Audio"

    try:
        if quality == "quality_low":
            fmt = 'bestaudio[abr<=64]/bestaudio[abr<=80]/bestaudio[ext=m4a]/bestaudio'
        elif quality == "quality_medium":
            fmt = 'bestaudio[abr<=128]/bestaudio[abr<=160]/bestaudio[ext=m4a]/bestaudio'
        else:  # high
            fmt = 'bestaudio/best'

        ydl_opts = {
            'format': fmt,
            'outtmpl': audio_path,
            'quiet': False,
            'no_warnings': False,
            'continuedl': True,
            'retries': 20,
            'fragment_retries': 20,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_title = info.get('title', 'YouTube Audio')
            ydl.download([url])

        if not os.path.exists(audio_path):
            raise Exception("File not found after download")

        os.sync()

        file_size_bytes = os.path.getsize(audio_path)
        file_size_mb = file_size_bytes / (1024 * 1024)

        cleaned_title = clean_filename(video_title)
        safe_filename = f"{cleaned_title}.m4a"

        if file_size_mb <= MAX_SAFE_AUDIO_MB:
            await query.message.reply_audio(
                audio=open(audio_path, 'rb'),
                title=cleaned_title,
                performer="Downloaded via bot",
                filename=safe_filename
            )
        else:
            await query.message.reply_document(
                document=open(audio_path, 'rb'),
                caption=f"{cleaned_title} ({file_size_mb:.1f} MB) – too large for audio player",
                filename=safe_filename
            )

        await query.message.reply_text(f"Done! Quality: {quality.replace('quality_', '').capitalize()}")

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await query.message.reply_text(f"Failed: {str(e)[:150] or 'Unknown error'}")

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
    application.add_handler(CallbackQueryHandler(button_callback))

    print("Bot starting...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
