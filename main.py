import asyncio
import time
import json
import os
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from telethon import TelegramClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database

user_client = None
router = Router()

class UserStates(StatesGroup):
    waiting_phone = State()
    waiting_code = State()
    waiting_message = State()
    selecting_chats = State()
    setting_interval = State()
    searching_chats = State()
    editing_broadcast = State()
    editing_message = State()
    editing_chats = State()
    editing_interval = State()

@router.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("У вас нет доступа к этому боту.")
        return

    await state.clear()
    keyboard = [
        [InlineKeyboardButton(text="🔐 Войти в аккаунт", callback_data="login")],
        [InlineKeyboardButton(text="📝 Создать рассылку", callback_data="create_broadcast")],
        [InlineKeyboardButton(text="📋 Мои рассылки", callback_data="my_broadcasts")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer(
        "Добро пожаловать в Telegram Sender Bot!\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

@router.callback_query(F.data == "login")
async def handle_login(callback: CallbackQuery, state: FSMContext):
    global user_client

    session_data = await database.get_user_session()
    if session_data and session_data[1] == 1:
        await callback.message.edit_text("Вы уже авторизованы!")
        await callback.answer()
        return

    user_client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await user_client.connect()

    if await user_client.is_user_authorized():
        await database.save_user_session("authorized")
        await callback.message.edit_text("✅ Авторизация успешна!")
    else:
        await state.set_state(UserStates.waiting_phone)
        await callback.message.edit_text(
            "Введите номер телефона в международном формате (например: +1234567890):"
        )
    await callback.answer()

@router.message(UserStates.waiting_phone)
async def handle_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)

    global user_client
    await user_client.send_code_request(phone)

    await state.set_state(UserStates.waiting_code)
    await message.answer("Введите код подтверждения, который пришел в Telegram:")

@router.message(UserStates.waiting_code)
async def handle_code(message: Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    phone = data.get('phone')

    global user_client
    try:
        await user_client.sign_in(phone, code)
        await database.save_user_session(phone)
        await state.clear()
        await message.answer("✅ Авторизация успешна!")
    except Exception as e:
        await message.answer(f"Ошибка авторизации: {str(e)}\nПопробуйте снова с /start")
        await state.clear()

@router.callback_query(F.data == "create_broadcast")
async def handle_create_broadcast(callback: CallbackQuery, state: FSMContext):
    session_data = await database.get_user_session()
    if not session_data or session_data[1] != 1:
        await callback.message.edit_text("Сначала войдите в аккаунт!")
        await callback.answer()
        return

    await state.set_state(UserStates.waiting_message)
    await state.update_data(selected_chats=[])
    await callback.message.edit_text(
        "Отправьте сообщение для рассылки.\n"
        "Можно отправить текст, фото или видео (с подписью или без)."
    )
    await callback.answer()

@router.message(UserStates.waiting_message)
async def handle_message_input(message: Message, state: FSMContext, bot: Bot):
    message_text = message.caption or message.text or ""
    media_path = None
    media_type = None

    os.makedirs('media', exist_ok=True)

    if message.photo:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        media_path = f"media/{photo.file_id}.jpg"
        await bot.download_file(file.file_path, media_path)
        media_type = "photo"
    elif message.video:
        video = message.video
        file = await bot.get_file(video.file_id)
        media_path = f"media/{video.file_id}.mp4"
        await bot.download_file(file.file_path, media_path)
        media_type = "video"

    await state.update_data(
        message_text=message_text,
        media_path=media_path,
        media_type=media_type
    )

    await state.set_state(UserStates.selecting_chats)
    await show_chats_list(message, state, page=0)

async def show_chats_list(message: Message, state: FSMContext, page=0):
    global user_client

    dialogs = []
    async for dialog in user_client.iter_dialogs():
        dialogs.append({
            'id': dialog.id,
            'name': dialog.name or "Без названия"
        })

    await state.update_data(all_chats=dialogs)
    data = await state.get_data()
    selected_chats = data.get('selected_chats', [])

    per_page = 8
    start = page * per_page
    end = start + per_page
    page_dialogs = dialogs[start:end]

    keyboard = []
    for dialog in page_dialogs:
        chat_id = dialog['id']
        selected = "✅ " if chat_id in selected_chats else ""
        keyboard.append([InlineKeyboardButton(
            text=f"{selected}{dialog['name']}",
            callback_data=f"chat_{chat_id}_{page}"
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page_{page-1}"))
    if end < len(dialogs):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"page_{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(text="🔍 Поиск", callback_data="search_chats")])
    keyboard.append([InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="confirm_chats")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    selected_count = len(selected_chats)

    await message.answer(
        f"Выберите чаты для рассылки (выбрано: {selected_count}):",
        reply_markup=reply_markup
    )

@router.callback_query(F.data.startswith("chat_"))
async def handle_chat_selection(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    chat_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    data = await state.get_data()
    selected_chats = data.get('selected_chats', [])

    if chat_id in selected_chats:
        selected_chats.remove(chat_id)
    else:
        selected_chats.append(chat_id)

    await state.update_data(selected_chats=selected_chats)

    dialogs = data.get('all_chats', [])
    per_page = 8
    start = page * per_page
    end = start + per_page
    page_dialogs = dialogs[start:end]

    keyboard = []
    for dialog in page_dialogs:
        chat_id_iter = dialog['id']
        selected = "✅ " if chat_id_iter in selected_chats else ""
        keyboard.append([InlineKeyboardButton(
            text=f"{selected}{dialog['name']}",
            callback_data=f"chat_{chat_id_iter}_{page}"
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page_{page-1}"))
    if end < len(dialogs):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"page_{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(text="🔍 Поиск", callback_data="search_chats")])
    keyboard.append([InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="confirm_chats")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    selected_count = len(selected_chats)

    await callback.message.edit_text(
        f"Выберите чаты для рассылки (выбрано: {selected_count}):",
        reply_markup=reply_markup
    )
    await callback.answer()

@router.callback_query(F.data.startswith("page_"))
async def handle_pagination(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[1])
    data = await state.get_data()

    dialogs = data.get('all_chats', [])
    selected_chats = data.get('selected_chats', [])

    per_page = 8
    start = page * per_page
    end = start + per_page
    page_dialogs = dialogs[start:end]

    keyboard = []
    for dialog in page_dialogs:
        chat_id = dialog['id']
        selected = "✅ " if chat_id in selected_chats else ""
        keyboard.append([InlineKeyboardButton(
            text=f"{selected}{dialog['name']}",
            callback_data=f"chat_{chat_id}_{page}"
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page_{page-1}"))
    if end < len(dialogs):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"page_{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(text="🔍 Поиск", callback_data="search_chats")])
    keyboard.append([InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="confirm_chats")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    selected_count = len(selected_chats)

    await callback.message.edit_text(
        f"Выберите чаты для рассылки (выбрано: {selected_count}):",
        reply_markup=reply_markup
    )
    await callback.answer()

@router.callback_query(F.data == "search_chats")
async def handle_search_request(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.searching_chats)
    await callback.message.edit_text("Введите название чата для поиска:")
    await callback.answer()

@router.message(UserStates.searching_chats)
async def handle_search_query(message: Message, state: FSMContext):
    search_query = message.text.strip().lower()
    data = await state.get_data()

    all_chats = data.get('all_chats', [])
    selected_chats = data.get('selected_chats', [])
    filtered_chats = [chat for chat in all_chats if search_query in chat['name'].lower()]

    if not filtered_chats:
        await message.answer("Чаты не найдены. Попробуйте другой запрос.")
        return

    keyboard = []
    for dialog in filtered_chats[:10]:
        chat_id = dialog['id']
        selected = "✅ " if chat_id in selected_chats else ""
        keyboard.append([InlineKeyboardButton(
            text=f"{selected}{dialog['name']}",
            callback_data=f"chat_{chat_id}_0"
        )])

    keyboard.append([InlineKeyboardButton(text="🔍 Новый поиск", callback_data="search_chats")])
    keyboard.append([InlineKeyboardButton(text="✅ Подтвердить выбор", callback_data="confirm_chats")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    selected_count = len(selected_chats)

    await state.set_state(UserStates.selecting_chats)
    await message.answer(
        f"Результаты поиска (выбрано: {selected_count}):",
        reply_markup=reply_markup
    )

@router.callback_query(F.data == "confirm_chats")
async def handle_confirm_chats(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_chats = data.get('selected_chats', [])

    if not selected_chats:
        await callback.answer("Выберите хотя бы один чат!", show_alert=True)
        return

    await state.set_state(UserStates.setting_interval)

    keyboard = [
        [InlineKeyboardButton(text="⏰ Раз в час", callback_data="interval_hour")],
        [InlineKeyboardButton(text="📅 Раз в день", callback_data="interval_day")],
        [InlineKeyboardButton(text="⚙️ Свой интервал", callback_data="custom_interval")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        "Выберите интервал отправки:",
        reply_markup=reply_markup
    )
    await callback.answer()

@router.callback_query(F.data.startswith("interval_"))
async def handle_interval_selection(callback: CallbackQuery, state: FSMContext):
    interval_type = callback.data.split("_")[1]
    interval_seconds = config.INTERVALS.get(interval_type)

    data = await state.get_data()
    chat_ids_json = json.dumps(data['selected_chats'])
    next_send_time = int(time.time()) + interval_seconds

    await database.save_scheduled_message(
        data['message_text'],
        data['media_path'],
        data['media_type'],
        chat_ids_json,
        interval_seconds,
        next_send_time
    )

    await state.clear()
    await callback.message.edit_text(
        f"✅ Рассылка создана!\n"
        f"Интервал: {'раз в час' if interval_type == 'hour' else 'раз в день'}\n"
        f"Чатов выбрано: {len(data['selected_chats'])}"
    )
    await callback.answer()

@router.callback_query(F.data == "custom_interval")
async def handle_custom_interval_request(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите интервал в минутах или часах.\n"
        "Примеры: 30м, 2ч, 90м"
    )
    await callback.answer()

@router.message(UserStates.setting_interval)
async def handle_custom_interval_input(message: Message, state: FSMContext):
    interval_text = message.text.strip().lower()

    try:
        if 'м' in interval_text:
            minutes = int(interval_text.replace('м', ''))
            interval_seconds = minutes * 60
        elif 'ч' in interval_text:
            hours = int(interval_text.replace('ч', ''))
            interval_seconds = hours * 3600
        else:
            await message.answer("Неверный формат. Используйте 'м' для минут или 'ч' для часов.")
            return

        data = await state.get_data()
        chat_ids_json = json.dumps(data['selected_chats'])
        next_send_time = int(time.time()) + interval_seconds

        await database.save_scheduled_message(
            data['message_text'],
            data['media_path'],
            data['media_type'],
            chat_ids_json,
            interval_seconds,
            next_send_time
        )

        await state.clear()
        await message.answer(
            f"✅ Рассылка создана!\n"
            f"Интервал: {interval_text}\n"
            f"Чатов выбрано: {len(data['selected_chats'])}"
        )
    except ValueError:
        await message.answer("Ошибка! Введите число с 'м' или 'ч'.")

@router.callback_query(F.data == "my_broadcasts")
async def handle_my_broadcasts(callback: CallbackQuery, state: FSMContext):
    messages = await database.get_active_scheduled_messages()

    if not messages:
        await callback.message.edit_text("У вас нет активных рассылок.")
        await callback.answer()
        return

    keyboard = []
    for msg in messages:
        msg_id, msg_text, media_path, media_type, chat_ids, interval, next_send = msg
        chat_count = len(json.loads(chat_ids))
        preview = msg_text[:30] + "..." if len(msg_text) > 30 else msg_text
        keyboard.append([InlineKeyboardButton(
            text=f"📨 {preview} ({chat_count} чатов)",
            callback_data=f"view_broadcast_{msg_id}"
        )])

    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        "📋 Ваши активные рассылки:\n\nВыберите рассылку для просмотра:",
        reply_markup=reply_markup
    )
    await callback.answer()

@router.callback_query(F.data.startswith("view_broadcast_"))
async def handle_view_broadcast(callback: CallbackQuery, state: FSMContext):
    msg_id = int(callback.data.split("_")[2])
    messages = await database.get_active_scheduled_messages()

    broadcast = None
    for msg in messages:
        if msg[0] == msg_id:
            broadcast = msg
            break

    if not broadcast:
        await callback.answer("Рассылка не найдена!", show_alert=True)
        return

    msg_id, msg_text, media_path, media_type, chat_ids_json, interval, next_send = broadcast
    chat_ids = json.loads(chat_ids_json)
    chat_count = len(chat_ids)

    hours = interval // 3600
    minutes = (interval % 3600) // 60
    interval_text = f"{hours}ч {minutes}м" if hours > 0 else f"{minutes}м"

    text = f"📨 Рассылка #{msg_id}\n\n"
    text += f"📝 Текст: {msg_text}\n\n"
    text += f"📊 Чатов: {chat_count}\n"
    text += f"⏰ Интервал: {interval_text}\n"
    text += f"🎬 Медиа: {'Да' if media_type else 'Нет'}"

    keyboard = [
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"edit_text_{msg_id}")],
        [InlineKeyboardButton(text="👥 Изменить чаты", callback_data=f"edit_chats_{msg_id}")],
        [InlineKeyboardButton(text="⏰ Изменить интервал", callback_data=f"edit_interval_{msg_id}")],
        [InlineKeyboardButton(text="🗑 Удалить рассылку", callback_data=f"delete_broadcast_{msg_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="my_broadcasts")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()

@router.callback_query(F.data.startswith("edit_text_"))
async def handle_edit_text_request(callback: CallbackQuery, state: FSMContext):
    msg_id = int(callback.data.split("_")[2])
    await state.set_state(UserStates.editing_message)
    await state.update_data(editing_broadcast_id=msg_id)

    await callback.message.edit_text(
        "Отправьте новое сообщение для рассылки.\n"
        "Можно отправить текст, фото или видео (с подписью или без)."
    )
    await callback.answer()

@router.message(UserStates.editing_message)
async def handle_edit_message_input(message: Message, state: FSMContext, bot: Bot):
    message_text = message.caption or message.text or ""
    media_path = None
    media_type = None

    os.makedirs('media', exist_ok=True)

    if message.photo:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        media_path = f"media/{photo.file_id}.jpg"
        await bot.download_file(file.file_path, media_path)
        media_type = "photo"
    elif message.video:
        video = message.video
        file = await bot.get_file(video.file_id)
        media_path = f"media/{video.file_id}.mp4"
        await bot.download_file(file.file_path, media_path)
        media_type = "video"

    data = await state.get_data()
    msg_id = data['editing_broadcast_id']

    await database.update_broadcast_message(msg_id, message_text, media_path, media_type)
    await state.clear()

    await message.answer("✅ Сообщение рассылки обновлено!")

@router.callback_query(F.data.startswith("edit_chats_"))
async def handle_edit_chats_request(callback: CallbackQuery, state: FSMContext):
    msg_id = int(callback.data.split("_")[2])

    messages = await database.get_active_scheduled_messages()
    broadcast = None
    for msg in messages:
        if msg[0] == msg_id:
            broadcast = msg
            break

    if not broadcast:
        await callback.answer("Рассылка не найдена!", show_alert=True)
        return

    chat_ids_json = broadcast[4]
    selected_chats = json.loads(chat_ids_json)

    await state.set_state(UserStates.editing_chats)
    await state.update_data(
        editing_broadcast_id=msg_id,
        selected_chats=selected_chats
    )

    await callback.answer()
    await show_chats_list_for_edit(callback.message, state, page=0)

async def show_chats_list_for_edit(message: Message, state: FSMContext, page=0):
    global user_client

    dialogs = []
    async for dialog in user_client.iter_dialogs():
        dialogs.append({
            'id': dialog.id,
            'name': dialog.name or "Без названия"
        })

    await state.update_data(all_chats=dialogs)
    data = await state.get_data()
    selected_chats = data.get('selected_chats', [])

    per_page = 8
    start = page * per_page
    end = start + per_page
    page_dialogs = dialogs[start:end]

    keyboard = []
    for dialog in page_dialogs:
        chat_id = dialog['id']
        selected = "✅ " if chat_id in selected_chats else ""
        keyboard.append([InlineKeyboardButton(
            text=f"{selected}{dialog['name']}",
            callback_data=f"editchat_{chat_id}_{page}"
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"editpage_{page-1}"))
    if end < len(dialogs):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"editpage_{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(text="✅ Сохранить изменения", callback_data="save_edited_chats")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    selected_count = len(selected_chats)

    await message.edit_text(
        f"Выберите чаты для рассылки (выбрано: {selected_count}):",
        reply_markup=reply_markup
    )

@router.callback_query(F.data.startswith("editchat_"))
async def handle_edit_chat_selection(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    chat_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    data = await state.get_data()
    selected_chats = data.get('selected_chats', [])

    if chat_id in selected_chats:
        selected_chats.remove(chat_id)
    else:
        selected_chats.append(chat_id)

    await state.update_data(selected_chats=selected_chats)

    dialogs = data.get('all_chats', [])
    per_page = 8
    start = page * per_page
    end = start + per_page
    page_dialogs = dialogs[start:end]

    keyboard = []
    for dialog in page_dialogs:
        chat_id_iter = dialog['id']
        selected = "✅ " if chat_id_iter in selected_chats else ""
        keyboard.append([InlineKeyboardButton(
            text=f"{selected}{dialog['name']}",
            callback_data=f"editchat_{chat_id_iter}_{page}"
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"editpage_{page-1}"))
    if end < len(dialogs):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"editpage_{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(text="✅ Сохранить изменения", callback_data="save_edited_chats")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    selected_count = len(selected_chats)

    await callback.message.edit_text(
        f"Выберите чаты для рассылки (выбрано: {selected_count}):",
        reply_markup=reply_markup
    )
    await callback.answer()

@router.callback_query(F.data.startswith("editpage_"))
async def handle_edit_pagination(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split("_")[1])
    data = await state.get_data()

    dialogs = data.get('all_chats', [])
    selected_chats = data.get('selected_chats', [])

    per_page = 8
    start = page * per_page
    end = start + per_page
    page_dialogs = dialogs[start:end]

    keyboard = []
    for dialog in page_dialogs:
        chat_id = dialog['id']
        selected = "✅ " if chat_id in selected_chats else ""
        keyboard.append([InlineKeyboardButton(
            text=f"{selected}{dialog['name']}",
            callback_data=f"editchat_{chat_id}_{page}"
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"editpage_{page-1}"))
    if end < len(dialogs):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперед", callback_data=f"editpage_{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(text="✅ Сохранить изменения", callback_data="save_edited_chats")])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    selected_count = len(selected_chats)

    await callback.message.edit_text(
        f"Выберите чаты для рассылки (выбрано: {selected_count}):",
        reply_markup=reply_markup
    )
    await callback.answer()

@router.callback_query(F.data == "save_edited_chats")
async def handle_save_edited_chats(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    msg_id = data['editing_broadcast_id']
    selected_chats = data.get('selected_chats', [])

    if not selected_chats:
        await callback.answer("Выберите хотя бы один чат!", show_alert=True)
        return

    chat_ids_json = json.dumps(selected_chats)
    await database.update_broadcast_chats(msg_id, chat_ids_json)
    await state.clear()

    await callback.message.edit_text("✅ Список чатов обновлен!")
    await callback.answer()

@router.callback_query(F.data.startswith("edit_interval_"))
async def handle_edit_interval_request(callback: CallbackQuery, state: FSMContext):
    msg_id = int(callback.data.split("_")[2])
    await state.set_state(UserStates.editing_interval)
    await state.update_data(editing_broadcast_id=msg_id)

    keyboard = [
        [InlineKeyboardButton(text="⏰ Раз в час", callback_data="editint_hour")],
        [InlineKeyboardButton(text="📅 Раз в день", callback_data="editint_day")],
        [InlineKeyboardButton(text="⚙️ Свой интервал", callback_data="editint_custom")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        "Выберите новый интервал отправки:",
        reply_markup=reply_markup
    )
    await callback.answer()

@router.callback_query(F.data.startswith("editint_"))
async def handle_edit_interval_selection(callback: CallbackQuery, state: FSMContext):
    interval_type = callback.data.split("_")[1]

    if interval_type == "custom":
        await callback.message.edit_text(
            "Введите интервал в минутах или часах.\n"
            "Примеры: 30м, 2ч, 90м"
        )
        await callback.answer()
        return

    interval_seconds = config.INTERVALS.get(interval_type)
    data = await state.get_data()
    msg_id = data['editing_broadcast_id']

    await database.update_broadcast_interval(msg_id, interval_seconds)
    await state.clear()

    await callback.message.edit_text(
        f"✅ Интервал обновлен!\n"
        f"Новый интервал: {'раз в час' if interval_type == 'hour' else 'раз в день'}"
    )
    await callback.answer()

@router.message(UserStates.editing_interval)
async def handle_edit_custom_interval_input(message: Message, state: FSMContext):
    interval_text = message.text.strip().lower()

    try:
        if 'м' in interval_text:
            minutes = int(interval_text.replace('м', ''))
            interval_seconds = minutes * 60
        elif 'ч' in interval_text:
            hours = int(interval_text.replace('ч', ''))
            interval_seconds = hours * 3600
        else:
            await message.answer("Неверный формат. Используйте 'м' для минут или 'ч' для часов.")
            return

        data = await state.get_data()
        msg_id = data['editing_broadcast_id']

        await database.update_broadcast_interval(msg_id, interval_seconds)
        await state.clear()

        await message.answer(
            f"✅ Интервал обновлен!\n"
            f"Новый интервал: {interval_text}"
        )
    except ValueError:
        await message.answer("Ошибка! Введите число с 'м' или 'ч'.")

@router.callback_query(F.data.startswith("delete_broadcast_"))
async def handle_delete_broadcast(callback: CallbackQuery, state: FSMContext):
    msg_id = int(callback.data.split("_")[2])

    keyboard = [
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{msg_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"view_broadcast_{msg_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить эту рассылку?",
        reply_markup=reply_markup
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def handle_confirm_delete(callback: CallbackQuery, state: FSMContext):
    msg_id = int(callback.data.split("_")[2])
    await database.delete_scheduled_message(msg_id)

    await callback.message.edit_text("✅ Рассылка удалена!")
    await callback.answer()

@router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    keyboard = [
        [InlineKeyboardButton(text="🔐 Войти в аккаунт", callback_data="login")],
        [InlineKeyboardButton(text="📝 Создать рассылку", callback_data="create_broadcast")],
        [InlineKeyboardButton(text="📋 Мои рассылки", callback_data="my_broadcasts")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.edit_text(
        "Главное меню:",
        reply_markup=reply_markup
    )
    await callback.answer()

async def send_scheduled_messages():
    global user_client

    try:
        if not user_client or not await user_client.is_user_authorized():
            return

        current_time = int(time.time())
        messages = await database.get_active_scheduled_messages()

        for msg in messages:
            msg_id, msg_text, media_path, media_type, chat_ids_json, interval, next_send = msg

            if current_time >= next_send:
                chat_ids = json.loads(chat_ids_json)

                for chat_id in chat_ids:
                    try:
                        if media_type == "photo" and media_path and os.path.exists(media_path):
                            await user_client.send_file(chat_id, media_path, caption=msg_text)
                        elif media_type == "video" and media_path and os.path.exists(media_path):
                            await user_client.send_file(chat_id, media_path, caption=msg_text)
                        else:
                            await user_client.send_message(chat_id, msg_text)

                        await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"Ошибка отправки в чат {chat_id}: {e}")
                        continue

                new_next_send = current_time + interval
                await database.update_next_send_time(msg_id, new_next_send)
    except Exception as e:
        print(f"Ошибка в send_scheduled_messages: {e}")

async def main():
    await database.init_db()

    os.makedirs('media', exist_ok=True)

    global user_client
    user_client = TelegramClient(
        config.SESSION_NAME,
        config.API_ID,
        config.API_HASH,
        connection_retries=5,
        retry_delay=3,
        timeout=30
    )
    await user_client.connect()

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_scheduled_messages, 'interval', seconds=60, max_instances=1, coalesce=True)
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
