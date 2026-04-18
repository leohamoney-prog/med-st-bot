from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import fmt_date


def dates_kb(dates: list) -> InlineKeyboardMarkup:
    buttons = []
    for d in dates:
        label = f"📅 {fmt_date(d['date'])}"
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f"date:{d['date']}")])
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def times_kb(times: list, date_str: str) -> InlineKeyboardMarkup:
    rows, row = [], []
    for t in times:
        row.append(InlineKeyboardButton(
            text=f"🕐 {t}", callback_data=f"time:{t}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_date"),
                 InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def services_kb() -> InlineKeyboardMarkup:
    services = [
        "🦷 Лечение кариеса",
        "🪥 Профессиональная чистка",
        "🔧 Установка пломбы",
        "👑 Установка коронки",
        "🦷 Удаление зуба",
        "✨ Отбеливание",
        "🔬 Консультация",
        "🩺 Другое",
    ]
    buttons = [[InlineKeyboardButton(text=s, callback_data=f"svc:{s}")]
               for s in services]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_time"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить запись", callback_data="confirm")],
        [InlineKeyboardButton(text="◀️ Изменить", callback_data="back_service"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])


def phone_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_phone")]
    ])


def cancel_appt_kb(appointments: list) -> InlineKeyboardMarkup:
    buttons = []
    for a in appointments:
        from utils import fmt_date
        label = f"{fmt_date(a['date'])} {a['time']}"
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f"cancel_appt:{a['id']}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def attendance_kb(appt_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, приду!", callback_data=f"attend:yes:{appt_id}"),
         InlineKeyboardButton(text="❌ Не приду", callback_data=f"attend:no:{appt_id}")]
    ])
