#!/usr/bin/env python3
import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
import argparse
import sys

day_of_week_translation = {
    "Monday": "thứ hai",
    "Tuesday": "thứ ba", 
    "Wednesday": "thứ tư",
    "Thursday": "thứ năm",
    "Friday": "thứ sáu",
    "Saturday": "thứ bảy",
    "Sunday": "chủ nhật"
}

def parse_date_input(date_str):
    """
    Chuyển đổi chuỗi ngày đầu vào thành datetime object
    Hỗ trợ các format: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
    """
    formats = ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Định dạng ngày không hợp lệ: {date_str}. Vui lòng sử dụng: YYYY-MM-DD, DD/MM/YYYY hoặc DD-MM-YYYY")

def get_target_date(target_input=None):
    """
    Lấy ngày mục tiêu dựa trên đầu vào
    target_input có thể là: None (hôm nay), "tomorrow", "yesterday", hoặc ngày cụ thể
    """
    now = datetime.now()
    
    if target_input is None or target_input.lower() == "today":
        return now
    elif target_input.lower() == "tomorrow":
        if now.weekday() == 4:  # Thứ 6
            return now + timedelta(days=3)  # Thứ 2 tuần sau
        else:
            return now + timedelta(days=1)
    elif target_input.lower() == "yesterday":
        if now.weekday() == 0:  # Thứ 2
            return now - timedelta(days=3)  # Thứ 6 tuần trước
        else:
            return now - timedelta(days=1)
    else:
        # Coi như là ngày cụ thể
        return parse_date_input(target_input)

def scrape_stock_events(target_date):
    """
    Scrape dữ liệu sự kiện chứng khoán từ VietStock
    Trả về dictionary chứa thông tin chi tiết
    """
    date_str = target_date.strftime("%Y-%m-%d")
    formatted_date = target_date.strftime("%d/%m/%Y")
    current_day_of_week_english = target_date.strftime("%A")
    current_day_of_week = day_of_week_translation.get(current_day_of_week_english, current_day_of_week_english)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            url = f"https://finance.vietstock.vn/lich-su-kien.htm?page=1&tab=1&from={date_str}&to={date_str}&exchange=-1"
            page.goto(url, timeout=60000)
            page.wait_for_timeout(25000)  
            page_source = page.content()
            browser.close()

        soup = BeautifulSoup(page_source, 'html.parser')
        table = soup.find('table', id='event-content')
        
        if not table:
            return {
                'success': False,
                'message': f"Không tìm thấy bảng sự kiện cho ngày {formatted_date}",
                'date': formatted_date,
                'day_of_week': current_day_of_week,
                'data': []
            }
        
        tbody = table.find('tbody')
        if not tbody:
            return {
                'success': False,
                'message': f"Không tìm thấy dữ liệu trong bảng cho ngày {formatted_date}",
                'date': formatted_date,
                'day_of_week': current_day_of_week,
                'data': []
            }
        
        rows = tbody.find_all('tr')
        
        events_data = []
        stock_codes = []
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 7:
                event_info = {
                    'stt': cols[0].get_text(strip=True),
                    'ma_ck': cols[1].get_text(strip=True),
                    'san': cols[2].get_text(strip=True),
                    'ngay_gdkhq': cols[3].get_text(strip=True),
                    'noi_dung': cols[6].get_text(strip=True).split(',', 1)[-1].strip(),
                    'co_tuc': cols[7].get_text(strip=True).split('bằng', 1)[-1].strip().capitalize()
                }
                events_data.append(event_info)
                stock_codes.append(event_info['ma_ck'])
        
        return {
            'success': True,
            'message': f"Tìm thấy {len(events_data)} sự kiện cho ngày {formatted_date}",
            'date': formatted_date,
            'day_of_week': current_day_of_week,
            'total_events': len(events_data),
            'stock_codes': stock_codes,
            'data': events_data
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Lỗi khi scrape dữ liệu: {str(e)}",
            'date': formatted_date,
            'day_of_week': current_day_of_week,
            'data': []
        }

def format_table_output(result_data):
    """
    Format dữ liệu thành bảng đẹp mắt để hiển thị
    """
    if not result_data['success'] or not result_data['data']:
        return f"Không có dữ liệu cho ngày {result_data['date']} ({result_data['day_of_week']})"
    
    # Tạo header bảng
    headers = ["STT", "Mã CK", "Sàn", "Ngày GDKHQ", "Nội dung", "Cổ tức"]
    table_data = [headers]
    
    # Thêm dữ liệu
    for event in result_data['data']:
        table_data.append([
            event['stt'],
            event['ma_ck'],
            event['san'],
            event['ngay_gdkhq'],
            event['noi_dung'],
            event['co_tuc']
        ])
    
    # Tính độ rộng cột
    col_widths = [max(len(str(row[i])) for row in table_data) for i in range(len(headers))]
    
    # Tạo bảng
    table_str = f"Danh sách sự kiện ngày {result_data['date']} ({result_data['day_of_week']}):\n"
    table_str += "=" * (sum(col_widths) + len(headers) * 3 - 1) + "\n"
    
    for i, row in enumerate(table_data):
        table_str += " | ".join(f"{row[j]:<{col_widths[j]}}" for j in range(len(headers))) + "\n"
        if i == 0:  # Sau header
            table_str += "=" * (sum(col_widths) + len(headers) * 3 - 1) + "\n"
    
    table_str += f"\nTổng cộng: {result_data['total_events']} sự kiện"
    table_str += f"\nMã CK: {', '.join(result_data['stock_codes'])}"
    
    return table_str

def save_to_file(result_data, output_path=None):
    """
    Lưu kết quả vào file JSON
    """
    if output_path is None:
        target_date = datetime.strptime(result_data['date'], '%d/%m/%Y')
        output_path = f"stock_events_{target_date.strftime('%Y%m%d')}.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    
    return output_path

def main():
    parser = argparse.ArgumentParser(description='Scrape stock events from VietStock')
    parser.add_argument('--date', '-d', type=str, 
                       help='Ngày cần lấy dữ liệu (YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, today, tomorrow, yesterday)')
    parser.add_argument('--output', '-o', type=str, 
                       help='File đầu ra (JSON)')
    parser.add_argument('--format', '-f', choices=['table', 'json', 'both'], default='table',
                       help='Định dạng output: table (bảng), json, hoặc both')
    parser.add_argument('--save', '-s', action='store_true',
                       help='Lưu kết quả vào file JSON')
    
    args = parser.parse_args()
    
    try:
        # Lấy ngày mục tiêu
        target_date = get_target_date(args.date)
        
        # Scrape dữ liệu
        print(f"Đang lấy dữ liệu cho ngày {target_date.strftime('%d/%m/%Y')}...", file=sys.stderr)
        result = scrape_stock_events(target_date)
        
        # Lưu file nếu được yêu cầu
        if args.save or args.output:
            file_path = save_to_file(result, args.output)
            print(f"Đã lưu kết quả vào: {file_path}", file=sys.stderr)
        
        # Output theo format được chọn
        if args.format in ['table', 'both']:
            print(format_table_output(result))
        
        if args.format in ['json', 'both']:
            if args.format == 'both':
                print("\n" + "="*50 + " JSON OUTPUT " + "="*50)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # Exit code
        sys.exit(0 if result['success'] else 1)
        
    except Exception as e:
        print(f"Lỗi: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
