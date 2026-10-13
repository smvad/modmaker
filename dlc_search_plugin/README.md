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
- Спрайты/аудио: Harmony-префикс перед оригинальным загрузчиком
  докладывает выигравший файл в корень, дальше грузит сама игра
  (декодирование PNG/WAV не тронуто; цели ищутся по имени метода через
  рефлексию, сгенерированный interop для сборки не нужен).
- `nsfw_dlc.dat`: постфикс делает OR поверх оригинальной проверки,
  в корень ничего не пишется.
- Свои копии в корне отслеживаются
  (`BepInEx/config/DlcRecursiveSearch.managed.txt`): при изменении
  исходника копия обновляется, при удалении исходника — удаляется,
  файл, заменённый пользователем вручную, не трогается никогда.
- Имена без префикса `dlc_` игнорируются (кроме `nsfw_dlc.dat`);
  поведение игры для них не меняется. Отключается конфигом
  `BepInEx/config/ledhearts.dlc.recursive-search.cfg`
  (`EnableRecursiveSearch = false`).

## Установка с нуля (чистая машина)

1. Поставьте BepInEx 6 для IL2CPP-игр: свежий `BepInEx-Unity.IL2CPP-win-x64`
   (ветка 6.0.0, bleeding edge) с официального сайта сборок BepInEx,
   распакуйте архив **в корень игры** (рядом с `LED HEARTS.exe`) —
   появятся `winhttp.dll`, `doorstop_config.ini`, `BepInEx/`, `dotnet/`.
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
относительные, на `..\..\BepInEx\core`, NuGet не нужен, интернет не нужен):

```bat
dotnet build modmaker\dlc_search_plugin\DlcRecursiveSearch.csproj -c Release
```

Выход: `modmaker\dlc_search_plugin\bin\Release\net6.0\DlcRecursiveSearch.dll`
(`bin/`/`obj/` в `.gitignore`, не коммитятся).

## Демо в начале главы 1 (установлено в игре, не в репозитории)

Первая строка узла `start` главы `chapter_01` показывает
`dlc_recursive_proof` из `DLC\test\` с подписью: новая игра → первый
кадр. Убрать: удалить первую строку узла `start` в `101_chapter_01.json`
и сделать repack (бэкап ванилы — `resources.assets.bak`).

## Проверено

- Unity 6000.3.11f1, BepInEx 6, mini-coreclr 6.0.7: прямой вызов обоих
  загрузчиков из игры — спрайт 1920px и клип 1.8с из подпапки
  загрузились, копии и state-файл на месте, ошибок нет.
- `nsfw_dlc.dat` из подпапки: игра выставила `dlc_nsfw_enabled = 1`.
- Файловая логика (shallowest-wins, refresh, takeover, orphan): 9/9.

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
