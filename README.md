# LED HEARTS Modmaker

Эту папку можно целиком положить в корень игры, рядом с `LED HEARTS.exe`.

## Быстрый запуск

1. Установите зависимости один раз:

   ```bat
   ..\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   Если `.venv` ещё нет, выполните из корня игры:

   ```bat
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r modmaker\requirements.txt
   ```

2. Примените демонстрационный мод:

   ```bat
   ..\.venv\Scripts\python.exe mod_demo_apply.py
   ..\.venv\Scripts\python.exe mod_demo_node.py
   ```

   Первый скрипт заменяет первый фон, добавляет `[MOD]` в первую реплику и
   сохраняет `resources.assets.bak`. Второй добавляет в начало главы 1
   демонстрационную цепочку узлов с выборами, переменными, спрайтами, фонами,
   музыкой, SFX, затемнением и кастомным WAV-звуком.

3. Запустите игру обычным способом.

Можно использовать `run_demo.bat` для применения обоих изменений одной командой.

## Откат

```bat
..\.venv\Scripts\python.exe mod_demo_node.py --remove
..\.venv\Scripts\python.exe mod_demo_apply.py --revert
```

Для полного возврата исходного файла можно восстановить:

```text
LED HEARTS_Data\resources.assets.bak
```

## Извлечение и упаковка

Извлечь все `TextAsset`:

```bat
..\.venv\Scripts\python.exe extract_resources.py
```

Данные появятся в `modmaker\extracted`.

Сделать человекочитаемый текст главы:

```bat
..\.venv\Scripts\python.exe read_chapter.py --input extracted\101_chapter_01.json --format md
```

Проверить изменения без записи:

```bat
..\.venv\Scripts\python.exe repack_resources.py --dry-run
```

Записать отредактированные JSON обратно:

```bat
..\.venv\Scripts\python.exe repack_resources.py
```

Скрипты сами находят корень игры на уровень выше, поэтому расположение
`modmaker` в корне обязательно, а текущая рабочая папка не важна.

## Содержимое

- `mod_demo_apply.py` — замена первого фона и простой текстовый маркер.
- `mod_demo_node.py` — добавление демонстрационной цепочки узлов.
- `extract_resources.py` — извлечение TextAsset из `resources.assets`.
- `repack_resources.py` — запись изменённых TextAsset обратно.
- `read_chapter.py` — вывод главы в TXT/Markdown.
- `mod_start_bg.png` — демонстрационный фон.
- `mod_demo_jingle.wav` — кастомный звук, загружаемый игрой из корня.
- `requirements.txt` — зависимость `UnityPy`.
- `run_demo.bat` — применить оба демо-мода.

При применении `mod_demo_node.py` кастомный WAV автоматически копируется из
`modmaker` в корень игры: внешний загрузчик игры ищет его именно там.

Не переименовывайте `mod_start_bg.png` и `mod_demo_jingle.wav`: эти имена
используются сценарием и внешним загрузчиком игры.
