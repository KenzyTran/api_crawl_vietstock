#!/bin/bash

# Script deploy Stock Events API cho Amazon Linux (EC2)

echo "=== STOCK EVENTS API DEPLOYMENT FOR AMAZON LINUX ==="

# Kiểm tra OS
if ! grep -q "Amazon Linux" /etc/os-release; then
    echo "WARNING: Script này được thiết kế cho Amazon Linux"
fi

# Cập nhật system
echo "Cập nhật system packages..."
sudo yum update -y

# Cài đặt Python và development tools
echo "Cài đặt Python và development tools..."
sudo yum install -y python3 python3-pip python3-devel gcc gcc-c++ make

# Cài đặt các dependencies cho Playwright
echo "Cài đặt dependencies cho Playwright..."
sudo yum install -y \
    glibc-devel \
    libX11-devel \
    libXcomposite-devel \
    libXcursor-devel \
    libXdamage-devel \
    libXext-devel \
    libXfixes-devel \
    libXi-devel \
    libXrandr-devel \
    libXrender-devel \
    libXss-devel \
    libXtst-devel \
    libxcb-devel \
    mesa-libgbm-devel \
    nss-devel \
    atk-devel \
    at-spi2-atk-devel \
    gtk3-devel \
    cups-devel \
    libdrm-devel \
    libxkbcommon-devel \
    alsa-lib-devel

# Tạo thư mục project
PROJECT_DIR="/home/$(whoami)/stock-events-api"
echo "Tạo thư mục project: $PROJECT_DIR"
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Copy files từ thư mục hiện tại
echo "Copy files..."
cp ../api_crawl_vietstock/app.py .
cp ../api_crawl_vietstock/requirements.txt .

# Tạo virtual environment
echo "Tạo virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Cài đặt Python packages
echo "Cài đặt Python packages..."
pip install --upgrade pip
pip install Flask==2.3.3 beautifulsoup4==4.12.2 requests==2.31.0

# Cài đặt Playwright riêng với các options đặc biệt cho Amazon Linux
echo "Cài đặt Playwright..."
pip install playwright==1.40.0

# Cài đặt browser với fallback dependencies
echo "Cài đặt Playwright browsers..."
export PLAYWRIGHT_BROWSERS_PATH=$PROJECT_DIR/browsers
playwright install chromium

# Nếu playwright install thất bại, cài đặt dependencies thủ công
if [ $? -ne 0 ]; then
    echo "Playwright install thất bại, cài đặt dependencies thủ công..."
    
    # Download chromium manually
    mkdir -p $PROJECT_DIR/browsers/chromium
    cd $PROJECT_DIR/browsers/chromium
    
    # Tạo script wrapper để chạy mà không cần system dependencies
    cat > $PROJECT_DIR/run_headless.py << 'EOF'
import os
import sys
sys.path.insert(0, '/home/ec2-user/stock-events-api/venv/lib/python3.9/site-packages')

from playwright.sync_api import sync_playwright
import subprocess

def check_dependencies():
    """Check và cài đặt các dependencies cần thiết"""
    try:
        # Set environment variables for headless mode
        os.environ['DISPLAY'] = ':99'
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/home/ec2-user/stock-events-api/browsers'
        
        # Test playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ])
            browser.close()
        print("Playwright test successful!")
        return True
    except Exception as e:
        print(f"Playwright test failed: {e}")
        return False

if __name__ == "__main__":
    check_dependencies()
EOF

    cd $PROJECT_DIR
fi

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
Environment=DISPLAY=:99
Environment=PLAYWRIGHT_BROWSERS_PATH=$PROJECT_DIR/browsers
ExecStart=$PROJECT_DIR/venv/bin/python app.py
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Cập nhật app.py để có thể handle lỗi playwright
cat > $PROJECT_DIR/app_wrapper.py << 'EOF'
#!/usr/bin/env python3
import os
import sys

# Set environment variables
os.environ['DISPLAY'] = ':99'
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/home/ec2-user/stock-events-api/browsers'

# Import và chạy app chính
try:
    from app import app
    if __name__ == '__main__':
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port, debug=False)
except Exception as e:
    print(f"Error starting app: {e}")
    sys.exit(1)
EOF

# Update systemd service to use wrapper
sudo sed -i 's|app.py|app_wrapper.py|g' /etc/systemd/system/stock-events-api.service

# Reload systemd và start service
echo "Khởi động service..."
sudo systemctl daemon-reload
sudo systemctl enable stock-events-api

# Test service trước khi start
echo "Testing service..."
source venv/bin/activate
python3 -c "
try:
    from playwright.sync_api import sync_playwright
    print('Playwright import successful')
    
    # Test basic functionality
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage'
        ])
        print('Browser launch successful')
        browser.close()
        print('Browser close successful')
except Exception as e:
    print(f'Test failed: {e}')
    import traceback
    traceback.print_exc()
"

sudo systemctl start stock-events-api

# Check service status
sleep 3
echo "=== SERVICE STATUS ==="
sudo systemctl status stock-events-api --no-pager

# Cài đặt nginx (optional)
echo "Cài đặt Nginx (optional)..."
sudo yum install -y nginx

if [ $? -eq 0 ]; then
    # Tạo nginx config cho Amazon Linux
    sudo tee /etc/nginx/conf.d/stock-events-api.conf > /dev/null <<EOF
server {
    listen 80;
    server_name _;

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

    # Start nginx
    sudo systemctl enable nginx
    sudo systemctl start nginx
    
    echo "Nginx đã được cài đặt và cấu hình"
else
    echo "Nginx installation failed, API vẫn chạy trên port 8080"
fi

# Mở firewall cho AWS Security Groups
echo "=== FIREWALL CONFIGURATION ==="
echo "Lưu ý: Trên AWS EC2, bạn cần cấu hình Security Groups để mở các port:"
echo "- Port 8080 (API trực tiếp)"
echo "- Port 80 (nếu sử dụng Nginx)"

# Test API
echo "=== TESTING API ==="
sleep 5
echo "Testing API endpoint..."
curl -s http://localhost:8080/ || echo "API test failed"

echo ""
echo "=== DEPLOYMENT HOÀN THÀNH ==="
echo "API đang chạy tại:"
echo "  - Local: http://localhost:8080"
echo "  - External: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8080"
if systemctl is-active --quiet nginx; then
    echo "  - Nginx: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
fi
echo ""
echo "Các lệnh quản lý service:"
echo "  sudo systemctl status stock-events-api    # Kiểm tra trạng thái"
echo "  sudo systemctl restart stock-events-api   # Restart service"
echo "  sudo journalctl -f -u stock-events-api    # Xem logs"
echo "  sudo systemctl stop stock-events-api      # Stop service"
echo ""
echo "Kiểm tra logs nếu có lỗi:"
echo "  sudo journalctl -u stock-events-api -n 50"
EOF
