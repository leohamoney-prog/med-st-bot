from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_CHAT_ID
from firebase_db import (get_available_dates, get_free_times,
                          create_appointment, get_patient_appointments,
                          get_appointment_by_id, update_status)
from keyboards import (dates_kb, times_kb, services_kb, confirm_kb,
                        phone_kb, cancel_appt_kb, attendance_kb)
from utils import fmt_date

router = Router()


def _end_time(start: str, duration_min: int = 60) -> str:
    """Возвращает время окончания приёма."""
    try:
        h, m = map(int, start.split(":"))
        total = h * 60 + m + duration_min
        return f"{total // 60:02d}:{total % 60:02d}"
    except Exception:
        return "—"


class BookFSM(StatesGroup):
    name       = State()
    birth      = State()
    phone      = State()
    date       = State()
    time       = State()
    service    = State()
    confirm    = State()


# ── /start ────────────────────────────────────────────────────────

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Я помогу вам записаться на приём.\n\n"
        "Выберите действие:",
        reply_markup=_main_menu()
    )


def _main_menu():
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Записаться на приём")],
            [KeyboardButton(text="📋 Мои записи")],
            [KeyboardButton(text="❌ Отменить запись")],
        ],
        resize_keyboard=True
    )


# ── ЗАПИСЬ ────────────────────────────────────────────────────────

@router.message(F.text == "📅 Записаться на приём")
async def book_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📝 Введите ваше <b>ФИО</b> полностью\n"
        "<i>(Фамилия Имя Отчество)</i>",
        parse_mode="HTML"
    )
    await state.set_state(BookFSM.name)


@router.message(BookFSM.name)
async def book_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name.split()) < 2:
        await message.answer("❌ Пожалуйста, введите <b>полное ФИО</b> (минимум имя и фамилию):", parse_mode="HTML")
        return
    await state.update_data(name=name)
    await message.answer(
        f"✅ ФИО: <b>{name}</b>\n\n"
        "📅 Введите дату рождения в формате <b>ДД.ММ.ГГГГ</b>\n"
        "<i>Например: 15.03.1990</i>",
        parse_mode="HTML"
    )
    await state.set_state(BookFSM.birth)


@router.message(BookFSM.birth)
async def book_birth(message: Message, state: FSMContext):
    birth = message.text.strip()
    # Простая проверка формата
    parts = birth.replace("-", ".").split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        await message.answer("❌ Введите дату в формате <b>ДД.ММ.ГГГГ</b>, например: 15.03.1990", parse_mode="HTML")
        return
    await state.update_data(birth=birth)
    await message.answer(
        f"✅ Дата рождения: <b>{birth}</b>\n\n"
        "📱 Введите ваш <b>номер телефона</b> или нажмите «Пропустить»:",
        parse_mode="HTML",
        reply_markup=phone_kb()
    )
    await state.set_state(BookFSM.phone)


@router.message(BookFSM.phone)
async def book_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await _show_dates(message, state)


@router.callback_query(BookFSM.phone, F.data == "skip_phone")
async def skip_phone(call: CallbackQuery, state: FSMContext):
    await state.update_data(phone="")
    await call.message.edit_text("⏭ Телефон не указан")
    await _show_dates(call.message, state)


async def _show_dates(message: Message, state: FSMContext):
    dates = await get_available_dates()
    if not dates:
        await message.answer(
            "😔 К сожалению, сейчас нет доступных дат для записи.\n"
            "Попробуйте позже или свяжитесь с нами напрямую."
        )
        await state.clear()
        return
    await message.answer(
        "📅 Выберите удобный день:",
        reply_markup=dates_kb(dates)
    )
    await state.set_state(BookFSM.date)


