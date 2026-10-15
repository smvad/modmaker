# reference_oldbuild — эталон dev-билда (10.09.2026)

Старый билд игры до Steam-релиза. `chapter_01_dev.json` / `chapter_02_dev.json` —
ванильные сценарии из его `LedHearts_Data/resources.assets` (извлечены UnityPy,
`m_Script` как есть). Русский текст в JSON — суррогаты шрифта, `*_en` поля читаемы.

## Что это за билд

Dev-сборка проекта `D:/led_hearts/ai Vn` (`app.info`: `DefaultCompany / ai Vn`,
релиз: `fugas_kitsune / LED HEARTS`). Движок тот же: `LedHearts.exe`
(SHA256 `AC5BC76F…`) и `UnityPlayer.dll` (`BB57338E…`) побайтово совпадают
с релизом, `D3D12/`, `level0`, `sharedassets0.assets` идентичны.

## Совпадает / изменилось

| Файл | Старый | Релиз | Вывод |
|---|---|---|---|
| `LedHearts.exe`, `UnityPlayer.dll`, `baselib.dll`, `UnityCrashHandler64.exe` | — | те же хеши | движок не менялся |
| 5× `dlc_milly_*.png`, `nsfw_dlc.dat` (0 байт) | в корне | в корне | NSFW-арт идентичен, `.dat` — файл-флаг |
| `GameAssembly.dll` | 42 392 576 | 42 492 416 (+~100 КБ) | код обновлён |
| `global-metadata.dat` | 8 550 384 | 8 577 580 (+27 КБ) | +озвучка, +аудио-DLC |
| `resources.assets` | 1 635 592 | 1 709 160 (`.bak`, ванила) | главы переписаны |
| `resources.resource` (аудио) | 22 095 232 | 40 857 888 | +войс (`VN_Voice_*`) |
| `resources.assets.resS` (текстуры) | 282 232 960 | 278 148 864 | арт менялся |
| `globalgamemanagers.assets` | хеш `f52fdaee…` | хеш `d6cd00ab…` (+128 байт) | контейнер/настройки менялись |
| `app.info`, `boot.config` | `DefaultCompany`, guid `dd0de622…` | `fugas_kitsune`, guid `73d26d43…` | dev → релиз |

## Механизм NSFW DLC (подтверждён кодом из `LedHearts_BackUp…/il2cppOutput`)

- `DialogueManager.IsNSFWDLCOwned`: `File.Exists(Path.Combine(Application.dataPath, "../nsfw_dlc.dat"))`
  (`dataPath` = `*_Data`, т.е. проверка фактически смотрит **корень игры** —
  совпадает с `readme.txt`: класть `.dat`/`.png` рядом с exe).
- `InitializeNSFWDLCStatus`: результат пишется в переменную **`dlc_nsfw_enabled`** (0/1).
- Выбор «Take off clothes» (`chapter_01`, узел `milly_inspect_undress` → `dlc_nsfw_dev_speech`)
  заперт гейтом `requiredVariables: "dlc_nsfw_enabled"`.
- `VNSceneSetup.LoadExternalDLCSprite(name)`: `File.ReadAllBytes` из корня игры
  (`<name>.png` → `Texture2D` → `Sprite`, pivot 0.5). Фоны `dlc_milly_*` грузятся так;
  спрайт `dlc_milly_nude` — как `characterSprite`. Отсутствие файла = warning + null.
- В метаданных релиза есть подсказка инспектора:
  «If true, DLC requires nsfw_dlc.dat file. If false (Full Build), DLC is 100% unlocked automatically.»
- `readme.txt` (инструкция RU/EN, Win + Android) есть только в старом билде.

## Дельта глав (dev → ванила релиза)

- `chapter_01`: те же 44 nodeId (включая всю ветку `dlc_milly_nsfw_scene…dlc_nsfw_climax`,
  10 узлов + `milly_inspect_undress(_locked)`), но каждый узел вырос в объёме;
  строк 305→315, упоминаний `nsfw` 29→33, `dlc` 32→37, `milly` 113→128.
- `chapter_02`: 63→51 узел — из dev-версии **вырезаны 12 продублированных стартовых узлов**
  (`scene2_start…classroom_exploration`, копия второй половины главы 1);
  все общие узлы сильно расширены (напр. `scene2_kiv_hug_reveal` 3.5→8.6 КБ).
- NSFW-звук: `dlc_nsfw_fingering`/`dlc_nsfw_climax` используют `sfxClip`
  `sex_sound:0.54:loop` / `sex_sound:0.65:loop` — это loose-`sex_sound.wav` в корне игры
  (в `DLC/` релиза лежат одноимённые wav от 13.10.2026 — продукт модмейкинга, не шипа).

## Дельта кода (dev → релиз, по строкам global-metadata)

Только в релизе: `LoadExternalDLCAudio`, `VN_Voice_Kiv/Maxim/Milly/Violetta`,
`Get/SetMillyVoiceEnabledSetting`, `Get/SetViolettaVoiceEnabledSetting`,
`settingsMillyVoiceText/settingsViolettaVoiceText`, титры голосов (4ntenna, Zombie,
Kesha Vex), ссылки Boosty/Twitch, промо «exclusive NSFW DLC … already available on Boosty!».
В обоих: `InitializeNSFWDLCStatus`, `IsNSFWDLCOwned`, `LoadExternalDLCSprite`, `VN Cheat & Debug Menu`.

## Что НЕ забирали (лежит в старом билде, большое)

- `LedHearts_BackUpThisFolder_ButDontShipItWithYourGame/`: полный сгенерённый
  IL2CPP C++ (`il2cppOutput/`, ~657 МБ, `Assembly-CSharp.cpp` + `Assembly-CSharp__1.cpp` —
  вся логика `DialogueManager`/`VNSceneSetup` с привязкой к `D:/led_hearts/ai Vn/...cs:строка`),
  `Managed/Assembly-CSharp.dll` (88 КБ, дот-IL2CPP имена методов),
  `GameAssembly.pdb` (~463 МБ), `Symbols/LineNumberMappings.json` (~5 МБ).
  Пригодится для точного реверса — тащить в репозиторий не стали из-за размера.
- `ai Vn_BurstDebugInformation_DoNotShip/` — только `lib_burst_generated.txt` (224 КБ), пользы нет.
