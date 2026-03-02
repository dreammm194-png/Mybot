import asyncio
import os
import aiohttp
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from bs4 import BeautifulSoup
from aiohttp import web
from dotenv import load_dotenv

# ===================== НАСТРОЙКИ =====================
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ===================== КРАСИВЫЕ СООБЩЕНИЯ =====================
async def send_styled_message(chat_id, text, reply_markup=None, reply_to_message_id=None):
    """Отправляет сообщение с красивым оформлением"""
    styled_text = f"✨ <b>{text}</b> ✨\n\n" if not text.startswith("⏳") else text
    await bot.send_message(
        chat_id,
        styled_text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
        reply_to_message_id=reply_to_message_id,
        disable_web_page_preview=True
    )

# ===================== ПОИСК GITHUB (с красивым выводом) =====================
async def search_github(query: str, limit: int = 5):
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
                    'lang': repo['language'] or 'Не указан',
                    'apk': apk_data
                })
    return results

# ===================== ПОИСК APKMIRROR =====================
async def search_apkmirror(query: str, limit: int = 5):
    url = 'https://www.apkmirror.com/'
    params = {'post_type': 'app_release', 'searchtype': 'apk', 's': query}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
    }
    results = []
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                logging.error(f"APKMirror Status: {resp.status}")
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

# ===================== КРАСИВЫЙ СТАРТ И МЕНЮ =====================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🔍 Поиск GitHub", callback_data="search_git"),
        InlineKeyboardButton("📱 Поиск APKMirror", callback_data="search_apk")
    )
    kb.add(
        InlineKeyboardButton("❓ Помощь", callback_data="help"),
        InlineKeyboardButton("💜 Поддержка", url="https://t.me/твой_канал")
    )

    text = (
        "✨ <b>Добро пожаловать в МУСОР КИЛЛЕР 3000</b> ✨\n\n"
        "Я ищу софт и APK быстрее, чем ты успеешь сказать «бля» 😈\n\n"
        "Выбери, что хочешь найти:"
    )
    await send_styled_message(message.chat.id, text, reply_markup=kb)

# ===================== INLINE-КНОПКИ =====================
@dp.callback_query_handler()
async def callback_handler(callback: types.CallbackQuery):
    await callback.answer()

    if callback.data == "search_git":
        await callback.message.answer(
            "<b>🔍 Введи запрос для GitHub</b>\nПример: python telegram bot",
            parse_mode="HTML"
        )
        await callback.message.delete()

    elif callback.data == "search_apk":
        await callback.message.answer(
            "<b>📱 Введи название приложения</b>\nПример: youtube vanced",
            parse_mode="HTML"
        )
        await callback.message.delete()

    elif callback.data == "help":
        text = (
            "<b>Как пользоваться:</b>\n"
            "• /git [запрос] — поиск репозиториев на GitHub\n"
            "• /apk [запрос] — поиск APK на APKMirror\n"
            "• Нажми на кнопки под сообщением — удобно и красиво ✨\n\n"
            "Если что-то не работает — пиши @твой_ник"
        )
        await send_styled_message(callback.message.chat.id, text)

# ===================== КОМАНДЫ /git и /apk (с красивым выводом) =====================
@dp.message_handler(commands=['git'])
async def cmd_git(message: types.Message):
    args = message.get_args()
    if not args:
        return await message.reply("<b>❌ Напиши запрос после /git</b>", parse_mode="HTML")

    await message.reply(f"<b>🔎 Ищу на GitHub:</b> <code>{args}</code>...", parse_mode="HTML")

    repos = await search_github(args)
    if not repos:
        return await message.reply("😕 Ничего не нашёл. Попробуй другой запрос.")

    for repo in repos:
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(InlineKeyboardButton("🌐 Репозиторий", url=repo['url']))
        if repo['apk']:
            kb.add(InlineKeyboardButton("📥 Скачать APK", url=repo['apk']['url']))

        text = (
            f"📦 <b>{repo['name']}</b>\n"
            f"⭐ {repo['stars']} • {repo['lang']}\n"
            f"📝 {repo['desc'][:200]}{'...' if len(repo['desc']) > 200 else ''}"
        )
        await send_styled_message(message.chat.id, text, reply_markup=kb)

@dp.message_handler(commands=['apk'])
async def cmd_apk(message: types.Message):
    args = message.get_args()
    if not args:
        return await message.reply("<b>❌ Напиши запрос после /apk</b>", parse_mode="HTML")

    status = await message.reply("⏳ <b>Ищу на APKMirror...</b>", parse_mode="HTML")
    apps = await search_apkmirror(args)
    await status.delete()

    if not apps:
        return await message.reply("😕 Ничего не найдено.")

    for app in apps:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📂 Открыть страницу", url=app['url']))

        text = (
            f"📱 <b>{app['title']}</b>\n"
            f"🏷 Версия: <code>{app['version']}</code>\n"
            f"💾 Размер: <code>{app['size']}</code>"
        )
        await send_styled_message(message.chat.id, text, reply_markup=kb)

# ===================== ВЕБ-СЕРВЕР ДЛЯ RENDER =====================
async def handle_ping(request):
    return web.Response(text="pong", status=200)

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 10000)))
    await site.start()
    logging.info(f"Веб-сервер запущен на порту {os.environ.get('PORT', 10000)}")

    logging.info("БОТ ЗАПУЩЕН")
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
