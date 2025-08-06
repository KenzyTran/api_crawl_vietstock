from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json

app = Flask(__name__)

day_of_week_translation = {
    "Monday": "thứ hai",
    "Tuesday": "thứ ba",
    "Wednesday": "thứ tư",
    "Thursday": "thứ năm",
    "Friday": "thứ sáu",
    "Saturday": "thứ bảy",
    "Sunday": "chủ nhật"
}

def get_target_date(target_type="tomorrow"):
    now = datetime.now()
    if target_type == "tomorrow":
        # Nếu hôm nay là thứ 6 thì ngày mai là thứ 2 (thêm 3 ngày)
        if now.weekday() == 4:
            target_date = now + timedelta(days=3)
        else:
            target_date = now + timedelta(days=1)
    elif target_type == "today":
        target_date = now
    else:
        raise ValueError("target_type không hợp lệ!")
    return target_date

def parse_date_string(date_str):
    """Parse date string từ nhiều format khác nhau"""
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Không thể parse ngày: {date_str}. Hỗ trợ format: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY")

def scrape_codes(target_date):
    try:
        date_str = target_date.strftime("%Y-%m-%d")
        formatted_date = target_date.strftime("%d/%m/%Y")
        current_day_of_week_english = target_date.strftime("%A")
        current_day_of_week = day_of_week_translation.get(current_day_of_week_english, current_day_of_week_english)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            url = f"https://finance.vietstock.vn/lich-su-kien.htm?page=1&tab=1&from={date_str}&to={date_str}&exchange=-1"
            page.goto(url, timeout=60000)
            page.wait_for_timeout(10000)  # Giảm thời gian chờ
            page_source = page.content()
            browser.close()

        soup = BeautifulSoup(page_source, 'html.parser')
        table = soup.find('table', id='event-content')
        if not table:
            return {
                'success': False,
                'message': f"Không tìm thấy bảng sự kiện cho ngày {formatted_date}",
                'data': []
            }
        
        tbody = table.find('tbody')
        if not tbody:
            return {
                'success': False,
                'message': f"Không tìm thấy dữ liệu trong bảng cho ngày {formatted_date}",
                'data': []
            }
        
        rows = tbody.find_all('tr')
        
        events_data = []
        codes = []
        
        for i, row in enumerate(rows):
            cols = row.find_all('td')
            if len(cols) >= 7:
                stt = i + 1
                ma_ck = cols[1].get_text(strip=True)
                san = cols[2].get_text(strip=True)
                ngay_gdkhq = cols[3].get_text(strip=True)
                noi_dung = cols[6].get_text(strip=True).split(',', 1)[-1].strip()
                su_kien = cols[7].get_text(strip=True).split('bằng', 1)[-1].strip().capitalize()
                
                event_info = {
                    'stt': stt,
                    'ma_ck': ma_ck,
                    'san': san,
                    'ngay_gdkhq': ngay_gdkhq,
                    'noi_dung': noi_dung,
                    'co_tuc': su_kien
                }
                events_data.append(event_info)
                codes.append(ma_ck)
        
        return {
            'success': True,
            'message': f"Lấy dữ liệu thành công cho ngày {formatted_date} ({current_day_of_week})",
            'date': formatted_date,
            'day_of_week': current_day_of_week,
            'total_events': len(events_data),
            'codes': codes,
            'events': events_data
        }
    
    except Exception as e:
        return {
            'success': False,
            'message': f"Lỗi khi lấy dữ liệu: {str(e)}",
            'data': []
        }

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': 'Stock Events API',
        'endpoints': {
            '/events': 'GET - Lấy sự kiện theo ngày',
            '/events/today': 'GET - Lấy sự kiện hôm nay',
            '/events/tomorrow': 'GET - Lấy sự kiện ngày mai'
        },
        'parameters': {
            'date': 'YYYY-MM-DD, DD/MM/YYYY, hoặc DD-MM-YYYY'
        }
    })

@app.route('/events', methods=['GET'])
def get_events():
    try:
        date_param = request.args.get('date')
        
        if not date_param:
            return jsonify({
                'error': 'Thiếu tham số date. Ví dụ: /events?date=2024-01-15'
            }), 400
        
        target_date = parse_date_string(date_param)
        result = scrape_codes(target_date)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except ValueError as e:
        return jsonify({
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'error': f'Lỗi server: {str(e)}'
        }), 500

@app.route('/events/today', methods=['GET'])
def get_today_events():
    try:
        target_date = get_target_date("today")
        result = scrape_codes(target_date)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Lỗi server: {str(e)}'
        }), 500

@app.route('/events/tomorrow', methods=['GET'])
def get_tomorrow_events():
    try:
        target_date = get_target_date("tomorrow")
        result = scrape_codes(target_date)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 404
            
    except Exception as e:
        return jsonify({
            'error': f'Lỗi server: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
