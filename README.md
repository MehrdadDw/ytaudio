
YouTube Audio Downloader Telegram Bot

A lightweight Telegram bot that lets users send a YouTube link, choose audio quality (Low / Medium / High), or request English subtitles (.srt), and receive the file.

Downloads audio in m4a (no mp3 re-encoding)
Keeps files under ~48 MB where possible (Telegram audio limit)
Sends larger files as documents
Retries up to 3 times on failure
Uses clean video titles for filenames and metadata
Handles common YouTube blocks with cookies

Features
Inline buttons: Low (~48–80 kbps), Medium (~96–160 kbps), High (best available, often 160+ kbps opus/m4a)
Subtitles option (.srt – manual or auto-generated English)
Concurrent fragment downloads → much faster on throttled VPS/server IPs
Automatic temp file cleanup
Basic error messages for YouTube blocks / rate-limits

Requirements
Python 3.10+ (3.12 recommended)
yt-dlp (keep updated: pip install -U yt-dlp)
python-telegram-bot v21+ (pip install python-telegram-bot --upgrade)
python-dotenv (for loading BOT_TOKEN from .env or env var)
ffmpeg (required by yt-dlp for merging / format conversion)
Deno (strongly recommended – fixes JS challenge warnings and improves reliability)

Ubuntu/Debian example installation commands:
sudo apt update
sudo apt install python3 python3-venv ffmpeg -y

Deno (very important in 2026 for smooth YouTube extraction):
curl -fsSL https://deno.land/install.sh | sh
Add to PATH permanently:
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
Verify:
deno --version

Setup
1. Clone / place files in /root/ytmp3-bot/ (or your preferred dir)
2. Create .env (or set in systemd service):
BOT_TOKEN=123456:AAF1b2C3d4e5f6G7h8I9j0K-lMnOpQrStUv
Never commit .env or hard-code the token!

3. Prepare cookies.txt (critical in 2026 – see section below)

4. Update systemd service file (yt-audio-bot.service):

[Unit]
Description=YouTube Audio Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=/root/ytmp3-bot
Environment="BOT_TOKEN=your-real-token-here"
ExecStart=/usr/bin/python3 /root/ytmp3-bot/ytmp3_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

5. Activate:
sudo systemctl daemon-reload
sudo systemctl enable yt-audio-bot.service
sudo systemctl restart yt-audio-bot.service

Live logs:
journalctl -u yt-audio-bot.service -f

About cookies.txt – Important in 2026

YouTube increasingly rate-limits / blocks datacenter/VPS IPs with the "Sign in to confirm you’re not a bot" error – even on normal videos.

Your bot uses cookiefile: COOKIES_PATH to include login cookies → this tells YouTube "this is a real logged-in user" and often bypasses the prompt + reduces throttling.

Why you need fresh cookies periodically
Cookies expire (sessions ~months, but YouTube invalidates suspicious ones faster)
Old/invalid cookies → still get "sign in" error
Using cookies from a real residential browser session helps a lot

How to create/update cookies.txt (recommended method 2026)

Option A – Easiest & cleanest (use yt-dlp itself)
On a machine with Chrome/Firefox where you're logged into YouTube:
yt-dlp --cookies-from-browser chrome --cookies /path/to/cookies.txt "https://www.youtube.com"
Or Firefox:
yt-dlp --cookies-from-browser firefox --cookies /path/to/cookies.txt "https://www.youtube.com"
Then copy this cookies.txt to your server (/root/ytmp3-bot/cookies.txt)

Option B – Chrome/Edge extension (very reliable)
1. Install extension: "Get cookies.txt LOCALLY" (Chrome Web Store – make sure it's the one that exports Netscape format)
2. Log in to youtube.com in that browser
3. Open YouTube → click extension → Export → choose Netscape HTTP Cookie File format
4. Save as cookies.txt
5. Upload to server + chmod 600 cookies.txt

Security notes
cookies.txt contains sensitive session data – treat like a password
Use chmod 600 cookies.txt (only root readable)
Never commit to git or share
Use an alternate/secondary Google account (not your main one) – in case YouTube flags heavy usage
Refresh every 1–3 months or when you see "sign in" errors again

If still blocked/throttled even with cookies
Add proxy (residential preferred)
Use --extractor-args "youtube:player_client=android" in yt-dlp options
Increase concurrent_fragment_downloads (already set to 6 in your script)

Troubleshooting
Bot stuck "Processing …" for ages? → Check logs: slow fragment downloads are common on VPS. Cookies + concurrent fragments usually fix it.
"Sign in to confirm…" → Update cookies.txt
No audio sent? → File >48 MB? Check if sent as document.
Update everything regularly: pip install -U yt-dlp python-telegram-bot

Enjoy your bot!
