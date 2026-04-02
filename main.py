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
    version="1.1.0"
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
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, follow_redirects=True)
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Shahar topilmadi.")
        except Exception:
            raise HTTPException(status_code=500, detail="Tizimga ulanishda xatolik.")
            
    soup = BeautifulSoup(response.text, 'html.parser')
    
    def safe_text(element):
        return element.text.strip() if element else ""

    def extract_detail(elements, index):
        if len(elements) > index:
            parts = elements[index].text.split(': ')
            return parts[1].strip() if len(parts) > 1 else elements[index].text.strip()
        return ""
        
    try:
        city_name = safe_text(soup.find('h2'))
        if not city_name:
            raise HTTPException(status_code=404, detail="Ma'lumot topilmadi.")
            
        current_day = safe_text(soup.find('div', class_='current-day'))
        
        current_forecast = soup.find('div', class_='current-forecast')
        temp_day = ""
        temp_night = ""
        if current_forecast:
            temp_day = safe_text(current_forecast.find('strong'))
            spans = current_forecast.find_all('span')
            if len(spans) > 2:
                temp_night = safe_text(spans[2])
                
        description = safe_text(soup.find('div', class_='current-forecast-desc'))
        
        details_col1 = soup.select('.current-forecast-details .col-1 p')
        humidity = extract_detail(details_col1, 0)
        wind = extract_detail(details_col1, 1)
        pressure = extract_detail(details_col1, 2)
        
        details_col2 = soup.select('.current-forecast-details .col-2 p')
        moon = extract_detail(details_col2, 0)
        sunrise = extract_detail(details_col2, 1)
        sunset = extract_detail(details_col2, 2)
        
        time_of_day_data = []
        times_div = soup.find('div', class_='current-forecast-day')
        if times_div:
            cols = times_div.find_all('div', recursive=False)
            for col in cols:
                time_name = safe_text(col.find('p', class_='time-of-day'))
                time_temp = safe_text(col.find('p', class_='forecast'))
                time_of_day_data.append({"vaqt": time_name, "harorat": time_temp})
                
        weekly_forecast = []
        table_rows = soup.select('.weather-table tbody tr')
        for row in table_rows[1:]:
            day_cell = row.find('td', class_='weather-row-day')
            day_full_text = day_cell.get_text(" ", strip=True) if day_cell else ""
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
        raise HTTPException(status_code=500, detail=f"Xatolik: {str(e)}")

# Frontend uchun endpoint
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API endpoint
@app.get("/api/weather/{city}")
async def get_weather(city: str):
    return await fetch_weather_data(city.lower())
