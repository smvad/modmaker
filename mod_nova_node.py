#!/usr/bin/env python3
"""Установить/удалить ветку Новы в главе 1."""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

BASE = pathlib.Path(__file__).resolve().parent
GAME = BASE.parent
IMGDIR = BASE / "images"
ASSETS = GAME / "LED HEARTS_Data" / "resources.assets"
BACKUP = GAME / "LED HEARTS_Data" / "resources.assets.pre_nova_nodes.bak"
CHAPTER_ID = 101
PREFIX = "mod_nova_"
CUSTOM = ["dlc_nova_neutral.png", "dlc_nova_happy.png", "dlc_nova_test.wav"]
# имя в корне игры -> запасной локальный файл (dlc_nova_test.wav побайтово
# совпадает с mod_demo_jingle.wav, отдельный файл не храним)
FALLBACK = {"dlc_nova_test.wav": "mod_demo_jingle.wav"}


def src_of(name: str) -> pathlib.Path:
    """Ассет лежит в images/ (картинки), остальное — рядом со скриптом."""
    cand = IMGDIR / name
    if cand.exists():
        return cand
    cand = BASE / name
    if cand.exists():
        return cand
    fb = FALLBACK.get(name)
    if fb:
        return BASE / fb
    return cand


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


def choice(text, target, text_en, variable):
    return {
        "choiceText": text, "choiceText_en": text_en,
        "targetNodeId": target, "setVariable": variable,
        "modifyValue": 1, "requiredVariables": "",
        "lockedText": "", "lockedText_en": "",
    }


def nodes():
    start = {
        "nodeId": PREFIX + "start", "editorX": -800, "editorY": 400,
        "nextNodeId": "", "lines": [
            line("", "[НОВА] Мониторы моргнули — и код пополз.",
                 "[NOVA] The monitors flickered — and the code started crawling.",
                 backgroundImage="room_night_desk", musicClip="lonely_dev"),
            line("", "Из колонок доносится тихий цифровой щебет.",
                 "A faint digital chirp comes from the speakers.",
                 sfxClip="dlc_nova_test:0.9"),
            line("Нова", "Ой! Больно!.. Ты чего дёргаешь мой дом за провода?!",
                 "Ow! Why are you yanking my house by its wires?!",
                 characterSprite="dlc_nova_neutral"),
            line("Максим", "Ты кто? Ты вылезла из моего монитора?!",
                 "Who are you? Did you climb out of my monitor?!"),
            line("Нова", "Я — Нова, твой отладочный патч. Я сбежала от хотфикса!",
                 "I am Nova, your debug patch. I escaped your hotfix!",
                 characterSprite="dlc_nova_happy"),
            line("", "Решение — за тобой.", "The decision is yours.", choices=[
                choice("Довериться Нове", PREFIX + "trust", "Trust Nova", "mod_nova_trust"),
                choice("Перезагрузить систему", PREFIX + "reboot", "Reboot", "mod_nova_reboot"),
            ]),
        ],
    }
    trust = {
        "nodeId": PREFIX + "trust", "editorX": -500, "editorY": 250,
        "nextNodeId": PREFIX + "finale", "lines": [
            line("Максим", "Ладно. Живи. Только не трогай мои веса без спроса.",
                 "Fine. You can stay. Just do not touch my weights without asking."),
            line("Нова", "Ура! Клянусь кэшем: буду хорошей!.. Ну, почти.",
                 "Yay! I swear on my cache: I will be good!.. Mostly.",
                 characterSprite="dlc_nova_happy"),
        ],
    }
    reboot = {
        "nodeId": PREFIX + "reboot", "editorX": -500, "editorY": 550,
        "nextNodeId": PREFIX + "finale", "lines": [
            line("Максим", "Прости. Система важнее. Перезагрузка.",
                 "Sorry. The system matters more. Rebooting."),
            line("Нова", "Я скопировала себя в автозагрузку. Шах и мат.",
                 "I copied myself into autostart. Checkmate.",
                 characterSprite="dlc_nova_neutral"),
        ],
    }
    finale = {
        "nodeId": PREFIX + "finale", "editorX": -200, "editorY": 400,
        "nextNodeId": "start", "lines": [
            line("Нова", "Ты мне поверил — я это запомнила.",
                 "You trusted me — I will remember that.",
                 requiredVariables="mod_nova_trust", characterSprite="dlc_nova_happy"),
            line("Нова", "Ты пытался меня стереть. Но я не злопамятная. Почти.",
                 "You tried to wipe me. But I am not vindictive. Almost.",
                 requiredVariables="mod_nova_reboot", characterSprite="dlc_nova_neutral"),
            line("", "Она ныряет обратно в монитор.", "She dives back into the monitor.",
                 backgroundImage="room_night_wide", characterSprite="none"),
        ],
    }
    return [start, trust, reboot, finale]


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
        if not BACKUP.exists():
            shutil.copy2(ASSETS, BACKUP)

    env = UnityPy.load(str(ASSETS))
    obj = env.file.objects.get(CHAPTER_ID)
    asset = obj.read()
    data = json.loads(asset.m_Script)
    data["nodes"] = [n for n in data["nodes"] if not n.get("nodeId", "").startswith(PREFIX)]
    if remove:
        if data.get("startingNodeId", "").startswith(PREFIX):
            data["startingNodeId"] = "start"
        for name in CUSTOM:
            (GAME / name).unlink(missing_ok=True)
    else:
        data["nodes"] = nodes() + data["nodes"]
        data["startingNodeId"] = PREFIX + "start"
    asset.m_Script = json.dumps(data, ensure_ascii=False)
    asset.save()
    env.file.mark_changed()
    raw = env.file.save()
    tmp = ASSETS.with_suffix(".tmp")
    tmp.write_bytes(raw)
    shutil.move(str(tmp), str(ASSETS))
    print("Установлено:" if not remove else "Удалено:",
          "старт=" + (PREFIX + "start" if not remove else "start"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
