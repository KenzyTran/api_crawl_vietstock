#!/bin/bash

# Deploy script cho VietStock API trên Ubuntu

echo "🚀 Bắt đầu deploy VietStock API..."

# Update system
echo "📦 Cập nhật hệ thống..."
sudo apt update && sudo apt upgrade -y

# Install Python 3.9+ và pip nếu chưa có
echo "🐍 Cài đặt Python và pip..."
sudo apt install python3 python3-pip python3-venv -y

# Install system dependencies for Playwright
echo "🌐 Cài đặt dependencies cho Playwright..."
sudo apt install -y \
    libnss3-dev \
    libatk-bridge2.0-dev \
    libdrm-dev \
    libxcomposite-dev \
    libxdamage-dev \
    libxrandr-dev \
    libgbm-dev \
    libxss-dev \
    libasound2-dev

# Tạo thư mục dự án
echo "📁 Tạo thư mục dự án..."
PROJECT_DIR="/opt/vietstock-api"
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER $PROJECT_DIR
cd $PROJECT_DIR

# Tạo virtual environment
echo "🔧 Tạo virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "📚 Cài đặt dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🌍 Cài đặt Playwright browsers..."
playwright install chromium
playwright install-deps chromium

# Tạo systemd service
echo "⚙️ Tạo systemd service..."
sudo tee /etc/systemd/system/vietstock-api.service > /dev/null <<EOF
[Unit]
Description=VietStock API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd và enable service
echo "🔄 Reload systemd và enable service..."
sudo systemctl daemon-reload
sudo systemctl enable vietstock-api.service

# Start service
echo "▶️ Khởi động service..."
sudo systemctl start vietstock-api.service

# Check status
echo "📊 Kiểm tra trạng thái service..."
sudo systemctl status vietstock-api.service --no-pager

# Setup firewall (mở port 8000)
echo "🔥 Cấu hình firewall..."
sudo ufw allow 8000/tcp

# Tạo log rotation
echo "📝 Tạo log rotation..."
sudo tee /etc/logrotate.d/vietstock-api > /dev/null <<EOF
/var/log/vietstock-api/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    create 644 $USER $USER
}
EOF

# Tạo thư mục log
sudo mkdir -p /var/log/vietstock-api
sudo chown $USER:$USER /var/log/vietstock-api

echo "✅ Deploy hoàn thành!"
echo ""
echo "🌍 API đang chạy tại: http://$(curl -s ifconfig.me):8000"
echo "📖 API Documentation: http://$(curl -s ifconfig.me):8000/docs"
echo ""
echo "🔧 Các lệnh quản lý service:"
echo "  - Khởi động: sudo systemctl start vietstock-api"
echo "  - Dừng: sudo systemctl stop vietstock-api" 
echo "  - Restart: sudo systemctl restart vietstock-api"
echo "  - Xem logs: sudo journalctl -u vietstock-api -f"
echo "  - Xem status: sudo systemctl status vietstock-api"
