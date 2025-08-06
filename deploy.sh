#!/bin/bash

# Script deploy Stock Events API lên Ubuntu/Linux server

echo "=== STOCK EVENTS API DEPLOYMENT ==="

# Cập nhật system
echo "Cập nhật system packages..."
sudo apt update && sudo apt upgrade -y

# Cài đặt Python và pip nếu chưa có
echo "Cài đặt Python và pip..."
sudo apt install -y python3 python3-pip python3-venv

# Tạo thư mục project
PROJECT_DIR="/home/$(whoami)/stock-events-api"
echo "Tạo thư mục project: $PROJECT_DIR"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Tạo virtual environment
echo "Tạo virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Copy files vào project directory (giả sử bạn đã có sẵn)
# Hoặc clone từ git repository
echo "Cài đặt Python packages..."
pip install --upgrade pip
pip install Flask==2.3.3 playwright==1.40.0 beautifulsoup4==4.12.2 requests==2.31.0

# Cài đặt Playwright browsers
echo "Cài đặt Playwright browsers..."
playwright install chromium
playwright install-deps chromium

# Tạo systemd service file
echo "Tạo systemd service..."
sudo tee /etc/systemd/system/stock-events-api.service > /dev/null <<EOF
[Unit]
Description=Stock Events API
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
Environment=PORT=8080
ExecStart=$PROJECT_DIR/venv/bin/python app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd và start service
echo "Khởi động service..."
sudo systemctl daemon-reload
sudo systemctl enable stock-events-api
sudo systemctl start stock-events-api

# Cài đặt nginx làm reverse proxy (tùy chọn)
echo "Cài đặt Nginx..."
sudo apt install -y nginx

# Tạo nginx config
sudo tee /etc/nginx/sites-available/stock-events-api > /dev/null <<EOF
server {
    listen 80;
    server_name _;  # Thay bằng domain của bạn

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
EOF

# Enable nginx site
sudo ln -sf /etc/nginx/sites-available/stock-events-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Mở firewall (nếu cần)
echo "Cấu hình firewall..."
sudo ufw allow 80
sudo ufw allow 8080

echo "=== DEPLOYMENT HOÀN THÀNH ==="
echo "API đang chạy tại:"
echo "  - Cổng 8080: http://your-server-ip:8080"
echo "  - Cổng 80 (qua Nginx): http://your-server-ip"
echo ""
echo "Các lệnh quản lý service:"
echo "  sudo systemctl status stock-events-api    # Kiểm tra trạng thái"
echo "  sudo systemctl restart stock-events-api   # Restart service"
echo "  sudo systemctl logs -f stock-events-api   # Xem logs"
