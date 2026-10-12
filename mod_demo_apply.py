#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Демо-мод LED HEARTS: наглядные изменения в самом начале главы 1.

1. Заменяет текстуру фона первой сцены (room_night_wide) на mod_start_bg.png
   (лежит в корне игры, по примеру DLC-файлов).
2. Помечает первую реплику главы 1 маркером [MOD].

Использование:
    .venv/Scripts/python.exe mod_demo_apply.py
    .venv/Scripts/python.exe mod_demo_apply.py --revert  (откат из .bak)

Оригинал сохраняется в LED HEARTS_Data/resources.assets.bak при первом запуске.
"""
import json
import shutil
import sys
import pathlib

BASE = pathlib.Path(__file__).resolve().parent

sys.path.insert(0, str(BASE))
from common import atomic_write, backup_once, find_game_root, require_unitypy

GAME = find_game_root(BASE)
ASSETS = GAME / 'LED HEARTS_Data' / 'resources.assets'
BAK = GAME / 'LED HEARTS_Data' / 'resources.assets.bak'
SRC_IMG = BASE / 'mod_start_bg.png'
if not SRC_IMG.exists():
    SRC_IMG = GAME / 'mod_start_bg.png'

BG_PATH_ID = 80          # room_night_wide — фон самой первой реплики
CHAPTER_PATH_ID = 101    # chapter_01


def main() -> int:
    UnityPy = require_unitypy()
    from PIL import Image

    revert = '--revert' in sys.argv

    if revert:
        if not BAK.exists():
            print('Нет бэкапа для отката:', BAK)
            return 1
        shutil.copy2(BAK, ASSETS)
        print('Откат выполнен из', BAK)
        return 0

    if not SRC_IMG.exists():
        print('Нет картинки:', SRC_IMG)
        return 1

    backup_once(ASSETS)

    env = UnityPy.load(str(ASSETS))

    # --- 1. подмена текстуры фона ---
    tex_obj = env.file.objects.get(BG_PATH_ID)
    if tex_obj is None:
        print(f'Нет объекта фона path_id={BG_PATH_ID} — игра обновилась?', file=sys.stderr)
        return 1
    tex = tex_obj.read()
    if tex.m_Name != 'room_night_wide':
        print(f'Фон path_id={BG_PATH_ID} теперь {tex.m_Name!r}, а не room_night_wide — '
              f'игра обновилась, подмена отменена', file=sys.stderr)
        return 1
    img = Image.open(SRC_IMG).convert('RGB').resize((tex.m_Width, tex.m_Height))
    tex.image = img
    tex.save()
    print(f'Текстура {BG_PATH_ID} {tex.m_Name!r} заменена ({img.size[0]}x{img.size[1]})')

    # --- 2. пометка первой реплики главы 1 ---
    ch_obj = env.file.objects.get(CHAPTER_PATH_ID)
    ch = ch_obj.read()
    data = json.loads(ch.m_Script)
    node = next(n for n in data['nodes'] if n['nodeId'] == data['startingNodeId'])
    first = node['lines'][0]
    if '[MOD]' not in first.get('text', ''):
        first['text'] = '[MOD] ' + first.get('text', '')
        first['text_en'] = '[MOD] ' + first.get('text_en', '')
    ch.m_Script = json.dumps(data, ensure_ascii=False)
    ch.save()
    print('Первая реплика главы 1 помечена [MOD]:')
    print('   ', first['text'][:120])

    env.file.mark_changed()
    new_bytes = env.file.save()

    # проверка из памяти (без лока файла на Windows)
    env2 = UnityPy.load(new_bytes)
    ok_tex = any(o.type.name == 'Texture2D' for o in env2.objects)
    ok_ch = any(o.type.name == 'TextAsset' for o in env2.objects)
    print(f'Проверка пересборки: Texture2D={ok_tex}, TextAsset={ok_ch}, размер={len(new_bytes)}')

    atomic_write(ASSETS, new_bytes)
    print('Записано:', ASSETS)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
