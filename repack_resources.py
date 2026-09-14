#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Запись изменённых данных обратно в Unity resources.assets (LED HEARTS).

Использование:
    python repack_resources.py
    python repack_resources.py --srcdir extracted --input "LED HEARTS_Data/resources.assets"
    python repack_resources.py --srcdir extracted --output "LED HEARTS_Data/resources.assets.new"

Что делает:
- Берёт файлы из srcdir (результат extract_resources.py):
    <path_id>_<name>.json/.txt  — сырое содержимое TextAsset (приоритет)
    <path_id>_<name>.unity.json  — обёртка {"m_Name":..,"m_Script":..} (запасной вариант)
    chapter_01-fixed.json / chapter_01-resources.assets-61.json — тоже понимаются:
        если в JSON есть ключ m_Script, берётся внутренняя строка как новое содержимое;
        иначе весь файл считается новым содержимым главы.
  Сопоставление с объектом идёт по path_id из имени файла (префикс до '_'),
  либо по m_Name (для файлов без префикса вроде chapter_01-fixed.json).
- Заменяет TextAsset.m_Script, вызывает .save(), помечает файл изменённым
  и записывает новый resources.assets.
- По умолчанию делает бэкап оригинала в resources.assets.bak (отключается --no-backup).
- Нетронутые объекты (MonoBehaviour и др.) сохраняются побайтово как были,
  поэтому repack безопасен даже если UnityPy не умеет парсить MonoBehaviour Unity 6000.
- В конце переоткрывает записанный файл для проверки.

Требования:
    pip install UnityPy
