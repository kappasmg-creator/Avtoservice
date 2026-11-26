# -*- coding: utf-8 -*-
"""HTML-шаблоны страниц. Все значения экранируются функцией e()."""
import datetime
import html

import db

SEVERITY = {1: ('Низкая', 'ok'), 2: ('Средняя', 'warn'), 3: ('Высокая', 'bad')}
KINDS = {'recommendation': 'Рекомендация', 'complaint': 'Жалоба'}
FB_STATUS = {'new': 'Новое', 'processed': 'Обработано'}


def e(value):
    return html.escape('' if value is None else str(value), quote=True)


CSS = """
:root{--bg:#f3f4f6;--card:#fff;--ink:#1f2933;--muted:#6b7280;--line:#e5e7eb;--brand:#1f2a37;--accent:#e8590c;--accent2:#c2410c;
--ok:#15803d;--warn:#b45309;--bad:#b91c1c}
*{box-sizing:border-box}
body{margin:0;font:16px/1.5 "Segoe UI",Roboto,Arial,sans-serif;background:var(--bg);color:var(--ink)}
header{background:var(--brand);color:#fff}
.bar{max-width:1100px;margin:0 auto;padding:12px 20px;display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center}
.logo{font-weight:700;font-size:20px;color:#fff;text-decoration:none;margin-right:auto}
.logo span{color:var(--accent)}
nav a{color:#d1d5db;text-decoration:none;margin-right:14px;font-size:15px}
nav a:hover,nav a.on{color:#fff;text-decoration:underline}
main{max-width:1100px;margin:0 auto;padding:24px 20px 60px}
h1{font-size:26px;margin:0 0 6px}h2{font-size:20px;margin:28px 0 10px}
.sub{color:var(--muted);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px;margin-bottom:18px}
.grid{display:grid;gap:16px}.g3{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}.g2{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}
.stat b{display:block;font-size:30px;line-height:1.1}.stat span{color:var(--muted);font-size:14px}
label{display:block;font-weight:600;margin:12px 0 4px;font-size:14px}
input,select,textarea{width:100%;padding:9px 11px;border:1px solid #cbd5e1;border-radius:7px;font:inherit;background:#fff}
textarea{min-height:100px;resize:vertical}
input:focus,select:focus,textarea:focus{outline:2px solid #fdba74;border-color:var(--accent)}
.btn{display:inline-block;background:var(--accent);color:#fff;border:0;border-radius:7px;padding:9px 18px;font:inherit;font-weight:600;cursor:pointer;text-decoration:none}
.btn:hover{background:var(--accent2)}.btn.sec{background:#e5e7eb;color:var(--ink)}.btn.sec:hover{background:#d1d5db}
.btn.red{background:#dc2626}.btn.red:hover{background:#b91c1c}.btn.sm{padding:4px 11px;font-size:14px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;font-size:15px}
th{background:#f9fafb;font-size:13px;text-transform:uppercase;letter-spacing:.03em;color:var(--muted)}
tr:last-child td{border-bottom:0}.tw{overflow-x:auto}
.badge{display:inline-block;padding:2px 9px;border-radius:20px;font-size:13px;font-weight:600;background:#e5e7eb}
.badge.new{background:#dbeafe;color:#1d4ed8}.badge.confirmed{background:#fef3c7;color:#92400e}
.badge.done,.badge.ok,.badge.processed{background:#dcfce7;color:var(--ok)}
.badge.cancelled{background:#f3f4f6;color:#6b7280}.badge.warn{background:#fef3c7;color:var(--warn)}.badge.bad,.badge.complaint{background:#fee2e2;color:var(--bad)}
.badge.recommendation{background:#dcfce7;color:var(--ok)}
.flash{padding:11px 16px;border-radius:8px;margin-bottom:18px}.flash.ok{background:#dcfce7;color:#14532d}.flash.err{background:#fee2e2;color:#7f1d1d}
.muted{color:var(--muted)}.row{display:flex;gap:10px;flex-wrap:wrap;align-items:end}.row>*{flex:1;min-width:150px}
.row .auto{flex:0 0 auto;min-width:0}
.narrow{max-width:460px;margin:30px auto}
ul.plain{margin:6px 0;padding-left:20px}ul.plain li{margin:3px 0}
.bar2{background:#e5e7eb;border-radius:5px;height:9px;overflow:hidden;min-width:80px}.bar2>i{display:block;height:100%;background:var(--accent)}
.checks{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:2px 14px}
.checks label{font-weight:400;margin:3px 0;display:flex;gap:8px;align-items:flex-start}.checks input{width:auto;margin-top:5px}
code.c{background:#1f2a37;color:#fff;padding:2px 8px;border-radius:5px;font-weight:700}
a{color:#c2410c}footer{text-align:center;color:var(--muted);font-size:13px;padding:20px}
.note{background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;padding:10px 14px;font-size:14px}
"""


