#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Вставка своей текстуры+спрайта внутрь resources.assets (LED HEARTS).

Использование (только из корня игры):
    .venv\\Scripts\\python.exe modmaker\\add_texture.py --png modmaker\\mod_start_bg.png --name ch3_room --dry-run
    .venv\\Scripts\\python.exe modmaker\\add_texture.py --png modmaker\\mod_start_bg.png --name ch3_room
    .venv\\Scripts\\python.exe modmaker\\add_texture.py --png hero.png --name milly/pose_a/ch3_hero --kind characters

Что делает:
- Клонирует пару-донора Texture2D+Sprite (по умолчанию cafe: path_id 10/494,
  1919x1080 RGB24) под новыми path_id (max+1, max+2).
- Картинка ресайзится строго в размер донора: вся геометрия спрайта
  (m_Rect, m_VertexData, uvTransform) остаётся валидной без пересчёта.
- Текстура пишется инлайн (UnityPy set_image зануляет m_StreamData):
  resources.assets.resS трогать не нужно.
- В globalgamemanagers/ResourceManager.m_Container добавляются две записи:
  `<kind>/<name>` -> Texture2D и `<kind>/<name>` -> Sprite
  (имена в контейнере строчные; Resources.Load ищет именно там).
  Без записей в контейнере игра новый ассет не найдёт.
- Ссылка из сценария: фон `"backgroundImage": "ch3_room"`,
  спрайт `"characterSprite": "milly/pose_a/ch3_hero"`.

Ограничения:
- Аудио этим скриптом не вставляется (FSB5 в resources.resource кодировать
  нечем): кастомный звук — только внешним dlc_*.wav.
- Повторный запуск с тем же --name обновляет картинки на месте (идемпотентно).

