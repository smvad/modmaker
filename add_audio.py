#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Вставка своего звука внутрь resources.assets + resources.resource (LED HEARTS).

Использование (только из корня игры):
    .venv\\Scripts\\python.exe modmaker\\add_audio.py --wav modmaker\\mod_demo_jingle.wav --name ch3_chime --dry-run
    .venv\\Scripts\\python.exe modmaker\\add_audio.py --wav modmaker\\mod_demo_jingle.wav --name ch3_chime
    .venv\\Scripts\\python.exe modmaker\\add_audio.py --wav voice.wav --name ch3_hello --kind voice

Что делает:
- Кодирует WAV (PCM 16-bit, 44100/48000 Гц, моно/стерео) в FSB5/PCM16
  (см. fsb5pcm.py: штатного кодировщика Vorbis/FSB5 нет, а PCM16 Unity
  отдаёт в FMOD как есть) и дописывает блоб в конец resources.resource
  (смещения в оригинале кратны 16 — инвариант сохраняется).
- Клонирует AudioClip под новым path_id: m_Resource -> {offset, size},
  m_CompressionFormat=0 (PCM), m_Length/каналы/частота из WAV.
- Добавляет `<kind>/<name>` -> AudioClip в ResourceManager.m_Container
  (globalgamemanagers). Без записи игра клип не найдёт.
- Ссылка из сценария: `"sfxClip": "ch3_chime:0.9"` (kind=sfx),
  `"musicClip"` / `"voiceClip"` — аналогично при kind=music/voice.

