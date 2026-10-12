#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Вставка новой главы (TextAsset) внутрь resources.assets (LED HEARTS).

Использование (только из корня игры):
    .venv\\Scripts\\python.exe modmaker\\add_chapter.py --dry-run
    .venv\\Scripts\\python.exe modmaker\\add_chapter.py
    .venv\\Scripts\\python.exe modmaker\\add_chapter.py --scenario my_ch3.json --link-from chapter_02:scene2_vio_stay

Что делает:
- Вставляет сценарий как новый TextAsset (клон typetree существующей главы,
  данные хранятся инлайн — resources.assets.resS/.resource не затрагиваются).
- Добавляет `dialoguedata/<chapter_id>` -> {FileID 4, path_id} в
  ResourceManager.m_Container внутри globalgamemanagers. Без этой записи
  Resources.Load главу не найдёт (проверено: chapters резолвятся только
  через контейнер).
- Патчит узел связки (по умолчанию конец chapter_02 `scene2_vio_milly_forgot`):
  nextNodeId = `load_chapter:<new_id>:<startingNodeId>` — тот же механизм,
  которым chapter_01 переходит в chapter_02.
- Проверяет ссылки главы на фоны/спрайты/звуки (предупреждения, не ошибки).

Повторный запуск обновляет главу на месте (идемпотентно).
Удаление: восстановить оба .bak вручную (скрипта --remove нет сознательно —
слишком легко снести чужой контент глав).