def nav_links(ctx):
    user = ctx['user']
    if not user:
        return [('/', 'Главная'), ('/login', 'Вход'), ('/register', 'Регистрация'), ('/admin', 'Для администратора')]
    if user['role'] == 'admin':
        return [('/admin', 'Панель'), ('/admin/appointments', 'Записи'), ('/admin/feedback', 'Отзывы'),
                ('/admin/users', 'Клиенты'), ('/admin/admins', 'Администраторы'), ('/admin/codes', 'Коды OBD-II'),
                ('/admin/symptoms', 'Симптомы'), ('/diagnostics', 'Диагностика')]
    return [('/cabinet', 'Кабинет'), ('/book', 'Записаться'), ('/diagnostics', 'Диагностика'),
            ('/codes', 'Справочник кодов'), ('/feedback', 'Отзывы и жалобы')]


def layout(title, body, ctx):
    links = nav_links(ctx)
    path = ctx.get('path', '')
    items = ''.join('<a href="%s"%s>%s</a>' % (u, ' class="on"' if path == u else '', e(t)) for u, t in links)
    user = ctx['user']
    if user:
        role = 'администратор' if user['role'] == 'admin' else 'клиент'
        items += ('<form method="post" action="/logout" style="display:inline">'
                  '<input type="hidden" name="_csrf" value="%s">'
                  '<button class="btn sec sm" type="submit">Выйти (%s, %s)</button></form>'
                  % (e(ctx['csrf']), e(user['username']), role))
    flash = ''
    if ctx.get('flash'):
        kind, msg = ctx['flash']
        flash = '<div class="flash %s">%s</div>' % ('ok' if kind == 'ok' else 'err', e(msg))
    return ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s - АвтоСервис</title><style>%s</style></head><body>'
            '<header><div class="bar"><a class="logo" href="/">Авто<span>Сервис</span></a><nav>%s</nav></div></header>'
            '<main>%s%s</main><footer>АвтоСервис - учебное приложение. Справочник носит информационный характер.</footer>'
            '</body></html>' % (e(title), CSS, items, flash, body))


def pform(ctx, action, inner, extra=''):
    return ('<form method="post" action="%s" %s><input type="hidden" name="_csrf" value="%s">%s</form>'
            % (e(action), extra, e(ctx['csrf']), inner))


def options(items, selected=''):
    return ''.join('<option value="%s"%s>%s</option>' % (e(v), ' selected' if v == selected else '', e(l))
                   for v, l in items)


def sev_badge(level):
    label, cls = SEVERITY.get(level, ('-', ''))
    return '<span class="badge %s">%s</span>' % (cls, label)


def status_badge(status):
    return '<span class="badge %s">%s</span>' % (e(status), e(db.STATUSES.get(status, status)))


# ======================= общие страницы =======================
def landing(ctx):
    cta = ''
    if not ctx['user']:
        cta = ('<p><a class="btn" href="/register">Записаться на обслуживание</a> '
               '<a class="btn sec" href="/login">Войти</a></p>')
    body = ('<div class="card"><h1>Автосервис: запись на ремонт и компьютерная диагностика</h1>'
            '<p class="sub">Запишитесь онлайн, отслеживайте статус заявки и оставляйте отзывы. '
            'Встроенный справочник кодов OBD-II поможет разобраться, что означает ошибка на приборной панели.</p>%s</div>'
            '<div class="grid g3">'
            '<div class="card"><h2 style="margin-top:0">Запись онлайн</h2><p>Выберите услугу, дату и свободное время. '
            'Мы работаем с понедельника по субботу с 9:00 до 18:00.</p></div>'
            '<div class="card"><h2 style="margin-top:0">База кодов OBD-II</h2><p>Расшифровка кодов неисправностей, возможные причины и '
            'что проверить в первую очередь.</p></div>'
            '<div class="card"><h2 style="margin-top:0">Подбор по симптомам</h2><p>Опишите симптомы и введите коды: программа ранжирует '
            'вероятные причины.</p></div></div>' % cta)
    return layout('Главная', body, ctx)


