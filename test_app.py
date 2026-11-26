# -*- coding: utf-8 -*-
"""Сквозные тесты: поднимают сервер на временной базе и проверяют основные сценарии.

Запуск:  python test_app.py
"""
import datetime
import http.cookiejar
import os
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request

tmp = tempfile.mkdtemp()
os.environ['AUTOSERVICE_DB'] = os.path.join(tmp, 'test.db')

import app  # noqa: E402
import db  # noqa: E402

db.init_db()
server, PORT = app.make_server(18765)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = 'http://127.0.0.1:%d' % PORT


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), NoRedirect())

    def _do(self, req):
        try:
            r = self.opener.open(req)
        except urllib.error.HTTPError as exc:
            r = exc
        return r.status if hasattr(r, 'status') else r.code, r.read().decode('utf-8'), dict(r.headers)

    def get(self, path, follow=True):
        st, body, h = self._do(urllib.request.Request(BASE + urllib.parse.quote(path, safe="/?=&%")))
        if follow and st in (301, 302, 303):
            return self.get(h['Location'])
        return st, body, h

    def csrf(self, path='/'):
        _, body, _ = self.get(path)
        m = re.search(r'name="_csrf" value="([^"]+)"', body)
        return m.group(1) if m else ''

    def post(self, path, data, csrf=True, follow=True, csrf_from='/'):
        data = dict(data)
        if csrf:
            data['_csrf'] = self.csrf(csrf_from)
        raw = urllib.parse.urlencode(data, doseq=True).encode()
        st, body, h = self._do(urllib.request.Request(BASE + path, data=raw))
        if follow and st in (301, 302, 303):
            return self.get(h['Location'])
        return st, body, h


passed, failed = 0, []


def check(name, cond, info=''):
    global passed
    if cond:
        passed += 1
        print('  ok   ', name)
    else:
        failed.append(name)
        print('  FAIL ', name, info)


def next_weekday(offset_days=3, weekday_not=(6,)):
    d = datetime.date.today() + datetime.timedelta(days=offset_days)
    while d.weekday() in weekday_not:
        d += datetime.timedelta(days=1)
    return d


def next_sunday():
    d = datetime.date.today() + datetime.timedelta(days=1)
    while d.weekday() != 6:
        d += datetime.timedelta(days=1)
    return d


print('== Общие страницы и защита ==')
c = Client()
st, body, _ = c.get('/')
check('главная открывается', st == 200 and 'АвтоСервис' in body)
st, _, _ = c.post('/login', {'username': 'x', 'password': 'y'}, csrf=False)
check('POST без CSRF-токена отклоняется', st == 403)
st, _, _ = c.get('/cabinet', follow=False)
check('кабинет без входа перенаправляет', st == 303)
st, _, _ = c.get('/nonexistent')
check('404 для неизвестной страницы', st == 404)

print('== Первый вход администратора = регистрация ==')
adm = Client()
st, body, _ = adm.get('/admin')
check('на первом запуске предлагается регистрация администратора', 'Первый запуск' in body)
st, body, _ = adm.post('/admin/login', {'username': 'boss', 'password': 'short', 'full_name': 'Босс'}, csrf_from='/admin')
check('короткий пароль отклоняется', st == 400 and '8 символов' in body)
st, body, _ = adm.post('/admin/login', {'username': 'boss', 'password': 'StrongPass1', 'full_name': 'Главный админ'}, csrf_from='/admin')
check('первый вход регистрирует администратора', st == 200 and 'Панель администратора' in body, body[:200])
check('в базе один администратор', len(db.query("SELECT 1 FROM users WHERE role='admin'")) == 1)

other = Client()
st, body, _ = other.get('/admin')
check('после регистрации показывается обычный вход', 'Вход для администратора' in body and 'Первый запуск' not in body)
st, body, _ = other.post('/admin/login', {'username': 'hacker', 'password': 'HackerPass1', 'full_name': 'X'}, csrf_from='/admin')
check('посторонний не может зарегистрироваться как админ', st == 401 and len(db.query("SELECT 1 FROM users WHERE role='admin'")) == 1)
st, body, _ = other.post('/admin/login', {'username': 'boss', 'password': 'wrongpass'}, csrf_from='/admin')
check('неверный пароль админа отклоняется', st == 401)

