import os
import asyncio
import random
import sqlite3
import threading
import logging
from datetime import datetime
from contextlib import closing

from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

TOKEN = os.getenv("TOKEN")

ADMINS = [1739947062, 5655991466]

INFO_CHANNEL = "https://t.me/+rFs7nnx639BmNzgy"
FLUD_LINK = "https://t.me/+zTukwrwrgxOGUy"
FLUD_CHAT_ID = int(os.getenv("FLUD_CHAT_ID", "-1000000000000"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

QUOTES = [f"✨ Цитата №{i}. Каждая история начинается с первого сообщения." for i in range(1, 101)]
ATMOSPHERES = [f"🌙 Атмосфера №{i}. За каждым сообщением скрывается новая история." for i in range(1, 51)]

RULES_TEXT = """
<b>📖 Правила</b>

━━━━━━━━━━━━━━
✨ Уважайте участников и их роли.
✨ Не провоцируйте конфликты.
✨ Сохраняйте атмосферу ролевого общения.
✨ Администрация всегда имеет финальное слово.
━━━━━━━━━━━━━━
"""

FAQ_TEXT = """
<b>❓ FAQ</b>

━━━━━━━━━━━━━━
• Как попасть во флуд?
— Заполнить анкету и пройти проверку.

• Когда рассмотрят заявку?
— Обычно в течение ближайшего времени после проверки.

• Можно ли менять роль?
— Да, через повторную анкету.
━━━━━━━━━━━━━━
"""

ABOUT_TEXT = """
<b>🎭 О флуде</b>
━━━━━━━━━━━━━━
Это место для общения, сюжетов, ролевых сцен и идей.
Каждый участник создаёт свою историю.
━━━━━━━━━━━━━━
"""

FANDOMS_TEXT = """
<b>🌍 Фандомы</b>
━━━━━━━━━━━━━━
Фандом — это мир, из которого пришёл ваш персонаж.

📌 Это может быть:
• Фильмы / сериалы (Marvel, Harry Potter)
• Аниме (Naruto, Jujutsu Kaisen)
• Игры (Genshin Impact, Minecraft)
• Или полностью ваш оригинальный мир

✨ Можно также придумать свой фандом (ориджинал вселенная)
━━━━━━━━━━━━━━
"""

WELCOME = """
<b>✨ Добро пожаловать ✨</b>
━━━━━━━━━━━━━━
<i>Каждая история начинается с первого сообщения.</i>
━━━━━━━━━━━━━━
"""

# ---------------- DB ----------------

def db():
    return sqlite3.connect("flud.db", check_same_thread=False)


def init_db():
    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT,
            fandom TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            admin_id INTEGER,
            action TEXT,
            created_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS bans(
            user_id INTEGER PRIMARY KEY,
            admin_id INTEGER,
            created_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS applications(
            user_id INTEGER PRIMARY KEY,
            msg_admin_1 INTEGER,
            msg_admin_2 INTEGER
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS applications_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            role TEXT,
            fandom TEXT,
            status TEXT,
            admin_id INTEGER,
            created_at TEXT
        )
        """)

        conn.commit()


def now():
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def user_status(user_id):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("SELECT status FROM users WHERE user_id=?", (user_id,))
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.exception(e)
        return None


def save_user(user_id, username):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT OR IGNORE INTO users(user_id,username,created_at)
            VALUES(?,?,?)
            """, (user_id, username, now()))
            conn.commit()
    except Exception as e:
        logger.exception(e)


def update_profile(user_id, role, fandom):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            UPDATE users SET role=?, fandom=?, status='pending'
            WHERE user_id=?
            """, (role, fandom, user_id))
            conn.commit()
    except Exception as e:
        logger.exception(e)


def update_status(user_id, status):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            UPDATE users SET status=? WHERE user_id=?
            """, (status, user_id))
            conn.commit()
    except Exception as e:
        logger.exception(e)


def add_log(user_id, admin_id, action):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO logs(user_id,admin_id,action,created_at)
            VALUES(?,?,?,?)
            """, (user_id, admin_id, action, now()))
            conn.commit()
    except Exception as e:
        logger.exception(e)


def save_application(user_id, m1, m2):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT OR REPLACE INTO applications(user_id,msg_admin_1,msg_admin_2)
            VALUES(?,?,?)
            """, (user_id, m1, m2))
            conn.commit()
    except Exception as e:
        logger.exception(e)