def login_form(ctx, admin=False, error='', first_admin=False, username=''):
    if admin and first_admin:
        title = 'Первый запуск: регистрация администратора'
        hint = ('<p class="note">Администратор в системе ещё не создан. Придумайте логин и пароль - '
                'ваш первый вход станет регистрацией главного администратора. '
                'Позже вы сможете создавать другие учётные записи администраторов.</p>')
        extra = ('<label>Имя администратора</label><input name="full_name" required maxlength="80" value="">')
        btn = 'Зарегистрироваться и войти'
    elif admin:
        title, hint, extra, btn = 'Вход для администратора', '', '', 'Войти'
    else:
        title, hint, extra, btn = 'Вход для клиентов', '', '', 'Войти'
    err = '<div class="flash err">%s</div>' % e(error) if error else ''
    action = '/admin/login' if admin else '/login'
    other = ('<p class="muted">Вы клиент? <a href="/login">Вход для клиентов</a></p>' if admin else
             '<p class="muted">Нет аккаунта? <a href="/register">Зарегистрироваться</a><br>'
             'Вы сотрудник? <a href="/admin">Вход для администратора</a></p>')
    inner = ('%s%s<label>Логин</label><input name="username" required autocomplete="username" maxlength="32" value="%s">'
             '<label>Пароль</label><input name="password" type="password" required autocomplete="%s">%s'
             '<p><button class="btn" type="submit">%s</button></p>'
             % (hint, err, e(username), 'new-password' if first_admin else 'current-password', extra, btn))
    body = '<div class="card narrow"><h1>%s</h1>%s%s</div>' % (e(title), pform(ctx, action, inner), other)
    return layout(title, body, ctx)


def register_form(ctx, error='', v=None):
    v = v or {}
    err = '<div class="flash err">%s</div>' % e(error) if error else ''
    inner = (err +
             '<label>Имя и фамилия</label><input name="full_name" required maxlength="80" value="%s">'
             '<label>Телефон</label><input name="phone" required maxlength="20" placeholder="+7 700 000 00 00" value="%s">'
             '<label>Логин (латиница, цифры, _ . -)</label><input name="username" required maxlength="32" value="%s" autocomplete="username">'
             '<label>Пароль (не менее 8 символов)</label><input name="password" type="password" required minlength="8" autocomplete="new-password">'
             '<p><button class="btn" type="submit">Создать аккаунт</button></p>'
             % (e(v.get('full_name')), e(v.get('phone')), e(v.get('username'))))
    body = ('<div class="card narrow"><h1>Регистрация клиента</h1>%s'
            '<p class="muted">Уже есть аккаунт? <a href="/login">Войти</a></p></div>' % pform(ctx, '/register', inner))
    return layout('Регистрация', body, ctx)


# ======================= клиент =======================
def cabinet(ctx, appts, stats):
    rows = ''
    today = datetime.date.today().isoformat()
    for a in appts:
        cancel = ''
        if a['status'] in ('new', 'confirmed') and a['visit_date'] >= today:
            cancel = pform(ctx, '/appointments/%d/cancel' % a['id'],
                           '<button class="btn red sm" type="submit">Отменить</button>',
                           'onsubmit="return confirm(\'Отменить запись?\')" style="display:inline"')
        note = '<br><span class="muted">Комментарий сервиса: %s</span>' % e(a['admin_note']) if a['admin_note'] else ''
        rows += ('<tr><td>%s<br><b>%s</b></td><td>%s<br><span class="muted">%s %s</span>%s</td><td>%s</td><td>%s</td></tr>'
                 % (e(a['visit_date']), e(a['visit_time']), e(a['service']), e(a['car']), e(a['plate']), note,
                    status_badge(a['status']), cancel))
    if not rows:
        rows = '<tr><td colspan="4" class="muted">Записей пока нет.</td></tr>'
    body = ('<h1>Здравствуйте, %s!</h1><p class="sub">Личный кабинет клиента</p>'
            '<div class="grid g3"><div class="card stat"><b>%d</b><span>Всего записей</span></div>'
            '<div class="card stat"><b>%d</b><span>Ожидают визита</span></div>'
            '<div class="card stat"><b>%d</b><span>Выполнено</span></div></div>'
            '<p><a class="btn" href="/book">Новая запись</a> <a class="btn sec" href="/diagnostics">Диагностика по кодам</a></p>'
            '<h2>Мои записи</h2><div class="tw"><table><tr><th>Дата и время</th><th>Услуга и автомобиль</th><th>Статус</th><th></th></tr>%s</table></div>'
            % (e(ctx['user']['full_name']), stats['total'], stats['active'], stats['done'], rows))
    return layout('Личный кабинет', body, ctx)


