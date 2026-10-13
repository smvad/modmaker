# LED HEARTS Modmaker

> **Language:** English | [Русская версия](README.md)

A set of scripts for modding LED HEARTS: asset extraction, chapter editing,
background replacement, custom sounds, and a demo mod.

> All commands in this file are run **only from the game root**
> (`./LED HEARTS` — the folder containing `LED HEARTS.exe`).

> **Recommendation:** modmaker is easier to drive via an agentic coding
> system (e.g. OpenCode): point the agent at `AGENTS.md` in the `modmaker/`
> folder — it will run the commands from the game root, the `--dry-run`
> checks, and roll back if needed. Manual runs work too, but require care
> with paths and backups.

## Installation

### Option 1: ZIP from Releases (no git)

1. Download `modmaker.zip` from the
   [Releases](https://github.com/smvad/modmaker/releases) page.
2. Unpack the archive into the game root (`./LED HEARTS`, next to
   `LED HEARTS.exe`) so that a `modmaker/` folder appears.
3. Install the dependencies once, from the game root:

    ```bat
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r modmaker\requirements.txt
    ```

### Option 2: git clone

Run from the game root (`./LED HEARTS`):

```bat
git clone https://github.com/smvad/modmaker.git modmaker
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r modmaker\requirements.txt
```

If `.venv` already exists, this is enough:

```bat
.venv\Scripts\python.exe -m pip install -r modmaker\requirements.txt
```

## Quick start

1. Apply the demo mod:

    ```bat
    .venv\Scripts\python.exe modmaker\mod_demo_apply.py
    .venv\Scripts\python.exe modmaker\mod_demo_node.py
    ```

    The first script replaces the first background, adds a `[MOD]` marker to
    the first line, and saves `resources.assets.bak`. The second one prepends
    a demo node chain with choices, variables, sprites, backgrounds, music,
    SFX, dimming, and a custom WAV sound to the beginning of chapter 1.

2. Start the game as usual.

You can use `modmaker\run_demo.bat` to apply both changes with a single command.

## Installing a mod from ZIP

A mod is a ZIP with chapter JSON (`chapter_01.json`, `chapter_02.json` — either
a plain scenario or a Unity wrapper `{"m_Name":..., "m_Script":...}`) plus
external assets (`dlc_*.png`, `dlc_*.wav`; subfolders inside the ZIP are
allowed). First a no-write check, then apply (from the game root):

```bat
.venv\Scripts\python.exe modmaker\load_mod.py mymod.zip --dry-run
.venv\Scripts\python.exe modmaker\load_mod.py mymod.zip
```

The script validates the JSON (`nodeId` uniqueness, existence of
`startingNodeId`/`nextNodeId`/`targetNodeId`, honoring the
`load_chapter:...` command), warns about asset references found neither in
the game, nor in the ZIP, nor in the game root (paths like
`milly/pose_a/happy` are considered internal and are not checked), rejects
files without the `dlc_` prefix and broken WAV/PNG files, makes a one-time
`resources.assets.bak`, and copies `dlc_*` files into the game root (next to
`LED HEARTS.exe`), where the game's external loader picks them up.

Details on manual JSON editing and custom assets (PNG/WAV, where to put them,
formats): [INSTRUCTIONS_EN.md](INSTRUCTIONS_EN.md).

## Recursive DLC asset search (BepInEx)

The vanilla game only sees external `dlc_*` files in the root.
The `DlcRecursiveSearch` plugin finds `dlc_*.png`, `dlc_*.wav` and
`nsfw_dlc.dat` in **any subfolder** of the game root (shallowest path
wins, duplicates warn in the log; staged root copies are tracked and
refreshed automatically).

Install: unpack BepInEx 6 (Unity.IL2CPP, win-x64) into the game root,
start the game once (`BepInEx/interop/` gets generated), put the built
`DlcRecursiveSearch.dll` into `BepInEx\plugins\`.
Check: drop a PNG into a subfolder, start the game,
`BepInEx\LogOutput.log` should show `DLC index: N file(s)`,
three `Patched ...` lines and `Patches applied: 3/3`.
Details, building (.NET SDK, offline), removal:
[dlc_search_plugin/README.md](dlc_search_plugin/README.md).

## Rollback

```bat
.venv\Scripts\python.exe modmaker\mod_demo_node.py --remove
.venv\Scripts\python.exe modmaker\mod_demo_apply.py --revert
```

To fully restore the original files you can recover:

```text
LED HEARTS_Data\resources.assets.bak
LED HEARTS_Data\globalgamemanagers.bak   (after add_texture.py / add_chapter.py)
```

## Extraction and repacking

Extract all assets of all types:

```bat
.venv\Scripts\python.exe modmaker\extract_resources.py
```

The data appears in `modmaker\extracted`. Inside there is a separate folder
for each type (`Texture2D`, `Sprite`, `AudioClip`, `TextAsset`, `GameObject`,
`MonoBehaviour`, etc.). Every object is saved as `.raw` plus `.json`;
textures and sprites are additionally saved as PNG. `index.json` holds the
full object map, `summary.json` — the per-type object counts. Verified on
`resources.assets`: 2444 objects in 11 type folders, each with `.raw` and
`.json`, plus 182 PNGs. The only decoding errors are the 4 built-in
`Font Texture`s (their `.raw` is still saved).

Render a human-readable chapter text:

```bat
.venv\Scripts\python.exe modmaker\read_chapter.py --input modmaker\extracted\TextAsset\101_chapter_01.json --format md
```

Extract all game audio to WAV (`ffmpeg` required in PATH, output goes to
`modmaker\extracted_audio`, the single `falling` clip needs `vgmstream-cli`):

```bat
.venv\Scripts\python.exe modmaker\extract_audio.py [--only classroom,crowd]
```

Check changes without writing:

```bat
.venv\Scripts\python.exe modmaker\repack_resources.py --srcdir modmaker\extracted --dry-run
```

Write edited JSON back:

```bat
.venv\Scripts\python.exe modmaker\repack_resources.py --srcdir modmaker\extracted
```

The scripts require the `modmaker` folder to sit in the game root:
paths like `modmaker\...` and `LED HEARTS_Data\...` are resolved from it.

## Contents

- `mod_demo_apply.py` — first-background replacement and a simple text marker.
- `mod_demo_node.py` — demo node chain insertion.
- `mod_nova_node.py` / `mod_gif_node.py` — extra demo chains (`--remove` to roll back).
- `common.py` — shared helpers (paths, backups, chapter validation).
- `load_mod.py` — mod installation from ZIP (chapter JSON + `dlc_*` PNG/JPG/WAV).
- `mod_test.zip` — a ready test mod (`mod_test_*` branch in chapter 1 + Nova
  assets): `.venv\Scripts\python.exe modmaker\load_mod.py modmaker\mod_test.zip`.
- `extract_resources.py` — extraction of all assets of all types.
- `repack_resources.py` — writing changed `TextAsset`s back.
- `read_chapter.py` — chapter output as TXT/Markdown.
- `extract_audio.py` — extraction of all `AudioClip`s (FSB5/Vorbis) to WAV.
- `mod_start_bg.png` — demo background.
- `mod_demo_jingle.wav` — custom sound loaded by the game from the root.
- `requirements.txt` — the `UnityPy`, `fsb5`, `Pillow` dependencies.
- `run_demo.bat` — apply both demo mods.
- `dlc_search_plugin/` — BepInEx plugin for recursive `dlc_*` subfolder
  search + README (install, build, verify).
- `INSTRUCTIONS_EN.md` / `INSTRUCTIONS.md` — manual chapter editing and custom assets (EN/RU).

## Experimental (test scripts, bugs possible)

Manually verified on build 6000.3.11f1 (embedded background/chapter/sound
play in-game), but test coverage is partial. The scripts back up to `.bak`
(and `led_saves_backup.reg` for saves) before writing — keep those until
verified in-game. Report bugs via repo issues.

- `add_texture.py` — embed a PNG inside `resources.assets` (Texture2D+Sprite
  pair plus container entries).
- `add_chapter.py` — insert a new chapter TextAsset plus container entry plus
  a `load_chapter` link from an old chapter.
- `chapter_03.json` — test chapter-3 scenario (embedded `ch3_room` background
  and `ch3_chime` sound, choice, variable).
- `fsb5pcm.py` — WAV PCM16 → FSB5/PCM16 encoder for the `resources.resource` bank.
- `add_audio.py` — embed a WAV inside `resources.resource` + AudioClip +
  container entry (`"sfxClip": "ch3_chime:0.9"`).
- `write_save.py` — write a slot save + Continue point before chapter 3
  (PlayerPrefs in `HKCU\Software\fugas_kitsune\LED HEARTS`).

When `mod_demo_node.py` is applied, the custom WAV is automatically copied
from `modmaker` into the game root: the game's external loader looks for it
exactly there.

Do not rename `mod_start_bg.png` and `mod_demo_jingle.wav`: these names are
used by the scenario and the game's external loader.