"""
import argparse
import json
import pathlib
import re
import shutil
import sys

# path_id_name.ext -> (path_id, rest)
PREFIX_RE = re.compile(r"^(\d+)_.*")


def load_new_content(path: pathlib.Path):
    """Вернуть (kind, text_or_bytes). kind: 'text' | 'bytes'."""
    raw = path.read_bytes()
    # unity.json — обёртка
    if path.suffixes[-2:] == [".unity", ".json"] or path.name.endswith(".unity.json"):
        try:
            wrapper = json.loads(raw.decode("utf-8-sig"))
            if isinstance(wrapper, dict) and "m_Script" in wrapper:
                return "text", wrapper["m_Script"]
        except Exception:
            pass
    # обычный json/txt: пробуем как текст
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "bytes", raw
    # chapter_01-fixed.json (чистый сценарий) остаётся текстом как есть;
    # chapter_01-resources.assets-61.json (обёртка) — достаём m_Script
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "m_Script" in parsed and isinstance(parsed["m_Script"], str):
            return "text", parsed["m_Script"]
    except Exception:
        pass
    return "text", text


def find_game_root(start: pathlib.Path) -> pathlib.Path:
    """Корень игры = папка с LED HEARTS_Data/resources.assets.

    Скрипт может лежать в корне игры или в подпапке (напр. modmaker/).
    """
    for d in (start, start.parent, pathlib.Path.cwd(),
              pathlib.Path.cwd().parent):
        if (d / "LED HEARTS_Data" / "resources.assets").exists():
            return d
    return start


def main() -> int:
    ap = argparse.ArgumentParser(description="Записать TextAsset обратно в resources.assets")
    ap.add_argument("--input", default="LED HEARTS_Data/resources.assets",
                    help="исходный resources.assets")
    ap.add_argument("--srcdir", default="extracted",
                    help="папка с отредактированными файлами")
    ap.add_argument("--output", default="",
                    help="куда записать (по умолчанию перезаписать --input)")
    ap.add_argument("--no-backup", action="store_true",
                    help="не делать resources.assets.bak")
    ap.add_argument("--dry-run", action="store_true",
                    help="только показать, что будет заменено, без записи")
    args = ap.parse_args()

    try:
        import UnityPy
    except ImportError:
        print("Нет модуля UnityPy. Установите: pip install UnityPy", file=sys.stderr)
        return 1

    base = pathlib.Path(__file__).resolve().parent
    game = find_game_root(base)
    inp = pathlib.Path(args.input)
    if not inp.is_absolute():
        for cand in (base / args.input, game / args.input,
                     pathlib.Path.cwd() / args.input):
            if cand.exists():
                inp = cand
                break
        else:
            inp = game / args.input
    if not inp.exists():
        print(f"Не найден файл: {inp}", file=sys.stderr)
        return 1

    srcdir = pathlib.Path(args.srcdir)
    if not srcdir.is_absolute():
        for cand in (base / args.srcdir, game / args.srcdir,
                     pathlib.Path.cwd() / args.srcdir):
            if cand.exists():
                srcdir = cand
                break
        else:
            srcdir = base / args.srcdir
    if not srcdir.exists():
        print(f"Не найдена папка: {srcdir}", file=sys.stderr)
        return 1
    # Новый extract_resources.py раскладывает TextAsset в отдельную папку.
    # Поддерживаем и старый плоский формат extracted/ для совместимости.
    scan_dir = srcdir / "TextAsset" if (srcdir / "TextAsset").is_dir() else srcdir

    out = pathlib.Path(args.output) if args.output else inp
    if not out.is_absolute():
        out = base / out if (base / out).parent.exists() else pathlib.Path.cwd() / out

    # --- собрать кандидатов на замену ---
    # приоритет: сырые <path_id>_*.json/.txt/.bin над *.unity.json
    by_path_id: dict[int, pathlib.Path] = {}
    by_name: dict[str, pathlib.Path] = {}
    for p in sorted(scan_dir.iterdir()):
        if not p.is_file():
            continue
        if p.name in ("index.json", "objects_list.txt"):
            continue
        if p.suffix not in (".json", ".txt", ".bin"):
            continue
        if p.name.endswith(".unity.json"):
            continue  # запасной вариант, обработаем позже
        m = PREFIX_RE.match(p.name)
        if m:
            by_path_id[int(m.group(1))] = p
        else:
            # файлы вида chapter_01-fixed.json — сопоставим по имени главы
            stem = p.stem  # chapter_01-fixed
            short = stem.split("-")[0].split("_resources")[0]
            by_name[short] = p
    # запасные unity.json только если нет сырого файла с тем же path_id
    for p in sorted(scan_dir.iterdir()):
        if not (p.is_file() and p.name.endswith(".unity.json")):
            continue
        m = PREFIX_RE.match(p.name)
        if m and int(m.group(1)) not in by_path_id:
            by_path_id[int(m.group(1))] = p

    if not by_path_id and not by_name:
        print(f"В {srcdir} нет файлов для записи (.json/.txt/.bin).", file=sys.stderr)
        return 1

    print(f"Загрузка: {inp} ...")
    env = UnityPy.load(str(inp))

    # индекс текущих TextAsset: path_id -> m_Name
    current = {}
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        try:
            d = obj.read()
        except Exception as e:
            print(f"  ! пропуск path_id={obj.path_id}: не читается ({e})")
            continue
        current[obj.path_id] = d.m_Name
        # файлы без префикса (chapter_01-fixed.json) -> найти path_id по имени
        if obj.path_id not in by_path_id and d.m_Name in by_name:
            by_path_id[obj.path_id] = by_name[d.m_Name]

    print(f"Кандидатов из папки: {len(by_path_id)}, TextAsset в файле: {len(current)}")

    changed = 0
    for path_id, src in sorted(by_path_id.items()):
        if path_id not in current:
            print(f"  ! {src.name}: path_id {path_id} нет в resources.assets — пропуск")
            continue
        kind, new_content = load_new_content(src)
        obj = env.file.objects.get(path_id)
        if obj is None:
            # fallback: поиск перебором
            found = None
            for o in env.objects:
                if o.path_id == path_id:
                    found = o
                    break
            if found is None:
                print(f"  ! path_id {path_id}: объект не найден — пропуск")
                continue
            obj = found
        d = obj.read()
        old = d.m_Script
        old_raw = old if isinstance(old, bytes) else old.encode("utf-8")
        new_raw = new_content if isinstance(new_content, bytes) else new_content.encode("utf-8")
        if old_raw == new_raw:
            print(f"  = {path_id} {d.m_Name!r} ({src.name}): без изменений")
            continue
        print(f"  * {path_id} {d.m_Name!r} ({src.name}): {len(old_raw)} -> {len(new_raw)} байт")
        changed += 1
        if args.dry_run:
            continue
        if kind == "bytes" or isinstance(new_content, bytes):
            d.m_Script = bytes(new_content)
        else:
            d.m_Script = str(new_content)
        d.save()  # помечает объект изменённым, остальные объекты сохранятся как были

    if args.dry_run:
        print(f"\nDry-run: изменений было бы {changed}. Запись не выполнялась.")
        return 0

    if changed == 0:
        print("\nИзменений нет — запись не требуется.")
        return 0

    # --- запись ---
    try:
        same_file = out.resolve() == inp.resolve()
    except OSError:
        same_file = False
    if not args.no_backup and same_file:
        bak = inp.with_name(inp.name + ".bak")
        if not bak.exists():
            shutil.copy2(inp, bak)
            print(f"Бэкап: {bak}")
        else:
            print(f"Бэкап уже есть: {bak} (новый не создаю)")

    env.file.mark_changed()
    new_bytes = env.file.save()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_bytes(new_bytes)

    # проверка: переоткрыть (из памяти, чтобы не держать lock на tmp в Windows)
    try:
        env2 = UnityPy.load(new_bytes)
        n = sum(1 for o in env2.objects if o.type.name == "TextAsset")
        print(f"Проверка: пересобранный файл читается, TextAsset: {n}")
    except Exception as e:
        tmp.unlink(missing_ok=True)
        print(f"ОШИБКА: пересобранный файл не читается: {e}", file=sys.stderr)
        return 1

    shutil.move(str(tmp), str(out))
    print(f"\nГотово: заменено TextAsset: {changed}")
    print(f"Записано: {out} ({len(new_bytes)} байт)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
