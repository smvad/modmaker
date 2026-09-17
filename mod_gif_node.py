#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тестовая GIF-нода LED HEARTS: проверка, грузит ли игра .gif.

Что делает:
- копирует modmaker/images/dlc_gif_test.gif (+ контрольный PNG первого кадра)
  в корень игры (рядом с LED HEARTS.exe);
- вставляет в главу 1 цепочку mod_gif_* и делает mod_gif_start стартом;
- в конце возвращает управление оригинальному узлу start.

Ожидание по коду игры:
- внешний загрузчик LoadExternalDLCSprite использует Texture2D.LoadImage,
  который по докам Unity грузит только PNG/JPG (EXR с 2023.1), но НЕ GIF;
- load_mod.py принимает только IMAGE_EXTS = {.png, .jpg, .jpeg}, .gif режет
  как "неизвестный тип";
- значит .gif либо не найдётся (чёрный фон / пустой спрайт + warning
  "not found in Resources"), либо покажет максимум 1-й кадр без анимации.
  Анимации GIF в движке без своего кода быть не может.

Использование (из корня игры):
    .venv\\Scripts\\python.exe modmaker\\mod_gif_node.py
    .venv\\Scripts\\python.exe modmaker\\mod_gif_node.py --remove
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

BASE = pathlib.Path(__file__).resolve().parent
GAME = BASE
if not (GAME / "LED HEARTS_Data" / "resources.assets").exists():
    GAME = BASE.parent
IMGDIR = BASE / "images"
ASSETS = GAME / "LED HEARTS_Data" / "resources.assets"
BACKUP = GAME / "LED HEARTS_Data" / "resources.assets.pre_gif_nodes.bak"
CHAPTER_ID = 101
PREFIX = "mod_gif_"
ORIG_START = "start"
CUSTOM = ["dlc_gif_test.gif", "dlc_gif_test_firstframe.png"]


def src_of(name: str) -> pathlib.Path:
    """Ассет лежит в images/ (картинки), остальное — рядом со скриптом."""
    cand = IMGDIR / name
    if cand.exists():
        return cand
    return BASE / name


def line(name, text, text_en, **changes):
    result = {
        "characterName": name, "characterName_en": name,
        "text": text, "text_en": text_en,
        "characterSprite": "", "backgroundImage": "",
        "voiceClip": "", "musicClip": "", "sfxClip": "",
        "characterPosition": "center", "emotion": "",
        "overlayAlpha": -1, "requiredVariables": "", "choices": [],
    }
    result.update(changes)
    return result


