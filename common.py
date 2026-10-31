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


def backup_once(path: pathlib.Path, label: str = "Бэкап",
                suffix: str = ".bak") -> pathlib.Path:
    """Копия path в path<suffix> один раз (повторно не перезаписывает).

    suffix: суффикс бэкапа (по умолчанию '.bak'). Позволяет создавать
    разные бэкапы для разных этапов (напр. '.pre_demo_nodes.bak').
    """
    bak = path.with_name(path.name + suffix)
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


def atomic_write_text(path: pathlib.Path, text: str,
                      encoding: str = "utf-8", newline: str = "") -> None:
    """Текстовая версия atomic_write (через .tmp + move).

    newline='': по умолчанию отключает трансляцию \\n -> \
\\n на Windows,
    чтобы соответствовать соглашению проекта (см. write_json).
    """
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding=encoding, newline=newline) as f:
        f.write(text)
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


# ---------------------------------------------------------------------------
# Helpers for mod scripts (node builders + container management)
# ---------------------------------------------------------------------------

def make_line(speaker: str, text: str, text_en: str = "", **overrides) -> dict:
    """Построить строку реплики со всеми полями схемы DialogueLine.

    text_en по умолчанию = text (чтобы не дублировать для моноязычных реплик).
    overrides перекрывают значения по умолчанию (напр. backgroundImage='room').
    """
    line = {
        "characterName": speaker,
        "characterName_en": speaker,
        "text": text,
        "text_en": text_en or text,
        "characterSprite": "",
        "backgroundImage": "",
        "voiceClip": "",
        "musicClip": "",
        "sfxClip": "",
        "characterPosition": "center",
        "emotion": "",
        "overlayAlpha": -1,
        "requiredVariables": "",
        "choices": [],
    }
    line.update(overrides)
    return line


def make_choice(text: str, target: str, text_en: str = "", **overrides) -> dict:
    """Построить объект выбора DialogueChoice.

    text_en по умолчанию = text. variable=... устанавливает setVariable.
    overrides перекрывают значения по умолчанию.
    """
    variable = overrides.pop("variable", "")
    ch = {
        "choiceText": text,
        "choiceText_en": text_en or text,
        "targetNodeId": target,
        "setVariable": variable,
        "modifyValue": 1 if variable else 0,
        "requiredVariables": "",
        "lockedText": "",
        "lockedText_en": "",
    }
    ch.update(overrides)
    return ch


def get_resource_manager(env) -> "tuple[object, dict]":
    """Найти ResourceManager в UnityPy env и вернуть (объект, typetree dict).

    Raises ValueError с понятным сообщением, если ResourceManager отсутствует
    (что не должно происходить в штатных ассетах игры).
    """
    for o in env.file.objects.values():
        if o.type.name == "ResourceManager":
            rm_obj = o
            rm = o.parse_as_dict(check_read=False)
            return rm_obj, rm
    raise ValueError("Нет ResourceManager в globalgamemanagers")


def upsert_container(rm_dict: dict, rm_obj, ckey: str, path_id: int,
                     file_id: int = 4) -> None:
    """Обновить запись в ResourceManager.m_Container: убрать старую (если была),
    добавить новую {FileID, PathID}.

    Модифицирует rm_dict и вызывает rm_obj.save_typetree(rm_dict) для фиксации
    изменений. Используется add_texture/add_chapter/add_audio для регистрации
    новых ассетов.
    """
    cont = [e for e in rm_dict["m_Container"]
            if not (e[0] == ckey and e[1].get("m_FileID") == file_id)]
    cont.append((ckey, {"m_FileID": file_id, "m_PathID": path_id}))
    rm_dict["m_Container"] = cont
    rm_obj.save_typetree(rm_dict)