print('== Администратор создаёт администраторов ==')
st, body, _ = adm.post('/admin/admins', {'full_name': 'Второй', 'username': 'second', 'password': 'SecondPass1'}, csrf_from='/admin/admins')
check('создание второго администратора', 'second' in body and st == 200)
st, body, _ = adm.post('/admin/admins', {'full_name': 'Дубль', 'username': 'SECOND', 'password': 'SecondPass1'}, csrf_from='/admin/admins')
check('дубликат логина (без учёта регистра) отклоняется', st == 400 and 'занят' in body)
adm2 = Client()
st, body, _ = adm2.post('/admin/login', {'username': 'second', 'password': 'SecondPass1'}, csrf_from='/admin')
check('второй администратор входит', 'Панель администратора' in body)
second_id = db.query("SELECT id FROM users WHERE username='second'", one=True)['id']
boss_id = db.query("SELECT id FROM users WHERE username='boss'", one=True)['id']
st, body, _ = adm.post('/admin/admins/%d/delete' % boss_id, {}, csrf_from='/admin/admins')
check('нельзя удалить самого себя', 'Нельзя удалить' in body)

print('== Клиент: регистрация, вход, разделение ролей ==')
u = Client()
xss = '<script>alert(1)</script>'
st, body, _ = u.post('/register', {'full_name': xss, 'phone': '+7 700 111 22 33', 'username': 'ivan', 'password': 'IvanPass123'}, csrf_from='/register')
check('регистрация клиента', st == 200 and 'Личный кабинет' in body or 'Здравствуйте' in body, body[:200])
check('HTML в имени экранируется (XSS)', xss not in body and '&lt;script&gt;' in body)
st, body, _ = u.post('/register', {'full_name': 'Дубль', 'phone': '+7 700', 'username': 'ivan', 'password': 'IvanPass123'}, csrf_from='/register')
check('повторная регистрация логина отклоняется', st == 400 and 'занят' in body)
st, _, _ = u.get('/admin/users')
check('клиент не имеет доступа к админ-страницам', st == 403)
st, _, _ = adm.get('/cabinet')
check('администратор не попадает в кабинет клиента', st == 403)
st, body, _ = Client().post('/login', {'username': 'boss', 'password': 'StrongPass1'}, csrf_from='/login')
check('админ не может войти через клиентскую форму', st == 401)

print('== Запись на обслуживание ==')
good = next_weekday(3)
data = {'service': db.SERVICES[0], 'car': 'Toyota Camry 2012', 'plate': '123ABC01',
        'visit_date': good.isoformat(), 'visit_time': '10:00', 'description': 'Горит Check Engine'}
st, body, _ = u.post('/book', data, csrf_from='/book')
check('запись создаётся', st == 200 and 'Вы записаны' in body, body[:300])
st, body, _ = u.post('/book', dict(data, visit_date=next_sunday().isoformat()), csrf_from='/book')
check('воскресенье отклоняется', st == 400 and 'воскресенье' in body)
st, body, _ = u.post('/book', dict(data, visit_date=(datetime.date.today() - datetime.timedelta(days=1)).isoformat()), csrf_from='/book')
check('прошедшая дата отклоняется', st == 400 and 'прошедшую' in body)
st, body, _ = u.post('/book', dict(data, visit_date=(datetime.date.today() + datetime.timedelta(days=200)).isoformat()), csrf_from='/book')
check('слишком далёкая дата отклоняется', st == 400)
st, body, _ = u.post('/book', dict(data, visit_time='03:00'), csrf_from='/book')
check('время вне списка отклоняется', st == 400)
st, body, _ = u.post('/book', dict(data, service='Взлом'), csrf_from='/book')
check('услуга вне списка отклоняется', st == 400)
u.post('/book', data, csrf_from='/book')
st, body, _ = u.post('/book', data, csrf_from='/book')
check('лимит записей на одно время (3-я запись отклонена)', st == 400 and 'занято' in body)
st, body, _ = u.post('/book/slots', {'visit_date': good.isoformat()}, csrf_from='/book')
check('показ свободного времени', st == 200 and '10:00' not in body.split('Свободное время')[1].split('</div>')[0])
appt = db.query('SELECT id FROM appointments ORDER BY id', one=True)['id']

