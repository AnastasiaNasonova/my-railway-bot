# bot.py

"""
Локальный голосовой бот с фоновым прослушиванием (Vosk + gTTS).
Все интенты из предыдущей работы сохранены + 3 навыка.

Запуск:  python bot.py
"""

import json
import re
import random
import threading
import queue
import sys
import os
import webbrowser
import subprocess
import datetime

import nltk
import pyaudio
import vosk
from gtts import gTTS
import pygame

# ─── sklearn (из предыдущей работы) ───────────────────────────────────────────
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.ensemble import RandomForestClassifier

# ──────────────────────────────────────────────────────────────────────────────
# INTENTS (все из предыдущей работы)
# ──────────────────────────────────────────────────────────────────────────────
INTENTS = {
    "hello": {
        "examples": ["привет", "здравствуйте", "добрый день", "как дела"],
        "responses": ["Йоу", "Здарова", "Приветствую тебя человек.", "Функционирую нормально"],
    },
    "bye": {
        "examples": ["пока", "до свидания", "всего хорошего"],
        "responses": ["Давайдосвиданья", "И вам приятного денечка"],
    },
    "buy_some_pizza": {
        "examples": ["голоден", "хочу есть", "пицца"],
        "responses": ["А вот фиг тебе"],
    },
    "thanks": {
        "examples": ["спасибо", "благодарю", "спс", "спасибо большое"],
        "responses": ["Всегда пожалуйста", "Обращайся", "Не за что"],
    },
    "how_are_you": {
        "examples": ["как ты", "как жизнь", "как сам", "как поживаешь"],
        "responses": ["Живу в коде", "Не жалуюсь", "Лучше всех"],
    },
    "weather": {
        "examples": ["какая погода", "что по погоде", "холодно", "жарко", "погода"],
        "responses": ["__SKILL_WEATHER__"],       # ← навык
    },
    "joke": {
        "examples": ["расскажи шутку", "пошути", "анекдот", "рассмеши меня"],
        "responses": ["Колобок повесился", "Я бы пошутил, но ты не поймешь", "404 шутка не найдена"],
    },
    "time": {
        "examples": ["сколько времени", "который час", "время", "скажи время"],
        "responses": ["__SKILL_TIME__"],           # ← навык
    },
    "help": {
        "examples": ["помоги", "нужна помощь", "что ты умеешь", "помощь"],
        "responses": ["Могу поговорить", "Могу не помочь", "Задай вопрос нормально"],
    },
    "music": {
        "examples": ["включи музыку", "музыка", "хочу трек", "поставь песню"],
        "responses": ["Воображаемая музыка включена", "Танцуй молча", "Представь бит"],
    },
    "age": {
        "examples": ["сколько тебе лет", "твой возраст", "ты старый", "когда ты родился"],
        "responses": ["Я вне времени", "Возраст засекречен", "Старше твоего калькулятора"],
    },
    "name": {
        "examples": ["как тебя зовут", "твое имя", "кто ты", "представься"],
        "responses": ["Я просто бот", "Имя мне не дали", "Зови меня как хочешь"],
    },
    "sleep": {
        "examples": ["хочу спать", "я устал", "спать пора", "сонный"],
        "responses": ["Иди вздремни", "Сон — это важно", "Закрывай глаза и оффлайн"],
    },
    "bored": {
        "examples": ["мне скучно", "скука", "нечего делать", "развлеки меня"],
        "responses": ["Попробуй подумать", "Скука — двигатель креатива", "Иди кодить"],
    },
    "food": {
        "examples": ["что поесть", "посоветуй еду", "хочу вкусное", "что приготовить"],
        "responses": ["Открой холодильник", "Закажи пиццу", "Еда сама себя не съест"],
    },
    # ── НАВЫК 1: открыть браузер ──────────────────────────────────────────────
    "open_browser": {
        "examples": [
            "открой браузер", "открой гугл", "открой сайт", "открой ютуб",
            "запусти браузер", "перейди на сайт",
        ],
        "responses": ["__SKILL_BROWSER__"],        # ← навык
    },
    # ── НАВЫК 2: калькулятор ─────────────────────────────────────────────────
    "calculator": {
        "examples": [
            "посчитай", "сколько будет", "вычисли", "реши пример",
            "два плюс два", "пять умножить на три", "раздели", "сложи",
        ],
        "responses": ["__SKILL_CALC__"],           # ← навык
    },
}

