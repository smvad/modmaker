#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Извлечение всех объектов из Unity resources.assets (LED HEARTS).

Использование:
    python extract_resources.py
    python extract_resources.py --input "LED HEARTS_Data/resources.assets" --outdir extracted
    python extract_resources.py --only chapter_01,chapter_02

Что делает:
- Загружает resources.assets через UnityPy.
- Составляет index.json для всех объектов: path_id -> type / name / files.
- Создаёт отдельную папку для каждого Unity-типа.
- Каждый объект сохраняет исходные байты (.raw) и JSON-метаданные (.json).
- Texture2D и Sprite дополнительно сохраняются как изображения (.png).
- Каждый TextAsset дополнительно сохраняет содержимое как:
    <path_id>_<m_Name>.bin  (если не текст)
    <path_id>_<m_Name>.json/.txt (если текст, расширение подбирается по содержимому)
  + дублирующий Unity-обёртка JSON: <path_id>_<m_Name>.unity.json  {"m_Name":..., "m_Script":...}
    (такой формат понимает repack_resources.py и старый read_chapter.py)
- Даже если UnityPy не может декодировать объект, его исходные байты и запись
  об ошибке сохраняются. Это важно для MonoBehaviour и AudioClip с внешними ресурсами.

Требования:
    pip install UnityPy
"""
import argparse
import json
import pathlib
import sys


def guess_ext(name: str, text: str) -> str:
    s = text.lstrip("\ufeff \r\n\t")
    if s.startswith("{") or s.startswith("["):
        return ".json"
    if name.endswith(".json"):
        return ".json"
    return ".txt"


def find_game_root(start: pathlib.Path) -> pathlib.Path:
    """Корень игры = папка с LED HEARTS_Data/resources.assets.

    Скрипт может лежать в корне игры или в подпапке (напр. modmaker/).
    """
    for d in (start, start.parent, pathlib.Path.cwd(),
              pathlib.Path.cwd().parent):
        if (d / "LED HEARTS_Data" / "resources.assets").exists():
            return d
    return start


def safe_name(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name) or "unnamed"


def write_json(path: pathlib.Path, value) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, default=repr)


def object_name(obj, parsed=None) -> str:
    if isinstance(parsed, dict):
        value = parsed.get("m_Name")
        if isinstance(value, str):
            return value
    try:
        return obj.peek_name() or ""
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Извлечь TextAsset из resources.assets")
    ap.add_argument("--input", default="LED HEARTS_Data/resources.assets",
                    help="путь к resources.assets")
    ap.add_argument("--outdir", default="extracted",
                    help="папка для извлечённых файлов")
    ap.add_argument("--only", default="",
                    help="только эти имена через запятую, напр. chapter_01,chapter_02 (пусто = все)")
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

    outdir = pathlib.Path(args.outdir)
    if not outdir.is_absolute():
        outdir = base / outdir
    outdir.mkdir(parents=True, exist_ok=True)

    only = {x.strip() for x in args.only.split(",") if x.strip()} if args.only else set()

    print(f"Загрузка: {inp} ...")
    env = UnityPy.load(str(inp))

    index = []
    objects_summary = []
    saved = 0
    errors = 0

    for obj in env.objects:
        otype = obj.type.name
        type_dir = outdir / otype
        type_dir.mkdir(parents=True, exist_ok=True)
        parsed = None
        error = None
        try:
            parsed = obj.parse_as_dict(check_read=False)
        except Exception as e:
            error = f"parse-error: {type(e).__name__}: {e}"
        name = object_name(obj, parsed)
        if only and name not in only:
            continue
        stem = f"{obj.path_id}_{safe_name(name)}"
        entry = {"path_id": obj.path_id, "type": otype, "name": name,
                 "files": [], "errors": []}
        if error:
            entry["errors"].append(error)

        try:
            raw = obj.get_raw_data()
            raw_path = type_dir / f"{stem}.raw"
            raw_path.write_bytes(raw)
            entry["files"].append(raw_path.relative_to(outdir).as_posix())
            entry["raw_size"] = len(raw)
        except Exception as e:
            entry["errors"].append(f"raw-error: {type(e).__name__}: {e}")

        if parsed is not None:
            meta_path = type_dir / f"{stem}.json"
            write_json(meta_path, parsed)
            entry["files"].append(meta_path.relative_to(outdir).as_posix())

        # Декодированные изображения полезнее одних Unity raw-байтов.
        if otype in ("Texture2D", "Sprite"):
            try:
                image = obj.read().image
                image_path = type_dir / f"{stem}.png"
                image.save(image_path)
                entry["files"].append(image_path.relative_to(outdir).as_posix())
                entry["image_size"] = list(image.size)
            except Exception as e:
                entry["errors"].append(f"image-error: {type(e).__name__}: {e}")

        # Сохраняем читабельное содержимое TextAsset для существующего repack-пайплайна.
        if otype == "TextAsset":
            try:
                d = obj.read()
                script = d.m_Script
                text = script.decode("utf-8-sig") if isinstance(script, bytes) else script
                text_path = type_dir / f"{stem}{guess_ext(name, text)}"
                with open(text_path, "w", encoding="utf-8", newline="") as f:
                    f.write(text)
                wrapper_path = type_dir / f"{stem}.unity.json"
                write_json(wrapper_path, {"m_Name": name, "m_Script": text})
                entry["files"].extend([
                    text_path.relative_to(outdir).as_posix(),
                    wrapper_path.relative_to(outdir).as_posix(),
                ])
            except Exception as e:
                entry["errors"].append(f"text-error: {type(e).__name__}: {e}")
        if entry["errors"]:
            errors += len(entry["errors"])
        index.append(entry)
        objects_summary.append(f"{obj.path_id}\t{otype}\t{name}\t{'; '.join(entry['errors'])}")
        saved += 1

    write_json(outdir / "index.json", index)
    (outdir / "objects_list.txt").write_text("\n".join(objects_summary) + "\n", encoding="utf-8")
    summary = {"input": str(inp), "objects": len(index), "errors": errors,
               "types": {t: sum(1 for x in index if x["type"] == t)
                         for t in sorted({x["type"] for x in index})}}
    write_json(outdir / "summary.json", summary)

    print(f"\nГотово: извлечено объектов: {saved}, ошибок декодирования/чтения: {errors}")
    print(f"Папка: {outdir}")
    print("Карта: index.json, objects_list.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
