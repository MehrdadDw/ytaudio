#!/bin/bash
# =============================================
# One-click installer for ytmp3-bot
# Run with: bash <(curl -s https://raw.githubusercontent.com/MehrdadDw/ytaudio/main/install.sh)
# =============================================

set -e

echo -e "\033[1;36m══════════════════════════════════════════════\033[0m"
echo -e "\033[1;32m   YouTube Audio Telegram Bot - Installer\033[0m"
echo -e "\033[1;36m══════════════════════════════════════════════\033[0m"

# Check root
if [[ $EUID -ne 0 ]]; then
   echo -e "\033[1;31m❌ Please run as root: sudo bash <(curl -s ...)\033[0m"
   exit 1
fi

# Ask for token
echo -e "\n📌 Enter your Telegram Bot Token (from @BotFather):"
read -r -p "👉 BOT_TOKEN = " BOT_TOKEN

if [[ -z "$BOT_TOKEN" ]]; then
    echo -e "\033[1;31m❌ Token cannot be empty!\033[0m"
    exit 1
fi

INSTALL_DIR="/root/ytmp3-bot"
SERVICE_NAME="yt-audio-bot"

echo -e "\n📦 Installing system dependencies (ffmpeg + Python venv)..."
apt-get update -qq
apt-get install -y python3 python3-venv python3-pip ffmpeg curl git

echo -e "\n📁 Creating directory $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

echo -e "\n⬇️  Downloading files from your repo..."
curl -s -o ytmp3_bot.py https://raw.githubusercontent.com/MehrdadDw/ytaudio/main/ytmp3_bot.py
curl -s -o yt-audio-bot.service https://raw.githubusercontent.com/MehrdadDw/ytaudio/main/yt-audio-bot.service

echo -e "\n🐍 Creating virtual environment + installing Python packages..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install "python-telegram-bot[rate-limiter,http2]" yt-dlp --upgrade
deactivate

echo -e "\n⚙️  Creating systemd service with your token..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=YouTube Audio Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=${INSTALL_DIR}
Environment=BOT_TOKEN=${BOT_TOKEN}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/ytmp3_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo -e "\n🚀 Enabling and starting the bot..."
systemctl daemon-reload
systemctl enable --now ${SERVICE_NAME}

echo -e "\n✅ Installation completed successfully!"
echo -e "\n📋 Next steps:"
echo -e "   1. Place your cookies.txt in ${INSTALL_DIR}/cookies.txt"
echo -e "      (use Chrome extension 'Get cookies.txt LOCALLY' while logged into YouTube)"
echo -e "   2. Check status:   \033[1;33msystemctl status ${SERVICE_NAME}\033[0m"
echo -e "   3. Live logs:      \033[1;33mjournalctl -u ${SERVICE_NAME} -f\033[0m"
echo -e "   4. Restart bot:    \033[1;33msystemctl restart ${SERVICE_NAME}\033[0m"

echo -e "\n🎉 Your bot is now running! Send /start to it on Telegram."
