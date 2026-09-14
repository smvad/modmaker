#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Кастомная демо-нода LED HEARTS: витрина всех возможностей моддинга глав.

Вставляет в начало главы 1 цепочку узлов mod_demo_* и делает mod_demo_start
стартовым узлом. В конце демо управление возвращается оригинальному узлу start.

Демонстрируется:
- новый стартовый узел (startingNodeId) + nextNodeId-цепочки
- текст RU/EN, спикеры, спрайты (characterSprite), позиции (center/left/right)
- фоны (backgroundImage), музыка (musicClip), звуковые эффекты (sfxClip, loop/stop)
- озвучка (voiceClip), затемнение (overlayAlpha), эмоция (emotion)
- выборы (choices) с ветвлением targetNodeId
- переменные: setVariable/modifyValue + условные строки requiredVariables
- закрытый выбор: lockedText + requiredVariables (как NSFW-DLC гейт)
- переименование главы (chapterTitle)

Использование:
    .venv/Scripts/python.exe mod_demo_node.py          (установить/обновить демо)
    .venv/Scripts/python.exe mod_demo_node.py --remove (убрать демо, вернуть старт)

Идемпотентно: повторный запуск сначала удаляет старые mod_demo_* узлы.
Перед первым изменением делает LED HEARTS_Data/resources.assets.pre_demo_nodes.bak
(основной .bak оригинала не трогается).
"""
import json
import shutil
import sys
import pathlib

BASE = pathlib.Path(__file__).resolve().parent
GAME = BASE
if not (GAME / 'LED HEARTS_Data' / 'resources.assets').exists():
    GAME = BASE.parent
ASSETS = GAME / 'LED HEARTS_Data' / 'resources.assets'
BAK = GAME / 'LED HEARTS_Data' / 'resources.assets.pre_demo_nodes.bak'
CHAPTER_PATH_ID = 101
PREFIX = 'mod_demo_'
ORIG_START = 'start'
CUSTOM_AUDIO = BASE / 'mod_demo_jingle.wav'


def L(speaker, text, text_en='', **kw):
    """Строка реплики со всеми полями схемы."""
    line = {
        'characterName': speaker,
        'characterName_en': speaker,
        'text': text,
        'text_en': text_en or text,
        'characterSprite': '',
        'backgroundImage': '',
        'voiceClip': '',
        'musicClip': '',
        'sfxClip': '',
        'characterPosition': 'center',
        'emotion': '',
        'overlayAlpha': -1,
        'requiredVariables': '',
        'choices': [],
    }
    line.update(kw)
    return line


def C(text, target, text_en='', **kw):
    """Выбор с полями схемы."""
    ch = {
        'choiceText': text,
        'choiceText_en': text_en or text,
        'targetNodeId': target,
        'setVariable': '',
        'modifyValue': 0,
        'requiredVariables': '',
        'lockedText': '',
        'lockedText_en': '',
    }
    ch.update(kw)
    return ch


def build_demo():
    start = {
        'nodeId': PREFIX + 'start',
        'editorX': -800, 'editorY': 0,
        'nextNodeId': '',
        'lines': [
            L('', '[ДЕМО-МОД] Это кастомная нода: текст, фон mod_start_bg.png, музыка.',
              '[MOD-DEMO] Custom node: text, mod_start_bg.png background, music.',
              backgroundImage='room_night_wide', musicClip='lonely_dev'),
            L('', 'Дзынь! Это кастомный звук mod_demo_jingle.wav из корня игры.',
              'That chime is a custom sound: mod_demo_jingle.wav from game root.',
              sfxClip='mod_demo_jingle:0.9'),
            L('Милли', 'А это спикер + спрайт + позиция по центру!',
              'Speaker + sprite + center position demo!',
              characterSprite='milly/pose_a/happy', characterPosition='center',
              backgroundImage='room_night_desk'),
            L('', '*Стук в дверь* — демонстрация звукового эффекта.',
              '*Knock on the door* — sound effect demo.',
              sfxClip='door_knock:0.5'),
            L('', 'А так работает затемнение экрана (overlayAlpha).',
              'Screen dim (overlayAlpha) demo.',
              backgroundImage='cafe', overlayAlpha=0.5),
            L('', 'Затемнение снято. Время выбора — выборы ведут в разные ветки!',
              'Dim off. Time to choose — choices branch the story!',
              overlayAlpha=-1,
              choices=[
                  C('Пойти в зоопарк (путь А)', PREFIX + 'branch_a',
                    'Go to the zoo (path A)',
                    setVariable='mod_demo_path_a', modifyValue=1),
                  C('Пойти в кафе (путь Б)', PREFIX + 'branch_b',
                    'Go to the cafe (path B)',
                    setVariable='mod_demo_path_b', modifyValue=1),
                  C('Секретная ветка', PREFIX + 'secret', 'Secret branch',
                    requiredVariables='mod_demo_path_a',
                    lockedText='(Сначала выбери путь А)',
                    lockedText_en='(Pick path A first)'),
              ]),
        ],
    }
    branch_a = {
        'nodeId': PREFIX + 'branch_a',
        'editorX': -500, 'editorY': -200,
        'nextNodeId': PREFIX + 'finale',
        'lines': [
            L('', 'Путь А: зоопарк. Фон и музыка сменились.',
              'Path A: the zoo. New background and music.',
              backgroundImage='zoo', musicClip='zoo_ending'),
            L('', 'Шум толпы по кругу (громко, отдельная строка без смены музыки).',
              'Looping crowd SFX on its own line, no music change.',
              sfxClip='crowd:0.6:loop'),
            L('Виолетта', 'Шум толпы остановлен командой stop. Эмоция: happy.',
              'Crowd stopped with "stop". Emotion: happy.',
              characterSprite='violet/pose_a/neutral', characterPosition='left',
              sfxClip='stop', emotion='happy'),
        ],
    }
    branch_b = {
        'nodeId': PREFIX + 'branch_b',
        'editorX': -500, 'editorY': 200,
        'nextNodeId': PREFIX + 'finale',
        'lines': [
            L('', 'Путь Б: кафе. Другая музыка.',
              'Path B: the cafe. Different music.',
              backgroundImage='cafe', musicClip='quiet_room'),
            L('', 'Фоновый гул классной комнаты по кругу (cafe_noise в игре отсутствует).',
              'Classroom ambience loop (cafe_noise is missing from the game).',
              sfxClip='classroom:0.5:loop'),
            L('Милли', 'Спрайт справа, позиция right! Гул остановлен.',
              'Sprite on the right! Ambience stopped.',
              characterSprite='milly/pose_a/surprised',
              characterPosition='right', sfxClip='stop'),
        ],
    }
    secret = {
        'nodeId': PREFIX + 'secret',
        'editorX': -500, 'editorY': 0,
        'nextNodeId': PREFIX + 'finale',
        'lines': [
            L('', 'Секретная ветка! Сюда пускает только переменная mod_demo_path_a.',
              'Secret branch! Gated by the mod_demo_path_a variable.',
              backgroundImage='silhouette_red_eyes',
              voiceClip='voice_chapter_01_dream_start_13'),
        ],
    }
    finale = {
        'nodeId': PREFIX + 'finale',
        'editorX': -200, 'editorY': 0,
        'nextNodeId': ORIG_START,
        'lines': [
            L('', 'Ты выбрал путь А — эта строка видна только с переменной mod_demo_path_a.',
              'You picked path A — this line needs mod_demo_path_a.',
              requiredVariables='mod_demo_path_a'),
            L('', 'Ты выбрал путь Б — эта строка видна только с переменной mod_demo_path_b.',
              'You picked path B — this line needs mod_demo_path_b.',
              requiredVariables='mod_demo_path_b'),
            L('', 'Демо окончено! Дальше — оригинальная игра с узла start.',
              'Demo over! The original game continues from node start.',
              backgroundImage='room_night_wide', musicClip='lonely_dev',
              characterSprite='none'),
        ],
    }
    return [start, branch_a, branch_b, secret, finale]


def main() -> int:
    import UnityPy

    remove = '--remove' in sys.argv

    if not remove:
        if not CUSTOM_AUDIO.exists():
            print('Нет кастомного звука:', CUSTOM_AUDIO, file=sys.stderr)
            return 1
        # Игра ищет внешний WAV в корне игры, а не внутри modmaker.
        shutil.copy2(CUSTOM_AUDIO, GAME / CUSTOM_AUDIO.name)
        print('Кастомный звук скопирован в корень игры:', GAME / CUSTOM_AUDIO.name)

    if not BAK.exists() and not remove:
        shutil.copy2(ASSETS, BAK)
        print('Бэкап перед демо-нодой:', BAK)

    env = UnityPy.load(str(ASSETS))
    ch_obj = env.file.objects.get(CHAPTER_PATH_ID)
    ch = ch_obj.read()
    data = json.loads(ch.m_Script)

    # убрать старые демо-узлы (идемпотентность)
    data['nodes'] = [n for n in data['nodes']
                     if not n.get('nodeId', '').startswith(PREFIX)]

    if remove:
        if data.get('startingNodeId', '').startswith(PREFIX):
            data['startingNodeId'] = ORIG_START
        data['chapterTitle'] = data['chapterTitle'].replace(' [MOD]', '')
        data['chapterTitle_en'] = data['chapterTitle_en'].replace(' [MOD]', '')
        print('Демо-узлы удалены, старт возвращён на', ORIG_START)
    else:
        demo = build_demo()
        data['nodes'] = demo + data['nodes']
        data['startingNodeId'] = PREFIX + 'start'
        if '[MOD]' not in data.get('chapterTitle', ''):
            data['chapterTitle'] += ' [MOD]'
            data['chapterTitle_en'] += ' [MOD]'
        print(f'Вставлено узлов: {len(demo)}, новый старт: {data["startingNodeId"]}')
        print('Заголовок:', data['chapterTitle'])

    ch.m_Script = json.dumps(data, ensure_ascii=False)
    ch.save()
    env.file.mark_changed()
    new_bytes = env.file.save()

    env2 = UnityPy.load(new_bytes)
    ch2 = json.loads(env2.file.objects[CHAPTER_PATH_ID].read().m_Script)
    demo_ids = [n['nodeId'] for n in ch2['nodes'] if n['nodeId'].startswith(PREFIX)]
    print(f'Проверка: старт={ch2["startingNodeId"]}, демо-узлы={demo_ids}')

    tmp = ASSETS.with_name(ASSETS.name + '.tmp')
    tmp.write_bytes(new_bytes)
    shutil.move(str(tmp), str(ASSETS))
    print('Записано:', ASSETS)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
