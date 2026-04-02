from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
from bs4 import BeautifulSoup
import uvicorn
import os

# FastAPI ilovasini yaratish
app = FastAPI(
    title="Obhavo.uz API",
    description="Obhavo.uz saytidan ob-havo ma'lumotlarini parsing qiluvchi norasmiy API",
    version="1.1.1"
)

# CORS sozlamalari
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates sozlamalari
templates = Jinja2Templates(directory="templates")

async def fetch_weather_data(city: str) -> dict:
    """
    Berilgan shahar uchun obhavo.uz saytidan ma'lumotlarni yuklab olish va parsing qilish.
    """
    url = f"https://obhavo.uz/{city}"
    
    # User-Agent qo'shish sayt bloklamasligi uchun yordam beradi
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
        try:
            response = await client.get(url, follow_redirects=True)
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Shahar topilmadi yoki obhavo.uz xatosi.")
        except httpx.RequestError:
            raise HTTPException(status_code=503, detail="Obhavo.uz serveriga ulanib bo'lmadi.")
            
    soup = BeautifulSoup(response.text, 'html.parser')
    
    def safe_text(element):
        return element.text.strip() if element else ""

    def extract_detail(elements, index):
        if len(elements) > index:
            text = elements[index].text
            if ':' in text:
                parts = text.split(':', 1)
                return parts[1].strip()
            return text.strip()
        return ""
        
    try:
        city_name = safe_text(soup.find('h2'))
        if not city_name:
            # Agar h2 bo'lmasa, shahar topilmagan bo'lishi mumkin
            raise HTTPException(status_code=404, detail="Ma'lumot topilmadi.")
            
        current_day = safe_text(soup.find('div', class_='current-day'))
        
        # Bugungi haroratni olishni xavfsizroq qilish
        current_forecast = soup.find('div', class_='current-forecast')
        temp_day = ""
        temp_night = ""
        if current_forecast:
            temp_day = safe_text(current_forecast.find('strong'))
            # Kechki harorat odatda oxirgi span ichida bo'ladi
            spans = current_forecast.find_all('span')
            if spans:
                # Harorat yozilgan spanni qidirish (odatda oxirrog'ida)
                for s in reversed(spans):
                    if any(char.isdigit() for char in s.text):
                        temp_night = s.text.strip()
                        break
                
        description = safe_text(soup.find('div', class_='current-forecast-desc'))
        
        # Tafsilotlar
        details_col1 = soup.select('.current-forecast-details .col-1 p')
        humidity = extract_detail(details_col1, 0)
        wind = extract_detail(details_col1, 1)
        pressure = extract_detail(details_col1, 2)
        
        details_col2 = soup.select('.current-forecast-details .col-2 p')
        moon = extract_detail(details_col2, 0)
        sunrise = extract_detail(details_col2, 1)
        sunset = extract_detail(details_col2, 2)
        
        # Kun qismlari
        time_of_day_data = []
        times_div = soup.find('div', class_='current-forecast-day')
        if times_div:
            cols = times_div.find_all('div', recursive=False)
            for col in cols:
                time_name = safe_text(col.find('p', class_='time-of-day'))
                time_temp = safe_text(col.find('p', class_='forecast'))
                if time_name:
                    time_of_day_data.append({"vaqt": time_name, "harorat": time_temp})
                
        # Haftalik ob-havo
        weekly_forecast = []
        table_rows = soup.select('.weather-table tbody tr')
        if table_rows:
            # Sarlavha qatorini tashlab ketish uchun tekshiruv
            start_idx = 1 if len(table_rows) > 1 else 0
            for row in table_rows[start_idx:]:
                day_cell = row.find('td', class_='weather-row-day')
                if not day_cell: continue
                
                day_full_text = day_cell.get_text(" ", strip=True)
                
                forecast_cell = row.find('td', class_='weather-row-forecast')
                day_t = safe_text(forecast_cell.find('span', class_='forecast-day')) if forecast_cell else ""
                night_t = safe_text(forecast_cell.find('span', class_='forecast-night')) if forecast_cell else ""
                
                desc_cell = row.find('td', class_='weather-row-desc')
                day_desc = safe_text(desc_cell)
                
                pop_cell = row.find('td', class_='weather-row-pop')
                precipitation = safe_text(pop_cell)
                
                weekly_forecast.append({
                    "sana": day_full_text,
                    "harorat_kunduzi": day_t,
                    "harorat_kechasi": night_t,
                    "tavsif": day_desc,
                    "yogingarchilik": precipitation
                })
            
        return {
            "shahar": city_name,
            "sana": current_day,
            "bugungi_obhavo": {
                "harorat_kunduzi": temp_day,
                "harorat_kechasi": temp_night,
                "tavsif": description,
                "namlik": humidity,
                "shamol": wind,
                "bosim": pressure,
                "oy": moon,
                "quyosh_chiqishi": sunrise,
                "quyosh_botishi": sunset
            },
            "kun_qismlari": time_of_day_data,
            "haftalik_obhavo": weekly_forecast
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ma'lumotlarni tahlil qilishda xatolik: {str(e)}")

# Frontend uchun endpoint
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API endpoint
@app.get("/api/weather/{city}")
async def get_weather(city: str):
    return await fetch_weather_data(city.lower())
