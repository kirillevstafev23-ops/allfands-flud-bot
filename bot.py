import os
import asyncio
import sqlite3
import time
import logging
from datetime import datetime
from contextlib import closing

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

TOKEN = os.getenv("TOKEN")

ADMINS = [
    1739947062,
    5655991466
]

INFO_CHANNEL = "https://t.me/+rFs7nnx639BmNzgy"
MAIN_LINK = "https://t.me/+zTukwrwrqlgxOGUy"

SPAM_DELAY = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

if not TOKEN:
    raise ValueError("TOKEN environment variable not found")

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher(storage=MemoryStorage())

user_last_action = {}

admin_reply_targets = {}

DB_NAME = "bot.db"


def is_spam(user_id: int) -> bool:
    now_time = time.time()

    if user_id in user_last_action:
        if now_time - user_last_action[user_id] < SPAM_DELAY:
            return True

    user_last_action[user_id] = now_time
    return False


def get_db():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def init_db():
    with closing(get_db()) as conn:
        cursor = conn.cursor()

        cursor.execute("""
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


def current_time():
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


def save_user(user_id: int, username: str):
    with closing(get_db()) as conn:
        cursor = conn.cursor()

        cursor.execute("""
        INSERT OR IGNORE INTO users(
            user_id,
            username,
            created_at
        )
        VALUES (?, ?, ?)
        """, (
            user_id,
            username,
            current_time()
        ))

        conn.commit()


def get_status(user_id: int):
    with closing(get_db()) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT status FROM users WHERE user_id=?",
            (user_id,)
        )

        row = cursor.fetchone()

        if row:
            return row[0]

        return None


def set_status(user_id: int, status: str):
    with closing(get_db()) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET status=? WHERE user_id=?",
            (status, user_id)
        )

        conn.commit()


def update_profile(user_id: int, role: str, fandom: str):
    with closing(get_db()) as conn:
        cursor = conn.cursor()

        cursor.execute("""
        UPDATE users
        SET role=?,
            fandom=?,
            status='pending'
        WHERE user_id=?
        """, (
            role,
            fandom,
            user_id
        ))

        conn.commit()


class Form(StatesGroup):
    question = State()
    role = State()
    fandom = State()

    support_message = State()
    admin_reply = State()


def start_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✦ Информационный канал",
                    url=INFO_CHANNEL
                )
            ],
            [
                InlineKeyboardButton(
                    text="✦ Продолжить путь",
                    callback_data="start_form"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🆘 Техподдержка",
                    callback_data="support"
                )
            ]
        ]
    )


def admin_keyboard(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять",
                    callback_data=f"accept:{user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⛔ Бан",
                    callback_data=f"ban:{user_id}"
                )
            ]
        ]
    )


def is_admin(user_id: int):
    return user_id in ADMINS


@dp.message(CommandStart())
async def start_handler(
    message: Message,
    state: FSMContext
):
    try:
        user_id = message.from_user.id

        if is_spam(user_id):
            await message.answer(
                "⏳ Подождите несколько секунд."
            )
            return

        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else "no_username"
        )

        save_user(user_id, username)

        if get_status(user_id) == "banned":
            await message.answer(
                "⛔ Вам запрещено пользоваться ботом."
            )
            return

        await state.clear()

        text = (
            "𖤐 <b>Добро пожаловать.</b>\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Иногда путь начинается не с шага,\n"
            "а с решения открыть дверь.\n\n"
            "Перед тобой небольшая анкета.\n"
            "Пройди её и дождись решения администрации.\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Сначала ознакомься с информацией."
        )

        await message.answer(
            text,
            reply_markup=start_keyboard()
        )

    except Exception as e:
        logging.exception(e)


@dp.callback_query(F.data == "start_form")
async def start_form(
    call: CallbackQuery,
    state: FSMContext
):
    try:
        if get_status(call.from_user.id) == "banned":
            await call.answer(
                "Доступ запрещён",
                show_alert=True
            )
            return

        await state.set_state(Form.question)

        await call.message.answer(
            "✦ Контрольный вопрос\n\n"
            "<b>Какой максимальный срок реста?</b>\n\n"
            "Отправьте ответ сообщением."
        )

        await call.answer()

    except Exception as e:
        logging.exception(e)


@dp.message(Form.question)
async def question_step(
    message: Message,
    state: FSMContext
):
    try:
        answer = message.text.strip().lower()

        if answer != "3 недели":
            await message.answer(
                "❌ Неверно.\nПопробуйте ещё раз."
            )
            return

        await state.set_state(Form.role)

        await message.answer(
            "✅ Верно.\n\nТеперь укажите вашу роль."
        )

    except Exception as e:
        logging.exception(e)


@dp.message(Form.role)
async def role_step(
    message: Message,
    state: FSMContext
):
    try:
        await state.update_data(
            role=message.text.strip()
        )

        await state.set_state(Form.fandom)

        await message.answer(
            "✦ Укажите ваш фандом."
        )

    except Exception as e:
        logging.exception(e)


@dp.message(Form.fandom)
async def fandom_step(
    message: Message,
    state: FSMContext
):
    try:
        data = await state.get_data()

        role = data.get("role")
        fandom = message.text.strip()

        username = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else "no_username"
        )

        update_profile(
            message.from_user.id,
            role,
            fandom
        )

        set_status(
            message.from_user.id,
            "pending"
        )

        application_text = (
            "📨 <b>Новая заявка</b>\n\n"
            f"👤 Username: {username}\n"
            f"🆔 ID: <code>{message.from_user.id}</code>\n"
            f"🎭 Роль: {role}\n"
            f"🌌 Фандом: {fandom}\n"
            f"🕒 Время: {current_time()}"
        )

        sent_count = 0

        for admin in ADMINS:
            try:
                await bot.send_message(
                    admin,
                    application_text,
                    reply_markup=admin_keyboard(
                        message.from_user.id
                    )
                )
                sent_count += 1

            except Exception as admin_error:
                logging.exception(
                    f"Failed to send application to admin {admin}: {admin_error}"
                )

        if sent_count == 0:
            await message.answer(
                "❌ Ошибка отправки заявки. Сообщите администрации."
            )
            await state.clear()
            return

        await message.answer(
            "✅ Анкета успешно отправлена.\n\n"
            "Ожидайте решения администрации."
        )

        await state.clear()

    except Exception as e:
        logging.exception(e)
        await state.clear()


@dp.callback_query(F.data.startswith("accept:"))
async def accept_application(
    call: CallbackQuery
):
    try:
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        user_id = int(
            call.data.split(":")[1]
        )

        set_status(
            user_id,
            "accepted"
        )

        try:
            await bot.send_message(
                user_id,
                (
                    "🎉 <b>Ваша заявка одобрена.</b>\n\n"
                    "Добро пожаловать.\n\n"
                    f"{MAIN_LINK}"
                )
            )
        except Exception as user_error:
            logging.exception(user_error)

        await call.message.edit_reply_markup(
            reply_markup=None
        )

        await call.message.answer(
            f"✅ Заявка пользователя <code>{user_id}</code> принята"
        )

        await call.answer(
            "Принято"
        )

    except Exception as e:
        logging.exception(e)


@dp.callback_query(F.data.startswith("reject:"))
async def reject_application(
    call: CallbackQuery
):
    try:
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        user_id = int(
            call.data.split(":")[1]
        )

        set_status(
            user_id,
            "rejected"
        )

        try:
            await bot.send_message(
                user_id,
                "❌ Ваша заявка была отклонена."
            )
        except Exception as user_error:
            logging.exception(user_error)

        await call.message.edit_reply_markup(
            reply_markup=None
        )

        await call.message.answer(
            f"❌ Заявка пользователя <code>{user_id}</code> отклонена"
        )

        await call.answer(
            "Отклонено"
        )

    except Exception as e:
        logging.exception(e)


@dp.callback_query(F.data.startswith("ban:"))
async def ban_application(
    call: CallbackQuery
):
    try:
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        user_id = int(
            call.data.split(":")[1]
        )

        set_status(
            user_id,
            "banned"
        )

        try:
            await bot.send_message(
                user_id,
                "⛔ Вы были заблокированы."
            )
        except Exception as user_error:
            logging.exception(user_error)

        await call.message.edit_reply_markup(
            reply_markup=None
        )

        await call.message.answer(
            f"⛔ Пользователь <code>{user_id}</code> заблокирован"
        )

        await call.answer(
            "Пользователь заблокирован"
        )

    except Exception as e:
        logging.exception(e)

@dp.callback_query(F.data == "support")
async def support_start(
    call: CallbackQuery,
    state: FSMContext
):
    await state.set_state(Form.support_message)

    await call.message.answer(
        "✉️ Напишите ваше обращение одним сообщением."
    )

    await call.answer()


@dp.message(Form.support_message)
async def support_send(
    message: Message,
    state: FSMContext
):
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "no_username"
    )

    text = (
        "🆘 <b>Новое обращение</b>\n\n"
        f"👤 {username}\n"
        f"🆔 <code>{message.from_user.id}</code>\n\n"
        f"{message.text}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✉️ Ответить",
                    callback_data=f"reply:{message.from_user.id}"
                )
            ]
        ]
    )

    for admin in ADMINS:
        await bot.send_message(
            admin,
            text,
            reply_markup=keyboard
        )

    await message.answer(
        "✅ Ваше обращение отправлено администрации."
    )

    await state.clear()


@dp.callback_query(F.data.startswith("reply:"))
async def reply_to_user(
    call: CallbackQuery,
    state: FSMContext
):
    if not is_admin(call.from_user.id):
        return

    user_id = int(call.data.split(":")[1])

    admin_reply_targets[call.from_user.id] = user_id

    await state.set_state(Form.admin_reply)

    await call.message.answer(
        f"✉️ Напишите ответ пользователю {user_id}"
    )

    await call.answer()


@dp.message(Form.admin_reply)
async def send_admin_reply(
    message: Message,
    state: FSMContext
):
    if not is_admin(message.from_user.id):
        return

    user_id = admin_reply_targets.get(
        message.from_user.id
    )

    if not user_id:
        await message.answer(
            "Ошибка. Пользователь не найден."
        )
        return

    try:
        await bot.send_message(
            user_id,
            (
                "📩 <b>Ответ администрации</b>\n\n"
                f"{message.text}"
            )
        )

        await message.answer(
            "✅ Ответ отправлен."
        )

    except Exception:
        await message.answer(
            "❌ Не удалось отправить ответ."
        )

    admin_reply_targets.pop(
        message.from_user.id,
        None
    )

    await state.clear()


@dp.error()
async def error_handler(event, exception):
    logging.exception(
        f"Unhandled error: {exception}"
    )
    return True


async def main():
    init_db()

    logging.info("Bot started")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )


if __name__ == "__main__":
    asyncio.run(main())
