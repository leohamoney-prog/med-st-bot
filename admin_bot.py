"""
Второй бот для врача — запускается параллельно с основным.
Позволяет:
  - Просматривать записи по дням
  - Подтверждать/отменять записи
  - Добавлять/удалять доступные даты
  - Получать уведомления о новых записях
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_BOT_TOKEN, ADMIN_CHAT_ID
from firebase_db import (get_all_upcoming_appointments, get_appointments_by_date,
                          get_appointment_by_id, update_status,
                          add_available_slot, get_available_dates, delete_available_slot)
from utils import fmt_date

logger = logging.getLogger(__name__)
admin_router = Router()


class AddSlotFSM(StatesGroup):
    date  = State()
    times = State()


# ── /start ────────────────────────────────────────────────────────

@admin_router.message(CommandStart())
async def admin_start(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await message.answer(
        "👨‍⚕️ <b>Панель врача</b>\n\n"
        "Команды:\n"
        "/today — записи на сегодня\n"
        "/tomorrow — записи на завтра\n"
        "/schedule — все предстоящие записи\n"
        "/slots — доступные даты записи\n"
        "/addslot — добавить дату\n"
        "/help — помощь",
        parse_mode="HTML"
    )


@admin_router.message(Command("help"))
async def admin_help(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    await message.answer(
        "📖 <b>Справка</b>\n\n"
        "/today — записи на сегодня\n"
        "/tomorrow — записи на завтра\n"
        "/schedule — все предстоящие записи\n"
        "/slots — посмотреть доступные даты\n"
        "/addslot — добавить новую дату для записи\n\n"
        "При добавлении даты пациенты смогут на неё записаться.\n"
        "При удалении даты — новые записи на неё прекратятся.",
        parse_mode="HTML"
    )


# ── РАСПИСАНИЕ ────────────────────────────────────────────────────

@admin_router.message(Command("today"))
async def today_schedule(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    from datetime import date
    today = date.today().isoformat()
    await _show_day(message, today)


@admin_router.message(Command("tomorrow"))
async def tomorrow_schedule(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    from utils import tomorrow_str
    await _show_day(message, tomorrow_str())


@admin_router.message(Command("schedule"))
async def full_schedule(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    apts = await get_all_upcoming_appointments()
    if not apts:
        await message.answer("📅 Нет предстоящих записей.")
        return
    text = "📅 <b>Все предстоящие записи:</b>\n"
    prev_date = None
    for a in apts:
        if a["date"] != prev_date:
            text += f"\n<b>📆 {fmt_date(a['date'])}</b>\n"
            prev_date = a["date"]
        icon = "✅" if a["status"] == "confirmed" else "🕐"
        text += f"  {icon} {a['time']} — {a.get('patientName','?')}\n"
        if a.get("phone"):
            text += f"       📱 {a['phone']}\n"
    await message.answer(text, parse_mode="HTML",
                         reply_markup=_schedule_actions_kb())


async def _show_day(message: Message, date_str: str):
    apts = await get_appointments_by_date(date_str)
    if not apts:
        await message.answer(f"📅 На <b>{fmt_date(date_str)}</b> записей нет.",
                             parse_mode="HTML")
        return
    text = f"📅 <b>Записи на {fmt_date(date_str)}:</b>\n\n"
    for a in apts:
        icon = "✅" if a["status"] == "confirmed" else "🕐"
        text += (f"{icon} <b>{a['time']}</b> — {a.get('patientName','?')}\n"
                 f"   🎂 {a.get('birthDate','—')}\n")
        if a.get("phone"):
            text += f"   📱 {a['phone']}\n"
        if a.get("tgUsername"):
            text += f"   💬 {a['tgUsername']}\n"
        text += f"   🦷 {a.get('service','')}\n\n"
    buttons = [[InlineKeyboardButton(
        text=f"📋 Детали: {a['time']} {a.get('patientName','?')[:15]}",
        callback_data=f"appt:{a['id']}"
    )] for a in apts]
    await message.answer(text, parse_mode="HTML",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


def _schedule_actions_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_schedule")]
    ])


@admin_router.callback_query(F.data == "refresh_schedule")
async def refresh_schedule(call: CallbackQuery):
    apts = await get_all_upcoming_appointments()
    if not apts:
        await call.message.edit_text("📅 Нет предстоящих записей.")
        return
    text = "📅 <b>Все предстоящие записи:</b>\n"
    prev_date = None
    for a in apts:
        if a["date"] != prev_date:
            text += f"\n<b>📆 {fmt_date(a['date'])}</b>\n"
            prev_date = a["date"]
        icon = "✅" if a["status"] == "confirmed" else "🕐"
        text += f"  {icon} {a['time']} — {a.get('patientName','?')}\n"
    await call.message.edit_text(text, parse_mode="HTML",
                                  reply_markup=_schedule_actions_kb())
    await call.answer()


# ── ДЕТАЛИ ЗАПИСИ ────────────────────────────────────────────────

@admin_router.callback_query(F.data.startswith("appt:"))
async def appt_details(call: CallbackQuery):
    appt_id = call.data.split(":")[1]
    a = await get_appointment_by_id(appt_id)
    if not a:
        await call.answer("Запись не найдена")
        return
    icon = "✅" if a["status"] == "confirmed" else "🕐"
    text = (f"{icon} <b>Запись #{appt_id[:8]}</b>\n\n"
            f"👤 {a.get('patientName','?')}\n"
            f"🎂 {a.get('birthDate','—')}\n"
            f"📱 {a.get('phone','—')}\n"
            f"💬 {a.get('tgUsername','—')}\n"
            f"📅 {fmt_date(a['date'])} в {a['time']}\n"
            f"🦷 {a.get('service','')}\n"
            f"Статус: {a.get('status','')}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_appt:{appt_id}"),
         InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_appt:{appt_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_schedule")]
    ])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@admin_router.callback_query(F.data.startswith("confirm_appt:"))
async def confirm_appt(call: CallbackQuery):
    appt_id = call.data.split(":")[1]
    await update_status(appt_id, "confirmed")
    await call.answer("✅ Запись подтверждена!")
    await call.message.edit_text("✅ Запись подтверждена.")


@admin_router.callback_query(F.data.startswith("cancel_appt:"))
async def cancel_appt(call: CallbackQuery):
    appt_id = call.data.split(":")[1]
    await update_status(appt_id, "cancelled")
    await call.answer("❌ Запись отменена")
    await call.message.edit_text("❌ Запись отменена.")


@admin_router.callback_query(F.data == "back_to_schedule")
async def back_schedule(call: CallbackQuery):
    await call.message.delete()


# ── УПРАВЛЕНИЕ ДАТАМИ ────────────────────────────────────────────

@admin_router.message(Command("slots"))
async def show_slots(message: Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    slots = await get_available_dates()
    if not slots:
        await message.answer(
            "📅 Нет доступных дат для записи.\n\n"
            "Добавьте дату командой /addslot"
        )
        return
    text = "📅 <b>Доступные даты для записи:</b>\n\n"
    buttons = []
    for s in slots:
        times_str = ", ".join(s.get("times", []))
        text += f"📆 <b>{fmt_date(s['date'])}</b>\n   ⏰ {times_str}\n\n"
        buttons.append([InlineKeyboardButton(
            text=f"🗑 Удалить {fmt_date(s['date'])}",
            callback_data=f"del_slot:{s['id']}"
        )])
    buttons.append([InlineKeyboardButton(
        text="➕ Добавить дату", callback_data="add_slot"
    )])
    await message.answer(text, parse_mode="HTML",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@admin_router.callback_query(F.data.startswith("del_slot:"))
async def del_slot(call: CallbackQuery):
    slot_id = call.data.split(":")[1]
    await delete_available_slot(slot_id)
    await call.answer("🗑 Дата удалена")
    await call.message.edit_text("✅ Дата удалена. Используйте /slots для просмотра.")


@admin_router.message(Command("addslot"))
@admin_router.callback_query(F.data == "add_slot")
async def add_slot_start(event, state: FSMContext):
    msg = event if isinstance(event, Message) else event.message
    if isinstance(event, CallbackQuery):
        await event.answer()
    await msg.answer(
        "📅 Введите дату в формате <b>ДД.ММ.ГГГГ</b>\n"
        "<i>Например: 25.03.2024</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddSlotFSM.date)


@admin_router.message(AddSlotFSM.date)
async def add_slot_date(message: Message, state: FSMContext):
    date_str = message.text.strip()
    parts = date_str.replace("-", ".").split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        await message.answer("❌ Формат: ДД.ММ.ГГГГ, например: 25.03.2024")
        return
    # Конвертируем в YYYY-MM-DD
    iso_date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    await state.update_data(date=iso_date, display_date=date_str)
    await message.answer(
        f"✅ Дата: <b>{date_str}</b>\n\n"
        "⏰ Введите доступные времена через запятую:\n"
        "<i>Например: 09:00, 10:00, 11:00, 14:00, 15:00</i>",
        parse_mode="HTML"
    )
    await state.set_state(AddSlotFSM.times)


@admin_router.message(AddSlotFSM.times)
async def add_slot_times(message: Message, state: FSMContext):
    times_raw = message.text.strip()
    times = [t.strip() for t in times_raw.split(",") if t.strip()]
    if not times:
        await message.answer("❌ Введите хотя бы одно время")
        return
    data = await state.get_data()
    await add_available_slot(data["date"], times)
    await state.clear()
    times_str = ", ".join(times)
    await message.answer(
        f"✅ <b>Дата добавлена!</b>\n\n"
        f"📅 {data['display_date']}\n"
        f"⏰ {times_str}\n\n"
        f"Пациенты могут записываться на эту дату.",
        parse_mode="HTML"
    )


# ── Запуск второго бота ───────────────────────────────────────────

async def run_admin_bot():
    bot = Bot(token=ADMIN_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    logger.info("Бот врача запущен ✅")
    await dp.start_polling(bot, skip_updates=True)