def book_form(ctx, error='', v=None, slots=None):
    v = v or {}
    today = datetime.date.today()
    err = '<div class="flash err">%s</div>' % e(error) if error else ''
    slot_opts = options([(s, s) for s in (slots if slots is not None else db.SLOTS)], v.get('visit_time', ''))
    inner = (err +
             '<label>Услуга</label><select name="service" required>%s</select>'
             '<div class="row"><div><label>Марка и модель автомобиля</label><input name="car" required maxlength="60" placeholder="Toyota Camry 2012" value="%s"></div>'
             '<div><label>Госномер (необязательно)</label><input name="plate" maxlength="15" value="%s"></div></div>'
             '<div class="row"><div><label>Дата</label><input type="date" name="visit_date" required min="%s" max="%s" value="%s"></div>'
             '<div><label>Время</label><select name="visit_time" required>%s</select></div></div>'
             '<label>Описание проблемы (симптомы, коды ошибок)</label><textarea name="description" maxlength="1000">%s</textarea>'
             '<p class="muted">Если выбрали дату, нажмите «Показать свободное время», чтобы увидеть доступные часы.</p>'
             '<p><button class="btn" type="submit">Записаться</button> '
             '<button class="btn sec" type="submit" formaction="/book/slots" formnovalidate>Показать свободное время</button></p>'
             % (options([(s, s) for s in db.SERVICES], v.get('service', '')), e(v.get('car')), e(v.get('plate')),
                today.isoformat(), (today + datetime.timedelta(days=90)).isoformat(), e(v.get('visit_date')),
                slot_opts, e(v.get('description'))))
    body = ('<h1>Запись на обслуживание</h1><p class="sub">Работаем Пн-Сб с 9:00 до 18:00. На одно время принимаем не более %d автомобилей.</p>'
            '<div class="card" style="max-width:700px">%s</div>' % (db.SLOT_CAPACITY, pform(ctx, '/book', inner)))
    return layout('Запись на обслуживание', body, ctx)


def feedback_page(ctx, items, error='', v=None):
    v = v or {}
    err = '<div class="flash err">%s</div>' % e(error) if error else ''
    inner = (err + '<label>Тип обращения</label><select name="kind">%s</select>'
             '<label>Текст</label><textarea name="message" required maxlength="2000"></textarea>'
             '<p><button class="btn" type="submit">Отправить</button></p>'
             % options([('recommendation', 'Рекомендация'), ('complaint', 'Жалоба')], v.get('kind', '')))
    rows = ''
    for f in items:
        reply = '<br><b>Ответ сервиса:</b> %s' % e(f['admin_reply']) if f['admin_reply'] else ''
        rows += ('<tr><td>%s</td><td><span class="badge %s">%s</span></td><td>%s%s</td><td>%s</td></tr>'
                 % (e(f['created_at']), e(f['kind']), KINDS[f['kind']], e(f['message']), reply,
                    '<span class="badge %s">%s</span>' % ('processed' if f['status'] == 'processed' else 'new', FB_STATUS[f['status']])))
    if not rows:
        rows = '<tr><td colspan="4" class="muted">Вы ещё не оставляли обращений.</td></tr>'
    body = ('<h1>Рекомендации и жалобы</h1><p class="sub">Расскажите, что понравилось или что нужно исправить.</p>'
            '<div class="card" style="max-width:700px">%s</div><h2>Мои обращения</h2>'
            '<div class="tw"><table><tr><th>Дата</th><th>Тип</th><th>Сообщение</th><th>Статус</th></tr>%s</table></div>'
            % (pform(ctx, '/feedback', inner), rows))
    return layout('Отзывы и жалобы', body, ctx)


def codes_page(ctx, rows, q='', system=''):
    trs = ''
    for r in rows:
        trs += ('<tr><td><a href="/codes/%s"><code class="c">%s</code></a></td><td>%s</td><td>%s</td></tr>'
                % (e(r['code']), e(r['code']), e(r['title']), sev_badge(r['severity'])))
    if not trs:
        trs = '<tr><td colspan="3" class="muted">Ничего не найдено.</td></tr>'
    systems = [('', 'Все системы'), ('P', 'P - силовой агрегат'), ('C', 'C - шасси'), ('B', 'B - кузов'), ('U', 'U - сеть')]
    body = ('<h1>Справочник кодов OBD-II</h1><p class="sub">Найдено: %d. Поиск по коду, названию и причинам.</p>'
            '<form method="get" action="/codes" class="row card"><div><label>Поиск</label><input name="q" value="%s" placeholder="P0300 или «пропуски»"></div>'
            '<div><label>Система</label><select name="system">%s</select></div>'
            '<div class="auto"><button class="btn" type="submit">Найти</button></div></form>'
            '<div class="tw"><table><tr><th>Код</th><th>Описание</th><th>Серьёзность</th></tr>%s</table></div>'
            % (len(rows), e(q), options(systems, system), trs))
    return layout('Справочник кодов', body, ctx)


