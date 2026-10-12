#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Общие помощники modmaker (LED HEARTS): пути, бэкапы, валидация глав.

Все скрипты запускаются из корня игры (`./LED HEARTS`) как
`modmaker/<script>.py`, поэтому обычный `import common` находит этот модуль
(sys.path[0] — папка modmaker). Отдельное копирование скриптов вне репозитория
не поддерживается.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

#: Маркер корня игры: папка с этим файлом относительно него.
GAME_MARKER = pathlib.Path("LED HEARTS_Data") / "resources.assets"

#: Значения полей сценария, которые не являются именами ассетов.
SKIP_REFS = frozenset({"", "none", "stop"})

IMAGE_FIELDS = ("backgroundImage", "characterSprite")
AUDIO_FIELDS = ("musicClip", "sfxClip", "voiceClip")


def find_game_root(start: pathlib.Path) -> pathlib.Path:
    """Корень игры = папка с LED HEARTS_Data/resources.assets.

    Скрипт может лежать в корне игры или в подпапке (напр. modmaker/).
    """
    for d in (start, start.parent, pathlib.Path.cwd(),
              pathlib.Path.cwd().parent):
        if (d / GAME_MARKER).exists():
            return d
    return start


def require_unitypy():
    """Импорт UnityPy с понятной ошибкой вместо traceback."""
    try:
        import UnityPy
    except ImportError:
        print("Нет модуля UnityPy. Установите: pip install -r modmaker\\requirements.txt",
              file=sys.stderr)
        raise SystemExit(1)
    return UnityPy


def safe_name(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name) or "unnamed"


def write_json(path: pathlib.Path, value) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, default=repr)


def backup_once(path: pathlib.Path, label: str = "Бэкап") -> pathlib.Path:
    """Копия path в path.bak один раз (повторно не перезаписывает)."""
    bak = path.with_name(path.name + ".bak")
    if not bak.exists():
        shutil.copy2(path, bak)
        print(f"{label}: {bak}")
    else:
        print(f"{label} уже есть: {bak} (новый не создаю)")
    return bak


def atomic_write(path: pathlib.Path, data: bytes) -> None:
    """Запись через .tmp + move (без полуфайлов при обрыве)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    shutil.move(str(tmp), str(path))


def load_scenario(path: pathlib.Path) -> dict:
    """Сценарий главы из сырого JSON или Unity-обёртки {m_Name, m_Script}."""
    outer = json.loads(path.read_bytes().decode("utf-8-sig"))
    if isinstance(outer, dict) and isinstance(outer.get("m_Script"), str):
        return json.loads(outer["m_Script"])
    if isinstance(outer, dict) and "nodes" in outer:
        return outer
    raise ValueError(f"{path.name}: нет ни m_Script, ни chapterId/nodes")


def validate_chapter(scenario: dict) -> list[str]:
    """Проверка связности главы: уникальность nodeId, next/target-ссылки."""
    problems: list[str] = []
    if not isinstance(scenario.get("nodes"), list) or not scenario["nodes"]:
        return ["нет массива nodes"]
    nodes = scenario["nodes"]
    ids = [n.get("nodeId", "") for n in nodes]
    if len(set(ids)) != len(ids):
        problems.append("дублирующиеся nodeId")
    start = scenario.get("startingNodeId", "")
    if start not in set(ids):
        problems.append(f"startingNodeId {start!r} нет среди узлов")
    known = set(ids)

    def is_special_target(tgt: str) -> bool:
        # load_chapter:chapter_02:node — переход между главами, не узел
        return tgt.startswith("load_chapter:")

    for n in nodes:
        nxt = n.get("nextNodeId", "")
        if nxt and nxt not in known and not is_special_target(nxt):
            problems.append(f"узел {n.get('nodeId')}: nextNodeId {nxt!r} никуда не ведёт")
        for i, line in enumerate(n.get("lines", []) or []):
            for c in line.get("choices", []) or []:
                tgt = c.get("targetNodeId", "")
                if tgt and tgt not in known and not is_special_target(tgt):
                    problems.append(
                        f"узел {n.get('nodeId')} строка {i + 1}: "
                        f"targetNodeId {tgt!r} никуда не ведёт"
                    )
    return problems


def clip_base(value: object) -> str:
    """'crowd:0.6:loop' -> 'crowd'; 'stop'/'none'/'' -> ''."""
    if not isinstance(value, str):
        return ""
    base = value.split(":")[0].strip()
    if base in SKIP_REFS:
        return ""
    return base


def collect_refs(scenario: dict) -> tuple[set[str], set[str]]:
    """Имена ассетов главы без пустых/none/stop: (изображения, звуки)."""
    images: set[str] = set()
    audios: set[str] = set()
    for n in scenario.get("nodes", []) or []:
        for line in n.get("lines", []) or []:
            if not isinstance(line, dict):
                continue
            for fld in IMAGE_FIELDS:
                v = line.get(fld, "")
                if isinstance(v, str) and v and v not in SKIP_REFS:
                    images.add(v)
            for fld in AUDIO_FIELDS:
                v = clip_base(line.get(fld, ""))
                if v:
                    audios.add(v)
    return images, audios
