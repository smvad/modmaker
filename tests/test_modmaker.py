#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke-тесты modmaker (LED HEARTS).

Запуск строго из корня игры:
    .\\.venv\\Scripts\\python.exe -m unittest modmaker.tests.test_modmaker -v

Все тесты только читают или работают с --dry-run / временными папками:
записи в LED HEARTS_Data и корень игры запрещены и проверяются.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import wave
import zipfile

BASE = pathlib.Path(__file__).resolve().parent.parent  # modmaker/
GAME = BASE.parent  # корень игры
sys.path.insert(0, str(BASE))

from common import collect_refs, load_scenario, validate_chapter, write_json  # noqa: E402

MOD_TEST = BASE / "mod_test.zip"
MOD_KM = BASE / "mod_km.zip"
CHAPTER_03 = BASE / "chapter_03.json"
ASSETS = GAME / "LED HEARTS_Data" / "resources.assets"


def run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(BASE / name), *args],
        cwd=str(GAME),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        env=env,
    )


def scenario_from_zip(zpath: pathlib.Path, member: str) -> dict:
    with zipfile.ZipFile(zpath) as z:
        raw = json.loads(z.read(member).decode("utf-8-sig"))
    if isinstance(raw, dict) and isinstance(raw.get("m_Script"), str):
        return json.loads(raw["m_Script"])
    return raw


def snapshot_game_root() -> dict:
    return {
        p.name: (p.stat().st_size, p.stat().st_mtime_ns)
        for p in GAME.iterdir()
        if p.is_file() and p.suffix.lower() not in (".tmp",)
    }