def code_detail(ctx, row, symptoms):
    causes = ''.join('<li>%s</li>' % e(c) for c in db.split_list(row['causes'])) or '<li class="muted">не указаны</li>'
    fixes = ''.join('<li>%s</li>' % e(c) for c in db.split_list(row['fixes'])) or '<li class="muted">не указано</li>'
    sy = ''.join('<li>%s</li>' % e(s['name']) for s in symptoms) or '<li class="muted">нет связанных симптомов</li>'
    adm = ''
    if ctx['user'] and ctx['user']['role'] == 'admin':
        adm = '<a class="btn sec" href="/admin/codes/%s/edit">Редактировать</a>' % e(row['code'])
    body = ('<p><a href="/codes">&larr; К справочнику</a></p><div class="card"><h1><code class="c">%s</code> %s</h1>'
            '<p>Серьёзность: %s</p><div class="grid g2"><div><h2>Возможные причины</h2><ul class="plain">%s</ul></div>'
            '<div><h2>Что проверить</h2><ul class="plain">%s</ul></div></div>'
            '<h2>Связанные симптомы</h2><ul class="plain">%s</ul>'
            '<p class="note">Трактовка кода может отличаться у разных производителей. Перед заменой деталей проверьте проводку и разъёмы, '
            'сверьтесь с документацией на конкретную модель.</p>%s'
            '<p><a class="btn" href="/diagnostics?codes=%s">Подобрать причины</a></p></div>'
            % (e(row['code']), e(row['title']), sev_badge(row['severity']), causes, fixes, sy, adm, e(row['code'])))
    return layout(row['code'], body, ctx)


def diagnostics_page(ctx, all_symptoms, v, result=None):
    selected = {str(x) for x in v.get('symptoms', [])}
    checks = ''.join('<label><input type="checkbox" name="symptom" value="%d"%s> %s</label>'
                     % (s['id'], ' checked' if str(s['id']) in selected else '', e(s['name'])) for s in all_symptoms)
    form = pform(ctx, '/diagnostics',
                 '<label>Коды ошибок (через пробел или запятую)</label><input name="codes" value="%s" placeholder="P0300, P0171">'
                 '<label>Симптомы (отметьте подходящие)</label><div class="checks">%s</div>'
                 '<label>Опишите проблему своими словами (необязательно)</label><textarea name="free_text" maxlength="500" style="min-height:70px">%s</textarea>'
                 '<p><button class="btn" type="submit">Подобрать причины</button></p>'
                 % (e(v.get('codes')), checks, e(v.get('free_text'))))
    out = ''
    if result is not None:
        if not (result['codes'] or result['symptoms'] or result['text_symptoms'] or result['unknown']):
            out = '<div class="flash err">Ничего не введено или совпадений не найдено. Введите код или выберите симптом.</div>'
        else:
            out = _diag_result(result)
    body = ('<h1>Диагностика по кодам и симптомам</h1>'
            '<p class="sub">Введите коды, считанные сканером OBD-II, и/или отметьте симптомы. Программа ранжирует вероятные причины по локальной базе знаний.</p>'
            '<div class="card">%s</div>%s' % (form, out))
    return layout('Диагностика', body, ctx)


