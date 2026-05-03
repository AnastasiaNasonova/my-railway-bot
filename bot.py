from aiogram import Dispatcher, Bot, types
from config import TELEGRAM_BOT_TOKEN
from random import choice

# Создаем объекты бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

# Варианты ответов
predicts =[
    'Вижу, на канал ты подпишешься!',
    'Сегодня тебя ждёт успех!',
    'Сегодня ты научишься пользоваться хуками!'
]

# Обработчик команды /start
@dp.message_handler(commands="start")
async def start(message: types.Message):
    answer = choice(predicts)
    await message.answer(f"{message.from_user.full_name}, {answer}")