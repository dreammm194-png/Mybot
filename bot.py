import aiohttp
import logging
from typing import List, Dict
from bot.config import config

logger = logging.getLogger(__name__)

async def search_github(query: str) -> List[Dict]:
    url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page=5"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"token {config.GITHUB_TOKEN}"
    
    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("items", [])
                    if items and isinstance(items, list):
                        for item in items[:5]:
                            if not isinstance(item, dict):
                                continue
                            description = item.get("description")
                            desc_text = "Нет описания"
                            if description and isinstance(description, str):
                                desc_text = description[:100]
                            
                            results.append({
                                "name": item.get("full_name", "N/A"),
                                "stars": item.get("stargazers_count", 0),
                                "desc": desc_text,
                                "url": item.get("html_url", ""),
                                "lang": item.get("language", "N/A")
                            })
                else:
                    logger.warning(f"GitHub API вернул статус: {resp.status}")
    except Exception as e:
        logger.error(f"Ошибка в github_api.search_github: {e}")
    return results


import aiohttp
import logging
from typing import Dict, Optional
from bot.config import config

logger = logging.getLogger(__name__)

async def get_weather(city: str) -> Optional[Dict]:
    if not config.OPENWEATHER_API_KEY:
        logger.warning("OPENWEATHER_API_KEY не задан")
        return None
    
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={config.OPENWEATHER_API_KEY}&units=metric&lang=ru"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    if not isinstance(data, dict):
                        logger.error("API вернул не dict")
                        return None
                    
                    main_data = data.get("main", {})
                    weather_list = data.get("weather", [])
                    wind_data = data.get("wind", {})
                    
                    if not isinstance(main_data, dict):
                        main_data = {}
                    if not isinstance(weather_list, list) or len(weather_list) == 0:
                        weather_list = [{}]
                    if not isinstance(wind_data, dict):
                        wind_data = {}
                    
                    weather_first = weather_list[0] if weather_list else {}
                    if not isinstance(weather_first, dict):
                        weather_first = {}
                    
                    desc_raw = weather_first.get("description", "Нет данных")
                    description = desc_raw.capitalize() if isinstance(desc_raw, str) else "Нет данных"
                    
                    return {
                        "city": data.get("name", city),
                        "temp": main_data.get("temp", 0),
                        "feels": main_data.get("feels_like", 0),
                        "desc": description,
                        "humidity": main_data.get("humidity", 0),
                        "wind": wind_data.get("speed", 0)
                    }
                else:
                    logger.warning(f"Weather API вернул статус: {resp.status}")
    except Exception as e:
        logger.error(f"Ошибка в weather_api.get_weather: {e}")
    return None


import aiohttp
import logging
from bs4 import BeautifulSoup
from typing import List, Dict
import urllib.parse
import time

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9',
}

_cache: Dict[str, tuple] = {}
CACHE_TTL = 300

def _get_cache(key: str):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None

def _set_cache(key: str, data):
    _cache[key] = (data, time.time())

async def search_apkmirror(query: str) -> List[Dict]:
    cached = _get_cache(f"apk:{query}")
    if cached:
        return cached
    
    url = f"https://www.apkmirror.com/?post_type=app_release&searchtype=apk&s={urllib.parse.quote(query)}"
    results = []
    
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.warning(f"APKMirror вернул статус: {resp.status}")
                    return results
                html = await resp.text()
        
        soup = BeautifulSoup(html, 'lxml')
        rows = soup.find_all('div', class_='appRow')
        
        for row in rows[:8]:
            try:
                title_elem = row.find('a', class_='appRowTitle')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '')
                
                if link and isinstance(link, str) and not link.startswith('http'):
                    link = 'https://www.apkmirror.com' + link
                
                ver_elem = row.find('div', class_='appRowVersion')
                version = ver_elem.get_text(strip=True) if ver_elem else 'N/A'
                
                if title and link:
                    results.append({
                        'title': title,
                        'version': version,
                        'link': link
                    })
            except Exception as e:
                logger.error(f"Ошибка парсинга строки APKMirror: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Ошибка в apk_parser.search_apkmirror: {e}")
    
    _set_cache(f"apk:{query}", results)
    return results

async def search_trashbox(query: str) -> List[Dict]:
    cached = _get_cache(f"trash:{query}")
    if cached:
        return cached
    
    url = f"https://trashbox.ru/search?query={urllib.parse.quote(query)}"
    results = []
    
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.warning(f"Trashbox вернул статус: {resp.status}")
                    return results
                html = await resp.text()
        
        soup = BeautifulSoup(html, 'lxml')
        items = soup.find_all('div', class_='catalog_item')
        if not items:
            items = soup.find_all('li', class_='search-item')
        
        for item in items[:8]:
            try:
                title_elem = item.find('a', class_='name')
                if not title_elem:
                    title_elem = item.find('a', class_='search-link')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '')
                
                if link and isinstance(link, str) and not link.startswith('http'):
                    link = 'https://trashbox.ru' + link
                
                ver_elem = item.find('span', class_='version')
                if not ver_elem:
                    ver_elem = item.find('span', class_='app_ver')
                version = ver_elem.get_text(strip=True) if ver_elem else 'N/A'
                
                if title and link:
                    results.append({
                        'title': title,
                        'version': version,
                        'link': link
                    })
            except Exception as e:
                logger.error(f"Ошибка парсинга строки Trashbox: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Ошибка в apk_parser.search_trashbox: {e}")
    
    _set_cache(f"trash:{query}", results)
    return results