Бэкапы resources.assets.bak / globalgamemanagers.bak создаются один раз.
"""
from __future__ import annotations

import argparse
import copy
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import atomic_write, backup_once, find_game_root, require_unitypy

BASE = pathlib.Path(__file__).resolve().parent
RES = "LED HEARTS_Data/resources.assets"
GGM = "LED HEARTS_Data/globalgamemanagers"


def main() -> int:
    ap = argparse.ArgumentParser(description="Вставить PNG внутрь resources.assets")
    ap.add_argument("--png", required=True, help="исходный PNG")
    ap.add_argument("--name", required=True,
                    help="короткое имя (ch3_room; для персонажа milly/pose_a/ch3_hero)")
    ap.add_argument("--kind", default="backgrounds",
                    choices=["backgrounds", "characters"],
                    help="префикс пути в контейнере ресурсов")
    ap.add_argument("--donor-tex", type=int, default=10,
                    help="path_id текстуры-донора (по умолчанию 10 = cafe 1919x1080)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()
    UnityPy = require_unitypy()
    try:
        from PIL import Image
    except ImportError:
        print("Нет модуля Pillow.", file=sys.stderr)
        return 1

    game = find_game_root(BASE)
    assets = game / RES
    ggm = game / GGM
    png = pathlib.Path(args.png)
    if not png.is_absolute():
        for cand in (pathlib.Path.cwd() / args.png, BASE / pathlib.Path(args.png).name,
                     game / args.png):
            if cand.exists():
                png = cand
                break
    if not png.exists():
        print(f"Нет PNG: {png}", file=sys.stderr)
        return 1
    short = args.name.strip().strip("/")
    if not short or any(c in short for c in "\\:*?\"<>|"):
        print(f"Плохое имя: {short!r}", file=sys.stderr)
        return 1
    ckey = f"{args.kind}/{short}".lower()
    leaf = short.split("/")[-1]
    tex_name, spr_name = leaf, leaf + "_0"

    env = UnityPy.load(str(assets))
    f = env.file
    donor = f.objects.get(args.donor_tex)
    if donor is None or donor.type.name != "Texture2D":
        print(f"Донор {args.donor_tex} не Texture2D.", file=sys.stderr)
        return 1
    dt = donor.read()
    # спрайт донора: чей m_RD.texture указывает на донора
    donor_spr = None
    for o in f.objects.values():
        if o.type.name != "Sprite":
            continue
        try:
            if o.read().m_RD.texture.m_PathID == args.donor_tex:
                donor_spr = o
                break
        except Exception:
            continue
    if donor_spr is None:
        print(f"Нет спрайта на текстуру {args.donor_tex}.", file=sys.stderr)
        return 1
    ds = donor_spr.read()
    print(f"Донор: tex {args.donor_tex} {dt.m_Name!r} {dt.m_Width}x{dt.m_Height} "
          f"+ spr {donor_spr.path_id} {ds.m_Name!r}")

    # существующая пара с таким именем?
    ggm_env = UnityPy.load(str(ggm))
    rm_obj = next((o for o in ggm_env.file.objects.values() if o.type.name == "ResourceManager"), None)
    if rm_obj is None:
        print("Нет ResourceManager в globalgamemanagers.", file=sys.stderr)
        return 1
    rm = rm_obj.parse_as_dict(check_read=False)
    have = [(p, ptr) for p, ptr in rm["m_Container"] if p == ckey]
    tex_id = spr_id = None
    for _p, ptr in have:
        o = f.objects.get(ptr["m_PathID"])
        if o is not None and ptr["m_FileID"] == 4:
            if o.type.name == "Texture2D":
                tex_id = o.path_id
            elif o.type.name == "Sprite":
                spr_id = o.path_id
    fresh = tex_id is None or spr_id is None
    if tex_id is None:
        tex_id = max(f.objects.keys()) + 1
    if spr_id is None:
        spr_id = max(max(f.objects.keys()), tex_id) + 1
    print(f"Пара {'новая' if fresh else 'обновление'}: tex path_id={tex_id}, spr path_id={spr_id}")
    print(f"Ключ контейнера: {ckey!r}")

    img = Image.open(png).convert("RGB")
    if img.size != (dt.m_Width, dt.m_Height):
        print(f"Ресайз {img.size} -> {(dt.m_Width, dt.m_Height)} (размер донора обязателен).")
        img = img.resize((dt.m_Width, dt.m_Height), Image.Resampling.BICUBIC)

    def already_in_place() -> bool:
        if fresh:
            return False
        try:
            from PIL import ImageOps
            t0 = f.objects[tex_id].read()
            raw = t0.get_image_data()
            # UnityPy хранит строки перевёрнутыми (Unity bottom-up)
            if bytes(raw) != ImageOps.flip(img).tobytes():
                return False
            s0 = f.objects[spr_id].parse_as_dict(check_read=False)
            if s0.get("m_Name") != spr_name:
                return False
            if (s0.get("m_RD", {}).get("texture", {}).get("m_PathID") != tex_id):
                return False
        except Exception:
            return False
        ids = sorted(ptr["m_PathID"] for p, ptr in rm["m_Container"]
                     if p == ckey and ptr.get("m_FileID") == 4)
        return ids == sorted([tex_id, spr_id])

    if already_in_place():
        print(f"Всё уже на месте: {ckey!r} (tex {tex_id}, spr {spr_id}) — запись не требуется.")
        return 0

    if args.dry_run:
        print(f"Dry-run: tex {tex_id} {tex_name!r} RGB24 {img.size} "
              f"~{img.size[0]*img.size[1]*3} байт инлайн; spr {spr_id} {spr_name!r}; "
              f"записей в контейнер: 2. Запись не выполнялась.")
        return 0

    # --- текстура ---
    if fresh or f.objects.get(tex_id) is None:
        new_tex = copy.copy(donor)
        new_tex.path_id = tex_id
        new_tex.data = None
    else:
        new_tex = f.objects[tex_id]
    t = new_tex.read()
    t.m_Name = tex_name
    t.image = img  # инлайн RGB, m_StreamData зануляется
    t.save()
    f.objects[tex_id] = new_tex

    # --- спрайт (клон геометрии донора) ---
    if fresh or f.objects.get(spr_id) is None:
        new_spr = copy.copy(donor_spr)
        new_spr.path_id = spr_id
        new_spr.data = None
    else:
        new_spr = f.objects[spr_id]
    tree = new_spr.parse_as_dict(check_read=False)
    tree["m_Name"] = spr_name
    tree["m_RD"]["texture"] = {"m_FileID": 0, "m_PathID": tex_id}
    rnd = random.Random(f"{ckey}:{tex_id}")
    tree["m_RenderDataKey"] = (
        {"data[0]": rnd.getrandbits(32), "data[1]": rnd.getrandbits(32),
         "data[2]": rnd.getrandbits(32), "data[3]": rnd.getrandbits(32)},
        rnd.getrandbits(63),
    )
    new_spr.save_typetree(tree)
    f.objects[spr_id] = new_spr

    # --- контейнер ---
    cont = rm["m_Container"]
    cont = [e for e in cont
            if not (e[0] == ckey and e[1].get("m_FileID") == 4
                    and e[1].get("m_PathID") in (tex_id, spr_id))]
    cont.append((ckey, {"m_FileID": 4, "m_PathID": tex_id}))
    cont.append((ckey, {"m_FileID": 4, "m_PathID": spr_id}))
    rm["m_Container"] = cont
    rm_obj.save_typetree(rm)

    if not args.no_backup:
        for p in (assets, ggm):
            backup_once(p)

    f.mark_changed()
    new_assets = f.save()
    env2 = UnityPy.load(new_assets)
    ok_t = ok_s = False
    for o in env2.objects:
        if o.path_id == tex_id and o.type.name == "Texture2D":
            ok_t = o.read().m_Name == tex_name
        if o.path_id == spr_id and o.type.name == "Sprite":
            dd = o.read()
            ok_s = dd.m_Name == spr_name and dd.m_RD.texture.m_PathID == tex_id
    if not (ok_t and ok_s):
        print("ОШИБКА: пересборка не содержит пару.", file=sys.stderr)
        return 1
    print(f"Проверка assets: tex={ok_t}, spr={ok_s}, размер {len(new_assets)}")

    ggm_env.file.mark_changed()
    new_ggm = ggm_env.file.save()
    env3 = UnityPy.load(new_ggm)
    ok_c = False
    for o in env3.objects:
        if o.type.name == "ResourceManager":
            cc = o.parse_as_dict(check_read=False)["m_Container"]
            ids = sorted(ptr["m_PathID"] for p, ptr in cc if p == ckey)
            ok_c = ids == sorted([tex_id, spr_id])
    if not ok_c:
        print("ОШИБКА: контейнер не сохранился.", file=sys.stderr)
        return 1
    print(f"Проверка globalgamemanagers: контейнер {ckey!r} -> [{tex_id}, {spr_id}]")

    atomic_write(assets, new_assets)
    atomic_write(ggm, new_ggm)
    print(f"Записано: {assets} ({len(new_assets)}), {ggm} ({len(new_ggm)})")
    print(f"Использование: \"backgroundImage\": \"{short}\"" if args.kind == "backgrounds"
          else f"Использование: \"characterSprite\": \"{short}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