def get_application(user_id):
    try:
        with closing(db()) as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT msg_admin_1,msg_admin_2 FROM applications WHERE user_id=?
            """, (user_id,))
            return cur.fetchone()
    except Exception as e:
        logger.exception(e)
        return None


# ---------------- FSM ----------------

class Register(StatesGroup):
    question = State()
    role = State()
    fandom = State()


# ---------------- KEYBOARDS ----------------

def info_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Инфо-канал", url=INFO_CHANNEL)],
        [InlineKeyboardButton(text="✅ Ознакомился", callback_data="read_info")]
    ])


def pending_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Правила", callback_data="rules")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="faq")],
        [InlineKeyboardButton(text="🎭 О флуде", callback_data="about")],
        [InlineKeyboardButton(text="🌍 Фандомы", callback_data="fandoms")]
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="users")],
        [InlineKeyboardButton(text="📨 Заявки", callback_data="apps")],
        [InlineKeyboardButton(text="📜 История", callback_data="history")]
    ])


# ---------------- FLASK ----------------

@app.route("/")
def home():
    return "BOT ONLINE"


def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))


# ---------------- SAFE SEND ----------------

async def safe_send(admin, text, kb):
    try:
        return await bot.send_message(admin, text, reply_markup=kb)
    except Exception as e:
        logger.exception(e)
        return None


# ---------------- START ----------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    try:
        username = f"@{message.from_user.username}" if message.from_user.username else "Не указан"
        save_user(message.from_user.id, username)

        if user_status(message.from_user.id) == "banned":
            await message.answer("🚫 Вы заблокированы.")
            return

        await state.clear()

        await message.answer(WELCOME + "\n\n" + random.choice(QUOTES), reply_markup=info_kb())
    except Exception as e:
        logger.exception(e)


@dp.callback_query(F.data == "read_info")
async def read_info(call: CallbackQuery, state: FSMContext):
    try:
        await state.set_state(Register.question)
        await call.message.answer("❓ Проверочный вопрос:\nМаксимальный срок реста?")
        await call.answer()
    except Exception as e:
        logger.exception(e)


@dp.message(Register.question)
async def q_step(message: Message, state: FSMContext):
    try:
        if message.text.lower().strip() != "3 недели":
            await message.answer("🚫 Неверно")
            return
        await state.set_state(Register.role)
        await message.answer("🎭 Роль?\n<i>Кто ваш персонаж или какую роль вы играете в мире.</i>")
    except Exception as e:
        logger.exception(e)


@dp.message(Register.role)
async def role_step(message: Message, state: FSMContext):
    try:
        await state.update_data(role=message.text)
        await state.set_state(Register.fandom)
        await message.answer(
            "🌍 Фандом?\n"
            "<i>Фандом — это мир/вселенная, откуда ваш персонаж.\n"
            "Например: Harry Potter, Naruto, Genshin Impact или ваш оригинальный мир.</i>"
        )
    except Exception as e:
        logger.exception(e)


@dp.message(Register.fandom)
async def fandom_step(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        role = data["role"]
        fandom = message.text

        update_profile(message.from_user.id, role, fandom)

        username = f"@{message.from_user.username}" if message.from_user.username else "Не указан"

        text = f"""
📨 <b>Новая заявка</b>

━━━━━━━━━━━━━━
👤 Пользователь: {username}
🆔 ID: {message.from_user.id}
🎭 Роль: {role}
🌍 Фандом: {fandom}
🕰 Время: {now()}
━━━━━━━━━━━━━━
"""

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept:{message.from_user.id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{message.from_user.id}")],
            [InlineKeyboardButton(text="🚫 Бан", callback_data=f"ban:{message.from_user.id}")]
        ])

        ids = []
        for admin in ADMINS:
            msg = await safe_send(admin, text, kb)
            ids.append(msg.message_id if msg else 0)

        save_application(message.from_user.id, ids[0], ids[1])

        await message.answer("📨 Заявка отправлена", reply_markup=pending_menu())
        await state.clear()

    except Exception as e:
        logger.exception(e)