@router.callback_query(BookFSM.date, F.data.startswith("date:"))
async def book_date(call: CallbackQuery, state: FSMContext):
    appt_date = call.data.split(":")[1]
    times = await get_free_times(appt_date)
    if not times:
        await call.answer("😔 На этот день уже нет свободных слотов", show_alert=True)
        return
    await state.update_data(date=appt_date)
    await call.message.edit_text(
        f"📅 <b>{fmt_date(appt_date)}</b>\n\n⏰ Выберите удобное время:",
        parse_mode="HTML",
        reply_markup=times_kb(times, appt_date)
    )
    await state.set_state(BookFSM.time)


@router.callback_query(BookFSM.time, F.data.startswith("time:"))
async def book_time(call: CallbackQuery, state: FSMContext):
    t = call.data.split(":")[1]
    await state.update_data(time=t)
    data = await state.get_data()
    await call.message.edit_text(
        f"📅 {fmt_date(data['date'])} в {t}\n\n🦷 Выберите вид работы:",
        parse_mode="HTML",
        reply_markup=services_kb()
    )
    await state.set_state(BookFSM.service)


@router.callback_query(BookFSM.service, F.data.startswith("svc:"))
async def book_service(call: CallbackQuery, state: FSMContext):
    service = call.data[4:]
    await state.update_data(service=service)
    data = await state.get_data()
    tg = f"@{call.from_user.username}" if call.from_user.username else "не указан"
    await call.message.edit_text(
        f"📋 <b>Проверьте данные записи:</b>\n\n"
        f"👤 {data['name']}\n"
        f"🎂 {data['birth']}\n"
        f"📱 {data.get('phone') or 'не указан'}\n"
        f"💬 Telegram: {tg}\n"
        f"📅 {fmt_date(data['date'])}\n"
        f"🕐 {data['time']}\n"
        f"🦷 {service}",
        parse_mode="HTML",
        reply_markup=confirm_kb()
    )
    await state.set_state(BookFSM.confirm)


@router.callback_query(BookFSM.confirm, F.data == "confirm")
async def book_confirm(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    tg = f"@{call.from_user.username}" if call.from_user.username else ""

    appt_id = await create_appointment(
        tg_id=call.from_user.id,
        patient_name=data["name"],
        birth_date=data["birth"],
        phone=data.get("phone", ""),
        tg_username=tg,
        appt_date=data["date"],
        appt_time=data["time"],
        service=data["service"]
    )

    await call.message.edit_text(
        f"✅ <b>Вы записаны!</b>\n\n"
        f"📅 {fmt_date(data['date'])}\n"
        f"🕐 {data['time']}\n"
        f"🦷 {data['service']}\n\n"
        f"Мы напомним вам за день до приёма 🔔",
        parse_mode="HTML"
    )
    await call.message.answer("Главное меню:", reply_markup=_main_menu())

    # Уведомление врачу
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"🆕 <b>Новая запись!</b>\n\n"
        f"👤 <b>{data['name']}</b>\n"
        f"🎂 {data['birth']}\n"
        f"📱 {data.get('phone') or '—'}\n"
        f"💬 {tg or '—'}\n"
        f"📅 {fmt_date(data['date'])}\n"
        f"🕐 Время приёма: <b>{data['time']} — {_end_time(data['time'])}</b>\n"
        f"🦷 {data['service']}\n"
        f"🔑 ID: #{appt_id[:8]}",
        parse_mode="HTML"
    )


# ── Навигация назад ───────────────────────────────────────────────

@router.callback_query(F.data == "back_date")
async def back_date(call: CallbackQuery, state: FSMContext):
    dates = await get_available_dates()
    await call.message.edit_text("📅 Выберите удобный день:", reply_markup=dates_kb(dates))
    await state.set_state(BookFSM.date)


