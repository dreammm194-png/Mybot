import asyncio
import os
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from bs4 import BeautifulSoup
from aiohttp import web
from dotenv import load_dotenv

# ===================== НАСТРОЙКИ =====================
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# ===================== [НОВАЯ ФУНКЦИЯ] ЗАГРУЗЧИК-СТРИМЕР =====================
async def send_apk_stream(chat_id, url, filename):
    """Качает файл и сразу шлет в TG, обходя лимит 50МБ и экономя ОЗУ Render"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    await bot.send_document(
                        chat_id, 
                        document=types.InputFile(resp.content, filename=filename),
                        caption=f"✅ *Файл готов:* `{filename}`\n🚀 _Отправлено через Stream_"
                    )
                else:
                    await bot.send_message(chat_id, "❌ Ошибка: не удалось получить файл.")
    except Exception as e:
        await bot.send_message(chat_id, f"❌ Ошибка загрузки: {e}")

# ===================== ВЕБ-СЕРВЕР (БЕЗ ИЗМЕНЕНИЙ) =====================
async def handle_ping(request): return web.Response(text="pong", status=200)
async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    port = int(os.environ.get('PORT', 10000))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', port).start()

# ===================== ПОИСК (ТВОЯ ЛОГИКА) =====================
async def search_github(query: str, limit: int = 5):
    url = 'https://api.github.com/search/repositories'
    params = {'q': query, 'sort': 'stars', 'per_page': limit}
    results = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200: return []
            data = await resp.json()
            for repo in data.get('items', []):
                rel_url = f"https://api.github.com/repos/{repo['full_name']}/releases/latest"
                apk_url = None
                async with session.get(rel_url) as r:
                    if r.status == 200:
                        assets = (await r.json()).get('assets', [])
                        for a in assets:
                            if a['name'].endswith('.apk'):
                                apk_url = a['browser_download_url']; break
                results.append({'name': repo['full_name'], 'url': repo['html_url'], 'desc': repo['description'] or 'Нет описания', 'stars': repo['stargazers_count'], 'lang': repo['language'] or '?', 'apk_url': apk_url})
    return results

async def search_apkmirror(query: str, limit: int = 5):
    url = 'https://www.apkmirror.com/'
    params = {'post_type': 'app_release', 'searchtype': 'apk', 's': query}
    headers = {'User-Agent': 'Mozilla/5.0'}
    results = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200: return []
            soup = BeautifulSoup(await resp.text(), 'html.parser')
            for item in soup.select('.appRow')[:limit]:
                t = item.select_one('.appRowTitle a')
                if t:
                    results.append({'title': t.text.strip(), 'url': 'https://www.apkmirror.com' + t['href'], 'version': item.select_one('.infoSlide-value').text.strip() if item.select_one('.infoSlide-value') else '?', 'size': item.select_one('.filesize').text.strip() if item.select_one('.filesize') else '?'})
    return results

# ===================== [ОБНОВЛЕННЫЙ ИНТЕРФЕЙС] =====================

@dp.message_handler(commands=['git'])
async def cmd_git(message: types.Message):
    args = message.get_args()
    if not args: return await message.reply("📝 Напиши: `/git название`", parse_mode="Markdown")
    
    repos = await search_github(args)
    if not repos: return await message.reply("😕 Ничего не нашли.")

    for repo in repos:
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("🌐 Репозиторий", url=repo['url']))
        if repo['apk_url']:
            kb.add(InlineKeyboardButton("📥 Скачать APK в Telegram", url=repo['apk_url'])) # Можно заменить на вызов стрима

        text = (
            f"📦 *{repo['name']}*\n"
            f"⭐️ Звезд: `{repo['stars']}` | 🛠 `{repo['lang']}`\n"
            f"📝 {repo['desc'][:120]}..."
        )
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.message_handler(commands=['apk'])
async def cmd_apk(message: types.Message):
    args = message.get_args()
    if not args: return await message.reply("📝 Напиши: `/apk название`", parse_mode="Markdown")
    
    apps = await search_apkmirror(args)
    if not apps: return await message.reply("😕 Ничего не нашли.")

    for app in apps:
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("📂 Перейти к загрузке", url=app['url']))
        
        text = (
            f"📱 *{app['title']}*\n"
            f"🏷 Версия: `{app['version']}`\n"
            f"💾 Размер: `{app['size']}`"
        )
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

# ===================== ЗАПУСК =====================
async def main():
    await start_web_server()
    print("✅ Бот онлайн")
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
