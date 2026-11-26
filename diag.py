# -*- coding: utf-8 -*-
"""Подбор вероятных причин неисправности по кодам OBD-II и симптомам.

Это не нейросеть, а прозрачный экспертный алгоритм поверх локальной базы знаний:
причины, которые повторяются у нескольких введённых кодов и симптомов, получают больше баллов.
Такой подход легко проверить и объяснить, поэтому он подходит для учебного использования.
"""
import re

import db

CODE_RE = re.compile(r'\b([PBCUpbcu][0-9A-Fa-f]{4})\b')
STOP = {'двигатель', 'машина', 'автомобиль', 'авто', 'при', 'после', 'когда', 'очень', 'стал', 'стала',
        'есть', 'нет', 'или', 'как', 'что', 'это', 'для', 'мотор', 'иногда', 'почему'}


def parse_codes(text):
    seen, out = set(), []
    for m in CODE_RE.findall(text or ''):
        code = m.upper()
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _stems(text):
    words = re.findall(r'[а-яёa-z0-9]+', (text or '').lower().replace('ё', 'е'))
    return {w[:5] for w in words if len(w) >= 3 and w not in STOP}


def match_symptoms(free_text, limit=3):
    """Находит симптомы, описание которых совпадает со свободным текстом."""
    query_stems = _stems(free_text)
    if not query_stems:
        return []
    scored = []
    for s in db.all_symptoms():
        name_stems = _stems(s['name'])
        kw_stems = _stems(s['keywords']) | _stems(s['description'])
        score = 2 * len(query_stems & name_stems) + len(query_stems & kw_stems)
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda x: (-x[0], x[1]['name']))
    return [s for _, s in scored[:limit]]


def diagnose(codes_text, symptom_ids, free_text):
    """Возвращает словарь с результатами диагностики."""
    codes_found, unknown = [], []
    for code in parse_codes(codes_text):
        row = db.get_code(code)
        (codes_found if row else unknown).append(row or code)

    selected = []
    for sid in symptom_ids:
        row = db.get_symptom(sid)
        if row:
            selected.append(row)
    text_matches = [s for s in match_symptoms(free_text) if s['id'] not in {x['id'] for x in selected}]

    scores = {}      # причина -> баллы
    sources = {}     # причина -> откуда взялась

    def add(cause, points, source):
        scores[cause] = scores.get(cause, 0) + points
        sources.setdefault(cause, [])
        if source not in sources[cause]:
            sources[cause].append(source)

    for row in codes_found:
        for cause in db.split_list(row['causes']):
            add(cause, 2, row['code'])
    for s in selected:
        for cause in db.split_list(s['causes']):
            add(cause, 2, s['name'])
    for s in text_matches:
        for cause in db.split_list(s['causes']):
            add(cause, 1, s['name'])

    # связанные коды: те, что указывают на выбранные симптомы, но не были введены
    entered = {r['code'].upper() for r in codes_found}
    related = {}
    for s in selected + text_matches:
        for c in db.codes_for_symptom(s['id']):
            if c['code'].upper() not in entered:
                related[c['code']] = c

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top = ranked[0][1] if ranked else 0
    causes = [{'cause': c, 'score': s, 'percent': round(100 * s / top) if top else 0, 'sources': sources[c]}
              for c, s in ranked[:10]]

    checks = []
    for row in codes_found:
        for f in db.split_list(row['fixes']):
            if f not in checks:
                checks.append(f)
    for s in selected + text_matches:
        for f in db.split_list(s['checks']):
            if f not in checks:
                checks.append(f)

    worst = max([r['severity'] for r in codes_found], default=0)
    return {
        'codes': codes_found,
        'unknown': unknown,
        'symptoms': selected,
        'text_symptoms': text_matches,
        'causes': causes,
        'checks': checks[:12],
        'related': sorted(related.values(), key=lambda r: r['code']),
        'severity': worst,
    }
