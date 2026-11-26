# -*- coding: utf-8 -*-
"""АвтоСервис: веб-приложение для записи на ремонт и диагностику (сервер на стандартной библиотеке Python).

Запуск:  python app.py            (откроется браузер на http://127.0.0.1:8765)
Параметры: --port N, --no-browser
Данные хранятся в файле autoservice.db рядом с программой.
"""
import datetime
import re
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import db
import diag
import views

SESSION_TTL = 8 * 3600
MAX_BODY = 64 * 1024
SESSIONS = {}
SESSIONS_LOCK = threading.Lock()
FAILED = {}  # ip -> [время неудачных входов]
FIRST_ADMIN_LOCK = threading.Lock()
ROUTES = []


# ---------------- сессии ----------------
def new_session(user_id=None):
    token = secrets.token_urlsafe(32)
    with SESSIONS_LOCK:
        SESSIONS[token] = {'user_id': user_id, 'csrf': secrets.token_urlsafe(24), 'flash': None,
                           'exp': time.time() + SESSION_TTL}
    return token


def get_session(token):
    with SESSIONS_LOCK:
        now = time.time()
        for t in [t for t, s in SESSIONS.items() if s['exp'] < now]:
            del SESSIONS[t]
        s = SESSIONS.get(token)
        if s:
            s['exp'] = now + SESSION_TTL
        return s


def too_many_failures(ip):
    now = time.time()
    FAILED[ip] = [t for t in FAILED.get(ip, []) if now - t < 300]
    return len(FAILED[ip]) >= 8


