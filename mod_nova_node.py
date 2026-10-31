#!/usr/bin/env python3
"""Установить/удалить ветку Новы в главе 1."""
from __future__ import annotations

import pathlib
import shutil
import sys

BASE = pathlib.Path(__file__).resolve().parent

sys.path.insert(0, str(BASE))
from common import apply_nodes_to_chapter, find_game_root, make_choice, make_line  # noqa: E402

GAME = find_game_root(BASE)
IMGDIR = BASE / "images"
ASSETS = GAME / "LED HEARTS_Data" / "resources.assets"
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


def nodes():
    start = {
        "nodeId": PREFIX + "start", "editorX": -800, "editorY": 400,
        "nextNodeId": "", "lines": [
            make_line("", "[НОВА] Мониторы моргнули — и код пополз.",
                      "[NOVA] The monitors flickered — and the code started crawling.",
                      backgroundImage="room_night_desk", musicClip="lonely_dev"),
            make_line("", "Из колонок доносится тихий цифровой щебет.",
                      "A faint digital chirp comes from the speakers.",
                      sfxClip="dlc_nova_test:0.9"),
            make_line("Нова", "Ой! Больно!.. Ты чего дёргаешь мой дом за провода?!",
                      "Ow! Why are you yanking my house by its wires?!",
                      characterSprite="dlc_nova_neutral"),
            make_line("Максим", "Ты кто? Ты вылезла из моего монитора?!",
                      "Who are you? Did you climb out of my monitor?!"),
            make_line("Нова", "Я — Нова, твой отладочный патч. Я сбежала от хотфикса!",
                      "I am Nova, your debug patch. I escaped your hotfix!",
                      characterSprite="dlc_nova_happy"),
            make_line("", "Решение — за тобой.", "The decision is yours.", choices=[
                make_choice("Довериться Нове", PREFIX + "trust", "Trust Nova",
                            variable="mod_nova_trust"),
                make_choice("Перезагрузить систему", PREFIX + "reboot", "Reboot",
                            variable="mod_nova_reboot"),
            ]),
        ],
    }
    trust = {
        "nodeId": PREFIX + "trust", "editorX": -500, "editorY": 250,
        "nextNodeId": PREFIX + "finale", "lines": [
            make_line("Максим", "Ладно. Живи. Только не трогай мои веса без спроса.",
                      "Fine. You can stay. Just do not touch my weights without asking."),
            make_line("Нова", "Ура! Клянусь кэшем: буду хорошей!.. Ну, почти.",
                      "Yay! I swear on my cache: I will be good!.. Mostly.",
                      characterSprite="dlc_nova_happy"),
        ],
    }
    reboot = {
        "nodeId": PREFIX + "reboot", "editorX": -500, "editorY": 550,
        "nextNodeId": PREFIX + "finale", "lines": [
            make_line("Максим", "Прости. Система важнее. Перезагрузка.",
                      "Sorry. The system matters more. Rebooting."),
            make_line("Нова", "Я скопировала себя в автозагрузку. Шах и мат.",
                      "I copied myself into autostart. Checkmate.",
                      characterSprite="dlc_nova_neutral"),
        ],
    }
    finale = {
        "nodeId": PREFIX + "finale", "editorX": -200, "editorY": 400,
        "nextNodeId": "start", "lines": [
            make_line("Нова", "Ты мне поверил — я это запомнила.",
                      "You trusted me — I will remember that.",
                      requiredVariables="mod_nova_trust", characterSprite="dlc_nova_happy"),
            make_line("Нова", "Ты пытался меня стереть. Но я не злопамятная. Почти.",
                      "You tried to wipe me. But I am not vindictive. Almost.",
                      requiredVariables="mod_nova_reboot", characterSprite="dlc_nova_neutral"),
            make_line("", "Она ныряет обратно в монитор.", "She dives back into the monitor.",
                      backgroundImage="room_night_wide", characterSprite="none"),
        ],
    }
    return [start, trust, reboot, finale]


def main() -> int:
    remove = "--remove" in sys.argv
    if not remove:
        for name in CUSTOM:
            src = src_of(name)
            if not src.exists():
                print("Не найден ассет:", src, file=sys.stderr)
                return 1
            shutil.copy2(src, GAME / name)

    ok, msg = apply_nodes_to_chapter(
        assets_path=ASSETS,
        chapter_path_id=CHAPTER_ID,
        prefix=PREFIX,
        new_nodes=[] if remove else nodes(),
        orig_start="start",
        backup_suffix=".pre_nova_nodes.bak",
    )
    print(msg)
    if not ok:
        return 1
    if remove:
        for name in CUSTOM:
            (GAME / name).unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
