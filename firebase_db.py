import os, json, logging
from datetime import datetime, date
import firebase_admin
from firebase_admin import credentials, firestore_async

logger = logging.getLogger(__name__)
_db = None


def init_firebase():
    global _db
    cred_json = os.getenv("GOOGLE_CREDENTIALS", "")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    _db = firestore_async.client()
    logger.info("Firebase подключён ✅")


def get_db():
    if _db is None:
        raise RuntimeError("Firebase не инициализирован")
    return _db


async def get_available_dates():
    db = get_db()
    today = date.today().isoformat()
    result = []
    try:
        async for doc in db.collection("available_slots").stream():
            d = doc.to_dict()
            if not d:
                continue
            if d.get("active", True) and d.get("date", "") >= today:
                result.append({"id": doc.id, **d})
        result.sort(key=lambda x: x.get("date", ""))
        logger.info(f"Найдено {len(result)} дат")
    except Exception as e:
        logger.error(f"Ошибка get_available_dates: {e}")
    return result


async def get_free_times(slot_date: str):
    db = get_db()
    slot = None
    try:
        async for doc in db.collection("available_slots").stream():
            d = doc.to_dict()
            if d.get("date") == slot_date:
                slot = d
                break
        if not slot:
            return []
        all_times = slot.get("times", [])
        booked = []
        async for doc in db.collection("appointments").stream():
            d = doc.to_dict()
            if d.get("date") == slot_date and d.get("status") in ["scheduled", "confirmed"]:
                booked.append(d.get("time", ""))
        return [t for t in all_times if t not in booked]
    except Exception as e:
        logger.error(f"Ошибка get_free_times: {e}")
        return []


async def add_available_slot(slot_date: str, times: list):
    db = get_db()
    await db.collection("available_slots").add({
        "date": slot_date, "times": times, "active": True,
        "createdAt": datetime.utcnow().isoformat()
    })


async def delete_available_slot(slot_id: str):
    await get_db().collection("available_slots").document(slot_id).delete()


async def create_appointment(tg_id, patient_name, birth_date, phone, tg_username, appt_date, appt_time, service):
    db = get_db()
    data = {
        "patientName": patient_name, "birthDate": birth_date,
        "phone": phone or "", "tgUsername": tg_username or "",
        "tgId": tg_id, "date": appt_date, "time": appt_time,
        "service": service, "status": "scheduled",
        "notified": False, "createdAt": datetime.utcnow().isoformat()
    }
    ref = await db.collection("appointments").add(data)
    return ref[1].id


async def get_appointments_by_date(appt_date):
    db = get_db()
    result = []
    async for doc in db.collection("appointments").stream():
        d = doc.to_dict()
        if d.get("date") == appt_date and d.get("status") != "cancelled":
            result.append({"id": doc.id, **d})
    result.sort(key=lambda a: a.get("time", ""))
    return result


async def get_all_upcoming_appointments():
    db = get_db()
    today = date.today().isoformat()
    result = []
    async for doc in db.collection("appointments").stream():
        d = doc.to_dict()
        if d.get("date", "") >= today and d.get("status") != "cancelled":
            result.append({"id": doc.id, **d})
    result.sort(key=lambda a: (a.get("date", ""), a.get("time", "")))
    return result


async def get_appointment_by_id(appt_id):
    doc = await get_db().collection("appointments").document(appt_id).get()
    return {"id": doc.id, **doc.to_dict()} if doc.exists else None


async def update_status(appt_id, status):
    await get_db().collection("appointments").document(appt_id).update({"status": status})


async def get_appointments_for_reminder(tomorrow):
    db = get_db()
    result = []
    async for doc in db.collection("appointments").stream():
        d = doc.to_dict()
        if d.get("date") == tomorrow and d.get("status") == "scheduled" and not d.get("notified"):
            result.append({"id": doc.id, **d})
    return result


async def mark_notified(appt_id):
    await get_db().collection("appointments").document(appt_id).update({"notified": True})


async def get_patient_appointments(tg_id):
    db = get_db()
    today = date.today().isoformat()
    result = []
    async for doc in db.collection("appointments").stream():
        d = doc.to_dict()
        if d.get("tgId") == tg_id and d.get("date", "") >= today and d.get("status") != "cancelled":
            result.append({"id": doc.id, **d})
    result.sort(key=lambda a: (a.get("date", ""), a.get("time", "")))
    return result
