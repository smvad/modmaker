#!/usr/bin/env python3
"""Тестовая GIF-нода LED HEARTS: проверка, грузит ли игра .gif."""
from __future__ import annotations

import pathlib
import shutil
import sys

BASE = pathlib.Path(__file__).resolve().parent

sys.path.insert(0, str(BASE))
from common import apply_nodes_to_chapter, find_game_root, make_line  # noqa: E402

GAME = find_game_root(BASE)
IMGDIR = BASE / "images"
ASSETS = GAME / "LED HEARTS_Data" / "resources.assets"
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


def nodes():
    start = {
        "nodeId": PREFIX + "start", "editorX": -800, "editorY": 800,
        "nextNodeId": PREFIX + "sprite", "lines": [
            make_line("", "[GIF-ТЕСТ 1/3] Сейчас фон = dlc_gif_test.gif (400x400, 44 кадра).",
                      "[GIF-TEST 1/3] Background should be dlc_gif_test.gif (400x400, 44 frames).",
                      backgroundImage="room_night_wide", musicClip="lonely_dev"),
            make_line("", "Ставлю фон dlc_gif_test. Если видишь вращение Земли — GIF работает. "
                      "Если чёрный фон / старый фон + warning в Player.log — не работает.",
                      "Setting background to dlc_gif_test. Spinning Earth = GIF works. "
                      "Black/old bg + Player.log warning = GIF NOT supported.",
                      backgroundImage="dlc_gif_test"),
            make_line("", "Жми дальше — проверим .gif как спрайт персонажа.",
                      "Continue — next we test .gif as a character sprite."),
        ],
    }
    sprite = {
        "nodeId": PREFIX + "sprite", "editorX": -500, "editorY": 800,
        "nextNodeId": PREFIX + "control", "lines": [
            make_line("", "[GIF-ТЕСТ 2/3] Сейчас спрайт = dlc_gif_test.gif по центру.",
                      "[GIF-TEST 2/3] Sprite should be dlc_gif_test.gif, centered.",
                      backgroundImage="room_night_desk",
                      characterSprite="dlc_gif_test", characterPosition="center"),
            make_line("Гифка", "Я — dlc_gif_test.gif. Если я кручусь — игра умеет в GIF. "
                               "Если меня нет / статичная картинка — только PNG/JPG.",
                      "I am dlc_gif_test.gif. Spinning = GIF works. Missing/static = PNG/JPG only.",
                      characterSprite="dlc_gif_test", characterPosition="center"),
        ],
    }
    control = {
        "nodeId": PREFIX + "control", "editorX": -200, "editorY": 800,
        "nextNodeId": ORIG_START, "lines": [
            make_line("", "[GIF-ТЕСТ 3/3] Контроль: PNG первого кадра — dlc_gif_test_firstframe.",
                      "[GIF-TEST 3/3] Control: PNG of first frame — dlc_gif_test_firstframe.",
                      backgroundImage="dlc_gif_test_firstframe",
                      characterSprite="none"),
            make_line("", "Этот PNG обязан показаться. Если GIF выше не показался, а PNG показался — "
                      "вывод: LoadImage ест PNG, но не ест GIF. Конвертируй GIF в PNG-секвенцию.",
                      "This PNG must show. If GIF above failed but this shows — "
                      "LoadImage eats PNG, not GIF. Convert GIF to PNG sequence.",
                      backgroundImage="dlc_gif_test_firstframe",
                      characterSprite="none"),
            make_line("", "Тест окончен. Дальше — оригинальная игра с узла start.",
                      "Test over. Original game continues from node start.",
                      backgroundImage="room_night_wide", musicClip="lonely_dev",
                      characterSprite="none"),
        ],
    }
    return [start, sprite, control]


def main() -> int:
    remove = "--remove" in sys.argv
    if not remove:
        for name in CUSTOM:
            src = src_of(name)
            if not src.exists():
                print("Не найден ассет:", src, file=sys.stderr)
                return 1
            shutil.copy2(src, GAME / name)
            print(f"+ {name} -> корень игры ({(GAME / name).stat().st_size} байт)")

    ok, msg = apply_nodes_to_chapter(
        assets_path=ASSETS,
        chapter_path_id=CHAPTER_ID,
        prefix=PREFIX,
        new_nodes=[] if remove else nodes(),
        orig_start=ORIG_START,
        backup_suffix=".pre_gif_nodes.bak",
    )
    print(msg)
    if not ok:
        return 1
    if remove:
        for name in CUSTOM:
            (GAME / name).unlink(missing_ok=True)
    else:
        print("Запусти LED HEARTS.exe и смотри Player.log: "
              "C:\\\\Users\\\\%USERNAME%\\\\AppData\\\\LocalLow\\\\fugas_kitsune\\\\LED HEARTS\\\\Player.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