print('== Админ управляет записями ==')
st, body, _ = adm.post('/admin/appointments/%d' % appt, {'status': 'confirmed', 'admin_note': 'Ждём вас'}, csrf_from='/admin/appointments')
check('администратор подтверждает запись', 'Запись #%d обновлена' % appt in body)
st, body, _ = u.get('/cabinet')
check('клиент видит статус и комментарий', 'Подтверждена' in body and 'Ждём вас' in body)
st, body, _ = adm.post('/admin/appointments/%d' % appt, {'status': 'hacked'}, csrf_from='/admin/appointments')
check('недопустимый статус отклоняется', 'Недопустимый статус' in body)

u2 = Client()
u2.post('/register', {'full_name': 'Пётр', 'phone': '+7 701 000 00 00', 'username': 'petr', 'password': 'PetrPass1234'}, csrf_from='/register')
u2.post('/appointments/%d/cancel' % appt, {}, csrf_from='/cabinet')
check('чужую запись отменить нельзя', db.query('SELECT status FROM appointments WHERE id=?', (appt,), one=True)['status'] == 'confirmed')
u.post('/appointments/%d/cancel' % appt, {}, csrf_from='/cabinet')
check('свою запись можно отменить', db.query('SELECT status FROM appointments WHERE id=?', (appt,), one=True)['status'] == 'cancelled')

print('== Рекомендации и жалобы ==')
st, body, _ = u.post('/feedback', {'kind': 'complaint', 'message': 'Долго ждал в очереди'}, csrf_from='/feedback')
check('жалоба сохраняется', 'Долго ждал' in body and 'Жалоба' in body)
st, body, _ = u.post('/feedback', {'kind': 'recommendation', 'message': 'ок'}, csrf_from='/feedback')
check('слишком короткое сообщение отклоняется', st == 400)
fid = db.query('SELECT id FROM feedback', one=True)['id']
st, body, _ = adm.post('/admin/feedback/%d' % fid, {'admin_reply': 'Приносим извинения'}, csrf_from='/admin/feedback')
st, body, _ = u.get('/feedback')
check('клиент видит ответ сервиса', 'Приносим извинения' in body and 'Обработано' in body)

print('== Справочник OBD-II и диагностика ==')
n_codes = db.query('SELECT COUNT(*) n FROM obd_codes', one=True)['n']
check('в базе не менее 100 кодов', n_codes >= 100, n_codes)
check('в базе не менее 20 симптомов', db.query('SELECT COUNT(*) n FROM symptoms', one=True)['n'] >= 20)
st, body, _ = u.get('/codes?q=P0300')
check('поиск кода', 'P0300' in body and 'пропуски' in body.lower())
st, body, _ = u.get('/codes?q=катализатор')
check('поиск по кириллице', 'P0420' in body)
st, body, _ = u.get('/codes/p0171')
check('карточка кода (нечувствительна к регистру)', st == 200 and 'слишком бедная' in body)
st, body, _ = u.post('/diagnostics', {'codes': 'P0300, p0171 U9999', 'free_text': ''}, csrf_from='/diagnostics')
check('диагностика по кодам: причины и расшифровка', 'Вероятные причины' in body and 'Подсос воздуха' in body and 'U9999' in body)
st, body, _ = u.post('/diagnostics', {'codes': '', 'free_text': 'двигатель троит на холостом'}, csrf_from='/diagnostics')
check('диагностика по свободному тексту', 'Двигатель троит' in body and 'Вероятные причины' in body)
sid = db.query("SELECT id FROM symptoms WHERE name='Перегрев двигателя'", one=True)['id']
st, body, _ = u.post('/diagnostics', {'codes': 'P0217', 'symptom': str(sid)}, csrf_from='/diagnostics')
check('коды + симптомы: предупреждение о высокой серьёзности', 'высокой серьёзности' in body)
res = __import__('diag').diagnose('P0300 P0171', [], '')
check('причины ранжируются по повторяемости', res['causes'][0]['score'] >= res['causes'][-1]['score'] and res['causes'][0]['score'] >= 4, res['causes'][:2])

