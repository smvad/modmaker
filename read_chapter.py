#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Конвертер chapter_01-resources.assets-61.json в читаемый вид.

Читает Unity-JSON (outer: m_Name/m_Script, где m_Script — строка с inner JSON)
и выводит человекочитаемый диалог: узлы, реплики, выборы, сцены.

Использование:
    python read_chapter.py
    python read_chapter.py --lang ru
    python read_chapter.py --lang both --format md
    python read_chapter.py --input chapter_01-resources.assets-61.json --output chapter_01-readable.txt
"""
import argparse
import json
import pathlib
import sys


def load_chapter(input_path: pathlib.Path) -> dict:
    raw_text = input_path.read_text(encoding="utf-8-sig")
    outer = json.loads(raw_text)
    # Обычный случай: Unity-экспорт, сценарий лежит строкой в m_Script
    if isinstance(outer, dict) and "m_Script" in outer:
        inner = json.loads(outer["m_Script"])
        return inner
    # Уже распакованный сценарий напрямую
    return outer


def pick(a_ru: str, a_en: str, lang: str) -> str:
    a_ru = (a_ru or "").strip()
    a_en = (a_en or "").strip()
    if lang == "ru":
        return a_ru or a_en
    if lang == "en":
        return a_en or a_ru
    # both
    if a_ru and a_en and a_ru != a_en:
        return f"{a_ru}\n    EN: {a_en}"
    return a_ru or a_en


def format_line(line: dict, idx: int, lang: str) -> list[str]:
    out: list[str] = []
    speaker = pick(line.get("characterName", ""), line.get("characterName_en", ""), lang)
    text = pick(line.get("text", ""), line.get("text_en", ""), lang)
    if not speaker:
        speaker = "(описание)"
    out.append(f"  [{idx}] {speaker}:")
    out.append(f"    {text}" if text else "    <пусто>")

    # Сцена / медиа — показываем только непустые, чтобы не шуметь
    meta = []
    for key, label in (
        ("characterSprite", "спрайт"),
        ("backgroundImage", "фон"),
        ("characterPosition", "позиция"),
        ("emotion", "эмоция"),
        ("voiceClip", "войс"),
        ("musicClip", "музыка"),
        ("sfxClip", "sfx"),
        ("requiredVariables", "условие"),
    ):
        v = line.get(key, "")
        if v not in ("", None, -1, []):
            if key == "overlayAlpha" or v == -1:
                continue
            meta.append(f"{label}={v}")
    if line.get("overlayAlpha", -1) != -1:
        meta.append(f"overlay={line.get('overlayAlpha')}")
    if meta:
        out.append("    {" + "; ".join(meta) + "}")

    for c in line.get("choices", []) or []:
        ct = pick(c.get("choiceText", ""), c.get("choiceText_en", ""), lang)
        tgt = c.get("targetNodeId", "")
        out.append(f"    -> выбор: \"{ct}\" => [{tgt}]")
    return out


def to_text(chapter: dict, lang: str) -> str:
    L: list[str] = []
    title = pick(chapter.get("chapterTitle", ""), chapter.get("chapterTitle_en", ""), lang)
    L.append(f"# {chapter.get('chapterId', '')}: {title}")
    L.append(f"Старт: {chapter.get('startingNodeId', '')}")
    L.append(f"Узлов: {len(chapter.get('nodes', []))}")
    L.append("")

    nodes = chapter.get("nodes", [])
    for n in nodes:
        node_id = n.get("nodeId", "?")
        nxt = n.get("nextNodeId", "")
        L.append("=" * 70)
        L.append(f"NODE [{node_id}]" + (f"  -> next: [{nxt}]" if nxt else "  (конец ветки)"))
        L.append("=" * 70)
        lines = n.get("lines", []) or []
        if not lines:
            L.append("  <пустой узел>")
        for i, ln in enumerate(lines, 1):
            L.extend(format_line(ln, i, lang))
            L.append("")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def to_markdown(chapter: dict, lang: str) -> str:
    L: list[str] = []
    title = pick(chapter.get("chapterTitle", ""), chapter.get("chapterTitle_en", ""), lang)
    L.append(f"# {chapter.get('chapterId', '')}: {title}")
    L.append("")
    L.append(f"- Старт: `{chapter.get('startingNodeId', '')}`")
    L.append(f"- Узлов: {len(chapter.get('nodes', []))}")
    L.append("")
    for n in chapter.get("nodes", []):
        node_id = n.get("nodeId", "?")
        nxt = n.get("nextNodeId", "")
        L.append(f"## `{node_id}`" + (f" → `{nxt}`" if nxt else ""))
        L.append("")
        for i, ln in enumerate(n.get("lines", []) or [], 1):
            speaker = pick(ln.get("characterName", ""), ln.get("characterName_en", ""), lang)
            text = pick(ln.get("text", ""), ln.get("text_en", ""), lang)
            L.append(f"**{speaker or '…'}** ({i}): {text or '<пусто>'}")
            meta = []
            for key in ("backgroundImage", "characterSprite", "musicClip", "sfxClip", "voiceClip"):
                if ln.get(key):
                    meta.append(f"{key}={ln.get(key)}")
            if meta:
                L.append(f"  - *{'; '.join(meta)}*")
            for c in ln.get("choices", []) or []:
                ct = pick(c.get("choiceText", ""), c.get("choiceText_en", ""), lang)
                L.append(f"  - ➜ _{ct}_ → `{c.get('targetNodeId', '')}`")
            L.append("")
    return "\n".join(L).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="JSON главы -> читаемый текст")
    ap.add_argument("--input", default="chapter_01-resources.assets-61.json", help="входной JSON")
    ap.add_argument("--output", default="", help="выходной файл (по умолчанию chapter_01-readable.txt/md)")
    ap.add_argument("--lang", choices=["ru", "en", "both"], default="both", help="какой текст выводить")
    ap.add_argument("--format", choices=["txt", "md"], default="txt", help="формат вывода")
    args = ap.parse_args()

    base = pathlib.Path(__file__).resolve().parent
    inp = pathlib.Path(args.input)
    if not inp.is_absolute():
        # сначала относительно папки скрипта, потом относительно cwd
        cand = base / args.input
        inp = cand if cand.exists() else pathlib.Path.cwd() / args.input
    if not inp.exists():
        print(f"Не найден входной файл: {inp}", file=sys.stderr)
        return 1

    chapter = load_chapter(inp)
    text = to_markdown(chapter, args.lang) if args.format == "md" else to_text(chapter, args.lang)

    if args.output:
        outp = pathlib.Path(args.output)
    else:
        outp = inp.with_name(f"{inp.stem}-readable.{args.format if args.format == 'md' else 'txt'}")
    if not outp.is_absolute():
        outp = base / outp.name
    outp.write_text(text, encoding="utf-8")
    print(f"Готово: {outp} ({len(text)} символов, узлов: {len(chapter.get('nodes', []))})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
