#!/usr/bin/env python3
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
import pathlib
import shutil
import sys

BASE = pathlib.Path(__file__).resolve().parent

sys.path.insert(0, str(BASE))
from common import apply_nodes_to_chapter, find_game_root, make_choice, make_line  # noqa: E402

GAME = find_game_root(BASE)
ASSETS = GAME / "LED HEARTS_Data" / "resources.assets"
CHAPTER_PATH_ID = 101
PREFIX = "mod_demo_"
ORIG_START = "start"
CUSTOM_AUDIO = BASE / "mod_demo_jingle.wav"


def build_demo():
    start = {
        "nodeId": PREFIX + "start",
        "editorX": -800, "editorY": 0,
        "nextNodeId": "",
        "lines": [
            make_line("", "[ДЕМО-МОД] Это кастомная нода: текст, фон mod_start_bg.png, музыка.",
                      "[MOD-DEMO] Custom node: text, mod_start_bg.png background, music.",
                      backgroundImage="room_night_wide", musicClip="lonely_dev"),
            make_line("", "Дзынь! Это кастомный звук mod_demo_jingle.wav из корня игры.",
                      "That chime is a custom sound: mod_demo_jingle.wav from game root.",
                      sfxClip="mod_demo_jingle:0.9"),
            make_line("Милли", "А это спикер + спрайт + позиция по центру!",
                      "Speaker + sprite + center position demo!",
                      characterSprite="milly/pose_a/happy", characterPosition="center",
                      backgroundImage="room_night_desk"),
            make_line("", "*Стук в дверь* — демонстрация звукового эффекта.",
                      "*Knock on the door* — sound effect demo.",
                      sfxClip="door_knock:0.5"),
            make_line("", "А так работает затемнение экрана (overlayAlpha).",
                      "Screen dim (overlayAlpha) demo.",
                      backgroundImage="cafe", overlayAlpha=0.5),
            make_line("", "Затемнение снято. Время выбора — выборы ведут в разные ветки!",
                      "Dim off. Time to choose — choices branch the story!",
                      overlayAlpha=-1,
                      choices=[
                          make_choice("Пойти в зоопарк (путь А)", PREFIX + "branch_a",
                                      "Go to the zoo (path A)",
                                      variable="mod_demo_path_a"),
                          make_choice("Пойти в кафе (путь Б)", PREFIX + "branch_b",
                                      "Go to the cafe (path B)",
                                      variable="mod_demo_path_b"),
                          make_choice("Секретная ветка", PREFIX + "secret", "Secret branch",
                                      requiredVariables="mod_demo_path_a",
                                      lockedText="(Сначала выбери путь А)",
                                      lockedText_en="(Pick path A first)"),
                      ]),
        ],
    }
    branch_a = {
        "nodeId": PREFIX + "branch_a",
        "editorX": -500, "editorY": -200,
        "nextNodeId": PREFIX + "finale",
        "lines": [
            make_line("", "Путь А: зоопарк. Фон и музыка сменились.",
                      "Path A: the zoo. New background and music.",
                      backgroundImage="zoo", musicClip="zoo_ending"),
            make_line("", "Шум толпы по кругу (громко, отдельная строка без смены музыки).",
                      "Looping crowd SFX on its own line, no music change.",
                      sfxClip="crowd:0.6:loop"),
            make_line("Виолетта", "Шум толпы остановлен командой stop. Эмоция: happy.",
                      "Crowd stopped with \"stop\". Emotion: happy.",
                      characterSprite="violet/pose_a/neutral", characterPosition="left",
                      sfxClip="stop", emotion="happy"),
        ],
    }
    branch_b = {
        "nodeId": PREFIX + "branch_b",
        "editorX": -500, "editorY": 200,
        "nextNodeId": PREFIX + "finale",
        "lines": [
            make_line("", "Путь Б: кафе. Другая музыка.",
                      "Path B: the cafe. Different music.",
                      backgroundImage="cafe", musicClip="quiet_room"),
            make_line("", "Фоновый гул классной комнаты по кругу (cafe_noise в игре отсутствует).",
                      "Classroom ambience loop (cafe_noise is missing from the game).",
                      sfxClip="classroom:0.5:loop"),
            make_line("Милли", "Спрайт справа, позиция right! Гул остановлен.",
                      "Sprite on the right! Ambience stopped.",
                      characterSprite="milly/pose_a/surprised",
                      characterPosition="right", sfxClip="stop"),
        ],
    }
    secret = {
        "nodeId": PREFIX + "secret",
        "editorX": -500, "editorY": 0,
        "nextNodeId": PREFIX + "finale",
        "lines": [
            make_line("", "Секретная ветка! Сюда пускает только переменная mod_demo_path_a.",
                      "Secret branch! Gated by the mod_demo_path_a variable.",
                      backgroundImage="silhouette_red_eyes",
                      voiceClip="voice_chapter_01_dream_start_13"),
        ],
    }
    finale = {
        "nodeId": PREFIX + "finale",
        "editorX": -200, "editorY": 0,
        "nextNodeId": ORIG_START,
        "lines": [
            make_line("", "Ты выбрал путь А — эта строка видна только с переменной mod_demo_path_a.",
                      "You picked path A — this line needs mod_demo_path_a.",
                      requiredVariables="mod_demo_path_a"),
            make_line("", "Ты выбрал путь Б — эта строка видна только с переменной mod_demo_path_b.",
                      "You picked path B — this line needs mod_demo_path_b.",
                      requiredVariables="mod_demo_path_b"),
            make_line("", "Демо окончено! Дальше — оригинальная игра с узла start.",
                      "Demo over! The original game continues from node start.",
                      backgroundImage="room_night_wide", musicClip="lonely_dev",
                      characterSprite="none"),
        ],
    }
    return [start, branch_a, branch_b, secret, finale]


def main() -> int:
    remove = "--remove" in sys.argv

    if not remove:
        if not CUSTOM_AUDIO.exists():
            print("Нет кастомного звука:", CUSTOM_AUDIO, file=sys.stderr)
            return 1
        # Игра ищет внешний WAV в корне игры, а не внутри modmaker.
        shutil.copy2(CUSTOM_AUDIO, GAME / CUSTOM_AUDIO.name)
        print("Кастомный звук скопирован в корень игры:", GAME / CUSTOM_AUDIO.name)

    ok, msg = apply_nodes_to_chapter(
        assets_path=ASSETS,
        chapter_path_id=CHAPTER_PATH_ID,
        prefix=PREFIX,
        new_nodes=[] if remove else build_demo(),
        orig_start=ORIG_START,
        backup_suffix=".pre_demo_nodes.bak",
        title_suffix=" [MOD]",
    )
    print(msg)
    if not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
