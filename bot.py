## bot/utils/github_api.py

```python
import aiohttp
from typing import List, Dict
from bot.config import config

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
                    for item in data.get("items", [])[:5]:
                        results.append({
                            "name": item.get("full_name", "N/A"),
                            "stars": item.get("stargazers_count", 0),
                            "desc": item.get("description", "Нет описания")[:100],
                            "url": item.get("html_url", ""),
                            "lang": item.get("language", "N/A")
                        })
    except:
        pass
    return results
```

---

## bot/utils/weather_api.py

```python
import aiohttp
from typing import Dict, Optional
from bot.config import config

async def get_weather(city: str) -> Optional[Dict]:
    if not config.OPENWEATHER_API_KEY:
        return None
    
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={config.OPENWEATHER_API_KEY}&units=metric&lang=ru"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "city": data.get("name", city),
                        "temp": data["main"]["temp"],
                        "feels": data["main"]["feels_like"],
                        "desc": data["weather"][0]["description"].capitalize(),
                        "humidity": data["main"]["humidity"],
                        "wind": data["wind"]["speed"]
                    }
    except:
        pass
    return None
```

---

## bot/utils/apk_parser.py

```python
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict
import urllib.parse
import time

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
                    return results
                html = await resp.text()
        
        soup = BeautifulSoup(html, 'lxml')
        for row in soup.find_all('div', class_='appRow')[:8]:
            title_elem = row.find('a', class_='appRowTitle')
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            link = title_elem.get('href', '')
            if link and not link.startswith('http'):
                link = 'https://www.apkmirror.com' + link
            ver_elem = row.find('div', class_='appRowVersion')
            version = ver_elem.get_text(strip=True) if ver_elem else 'N/A'
            if title and link:
                results.append({'title': title, 'version': version, 'link': link})
    except:
        pass
    
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
                    return results
                html = await resp.text()
        
        soup = BeautifulSoup(html, 'lxml')
        items = soup.find_all('div', class_='catalog_item') or soup.find_all('li', class_='search-item')
        
        for item in items[:8]:
            title_elem = item.find('a', class_='name') or item.find('a', class_='search-link')
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            link = title_elem.get('href', '')
            if link and not link.startswith('http'):
                link = 'https://trashbox.ru' + link
            ver_elem = item.find('span', class_='version') or item.find('span', class_='app_ver')
            version = ver_elem.get_text(strip=True) if ver_elem else 'N/A'
            if title and link:
                results.append({'title': title, 'version': version, 'link': link})
    except:
        pass
    
    _set_cache(f"trash:{query}", results)
    return results
```

---

## bot/config.py

```python
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    PORT: int = int(os.getenv("PORT", "10000"))

config = Config()
```

---

## bot/keyboards/reply_kb.py

```python
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
```

---

## bot/handlers/start.py

```python
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.keyboards.reply_kb import get_main_keyboard, get_cancel_keyboard
from bot.utils.github_api import search_github
from bot.utils.weather_api import get_weather
from bot.utils.apk_parser import search_apkmirror, search_trashbox

router = Router()

class UserState(StatesGroup):
    waiting_github_query = State()
    waiting_apk_query = State()
    waiting_trashbox_query = State()
    waiting_weather_city = State()
    waiting_news_query = State()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🤖 **Github Finder**\n\nПоиск репозиториев, APK, погоды и новостей.\n\nВыберите действие 👇",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    await message.answer(
        "🔍 GitHub — поиск репозиториев\n📱 APKMirror — поиск APK\n📁 Trashbox — софт для Android\n☀️ Погода — прогноз\n📰 Новости — в разработке",
        reply_markup=get_main_keyboard()
    )

# GitHub
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
    
    results = await search_github(message.text)
    if not results:
        await message.answer("Ничего не найдено.", reply_markup=get_main_keyboard())
    else:
        text = f"🔎 **Результаты: {message.text}**\n\n"
        for r in results:
            text += f"📦 [{r['name']}]({r['url']})\n⭐ {r['stars']} | 📝 {r['lang']}\n{r['desc']}\n\n"
        await message.answer(text[:4000], parse_mode="Markdown", reply_markup=get_main_keyboard())
    await state.clear()

# APKMirror
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
    
    results = await search_apkmirror(message.text)
    if not results:
        await message.answer("Ничего не найдено.", reply_markup=get_main_keyboard())
    else:
        text = f"📱 **APKMirror: {message.text}**\n\n"
        for r in results:
            text += f"[{r['title']}]({r['link']})\n📄 {r['version']}\n\n"
        await message.answer(text[:4000], parse_mode="Markdown", reply_markup=get_main_keyboard())
    await state.clear()

# Trashbox
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
    
    results = await search_trashbox(message.text)
    if not results:
        await message.answer("Ничего не найдено.", reply_markup=get_main_keyboard())
    else:
        text = f"📁 **Trashbox: {message.text}**\n\n"
        for r in results:
            text += f"[{r['title']}]({r['link']})\n📄 {r['version']}\n\n"
        await message.answer(text[:4000], parse_mode="Markdown", reply_markup=get_main_keyboard())
    await state.clear()

# Weather
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
    
    w = await get_weather(message.text)
    if not w:
        await message.answer("Город не найден или API ключ не задан.", reply_markup=get_main_keyboard())
    else:
        text = f"☀️ **{w['city']}**\n🌡 {w['temp']}°C (ощущается {w['feels']}°C)\n📝 {w['desc']}\n💧 {w['humidity']}% | 💨 {w['wind']} м/с"
        await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
    await state.clear()

# News placeholder
@router.message(F.text == "📰 Новости")
async def news_start(message: Message):
    await message.answer("📰 В разработке...", reply_markup=get_main_keyboard())
```

---

## bot/main.py

```python
import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from bot.config import config
from bot.handlers.start import router as start_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def health_handler(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get("/health", health_handler), web.get("/", health_handler)])
    port = int(os.getenv("PORT", "10000"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")
    return runner

async def main():
    if not config.BOT_TOKEN:
        logging.error("BOT_TOKEN не задан!")
        return
    
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher()
    dp.include_router(start_router)
    
    runner = await start_web_server()
    
    try:
        await asyncio.gather(
            dp.start_polling(bot),
        )
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## requirements.txt

```
aiogram>=3.10.0
aiohttp>=3.9.0
python-dotenv>=1.0.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

---

## Procfile

```
worker: python -m bot.main
```

---

## .env

```
BOT_TOKEN=
GITHUB_TOKEN=
OPENWEATHER_API_KEY=
NEWS_API_KEY=
DEBUG=false
PORT=10000
```