def apply_nodes_to_chapter(
    assets_path: pathlib.Path,
    chapter_path_id: int,
    prefix: str,
    new_nodes: list[dict],
    orig_start: str = "start",
    backup_suffix: str = ".bak",
    title_suffix: str = "",
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Применить или удалить демо-узлы в главе (общий pipeline для mod_*_node.py).

    Pipeline:
    1. Создать бэкап assets (один раз, с кастомным суффиксом)
    2. Загрузить resources.assets через UnityPy
    3. Прочитать главу по chapter_path_id
    4. Удалить старые узлы с nodeId, начинающимся на prefix
    5. Если new_nodes непустой: добавить новые узлы, установить startingNodeId
    6. Если new_nodes пустой (remove): восстановить startingNodeId на orig_start
    7. Опционально добавить/убрать title_suffix
    8. Валидировать главу через validate_chapter()
    9. Сохранить и проверить пересборку
    10. Записать через atomic_write (если не dry_run)

    Args:
        assets_path: путь к resources.assets
        chapter_path_id: path_id главы (обычно 101 для chapter_01)
        prefix: префикс demo-узлов (напр. "mod_demo_", "mod_nova_")
        new_nodes: список новых узлов для вставки (пустой для --remove)
        orig_start: имя оригинального стартового узла (обычно "start")
        backup_suffix: суффикс бэкапа (напр. ".pre_demo_nodes.bak")
        title_suffix: опциональный суффикс для chapterTitle (напр. " [MOD]")
        dry_run: если True, не записывать изменения

    Returns:
        (success, message): True если успешно, False + сообщение об ошибке
    """
    import json as _json
    UnityPy = require_unitypy()

    # 1. Бэкап
    if not dry_run:
        backup_once(assets_path, suffix=backup_suffix)

    # 2. Загрузка
    env = UnityPy.load(str(assets_path))
    ch_obj = env.file.objects.get(chapter_path_id)
    if ch_obj is None:
        return False, f"Нет объекта главы {chapter_path_id} в resources.assets"

    # 3. Чтение главы
    ch = ch_obj.read()
    data = _json.loads(ch.m_Script)

    # 4. Удаление старых demo-узлов
    data["nodes"] = [n for n in data["nodes"]
                     if not n.get("nodeId", "").startswith(prefix)]

    # 5/6. Установка или удаление
    remove = len(new_nodes) == 0
    if remove:
        if data.get("startingNodeId", "").startswith(prefix):
            data["startingNodeId"] = orig_start
        # Проверка что orig_start существует
        if not any(n["nodeId"] == orig_start for n in data["nodes"]):
            return False, f"Оригинальный старт '{orig_start}' не найден после удаления {prefix}* узлов"
        if title_suffix:
            data["chapterTitle"] = (data.get("chapterTitle") or "").replace(title_suffix, "")
            data["chapterTitle_en"] = (data.get("chapterTitle_en") or "").replace(title_suffix, "")
    else:
        data["nodes"] = new_nodes + data["nodes"]
        data["startingNodeId"] = prefix + "start"
        if title_suffix and title_suffix not in (data.get("chapterTitle") or ""):
            data["chapterTitle"] = (data.get("chapterTitle") or "") + title_suffix
            data["chapterTitle_en"] = (data.get("chapterTitle_en") or "") + title_suffix

    # 7. Валидация
    problems = validate_chapter(data)
    if problems:
        return False, f"Валидация главы не прошла: {'; '.join(problems)}"

    # 8. Сохранение
    ch.m_Script = _json.dumps(data, ensure_ascii=False)
    ch.save()
    env.file.mark_changed()
    new_bytes = env.file.save()

    # 9. Проверка пересборки
    env2 = UnityPy.load(new_bytes)
    ch_obj2 = env2.file.objects.get(chapter_path_id)
    if ch_obj2 is None:
        return False, f"Проверка не удалась: нет объекта {chapter_path_id} в пересборке"
    ch2 = _json.loads(ch_obj2.read().m_Script)
    demo_ids = [n["nodeId"] for n in ch2["nodes"] if n["nodeId"].startswith(prefix)]

    if dry_run:
        return True, f"Dry-run: {'удалено' if remove else f'вставлено {len(new_nodes)}'} узлов {prefix}*, старт={ch2['startingNodeId']}"

    # 10. Запись
    atomic_write(assets_path, new_bytes)
    action = "удалено" if remove else f"вставлено {len(new_nodes)}"
    return True, f"{action} узлов {prefix}*, старт={ch2['startingNodeId']}, записано: {assets_path}"
