from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyotp
import time
import os
import traceback
import json
from kiteconnect import KiteConnect
from urllib.parse import urlparse, parse_qs
from dotenv import dotenv_values, set_key

from app.config.settings import get_settings
from app.services.logger import get_logger
from app.brokers.zerodha import ZerodhaBroker
#from app.main import app


router = APIRouter()
logger = get_logger(__name__)
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../../templates"))
env_file_path = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "../../.env"))

BROKER_CHOICES = [
    ("zerodha", "Zerodha"),
    ("angel", "Angel Broking"),
    ("fyers", "Fyers"),
    ("custom", "Custom (Simulated)"),
    # Add more brokers as needed
]

def update_env_access_token(token: str, env_file_path: str = ".env"):
    """
    Adds or updates ZERODHA_ACCESS_TOKEN in the .env file
    """
    if not os.path.exists(env_file_path):
        raise FileNotFoundError(f"{env_file_path} does not exist")

    set_key(env_file_path, "ZERODHA_ACCESS_TOKEN", token)

@router.get("/main/settings", response_class=HTMLResponse)
async def get_main_settings(request: Request):
    # Optionally: Populate current settings from DB or config file
    return templates.TemplateResponse("_settings.html", {
        "request": request,
        "broker_choices": BROKER_CHOICES,
        "current": {}  # Your logic here for current configuration
    })

@router.post("/settings/auto-login")
async def auto_login_broker(request: Request, broker: str = Form(...)):
    settings = get_settings()

    # Currently we only support Zerodha
    if broker.lower() != "zerodha":
        return JSONResponse({
            "success": False,
            "error": f"Auto-login is only implemented for 'zerodha'. Got: '{broker}'"
        }, status_code=400)

    # Load credentials from settings
    api_key = settings.ZERODHA_API_KEY
    user_id = settings.ZERODHA_USER_ID
    password = settings.ZERODHA_PWD
    totp_secret = settings.ZERODHA_TOTP  # should be settings.TOTP if you add it
    driver_path = settings.chromedriver_path

    logger.info(f"Chromedrive path: {driver_path}")

    if not all([api_key, user_id, password, totp_secret, driver_path]):
        return JSONResponse({
            "success": False,
            "error": "One or more required credentials are missing from settings.py."
        }, status_code=400)

    try:
        logger.info("Inside the try")
        chrome_options = webdriver.ChromeOptions()
        #chrome_options.add_argument("--headless=new")
        #chrome_options.add_argument("--no-sandbox")
        #chrome_options.add_argument("--disable-dev-shm-usage")

        # ChromeDriver must point to full path inside the folder
        #driver_path = os.path.join(chromedriver_path, "chromedriver.exe")  # for Windows

        if not os.path.exists(driver_path):
            return JSONResponse({
                "success": False,
                "error": f"chromedriver not found at {driver_path}"
            }, status_code=404)

        driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)

        kite_url = f"https://kite.trade/connect/login?api_key={api_key}&v=3"
        driver.get(kite_url)
        logger.info(f"Kite URL: {kite_url}")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "userid"))
        ).send_keys(user_id)
        logger.info("User ID processed")
        driver.find_element(By.ID, "password").send_keys(password)
        logger.info("Password processed")
        driver.find_element(By.XPATH, '//button[@type="submit"]').click()
        logger.info("Submit processed")

        # Use TOTP to get 2FA code
        totp_code = pyotp.TOTP(totp_secret).now()

        time.sleep(5)
        logger.info(f"totp fetched: {totp_code}")
        
        driver.find_element(By.ID, "userid").send_keys(totp_code)
        #driver.find_element(By.XPATH, '//button[@type="submit"]').click()
        logger.info("almost done")
        time.sleep(5)
        redirected_url = driver.current_url
        logger.info(f"redirected URL: {redirected_url}")
        driver.quit()

        # Parse token
        parsed = urlparse(redirected_url)
        params = parse_qs(parsed.query)
        status = params.get("status", [None])[0]
        token = params.get("request_token", [None])[0]

        if status == "success" and token:
            {
                "success": True,
                "request_token": token,
                "redirect_url": redirected_url
            }
        else:
            {
                "success": False,
                "error": "Login was not successful or request_token missing.",
                "redirect_url": redirected_url
            }

        kite = KiteConnect(api_key=settings.ZERODHA_API_KEY)
        try:
            session_data = kite.generate_session(
                token, api_secret=settings.ZERODHA_API_SECRET
            )
            access_token = session_data["access_token"]

            #update_env_access_token(access_token)
            # Update settings singleton if you want in-memory reference:
            settings.ZERODHA_ACCESS_TOKEN = access_token
            if hasattr(request.app.state, "controller"):
                broker = ZerodhaBroker()
                request.app.state.controller.inject_broker(broker)
                logger.info("logged in to Zerodha")


            return {
                "success": True,
                #"access_token": access_token,
                #"user_id": session_data["userid"]
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Access token exchange failed: {e}"
            }


    except Exception as e:
        try:
            driver.quit()
        except:
            pass
        return JSONResponse({
            "success": False,
            "error": f"Selenium error: {e}"
        }, status_code=500)
    
    