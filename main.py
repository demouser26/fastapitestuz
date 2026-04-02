from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def homepage():
    return {"status": "API muvaffaqiyatli ishlamoqda!"}

@app.get("/user")
async def user(fullname, age):
    return {
        "fullname": fullname,
        "age": age,
    }