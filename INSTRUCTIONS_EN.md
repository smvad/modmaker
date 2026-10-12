# Manual chapter editing and custom assets

> **Language:** English | [Русская версия](INSTRUCTIONS.md)

## 1. Where the scenario lives

After extraction:

```bat
.venv\Scripts\python.exe modmaker\extract_resources.py --only chapter_01
```

the chapter is at `modmaker\extracted\TextAsset\101_chapter_01.json`.
It is a plain UTF-8 JSON file. Edit it with any text editor
(VS Code, Notepad++). Make sure the file stays valid JSON
(commas, quotes, brackets).

## 2. Chapter structure

- `chapterId` — the identifier, do not change.
- `chapterTitle` / `chapterTitle_en` — the title, visible in game.
- `startingNodeId` — the node the chapter starts from.
- `nodes[]` — story nodes. Each one has:
  - `nodeId` — a unique identifier;
  - `nextNodeId` — where to go after the last line (empty = branch end);
  - `lines[]` — dialogue lines in order.

Line (`lines[]`):

| Field | What it does |
|---|---|
| `characterName` (+`_en`) | Speaker name, empty = narration |
| `text` (+`_en`) | Line text |
| `backgroundImage` | Background (texture name or PNG file, `""` = keep, `"none"` = hide) |
| `characterSprite` | Character sprite (`""` = keep previous, `"none"` = hide) |
| `characterPosition` | `center`, `left`, `right`, `close`, `far` |
| `musicClip` | Music (`"none"` = stop) |
| `sfxClip` | Sound: `name`, `name:volume`, `name:volume:loop`; `"stop"` = stop loop |
| `voiceClip` | Line voice-over |
| `overlayAlpha` | Dimming: `-1` = none, `0..1` = amount |
| `emotion` | Field exists, currently unused by the game |
| `requiredVariables` | Line is shown only if the variable is set |
| `choices` | Choices (see below) |

Choice (`choices[]`):

| Field | What it does |
|---|---|
| `choiceText` (+`_en`) | Option text |
| `targetNodeId` | Node to jump to |
| `setVariable` + `modifyValue` | Set a variable (usually `1`) |
| `requiredVariables` | Choice is available only if the variable is set |
| `lockedText` (+`_en`) | Locked-option text (shown instead of `choiceText`) |

Variables are integers. Multiple conditions go comma-separated:
`"went_to_cafeteria_ch1,hugged_milly_twice"`. Variables persist across
playthroughs (e.g. a chapter 1 choice affects chapter 2).

## 3. Typical edits

- Change text: edit `text` / `text_en` of the line you need.
- Hide the character before narration: set `"characterSprite": "none"`.
- Change background: set an existing name (`zoo`, `cafe`, `room_day`, ...).
  The full name list is in `objects_list.txt` after extraction.
- Add a node: copy any node, give it a new `nodeId`, reference it via
  a choice's `nextNodeId` or `targetNodeId`.

## 4. Writing edits back into the game

First a no-write check (from the game root):

```bat
.venv\Scripts\python.exe modmaker\repack_resources.py --srcdir modmaker\extracted --dry-run
```

If the diff is as expected — write:

```bat
.venv\Scripts\python.exe modmaker\repack_resources.py --srcdir modmaker\extracted
```

The original is saved to `LED HEARTS_Data\resources.assets.bak` (once).

## 5. Custom assets: where to put them and in which format

The game first looks an asset up in `resources.assets`, and if it is not
there — loads an external file **from the game root** (next to
`LED HEARTS.exe`).

### Backgrounds and sprites — PNG in the game root, name strictly with the `dlc_` prefix

- The external loader (`LoadExternalDLCSprite`) only tries a file if its name
  starts with `dlc_`. Without the prefix the game stops at a
  `not found in Resources/...` warning and ignores the file (verified via
  `Player.log`).
- Format: plain PNG, any size (1920×1080 preferred for backgrounds).
- File name = scenario name. Example: the file `dlc_my_room.png` in the game
  root is used by the line `"backgroundImage": "dlc_my_room"`.
- Same for characters: `dlc_my_hero.png` + `"characterSprite": "dlc_my_hero"`.
- Do not put them in subfolders (e.g. inside `modmaker/`) — the loader looks
  strictly in the game root (next to `LED HEARTS.exe`).

### Sounds — WAV in the game root, name strictly with the `dlc_` prefix

- Format: WAV, PCM 16-bit, 44100 Hz, mono or stereo.
  Exactly this kind of WAV is what the game converts via `WavBytesToAudioClip`.
- The external loader (`LoadExternalDLCAudio`) only tries a file if its name
  starts with `dlc_` — the same prefix as for sprites and backgrounds.
- File name = scenario name without extension. Example: `dlc_my_jingle.wav`
  is used as `"sfxClip": "dlc_my_jingle:0.9"` (volume 0–1).
- Works in all three fields: `sfxClip`, `voiceClip`, `musicClip`.
- Bundled example: `modmaker\mod_demo_jingle.wav`
  (the `mod_demo_node.py` script copies it into the root itself).