import os
import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class Config:
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    GITHUB_TOKEN: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    OPENWEATHER_API_KEY: str = field(default_factory=lambda: os.getenv("OPENWEATHER_API_KEY", ""))
    NEWS_API_KEY: str = field(default_factory=lambda: os.getenv("NEWS_API_KEY", ""))
    DEBUG: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")
    PORT: int = field(default_factory=lambda: int(os.getenv("PORT", "10000")))

config = Config()


from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🔍 GitHub"), KeyboardButton(text="📱 APKMirror")],
        [KeyboardButton(text="📁 Trashbox"), KeyboardButton(text="☀️ Погода")],
        [KeyboardButton(text="📰 Новости"), KeyboardButton(text="ℹ️ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.keyboards.reply_kb import get_main_keyboard, get_cancel_keyboard
from bot.utils.github_api import search_github
from bot.utils.weather_api import get_weather
from bot.utils.apk_parser import search_apkmirror, search_trashbox

logger = logging.getLogger(__name__)
router = Router()

class UserState(StatesGroup):
    waiting_github_query = State()
    waiting_apk_query = State()
    waiting_trashbox_query = State()
    waiting_weather_city = State()
    waiting_news_query = State()

def escape_markdown(text: str) -> str:
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in chars:
        text = text.replace(char, f'\\{char}')
    return text

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🤖 *Github Finder*\n\nПоиск репозиториев, APK, погоды и новостей.\n\nВыберите действие 👇",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    await message.answer(
        "🔍 GitHub — поиск репозиториев\n📱 APKMirror — поиск APK\n📁 Trashbox — софт для Android\n☀️ Погода — прогноз\n📰 Новости — в разработке",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "🔍 GitHub")
async def github_start(message: Message, state: FSMContext):
    await message.answer("🔎 Введите запрос:", reply_markup=get_cancel_keyboard())
    await state.set_state(UserState.waiting_github_query)

@router.message(UserState.waiting_github_query)
async def github_search(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return
    
    query = message.text if message.text else ""
    results = await search_github(query)
    
    if not results:
        await message.answer("Ничего не найдено.", reply_markup=get_main_keyboard())
    else:
        text = f"🔎 *Результаты: {escape_markdown(query)}*\n\n"
        for r in results:
            name = escape_markdown(r.get('name', 'N/A'))
            url = r.get('url', '')
            stars = r.get('stars', 0)
            lang = escape_markdown(str(r.get('lang', 'N/A')))
            desc = escape_markdown(r.get('desc', 'Нет описания'))
            text += f"📦 [{name}]({url})\n⭐ {stars} | 📝 {lang}\n{desc}\n\n"
        await message.answer(text[:4000], parse_mode="Markdown", reply_markup=get_main_keyboard())
    await state.clear()

@router.message(F.text == "📱 APKMirror")
async def apk_start(message: Message, state: FSMContext):
    await message.answer("📱 Введите название приложения:", reply_markup=get_cancel_keyboard())
    await state.set_state(UserState.waiting_apk_query)

@router.message(UserState.waiting_apk_query)
async def apk_search(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return
    
    query = message.text if message.text else ""
    results = await search_apkmirror(query)
    
    if not results:
        await message.answer("Ничего не найдено.", reply_markup=get_main_keyboard())
    else:
        text = f"📱 *APKMirror: {escape_markdown(query)}*\n\n"
        for r in results:
            title = escape_markdown(r.get('title', 'N/A'))
            link = r.get('link', '')
            version = escape_markdown(r.get('version', 'N/A'))
            text += f"[{title}]({link})\n📄 {version}\n\n"
        await message.answer(text[:4000], parse_mode="Markdown", reply_markup=get_main_keyboard())
    await state.clear()

@router.message(F.text == "📁 Trashbox")
async def trashbox_start(message: Message, state: FSMContext):
    await message.answer("📁 Введите название приложения:", reply_markup=get_cancel_keyboard())
    await state.set_state(UserState.waiting_trashbox_query)

@router.message(UserState.waiting_trashbox_query)
async def trashbox_search(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return
    
    query = message.text if message.text else ""
    results = await search_trashbox(query)
    
    if not results:
        await message.answer("Ничего не найдено.", reply_markup=get_main_keyboard())
    else:
        text = f"📁 *Trashbox: {escape_markdown(query)}*\n\n"
        for r in results:
            title = escape_markdown(r.get('title', 'N/A'))
            link = r.get('link', '')
            version = escape_markdown(r.get('version', 'N/A'))
            text += f"[{title}]({link})\n📄 {version}\n\n"
        await message.answer(text[:4000], parse_mode="Markdown", reply_markup=get_main_keyboard())
    await state.clear()

@router.message(F.text == "☀️ Погода")
async def weather_start(message: Message, state: FSMContext):
    await message.answer("☀️ Введите город:", reply_markup=get_cancel_keyboard())
    await state.set_state(UserState.waiting_weather_city)

@router.message(UserState.waiting_weather_city)
async def weather_search(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return
    
    city = message.text if message.text else ""
    w = await get_weather(city)
    
    if not w:
        await message.answer("Город не найден или API ключ не задан.", reply_markup=get_main_keyboard())
    else:
        city_name = escape_markdown(w.get('city', city))
        temp = w.get('temp', 0)
        feels = w.get('feels', 0)
        desc = escape_markdown(w.get('desc', 'Нет данных'))
        humidity = w.get('humidity', 0)
        wind = w.get('wind', 0)
        text = f"☀️ *{city_name}*\n🌡 {temp}°C \\(ощущается {feels}°C\\)\n📝 {desc}\n💧 {humidity}% | 💨 {wind} м/с"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
    await state.clear()
