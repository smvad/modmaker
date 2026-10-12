#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Запись сейва перед переходом в главу 3 (LED HEARTS).

Сейвы игры = Unity PlayerPrefs в реестре HKCU\\Software\\fugas_kitsune\\LED HEARTS:
- vn_save_slot_<N> — JSON {"chapterId","nodeId","lineIndex","dateString",
  "previewText","varKeys","varValues"} (UTF-8 + NUL, тип REG_BINARY).
- save_chapter / save_node / save_line — точка "Продолжить" (автосейв).

Использование (только из корня игры):
    .venv\\Scripts\\python.exe modmaker\\write_save.py --slot 0 --dry-run
    .venv\\Scripts\\python.exe modmaker\\write_save.py --slot 0
    .venv\\Scripts\\python.exe modmaker\\write_save.py --slot 0 --line 5 --no-autosave

По умолчанию: chapter_02 / scene2_vio_milly_forgot / line 0 (начало узла,
после которого идёт load_chapter:chapter_03), переменные копируются из
самого свежего слота chapter_02. Перед записью делается бэкап ветки
реестра (reg export ..._saves_backup.reg рядом со скриптом).
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import subprocess
import sys
import winreg

BASE = pathlib.Path(__file__).resolve().parent

sys.path.insert(0, str(BASE))
from common import find_game_root, require_unitypy

KEY = r"Software\fugas_kitsune\LED HEARTS"
RES = "LED HEARTS_Data/resources.assets"

CH, NODE = "chapter_02", "scene2_vio_milly_forgot"


class Saves:
    """Снимок ветки PlayerPrefs: имя значения PlayerPrefs — <name>_h<hash>."""

    def __init__(self) -> None:
        self.values: dict[str, tuple] = {}
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
            i = 0
            try:
                while True:
                    n, v, t = winreg.EnumValue(k, i)
                    self.values[n] = (v, t)
                    i += 1
            except OSError:
                pass

    def resolve(self, name: str) -> str | None:
        found = [n for n in self.values if n == name or n.startswith(name + "_h")]
        if len(found) > 1:
            raise ValueError(f"several keys for {name!r}")
        return found[0] if found else None

    def get_bytes(self, name: str) -> bytes:
        key = self.resolve(name)
        v, t = self.values[key]
        assert isinstance(v, bytes), (name, t)
        return v

    def get_dword(self, name: str) -> int:
        key = self.resolve(name)
        return int(self.values[key][0])

    def set_bytes(self, name: str, data: bytes) -> None:
        key = self.resolve(name)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, key, 0, winreg.REG_BINARY, data)
        self.values[key] = (data, winreg.REG_BINARY)

    def set_dword(self, name: str, val: int) -> None:
        key = self.resolve(name)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, key, 0, winreg.REG_DWORD, val)
        self.values[key] = (val, winreg.REG_DWORD)


def z(s: str) -> bytes:
    return s.encode("utf-8") + b"\x00"


