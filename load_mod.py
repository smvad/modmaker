#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузка мода из ZIP: JSON глав + внешние ассеты (PNG/WAV).

Формат ZIP (регистр имён сохраняется, подпапки разрешены):
    chapter_01.json / chapter_02.json      — сценарий главы:
        либо чистый сценарий {"chapterId": "chapter_01", "nodes": [...]},
        либо Unity-обёртка {"m_Name": "chapter_01", "m_Script": "{...}"}
        (оба варианта понимает и repack_resources.py);
        имя файла тоже подходит: 101_chapter_01.json, chapter_01-fixed.json.
    dlc_*.png / dlc_*.jpg                  — фоны и спрайты
    dlc_*.wav                              — звуки (PCM 16-bit 44100 Гц)

Внешний загрузчик игры ищет файлы строго в корне игры (рядом с
LED HEARTS.exe) и только с префиксом ``dlc_`` — без префикса ассет
игрой игнорируется (см. INSTRUCTIONS.md). Скрипт копирует такие файлы
в корень игры и предупреждает о файлах без префикса.

Использование (только из корня игры):
    .venv\\Scripts\\python.exe modmaker\\load_mod.py mymod.zip
    .venv\\Scripts\\python.exe modmaker\\load_mod.py mymod.zip --dry-run
    .venv\\Scripts\\python.exe modmaker\\load_mod.py mymod.zip --no-backup

Проверки перед записью:
- JSON валиден, содержит chapterId/nodes/startingNodeId;
- startingNodeId существует, nodeId уникальны;
- nextNodeId/targetNodeId ссылаются на существующие узлы (иначе предупреждение);
- все backgroundImage/characterSprite/musicClip/sfxClip/voiceClip либо есть
  в resources.assets, либо приложены к зипу как dlc_* файлы, либо уже лежат
  в корне игры (иначе предупреждение, но запись всё равно выполняется).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys
import tempfile
import wave
import zipfile

BASE = pathlib.Path(__file__).resolve().parent
GAME = BASE
if not (GAME / "LED HEARTS_Data" / "resources.assets").exists():
    GAME = BASE.parent

CHAPTER_RE = re.compile(r"^(\d+)_.*")
IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
AUDIO_EXTS = {".wav"}
JSON_EXTS = {".json"}
# значения, которые не являются именами ассетов
SKIP_REFS = {"", "none", "stop"}

# поля строк, где лежат ссылки на ассеты
IMAGE_FIELDS = ("backgroundImage", "characterSprite")
AUDIO_FIELDS = ("musicClip", "sfxClip", "voiceClip")


def find_game_root(start: pathlib.Path) -> pathlib.Path:
    for d in (start, start.parent, pathlib.Path.cwd(),
              pathlib.Path.cwd().parent):
        if (d / "LED HEARTS_Data" / "resources.assets").exists():
            return d
    return start


def chapter_key_from_filename(name: str) -> str:
    """101_chapter_01.json -> chapter_01; chapter_01-fixed.json -> chapter_01."""
    stem = pathlib.Path(name).stem
    m = CHAPTER_RE.match(stem)
    if m:
        # отрезать числовой префикс path_id: "101_chapter_01" -> "chapter_01"
        stem = stem.split("_", 1)[1]
    short = stem.split("-")[0].split("_resources")[0]
    return short


def parse_chapter_file(text: str, fname: str) -> tuple[str, dict, str]:
    """Вернуть (target_name, scenario_dict, kind). kind: 'raw' | 'wrapper'.

    Raises ValueError с понятным текстом при любой проблеме.
    """
    try:
        outer = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"{fname}: не JSON ({e})")
    if isinstance(outer, dict) and isinstance(outer.get("m_Script"), str):
        target = str(outer.get("m_Name") or chapter_key_from_filename(fname))
        try:
            inner = json.loads(outer["m_Script"])
        except json.JSONDecodeError as e:
            raise ValueError(f"{fname}: m_Script не JSON ({e})")
        if not isinstance(inner, dict):
            raise ValueError(f"{fname}: m_Script не объект главы")
        return target, inner, "wrapper"
    if isinstance(outer, dict) and "nodes" in outer:
        target = str(outer.get("chapterId") or chapter_key_from_filename(fname))
        return target, outer, "raw"
    raise ValueError(f"{fname}: нет ни m_Script, ни chapterId/nodes")


