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
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Включаем логи, чтобы видеть ошибки в консоли Render
logging.basicConfig(level=logging.INFO)

# ===================== ЗАГРУЗЧИК (STREAM) =====================
async def send_apk_stream(chat_id, url, filename):
    """Качает файл и сразу шлет в TG, экономя память сервера"""
    status_msg = await bot.send_message(chat_id, f"⏳ *Загружаю файл:* `{filename}`...", parse_mode="Markdown")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=300) as resp:
                if resp.status == 200:
                    # Передаем поток данных напрямую в Telegram
                    await bot.send_document(
                        chat_id, 
                        document=types.InputFile(resp.content, filename=filename),
                        caption=f"✅ *Готово!* \n📦 {filename}"
                    )
                else:
                    await bot.send_message(chat_id, f"❌ Ошибка сервера: {resp.status}")
    except Exception as e:
        logging.error(f"Ошибка стрима: {e}")
        await bot.send_message(chat_id, f"❌ Не удалось отправить файл: {e}")
    finally:
        await bot.delete_message(chat_id, status_msg.message_id)

# ===================== ПОИСК GITHUB =====================
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
                apk_data = None
                async with session.get(rel_url) as r:
                    if r.status == 200:
                        assets = (await r.json()).get('assets', [])
                        for a in assets:
                            if a['name'].endswith('.apk'):
                                apk_data = {'url': a['browser_download_url'], 'name': a['name']}
                                break
                results.append({
                    'name': repo['full_name'], 'url': repo['html_url'], 
                    'desc': repo['description'] or 'Нет описания', 
                    'stars': repo['stargazers_count'], 'lang': repo['language'] or '?', 
                    'apk': apk_data
                })
    return results

# ===================== ПОИСК APKMIRROR =====================
async def search_apkmirror(query: str, limit: int = 5):
    url = 'https://www.apkmirror.com/'
    params = {'post_type': 'app_release', 'searchtype': 'apk', 's': query}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
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

# ===================== ОБРАБОТЧИКИ КОМАНД =====================

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("🔍 *Поиск софта v2.0*\n\n`/git` — поиск на GitHub\n`/apk` — поиск на APKMirror", parse_mode="Markdown")

@dp.message_handler(commands=['git'])
async def cmd_git(message: types.Message):
    args = message.get_args()
    if not args: return await message.reply("Напиши название после команды.")
    
    repos = await search_github(args)
    if not repos: return await message.reply("Ничего не нашлось.")

    for repo in repos:
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("🌐 Репозиторий", url=repo['url']))
        
        # Если есть APK, делаем кнопку вызова стрима (через callback) или просто ссылку
        if repo['apk']:
            # В данном примере для простоты шлем файл сразу, если юзер нашел его
            kb.add(InlineKeyboardButton("📥 Скачать файл", callback_data=f"dl_git:{repo['name']}"))
            # Временный хак: сохраним URL в памяти или просто дадим прямую ссылку
            kb.insert(InlineKeyboardButton("🔗 Прямая ссылка", url=repo['apk']['url']))

        text = f"📦 *{repo['name']}*\n⭐ `{repo['stars']}` | 🛠 `{repo['lang']}`\n\n_{repo['desc'][:150]}_"
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.message_handler(commands=['apk'])
async def cmd_apk(message: types.Message):
    args = message.get_args()
    if not args: return await message.reply("Напиши название.")
    
    status = await message.answer("⏳ _Ищу на APKMirror..._", parse_mode="Markdown")
    apps = await search_apkmirror(args)
    await status.delete()

    if not apps: return await message.reply("😕 Ничего не найдено.")

    for app in apps:
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("📂 Открыть страницу", url=app['url']))
        
        text = f"📱 *{app['title']}*\n🏷 Версия: `{app['version']}`\n💾 Размер: `{app['size']}`"
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")

# ===================== ВЕБ-СЕРВЕР ДЛЯ RENDER =====================
async def handle_ping(request): return web.Response(text="online")

async def main():
    # Запуск сервера для пингов
    app = web.Application(); app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 10000))).start()
    
    # Запуск бота
    logging.info("БОТ ЗАПУЩЕН")
    await dp.start_polling()

if __name__ == '__main__':
    asyncio.run(main())