print('== Администрирование базы знаний ==')
st, body, _ = adm.post('/admin/codes/new', {'code': 'p1234', 'title': 'Тестовый код', 'severity': '2',
                                             'causes': 'Причина 1\nПричина 2', 'fixes': 'Проверка 1'}, csrf_from='/admin/codes/new')
check('добавление кода', 'Код P1234 добавлен' in body)
st, body, _ = adm.post('/admin/codes/new', {'code': 'P1234', 'title': 'Дубль', 'severity': '2'}, csrf_from='/admin/codes/new')
check('дубликат кода отклоняется', st == 400 and 'уже есть' in body)
st, body, _ = adm.post('/admin/codes/new', {'code': 'XYZ12', 'title': 'Плохой', 'severity': '2'}, csrf_from='/admin/codes/new')
check('неверный формат кода отклоняется', st == 400)
st, body, _ = adm.post('/admin/codes/P1234/edit', {'title': 'Изменено', 'severity': '3', 'causes': 'Новая', 'fixes': ''}, csrf_from='/admin/codes')
check('изменение кода', 'Код P1234 обновлён' in body)
st, body, _ = adm.post('/admin/symptoms/new', {'name': 'Тестовый симптом', 'codes': 'P1234, P9999', 'causes': 'x'}, csrf_from='/admin/symptoms/new')
check('симптом с неизвестным кодом отклоняется', st == 400 and 'P9999' in body)
st, body, _ = adm.post('/admin/symptoms/new', {'name': 'Тестовый симптом', 'codes': 'P1234', 'causes': 'Причина', 'keywords': 'тест'}, csrf_from='/admin/symptoms/new')
check('добавление симптома', 'Тестовый симптом' in body)
tsid = db.query("SELECT id FROM symptoms WHERE name='Тестовый симптом'", one=True)['id']
check('связь симптом-код создана', len(db.codes_for_symptom(tsid)) == 1)
adm.post('/admin/codes/P1234/delete', {}, csrf_from='/admin/codes')
check('удаление кода каскадно убирает связь', len(db.codes_for_symptom(tsid)) == 0 and db.get_code('P1234') is None)
adm.post('/admin/symptoms/%d/delete' % tsid, {}, csrf_from='/admin/symptoms')
check('удаление симптома', db.get_symptom(tsid) is None)

print('== Прочее ==')
uid = db.query("SELECT id FROM users WHERE username='petr'", one=True)['id']
adm.post('/admin/users/%d/delete' % uid, {}, csrf_from='/admin/users')
check('удаление клиента', db.query('SELECT 1 FROM users WHERE id=?', (uid,), one=True) is None)
adm.post('/admin/admins/%d/delete' % second_id, {}, csrf_from='/admin/admins')
check('удаление другого администратора', db.query('SELECT 1 FROM users WHERE id=?', (second_id,), one=True) is None)
st, body, _ = adm.get('/admin')
check('панель показывает статистику', 'Кодов в базе' in body)
check('пароли хранятся только в виде хеша', all(r['password_hash'].startswith('pbkdf2$') for r in db.query('SELECT password_hash FROM users')))

bf = Client()
codes = []
for _ in range(9):
    st, _, _ = bf.post('/login', {'username': 'ivan', 'password': 'wrong-password'}, csrf_from='/login')
    codes.append(st)
check('ограничение числа неудачных входов (429)', 429 in codes, codes)

st, _, _ = Client().get('/')
req = urllib.request.Request(BASE + '/', headers={'Host': 'evil.example.com'})
try:
    r = urllib.request.urlopen(req)
    hs = r.status
except urllib.error.HTTPError as exc:
    hs = exc.code
check('чужой заголовок Host отклоняется', hs == 400)

print()
print('Пройдено: %d, провалено: %d' % (passed, len(failed)))
if failed:
    print('Провалены:', failed)
    sys.exit(1)
