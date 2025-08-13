from fastapi import APIRouter, Form
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
# ... (other imports)

from app.config.settings import get_settings

router = APIRouter()

@router.post("/settings/auto-login")
async def auto_login_broker(broker: str = Form(...)):
    settings = get_settings()
    driver_path = settings.chromedriver_path

    print(f"Chromedriver path used in endpoint: {driver_path}")  # <--- Add this!

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    try:
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get("https://www.google.com")
        print(driver.title)
        driver.quit()
        return {"success": True, "msg": "It worked in FastAPI too!"}
    except Exception as e:
        return {"success": False, "error": str(e)}
