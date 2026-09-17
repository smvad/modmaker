# AGENTS.md — LED HEARTS modmaker

Modding toolkit for the Unity (6000.3, IL2CPP) game LED HEARTS.
Repo root = `modmaker/`; it must sit in the game root (`./LED HEARTS`,
next to `LED HEARTS.exe`). Live game files are one level up.

## Commands (run ONLY from game root)

```bat
.\.venv\Scripts\python.exe modmaker\extract_resources.py [--only chapter_01]
.\.venv\Scripts\python.exe modmaker\extract_audio.py [--only classroom,crowd]
.\.venv\Scripts\python.exe modmaker\repack_resources.py --srcdir modmaker\extracted --dry-run
.\.venv\Scripts\python.exe modmaker\mod_demo_apply.py [--revert]
.\.venv\Scripts\python.exe modmaker\mod_demo_node.py [--remove]
.\.venv\Scripts\python.exe modmaker\load_mod.py mymod.zip --dry-run
.\.venv\Scripts\python.exe modmaker\load_mod.py modmaker\mod_test.zip --dry-run
```

- The venv lives in the **game root** (`.\.venv`), not in `modmaker/`.
- Pinned dep: `UnityPy==1.25.3`, plus `fsb5` for audio (`modmaker/requirements.txt`).
  `extract_audio.py` also needs `ffmpeg` in PATH and the vorbis DLLs in
  `modmaker/tools/` (already vendored); the single `falling` clip needs
  external `vgmstream-cli` (auto-used from `modmaker/tools/` or PATH).
- Shell here is Windows PowerShell 5.1: no `&&` (use `;`), quote paths
  with spaces, invoke `.venv/Scripts/python.exe` directly (no `& "..."` wrapper needed).
- Verification pattern: `repack --dry-run` must show 0 changes on a fresh
  extract; after edits, repack then reload the file with UnityPy and read back.

## UnityPy gotchas (verified, do not "fix")

- `env.file.objects.get(path_id)` — `env.file.get(int)` is `File.getattr` and crashes.
- Untouched objects round-trip byte-for-byte (`data is None` → raw copy).
  Only call `.save()` on objects you actually changed; never "repair" the rest.
- `MonoBehaviour` reads often raise `ValueError` on Unity 6000 — expected.
  The extractor still keeps their `.raw`.
- `AudioClip.m_AudioData` is `None`: audio bytes live in
  `LED HEARTS_Data/resources.resource` as FSB5. Never hand-edit bundle audio;
  custom sounds go in as loose files (below).
- `Texture2D.image` works (game textures are uncompressed RGB24), except the
  4 built-in `Font Texture`s which fail PNG decode with a bogus
  `PermissionError` — their `.raw` is still saved, leave them alone.

## Text encoding trap

Game chapter JSON uses `\r\n`. Always write text with
`open(path, "w", encoding="utf-8", newline="")`. Plain `Path.write_text`
on Windows doubles it to `\r\r\n`, which shows up as phantom repack diffs.

## Game data semantics (`DialogueLine` / `DialogueChoice`)

- `characterSprite` / `backgroundImage`: `""` = keep previous, `"none"` = hide.
  A demo chain MUST end with `characterSprite: "none"` or its sprite leaks
  into the original chapter.
- `sfxClip`: `name`, `name:vol`, `name:vol:loop`; `"stop"` ends a loop.
  Keep SFX on its own line (no simultaneous `musicClip` change) and prefer
  audible volumes (`crowd:0.6:loop`, not `0.1`).
- `musicClip: "none"` stops music. `overlayAlpha: -1` = off.
- Variables are ints: `setVariable` + `modifyValue: 1`;
  `requiredVariables` is comma-AND; `lockedText` shows when the gate fails.
- External assets load from the **game root by base name**:
  `my_room.png` → `"backgroundImage": "my_room"`;
  `my_jingle.wav` → `"sfxClip": "my_jingle:0.9"`.
  WAV must be PCM 16-bit 44100 Hz. Never reference `DLC/` — that folder is the
  user's private add-on and does not ship with the game.

## Repo conventions

- `repack_resources.py` reads `TextAsset` from `<srcdir>/TextAsset/` when the
  new per-type layout exists, else flat layout (back-compat).
- `mod_demo_node.py` is idempotent: it deletes `mod_demo_*` nodes before
  re-inserting. Backups (`resources.assets.bak`, `*.pre_demo_nodes.bak`)
  are created once, next to the assets — never overwrite them.
- Do not commit: `extracted/`, `__pycache__/`, `*.tmp`, `*.bak` (gitignored).
- `read_chapter.py --input` must be passed explicitly (its default filename
  is a stale artifact).
- Release flow: zip must contain top-level `modmaker/` dir; to replace a
  release: `gh release delete <tag> --yes --cleanup-tag`, rebuild zip,
  `gh release create <tag> <zip>`.
