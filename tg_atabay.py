# tg_atabay.py

# tg_webhook.py

"""
tg_webhook.py — Telegram-бот на вебхуках (FastAPI).
Весь NLP-код берётся из bot.py как есть.

Переменные окружения (задать в Railway):
  BOT_TOKEN   — токен от @BotFather
  WEBHOOK_URL — публичный URL Railway-приложения (без слеша в конце)
                например: https://myapp.up.railway.app
"""

import os
import io
import logging
import asyncio
import datetime

from fastapi import FastAPI, Request, Response
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from gtts import gTTS

# ── импортируем всё из bot.py ──────────────────────────────────────────────
from bot import bot, INTENTS, filter_text, skill_weather, skill_time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
import os

load_dotenv()

# ── конфиг ────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.environ["BOT_TOKEN"]
WEBHOOK_URL = os.environ["WEBHOOK_URL"].rstrip("/")
PORT        = int(os.getenv("PORT", 8000))

# ── TTS helper ────────────────────────────────────────────────────────────

def make_voice(text: str) -> io.BytesIO:
    """Генерирует mp3 через gTTS и возвращает BytesIO."""
    tts = gTTS(text=text, lang="ru")
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    buf.name = "response.mp3"   # telegram требует атрибут name
    return buf

# ── хендлеры ──────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context):
    await update.message.reply_text(
        "Привет! Я голосовой бот 🎙️\n"
        "Пиши текст или отправляй голосовое — отвечу голосом и текстом.\n\n"
        "Умею:\n"
        "• /weather — погода\n"
        "• /time    — время\n"
        "• /help    — помощь"
    )

async def cmd_weather(update: Update, context):
    text = skill_weather("")
    await update.message.reply_text(text)
    await update.message.reply_voice(voice=make_voice(text))

async def cmd_time(update: Update, context):
    text = skill_time("")
    await update.message.reply_text(text)
    await update.message.reply_voice(voice=make_voice(text))

async def cmd_help(update: Update, context):
    text = (
        "Что я умею:\n"
        "— отвечать на приветствия, шутки, вопросы о себе\n"
        "— говорить время и погоду\n"
        "— считать: «посчитай пять плюс три»\n"
        "— принимать голосовые сообщения\n"
    )
    await update.message.reply_text(text)

async def handle_text(update: Update, context):
    user_text = update.message.text or ""
    response  = bot(user_text)
    await update.message.reply_text(response)
    try:
        await update.message.reply_voice(voice=make_voice(response))
    except Exception as e:
        logger.warning("TTS error: %s", e)

async def handle_voice(update: Update, context):
    """Голосовое → STT через Telegram (получаем файл) → bot() → ответ."""
    try:
        # Скачиваем ogg файл
        voice_file = await update.message.voice.get_file()
        ogg_buf = io.BytesIO()
        await voice_file.download_to_memory(ogg_buf)
        ogg_buf.seek(0)

        # STT через SpeechRecognition (Google, бесплатно)
        import speech_recognition as sr
        from pydub import AudioSegment

        audio = AudioSegment.from_ogg(ogg_buf)
        wav_buf = io.BytesIO()
        audio.export(wav_buf, format="wav")
        wav_buf.seek(0)

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_buf) as source:
            audio_data = recognizer.record(source)
        user_text = recognizer.recognize_google(audio_data, language="ru-RU")

        await update.message.reply_text(f"🎙 Я услышал: *{user_text}*", parse_mode="Markdown")
        response = bot(user_text)

    except Exception as e:
        logger.warning("STT error: %s", e)
        response = "Не смог распознать голос. Попробуй написать текстом."

    await update.message.reply_text(response)
    try:
        await update.message.reply_voice(voice=make_voice(response))
    except Exception as e:
        logger.warning("TTS error: %s", e)

# ── FastAPI + PTB Application ──────────────────────────────────────────────

app = FastAPI()

# Строим PTB Application один раз
ptb_app = (
    Application.builder()
    .token(BOT_TOKEN)
    .updater(None)          # вебхук — updater не нужен
    .build()
)

ptb_app.add_handler(CommandHandler("start",   cmd_start))
ptb_app.add_handler(CommandHandler("weather", cmd_weather))
ptb_app.add_handler(CommandHandler("time",    cmd_time))
ptb_app.add_handler(CommandHandler("help",    cmd_help))
ptb_app.add_handler(MessageHandler(filters.VOICE,                  handle_voice))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


@app.on_event("startup")
async def on_startup():
    await ptb_app.initialize()
    webhook = f"{WEBHOOK_URL}/webhook"
    await ptb_app.bot.set_webhook(webhook)
    logger.info("Webhook set: %s", webhook)


@app.on_event("shutdown")
async def on_shutdown():
    await ptb_app.bot.delete_webhook()
    await ptb_app.shutdown()


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, ptb_app.bot)
    await ptb_app.process_update(update)
    return Response(status_code=200)


@app.get("/")
async def healthcheck():
    return {"status": "ok"}


# ── локальный запуск (для тестирования без Railway) ───────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("tg_atabay:app", host="0.0.0.0", port=PORT, reload=False)
