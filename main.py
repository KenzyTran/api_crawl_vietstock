from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import json
from typing import List, Optional
import uvicorn

app = FastAPI(
    title="VietStock Events API",
    description="API để lấy dữ liệu sự kiện chứng khoán từ VietStock",
    version="1.0.0"
)

# Models
class EventData(BaseModel):
    stt: str
    ma_ck: str
    san: str
    ngay_gdkhq: str
    noi_dung: str
    co_tuc: str

class EventResponse(BaseModel):
    date: str
    day_of_week: str
    total_events: int
    codes: List[str]
    events: List[EventData]
    table_formatted: str

class ErrorResponse(BaseModel):
    error: str
    message: str

day_of_week_translation = {
    "Monday": "thứ hai",
    "Tuesday": "thứ ba", 
    "Wednesday": "thứ tư",
    "Thursday": "thứ năm",
    "Friday": "thứ sáu",
    "Saturday": "thứ bảy",
    "Sunday": "chủ nhật"
}

def parse_date_string(date_str: str) -> datetime:
    """Parse date string in format YYYY-MM-DD or DD/MM/YYYY"""
    try:
        if '-' in date_str:
            return datetime.strptime(date_str, "%Y-%m-%d")
        elif '/' in date_str:
            return datetime.strptime(date_str, "%d/%m/%Y")
        else:
            raise ValueError("Invalid date format")
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail="Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY"
        )

def scrape_vietstock_events(target_date: datetime) -> tuple:
    """Scrape events from VietStock for given date"""
    date_str = target_date.strftime("%Y-%m-%d")
    formatted_date = target_date.strftime("%d/%m/%Y")
    current_day_of_week_english = target_date.strftime("%A")
    current_day_of_week = day_of_week_translation.get(
        current_day_of_week_english, 
        current_day_of_week_english
    )
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            url = f"https://finance.vietstock.vn/lich-su-kien.htm?page=1&tab=1&from={date_str}&to={date_str}&exchange=-1"
            page.goto(url, timeout=60000)
            page.wait_for_timeout(25000)
            page_source = page.content()
            browser.close()
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error scraping data: {str(e)}"
        )

    soup = BeautifulSoup(page_source, 'html.parser')
    table = soup.find('table', id='event-content')
    if not table:
        return [], f"Không tìm thấy dữ liệu cho ngày {formatted_date}", current_day_of_week, []
    
    tbody = table.find('tbody')
    if not tbody:
        return [], f"Không tìm thấy dữ liệu cho ngày {formatted_date}", current_day_of_week, []
    
    rows = tbody.find_all('tr')
    
    # Xây dựng dữ liệu
    events_data = []
    codes = []
    table_data = []
    headers = ["STT", "Mã CK", "Sàn", "Ngày GDKHQ", "Nội dung", "Cổ tức"]
    table_data.append(headers)
    
    for row in rows:
        cols = row.find_all('td')
        if len(cols) >= 7:
            stt = cols[0].get_text(strip=True)
            ma_ck = cols[1].get_text(strip=True)
            san = cols[2].get_text(strip=True)
            ngay_gdkhq = cols[3].get_text(strip=True)
            noi_dung = cols[6].get_text(strip=True).split(',', 1)[-1].strip()
            co_tuc = cols[7].get_text(strip=True).split('bằng', 1)[-1].strip().capitalize()
            
            # Tạo object EventData
            event = EventData(
                stt=stt,
                ma_ck=ma_ck,
                san=san,
                ngay_gdkhq=ngay_gdkhq,
                noi_dung=noi_dung,
                co_tuc=co_tuc
            )
            events_data.append(event)
            codes.append(ma_ck)
            table_data.append([stt, ma_ck, san, ngay_gdkhq, noi_dung, co_tuc])
    
    # Tạo bảng formatted
    if table_data:
        col_widths = [max(len(str(row[i])) for row in table_data) for i in range(len(headers))]
        table_str = ""
        for row in table_data:
            table_str += "\n" + " | ".join(f"{row[i]:<{col_widths[i]}}" for i in range(len(headers)))
    else:
        table_str = "\nKhông có sự kiện nào"
    
    return events_data, formatted_date, current_day_of_week, codes, table_str

@app.get("/", summary="API Info")
async def root():
    return {
        "message": "VietStock Events API",
        "version": "1.0.0",
        "endpoints": {
            "/events/{date}": "Get events for specific date (YYYY-MM-DD or DD/MM/YYYY)",
            "/events/today": "Get events for today",
            "/events/tomorrow": "Get events for tomorrow (next business day)",
            "/docs": "API documentation"
        }
    }

@app.get("/events/today", response_model=EventResponse, summary="Get today's events")
async def get_today_events():
    """Lấy sự kiện của ngày hôm nay"""
    target_date = datetime.now()
    return await get_events_by_date_obj(target_date)

@app.get("/events/tomorrow", response_model=EventResponse, summary="Get tomorrow's events")
async def get_tomorrow_events():
    """Lấy sự kiện của ngày mai (bỏ qua cuối tuần)"""
    now = datetime.now()
    # Nếu hôm nay là thứ 6 thì ngày mai là thứ 2 (thêm 3 ngày)
    if now.weekday() == 4:
        target_date = now + timedelta(days=3)
    else:
        target_date = now + timedelta(days=1)
    return await get_events_by_date_obj(target_date)

@app.get("/events/{date}", response_model=EventResponse, summary="Get events by date")
async def get_events_by_date(date: str):
    """
    Lấy sự kiện theo ngày cụ thể
    
    Args:
        date: Ngày cần lấy (format: YYYY-MM-DD hoặc DD/MM/YYYY)
    
    Returns:
        EventResponse: Dữ liệu sự kiện của ngày đó
    """
    target_date = parse_date_string(date)
    return await get_events_by_date_obj(target_date)

async def get_events_by_date_obj(target_date: datetime) -> EventResponse:
    """Helper function to get events by datetime object"""
    try:
        events_data, formatted_date, day_of_week, codes, table_str = scrape_vietstock_events(target_date)
        
        return EventResponse(
            date=formatted_date,
            day_of_week=day_of_week,
            total_events=len(events_data),
            codes=codes,
            events=events_data,
            table_formatted=table_str
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health", summary="Health check")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )
