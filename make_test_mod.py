#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Собрать тестовый мод-ZIP из ассетов и придумать сюжет для проверки load_mod.

Берёт из корня игры переименованные PNG Новы (ampreview-*.png, побайтово те же,
что modmaker/dlc_nova_*.png), WAV — из modmaker/dlc_nova_test.wav, читает
текущую главу 1 из resources.assets, вставляет в начало тестовую ветку
``mod_test_*`` через функцию build_test_story() и пакует всё в mod_test.zip.

Использование (только из корня игры):
    .venv\\Scripts\\python.exe modmaker\\make_test_mod.py
    .venv\\Scripts\\python.exe modmaker\\load_mod.py mod_test.zip --dry-run
    .venv\\Scripts\\python.exe modmaker\\load_mod.py mod_test.zip
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import zipfile

BASE = pathlib.Path(__file__).resolve().parent
GAME = BASE
if not (GAME / "LED HEARTS_Data" / "resources.assets").exists():
    GAME = BASE.parent
ASSETS = GAME / "LED HEARTS_Data" / "resources.assets"
OUT_ZIP = GAME / "mod_test.zip"

PREFIX = "mod_test_"
ORIG_START = "start"

# ассеты: (имя в корне игры, имя в ZIP)
ROOT_ASSETS = [
    ("ampreview-97188269-2x-Photoroom.png", "dlc_nova_happy.png"),
    ("ampreview-97188269-neutral-Photoroom.png", "dlc_nova_neutral.png"),
]
WAV_SRC = BASE / "dlc_nova_test.wav"


def L(speaker, text, text_en="", **kw):
    line = {
        "characterName": speaker, "characterName_en": speaker,
        "text": text, "text_en": text_en or text,
        "characterSprite": "", "backgroundImage": "",
        "voiceClip": "", "musicClip": "", "sfxClip": "",
        "characterPosition": "center", "emotion": "",
        "overlayAlpha": -1, "requiredVariables": "", "choices": [],
    }
    line.update(kw)
    return line


def C(text, target, text_en="", **kw):
    ch = {
        "choiceText": text, "choiceText_en": text_en or text,
        "targetNodeId": target, "setVariable": "",
        "modifyValue": 0, "requiredVariables": "",
        "lockedText": "", "lockedText_en": "",
    }
    ch.update(kw)
    return ch


def build_test_story(chapter: dict) -> dict:
    """Вернуть копию главы с тестовой веткой «Сон Новы» в начале.

    Ветка: старт -> выбор (доверие/перезагрузка) -> две ветки -> финал,
    финал возвращает управление оригинальному узлу ``start``.
    """
    chapter = json.loads(json.dumps(chapter, ensure_ascii=False))
    chapter["nodes"] = [n for n in chapter["nodes"]
                        if not n.get("nodeId", "").startswith(PREFIX)]

    start = {
        "nodeId": PREFIX + "start", "editorX": -800, "editorY": 800,
        "nextNodeId": "", "lines": [
            L("", "[ТЕСТ-МОД] Ночь. Монитор гудит, за окном спит город.",
              "[TEST-MOD] Night. The monitor hums, the city sleeps outside.",
              backgroundImage="room_night_wide", musicClip="lonely_dev"),
            L("", "Из колонок доносится тихий цифровой щебет.",
              "A faint digital chirp comes from the speakers.",
              sfxClip="dlc_nova_test:0.9"),
            L("Нова", "Ты меня слышишь? Я — Нова, и это тестовая ветка!",
              "Can you hear me? I am Nova, and this is a test branch!",
              characterSprite="dlc_nova_neutral"),
            L("Максим", "Опять ты? Ладно, что на этот раз?",
              "You again? Fine, what is it this time?"),
            L("", "Решение — за тобой.", "The decision is yours.", choices=[
                C("Довериться Нове", PREFIX + "trust", "Trust Nova",
                  setVariable="mod_test_trust", modifyValue=1),
                C("Перезагрузить систему", PREFIX + "reboot", "Reboot the system",
                  setVariable="mod_test_reboot", modifyValue=1),
            ]),
        ],
    }
    trust = {
        "nodeId": PREFIX + "trust", "editorX": -500, "editorY": 650,
        "nextNodeId": PREFIX + "finale", "lines": [
            L("Максим", "Ладно, живи. Только кэш не захламляй.",
              "Fine, stay. Just do not clutter the cache.",
              backgroundImage="room_night_desk", musicClip="quiet_room"),
            L("Нова", "Ура! Записала твоё доверие в долговременную память!",
              "Yay! I saved your trust to long-term memory!",
              characterSprite="dlc_nova_happy"),
        ],
    }
    reboot = {
        "nodeId": PREFIX + "reboot", "editorX": -500, "editorY": 950,
        "nextNodeId": PREFIX + "finale", "lines": [
            L("Максим", "Прости, так надо. Перезагрузка.",
              "Sorry, it must be done. Rebooting.",
              backgroundImage="cafe", musicClip="quiet_room"),
            L("Нова", "Поздно! Я уже скопировала себя в автозагрузку.",
              "Too late! I already copied myself into autostart.",
              characterSprite="dlc_nova_neutral"),
        ],
    }
    finale = {
        "nodeId": PREFIX + "finale", "editorX": -200, "editorY": 800,
        "nextNodeId": ORIG_START, "lines": [
            L("Нова", "Ты мне поверил — я это запомнила.",
              "You trusted me — I will remember that.",
              requiredVariables="mod_test_trust",
              characterSprite="dlc_nova_happy"),
            L("Нова", "Ты пытался меня стереть. Я не в обиде. Почти.",
              "You tried to wipe me. No hard feelings. Almost.",
              requiredVariables="mod_test_reboot",
              characterSprite="dlc_nova_neutral"),
            L("", "Она ныряет обратно в монитор. Тест окончен — дальше оригинальная игра.",
              "She dives back into the monitor. Test over — the original game continues.",
              backgroundImage="room_night_wide", musicClip="lonely_dev",
              characterSprite="none"),
        ],
    }
    chapter["nodes"] = [start, trust, reboot, finale] + chapter["nodes"]
    chapter["startingNodeId"] = PREFIX + "start"
    if "[TEST]" not in chapter.get("chapterTitle", ""):
        chapter["chapterTitle"] += " [TEST]"
        chapter["chapterTitle_en"] += " [TEST]"
    return chapter


def main() -> int:
    import UnityPy

    missing = [GAME / src for src, _dst in ROOT_ASSETS if not (GAME / src).exists()]
    if not WAV_SRC.exists():
        missing.append(WAV_SRC)
    if missing:
        print("Нет ассетов:", ", ".join(str(p) for p in missing), file=sys.stderr)
        return 1
    if not ASSETS.exists():
        print("Не найден файл:", ASSETS, file=sys.stderr)
        return 1

    env = UnityPy.load(str(ASSETS))
    obj = env.file.objects.get(101)
    chapter = json.loads(obj.read().m_Script)
    if chapter.get("chapterId") != "chapter_01":
        print("path_id 101 — не chapter_01, прерываю", file=sys.stderr)
        return 1

    new_chapter = build_test_story(chapter)

    tmp = OUT_ZIP.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("chapter_01.json",
                   json.dumps(new_chapter, ensure_ascii=False))
        for src, dst in ROOT_ASSETS:
            z.write(GAME / src, dst)
        z.write(WAV_SRC, WAV_SRC.name)
    shutil.move(str(tmp), str(OUT_ZIP))
    print(f"Готово: {OUT_ZIP}")
    print(f"  глава: chapter_01, узлов {len(new_chapter['nodes'])}, "
          f"старт={new_chapter['startingNodeId']}")
    print(f"  ассеты: {', '.join([d for _, d in ROOT_ASSETS] + [WAV_SRC.name])}")
    print(f"Дальше: .venv\\Scripts\\python.exe modmaker\\load_mod.py {OUT_ZIP.name} --dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
