# DlcRecursiveSearch — рекурсивный поиск DLC-ассетов (BepInEx-плагин)

Ванильная игра ищет внешние ассеты **только в корне** (рядом с
`LED HEARTS.exe`): `VNSceneSetup.LoadExternalDLCSprite`,
`VNSceneSetup.LoadExternalDLCAudio` и проверка `nsfw_dlc.dat`
(`DialogueManager.IsNSFWDLCOwned`). Плагин находит `dlc_*.png`,
`dlc_*.wav` и `nsfw_dlc.dat` **в любой подпапке** корня игры.

## Как работает

- При старте строится индекс всех подходящих файлов под корнем игры.
  Побеждает самый мелкий путь, далее — ordinal; дубли — warning в лог
  со списком всех мест.
- Спрайты/аудио: Harmony-префикс грузит выигравший файл **напрямую
  из его подпапки** (`Texture2D.LoadImage` → `Sprite.Create` с pivot 0.5;
  WAV разбирается встроенным парсером PCM 8/16/24/32 + IEEE float →
  `AudioClip.Create` + `SetData`) и пропускает оригинальный загрузчик.
  **В корень игры ничего не пишется.** Цели ищутся по имени метода через
  рефлексию; аргумент маппится позиционно (`__0`), возврат — через
  `__result`, так что переименование параметров в игре не страшно.
- Если файла нет в индексе или прямая загрузка не удалась — управление
  отдаётся ванильному загрузчику (включая его warning), поведение игры
  для остальных имён не меняется.
- `nsfw_dlc.dat`: постфикс делает OR поверх оригинальной проверки,
  в корень ничего не пишется.
- State-файл v1.0.x (`BepInEx/config/DlcRecursiveSearch.managed.txt`)
  при старте удаляется; корневые копии за собой НЕ трогаем (там могут
  быть файлы пользователя) — дубли корня против подпапок видны как
  warning в логе, чистить руками.
- Имена без префикса `dlc_` игнорируются (кроме `nsfw_dlc.dat`);
  поведение игры для них не меняется. Отключается конфигом
  `BepInEx/config/ledhearts.dlc.recursive-search.cfg`
  (`EnableRecursiveSearch = false`).

## Установка с нуля (чистая машина)

1. Поставьте BepInEx 6 для IL2CPP-игр: свежий `BepInEx-Unity.IL2CPP-win-x64`
   (ветка 6.0.0, bleeding edge) с официального сайта сборок BepInEx,
   распакуйте архив **в корень игры** (рядом с `LED HEARTS.exe`) —
   появятся `winhttp.dll`, `.doorstop_version`, `doorstop_config.ini`, `BepInEx/`, `dotnet/`.
2. Запустите игру один раз и дождитесь меню: BepInEx сам сгенерирует
   interop-сборки для Unity 6000.3.11f1 в `BepInEx/interop/`
   (нужен интернет — докачиваются базовые Unity-библиотеки), затем
   закройте игру.
3. Соберите плагин (нужен .NET SDK 8+, см. ниже) и положите
   `DlcRecursiveSearch.dll` в `BepInEx\plugins\`.
4. Проверка: положите `dlc_*.png` в любую подпапку, запустите игру —
   в `BepInEx\LogOutput.log` должны быть `DLC index: N file(s)`,
   три `Patched ...` и `Patches applied: 3/3`.
5. Удаление: стереть `winhttp.dll`, `.doorstop_version`,
   `doorstop_config.ini`, `BepInEx/`, `dotnet/` (сейвы и ассеты игры
   не трогаются).

## Сборка плагина

Нужен только .NET SDK 8+ и установленный BepInEx (ссылки в проекте —
относительные, на `..\..\BepInEx\core` и `..\..\BepInEx\interop`,
NuGet не нужен, интернет не нужен):

```bat
dotnet build modmaker\dlc_search_plugin\DlcRecursiveSearch.csproj -c Release
```

Выход: `modmaker\dlc_search_plugin\bin\Release\net6.0\DlcRecursiveSearch.dll`
(`bin/`/`obj/` в `.gitignore`, не коммитятся).

> Ловушка сборки (проверено): interop-сборки вшивают свои
> `NullableAttribute`/`NullableContextAttribute`, поэтому **лямбды в
> обработчиках событий и `Timer` не компилируются** (CS0656) — только
> именованные методы (`OnFsEvent`, `OnTimer`). LINQ-лямбды (`Func<>`)
> безопасны.

## Демо в начале главы 1 (установлено в игре, не в репозитории)

Первая строка узла `start` главы `chapter_01` показывает
`dlc_recursive_proof` из `DLC\test\` с подписью: новая игра → первый
кадр. Убрать: удалить первую строку узла `start` в `101_chapter_01.json`
и сделать repack (бэкап ванилы — `resources.assets.bak`).

## Проверено (v1.1.0, без копий в корень)

- WAV-парсер: стерео 44100/16 + 3× моно 44100/16 из игры — все ок,
  число сэмплов = frames×channels, первые сэмплы совпали с эталоном
  (`struct.unpack`), мусор отклоняется (юнит-тест через тот же
  `DlcLoaders.cs`, скомпилированный в консольный проект).
- Игра (дальше — живой прогон): индекс, `Patches applied: 3/3`,
  `nsfw_dlc.dat` из `DLC/` → `dlc_nsfw_enabled = 1`, новых файлов в корне
  нет, legacy `DlcRecursiveSearch.managed.txt` удалён при старте.

Старые проверки v1.0.x (копирование в корень) больше не применимы:
прямого вызова загрузчиков из игры, state-файла, refresh/takeover/orphan
(9/9) — логика удалена вместе с копиями.

## Приложение: как BepInEx собран здесь без интернета

Обычному пользователю это не нужно (ставь официальный архив, см.
выше). Здесь скачивание сборок/фидов было недоступно, поэтому:
BepInEx собран из исходников (master 01.09.2026), Cpp2IL — тоже из
исходников (свежий, понимает метаданные v39 Unity 6),
недостающие пакеты заменены локальными сборками (Disarm из исходников,
`Il2CppInterop.ReferenceLibs` — сгенерированными `Il2Cpp*.dll`).
Interop сгенерирован заранее в два этапа (Cpp2IL→dummy на
AsmResolver 6.0.1, затем Il2CppInterop.Generator 1.5.3 на AsmResolver
6.0.0-beta.5 — иначе конфликт абстрактного `ProbeAssemblyFilePath`),
`unity-libs` взяты из `Managed/*.dll` dev-билда с тем же движком.
В исходник BepInEx внесён минимальный патч: при наличии
`BepInEx/interop/offline-generated.txt` регенерация и скачивание
unity-libs при запуске пропускаются.