# ---------------- запрос / ответ ----------------
class Request:
    def __init__(self, handler, method):
        self.method = method
        parts = urlsplit(handler.path)
        self.path = parts.path
        self.query = {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
        self.query_all = parse_qs(parts.query, keep_blank_values=True)
        self.form, self.form_all = {}, {}
        self.ip = handler.client_address[0]
        self.token = None
        self.session = None
        self.user = None
        self.set_cookie = None

    def ctx(self):
        flash = self.session['flash']
        self.session['flash'] = None
        return {'user': self.user, 'csrf': self.session['csrf'], 'flash': flash, 'path': self.path}

    def flash(self, kind, message):
        self.session['flash'] = (kind, message)


class Response:
    def __init__(self, body='', status=200, headers=None, ctype='text/html; charset=utf-8'):
        self.body = body.encode('utf-8') if isinstance(body, str) else body
        self.status = status
        self.headers = headers or {}
        self.ctype = ctype


def redirect(url):
    return Response('', 303, {'Location': url})


def route(method, pattern, role=None):
    """role: None - любой; 'user' - клиент; 'admin' - администратор; 'any' - любой вошедший."""
    def deco(fn):
        ROUTES.append((method, re.compile('^' + pattern + '$'), role, fn))
        return fn
    return deco


def denied(req):
    if req.user:
        return Response(views.not_found(req.ctx(), 'Недостаточно прав для этой страницы'), 403)
    return redirect('/admin' if req.path.startswith('/admin') else '/login')


# ---------------- вход / выход ----------------
def login_user(req, user_id):
    with SESSIONS_LOCK:
        SESSIONS.pop(req.token, None)
    token = new_session(user_id)
    req.token = token
    req.session = get_session(token)
    req.set_cookie = token


@route('GET', '/')
def index(req):
    if req.user:
        return redirect('/admin' if req.user['role'] == 'admin' else '/cabinet')
    return Response(views.landing(req.ctx()))


@route('GET', '/login')
def login_page(req):
    return Response(views.login_form(req.ctx()))


@route('POST', '/login')
def login_post(req):
    username, password = req.form.get('username', '').strip(), req.form.get('password', '')
    if too_many_failures(req.ip):
        return Response(views.login_form(req.ctx(), error='Слишком много попыток. Подождите несколько минут.', username=username), 429)
    user = db.authenticate('user', username, password)
    if not user:
        FAILED.setdefault(req.ip, []).append(time.time())
        msg = 'Неверный логин или пароль. Сотрудники входят на отдельной странице для администратора.'
        return Response(views.login_form(req.ctx(), error=msg, username=username), 401)
    login_user(req, user['id'])
    return redirect('/cabinet')


@route('POST', '/logout')
def logout(req):
    with SESSIONS_LOCK:
        SESSIONS.pop(req.token, None)
    req.token = None
    req.session = {'csrf': '', 'flash': None, 'user_id': None}
    req.user = None
    resp = redirect('/')
    resp.headers['Set-Cookie'] = 'sid=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax'
    return resp


@route('GET', '/register')
def register_page(req):
    return Response(views.register_form(req.ctx()))


@route('POST', '/register')
def register_post(req):
    f = req.form
    values = {k: f.get(k, '').strip() for k in ('full_name', 'phone', 'username')}
    if not values['phone']:
        return Response(views.register_form(req.ctx(), 'Укажите телефон.', values), 400)
    uid, err = db.create_account('user', values['username'], f.get('password', ''), values['full_name'], values['phone'])
    if err:
        return Response(views.register_form(req.ctx(), err, values), 400)
    login_user(req, uid)
    req.flash('ok', 'Регистрация прошла успешно. Добро пожаловать!')
    return redirect('/cabinet')


# ---------------- клиент ----------------
@route('GET', '/cabinet', 'user')
def cabinet(req):
    rows = db.query('SELECT * FROM appointments WHERE user_id=? ORDER BY visit_date DESC, visit_time DESC', (req.user['id'],))
    today = datetime.date.today().isoformat()
    stats = {'total': len(rows),
             'active': sum(1 for r in rows if r['status'] in ('new', 'confirmed') and r['visit_date'] >= today),
             'done': sum(1 for r in rows if r['status'] == 'done')}
    return Response(views.cabinet(req.ctx(), rows, stats))


@route('GET', '/book', 'user')
def book_page(req):
    return Response(views.book_form(req.ctx()))


def booking_values(req):
    return {k: req.form.get(k, '').strip() for k in ('service', 'car', 'plate', 'visit_date', 'visit_time', 'description')}


@route('POST', '/book/slots', 'user')
def book_slots(req):
    v = booking_values(req)
    ctx = req.ctx()
    slots = None
    try:
        datetime.date.fromisoformat(v['visit_date'])
        slots = db.free_slots(v['visit_date'])
        ctx['flash'] = ('ok', 'Свободное время на %s: %s' % (v['visit_date'], ', '.join(slots) if slots else 'нет свободных мест'))
    except ValueError:
        ctx['flash'] = ('err', 'Сначала выберите дату.')
    return Response(views.book_form(ctx, v=v, slots=slots))


@route('POST', '/book', 'user')
def book_post(req):
    v = booking_values(req)
    err = None
    if v['service'] not in db.SERVICES:
        err = 'Выберите услугу из списка.'
    elif len(v['car']) < 2 or len(v['car']) > 60:
        err = 'Укажите марку и модель автомобиля (до 60 символов).'
    elif len(v['plate']) > 15 or len(v['description']) > 1000:
        err = 'Слишком длинное значение в одном из полей.'
    else:
        err = db.validate_booking(v['visit_date'], v['visit_time'])
    if err:
        return Response(views.book_form(req.ctx(), err, v), 400)
    db.execute('INSERT INTO appointments (user_id, service, car, plate, visit_date, visit_time, description, created_at) '
               'VALUES (?,?,?,?,?,?,?,?)',
               (req.user['id'], v['service'], v['car'], v['plate'], v['visit_date'], v['visit_time'], v['description'], db.now()))
    req.flash('ok', 'Вы записаны на %s в %s. Статус заявки можно отслеживать в кабинете.' % (v['visit_date'], v['visit_time']))
    return redirect('/cabinet')


@route('POST', r'/appointments/(\d+)/cancel', 'user')
def cancel_appointment(req, aid):
    a = db.query('SELECT * FROM appointments WHERE id=? AND user_id=?', (aid, req.user['id']), one=True)
    if not a or a['status'] not in ('new', 'confirmed'):
        req.flash('err', 'Эту запись отменить нельзя.')
    else:
        db.execute("UPDATE appointments SET status='cancelled' WHERE id=?", (a['id'],))
        req.flash('ok', 'Запись отменена.')
    return redirect('/cabinet')


@route('GET', '/feedback', 'user')
def feedback_page(req):
    items = db.query('SELECT * FROM feedback WHERE user_id=? ORDER BY id DESC', (req.user['id'],))
    return Response(views.feedback_page(req.ctx(), items))


@route('POST', '/feedback', 'user')
def feedback_post(req):
    kind, message = req.form.get('kind', ''), req.form.get('message', '').strip()
    if kind not in views.KINDS or len(message) < 5 or len(message) > 2000:
        items = db.query('SELECT * FROM feedback WHERE user_id=? ORDER BY id DESC', (req.user['id'],))
        return Response(views.feedback_page(req.ctx(), items, 'Выберите тип и напишите сообщение (от 5 до 2000 символов).', {'kind': kind}), 400)
    db.execute('INSERT INTO feedback (user_id, kind, message, created_at) VALUES (?,?,?,?)', (req.user['id'], kind, message, db.now()))
    req.flash('ok', 'Спасибо! Обращение отправлено.')
    return redirect('/feedback')


# ---------------- справочник и диагностика (клиент и администратор) ----------------
@route('GET', '/codes', 'any')
def codes_list(req):
    q, system = req.query.get('q', ''), req.query.get('system', '')
    return Response(views.codes_page(req.ctx(), db.search_codes(q, system), q, system))


@route('GET', r'/codes/([A-Za-z0-9]{5})', 'any')
def code_view(req, code):
    row = db.get_code(code.upper())
    if not row:
        return Response(views.not_found(req.ctx(), 'Такого кода нет в базе'), 404)
    return Response(views.code_detail(req.ctx(), row, db.symptoms_for_code(row['code'])))


def run_diagnostics(req, source):
    values = {'codes': source.get('codes', ''), 'free_text': source.get('free_text', '')[:500],
              'symptoms': []}
    for x in (req.form_all.get('symptom', []) if req.method == 'POST' else []):
        if x.isdigit():
            values['symptoms'].append(int(x))
    result = diag.diagnose(values['codes'][:200], values['symptoms'], values['free_text']) \
        if (values['codes'] or values['symptoms'] or values['free_text']) else None
    return Response(views.diagnostics_page(req.ctx(), db.all_symptoms(), values, result))


@route('GET', '/diagnostics', 'any')
def diagnostics_get(req):
    return run_diagnostics(req, req.query)


@route('POST', '/diagnostics', 'any')
def diagnostics_post(req):
    return run_diagnostics(req, req.form)


# ---------------- администратор ----------------
@route('GET', '/admin')
def admin_entry(req):
    if req.user and req.user['role'] == 'admin':
        stats = {
            'new': db.query("SELECT COUNT(*) n FROM appointments WHERE status='new'", one=True)['n'],
            'today': db.query("SELECT COUNT(*) n FROM appointments WHERE visit_date=? AND status!='cancelled'",
                              (datetime.date.today().isoformat(),), one=True)['n'],
            'fb_new': db.query("SELECT COUNT(*) n FROM feedback WHERE status='new'", one=True)['n'],
            'users': db.query("SELECT COUNT(*) n FROM users WHERE role='user'", one=True)['n'],
            'codes': db.query('SELECT COUNT(*) n FROM obd_codes', one=True)['n'],
            'symptoms': db.query('SELECT COUNT(*) n FROM symptoms', one=True)['n'],
        }
        recent = db.query("SELECT a.*, u.full_name FROM appointments a JOIN users u ON u.id=a.user_id "
                          "WHERE a.visit_date >= ? AND a.status != 'cancelled' ORDER BY a.visit_date, a.visit_time LIMIT 8",
                          (datetime.date.today().isoformat(),))
        return Response(views.admin_dashboard(req.ctx(), stats, recent))
    if req.user:
        return denied(req)
    return Response(views.login_form(req.ctx(), admin=True, first_admin=not db.admin_exists()))


@route('GET', '/admin/login')
def admin_login_page(req):
    return redirect('/admin')


@route('POST', '/admin/login')
def admin_login_post(req):
    username, password = req.form.get('username', '').strip(), req.form.get('password', '')
    if too_many_failures(req.ip):
        return Response(views.login_form(req.ctx(), admin=True, first_admin=not db.admin_exists(),
                                         error='Слишком много попыток. Подождите несколько минут.', username=username), 429)
    with FIRST_ADMIN_LOCK:
        first = not db.admin_exists()
        if first:  # первый вход = регистрация главного администратора
            uid, err = db.create_account('admin', username, password, req.form.get('full_name', ''))
            if err:
                return Response(views.login_form(req.ctx(), admin=True, first_admin=True, error=err, username=username), 400)
            login_user(req, uid)
            req.flash('ok', 'Администратор зарегистрирован. Теперь вы можете создавать другие учётные записи.')
            return redirect('/admin')
    user = db.authenticate('admin', username, password)
    if not user:
        FAILED.setdefault(req.ip, []).append(time.time())
        return Response(views.login_form(req.ctx(), admin=True, error='Неверный логин или пароль администратора.', username=username), 401)
    login_user(req, user['id'])
    return redirect('/admin')


@route('GET', '/admin/appointments', 'admin')
def admin_appointments(req):
    status = req.query.get('status', '')
    sql = ('SELECT a.*, u.full_name, u.phone FROM appointments a JOIN users u ON u.id=a.user_id')
    args = ()
    if status in db.STATUSES:
        sql += ' WHERE a.status=?'
        args = (status,)
    rows = db.query(sql + ' ORDER BY a.visit_date DESC, a.visit_time DESC LIMIT 300', args)
    return Response(views.admin_appointments(req.ctx(), rows, status))


@route('POST', r'/admin/appointments/(\d+)', 'admin')
def admin_appointment_update(req, aid):
    status = req.form.get('status', '')
    if status not in db.STATUSES:
        req.flash('err', 'Недопустимый статус.')
    else:
        db.execute('UPDATE appointments SET status=?, admin_note=? WHERE id=?', (status, req.form.get('admin_note', '').strip()[:300], aid))
        req.flash('ok', 'Запись #%s обновлена.' % aid)
    return redirect('/admin/appointments')


@route('GET', '/admin/feedback', 'admin')
def admin_feedback(req):
    rows = db.query('SELECT f.*, u.full_name, u.phone FROM feedback f JOIN users u ON u.id=f.user_id '
                    "ORDER BY (f.status='new') DESC, f.id DESC LIMIT 300")
    return Response(views.admin_feedback(req.ctx(), rows))


@route('POST', r'/admin/feedback/(\d+)', 'admin')
def admin_feedback_reply(req, fid):
    db.execute("UPDATE feedback SET admin_reply=?, status='processed' WHERE id=?", (req.form.get('admin_reply', '').strip()[:1000], fid))
    req.flash('ok', 'Обращение отмечено как обработанное.')
    return redirect('/admin/feedback')


@route('GET', '/admin/users', 'admin')
def admin_users(req):
    rows = db.query("SELECT u.*, (SELECT COUNT(*) FROM appointments a WHERE a.user_id=u.id) AS n "
                    "FROM users u WHERE role='user' ORDER BY u.id DESC")
    return Response(views.admin_users(req.ctx(), rows))


@route('POST', r'/admin/users/(\d+)/delete', 'admin')
def admin_user_delete(req, uid):
    db.execute("DELETE FROM users WHERE id=? AND role='user'", (uid,))
    req.flash('ok', 'Клиент удалён.')
    return redirect('/admin/users')


@route('GET', '/admin/admins', 'admin')
def admin_admins(req):
    return Response(views.admin_admins(req.ctx(), db.query("SELECT * FROM users WHERE role='admin' ORDER BY id")))


@route('POST', '/admin/admins', 'admin')
def admin_admin_create(req):
    f = req.form
    values = {'full_name': f.get('full_name', '').strip(), 'username': f.get('username', '').strip()}
    uid, err = db.create_account('admin', values['username'], f.get('password', ''), values['full_name'])
    if err:
        rows = db.query("SELECT * FROM users WHERE role='admin' ORDER BY id")
        return Response(views.admin_admins(req.ctx(), rows, err, values), 400)
    req.flash('ok', 'Администратор «%s» создан.' % values['username'])
    return redirect('/admin/admins')


@route('POST', r'/admin/admins/(\d+)/delete', 'admin')
def admin_admin_delete(req, uid):
    uid = int(uid)
    if uid == req.user['id']:
        req.flash('err', 'Нельзя удалить собственную учётную запись.')
    else:
        db.execute("DELETE FROM users WHERE id=? AND role='admin'", (uid,))
        req.flash('ok', 'Учётная запись администратора удалена.')
    return redirect('/admin/admins')


CODE_FMT = re.compile(r'^[PBCU][0-9A-F]{4}$')


def code_values(form):
    return {'title': form.get('title', '').strip(), 'severity': form.get('severity', '2'),
            'causes': form.get('causes', '').strip(), 'fixes': form.get('fixes', '').strip()}


def code_error(v):
    if not v['title'] or len(v['title']) > 200:
        return 'Укажите описание (до 200 символов).'
    if v['severity'] not in ('1', '2', '3'):
        return 'Недопустимая серьёзность.'
    return None


def norm_lines(text):
    return db.SEP.join(x.strip() for x in text.replace('\r', '').split('\n') if x.strip())


@route('GET', '/admin/codes', 'admin')
def admin_codes(req):
    q = req.query.get('q', '')
    return Response(views.admin_codes(req.ctx(), db.search_codes(q), q))


@route('GET', '/admin/codes/new', 'admin')
def admin_code_new(req):
    return Response(views.code_form(req.ctx()))


@route('POST', '/admin/codes/new', 'admin')
def admin_code_create(req):
    code = req.form.get('code', '').strip().upper()
    v = code_values(req.form)
    err = None if CODE_FMT.match(code) else 'Код должен выглядеть как P0300 (буква P, B, C или U и 4 символа 0-9, A-F).'
    err = err or code_error(v)
    if not err and db.get_code(code):
        err = 'Такой код уже есть в базе.'
    if err:
        return Response(views.code_form(req.ctx(), dict(v, code=code), err), 400)
    db.execute('INSERT INTO obd_codes VALUES (?,?,?,?,?)', (code, v['title'], int(v['severity']), norm_lines(v['causes']), norm_lines(v['fixes'])))
    req.flash('ok', 'Код %s добавлен.' % code)
    return redirect('/admin/codes')


@route('GET', r'/admin/codes/([A-Za-z0-9]{5})/edit', 'admin')
def admin_code_edit(req, code):
    row = db.get_code(code.upper())
    if not row:
        return Response(views.not_found(req.ctx(), 'Такого кода нет в базе'), 404)
    return Response(views.code_form(req.ctx(), dict(row)))


@route('POST', r'/admin/codes/([A-Za-z0-9]{5})/edit', 'admin')
def admin_code_update(req, code):
    row = db.get_code(code.upper())
    if not row:
        return Response(views.not_found(req.ctx(), 'Такого кода нет в базе'), 404)
    v = code_values(req.form)
    err = code_error(v)
    if err:
        return Response(views.code_form(req.ctx(), dict(v, code=row['code']), err), 400)
    db.execute('UPDATE obd_codes SET title=?, severity=?, causes=?, fixes=? WHERE code=?',
               (v['title'], int(v['severity']), norm_lines(v['causes']), norm_lines(v['fixes']), row['code']))
    req.flash('ok', 'Код %s обновлён.' % row['code'])
    return redirect('/admin/codes')


@route('POST', r'/admin/codes/([A-Za-z0-9]{5})/delete', 'admin')
def admin_code_delete(req, code):
    db.execute('DELETE FROM obd_codes WHERE code=?', (code.upper(),))
    req.flash('ok', 'Код удалён.')
    return redirect('/admin/codes')


@route('GET', '/admin/symptoms', 'admin')
def admin_symptoms(req):
    return Response(views.admin_symptoms(req.ctx(), db.all_symptoms()))


@route('GET', '/admin/symptoms/new', 'admin')
def admin_symptom_new(req):
    return Response(views.symptom_form(req.ctx()))


def symptom_values(form):
    return {'name': form.get('name', '').strip(), 'description': form.get('description', '').strip(),
            'keywords': form.get('keywords', '').strip(), 'causes': norm_lines(form.get('causes', '')),
            'checks': norm_lines(form.get('checks', ''))}


def save_symptom(req, sid=None):
    v = symptom_values(req.form)
    codes_text = req.form.get('codes', '')
    codes = diag.parse_codes(codes_text)
    err = None
    if not v['name'] or len(v['name']) > 120:
        err = 'Укажите название симптома (до 120 символов).'
    else:
        dup = db.query('SELECT id FROM symptoms WHERE name=?', (v['name'],), one=True)
        if dup and dup['id'] != sid:
            err = 'Симптом с таким названием уже есть.'
    unknown = [c for c in codes if not db.get_code(c)]
    if not err and unknown:
        err = 'Этих кодов нет в базе: %s. Сначала добавьте их в справочник.' % ', '.join(unknown)
    if err:
        row = dict(v, id=sid) if sid else dict(v)
        return Response(views.symptom_form(req.ctx(), row, codes_text, err), 400)
    c = db.connect()
    try:
        if sid:
            c.execute('UPDATE symptoms SET name=?, description=?, keywords=?, causes=?, checks=? WHERE id=?',
                      (v['name'], v['description'], v['keywords'], v['causes'], v['checks'], sid))
            c.execute('DELETE FROM symptom_codes WHERE symptom_id=?', (sid,))
        else:
            sid = c.execute('INSERT INTO symptoms (name, description, keywords, causes, checks) VALUES (?,?,?,?,?)',
                            (v['name'], v['description'], v['keywords'], v['causes'], v['checks'])).lastrowid
        for code in codes:
            c.execute('INSERT OR IGNORE INTO symptom_codes VALUES (?,?)', (sid, db.get_code(code)['code']))
        c.commit()
    finally:
        c.close()
    req.flash('ok', 'Симптом сохранён.')
    return redirect('/admin/symptoms')


@route('POST', '/admin/symptoms/new', 'admin')
def admin_symptom_create(req):
    return save_symptom(req)


@route('GET', r'/admin/symptoms/(\d+)/edit', 'admin')
def admin_symptom_edit(req, sid):
    row = db.get_symptom(int(sid))
    if not row:
        return Response(views.not_found(req.ctx(), 'Симптом не найден'), 404)
    codes = ', '.join(c['code'] for c in db.codes_for_symptom(row['id']))
    return Response(views.symptom_form(req.ctx(), dict(row), codes))


@route('POST', r'/admin/symptoms/(\d+)/edit', 'admin')
def admin_symptom_update(req, sid):
    if not db.get_symptom(int(sid)):
        return Response(views.not_found(req.ctx(), 'Симптом не найден'), 404)
    return save_symptom(req, int(sid))


@route('POST', r'/admin/symptoms/(\d+)/delete', 'admin')
def admin_symptom_delete(req, sid):
    db.execute('DELETE FROM symptoms WHERE id=?', (int(sid),))
    req.flash('ok', 'Симптом удалён.')
    return redirect('/admin/symptoms')


# ---------------- HTTP-сервер ----------------
class Handler(BaseHTTPRequestHandler):
    server_version = 'AutoService/1.0'

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def send(self, resp, req=None):
        self.send_response(resp.status)
        self.send_header('Content-Type', resp.ctype)
        self.send_header('Content-Length', str(len(resp.body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-store')
        if req is not None and req.set_cookie:
            self.send_header('Set-Cookie', 'sid=%s; Path=/; HttpOnly; SameSite=Lax; Max-Age=%d' % (req.set_cookie, SESSION_TTL))
        for k, v in resp.headers.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(resp.body)

    def dispatch(self, method):
        req = Request(self, method)
        # защита от DNS-rebinding: принимаем только обращения к локальному адресу
        host = (self.headers.get('Host') or '').split(':')[0].lower()
        if host not in ('127.0.0.1', 'localhost', '[::1]'):
            return self.send(Response('Неверный адрес', 400))
        cookie = self.headers.get('Cookie', '')
        m = re.search(r'(?:^|;\s*)sid=([A-Za-z0-9_\-]+)', cookie)
        req.token = m.group(1) if m else None
        req.session = get_session(req.token) if req.token else None
        if req.session is None:
            req.token = new_session()
            req.session = get_session(req.token)
            req.set_cookie = req.token
        if req.session['user_id']:
            req.user = db.query('SELECT * FROM users WHERE id=?', (req.session['user_id'],), one=True)
            if not req.user:
                req.session['user_id'] = None
        try:
            if req.path == '/favicon.ico':
                return self.send(Response('', 204), req)
            if method == 'POST':
                length = int(self.headers.get('Content-Length') or 0)
                if length > MAX_BODY:
                    return self.send(Response('Слишком большой запрос', 413), req)
                raw = self.rfile.read(length).decode('utf-8', 'replace')
                req.form_all = parse_qs(raw, keep_blank_values=True)
                req.form = {k: v[0] for k, v in req.form_all.items()}
                if not secrets.compare_digest(req.form.get('_csrf', ''), req.session['csrf']):
                    return self.send(Response(views.not_found(req.ctx(), 'Сессия устарела. Вернитесь назад, обновите страницу и повторите.'), 403), req)
            path_matched = False
            for m_, pattern, role, fn in ROUTES:
                match = pattern.match(req.path)
                if not match:
                    continue
                path_matched = True
                if m_ != method:
                    continue
                if role == 'any' and not req.user:
                    resp = denied(req)
                elif role in ('user', 'admin') and (not req.user or req.user['role'] != role):
                    resp = denied(req)
                else:
                    resp = fn(req, *match.groups())
                return self.send(resp, req)
            status = 405 if path_matched else 404
            return self.send(Response(views.not_found(req.ctx()), status), req)
        except Exception as exc:  # не показываем пользователю трассировку
            print('Ошибка при обработке %s %s: %r' % (method, req.path, exc), file=sys.stderr)
            return self.send(Response('<h1>Внутренняя ошибка сервера</h1><p><a href="/">На главную</a></p>', 500), req)


def make_server(port):
    last = None
    for p in range(port, port + 20):
        try:
            return ThreadingHTTPServer(('127.0.0.1', p), Handler), p
        except OSError as exc:
            last = exc
    raise last


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    port = 8765
    if '--port' in argv:
        port = int(argv[argv.index('--port') + 1])
    db.init_db()
    server, port = make_server(port)
    url = 'http://127.0.0.1:%d/' % port
    print('=' * 60)
    print(' АвтоСервис запущен: %s' % url)
    print(' База данных: %s' % db.db_path())
    print(' Для остановки закройте это окно или нажмите Ctrl+C.')
    print('=' * 60)
    if '--no-browser' not in argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nОстановлено.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