def main() -> int:
    ap = argparse.ArgumentParser(description="Сейв перед главой 3")
    ap.add_argument("--slot", type=int, required=True, help="слот 0-9 (перезаписывается!)")
    ap.add_argument("--line", type=int, default=0, help="lineIndex внутри узла")
    ap.add_argument("--no-autosave", action="store_true",
                    help="не трогать точку Продолжить (save_chapter/save_node/save_line)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not 0 <= args.slot <= 9:
        print("Слот 0-9.", file=sys.stderr)
        return 1

    game = find_game_root(BASE)
    UnityPy = require_unitypy()
    env = UnityPy.load(str(game / RES))
    ch2 = next(o for o in env.objects
               if o.type.name == "TextAsset" and o.read().m_Name == "chapter_02")
    data = json.loads(ch2.read().m_Script)
    nodes = [n for n in data["nodes"] if n.get("nodeId") == NODE]
    if not nodes:
        print(f"Нет узла {NODE!r} в chapter_02.", file=sys.stderr)
        return 1
    lines = nodes[0].get("lines", [])
    if not 0 <= args.line < len(lines):
        print(f"Строка 0-{len(lines)-1}, дано {args.line}.", file=sys.stderr)
        return 1

    # переменные: из самого свежего слота chapter_02 (один снимок реестра)
    saves = Saves()
    best, best_date = None, ""
    for s in range(10):
        try:
            raw = saves.get_bytes(f"vn_save_slot_{s}").rstrip(b"\x00").decode("utf-8")
            d = json.loads(raw)
        except Exception:
            continue
        if d.get("chapterId") == "chapter_02" and d.get("dateString", "") >= best_date:
            best, best_date = d, d.get("dateString", "")
    if best is None:
        print("Нет ни одного слота chapter_02 для образца переменных.", file=sys.stderr)
        return 1
    var_keys, var_vals = best["varKeys"], best["varValues"]

    text = lines[args.line].get("text", "")
    save = {"chapterId": CH, "nodeId": NODE, "lineIndex": args.line,
            "dateString": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "previewText": text, "varKeys": var_keys, "varValues": var_vals}
    blob = z(json.dumps(save, ensure_ascii=False))
    try:
        slot_key = saves.resolve(f"vn_save_slot_{args.slot}")
    except ValueError as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        return 1
    if slot_key is None:
        print(f"Нет ключа слота {args.slot}.", file=sys.stderr)
        return 1
    old_slot = saves.get_bytes(slot_key).rstrip(b"\x00").decode("utf-8", "replace")
    try:
        old_d = json.loads(old_slot)
        old_desc = f"{old_d.get('chapterId')}/{old_d.get('nodeId')}:{old_d.get('lineIndex')}"
    except Exception:
        old_desc = old_slot[:80]

    print(f"Слот {args.slot}: {old_desc} -> {CH}/{NODE}:{args.line}")
    print(f"Переменных: {len(var_keys)}, образец из слота ({best_date}).")
    print(f"Превью: {text[:120]}")
    if not args.no_autosave:
        cur_ch = saves.get_bytes("save_chapter").rstrip(b"\x00").decode()
        cur_nd = saves.get_bytes("save_node").rstrip(b"\x00").decode()
        print(f"Продолжить: {cur_ch}/{cur_nd}:{saves.get_dword('save_line')} "
              f"-> {CH}/{NODE}:{args.line}")

    if args.dry_run:
        print("Dry-run: реестр не тронут.")
        return 0

    bak = BASE / "led_saves_backup.reg"
    r = subprocess.run(["reg", "export", "HKCU\\" + KEY, str(bak), "/y"],
                       capture_output=True, text=True)
    if r.returncode != 0 or not bak.exists():
        print(f"ОШИБКА: не вышло сбэкапить реестр: {r.stderr.strip()}", file=sys.stderr)
        return 1
    print(f"Бэкап реестра: {bak}")

    saves.set_bytes(slot_key, blob)
    if not args.no_autosave:
        saves.set_bytes("save_chapter", z(CH))
        saves.set_bytes("save_node", z(NODE))
        saves.set_dword("save_line", args.line)

    saves = Saves()  # свежий снимок для проверки
    chk = json.loads(saves.get_bytes(slot_key).rstrip(b"\x00").decode("utf-8"))
    ok = chk["chapterId"] == CH and chk["nodeId"] == NODE and chk["lineIndex"] == args.line
    print(f"Проверка: слот={ok}", end="")
    if not args.no_autosave:
        ok2 = (saves.get_bytes("save_chapter").rstrip(b"\x00").decode() == CH
               and saves.get_bytes("save_node").rstrip(b"\x00").decode() == NODE
               and saves.get_dword("save_line") == args.line)
        print(f", продолжить={ok2}", end="")
        ok = ok and ok2
    print()
    if not ok:
        print("ОШИБКА: проверка не сошлась.", file=sys.stderr)
        return 1
    print("Готово: загрузите слот (или Продолжить) — после узла откроется глава 3.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
