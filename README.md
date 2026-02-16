# YouTube Audio Downloader Telegram Bot

A simple Telegram bot that lets users send a YouTube link → choose audio quality (Low / Medium / High) → and receive the audio file (m4a format).

- Tries to keep files under ~48 MB (Telegram bot audio/document limit)
- If file is larger → sends it as a downloadable document
- Uses medium bitrate preference by default to avoid hitting size limits too often
- Clean video titles used for filename and audio metadata

## Features

- Inline quality selection buttons (Low ~48–64 kbps, Medium ~96–128 kbps, High best)
- Direct m4a download (no mp3 re-encoding)
- Automatic fallback to document if >48 MB
- Basic error handling & cleanup

## Requirements

- Python 3.10+
- ffmpeg (for yt-dlp audio processing)
- Deno (strongly recommended – removes yt-dlp JS runtime warning)

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install python3 python3-venv ffmpeg -y

# Deno (very important for reliable YouTube extraction)
curl -fsSL https://deno.land/install.sh | sh
export PATH="$HOME/.deno/bin:$PATH"
# add the line above to ~/.bashrc or ~/.zshrc
```


```bash
sudo systemctl daemon-reload
sudo systemctl enable yt-audio-bot.service
sudo systemctl start yt-audio-bot.service

# Check logs live
journalctl -u yt-audio-bot -f
```
