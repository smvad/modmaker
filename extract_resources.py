#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Извлечение данных (TextAsset) из Unity resources.assets (LED HEARTS).

Использование:
    python extract_resources.py
    python extract_resources.py --input "LED HEARTS_Data/resources.assets" --outdir extracted
    python extract_resources.py --only chapter_01,chapter_02

Что делает:
- Загружает resources.assets через UnityPy.
- Составляет index.json: path_id -> type / name / size.
- Каждый TextAsset сохраняет в outdir как:
    <path_id>_<m_Name>.bin  (если не текст)
    <path_id>_<m_Name>.json/.txt (если текст, расширение подбирается по содержимому)
  + дублирующий Unity-обёртка JSON: <path_id>_<m_Name>.unity.json  {"m_Name":..., "m_Script":...}
    (такой формат понимает repack_resources.py и старый read_chapter.py)
- Остальные типы объектов не трогает, но перечисляет в objects_list.txt
  (MonoBehaviour в Unity 6000 UnityPy часто не может распарсить — это нормально,
   текстовые данные глав лежат именно в TextAsset и извлекаются корректно).

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

    outdir = pathlib.Path(args.only if False else args.outdir)
    if not outdir.is_absolute():
        outdir = base / outdir
    outdir.mkdir(parents=True, exist_ok=True)

    only = {x.strip() for x in args.only.split(",") if x.strip()} if args.only else set()

    print(f"Загрузка: {inp} ...")
    env = UnityPy.load(str(inp))

    index = []
    objects_summary = []
    saved = 0

    for obj in env.objects:
        otype = obj.type.name
        # Безопасно получить имя, не роняя весь дамп на битых MonoBehaviour (Unity 6000)
        name = ""
        try:
            if otype == "TextAsset":
                d = obj.read()
                name = d.m_Name
            else:
                # peek не всегда работает, поэтому пробуем аккуратно
                try:
                    name = obj.peek_name() or ""
                except Exception:
                    name = ""
        except Exception as e:
            objects_summary.append(f"{obj.path_id}\t{otype}\t<read-error: {e}>")
            index.append({"path_id": obj.path_id, "type": otype,
                          "name": "", "error": f"read-error: {e}"})
            continue

        objects_summary.append(f"{obj.path_id}\t{otype}\t{name}")

        if otype != "TextAsset":
            continue
        if only and name not in only:
            continue

        d = obj.read()
        script = d.m_Script  # str или bytes
        if isinstance(script, bytes):
            raw = bytes(script)
            try:
                text = raw.decode("utf-8-sig")
                is_text = True
            except UnicodeDecodeError:
                is_text = False
                text = ""
        else:
            text = script
            raw = script.encode("utf-8")
            is_text = True

        safe_name = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name) or "unnamed"
        if is_text:
            ext = guess_ext(name, text)
            main_path = outdir / f"{obj.path_id}_{safe_name}{ext}"
            # newline='' важен: иначе Windows превратит \r\n в \r\r\n и файл
            # будет отличаться от оригинала (ложные "изменения" при repack)
            with open(main_path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            # Unity-обёртка для совместимости со старым пайплайном
            wrapper = {"m_Name": name, "m_Script": text}
            with open(outdir / f"{obj.path_id}_{safe_name}.unity.json",
                      "w", encoding="utf-8", newline="") as f:
                f.write(json.dumps(wrapper, ensure_ascii=False, indent=2))
            print(f"  [TextAsset] {obj.path_id} {name!r} -> {main_path.name} ({len(raw)} байт)")
        else:
            main_path = outdir / f"{obj.path_id}_{safe_name}.bin"
            main_path.write_bytes(raw)
            print(f"  [TextAsset:bin] {obj.path_id} {name!r} -> {main_path.name} ({len(raw)} байт)")

        index.append({"path_id": obj.path_id, "type": otype, "name": name,
                      "file": main_path.name, "size": len(raw)})
        saved += 1

    # полный список объектов тоже сохраняем (вдруг понадобятся path_id)
    for extra in sorted(set(index[i]["path_id"] for i in range(len(index)) if "path_id" in index[i])):
        pass
    (outdir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    (outdir / "objects_list.txt").write_text("\n".join(objects_summary) + "\n", encoding="utf-8")

    print(f"\nГотово: извлечено TextAsset: {saved}, всего объектов: {len(objects_summary)}")
    print(f"Папка: {outdir}")
    print("Карта: index.json, objects_list.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
