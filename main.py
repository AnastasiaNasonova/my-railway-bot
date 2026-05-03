from fastapi import FastAPI
from aiogram import types, Dispatcher, Bot
from bot import dp, bot
from config import TELEGRAM_BOT_TOKEN, APP_DOMAIN

app = FastAPI()

# Путь для вебхука
WEBHOOK_PATH = f"/bot/{TELEGRAM_BOT_TOKEN}"
# Полный URL, который мы сообщим Телеграму
WEBHOOK_URL = f"{APP_DOMAIN}{WEBHOOK_PATH}"

# При запуске сервера подключаем вебхук к Telegram
@app.on_event("startup")
async def on_startup():
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(url=WEBHOOK_URL)

# Сюда Telegram будет присылать новые сообщения
@app.post(WEBHOOK_PATH)
async def bot_webhook(update: dict):
    telegram_update = types.Update(**update)
    Dispatcher.set_current(dp)
    Bot.set_current(bot)
    await dp.process_update(telegram_update)

# При выключении закрываем сессию
@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()