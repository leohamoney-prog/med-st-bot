from datetime import datetime

MONTHS = ["января","февраля","марта","апреля","мая","июня",
          "июля","августа","сентября","октября","ноября","декабря"]
DAYS   = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]


def fmt_date(date_str: str) -> str:
    """2024-02-15 → 'Чт, 15 февраля'"""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return f"{DAYS[d.weekday()]}, {d.day} {MONTHS[d.month-1]}"


def tomorrow_str() -> str:
    from datetime import date, timedelta
    return (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