def _diag_result(r):
    parts = []
    if r['severity'] == 3:
        parts.append('<div class="flash err"><b>Внимание:</b> среди кодов есть неисправности высокой серьёзности. '
                     'Продолжение эксплуатации может повредить двигатель или быть небезопасным - обратитесь в сервис.</div>')
    if r['unknown']:
        parts.append('<div class="note">Кодов нет в локальной базе: %s. Они могут быть специфичными для производителя.</div>'
                     % e(', '.join(r['unknown'])))
    if r['codes']:
        items = ''.join('<tr><td><a href="/codes/%s"><code class="c">%s</code></a></td><td>%s</td><td>%s</td></tr>'
                        % (e(c['code']), e(c['code']), e(c['title']), sev_badge(c['severity'])) for c in r['codes'])
        parts.append('<h2>Расшифровка кодов</h2><div class="tw"><table><tr><th>Код</th><th>Описание</th><th>Серьёзность</th></tr>%s</table></div>' % items)
    syms = r['symptoms'] + r['text_symptoms']
    if r['text_symptoms']:
        parts.append('<p class="muted">По вашему описанию найдены симптомы: %s.</p>' % e(', '.join(s['name'] for s in r['text_symptoms'])))
    if r['causes']:
        trs = ''.join('<tr><td>%s</td><td style="width:140px"><div class="bar2"><i style="width:%d%%"></i></div></td>'
                      '<td class="muted">%s</td></tr>' % (e(c['cause']), c['percent'], e(', '.join(c['sources'])))
                      for c in r['causes'])
        parts.append('<h2>Вероятные причины (от более вероятных к менее)</h2><div class="tw"><table>'
                     '<tr><th>Причина</th><th>Вес</th><th>Источник совпадения</th></tr>%s</table></div>' % trs)
    if r['checks']:
        parts.append('<h2>Что проверить в первую очередь</h2><div class="card"><ol class="plain">%s</ol></div>'
                     % ''.join('<li>%s</li>' % e(c) for c in r['checks']))
    if r['related']:
        parts.append('<h2>Коды, которые часто сопровождают эти симптомы</h2><p>%s</p>'
                     % ' '.join('<a href="/codes/%s"><code class="c">%s</code></a>' % (e(c['code']), e(c['code'])) for c in r['related']))
    parts.append('<p class="note">Результат - ориентир для диагностики, а не окончательный диагноз. '
                 'Подтверждайте неисправность измерениями, не меняйте детали наугад. '
                 '<a href="/book">Записаться на диагностику</a></p>')
    return ''.join(parts)


# ======================= администратор =======================
def admin_dashboard(ctx, stats, recent):
    rows = ''.join('<tr><td>%s %s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                   % (e(a['visit_date']), e(a['visit_time']), e(a['full_name']), e(a['service']), status_badge(a['status']))
                   for a in recent) or '<tr><td colspan="4" class="muted">Записей нет.</td></tr>'
    body = ('<h1>Панель администратора</h1><p class="sub">Сводка по автосервису</p><div class="grid g3">'
            '<div class="card stat"><b>%d</b><span>Новых записей</span></div>'
            '<div class="card stat"><b>%d</b><span>Записей на сегодня</span></div>'
            '<div class="card stat"><b>%d</b><span>Необработанных обращений</span></div>'
            '<div class="card stat"><b>%d</b><span>Клиентов</span></div>'
            '<div class="card stat"><b>%d</b><span>Кодов в базе</span></div>'
            '<div class="card stat"><b>%d</b><span>Симптомов в базе</span></div></div>'
            '<h2>Ближайшие записи</h2><div class="tw"><table><tr><th>Когда</th><th>Клиент</th><th>Услуга</th><th>Статус</th></tr>%s</table></div>'
            % (stats['new'], stats['today'], stats['fb_new'], stats['users'], stats['codes'], stats['symptoms'], rows))
    return layout('Панель администратора', body, ctx)


def admin_appointments(ctx, rows, status=''):
    flt = options([('', 'Все статусы')] + list(db.STATUSES.items()), status)
    trs = ''
    for a in rows:
        form = pform(ctx, '/admin/appointments/%d' % a['id'],
                     '<select name="status">%s</select><input name="admin_note" maxlength="300" placeholder="Комментарий клиенту" value="%s">'
                     '<button class="btn sm" type="submit">Сохранить</button>'
                     % (options(list(db.STATUSES.items()), a['status']), e(a['admin_note'])))
        trs += ('<tr><td>#%d<br>%s<br><b>%s</b></td><td>%s<br><span class="muted">%s</span></td>'
                '<td>%s<br><span class="muted">%s %s</span><br>%s</td><td>%s</td></tr>'
                % (a['id'], e(a['visit_date']), e(a['visit_time']), e(a['full_name']), e(a['phone']),
                   e(a['service']), e(a['car']), e(a['plate']), e(a['description']), form))
    if not trs:
        trs = '<tr><td colspan="4" class="muted">Записей нет.</td></tr>'
    body = ('<h1>Записи клиентов</h1><form method="get" class="row card"><div><label>Статус</label><select name="status">%s</select></div>'
            '<div class="auto"><button class="btn" type="submit">Применить</button></div></form>'
            '<div class="tw"><table><tr><th>Дата</th><th>Клиент</th><th>Услуга, автомобиль, проблема</th><th>Управление</th></tr>%s</table></div>'
            % (flt, trs))
    return layout('Записи', body, ctx)


