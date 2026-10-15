# LED HEARTS Modmaker

> **Язык:** Русский | [English version](README_EN.md)

Набор скриптов для моддинга LED HEARTS: извлечение ассетов, правка глав,
замена фонов, кастомные звуки и демо-мод.

> Все команды в этом файле запускаются **только из корня игры**
> (`./LED HEARTS` — папка с `LED HEARTS.exe`).

> **Рекомендация:** с модмейкером проще работать через агентную
> coding-систему (например, OpenCode): покажите агенту `AGENTS.md` в папке
> `modmaker/` — он выполнит команды из корня игры, проверки `--dry-run`
> и откат при необходимости. Ручной запуск тоже поддерживается, но требует
> аккуратности с путями и бэкапами.

## Установка

### Вариант 1: ZIP из Releases (без git)

1. Скачайте `modmaker.zip` со страницы
   [Releases](https://github.com/smvad/modmaker/releases).
2. Распакуйте архив в корень игры (`./LED HEARTS`, рядом с `LED HEARTS.exe`),
   чтобы появилась папка `modmaker/`.
3. Установите зависимости один раз из корня игры:

   ```bat
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r modmaker\requirements.txt
   ```

### Вариант 2: git clone

Выполните из корня игры (`./LED HEARTS`):

```bat
git clone https://github.com/smvad/modmaker.git modmaker
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r modmaker\requirements.txt
```

Если `.venv` уже создан, достаточно:

```bat
.venv\Scripts\python.exe -m pip install -r modmaker\requirements.txt
```

## Быстрый запуск

1. Примените демонстрационный мод:

   ```bat
   .venv\Scripts\python.exe modmaker\mod_demo_apply.py
   .venv\Scripts\python.exe modmaker\mod_demo_node.py
   ```

   Первый скрипт заменяет первый фон, добавляет `[MOD]` в первую реплику и
   сохраняет `resources.assets.bak`. Второй добавляет в начало главы 1
   демонстрационную цепочку узлов с выборами, переменными, спрайтами, фонами,
   музыкой, SFX, затемнением и кастомным WAV-звуком.

2. Запустите игру обычным способом.

Можно использовать `modmaker\run_demo.bat` для применения обоих изменений
одной командой.

## Установка мода из ZIP

Мод — это ZIP с JSON глав (`chapter_01.json`, `chapter_02.json` — чистый
сценарий или Unity-обёртка `{"m_Name":..., "m_Script":...}`) и внешними
ассетами (`dlc_*.png`, `dlc_*.wav`, подпапки внутри ZIP разрешены).
Сначала проверка без записи, затем применение (из корня игры):

```bat
.venv\Scripts\python.exe modmaker\load_mod.py mymod.zip --dry-run
.venv\Scripts\python.exe modmaker\load_mod.py mymod.zip
```

Скрипт проверяет JSON (уникальность `nodeId`, существование
`startingNodeId`/`nextNodeId`/`targetNodeId`, с учётом команды
`load_chapter:...`), предупреждает о ссылках на ассеты, которых нет ни
в игре, ни в ZIP, ни в корне игры (пути вида `milly/pose_a/happy`
считаются внутренними и не проверяются), отклоняет файлы без префикса
`dlc_` и битые WAV/PNG, делает `resources.assets.bak` один раз и копирует
`dlc_*` файлы в корень игры (рядом с `LED HEARTS.exe`), откуда их забирает
внешний загрузчик игры.

Подробно о ручном редактировании JSON и своих ассетах (PNG/WAV, куда кидать,
форматы): [INSTRUCTIONS.md](INSTRUCTIONS.md).

## Рекурсивный поиск DLC-ассетов (BepInEx)

Ванильная игра видит внешние `dlc_*` файлы только в корне. Плагин
`DlcRecursiveSearch` ищет `dlc_*.png`, `dlc_*.wav` и `nsfw_dlc.dat`
**в любой подпапке** корня игры (побеждает самый мелкий путь, дубли —
warning в лог; свои копии в корне отслеживаются и обновляются сами).

Установка: распаковать BepInEx 6 (Unity.IL2CPP, win-x64) в корень игры,
один раз запустить игру (сгенерируется `BepInEx/interop/`), положить
собранный `DlcRecursiveSearch.dll` в `BepInEx\plugins\`.
Проверка: положить PNG в подпапку, запустить игру,
в `BepInEx\LogOutput.log` должны быть `DLC index: N file(s)`,
три `Patched ...` и `Patches applied: 3/3`.
Подробности, сборка (.NET SDK, офлайн), удаление:
[dlc_search_plugin/README.md](dlc_search_plugin/README.md).

## Откат

```bat
.venv\Scripts\python.exe modmaker\mod_demo_node.py --remove
.venv\Scripts\python.exe modmaker\mod_demo_apply.py --revert
```

Для полного возврата исходного файла можно восстановить:

```text
LED HEARTS_Data\resources.assets.bak
LED HEARTS_Data\globalgamemanagers.bak   (после add_texture.py / add_chapter.py)
```

## Извлечение и упаковка

Извлечь все ассеты всех типов:

```bat
.venv\Scripts\python.exe modmaker\extract_resources.py
```

Данные появятся в `modmaker\extracted`. Внутри будет отдельная папка для
каждого типа (`Texture2D`, `Sprite`, `AudioClip`, `TextAsset`, `GameObject`,
`MonoBehaviour` и т.д.). Каждый объект сохраняется как `.raw` и `.json`;
текстуры и спрайты дополнительно сохраняются в PNG. `index.json` содержит
полную карту объектов, `summary.json` — количество объектов по типам.
Проверено на `resources.assets`: 2444 объекта в 11 папках-типах, для каждого
есть `.raw` и `.json`, плюс 182 PNG. Единственные ошибки декодирования —
4 встроенные `Font Texture` (их `.raw` при этом сохраняется).

Сделать человекочитаемый текст главы:

```bat
.venv\Scripts\python.exe modmaker\read_chapter.py --input modmaker\extracted\TextAsset\101_chapter_01.json --format md
```

Извлечь весь звук игры в WAV (нужен `ffmpeg` в PATH, результат — в
`modmaker\extracted_audio`, один клип `falling` требует `vgmstream-cli`):

```bat
.venv\Scripts\python.exe modmaker\extract_audio.py [--only classroom,crowd]
```

Проверить изменения без записи:

```bat
.venv\Scripts\python.exe modmaker\repack_resources.py --srcdir modmaker\extracted --dry-run
```

Записать отредактированные JSON обратно:

```bat
.venv\Scripts\python.exe modmaker\repack_resources.py --srcdir modmaker\extracted
```

Скрипты требуют, чтобы папка `modmaker` лежала в корне игры:
пути вида `modmaker\...` и `LED HEARTS_Data\...` отсчитываются от него.

## Содержимое

- `mod_demo_apply.py` — замена первого фона и простой текстовый маркер.
- `mod_demo_node.py` — добавление демонстрационной цепочки узлов.
- `mod_nova_node.py` / `mod_gif_node.py` — дополнительные демо-цепочки (`--remove` для отката).
- `common.py` — общие помощники (пути, бэкапы, валидация глав).
- `load_mod.py` — установка мода из ZIP (JSON глав + `dlc_*` PNG/JPG/WAV).
- `mod_test.zip` — готовый тестовый мод (ветка `mod_test_*` в главе 1 + ассеты
  Новы): `.venv\Scripts\python.exe modmaker\load_mod.py modmaker\mod_test.zip`.
- `extract_resources.py` — извлечение всех ассетов всех типов.
- `repack_resources.py` — запись изменённых `TextAsset` обратно.
- `read_chapter.py` — вывод главы в TXT/Markdown.
- `extract_audio.py` — извлечение всех `AudioClip` (FSB5/Vorbis) в WAV.
- `mod_start_bg.png` — демонстрационный фон.
- `mod_demo_jingle.wav` — кастомный звук, загружаемый игрой из корня.
- `requirements.txt` — зависимости `UnityPy`, `fsb5`, `Pillow`.
- `run_demo.bat` — применить оба демо-мода.
- `dlc_search_plugin/` — BepInEx-плагин рекурсивного поиска `dlc_*`
  по подпапкам + README (установка, сборка, проверка).
- `exit_skip_plugin/` — BepInEx-плагин: пропуск экрана выхода/капчи
  любой клавишей или кнопкой мыши + README.
- `gallery_unlock_plugin/` — BepInEx-плагин (временный): открывает все 20 CG
  галереи, выставляя `cg_seen_*` в PlayerPrefs.
- `INSTRUCTIONS.md` / `INSTRUCTIONS_EN.md` — ручное редактирование глав и свои ассеты (RU/EN).

## Экспериментальное (тестовые скрипты, возможны баги)

Проверены на сборке 6000.3.11f1 вручную (фон/глава/звук в игре работают),
но покрытие тестами частичное. Перед записью скрипты делают `.bak`
(и `led_saves_backup.reg` для сейвов) — не удаляйте их до проверки в игре.
О багах — issue в репозитории.

- `add_texture.py` — вставить PNG внутрь `resources.assets` (пара Texture2D+Sprite
  + записи в контейнере).
- `add_chapter.py` — вставить новую главу-TextAsset + запись в контейнере +
  связка `load_chapter` из старой главы.
- `chapter_03.json` — тестовый сценарий главы 3 (встроенные фон `ch3_room`
  и звук `ch3_chime`, выбор, переменная).
- `fsb5pcm.py` — кодировщик WAV PCM16 → FSB5/PCM16 для банка `resources.resource`.
- `add_audio.py` — вшить WAV внутрь `resources.resource` + AudioClip + запись
  в контейнере (`"sfxClip": "ch3_chime:0.9"`).
- `write_save.py` — сейв в слот + точка Продолжить перед главой 3
  (PlayerPrefs в `HKCU\Software\fugas_kitsune\LED HEARTS`).

При применении `mod_demo_node.py` кастомный WAV автоматически копируется из
`modmaker` в корень игры: внешний загрузчик игры ищет его именно там.

Не переименовывайте `mod_start_bg.png` и `mod_demo_jingle.wav`: эти имена
используются сценарием и внешним загрузчиком игры.
