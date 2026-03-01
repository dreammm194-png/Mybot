import asyncio
import os
import aiohttp
import logging
import time
from threading import Thread
from datetime import datetime
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode
from aiogram.utils import executor
from bs4 import BeautifulSoup

# ===================== НАСТРОЙКИ =====================
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле")

# ===================== ИНИЦИАЛИЗАЦИЯ =====================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ===================== АВТОПИНГЕР ДЛЯ RENDER =====================
class SelfPinger:
    def __init__(self, url, interval_minutes=10):
        self.url = url
        self.interval = interval_minutes * 60  # в секунды
        self.running = True
        self.logger = logging.getLogger('SelfPinger')
        
    def start(self):
        thread = Thread(target=self._ping_loop, daemon=True)
        thread.start()
        self.logger.info(f"✅ Автопингер запущен для {self.url}, интервал {self.interval//60} минут")
    
    def _ping_loop(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                response = loop.run_until_complete(self._ping())
                if response and response.status == 200:
                    self.logger.info(f"✅ Пинг успешен: {response.status} в {datetime.now().strftime('%H:%M:%S')}")
                else:
                    self.logger.warning(f"⚠️ Пинг вернул статус: {response.status if response else 'None'}")
            except Exception as e:
                self.logger.error(f"❌ Ошибка пинга: {e}")
            
            time.sleep(self.interval)
    
    async def _ping(self):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.url, timeout=10) as resp:
                    return resp
            except Exception as e:
                self.logger.error(f"Ошибка соединения: {e}")
                return None
    
    def stop(self):
        self.running = False

# Запускаем автопингер если есть URL
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')
if RENDER_URL:
    pinger = SelfPinger(RENDER_URL, interval_minutes=10)
    pinger.start()
    print(f"🔄 Автопингер активирован для {RENDER_URL}")
else:
    print("⚠️ RENDER_EXTERNAL_URL не найден. Автопинг не работает.")
    print("💡 Добавь переменную RENDER_EXTERNAL_URL в настройках Render")

# ===================== ПОИСК НА GITHUB =====================
async def search_github(query: str, limit: int = 5):
    url = 'https://api.github.com/search/repositories'
    params = {'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': limit}
    results = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            items = data.get('items', [])
            for repo in items:
                full_name = repo['full_name']
                html_url = repo['html_url']
                description = repo['description'] or 'Нет описания'
                stars = repo['stargazers_count']
                lang = repo['language'] or 'Unknown'
                releases_url = f"https://api.github.com/repos/{full_name}/releases/latest"
                async with session.get(releases_url) as rel_resp:
                    apk_url = None
                    if rel_resp.status == 200:
                        rel_data = await rel_resp.json()
                        assets = rel_data.get('assets', [])
                        for asset in assets:
                            if asset['name'].endswith('.apk'):
                                apk_url = asset['browser_download_url']
                                break
                results.append({
                    'name': full_name,
                    'url': html_url,
                    'desc': description,
                    'stars': stars,
                    'lang': lang,
                    'apk_url': apk_url
                })
            return results

# ===================== ПОИСК НА APKMIRROR =====================
async def search_apkmirror(query: str, limit: int = 5):
    url = 'https://www.apkmirror.com/'
    params = {'post_type': 'app_release', 'searchtype': 'apk', 's': query}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    results = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()
            soup = BeautifulSoup(html, 'html.parser')
            items = soup.select('.appRow')
            for item in items[:limit]:
                title_tag = item.select_one('.appRowTitle a')
                if not title_tag:
                    continue
                title = title_tag.text.strip()
                link = 'https://www.apkmirror.com' + title_tag['href']
                version_tag = item.select_one('.infoSlide-value')
                version = version_tag.text.strip() if version_tag else '?'
                date_tag = item.select_one('.date')
                date = date_tag.text.strip() if date_tag else '?'
                size_tag = item.select_one('.filesize')
                size = size_tag.text.strip() if size_tag else '?'
                results.append({
                    'title': title,
                    'url': link,
                    'version': version,
                    'date': date,
                    'size': size
                })
            return results

# ===================== КОМАНДА /start =====================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    text = (
        "🔍 *Git & APK Search Bot*\n\n"
        "Я ищу приложения (APK) на APKMirror и исходники/скрипты на GitHub.\n\n"
        "*Команды:*\n"
        "/git [запрос] — поиск на GitHub\n"
        "/apk [запрос] — поиск на APKMirror\n"
        "/help — подсказки\n\n"
        "_Иконка: Kiranshastry / Flaticon_"
    )
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

# ===================== КОМАНДА /help =====================
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    text = (
        "📚 *Как пользоваться ботом*\n\n"
        "🔹 `/git python telegram` — ищет репозитории на GitHub по запросу\n"
        "🔹 `/apk youtube` — ищет APK на APKMirror\n"
        "🔹 Для GitHub бот покажет репозитории, а если в релизах есть APK — даст ссылку на скачивание.\n"
        "🔹 Для APKMirror бот выдаст прямые ссылки на страницы с загрузкой.\n\n"
        "Если нужна помощь — пиши @твой_юзернейм"
    )
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

# ===================== КОМАНДА /git =====================
@dp.message_handler(commands=['git'])
async def cmd_git(message: types.Message):
    args = message.get_args()
    if not args:
        await message.reply("❌ Укажи запрос после /git, например: `/git python telegram`", parse_mode=ParseMode.MARKDOWN)
        return
    await message.reply(f"🔍 Ищу на GitHub: `{args}` ...", parse_mode=ParseMode.MARKDOWN)
    repos = await search_github(args)
    if not repos:
        await message.reply("😕 Ничего не нашёл. Попробуй другой запрос.")
        return
    text_lines = []
    for repo in repos:
        line = f"📦 *{repo['name']}*\n"
        line += f"⭐ {repo['stars']} • 🐍 {repo['lang']}\n"
        if len(repo['desc']) > 100:
            line += f"📝 {repo['desc'][:100]}...\n"
        else:
            line += f"📝 {repo['desc']}\n"
        line += f"🔗 [Открыть репозиторий]({repo['url']})\n"
        if repo['apk_url']:
            line += f"📱 [Скачать APK]({repo['apk_url']})\n"
        text_lines.append(line)
    text = "\n".join(text_lines)
    await message.reply(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

# ===================== КОМАНДА /apk =====================
@dp.message_handler(commands=['apk'])
async def cmd_apk(message: types.Message):
    args = message.get_args()
    if not args:
        await message.reply("❌ Укажи запрос после /apk, например: `/apk youtube`", parse_mode=ParseMode.MARKDOWN)
        return
    await message.reply(f"🔍 Ищу на APKMirror: `{args}` ...", parse_mode=ParseMode.MARKDOWN)
    apps = await search_apkmirror(args)
    if not apps:
        await message.reply("😕 Ничего не нашёл. Попробуй другой запрос.")
        return
    text_lines = []
    for app in apps:
        line = f"📱 *{app['title']}*\n"
        line += f"Версия: {app['version']} • {app['date']}\n"
        line += f"💾 {app['size']}\n"
        line += f"🔗 [Скачать с APKMirror]({app['url']})\n"
        text_lines.append(line)
    text = "\n".join(text_lines)
    await message.reply(text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)

# ===================== ЗАПУСК =====================
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