def admin_feedback(ctx, rows):
    trs = ''
    for f in rows:
        form = pform(ctx, '/admin/feedback/%d' % f['id'],
                     '<textarea name="admin_reply" maxlength="1000" style="min-height:60px" placeholder="Ответ клиенту">%s</textarea>'
                     '<button class="btn sm" type="submit">Ответить и отметить обработанным</button>' % e(f['admin_reply']))
        st_cls = 'processed' if f['status'] == 'processed' else 'new'
        trs += ('<tr><td>%s<br><span class="badge %s">%s</span><br><span class="badge %s">%s</span></td>'
                '<td><b>%s</b> <span class="muted">%s</span><p>%s</p></td><td>%s</td></tr>'
                % (e(f['created_at']), e(f['kind']), KINDS[f['kind']], st_cls, FB_STATUS[f['status']],
                   e(f['full_name']), e(f['phone']), e(f['message']), form))
    if not trs:
        trs = '<tr><td colspan="3" class="muted">Обращений нет.</td></tr>'
    body = ('<h1>Рекомендации и жалобы</h1><div class="tw"><table><tr><th>Дата и тип</th><th>Клиент и сообщение</th><th>Ответ</th></tr>%s</table></div>' % trs)
    return layout('Обращения', body, ctx)


def admin_users(ctx, rows):
    trs = ''
    for u in rows:
        btn = pform(ctx, '/admin/users/%d/delete' % u['id'], '<button class="btn red sm" type="submit">Удалить</button>',
                    'onsubmit="return confirm(\'Удалить клиента вместе с его записями и обращениями?\')"')
        trs += ('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td>%s</td></tr>'
                % (e(u['full_name']), e(u['username']), e(u['phone']), e(u['created_at']), u['n'], btn))
    if not trs:
        trs = '<tr><td colspan="6" class="muted">Клиентов пока нет.</td></tr>'
    body = ('<h1>Клиенты</h1><div class="tw"><table><tr><th>Имя</th><th>Логин</th><th>Телефон</th><th>Регистрация</th><th>Записей</th><th></th></tr>%s</table></div>' % trs)
    return layout('Клиенты', body, ctx)


def admin_admins(ctx, rows, error='', v=None):
    v = v or {}
    err = '<div class="flash err">%s</div>' % e(error) if error else ''
    trs = ''
    for a in rows:
        if a['id'] == ctx['user']['id']:
            btn = '<span class="muted">это вы</span>'
        else:
            btn = pform(ctx, '/admin/admins/%d/delete' % a['id'], '<button class="btn red sm" type="submit">Удалить</button>',
                        'onsubmit="return confirm(\'Удалить учётную запись администратора?\')"')
        trs += '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (e(a['full_name']), e(a['username']), e(a['created_at']), btn)
    inner = (err + '<label>Имя</label><input name="full_name" required maxlength="80" value="%s">'
             '<label>Логин</label><input name="username" required maxlength="32" value="%s">'
             '<label>Пароль (не менее 8 символов)</label><input name="password" type="password" required minlength="8" autocomplete="new-password">'
             '<p><button class="btn" type="submit">Создать администратора</button></p>' % (e(v.get('full_name')), e(v.get('username'))))
    body = ('<h1>Администраторы</h1><div class="grid g2"><div><div class="tw"><table><tr><th>Имя</th><th>Логин</th><th>Создан</th><th></th></tr>%s</table></div></div>'
            '<div class="card"><h2 style="margin-top:0">Новый администратор</h2>%s</div></div>' % (trs, pform(ctx, '/admin/admins', inner)))
    return layout('Администраторы', body, ctx)


def admin_codes(ctx, rows, q=''):
    trs = ''
    for r in rows:
        del_btn = pform(ctx, '/admin/codes/%s/delete' % r['code'], '<button class="btn red sm" type="submit">Удалить</button>',
                        'onsubmit="return confirm(\'Удалить код из базы?\')" style="display:inline"')
        trs += ('<tr><td><a href="/codes/%s"><code class="c">%s</code></a></td><td>%s</td><td>%s</td>'
                '<td><a class="btn sec sm" href="/admin/codes/%s/edit">Изменить</a> %s</td></tr>'
                % (e(r['code']), e(r['code']), e(r['title']), sev_badge(r['severity']), e(r['code']), del_btn))
    body = ('<h1>Справочник кодов OBD-II</h1><p><a class="btn" href="/admin/codes/new">Добавить код</a></p>'
            '<form method="get" class="row card"><div><label>Поиск</label><input name="q" value="%s"></div>'
            '<div class="auto"><button class="btn" type="submit">Найти</button></div></form>'
            '<div class="tw"><table><tr><th>Код</th><th>Описание</th><th>Серьёзность</th><th></th></tr>%s</table></div>' % (e(q), trs))
    return layout('Коды OBD-II', body, ctx)


