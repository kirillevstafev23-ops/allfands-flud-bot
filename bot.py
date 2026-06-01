import os
import asyncio
import sqlite3
import logging
import time
from datetime import datetime
from contextlib import closing

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# ---------------- CONFIG ----------------

TOKEN = os.getenv("TOKEN")

ADMINS = [1739947062, 5655991466]

INFO_CHANNEL = "https://t.me/+rFs7nnx639BmNzgy"
FLUD_LINK = "https://t.me/+zTukwrwrqlgxOGUy"

# ---------------- BOT ----------------

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

# ---------------- ANTI-SPAM ----------------

last_action = {}
SPAM_DELAY = 8

def spam(user_id: int):
    now = time.time()
    if now - last_action.get(user_id, 0) < SPAM_DELAY:
        return True
    last_action[user_id] = now
    return False

# ---------------- DB ----------------

def db():
    return sqlite3.connect("bot.db", check_same_thread=False)

def init_db():
    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT,
            fandom TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT
        )
        """)

        conn.commit()

def now():
    return datetime.now().strftime("%d.%m.%Y %H:%M")

def save_user(uid, username):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO users(user_id, username, created_at)
        VALUES (?, ?, ?)
        """, (uid, username, now()))
        conn.commit()

def get_status(uid):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM users WHERE user_id=?", (uid,))
        row = cur.fetchone()
        return row[0] if row else None

def set_status(uid, status):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET status=? WHERE user_id=?", (status, uid))
        conn.commit()

def update_profile(uid, role, fandom):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
        UPDATE users SET role=?, fandom=?, status='pending'
        WHERE user_id=?
        """, (role, fandom, uid))
        conn.commit()

# ---------------- FSM ----------------

class Form(StatesGroup):
    question = State()
    role = State()
    fandom = State()

# ---------------- UI ----------------

def start_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Официальный инфо-канал", url=INFO_CHANNEL)],
        [InlineKeyboardButton(text="✨ Начать регистрацию", callback_data="start_form")]
    ])

def admin_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"accept:{uid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{uid}")
        ],
        [InlineKeyboardButton(text="🚫 Бан", callback_data=f"ban:{uid}")]
    ])

# ---------------- START ----------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):

    if spam(message.from_user.id):
        await message.answer("⏳ Пожалуйста, не спамьте.")
        return

    save_user(
        message.from_user.id,
        f"@{message.from_user.username}" if message.from_user.username else "no_username"
    )

    if get_status(message.from_user.id) == "banned":
        await message.answer("🚫 Вы заблокированы.")
        return

    await state.clear()

    text = (
        "🌙 <b>Добро пожаловать!</b>\n\n"
        "━━━━━━━━━━━━━━\n"
        "✨ Здесь ты можешь подать заявку на вступление во флуд-сообщество.\n\n"
        "📌 Перед началом обязательно ознакомься с информацией в канале.\n"
        "━━━━━━━━━━━━━━\n\n"
        "💬 Нажми кнопку ниже, чтобы продолжить."
    )

    await message.answer(text, reply_markup=start_kb())

# ---------------- STEP 1 ----------------

@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):

    if spam(call.from_user.id):
        await call.answer("⏳ Подождите немного")
        return

    await state.set_state(Form.question)

    await call.message.answer(
        "🧠 <b>Проверочный вопрос</b>\n\n"
        "Сколько длится рест?\n\n"
        "✍️ Ответьте одним сообщением."
    )

    await call.answer()

# ---------------- STEP 2 ----------------

@dp.message(Form.question)
async def question(message: Message, state: FSMContext):

    if message.text.lower().strip() != "3 недели":
        await message.answer("❌ Неверный ответ. Попробуйте ещё раз.")
        return

    await state.set_state(Form.role)

    await message.answer(
        "🎭 <b>Отлично!</b>\n\n"
        "Теперь укажите вашу роль."
    )

# ---------------- STEP 3 ----------------

@dp.message(Form.role)
async def role(message: Message, state: FSMContext):

    await state.update_data(role=message.text)
    await state.set_state(Form.fandom)

    await message.answer(
        "🌍 <b>Хорошо!</b>\n\n"
        "Теперь укажите ваш фандом."
    )

# ---------------- STEP 4 ----------------

@dp.message(Form.fandom)
async def fandom(message: Message, state: FSMContext):

    if spam(message.from_user.id):
        await message.answer("⏳ Подождите немного.")
        return

    if get_status(message.from_user.id) == "pending":
        await message.answer("⚠️ Вы уже отправили заявку.")
        return

    data = await state.get_data()

    role = data["role"]
    fandom = message.text

    update_profile(message.from_user.id, role, fandom)
    set_status(message.from_user.id, "pending")

    username = f"@{message.from_user.username}" if message.from_user.username else "no_username"

    text = (
        "📨 <b>НОВАЯ ЗАЯВКА</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 Пользователь: {username}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"🎭 Роль: {role}\n"
        f"🌍 Фандом: {fandom}\n"
        f"🕰 Время: {now()}\n"
        "━━━━━━━━━━━━━━"
    )

    for admin in ADMINS:
        await bot.send_message(admin, text, reply_markup=admin_kb(message.from_user.id))

    await message.answer(
        "✅ <b>Заявка успешно отправлена!</b>\n\n"
        "⏳ Ожидайте ответа администрации."
    )

    await state.clear()

# ---------------- ADMIN ACTIONS ----------------

def is_admin(uid):
    return uid in ADMINS

@dp.callback_query(F.data.startswith("accept:"))
async def accept(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    uid = int(call.data.split(":")[1])

    set_status(uid, "accepted")

    await bot.send_message(
        uid,
        "🎉 <b>Поздравляем!</b>\n\n"
        "Ваша заявка одобрена.\n\n"
        f"👉 {FLUD_LINK}"
    )

    await call.message.edit_text("✅ ЗАЯВКА ПРИНЯТА")
    await call.answer()


@dp.callback_query(F.data.startswith("reject:"))
async def reject(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    uid = int(call.data.split(":")[1])

    set_status(uid, "rejected")

    await bot.send_message(
        uid,
        "❌ <b>К сожалению</b>\n\n"
        "Ваша заявка отклонена."
    )

    await call.message.edit_text("❌ ЗАЯВКА ОТКЛОНЕНА")
    await call.answer()


@dp.callback_query(F.data.startswith("ban:"))
async def ban(call: CallbackQuery):

    if not is_admin(call.from_user.id):
        return

    uid = int(call.data.split(":")[1])

    set_status(uid, "banned")

    await bot.send_message(uid, "🚫 Вы были заблокированы.")

    await call.message.edit_text("🚫 ПОЛЬЗОВАТЕЛЬ ЗАБАНЕН")
    await call.answer()

# ---------------- MAIN ----------------

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
