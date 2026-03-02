import asyncio
import os
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from bs4 import BeautifulSoup
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO)

# ===================== ПОИСК GITHUB =====================
async def search_github(query: str, limit: int = 6):
    url = 'https://api.github.com/search/repositories'
    params = {'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': limit}
    results = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            for repo in data.get('items', []):
                rel_url = f"https://api.github.com/repos/{repo['full_name']}/releases/latest"
                apk_data = None
                async with session.get(rel_url) as r:
                    if r.status == 200:
                        assets = (await r.json()).get('assets', [])
                        for a in assets:
                            if a['name'].lower().endswith('.apk'):
                                apk_data = {'url': a['browser_download_url'], 'name': a['name']}
                                break
                results.append({
                    'name': repo['full_name'],
                    'url': repo['html_url'],
                    'desc': repo['description'] or 'Нет описания',
                    'stars': repo['stargazers_count'],
                    'lang': repo['language'] or '?',
                    'apk': apk_data
                })
    return results

# ===================== ПОИСК APKMIRROR =====================
async def search_apkmirror(query: str, limit: int = 6):
    url = 'https://www.apkmirror.com/'
    params = {'post_type': 'app_release', 'searchtype': 'apk', 's': query}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    results = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                return []
            soup = BeautifulSoup(await resp.text(), 'html.parser')
            items = soup.select('.appRow')
            for item in items[:limit]:
                t = item.select_one('.appRowTitle a')
                if t:
                    results.append({
                        'title': t.text.strip(),
                        'url': 'https://www.apkmirror.com' + t['href'],
                        'version': item.select_one('.infoSlide-value').text.strip() if item.select_one('.infoSlide-value') else '?',
                        'size': item.select_one('.filesize').text.strip() if item.select_one('.filesize') else '?'
                    })
    return results

# ===================== СТИЛЬНЫЕ СООБЩЕНИЯ =====================
async def send_card(chat_id, title, text, url=None, apk_url=None):
    kb = InlineKeyboardMarkup(row_width=2)
    if url:
        kb.add(InlineKeyboardButton("🌐 Открыть", url=url))
    if apk_url:
        kb.add(InlineKeyboardButton("📥 Скачать APK", url=apk_url))
    
    styled = f"<b>{title}</b>\n\n{text}"
    await bot.send_message(chat_id, styled, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

# ===================== КОМАНДЫ =====================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    text = (
        "🔥 <b> GitHubFinder </b> 🔥\n\n"
        "Ищи софт и APK мгновенно:\n\n"
        "• /git [запрос] — GitHub\n"
        "• /apk [запрос] — APKMirror\n\n"
        "Просто пиши и качай."
    )
    await bot.send_message(message.chat.id, text, parse_mode=ParseMode.HTML)

@dp.message_handler(commands=['git'])
async def cmd_git(message: types.Message):
    args = message.get_args().strip()
    if not args:
        return await bot.send_message(message.chat.id, "<b>Напиши запрос после /git</b>", parse_mode="HTML")

    await bot.send_message(message.chat.id, f"<b>Ищу на GitHub:</b> <code>{args}</code>...", parse_mode="HTML")

    repos = await search_github(args)
    if not repos:
        return await bot.send_message(message.chat.id, "😕 Ничего не нашлось.")

    for repo in repos:
        text = f"⭐ {repo['stars']} • {repo['lang']}\n{repo['desc'][:180]}{'...' if len(repo['desc']) > 180 else ''}"
        apk_url = repo['apk']['url'] if repo['apk'] else None
        await send_card(message.chat.id, repo['name'], text, repo['url'], apk_url)

@dp.message_handler(commands=['apk'])
async def cmd_apk(message: types.Message):
    args = message.get_args().strip()
    if not args:
        return await bot.send_message(message.chat.id, "<b>Напиши запрос после /apk</b>", parse_mode="HTML")

    status = await bot.send_message(message.chat.id, "<b>Поиск на APKMirror...</b>", parse_mode="HTML")
    apps = await search_apkmirror(args)
    await status.delete()

    if not apps:
        return await bot.send_message(message.chat.id, "😕 Ничего не найдено.")

    for app in apps:
        text = f"Версия: <code>{app['version']}</code>\nРазмер: <code>{app['size']}</code>"
        await send_card(message.chat.id, app['title'], text, app['url'])

# ===================== ВЕБ-СЕРВЕР =====================
async def handle_ping(request):
    return web.Response(text="pong")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 10000)))
    await site.start()
    logging.info("Сервер стартовал")
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