Повторный запуск с тем же --name --wav обновляет на месте (старый блоб
в .resource остаётся сиротой — это нормально).
Бэкапы resources.assets.bak / globalgamemanagers.bak / resources.resource.bak
создаются один раз.
"""
from __future__ import annotations

import argparse
import copy
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import atomic_write, backup_once, find_game_root, require_unitypy
from fsb5pcm import build_fsb5_pcm16, parse_fsb5_pcm16, read_wav_pcm16

BASE = pathlib.Path(__file__).resolve().parent
RES = "LED HEARTS_Data/resources.assets"
GGM = "LED HEARTS_Data/globalgamemanagers"
BANK = "LED HEARTS_Data/resources.resource"


def main() -> int:
    ap = argparse.ArgumentParser(description="Вшить WAV внутрь resources.resource")
    ap.add_argument("--wav", required=True)
    ap.add_argument("--name", required=True, help="короткое имя без префиксов (ch3_chime)")
    ap.add_argument("--kind", default="sfx", choices=["sfx", "music", "voice"])
    ap.add_argument("--donor", default="door_knock", help="клип-донор typetree")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()
    UnityPy = require_unitypy()

    game = find_game_root(BASE)
    assets, ggm, bank_p = game / RES, game / GGM, game / BANK
    wav = pathlib.Path(args.wav)
    if not wav.is_absolute():
        for cand in (pathlib.Path.cwd() / args.wav, BASE / pathlib.Path(args.wav).name,
                     game / args.wav):
            if cand.exists():
                wav = cand
                break
    if not wav.exists():
        print(f"Нет WAV: {wav}", file=sys.stderr)
        return 1
    short = args.name.strip().strip("/")
    if not short or any(c in short for c in "\\/:*?\"<>|"):
        print(f"Плохое имя: {short!r}", file=sys.stderr)
        return 1
    try:
        pcm, channels, rate, frames = read_wav_pcm16(wav)
    except ValueError as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        return 1
    blob = build_fsb5_pcm16(pcm, channels, rate, frames)
    ckey = f"{args.kind}/{short}".lower()

    env = UnityPy.load(str(assets))
    f = env.file
    donor = None
    for o in f.objects.values():
        if o.type.name != "AudioClip":
            continue
        try:
            if o.read().m_Name == args.donor:
                donor = o
                break
        except Exception:
            continue
    if donor is None:
        donor = next((o for o in f.objects.values() if o.type.name == "AudioClip"), None)
    if donor is None:
        print("В resources.assets нет AudioClip.", file=sys.stderr)
        return 1

    ggm_env = UnityPy.load(str(ggm))
    rm_obj = next((o for o in ggm_env.file.objects.values()
                   if o.type.name == "ResourceManager"), None)
    if rm_obj is None:
        print("Нет ResourceManager.", file=sys.stderr)
        return 1
    rm = rm_obj.parse_as_dict(check_read=False)
    clip_id = None
    for p, ptr in rm["m_Container"]:
        if p == ckey and ptr.get("m_FileID") == 4:
            o = f.objects.get(ptr["m_PathID"])
            if o is not None and o.type.name == "AudioClip":
                clip_id = o.path_id
                break
    fresh = clip_id is None
    if fresh:
        clip_id = max(f.objects.keys()) + 1
    bank = bank_p.read_bytes()
    assert len(bank) % 16 == 0, "resources.resource не выровнен — странно"

    def already_in_place() -> bool:
        if fresh:
            return False
        try:
            t = f.objects[clip_id].read()
            if t.m_Name != short:
                return False
            ro, rs = t.m_Resource.m_Offset, t.m_Resource.m_Size
            if rs != len(blob) or bank[ro:ro + rs] != blob:
                return False
            if not (t.m_Channels == channels and t.m_Frequency == rate
                    and abs(t.m_Length - frames / rate) < 1e-6
                    and t.m_CompressionFormat == 0):
                return False
        except Exception:
            return False
        ids = sorted(ptr["m_PathID"] for p, ptr in rm["m_Container"]
                     if p == ckey and ptr.get("m_FileID") == 4)
        return ids == [clip_id]

    if already_in_place():
        print(f"Всё уже на месте: {ckey!r} (clip {clip_id}) — запись не требуется.")
        return 0
    print(f"Клип {'новый' if fresh else 'обновление'}: path_id={clip_id}, "
          f"{ckey!r}, {channels}ch {rate}Гц {frames / rate:.2f}с, блоб {len(blob)} байт")

    if args.dry_run:
        print(f"Dry-run: +{len(blob)} байт в {BANK}, AudioClip {clip_id}, "
              f"1 запись в контейнер. Запись не выполнялась.")
        return 0

    offset = len(bank)

    if fresh:
        new_obj = copy.copy(donor)
        new_obj.path_id = clip_id
        new_obj.data = None
        f.objects[clip_id] = new_obj
    tree = f.objects[clip_id].parse_as_dict(check_read=False)
    tree["m_Name"] = short
    tree["m_Channels"] = channels
    tree["m_Frequency"] = rate
    tree["m_BitsPerSample"] = 16
    tree["m_Length"] = frames / rate
    tree["m_CompressionFormat"] = 0
    tree["m_LoadType"] = 0
    tree["m_PreloadAudioData"] = False
    tree["m_LoadInBackground"] = False
    tree["m_Resource"] = {"m_Source": "resources.resource",
                          "m_Offset": offset, "m_Size": len(blob)}
    f.objects[clip_id].save_typetree(tree)

    cont = [e for e in rm["m_Container"]
            if not (e[0] == ckey and e[1].get("m_FileID") == 4)]
    cont.append((ckey, {"m_FileID": 4, "m_PathID": clip_id}))
    rm["m_Container"] = cont
    rm_obj.save_typetree(rm)

    if not args.no_backup:
        for p in (assets, ggm, bank_p):
            backup_once(p)

    f.mark_changed()
    new_assets = f.save()
    env2 = UnityPy.load(new_assets)
    ok_a = False
    for o in env2.objects:
        if o.path_id == clip_id and o.type.name == "AudioClip":
            d = o.read()
            ok_a = (d.m_Name == short and d.m_Resource.m_Offset == offset
                    and d.m_Resource.m_Size == len(blob)
                    and abs(d.m_Length - frames / rate) < 1e-6)
    if not ok_a:
        print("ОШИБКА: клип не пережил пересборку.", file=sys.stderr)
        return 1
    ggm_env.file.mark_changed()
    new_ggm = ggm_env.file.save()
    env3 = UnityPy.load(new_ggm)
    ok_c = any(p == ckey and ptr.get("m_PathID") == clip_id
               for o in env3.objects if o.type.name == "ResourceManager"
               for p, ptr in o.parse_as_dict(check_read=False)["m_Container"])
    if not ok_c:
        print("ОШИБКА: контейнер не сохранился.", file=sys.stderr)
        return 1
    # блоб самопроверяем парсером
    back, _ch, _r, _fr = parse_fsb5_pcm16(blob)
    assert back == pcm
    print(f"Проверка: клип={ok_a}, контейнер={ok_c}, блоб самодостаточен")

    atomic_write(bank_p, bank + blob)
    atomic_write(assets, new_assets)
    atomic_write(ggm, new_ggm)
    field = {"sfx": "sfxClip", "music": "musicClip", "voice": "voiceClip"}[args.kind]
    print(f"Записано: +{len(blob)} в {BANK}, {assets}, {ggm}")
    print(f"Использование: \"{field}\": \"{short}:0.9\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
