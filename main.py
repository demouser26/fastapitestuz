from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup
import uvicorn

# FastAPI ilovasini yaratish
app = FastAPI(
    title="Obhavo.uz API",
    description="Obhavo.uz saytidan ob-havo ma'lumotlarini parsing qiluvchi norasmiy API",
    version="1.0.0"
)

# CORS sozlamalari (Istalgan front-end dan so'rov yuborishga ruxsat berish uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def fetch_weather_data(city: str) -> dict:
    """
    Berilgan shahar uchun obhavo.uz saytidan ma'lumotlarni yuklab olish va parsing qilish.
    """
    url = f"https://obhavo.uz/{city}"
    
    # Asinxron so'rov yuborish
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        
        # Agar sahifa topilmasa (masalan noto'g'ri shahar nomi)
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Shahar topilmadi. Iltimos, shahar nomini to'g'ri kiriting (masalan: tashkent, navoi, samarkand).")
            
    # BeautifulSoup yordamida HTML ni tahlil qilish
    soup = BeautifulSoup(response.text, 'html.parser')
    
    try:
        # 1. Asosiy ma'lumotlar
        city_name = soup.find('h2').text.strip()
        current_day = soup.find('div', class_='current-day').text.strip()
        
        # 2. Bugungi harorat
        current_forecast = soup.find('div', class_='current-forecast')
        temp_day = current_forecast.find('strong').text.strip()
        temp_night = current_forecast.find_all('span')[2].text.strip()
        description = soup.find('div', class_='current-forecast-desc').text.strip()
        
        # 3. Qo'shimcha tafsilotlar (Namlik, shamol, bosim)
        details_col1 = soup.select('.current-forecast-details .col-1 p')
        humidity = details_col1[0].text.split(': ')[1] if len(details_col1) > 0 else ""
        wind = details_col1[1].text.split(': ')[1] if len(details_col1) > 1 else ""
        pressure = details_col1[2].text.split(': ')[1] if len(details_col1) > 2 else ""
        
        # Quyosh va oy ma'lumotlari
        details_col2 = soup.select('.current-forecast-details .col-2 p')
        moon = details_col2[0].text.split(': ')[1] if len(details_col2) > 0 else ""
        sunrise = details_col2[1].text.split(': ')[1] if len(details_col2) > 1 else ""
        sunset = details_col2[2].text.split(': ')[1] if len(details_col2) > 2 else ""
        
        # 4. Kun qismlari bo'yicha harorat (Tong, Kun, Oqshom)
        time_of_day_data = []
        times_div = soup.find('div', class_='current-forecast-day')
        if times_div:
            cols = times_div.find_all('div', recursive=False)
            for col in cols:
                time_name = col.find('p', class_='time-of-day').text.strip()
                time_temp = col.find('p', class_='forecast').text.strip()
                time_of_day_data.append({
                    "vaqt": time_name,
                    "harorat": time_temp
                })
                
        # 5. Haftalik ma'lumot (Kunlik)
        weekly_forecast = []
        table_rows = soup.select('.weather-table tbody tr')
        
        # Birinchi qator <th> sarlavhalar, shuning uchun uni tashlab o'tamiz (index 1 dan boshlaymiz)
        for row in table_rows[1:]:
            # Kun nomi va sanasi (masalan: "Ertaga 3 aprel")
            day_cell = row.find('td', class_='weather-row-day')
            day_full_text = day_cell.get_text(" ", strip=True) if day_cell else ""
            
            # Harorat
            forecast_cell = row.find('td', class_='weather-row-forecast')
            day_t = forecast_cell.find('span', class_='forecast-day').text.strip() if forecast_cell else ""
            night_t = forecast_cell.find('span', class_='forecast-night').text.strip() if forecast_cell else ""
            
            # Tavsif
            desc_cell = row.find('td', class_='weather-row-desc')
            day_desc = desc_cell.text.strip() if desc_cell else ""
            
            # Yog'ingarchilik ehtimoli
            pop_cell = row.find('td', class_='weather-row-pop')
            precipitation = pop_cell.text.strip() if pop_cell else ""
            
            weekly_forecast.append({
                "sana": day_full_text,
                "harorat_kunduzi": day_t,
                "harorat_kechasi": night_t,
                "tavsif": day_desc,
                "yogingarchilik": precipitation
            })
            
        # Barcha ma'lumotlarni yig'ib qaytarish
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
        # Sahifa tuzilishi o'zgargan bo'lsa yoki boshqa xatolik yuz bersa
        raise HTTPException(status_code=500, detail=f"Ma'lumotlarni o'qishda xatolik yuz berdi: {str(e)}")

# Asosiy sahifa - API qanday ishlashini ko'rsatadi
@app.get("/", tags=["Asosiy"])
async def root():
    return {
        "xabar": "Obhavo.uz API ga xush kelibsiz!",
        "qollanma": "Ob-havo ma'lumotlarini olish uchun /api/weather/{shahar_nomi} manziliga murojaat qiling.",
        "misollar": [
            "/api/weather/tashkent",
            "/api/weather/navoi",
            "/api/weather/samarkand"
        ]
    }

# Ma'lum shahar uchun ob-havoni olish endpointi
@app.get("/api/weather/{city}", tags=["Ob-havo"])
async def get_weather(city: str):
    """
    Kiritilgan shahar nomi bo'yicha joriy va haftalik ob-havo ma'lumotlarini qaytaradi.
    Shahar nomi lotin harflarida va kichik yozilishi kerak (masalan: andijan, bukhara, navoi).
    """
    data = await fetch_weather_data(city.lower())
    return data
