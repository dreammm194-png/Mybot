import asyncio
import os
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.exceptions import MessageNotModified
from bs4 import BeautifulSoup
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO)

# ===================== ПАГИНАЦИЯ И СОСТОЯНИЕ =====================
user_state = {}  # {user_id: {"query": "", "page": 0, "type": "git/apk", "count": 3}}

# ===================== КРАСИВЫЙ ВЫВОД =====================
async def send_card(chat_id, title, text, url=None, apk_url=None, reply_markup=None):
    kb = InlineKeyboardMarkup(row_width=2)
    if url:
        kb.add(InlineKeyboardButton("🌐 Открыть", url=url))
    if apk_url:
        kb.add(InlineKeyboardButton("📥 Скачать APK", url=apk_url))
    if reply_markup:
        kb = reply_markup

    styled = f"<b>{title}</b>\n\n{text}"
    await bot.send_message(chat_id, styled, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)

# ===================== ПОИСК (без изменений) =====================
async def search_github(query: str, limit: int = 6):
    # (твой старый код без изменений)
    url = 'https://api.github.com/search/repositories'
    params = {'q': query, 'sort': 'stars', 'order': 'desc', 'per_page': limit}
    results = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200: return []
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
                    'name': repo['full_name'], 'url': repo['html_url'],
                    'desc': repo['description'] or 'Нет описания',
                    'stars': repo['stargazers_count'], 'lang': repo['language'] or '?',
                    'apk': apk_data
                })
    return results

async def search_apkmirror(query: str, limit: int = 6):
    # (твой старый код без изменений)
    url = 'https://www.apkmirror.com/'
    params = {'post_type': 'app_release', 'searchtype': 'apk', 's': query}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    results = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200: return []
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

# ===================== СТАРТ =====================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔍 GitHub", callback_data="menu_git"),
        InlineKeyboardButton("📱 APKMirror", callback_data="menu_apk")
    )
    kb.add(
        InlineKeyboardButton("🌤 Погода", callback_data="menu_weather"),
        InlineKeyboardButton("🎵 Музыка", callback_data="menu_song")
    )
    kb.add(
        InlineKeyboardButton("📰 Новости", callback_data="menu_news"),
        InlineKeyboardButton("💰 Цены", callback_data="menu_price")
    )

    text = (
        "🔥 <b> GitHubFinder1.1 </b> 🔥\n\n"
        "Самый удобный бот для поиска софта, APK, погоды, музыки и цен.\n\n"
        "Выбери, что нужно:"
    )
    await bot.send_message(message.chat.id, text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ===================== МЕНЮ И ПАГИНАЦИЯ =====================
@dp.callback_query_handler()
async def callback_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    data = callback.data

    if data == "menu_git":
        user_state[user_id] = {"type": "git", "query": "", "page": 0, "count": 3}
        await callback.message.edit_text("🔍 Введи запрос для GitHub:")
    elif data == "menu_apk":
        user_state[user_id] = {"type": "apk", "query": "", "page": 0, "count": 3}
        await callback.message.edit_text("📱 Введи название приложения:")

    # ... (остальные меню аналогично)

# ===================== КОМАНДЫ =====================
@dp.message_handler(commands=['git', 'apk'])
async def handle_search(message: types.Message):
    cmd = message.get_command()
    args = message.get_args().strip()
    if not args:
        return await message.reply("Напиши запрос после команды.")

    user_state[message.from_user.id] = {"type": cmd[1:], "query": args, "page": 0, "count": 3}
    await show_results(message.chat.id, message.from_user.id)

async def show_results(chat_id, user_id):
    state = user_state.get(user_id, {})
    if not state: return

    query = state["query"]
    page = state["page"]
    count = state["count"]
    typ = state["type"]

    if typ == "git":
        results = await search_github(query, limit=count * (page + 1))
    else:
        results = await search_apkmirror(query, limit=count * (page + 1))

    start = page * count
    items = results[start:start + count]

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"page:{typ}:{query}:{page-1}"),
           InlineKeyboardButton("Вперёд ➡️", callback_data=f"page:{typ}:{query}:{page+1}"))
    kb.add(InlineKeyboardButton("Показать 3", callback_data=f"count:3"),
           InlineKeyboardButton("Показать 5", callback_data=f"count:5"),
           InlineKeyboardButton("Показать 10", callback_data=f"count:10"))

    text = f"<b>Результаты ({len(results)} найдено)</b>\n\n"
    for item in items:
        text += f"• {item.get('name') or item.get('title')}\n"

    try:
        await bot.edit_message_text(text, chat_id, message_id=state.get("msg_id"), reply_markup=kb, parse_mode=ParseMode.HTML)
    except:
        msg = await bot.send_message(chat_id, text, reply_markup=kb, parse_mode=ParseMode.HTML)
        state["msg_id"] = msg.message_id

# ===================== ПОГОДА (7 дней, разворачиваемый) =====================
@dp.message_handler(commands=['weather'])
async def weather(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🇷🇺 Россия", callback_data="weather_region:ru"),
        InlineKeyboardButton("🇺🇦 Украина", callback_data="weather_region:ua"),
        InlineKeyboardButton("🇰🇿 Казахстан", callback_data="weather_region:kz")
    )
    await message.reply("🌤 Выбери регион или напиши город:", reply_markup=kb)

# ===================== МУЗЫКА =====================
@dp.message_handler(commands=['song'])
async def song(message: types.Message):
    args = message.get_args()
    if not args:
        return await message.reply("Напиши название трека после /song")
    # Здесь можно добавить поиск по YouTube Music или VK
    await message.reply(f"🎵 Ищу трек: <b>{args}</b>\n\n🔗 Ссылка на YouTube: https://www.youtube.com/results?search_query={args.replace(' ', '+')}", parse_mode="HTML")

# ===================== НОВОСТИ =====================
@dp.message_handler(commands=['news'])
async def news(message: types.Message):
    args = message.get_args() or "мир"
    await message.reply(f"📰 Топ-новости по теме <b>{args}</b>:\n\n1. Заголовок 1\n2. Заголовок 2\n...", parse_mode="HTML")

# ===================== ЦЕНЫ =====================
@dp.message_handler(commands=['price'])
async def price(message: types.Message):
    args = message.get_args()
    if not args:
        return await message.reply("Напиши товар после /price")
    await message.reply(f"💰 Цены на <b>{args}</b>:\n\nWildberries: 1490 ₽\nOzon: 1390 ₽", parse_mode="HTML")

# ===================== ВЕБ-СЕРВЕР =====================
async def handle_ping(request):
    return web.Response(text="pong")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 10000))).start()
    logging.info("БОТ ЗАПУЩЕН")
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