class TestRequirements(unittest.TestCase):
    def test_pinned_deps(self):
        req = (BASE / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("UnityPy==1.25.3", req)
        self.assertIn("fsb5", req)
        self.assertIn("Pillow", req)


class TestChapters(unittest.TestCase):
    def test_chapter_03_valid(self):
        scen = load_scenario(CHAPTER_03)
        self.assertEqual(scen.get("chapterId"), "chapter_03")
        self.assertEqual(validate_chapter(scen), [])

    def test_mod_zip_chapters_valid(self):
        for zpath, member, want_id in (
            (MOD_TEST, "chapter_01.json", "chapter_01"),
            (MOD_KM, "chapter_02.json", "chapter_02"),
        ):
            with self.subTest(zip=zpath.name):
                scen = scenario_from_zip(zpath, member)
                self.assertEqual(scen.get("chapterId"), want_id)
                self.assertEqual(validate_chapter(scen), [])

    def test_mod_zip_assets_prefixed_and_parseable(self):
        for zpath in (MOD_TEST, MOD_KM):
            with self.subTest(zip=zpath.name), zipfile.ZipFile(zpath) as z:
                externals = [n for n in z.namelist()
                             if n.lower().endswith((".png", ".jpg", ".jpeg", ".wav"))]
                self.assertTrue(externals, "в моде нет внешних ассетов")
                for n in externals:
                    self.assertTrue(
                        pathlib.PurePosixPath(n).name.startswith("dlc_"),
                        f"{n}: внешний ассет без префикса dlc_",
                    )
                for n in externals:
                    data = z.read(n)
                    if n.lower().endswith(".wav"):
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                            f.write(data)
                            tmp = f.name
                        try:
                            with wave.open(tmp, "rb") as w:
                                self.assertEqual(w.getsampwidth(), 2, f"{n}: не 16-bit")
                                self.assertEqual(w.getframerate(), 44100, f"{n}: не 44100 Гц")
                        finally:
                            pathlib.Path(tmp).unlink(missing_ok=True)
                    else:
                        from PIL import Image
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                            f.write(data)
                            tmp = f.name
                        try:
                            with Image.open(tmp) as im:
                                im.verify()
                        finally:
                            pathlib.Path(tmp).unlink(missing_ok=True)

    def test_mod_zip_own_dlc_refs_covered(self):
        """Ссылки мода на его собственные dlc-префикс покрыты ZIP или корнем игры.

        Чужие dlc-ссылки (напр. dlc_milly_* из приватного NSFW-DLC, уже
        известные текущей главе в игре) load_mod.py сознательно не проверяет
        строго: он предупреждает только о НОВЫХ ссылках. Здесь проверяем то,
        что обязан предоставить сам мод: assets под его собственным префиксом.
        """
        own_prefix = {"mod_test.zip": "dlc_nova_", "mod_km.zip": "dlc_km_"}
        for zpath, member in (
            (MOD_TEST, "chapter_01.json"),
            (MOD_KM, "chapter_02.json"),
        ):
            with self.subTest(zip=zpath.name):
                scen = scenario_from_zip(zpath, member)
                imgs, clips = collect_refs(scen)
                with zipfile.ZipFile(zpath) as z:
                    zip_bases = {pathlib.PurePosixPath(n).stem for n in z.namelist()}
                for ref in sorted(imgs | clips):
                    if not ref.startswith(own_prefix[zpath.name]):
                        continue
                    covered = (
                        ref in zip_bases
                        or (GAME / (ref + ".png")).exists()
                        or (GAME / (ref + ".wav")).exists()
                    )
                    self.assertTrue(covered, f"{ref}: ассет мода ничем не покрыт")


class TestDryRunCLIs(unittest.TestCase):
    def test_load_mod_dry_run_no_write(self):
        before_files = snapshot_game_root()
        before_assets = (ASSETS.stat().st_size, ASSETS.stat().st_mtime_ns)
        for zpath in (MOD_TEST, MOD_KM):
            with self.subTest(zip=zpath.name):
                proc = run_script("load_mod.py", str(zpath), "--dry-run")
                self.assertEqual(proc.returncode, 0, msg=proc.stderr[-2000:])
                self.assertIn("Dry-run", proc.stdout)
        self.assertEqual(snapshot_game_root(), before_files, "dry-run изменил корень игры")
        self.assertEqual(
            (ASSETS.stat().st_size, ASSETS.stat().st_mtime_ns),
            before_assets,
            "dry-run изменил resources.assets",
        )

    def test_extract_repack_roundtrip_zero_diff(self):
        with tempfile.TemporaryDirectory(prefix="modmaker_test_") as tmp:
            ext = run_script("extract_resources.py", "--only", "chapter_01",
                             "--outdir", tmp)
            self.assertEqual(ext.returncode, 0, msg=ext.stderr[-2000:])
            rep = run_script("repack_resources.py", "--srcdir", tmp, "--dry-run")
            self.assertEqual(rep.returncode, 0, msg=rep.stderr[-2000:])
            self.assertIn("изменений было бы 0", rep.stdout)


class TestHelpers(unittest.TestCase):
    def test_write_json_no_crlf_doubling(self):
        # Ловушка кодировки (см. AGENTS.md): запись через newline="" не должна
        # превращать \r\n в \r\r\n. json.dump экранирует переводы строк, поэтому
        # проверяем round-trip и отсутствие удвоенных CR на двух уровнях:
        # сам write_json и plain-text запись главы как в repack/extract.
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "x.json"
            value = {"text": "a\r\nb"}
            write_json(p, value)
            raw = p.read_bytes()
            self.assertNotIn(b"\r\r\n", raw)
            self.assertEqual(json.loads(raw.decode("utf-8")), value)
            t = pathlib.Path(tmp) / "chapter.txt"
            with open(t, "w", encoding="utf-8", newline="") as f:
                f.write("line1\r\nline2\r\n")
            self.assertNotIn(b"\r\r\n", t.read_bytes())


class TestRepoState(unittest.TestCase):
    def test_tracked_files_intact(self):
        for name in ("images/logo.png", "mod_gif_node.py", "mod_nova_node.py",
                     "mod_start_bg.png", "mod_demo_jingle.wav"):
            with self.subTest(file=name):
                self.assertTrue((BASE / name).is_file(), f"{name} отсутствует")
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=str(BASE), capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        ).stdout.split()
        for name in ("images/logo.png", "mod_gif_node.py", "mod_start_bg.png"):
            self.assertIn(name, tracked)

    def test_mod_km_stays_untracked(self):
        self.assertTrue(MOD_KM.is_file())
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=str(BASE), capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        ).stdout.split()
        self.assertNotIn("mod_km.zip", tracked)

    def test_no_generated_junk(self):
        for p in (BASE / "extracted", BASE / "extracted_audio"):
            self.assertFalse(p.exists(), f"{p.name}/ должен быть удалён")
        self.assertEqual(list((BASE / "images").glob("dlc_nova_*.png")), [])
        # __pycache__ неизбежно пересоздаётся самим запуском тестов —
        # проверяем, что он хотя бы gitignored, а не трекается.
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=str(BASE), capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        ).stdout.split()
        self.assertNotIn("__pycache__", " ".join(tracked))
        ignored = subprocess.run(
            ["git", "check-ignore", "__pycache__"], cwd=str(BASE),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        self.assertEqual(ignored.returncode, 0, "__pycache__ должен быть в .gitignore")


if __name__ == "__main__":
    unittest.main(verbosity=2)