def validate_chapter(scenario: dict) -> list[str]:
    """Список проблем (ошибки и предупреждения одной строкой)."""
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
        # load_chapter:chapter_02:node — команда перехода между главами, не узел
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
    """Вернуть (image_refs, audio_refs) — имена ассетов без пустых/none/stop."""
    images: set[str] = set()
    audios: set[str] = set()
    for n in scenario.get("nodes", []) or []:
        for line in n.get("lines", []) or []:
            if not isinstance(line, dict):
                continue
            for f in IMAGE_FIELDS:
                v = line.get(f, "")
                if isinstance(v, str) and v and v not in SKIP_REFS:
                    images.add(v)
            for f in AUDIO_FIELDS:
                v = clip_base(line.get(f, ""))
                if v:
                    audios.add(v)
    return images, audios


def check_wav(path: pathlib.Path) -> str:
    """Вернуть текст предупреждения или '' если формат корректный."""
    try:
        with wave.open(str(path), "rb") as w:
            if w.getcomptype() != "NONE" or w.getsampwidth() != 2:
                return f"{path.name}: нужен PCM 16-bit"
            if w.getframerate() != 44100:
                return f"{path.name}: частота {w.getframerate()} Гц, нужна 44100 Гц"
            if w.getnchannels() not in (1, 2):
                return f"{path.name}: каналов {w.getnchannels()}, нужно 1-2"
    except Exception as e:
        return f"{path.name}: не читается как WAV ({e})"
    return ""