def nodes():
    start = {
        "nodeId": PREFIX + "start", "editorX": -800, "editorY": 800,
        "nextNodeId": PREFIX + "sprite", "lines": [
            line("", "[GIF-ТЕСТ 1/3] Сейчас фон = dlc_gif_test.gif (400x400, 44 кадра).",
                 "[GIF-TEST 1/3] Background should be dlc_gif_test.gif (400x400, 44 frames).",
                 backgroundImage="room_night_wide", musicClip="lonely_dev"),
            line("", "Ставлю фон dlc_gif_test. Если видишь вращение Земли — GIF работает. "
                     "Если чёрный фон / старый фон + warning в Player.log — не работает.",
                 "Setting background to dlc_gif_test. Spinning Earth = GIF works. "
                 "Black/old bg + Player.log warning = GIF NOT supported.",
                 backgroundImage="dlc_gif_test"),
            line("", "Жми дальше — проверим .gif как спрайт персонажа.",
                 "Continue — next we test .gif as a character sprite."),
        ],
    }
    sprite = {
        "nodeId": PREFIX + "sprite", "editorX": -500, "editorY": 800,
        "nextNodeId": PREFIX + "control", "lines": [
            line("", "[GIF-ТЕСТ 2/3] Сейчас спрайт = dlc_gif_test.gif по центру.",
                 "[GIF-TEST 2/3] Sprite should be dlc_gif_test.gif, centered.",
                 backgroundImage="room_night_desk",
                 characterSprite="dlc_gif_test", characterPosition="center"),
            line("Гифка", "Я — dlc_gif_test.gif. Если я кручусь — игра умеет в GIF. "
                           "Если меня нет / статичная картинка — только PNG/JPG.",
                 "I am dlc_gif_test.gif. Spinning = GIF works. Missing/static = PNG/JPG only.",
                 characterSprite="dlc_gif_test", characterPosition="center"),
        ],
    }
    control = {
        "nodeId": PREFIX + "control", "editorX": -200, "editorY": 800,
        "nextNodeId": ORIG_START, "lines": [
            line("", "[GIF-ТЕСТ 3/3] Контроль: PNG первого кадра — dlc_gif_test_firstframe.",
                 "[GIF-TEST 3/3] Control: PNG of first frame — dlc_gif_test_firstframe.",
                 backgroundImage="dlc_gif_test_firstframe",
                 characterSprite="none"),
            line("", "Этот PNG обязан показаться. Если GIF выше не показался, а PNG показался — "
                     "вывод: LoadImage ест PNG, но не ест GIF. Конвертируй GIF в PNG-секвенцию.",
                 "This PNG must show. If GIF above failed but this shows — "
                 "LoadImage eats PNG, not GIF. Convert GIF to PNG sequence.",
                 backgroundImage="dlc_gif_test_firstframe",
                 characterSprite="none"),
            line("", "Тест окончен. Дальше — оригинальная игра с узла start.",
                 "Test over. Original game continues from node start.",
                 backgroundImage="room_night_wide", musicClip="lonely_dev",
                 characterSprite="none"),
        ],
    }
    return [start, sprite, control]


def main() -> int:
    import UnityPy

    remove = "--remove" in sys.argv
    if not remove:
        for name in CUSTOM:
            src = src_of(name)
            if not src.exists():
                print("Не найден ассет:", src, file=sys.stderr)
                return 1
            shutil.copy2(src, GAME / name)
            print(f"+ {name} -> корень игры ({(GAME / name).stat().st_size} байт)")
        if not BACKUP.exists():
            shutil.copy2(ASSETS, BACKUP)
            print("Бэкап:", BACKUP)

    env = UnityPy.load(str(ASSETS))
    obj = env.file.objects.get(CHAPTER_ID)
    asset = obj.read()
    data = json.loads(asset.m_Script)
    data["nodes"] = [n for n in data["nodes"] if not n.get("nodeId", "").startswith(PREFIX)]
    if remove:
        if data.get("startingNodeId", "").startswith(PREFIX):
            data["startingNodeId"] = ORIG_START
        for name in CUSTOM:
            (GAME / name).unlink(missing_ok=True)
        print("GIF-ноды удалены, старт возвращён на", ORIG_START)
    else:
        data["nodes"] = nodes() + data["nodes"]
        data["startingNodeId"] = PREFIX + "start"
    asset.m_Script = json.dumps(data, ensure_ascii=False)
    asset.save()
    env.file.mark_changed()
    raw = env.file.save()
    # проверка чтением
    env2 = UnityPy.load(raw)
    ch2 = json.loads(env2.file.objects[CHAPTER_ID].read().m_Script)
    ids = [n["nodeId"] for n in ch2["nodes"] if n["nodeId"].startswith(PREFIX)]
    print(f"Проверка: старт={ch2['startingNodeId']}, gif-узлы={ids}")
    tmp = ASSETS.with_suffix(".tmp")
    tmp.write_bytes(raw)
    shutil.move(str(tmp), str(ASSETS))
    print("Записано:", ASSETS)
    if not remove:
        print("Запусти LED HEARTS.exe и смотри Player.log: "
              "C:\\Users\\%USERNAME%\\AppData\\LocalLow\\fugas_kitsune\\LED HEARTS\\Player.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