Бэкапы resources.assets.bak / globalgamemanagers.bak создаются один раз.
"""
from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import (
    atomic_write,
    backup_once,
    collect_refs,
    find_game_root,
    load_scenario,
    require_unitypy,
    validate_chapter as validate,
)

BASE = pathlib.Path(__file__).resolve().parent
RES = "LED HEARTS_Data/resources.assets"
GGM = "LED HEARTS_Data/globalgamemanagers"


def main() -> int:
    ap = argparse.ArgumentParser(description="Вставить новую главу в resources.assets")
    ap.add_argument("--scenario", default="modmaker/chapter_03.json")
    ap.add_argument("--chapter-id", default="",
                    help="переопределить chapterId (по умолчанию из сценария)")
    ap.add_argument("--link-from", default="chapter_02:scene2_vio_milly_forgot",
                    help="глава:узел, чей nextNodeId вести в новую главу (пусто = не связывать)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()
    UnityPy = require_unitypy()

    game = find_game_root(BASE)
    assets, ggm = game / RES, game / GGM
    scen_path = pathlib.Path(args.scenario)
    if not scen_path.is_absolute():
        for cand in (pathlib.Path.cwd() / args.scenario, BASE / pathlib.Path(args.scenario).name,
                     game / args.scenario):
            if cand.exists():
                scen_path = cand
                break
    if not scen_path.exists():
        print(f"Нет сценария: {scen_path}", file=sys.stderr)
        return 1
    try:
        scenario = load_scenario(scen_path)
    except ValueError as e:
        print(f"ОШИБКА: {e}", file=sys.stderr)
        return 1
    if args.chapter_id:
        scenario["chapterId"] = args.chapter_id
    cid = scenario.get("chapterId", "")
    if not cid:
        print("ОШИБКА: пустой chapterId.", file=sys.stderr)
        return 1
    for prob in validate(scenario):
        print(f"  ! глава {cid!r}: {prob}")

    env = UnityPy.load(str(assets))
    f = env.file
    text_ids: dict[str, int] = {}
    for o in f.objects.values():
        if o.type.name != "TextAsset":
            continue
        try:
            text_ids[o.read().m_Name] = o.path_id
        except Exception:
            continue
    if cid in text_ids and cid not in ("chapter_01", "chapter_02"):
        ch_id = text_ids[cid]
        is_new = False
    else:
        if cid in text_ids:
            print(f"ОШИБКА: {cid!r} — штатная глава, перезаписывать её нельзя "
                  f"(только repack/load_mod).", file=sys.stderr)
            return 1
        donor = f.objects.get(text_ids.get("chapter_02", 103))
        ch_id = max(f.objects.keys()) + 1
        is_new = True
        print(f"Новый TextAsset: path_id={ch_id} (донор typetree: chapter_02)")

    # проверка ссылок: что есть в контейнере игры
    ggm_env = UnityPy.load(str(ggm))
    rm_obj = next((o for o in ggm_env.file.objects.values() if o.type.name == "ResourceManager"), None)
    if rm_obj is None:
        print("Нет ResourceManager.", file=sys.stderr)
        return 1
    rm = rm_obj.parse_as_dict(check_read=False)
    have_paths = {p for p, _ptr in rm["m_Container"]}
    images, clips = collect_refs(scenario)
    for ref in sorted(images):
        if "/" in ref:
            cand = f"characters/{ref}".lower()
            alt = f"backgrounds/{ref}".lower()
            if cand not in have_paths and alt not in have_paths:
                print(f"  ! фон/спрайт {ref!r}: нет ни characters/, ни backgrounds/ в контейнере")
        else:
            if f"backgrounds/{ref}".lower() not in have_paths:
                print(f"  ! фон {ref!r}: нет backgrounds/ в контейнере (или это dlc_*)")
    for ref in sorted(clips):
        low = ref.lower()
        if not any(p.split("/")[-1] == low for p in have_paths):
            print(f"  ! звук {ref!r}: нет в контейнере (или это dlc_*)")

    # связка из старой главы
    link = args.link_from.strip()
    link_patch = None
    if link:
        try:
            lchap, lnode = link.split(":", 1)
        except ValueError:
            print(f"ОШИБКА: --link-from формата глава:узел, дано {link!r}.", file=sys.stderr)
            return 1
        if lchap not in text_ids:
            print(f"ОШИБКА: главы {lchap!r} нет в resources.assets.", file=sys.stderr)
            return 1
        ldata = json.loads(f.objects[text_ids[lchap]].read().m_Script)
        lns = [n for n in ldata["nodes"] if n.get("nodeId") == lnode]
        if not lns:
            print(f"ОШИБКА: узла {lnode!r} нет в {lchap!r}.", file=sys.stderr)
            return 1
        target = f"load_chapter:{cid}:{scenario['startingNodeId']}"
        if lns[0].get("nextNodeId") != target:
            link_patch = (lchap, text_ids[lchap], ldata, lnode, lns[0].get("nextNodeId", ""), target)
            print(f"Связка: {lchap}:{lnode} {link_patch[4]!r} -> {target!r}")
        else:
            print(f"Связка уже на месте: {lchap}:{lnode} -> {target!r}")

    ckey = f"dialoguedata/{cid}".lower()
    cont_has = any(p == ckey and ptr.get("m_FileID") == 4 and ptr.get("m_PathID") == ch_id
                   for p, ptr in rm["m_Container"])
    new_text = json.dumps(scenario, ensure_ascii=False)
    if not is_new:
        old_raw = f.objects[ch_id].read().m_Script
        old_raw = old_raw if isinstance(old_raw, bytes) else old_raw.encode("utf-8")
        same_text = old_raw.decode("utf-8", errors="replace") == new_text
    else:
        same_text = False

    if args.dry_run:
        print(f"Dry-run: TextAsset {cid!r} path_id={ch_id} "
              f"({'без изменений' if same_text else str(len(new_text.encode())) + ' байт'}), "
              f"контейнер {'есть' if cont_has else 'добавить'}, "
              f"связка {'есть/не нужна' if not link_patch else 'патч'}. Запись не выполнялась.")
        return 0

    if not is_new and same_text and cont_has and not link_patch:
        print("Всё уже на месте — запись не требуется.")
        return 0

    # --- TextAsset ---
    if is_new:
        new_obj = copy.copy(donor)
        new_obj.path_id = ch_id
        new_obj.data = None
        f.objects[ch_id] = new_obj
    ch_obj = f.objects[ch_id]
    ch = ch_obj.read()
    ch.m_Name = cid
    ch.m_Script = new_text
    ch.save()
    print(f"TextAsset {cid!r} (path_id {ch_id}): {len(new_text.encode())} байт")

    # --- связка ---
    if link_patch:
        lchap, lpid, ldata, lnode, _old, target = link_patch
        for n in ldata["nodes"]:
            if n.get("nodeId") == lnode:
                n["nextNodeId"] = target
        lo = f.objects[lpid].read()
        lo.m_Script = json.dumps(ldata, ensure_ascii=False)
        lo.save()
        print(f"Пропатчена связка {lchap}:{lnode}")

    # --- контейнер ---
    if not cont_has:
        cont = [e for e in rm["m_Container"]
                if not (e[0] == ckey and e[1].get("m_FileID") == 4)]
        cont.append((ckey, {"m_FileID": 4, "m_PathID": ch_id}))
        rm["m_Container"] = cont
        rm_obj.save_typetree(rm)
        print(f"Контейнер: + {ckey!r} -> {{4, {ch_id}}}")
    else:
        print("Контейнер уже содержит запись.")

    if not args.no_backup:
        for p in (assets, ggm):
            backup_once(p)

    f.mark_changed()
    new_assets = f.save()
    env2 = UnityPy.load(new_assets)
    ok_ch = any(o.type.name == "TextAsset" and o.path_id == ch_id
                and o.read().m_Name == cid for o in env2.objects)
    if not ok_ch:
        print("ОШИБКА: глава не пережила пересборку.", file=sys.stderr)
        return 1
    ggm_env.file.mark_changed()
    new_ggm = ggm_env.file.save()
    env3 = UnityPy.load(new_ggm)
    ok_c = any(p == ckey for o in env3.objects
               if o.type.name == "ResourceManager"
               for p, _ptr in o.parse_as_dict(check_read=False)["m_Container"])
    if not ok_c:
        print("ОШИБКА: контейнер не сохранился.", file=sys.stderr)
        return 1
    print(f"Проверка: глава={ok_ch}, контейнер={ok_c}")

    atomic_write(assets, new_assets)
    atomic_write(ggm, new_ggm)
    print(f"Записано: {assets} ({len(new_assets)}), {ggm} ({len(new_ggm)})")
    print("Вход в главу: конец chapter_02" +
          (f" ({link})" if link else " (без связки — только через load_chapter вручную)") +
          f" -> load_chapter:{cid}:{scenario['startingNodeId']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