@router.callback_query(F.data == "back_time")
async def back_time(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    times = await get_free_times(data.get("date", ""))
    await call.message.edit_text(
        f"📅 {fmt_date(data['date'])}\n\n⏰ Выберите время:",
        parse_mode="HTML",
        reply_markup=times_kb(times, data["date"])
    )
    await state.set_state(BookFSM.time)


@router.callback_query(F.data == "back_service")
async def back_service(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await call.message.edit_text(
        f"📅 {fmt_date(data['date'])} в {data['time']}\n\n🦷 Вид работы:",
        parse_mode="HTML",
        reply_markup=services_kb()
    )
    await state.set_state(BookFSM.service)


@router.callback_query(F.data == "cancel")
async def cancel_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Отменено.")
    await call.message.answer("Главное меню:", reply_markup=_main_menu())


# ── МОИ ЗАПИСИ ───────────────────────────────────────────────────

@router.message(F.text == "📋 Мои записи")
async def my_appointments(message: Message):
    apts = await get_patient_appointments(message.from_user.id)
    if not apts:
        await message.answer("У вас нет активных записей.", reply_markup=_main_menu())
        return
    text = "📋 <b>Ваши записи:</b>\n\n"
    for a in apts:
        icon = "✅" if a["status"] == "confirmed" else "🕐"
        text += f"{icon} <b>{fmt_date(a['date'])}</b> в {a['time']}\n   🦷 {a.get('service','')}\n\n"
    await message.answer(text, parse_mode="HTML", reply_markup=_main_menu())


# ── ОТМЕНА ЗАПИСИ ────────────────────────────────────────────────

@router.message(F.text == "❌ Отменить запись")
async def cancel_appt_start(message: Message):
    apts = await get_patient_appointments(message.from_user.id)
    if not apts:
        await message.answer("У вас нет активных записей.", reply_markup=_main_menu())
        return
    await message.answer("Выберите запись для отмены:", reply_markup=cancel_appt_kb(apts))


@router.callback_query(F.data.startswith("cancel_appt:"))
async def cancel_appt_exec(call: CallbackQuery, bot: Bot):
    appt_id = call.data.split(":")[1]
    appt = await get_appointment_by_id(appt_id)
    await update_status(appt_id, "cancelled")
    await call.message.edit_text(
        f"✅ Запись на {fmt_date(appt['date'])} в {appt['time']} отменена."
    )
    await call.message.answer("Главное меню:", reply_markup=_main_menu())
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"⚠️ <b>Пациент отменил запись</b>\n\n"
        f"👤 {appt.get('patientName','?')}\n"
        f"📅 {fmt_date(appt['date'])} в {appt['time']}\n"
        f"🦷 {appt.get('service','')}",
        parse_mode="HTML"
    )


# ── НАПОМИНАНИЕ (приду / не приду) ───────────────────────────────

@router.callback_query(F.data.startswith("attend:"))
async def attend(call: CallbackQuery, bot: Bot):
    _, answer, appt_id = call.data.split(":", 2)
    appt = await get_appointment_by_id(appt_id)
    if answer == "yes":
        await update_status(appt_id, "confirmed")
        await call.message.edit_text(
            f"✅ Ждём вас <b>{fmt_date(appt['date'])}</b> в <b>{appt['time']}</b>!",
            parse_mode="HTML"
        )
        admin_msg = f"✅ <b>Придёт!</b>\n👤 {appt.get('patientName')}\n📅 {fmt_date(appt['date'])} в {appt['time']}"
    else:
        await update_status(appt_id, "cancelled")
        await call.message.edit_text("❌ Запись отменена. Для новой записи — /start")
        admin_msg = f"❌ <b>НЕ придёт!</b>\n👤 {appt.get('patientName')}\n📅 {fmt_date(appt['date'])} в {appt['time']}"
    await bot.send_message(ADMIN_CHAT_ID, admin_msg, parse_mode="HTML")
    await call.answer()


# ── FALLBACK ─────────────────────────────────────────────────────

@router.message()
async def fallback(message: Message, state: FSMContext):
    if await state.get_state() is None:
        await message.answer(
            "Используйте меню для записи или введите /start",
            reply_markup=_main_menu()
        )
