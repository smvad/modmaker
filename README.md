# LED HEARTS Modmaker

Набор скриптов для моддинга LED HEARTS: извлечение ассетов, правка глав,
замена фонов, кастомные звуки и демо-мод.

> Все команды в этом файле запускаются **только из корня игры**
> (`./LED HEARTS` — папка с `LED HEARTS.exe`).

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

## Откат

```bat
.venv\Scripts\python.exe modmaker\mod_demo_node.py --remove
.venv\Scripts\python.exe modmaker\mod_demo_apply.py --revert
```

Для полного возврата исходного файла можно восстановить:

```text
LED HEARTS_Data\resources.assets.bak
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
- `extract_resources.py` — извлечение всех ассетов всех типов.
- `repack_resources.py` — запись изменённых `TextAsset` обратно.
- `read_chapter.py` — вывод главы в TXT/Markdown.
- `mod_start_bg.png` — демонстрационный фон.
- `mod_demo_jingle.wav` — кастомный звук, загружаемый игрой из корня.
- `requirements.txt` — зависимость `UnityPy`.
- `run_demo.bat` — применить оба демо-мода.

При применении `mod_demo_node.py` кастомный WAV автоматически копируется из
`modmaker` в корень игры: внешний загрузчик игры ищет его именно там.

Не переименовывайте `mod_start_bg.png` и `mod_demo_jingle.wav`: эти имена
используются сценарием и внешним загрузчиком игры.
