# AGENTS.md — LED HEARTS modmaker

Modding toolkit for the Unity (6000.3, IL2CPP) game LED HEARTS.
Repo root = `modmaker/`; it must sit in the game root (`./LED HEARTS`,
next to `LED HEARTS.exe`). Live game files are one level up.

> Human users are encouraged to drive this repo via an agentic coding
> system (e.g. OpenCode) rather than by hand: point the agent at this file
> and let it run the commands below from the game root.

## Commands (run ONLY from game root)

```bat
.\.venv\Scripts\python.exe modmaker\extract_resources.py [--only chapter_01]
.\.venv\Scripts\python.exe modmaker\extract_audio.py [--only classroom,crowd]
.\.venv\Scripts\python.exe modmaker\repack_resources.py --srcdir modmaker\extracted --dry-run
.\.venv\Scripts\python.exe modmaker\mod_demo_apply.py [--revert]
.\.venv\Scripts\python.exe modmaker\mod_demo_node.py [--remove]
.\.venv\Scripts\python.exe modmaker\load_mod.py mymod.zip --dry-run
.\.venv\Scripts\python.exe modmaker\load_mod.py modmaker\mod_test.zip --dry-run
.\.venv\Scripts\python.exe modmaker\add_texture.py --png modmaker\mod_start_bg.png --name ch3_room --dry-run
.\.venv\Scripts\python.exe modmaker\add_chapter.py --dry-run
.\.venv\Scripts\python.exe modmaker\add_audio.py --wav modmaker\mod_demo_jingle.wav --name ch3_chime --dry-run
.\.venv\Scripts\python.exe modmaker\write_save.py --slot 0 --dry-run
```

- The venv lives in the **game root** (`.\.venv`), not in `modmaker/`.
- Pinned deps: `UnityPy==1.25.3`, plus `fsb5` for audio and `Pillow` for images (`modmaker/requirements.txt`).
  `extract_audio.py` also needs `ffmpeg` in PATH and the vorbis DLLs in
  `modmaker/tools/` (already vendored); the single `falling` clip needs
  external `vgmstream-cli` (auto-used from `modmaker/tools/` or PATH).
- Shell here is Windows PowerShell 5.1: no `&&` (use `;`), quote paths
  with spaces, invoke `.venv/Scripts/python.exe` directly (no `& "..."` wrapper needed).
- Verification pattern: `repack --dry-run` must show 0 changes on a fresh
  extract; after edits, repack then reload the file with UnityPy and read back.
- Every game launch MUST end with killing it in the same command
  (`try { Start-Process ...; Start-Sleep ... } finally { Stop-Process -Name 'LED HEARTS' -Force }`);
  never leave the game running for the user to kill.

## DlcRecursiveSearch plugin (`modmaker/dlc_search_plugin/`, net6.0)

- Build (needs .NET SDK 8+, offline — project has only DLL refs to the
  installed `BepInEx/core`, no NuGet restore needed):
  `dotnet build modmaker\dlc_search_plugin\DlcRecursiveSearch.csproj -c Release`;
  output DLL goes to `BepInEx\plugins\`. `bin/`/`obj/` are gitignored.
- Patch targets resolve at runtime by method name over `Assembly-CSharp`
  (`VNSceneSetup.LoadExternalDLCSprite/LoadExternalDLCAudio`,
  `DialogueManager.IsNSFWDLCOwned`); no generated interop needed to build.
- Load markers in `BepInEx\LogOutput.log`: `DLC index: N file(s)`,
  `Patched ...`, `Patches applied: 3/3`.
- BepInEx install layout in game root (create by unpacking BepInEx 6
  Unity.IL2CPP + one first launch; on this machine already present):
  `winhttp.dll`, `.doorstop_version`, `doorstop_config.ini`, `BepInEx/`
  (`core`, `plugins`, `interop` + `offline-generated.txt`, `config`),
  `dotnet/` (mini-coreclr 6.0.7). Removal = delete these; saves/game
  files untouched.

## UnityPy gotchas (verified, do not "fix")

- `env.objects` is a **list**, `env.file.objects` is a **dict** keyed by path_id.
  New objects: `copy.copy(donor_reader)` + new `path_id` + `save()`/`save_typetree()`,
  insert into `env.file.objects`, `mark_changed()`, `save()`. Verified for
  TextAsset/Sprite; Texture2D via `.image=` writes inline and zeroes `m_StreamData`.
- `Resources.Load` resolves ONLY through `ResourceManager.m_Container` in the
  `globalgamemanagers` file (path `dialoguedata/chapter_03`, `backgrounds/<name>`
  twice: Texture2D + Sprite, all lowercase, `m_FileID: 4` = resources.assets).
  A new object without a container entry is invisible to the game.
  Chapters chain via `nextNodeId: "load_chapter:<id>:<node>"`.
- `env.file.objects.get(path_id)` — `env.file.get(int)` is `File.getattr` and crashes.
- Untouched objects round-trip byte-for-byte (`data is None` → raw copy).
  Only call `.save()` on objects you actually changed; never "repair" the rest.
- `MonoBehaviour` reads often raise `ValueError` on Unity 6000 — expected.
  The extractor still keeps their `.raw`.
- `AudioClip.m_AudioData` is `None`: stock audio bytes live in
  `LED HEARTS_Data/resources.resource` as FSB5/Vorbis. New sounds can be
  embedded as FSB5/PCM16 via `fsb5pcm.py` + `add_audio.py` (pure Python,
  keeps the 16-byte alignment invariant); hand-editing stock blobs is still
  off-limits. Loose `dlc_*.wav` remains the zero-risk option.
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
  `dlc_my_room.png` → `"backgroundImage": "dlc_my_room"`;
  `dlc_my_jingle.wav` → `"sfxClip": "dlc_my_jingle:0.9"`.
  WAV must be PCM 16-bit 44100 Hz. Never reference `DLC/` — that folder is the
  user's private add-on and does not ship with the game.
  With the `DlcRecursiveSearch` plugin, `dlc_*` also resolves from any root
  subfolder (shallowest wins, duplicates warn, staged copies auto-refresh).

## Repo conventions

- `repack_resources.py` reads `TextAsset` from `<srcdir>/TextAsset/` when the
  new per-type layout exists, else flat layout (back-compat).
- `mod_demo_node.py` is idempotent: it deletes `mod_demo_*` nodes before
  re-inserting. Backups (`resources.assets.bak`, `*.pre_demo_nodes.bak`)
  are created once, next to the assets — never overwrite them.
- Do not commit: `extracted/`, `__pycache__/`, `*.tmp`, `*.bak`,
  `[Bb]in/`, `[Oo]bj/` (gitignored).
- `read_chapter.py --input` must be passed explicitly (its default filename
  is a stale artifact).
- Shared helpers live in `common.py` (`find_game_root`, `backup_once`,
  `atomic_write`, chapter validation via `validate_chapter`/`collect_refs`).
  New scripts must reuse them instead of duplicating; run scripts only from
  the game root so `import common` resolves.
- `add_texture.py` / `add_chapter.py` / `add_audio.py` / `write_save.py` /
  `fsb5pcm.py` are experimental test scripts (bugs possible): verified manually
  on 6000.3.11f1, do not present them as stable API. `chapter_03.json` is the
  test scenario used by them.
- Release flow: zip must contain top-level `modmaker/` dir; to replace a
  release: `gh release delete <tag> --yes --cleanup-tag`, rebuild zip,
  `gh release create <tag> <zip>`.
