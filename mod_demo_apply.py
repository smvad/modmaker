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
GAME = BASE
if not (GAME / 'LED HEARTS_Data' / 'resources.assets').exists():
    GAME = BASE.parent
ASSETS = GAME / 'LED HEARTS_Data' / 'resources.assets'
BAK = BASE / 'LED HEARTS_Data' / 'resources.assets.bak'
if not BAK.parent.exists():
    BAK = GAME / 'LED HEARTS_Data' / 'resources.assets.bak'
SRC_IMG = BASE / 'mod_start_bg.png'
if not SRC_IMG.exists():
    SRC_IMG = GAME / 'mod_start_bg.png'

BG_PATH_ID = 80          # room_night_wide — фон самой первой реплики
CHAPTER_PATH_ID = 101    # chapter_01


def main() -> int:
    import UnityPy
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

    if not BAK.exists():
        shutil.copy2(ASSETS, BAK)
        print('Бэкап оригинала:', BAK)
    else:
        print('Бэкап уже есть, оригинал не трогаю:', BAK)

    env = UnityPy.load(str(ASSETS))

    # --- 1. подмена текстуры фона ---
    tex_obj = env.file.objects.get(BG_PATH_ID)
    tex = tex_obj.read()
    assert tex.m_Name == 'room_night_wide', tex.m_Name
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

    tmp = ASSETS.with_name(ASSETS.name + '.tmp')
    tmp.write_bytes(new_bytes)
    shutil.move(str(tmp), str(ASSETS))
    print('Записано:', ASSETS)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