with open('big_bot_config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)
    INTENTS.update(config.get('intents', {}))


SKILL_MARKERS = {"__SKILL_WEATHER__", "__SKILL_TIME__", "__SKILL_BROWSER__", "__SKILL_CALC__"}

# ──────────────────────────────────────────────────────────────────────────────
# НАВЫКИ
# ──────────────────────────────────────────────────────────────────────────────

def skill_weather(user_text: str) -> str:
    """Навык 1 — погода (через wttr.in, без API-ключа)."""
    try:
        import urllib.request
        url = "https://wttr.in/?format=3&lang=ru"
        with urllib.request.urlopen(url, timeout=4) as r:
            data = r.read().decode("utf-8").strip()
        return f"Погода: {data}"
    except Exception:
        return "Не смог получить погоду — нет интернета."


def skill_time(_: str) -> str:
    """Навык 2 — текущее время и дата."""
    now = datetime.datetime.now()
    return (
        f"Сейчас {now.hour} часов {now.minute:02d} минут, "
        f"{now.day} {_month_name(now.month)} {now.year} года."
    )


def _month_name(m: int) -> str:
    months = ["","января","февраля","марта","апреля","мая","июня",
               "июля","августа","сентября","октября","ноября","декабря"]
    return months[m]


def skill_browser(user_text: str) -> str:
    """Навык 3 — открыть браузер."""
    urls = {
        "ютуб": "https://youtube.com",
        "youtube": "https://youtube.com",
        "гугл": "https://google.com",
        "google": "https://google.com",
        "гитхаб": "https://github.com",
        "github": "https://github.com",
        "вконтакте": "https://vk.com",
        "вк": "https://vk.com",
    }
    text_lower = user_text.lower()
    for keyword, url in urls.items():
        if keyword in text_lower:
            webbrowser.open(url)
            return f"Открываю {keyword}."
    webbrowser.open("https://google.com")
    return "Открываю браузер."


def skill_calc(user_text: str) -> str:
    """Навык 4 — простой калькулятор. Понимает цифры и слова."""
    word_map = {
        "ноль": "0", "один": "1", "одну": "1", "два": "2", "две": "2",
        "три": "3", "четыре": "4", "пять": "5", "шесть": "6",
        "семь": "7", "восемь": "8", "девять": "9", "десять": "10",
        "плюс": "+", "минус": "-", "умножить": "*", "умножить на": "*",
        "разделить": "/", "разделить на": "/", "на": "*",
    }
    text = user_text.lower()
    for word, sym in sorted(word_map.items(), key=lambda x: -len(x[0])):
        text = text.replace(word, sym)
    # оставляем только цифры и операторы
    text = re.sub(r"[^\d\+\-\*\/\.\s]", "", text).strip()
    # убираем лишние пробелы вокруг операторов
    text = re.sub(r"\s+", "", text)
    if not text:
        return "Скажи пример, например: пять плюс три."
    try:
        result = eval(text, {"__builtins__": {}})   # noqa: S307
        return f"Результат: {result}"
    except Exception:
        return f"Не смог вычислить «{user_text}». Скажи пример понятнее."


SKILL_HANDLERS = {
    "__SKILL_WEATHER__": skill_weather,
    "__SKILL_TIME__":    skill_time,
    "__SKILL_BROWSER__": skill_browser,
    "__SKILL_CALC__":    skill_calc,
}

# ──────────────────────────────────────────────────────────────────────────────
# NLP — фильтр + ML-классификатор (из предыдущей работы)
# ──────────────────────────────────────────────────────────────────────────────

def filter_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return text


def _build_model():
    X, y = [], []
    for intent_name, data in INTENTS.items():
        for ex in data["examples"]:
            ex = filter_text(ex)
            if len(ex) >= 3:
                X.append(ex)
                y.append(intent_name)

    vec = CountVectorizer(ngram_range=(1, 2), analyzer="word", min_df=1)
    X_vec = vec.fit_transform(X)

    clf = RandomForestClassifier(
        n_estimators=200, max_depth=20, random_state=42,
        n_jobs=-1, class_weight="balanced"
    )
    clf.fit(X_vec, y)
    return vec, clf


print("Обучаю модель…")
vectorizer, model = _build_model()
print("Модель готова.")


def get_intent_ml(user_text: str) -> str:
    user_text = filter_text(user_text)
    vec_text = vectorizer.transform([user_text])
    return model.predict(vec_text)[0]


def get_response(intent: str, user_text: str) -> str:
    if intent not in INTENTS:
        return "Извините, я вас не понял."
    responses = INTENTS[intent]["responses"]
    chosen = random.choice(responses)
    if chosen in SKILL_HANDLERS:
        return SKILL_HANDLERS[chosen](user_text)
    return chosen


def bot(user_text: str) -> str:
    intent = get_intent_ml(user_text)
    return get_response(intent, user_text)

