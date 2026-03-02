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

user_state = {}

async def send_styled_message(chat_id, text, reply_markup=None, reply_to=None):
    await bot.send_message(chat_id, text, parse_mode=ParseMode.HTML, reply_markup=reply_markup, reply_to_message_id=reply_to, disable_web_page_preview=True)

async def search_github(query: str, limit: int = 6):
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
                    if r.status = 200:
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
        "Все команды: /commands\n\n"
        "Выбери функцию:"
    )
    await send_styled_message(message.chat.id, text, kb)

@dp.message_handler(commands=['commands'])
async def cmd_commands(message: types.Message):
    text = (
        "<b>Команды:</b>\n\n"
        "/git [запрос] — GitHub\n"
        "/apk [запрос] — APKMirror\n"
        "/weather [город] — Погода\n"
        "/song [трек] — Музыка\n"
        "/news [тема] — Новости\n"
        "/price [товар] — Цены"
    )
    await send_styled_message(message.chat.id, text)

@dp.callback_query_handler()
async def callback_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    data = callback.data

    if data.startswith("menu_"):
        typ = data.split("_")[1]
        user_state[user_id] = {"type": typ, "query": "", "page": 0, "count": 3}
        await callback.message.edit_text(f"Введи запрос для {typ.upper()}:", reply_markup=None)
    elif data.startswith("page:"):
        _, typ, query, page = data.split(":")
        user_state[user_id] = {"type": typ, "query": query, "page": int(page), "count": user_state[user_id].get("count", 3)}
        await show_results(callback.message.chat.id, user_id, callback.message.message_id)
    elif data.startswith("count:"):
        count = int(data.split(":")[1])
        user_state[user_id]["count"] = count
        user_state[user_id]["page"] = 0
        await show_results(callback.message.chat.id, user_id, callback.message.message_id)
    elif data.startswith("weather_region:"):
        region = data.split(":")[1]
        user_state[user_id] = {"type": "weather", "region": region, "query": ""}
        await callback.message.edit_text("Введи город:")
    elif data == "collapse_week":
        await callback.message.edit_text("<b>Прогноз свернут</b>", reply_markup=None)

@dp.message_handler(commands=['git', 'apk', 'weather', 'song', 'news', 'price'])
async def handle_command(message: types.Message):
    cmd = message.get_command()[1:]
    args = message.get_args().strip()
    if not args:
        return await message.reply("Напиши запрос после команды.")

    user_state[message.from_user.id] = {"type": cmd, "query": args, "page": 0, "count": 3}
    await show_results(message.chat.id, message.from_user.id)

async def show_results(chat_id, user_id, msg_id=None):
    state = user_state.get(user_id, {})
    if not state: return

    query = state["query"]
    page = state["page"]
    count = state["count"]
    typ = state["type"]

    if typ in ["git", "apk"]:
        if typ == "git":
            results = await search_github(query, limit=count * 3)
        else:
            results = await search_apkmirror(query, limit=count * 3)

        start = page * count
        items = results[start:start + count]

        kb = InlineKeyboardMarkup(row_width=2)
        if page > 0:
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data=f"page:{typ}:{query}:{page-1}"))
        if len(results) > start + count:
            kb.add(InlineKeyboardButton("Вперёд ➡️", callback_data=f"page:{typ}:{query}:{page+1}"))
        kb.add(InlineKeyboardButton("3", callback_data="count:3"), InlineKeyboardButton("5", callback_data="count:5"), InlineKeyboardButton("10", callback_data="count:10"))

        text = f"<b>Результаты для {query} ({len(results)})</b>\n\n"
        for i, item in enumerate(items, start + 1):
            title = item.get('name') or item.get('title')
            desc = item.get('desc') or f"Версия: {item.get('version')} Размер: {item.get('size')}"
            text += f"{i}. <b>{title}</b> - {desc}\n"

        if msg_id:
            await bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            msg = await bot.send_message(chat_id, text, reply_markup=kb, parse_mode=ParseMode.HTML)
            user_state[user_id]["msg_id"] = msg.message_id

    elif typ == "weather":
        # (web_search for weather)
        text = f"<b>Погода в {query}</b>\nСегодня: 15°C, солнечно\n\n<b>На неделю (развернуть):</b>\nПн: 16°C\nВт: 17°C\nСр: 15°C\nЧт: 14°C\nПт: 13°C\nСб: 18°C\nВс: 19°C"
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("Свернуть неделю", callback_data="collapse_week"))
        await bot.send_message(chat_id, text, reply_markup=kb, parse_mode=ParseMode.HTML)

    # (аналогично для song, news, price)

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 10000))).start()
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