def code_form(ctx, row=None, error=''):
    row = row or {}
    new = not row.get('code')
    err = '<div class="flash err">%s</div>' % e(error) if error else ''
    code_field = ('<label>Код (например, P0300)</label><input name="code" required maxlength="5" pattern="[PBCUpbcu][0-9A-Fa-f]{4}" value="%s">' % e(row.get('code', ''))
                  if new else '<p>Код: <code class="c">%s</code></p>' % e(row['code']))
    inner = (err + code_field +
             '<label>Описание</label><input name="title" required maxlength="200" value="%s">'
             '<label>Серьёзность</label><select name="severity">%s</select>'
             '<label>Возможные причины (каждая с новой строки)</label><textarea name="causes">%s</textarea>'
             '<label>Что проверить (каждый пункт с новой строки)</label><textarea name="fixes">%s</textarea>'
             '<p><button class="btn" type="submit">Сохранить</button> <a class="btn sec" href="/admin/codes">Отмена</a></p>'
             % (e(row.get('title', '')), options([('1', '1 - низкая'), ('2', '2 - средняя'), ('3', '3 - высокая')], str(row.get('severity', 2))),
                e(row.get('causes', '')), e(row.get('fixes', ''))))
    action = '/admin/codes/new' if new else '/admin/codes/%s/edit' % row['code']
    body = '<h1>%s</h1><div class="card" style="max-width:720px">%s</div>' % ('Новый код' if new else 'Редактирование кода', pform(ctx, action, inner))
    return layout('Код OBD-II', body, ctx)


def admin_symptoms(ctx, rows):
    trs = ''
    for s in rows:
        del_btn = pform(ctx, '/admin/symptoms/%d/delete' % s['id'], '<button class="btn red sm" type="submit">Удалить</button>',
                        'onsubmit="return confirm(\'Удалить симптом?\')" style="display:inline"')
        trs += ('<tr><td><b>%s</b><br><span class="muted">%s</span></td><td><a class="btn sec sm" href="/admin/symptoms/%d/edit">Изменить</a> %s</td></tr>'
                % (e(s['name']), e(s['description']), s['id'], del_btn))
    body = ('<h1>Симптомы поломок</h1><p><a class="btn" href="/admin/symptoms/new">Добавить симптом</a></p>'
            '<div class="tw"><table><tr><th>Симптом</th><th></th></tr>%s</table></div>' % trs)
    return layout('Симптомы', body, ctx)


def symptom_form(ctx, row=None, codes_text='', error=''):
    row = row or {}
    new = not row.get('id')
    err = '<div class="flash err">%s</div>' % e(error) if error else ''
    inner = (err + '<label>Название симптома</label><input name="name" required maxlength="120" value="%s">'
             '<label>Описание</label><textarea name="description" style="min-height:70px">%s</textarea>'
             '<label>Ключевые слова для поиска (через запятую)</label><input name="keywords" value="%s">'
             '<label>Возможные причины (каждая с новой строки)</label><textarea name="causes">%s</textarea>'
             '<label>Что проверить (каждый пункт с новой строки)</label><textarea name="checks">%s</textarea>'
             '<label>Связанные коды (через запятую)</label><input name="codes" value="%s" placeholder="P0300, P0301">'
             '<p><button class="btn" type="submit">Сохранить</button> <a class="btn sec" href="/admin/symptoms">Отмена</a></p>'
             % (e(row.get('name', '')), e(row.get('description', '')), e(row.get('keywords', '')),
                e(row.get('causes', '')), e(row.get('checks', '')), e(codes_text)))
    action = '/admin/symptoms/new' if new else '/admin/symptoms/%d/edit' % row['id']
    body = '<h1>%s</h1><div class="card" style="max-width:720px">%s</div>' % ('Новый симптом' if new else 'Редактирование симптома', pform(ctx, action, inner))
    return layout('Симптом', body, ctx)


def not_found(ctx, text='Страница не найдена'):
    return layout('Ошибка', '<div class="card"><h1>%s</h1><p><a href="/">На главную</a></p></div>' % e(text), ctx)
