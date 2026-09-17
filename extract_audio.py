#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Извлечение всех AudioClip игры в WAV (LED HEARTS).

Звук в игре лежит не в resources.assets, а в LED HEARTS_Data/resources.resource:
каждый AudioClip — отдельный FSB5-блоб (Vorbis) со смещением/размером из
m_Resource. UnityPy их не декодирует, поэтому скрипт:
  1. читает список клипов из resources.assets через UnityPy;
  2. пересобирает валидный OGG из FSB5-блоба (fsb5 + DLL из modmaker/tools);
  3. декодирует OGG в PCM WAV через системный ffmpeg (должен быть в PATH);
  4. проверяет длительность WAV против m_Length клипа.

Один клип (falling, кодер другой версии) таблицей fsb5 не покрывается:
для него скрипт пробует внешний vgmstream-cli (ищет в modmaker/tools
и в PATH; без него клип пропускается с подсказкой).

Использование (только из корня игры):
    .venv\\Scripts\\python.exe modmaker\\extract_audio.py
    .venv\\Scripts\\python.exe modmaker\\extract_audio.py --only classroom,crowd
    .venv\\Scripts\\python.exe modmaker\\extract_audio.py --outdir my_wavs --force

Зависимости: pip install -r modmaker\\requirements.txt (UnityPy, fsb5).
Результат (~hundreds MB в PCM) складывается в modmaker/extracted_audio/
и не коммитится (см. .gitignore).
"""
from __future__ import annotations

import argparse
import ctypes
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import wave

BASE = pathlib.Path(__file__).resolve().parent
GAME = BASE
if not (GAME / "LED HEARTS_Data" / "resources.assets").exists():
    GAME = BASE.parent
TOOLS = BASE / "tools"
DLL_NAMES = {"vorbis": "libvorbis-0.dll", "vorbisenc": "libvorbisenc-2.dll",
             "ogg": "libogg-0.dll"}


def ensure_vorbis_libs() -> None:
    """Подключить DLL для fsb5 до импорта fsb5.vorbis."""
    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(TOOLS))
    import fsb5.utils

    def _load(*names):
        for n in names:
            p = TOOLS / DLL_NAMES[n]
            if p.exists():
                return ctypes.CDLL(str(p))
        raise OSError("нет DLL для %r в %s" % (names, TOOLS))

    fsb5.utils.load_lib = _load


def safe_name(name: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in name) or "unnamed"


def decode_via_vgmstream(blob: bytes, wav_path: pathlib.Path) -> bool:
    """Фолбэк для клипов, чьи кодовые книги fsb5 не знает. True если вышло."""
    exe = shutil.which("vgmstream-cli") or shutil.which("vgmstream-cli.exe")
    if exe is None:
        for cand in (BASE / "tools" / "vgmstream-cli.exe", GAME / "tools" / "vgmstream-cli.exe"):
            if cand.exists():
                exe = str(cand)
                break
    if exe is None:
        return False
    with tempfile.TemporaryDirectory(prefix="led_fsb_") as tmp:
        fsb = pathlib.Path(tmp) / "clip.fsb"
        fsb.write_bytes(blob)
        r = subprocess.run([exe, "-o", str(wav_path), str(fsb)], capture_output=True)
        return r.returncode == 0 and wav_path.exists()


def find_game_root(start: pathlib.Path) -> pathlib.Path:
    for d in (start, start.parent, pathlib.Path.cwd(),
              pathlib.Path.cwd().parent):
        if (d / "LED HEARTS_Data" / "resources.assets").exists():
            return d
    return start


def main() -> int:
    ap = argparse.ArgumentParser(description="Извлечь AudioClip (FSB5/Vorbis) в WAV")
    ap.add_argument("--input", default="LED HEARTS_Data/resources.assets",
                    help="путь к resources.assets")
    ap.add_argument("--resource", default="LED HEARTS_Data/resources.resource",
                    help="путь к resources.resource (банк FSB5)")
    ap.add_argument("--outdir", default="extracted_audio",
                    help="куда складывать WAV")
    ap.add_argument("--only", default="",
                    help="только эти клипы через запятую (пусто = все)")
    ap.add_argument("--force", action="store_true",
                    help="перезаписывать существующие WAV")
    args = ap.parse_args()

    if not all((TOOLS / v).exists() for v in DLL_NAMES.values()):
        print(f"Нет DLL в {TOOLS} (нужны libogg/libvorbis/libvorbisenc)", file=sys.stderr)
        return 1
    if shutil.which("ffmpeg") is None:
        print("Не найден ffmpeg в PATH. Установите: winget install Gyan.FFmpeg", file=sys.stderr)
        return 1
    try:
        import UnityPy  # noqa: F401
    except ImportError:
        print("Нет модуля UnityPy. Установите: pip install -r modmaker\\requirements.txt",
              file=sys.stderr)
        return 1
    ensure_vorbis_libs()
    try:
        from fsb5 import FSB5, MetadataChunkType
        from fsb5.vorbis import rebuild
    except Exception as e:
        print(f"Не загрузился декодер fsb5: {e}", file=sys.stderr)
        return 1

    game = find_game_root(BASE)
    inp = game / args.input if not pathlib.Path(args.input).is_absolute() else pathlib.Path(args.input)
    res = game / args.resource if not pathlib.Path(args.resource).is_absolute() else pathlib.Path(args.resource)
    for p in (inp, res):
        if not p.exists():
            print(f"Не найден файл: {p}", file=sys.stderr)
            return 1
    outdir = pathlib.Path(args.outdir)
    if not outdir.is_absolute():
        outdir = BASE / outdir
    outdir.mkdir(parents=True, exist_ok=True)
    only = {x.strip() for x in args.only.split(",") if x.strip()} if args.only else set()

    import UnityPy
    print(f"Загрузка: {inp} ...")
    env = UnityPy.load(str(inp))
    bank = res.read_bytes()

    clips = []
    for obj in env.objects:
        if obj.type.name != "AudioClip":
            continue
        try:
            d = obj.read()
        except Exception as e:
            print(f"  ! path_id={obj.path_id}: не читается ({e})")
            continue
        if only and d.m_Name not in only:
            continue
        clips.append(d)
    print(f"Клипов к извлечению: {len(clips)} -> {outdir}")

    ok = skip = fail = 0
    for d in clips:
        name, off, size = d.m_Name, d.m_Resource.m_Offset, d.m_Resource.m_Size
        wav_path = outdir / f"{safe_name(name)}.wav"
        if wav_path.exists() and not args.force:
            skip += 1
            continue
        try:
            blob = bank[off:off + size]
            if blob[:4] != b"FSB5":
                raise ValueError("нет сигнатуры FSB5 по смещению %d" % off)
            try:
                samples = FSB5(blob).samples
                if len(samples) != 1 or MetadataChunkType.VORBISDATA not in samples[0].metadata:
                    raise ValueError("не Vorbis с одним сэмплом")
                ogg = bytes(rebuild(samples[0]))
            except ValueError as e:
                if "header info" not in str(e) or not decode_via_vgmstream(blob, wav_path):
                    if "header info" in str(e):
                        raise ValueError(
                            "%s (кодовые книги кодера неизвестны fsb5; "
                            "положите vgmstream-cli в modmaker/tools или в PATH)" % e)
                    raise
                print(f"  ~ {name}: декодирован через vgmstream-cli")
                ogg = None
            if ogg is not None:
                r = subprocess.run(
                    ["ffmpeg", "-y", "-v", "error", "-i", "-", "-c:a", "pcm_s16le",
                     "-ar", str(int(d.m_Frequency)), "-ac", str(int(d.m_Channels)), str(wav_path)],
                    input=ogg, capture_output=True)
                if r.returncode != 0:
                    raise ValueError("ffmpeg: %s" % r.stderr.decode("utf-8", "replace").strip())
            with wave.open(str(wav_path), "rb") as w:
                dur = w.getnframes() / w.getframerate()
            expect = float(d.m_Length)
            if abs(dur - expect) > max(0.1, 0.01 * expect):
                print(f"  ! {name}: длительность {dur:.2f}с != m_Length {expect:.2f}с")
            ok += 1
        except Exception as e:
            fail += 1
            print(f"  ! {name}: {e}")
    print(f"\nГотово: извлечено {ok}, пропущено (уже есть) {skip}, ошибок {fail}. Папка: {outdir}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