def check_image(path: pathlib.Path) -> str:
    try:
        from PIL import Image
    except ImportError:
        return ""
    try:
        with Image.open(path) as im:
            im.verify()
    except Exception as e:
        return f"{path.name}: битый PNG/JPG ({e})"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Установить мод из ZIP (JSON глав + dlc PNG/WAV)")
    ap.add_argument("zip", help="путь к zip мода")
    ap.add_argument("--input", default="LED HEARTS_Data/resources.assets",
                    help="исходный resources.assets")
    ap.add_argument("--no-backup", action="store_true",
                    help="не делать resources.assets.bak")
    ap.add_argument("--dry-run", action="store_true",
                    help="только показать, что будет применено, без записи")
    args = ap.parse_args()

    game = find_game_root(BASE)
    zpath = pathlib.Path(args.zip)
    if not zpath.is_absolute():
        for cand in (pathlib.Path.cwd() / args.zip, BASE / args.zip, game / args.zip):
            if cand.exists():
                zpath = cand
                break
    if not zpath.exists() or not zipfile.is_zipfile(zpath):
        print(f"Не найден zip мода: {zpath}", file=sys.stderr)
        return 1

    inp = pathlib.Path(args.input)
    if not inp.is_absolute():
        inp = game / args.input
    if not inp.exists():
        print(f"Не найден файл: {inp}", file=sys.stderr)
        return 1

    try:
        import UnityPy  # noqa: F401
    except ImportError:
        print("Нет модуля UnityPy. Установите: pip install UnityPy", file=sys.stderr)
        return 1

    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="led_mod_"))
    try:
        with zipfile.ZipFile(zpath) as z:
            members = [m for m in z.namelist() if not m.endswith("/")]
            if not members:
                print(f"{zpath.name}: zip пустой", file=sys.stderr)
                return 1
            z.extractall(tmpdir)
    except zipfile.BadZipFile as e:
        print(f"{zpath.name}: битый zip ({e})", file=sys.stderr)
        return 1

    # --- разобрать содержимое ---
    chapters: dict[str, tuple[pathlib.Path, dict]] = {}
    externals: dict[str, pathlib.Path] = {}
    skipped: list[str] = []
    for p in sorted(tmpdir.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in JSON_EXTS:
            try:
                text = p.read_bytes().decode("utf-8-sig")
                target, scenario, _kind = parse_chapter_file(text, p.name)
            except ValueError as e:
                print(f"  ! пропуск: {e}", file=sys.stderr)
                continue
            if target in chapters:
                print(f"  ! {p.name}: глава {target!r} уже есть из "
                      f"{chapters[target][0].name} — беру последний")
            chapters[target] = (p, scenario)
        elif ext in IMAGE_EXTS or ext in AUDIO_EXTS:
            if not p.name.startswith("dlc_"):
                skipped.append(f"{p.name}: без префикса dlc_ игра его проигнорирует — пропуск")
                continue
            if p.name in externals:
                print(f"  ! {p.name}: дублируется в зипе — беру последний")
            externals[p.name] = p
        else:
            skipped.append(f"{p.name}: неизвестный тип — пропуск")

    if not chapters and not externals:
        print(f"{zpath.name}: нет ни JSON глав, ни dlc_* ассетов.", file=sys.stderr)
        for s in skipped:
            print(f"  ! {s}", file=sys.stderr)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return 1

    print(f"Мод: {zpath.name}")
    print(f"  глав: {len(chapters)} ({', '.join(sorted(chapters)) or '—'})")
    print(f"  внешних файлов: {len(externals)} ({', '.join(sorted(externals)) or '—'})")
    for s in skipped:
        print(f"  ! {s}")

    # --- валидация глав ---
    for target in sorted(chapters):
        _p, scenario = chapters[target]
        for prob in validate_chapter(scenario):
            print(f"  ! глава {target!r}: {prob}")

    # --- проверка внешних файлов ---
    for name in sorted(externals):
        p = externals[name]
        warn = check_wav(p) if p.suffix.lower() == ".wav" else check_image(p)
        if warn:
            print(f"  ! {warn}")

    # --- индекс игры ---
    import UnityPy
    print(f"Загрузка: {inp} ...")
    env = UnityPy.load(str(inp))
    text_assets: dict[str, int] = {}   # m_Name -> path_id
    textures: set[str] = set()
    sprites: set[str] = set()
    audios: set[str] = set()
    for obj in env.objects:
        t = obj.type.name
        try:
            d = obj.read()
        except Exception:
            continue
        nm = getattr(d, "m_Name", "")
        if not nm:
            continue
        if t == "TextAsset":
            text_assets[nm] = obj.path_id
        elif t == "Texture2D":
            textures.add(nm)
        elif t == "Sprite":
            sprites.add(nm)
        elif t == "AudioClip":
            audios.add(nm)

    # --- сопоставление глав ---
    unmatched = [t for t in chapters if t not in text_assets]
    for t in unmatched:
        print(f"  ! глава {t!r}: нет TextAsset с таким именем в игре "
              f"(есть: {', '.join(sorted(text_assets))}) — пропуск")

    # --- проверка ссылок на ассеты ---
    # предупреждаем только о НОВЫХ ссылках (которых не было в текущей главе
    # в игре): иначе перепаковка нетронутой главы шумела бы про NSFW-DLC
    # и отсутствующий cafe_noise, которые игре уже известны.
    zip_bases = {pathlib.Path(n).stem for n in externals}
    old_refs_cache: dict[str, tuple[set[str], set[str]]] = {}
    for target in sorted(chapters):
        if target not in text_assets:
            continue
        _p, scenario = chapters[target]
        images, clips = collect_refs(scenario)
        if target not in old_refs_cache:
            try:
                old_obj = env.file.objects.get(text_assets[target])
                old_data = json.loads(old_obj.read().m_Script)
                old_refs_cache[target] = collect_refs(old_data)
            except Exception:
                old_refs_cache[target] = (set(), set())
        old_images, old_clips = old_refs_cache[target]
        for ref in sorted(images - old_images):
            if "/" in ref:
                # путь в Resources (напр. milly/pose_a/happy): в resources.assets
                # таких имён нет, локально не проверить — считаем внутренним
                continue
            if ref in textures or ref in sprites or ref in zip_bases:
                continue
            if (game / (ref + ".png")).exists() or (game / (ref + ".jpg")).exists():
                continue
            print(f"  ! глава {target!r}: фон/спрайт {ref!r} не найден "
                  f"(ни в игре, ни в зипе, ни в корне игры)")
        for ref in sorted(clips - old_clips):
            if ref in audios or ref in zip_bases:
                continue
            if (game / (ref + ".wav")).exists():
                continue
            print(f"  ! глава {target!r}: звук {ref!r} не найден "
                  f"(ни в игре, ни в зипе, ни в корне игры)")

    matched = {t: v for t, v in chapters.items() if t in text_assets}
    if args.dry_run:
        print(f"\nDry-run: глав было бы заменено: {len(matched)}, "
              f"файлов скопировано в корень игры: {len(externals)}. "
              f"Запись не выполнялась.")
        shutil.rmtree(tmpdir, ignore_errors=True)
        return 0

    if not matched and not externals:
        print("Нечего применять.", file=sys.stderr)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return 1

    # --- применение глав ---
    changed = 0
    for target in sorted(matched):
        src, scenario = matched[target]
        path_id = text_assets[target]
        obj = env.file.objects.get(path_id)
        if obj is None:
            print(f"  ! глава {target!r}: path_id {path_id} не найден — пропуск")
            continue
        d = obj.read()
        new_text = json.dumps(scenario, ensure_ascii=False)
        old = d.m_Script
        old_raw = old if isinstance(old, bytes) else old.encode("utf-8")
        if old_raw.decode("utf-8", errors="replace") == new_text:
            print(f"  = {target!r} (path_id {path_id}, {src.name}): без изменений")
            continue
        print(f"  * {target!r} (path_id {path_id}, {src.name}): "
              f"{len(old_raw)} -> {len(new_text.encode('utf-8'))} байт")
        d.m_Script = new_text
        d.save()
        changed += 1

    if changed:
        if not args.no_backup:
            bak = inp.with_name(inp.name + ".bak")
            if not bak.exists():
                shutil.copy2(inp, bak)
                print(f"Бэкап: {bak}")
            else:
                print(f"Бэкап уже есть: {bak} (новый не создаю)")
        env.file.mark_changed()
        new_bytes = env.file.save()
        try:
            env2 = UnityPy.load(new_bytes)
            n = sum(1 for o in env2.objects if o.type.name == "TextAsset")
            print(f"Проверка: пересобранный файл читается, TextAsset: {n}")
        except Exception as e:
            print(f"ОШИБКА: пересобранный файл не читается: {e}", file=sys.stderr)
            shutil.rmtree(tmpdir, ignore_errors=True)
            return 1
        tmp = inp.with_name(inp.name + ".tmp")
        tmp.write_bytes(new_bytes)
        shutil.move(str(tmp), str(inp))
        print(f"Глав заменено: {changed}. Записано: {inp} ({len(new_bytes)} байт)")
    else:
        print("Главы без изменений — resources.assets не трогаю.")

    # --- копирование внешних файлов в корень игры ---
    copied = 0
    for name in sorted(externals):
        dst = game / name
        if dst.exists():
            try:
                if dst.read_bytes() == externals[name].read_bytes():
                    print(f"  = {name}: уже есть в корне игры, без изменений")
                    continue
            except OSError:
                pass
            print(f"  * {name}: перезаписываю в корне игры")
        else:
            print(f"  + {name}: копирую в корень игры")
        shutil.copy2(externals[name], dst)
        copied += 1

    shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"\nГотово: глав применено: {changed}, файлов в корне игры: {copied}.")
    print("Запустите LED HEARTS.exe для проверки.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
