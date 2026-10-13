# DlcRecursiveSearch — BepInEx-плагин рекурсивного поиска DLC-ассетов

Игра ищет внешние ассеты только в корне (рядом с `LED HEARTS.exe`):
`VNSceneSetup.LoadExternalDLCSprite`, `VNSceneSetup.LoadExternalDLCAudio`
и `DialogueManager.IsNSFWDLCOwned`. Плагин находит `dlc_*.png`,
`dlc_*.wav` и `nsfw_dlc.dat` **в любой подпапке** корня игры:

- спрайты/аудио: префикс перед оригинальным загрузчиком докладывает
  выигравший файл в корень, дальше грузит сама игра (декодирование
  не тронуто);
- `nsfw_dlc.dat`: постфикс делает OR поверх оригинальной проверки,
  в корень ничего не пишется.

Правила: побеждает самый мелкий путь, далее — ordinal; дубли —
warning в лог. Свои копии в корне отслеживаются
(`BepInEx/config/DlcRecursiveSearch.managed.txt`): протухшие удаляются,
заменённые пользователем — не трогаются. Файлы без префикса `dlc_`
игнорируются, поведение игры для них не меняется.

## Сборка

Нужен .NET SDK (8+) и установленный BepInEx (ссылки — на его `core/`):

```bat
dotnet build modmaker\dlc_search_plugin\DlcRecursiveSearch.csproj -c Release
```

Выход `modmaker\dlc_search_plugin\bin\Release\net6.0\DlcRecursiveSearch.dll`
положить в `BepInEx\plugins\`. В `bin/`/`obj/` ничего коммитить не надо
(закрыто `.gitignore`).

## Установка BepInEx (как это сделано здесь)

BepInEx 6 собран из исходников офлайн (см. историю в корне репозитория
модмейкера у владельца): Doorstop 4.5.0 (`winhttp.dll`,
`doorstop_config.ini`), mini-coreclr 6.0.7 (`dotnet/`), interop для
Unity 6000.3.11f1 сгенерирован заранее (`BepInEx/interop/` +
`offline-generated.txt`, регенерация при запуске пропущена).
Файлы в корне игры: `winhttp.dll`, `.doorstop_version`,
`doorstop_config.ini`, каталоги `BepInEx/`, `dotnet/`.
Удаление = стереть их (сейвы и ассеты игры не трогаются).

## Проверка

1. Положить `dlc_test_recursive.png` в подпапку (напр. `DLC\test\`).
2. Запустить игру. В `BepInEx\LogOutput.log` должны быть:
   `DLC index: N file(s)`, `Patched ... LoadExternalDLCSprite`,
   `Patched ... LoadExternalDLCAudio`, `Patched ... IsNSFWDLCOwned`.
3. Сослаться на имя без расширения из главы
   (`"backgroundImage": "dlc_test_recursive"`) — префикс доложит файл
   в корень, игра загрузит как обычно.
4. Логика индекса покрыта тестами `TestDlcIndex` (8/8, без игры).

## Тестовая геймплей-проверка

Добавить строку со спрайтом из подпапки в главу (см. `INSTRUCTIONS.md`),
дойти до неё в игре: спрайт должен показаться, а в корне игры —
появиться его копия. После выхода лишние копии удаляются сами при
удалении исходника (rescan), ручные файлы в корне не трогаются.
