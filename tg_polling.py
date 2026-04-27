# tg_polling.py

"""
tg_local.py — локальная версия Telegram-бота (polling).
Никаких webhook и FastAPI — просто запуск через python.

Нужно только:
BOT_TOKEN=токен
в .env
"""

import os
import io
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from gtts import gTTS
from dotenv import load_dotenv

# ── импортируем NLP из bot.py ─────────────────────────────────────────────
from bot import bot, INTENTS, filter_text, skill_weather, skill_time

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]

# ── TTS helper ────────────────────────────────────────────────────────────

def make_voice(text: str) -> io.BytesIO:
    """Генерирует mp3 через gTTS и возвращает BytesIO."""
    tts = gTTS(text=text, lang="ru")
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    buf.name = "response.mp3"
    return buf


# ── команды ───────────────────────────────────────────────────────────────

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


# ── текст ─────────────────────────────────────────────────────────────────

async def handle_text(update: Update, context):
    user_text = update.message.text or ""
    response = bot(user_text)

    await update.message.reply_text(response)

    try:
        await update.message.reply_voice(voice=make_voice(response))
    except Exception as e:
        logger.warning("TTS error: %s", e)


# ── голос ─────────────────────────────────────────────────────────────────

async def handle_voice(update: Update, context):
    try:
        voice_file = await update.message.voice.get_file()

        ogg_buf = io.BytesIO()
        await voice_file.download_to_memory(ogg_buf)
        ogg_buf.seek(0)

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

        await update.message.reply_text(
            f"🎙 Я услышал: *{user_text}*",
            parse_mode="Markdown"
        )

        response = bot(user_text)

    except Exception as e:
        logger.warning("STT error: %s", e)
        response = "Не смог распознать голос. Попробуй написать текстом."

    await update.message.reply_text(response)

    try:
        await update.message.reply_voice(voice=make_voice(response))
    except Exception as e:
        logger.warning("TTS error: %s", e)


# ── запуск ────────────────────────────────────────────────────────────────

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("weather", cmd_weather))
    application.add_handler(CommandHandler("time", cmd_time))
    application.add_handler(CommandHandler("help", cmd_help))

    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
    )

    print("Бот запущен локально...")
    application.run_polling()


if __name__ == "__main__":
    main()