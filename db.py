# -*- coding: utf-8 -*-
"""Работа с локальной базой данных SQLite."""
import datetime
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import sys

from obd_data import CODES, SYMPTOMS

SEP = '\n'  # разделитель списков (причины, проверки) внутри текстовых полей

SERVICES = [
    'Компьютерная диагностика (OBD-II)',
    'Диагностика ходовой части',
    'Плановое ТО (масло и фильтры)',
    'Ремонт двигателя',
    'Ремонт тормозной системы',
    'Ремонт подвески',
    'Ремонт АКПП / КПП',
    'Автоэлектрика',
    'Шиномонтаж',
    'Другое',
]
SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
SLOT_CAPACITY = 2  # сколько записей принимается на одно время
STATUSES = {
    'new': 'Новая',
    'confirmed': 'Подтверждена',
    'done': 'Выполнена',
    'cancelled': 'Отменена',
}


def app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def db_path():
    return os.environ.get('AUTOSERVICE_DB') or os.path.join(app_dir(), 'autoservice.db')


def connect():
    c = sqlite3.connect(db_path(), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys = ON')
    return c


def query(sql, args=(), one=False):
    c = connect()
    try:
        rows = c.execute(sql, args).fetchall()
    finally:
        c.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    c = connect()
    try:
        cur = c.execute(sql, args)
        c.commit()
        return cur.lastrowid
    finally:
        c.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL CHECK (role IN ('admin','user')),
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service TEXT NOT NULL,
    car TEXT NOT NULL,
    plate TEXT NOT NULL DEFAULT '',
    visit_date TEXT NOT NULL,
    visit_time TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new',
    admin_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('recommendation','complaint')),
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    admin_reply TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS obd_codes (
    code TEXT PRIMARY KEY COLLATE NOCASE,
    title TEXT NOT NULL,
    severity INTEGER NOT NULL DEFAULT 2,
    causes TEXT NOT NULL DEFAULT '',
    fixes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS symptoms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    causes TEXT NOT NULL DEFAULT '',
    checks TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS symptom_codes (
    symptom_id INTEGER NOT NULL REFERENCES symptoms(id) ON DELETE CASCADE,
    code TEXT NOT NULL REFERENCES obd_codes(code) ON DELETE CASCADE ON UPDATE CASCADE,
    PRIMARY KEY (symptom_id, code)
);
"""


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


def init_db():
    c = connect()
    try:
        c.executescript(SCHEMA)
        c.commit()
        if c.execute('SELECT COUNT(*) FROM obd_codes').fetchone()[0] == 0:
            for code, title, sev, causes, fixes in CODES:
                c.execute('INSERT OR IGNORE INTO obd_codes VALUES (?,?,?,?,?)',
                          (code, title, sev, SEP.join(causes), SEP.join(fixes)))
            c.commit()
        if c.execute('SELECT COUNT(*) FROM symptoms').fetchone()[0] == 0:
            for name, desc, kw, causes, checks, codes in SYMPTOMS:
                cur = c.execute(
                    'INSERT OR IGNORE INTO symptoms (name, description, keywords, causes, checks) VALUES (?,?,?,?,?)',
                    (name, desc, kw, SEP.join(causes), SEP.join(checks)))
                sid = cur.lastrowid
                for code in codes:
                    c.execute('INSERT OR IGNORE INTO symptom_codes VALUES (?,?)', (sid, code))
            c.commit()
    finally:
        c.close()


# ---------------- пароли ----------------
ITERATIONS = 200_000


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return 'pbkdf2$%d$%s$%s' % (ITERATIONS, salt.hex(), digest.hex())


def check_password(password, stored):
    try:
        _, it, salt, digest = stored.split('$')
        calc = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(calc.hex(), digest)
    except (ValueError, AttributeError):
        return False


# ---------------- пользователи ----------------
USERNAME_RE = re.compile(r'^[A-Za-z0-9_.-]{3,32}$')


def admin_exists():
    return query("SELECT 1 FROM users WHERE role='admin' LIMIT 1", one=True) is not None


def validate_account(username, password, full_name, phone=''):
    """Возвращает текст ошибки или None."""
    if not USERNAME_RE.match(username or ''):
        return 'Логин: 3-32 символа, только латиница, цифры и знаки _ . -'
    if len(password or '') < 8:
        return 'Пароль должен содержать не менее 8 символов.'
    if len((full_name or '').strip()) < 2:
        return 'Укажите имя.'
    if phone and not re.match(r'^[0-9+()\-\s]{5,20}$', phone):
        return 'Телефон указан в неверном формате.'
    return None


def create_account(role, username, password, full_name, phone=''):
    err = validate_account(username, password, full_name, phone)
    if err:
        return None, err
    if query('SELECT 1 FROM users WHERE username = ?', (username,), one=True):
        return None, 'Такой логин уже занят.'
    uid = execute(
        'INSERT INTO users (role, username, full_name, phone, password_hash, created_at) VALUES (?,?,?,?,?,?)',
        (role, username, full_name.strip(), phone.strip(), hash_password(password), now()))
    return uid, None


def authenticate(role, username, password):
    row = query('SELECT * FROM users WHERE username = ? AND role = ?', (username, role), one=True)
    # проверка выполняется и для несуществующего логина, чтобы не выдавать его наличие по времени
    stored = row['password_hash'] if row else hash_password('dummy-password')
    ok = check_password(password, stored)
    return row if (row and ok) else None


# ---------------- записи на обслуживание ----------------
def validate_booking(visit_date, visit_time):
    try:
        d = datetime.date.fromisoformat(visit_date)
    except ValueError:
        return 'Укажите корректную дату.'
    today = datetime.date.today()
    if d < today:
        return 'Нельзя записаться на прошедшую дату.'
    if d > today + datetime.timedelta(days=90):
        return 'Запись открыта не более чем на 90 дней вперёд.'
    if d.weekday() == 6:
        return 'В воскресенье автосервис не работает.'
    if visit_time not in SLOTS:
        return 'Выберите время из списка.'
    if d == today and visit_time <= datetime.datetime.now().strftime('%H:%M'):
        return 'Это время уже прошло.'
    busy = query("SELECT COUNT(*) AS n FROM appointments WHERE visit_date=? AND visit_time=? AND status!='cancelled'",
                 (visit_date, visit_time), one=True)['n']
    if busy >= SLOT_CAPACITY:
        return 'Это время уже занято, выберите другое.'
    return None


def free_slots(visit_date):
    rows = query("SELECT visit_time, COUNT(*) AS n FROM appointments "
                 "WHERE visit_date=? AND status!='cancelled' GROUP BY visit_time", (visit_date,))
    taken = {r['visit_time']: r['n'] for r in rows}
    return [s for s in SLOTS if taken.get(s, 0) < SLOT_CAPACITY]


# ---------------- справочник ----------------
def split_list(text):
    return [x.strip() for x in (text or '').split(SEP) if x.strip()]


def all_codes():
    return query('SELECT * FROM obd_codes ORDER BY code')


def search_codes(text='', system=''):
    text = (text or '').strip().lower()
    out = []
    for r in all_codes():
        if system and not r['code'].upper().startswith(system.upper()):
            continue
        if text:
            hay = ' '.join([r['code'], r['title'], r['causes'], r['fixes']]).lower()
            if text not in hay:
                continue
        out.append(r)
    return out


def get_code(code):
    return query('SELECT * FROM obd_codes WHERE code = ?', (code,), one=True)


def symptoms_for_code(code):
    return query('SELECT s.* FROM symptoms s JOIN symptom_codes sc ON sc.symptom_id = s.id '
                 'WHERE sc.code = ? ORDER BY s.name', (code,))


def codes_for_symptom(symptom_id):
    return query('SELECT c.* FROM obd_codes c JOIN symptom_codes sc ON sc.code = c.code '
                 'WHERE sc.symptom_id = ? ORDER BY c.code', (symptom_id,))


def all_symptoms():
    return query('SELECT * FROM symptoms ORDER BY name')


def get_symptom(symptom_id):
    return query('SELECT * FROM symptoms WHERE id = ?', (symptom_id,), one=True)
