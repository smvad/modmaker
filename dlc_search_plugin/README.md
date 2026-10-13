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
  (декодирование PNG/WAV не тронуто, сигнатуры оригинала не нужны —
  цели ищутся по имени метода через рефлексию).
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

## Установка

BepInEx 6 (Unity.IL2CPP) уже разложен в корне игры:

```text
LED HEARTS/
  winhttp.dll                 <- Doorstop 4.5.0, грузится сам при старте
  .doorstop_version
  doorstop_config.ini         <- target BepInEx\core\BepInEx.Unity.IL2CPP.dll
  dotnet/                     <- mini-coreclr 6.0.7
  BepInEx/
    core/                     <- рантайм (32 файла)
    plugins/DlcRecursiveSearch.dll
    interop/                  <- interop для 6000.3.11f1 + offline-generated.txt
    config/                   <- BepInEx.cfg + managed.txt + конфиг плагина
    patchers/                 <- пусто
```

Плагин: собрать (см. ниже) и положить `DlcRecursiveSearch.dll` в
`BepInEx\plugins\`. Удаление BepInEx = стереть `winhttp.dll`,
`.doorstop_version`, `doorstop_config.ini`, `BepInEx/`, `dotnet/`
(сейвы и ассеты игры не трогаются).

## Сборка плагина

Нужен .NET SDK 8+ (проверено на 8.0.425 и 10.0.401), интернет не нужен:
в проекте только DLL-ссылки на уже установленный `BepInEx/core`
(относительные пути — собирается на любой машине с такой раскладкой):

```bat
dotnet build modmaker\dlc_search_plugin\DlcRecursiveSearch.csproj -c Release
```

Выход: `modmaker\dlc_search_plugin\bin\Release\net6.0\DlcRecursiveSearch.dll`
(`bin/`/`obj/` в `.gitignore`, не коммитятся).
Цели патчей (`LoadExternalDLCSprite`, `LoadExternalDLCAudio`,
`IsNSFWDLCOwned`) резолвятся в рантайме по имени — сгенерированный
interop для сборки не нужен.

## Проверка

1. Положить `dlc_*.png` в любую подпапку (напр. `DLC\test\`).
2. Запустить игру. В `BepInEx\LogOutput.log` должны быть:
   `DLC index: N file(s)`, три `Patched ...`, `Patches applied: 3/3`.
3. Сослаться на имя без расширения из главы
   (`"backgroundImage": "dlc_test_recursive"`) — префикс доложит файл
   в корень (запись в state-файле), игра загрузит как обычно.
4. Факт из этой установки (Unity 6000.3.11f1): пробник вызвал оба
   загрузчика напрямую — спрайт 1920px и клип 1.8с из `DLC\test\`
   загрузились, копии и state на месте, ошибок нет. Файловая логика
   (shallowest-wins, refresh, takeover, orphan) покрыта тестами 9/9.

## Демо в начале главы 1 (установлено в игре, не в репозитории)

Первая строка узла `start` главы `chapter_01` показывает
`dlc_recursive_proof` из `DLC\test\` с подписью: новая игра → первый
кадр. Убрать: удалить первую строку узла `start` в `101_chapter_01.json`
и сделать repack (бэкап ванилы — `resources.assets.bak`).

## Как собран BepInEx (офлайн, особенности)

- Исходники: BepInEx `5b766a3` (master, 01.09.2026), Cpp2IL `b5ad444`
  (12.09.2026, нужен для метаданных v39), Disarm `9f2061e` (исходники,
  т.к. в пакете master.99 нет мнемоник `BTI_C/BTI_J/BTI_JC/UDF`).
- SDK: сначала 8.0.425 (не взял C#14 в Cpp2IL), итог — 10.0.401
  (портативный, без админки). NuGet — только локальный фид
  (~230 пакетов) + `--ignore-failed-sources`, сеть была с рваным TLS.
- Замены недоступных пакетов: `Samboy063.Cpp2IL.Core dev.1452` →
  DLL-референс на source-built netstandard2.0;
  `Il2CppInterop.ReferenceLibs 1.0.0` → сгенерированные `Il2Cpp*.dll`;
  `Disarm master.117` → source-built Disarm (пины `.99` не хватило).
- Interop сгенерирован в два этапа (из-за абстрактного
  `ProbeAssemblyFilePath` в AsmResolver 6.0.1 против генератора 1.5.3):
  1) Cpp2IL→dummy-DLL на AsmResolver 6.0.1;
  2) Il2CppInterop.Generator 1.5.3 на AsmResolver 6.0.0-beta.5 читает
  dummy с диска. 70 dummy → 70 interop (включая `Assembly-CSharp`,
  `Il2Cppmscorlib`, `Il2CppSystem*`).
- `unity-libs` для генератора: `Managed/*.dll` старого билда
  (`C:\fff\Windows`, тот же движок 6000.3.11f1) → `6000.3.11f1.zip`.
- Патч исходника BepInEx (`Il2CppInteropManager`): при наличии
  `BepInEx/interop/offline-generated.txt` регенерация и скачивание
  unity-libs пропускаются — первый запуск работает офлайн.
- Урезанные TFM (временные клоны, на игру не влияют): убраны net35
  (BepInEx.Core/Preloader/Unity.Common → только netstandard2.0),
  Cpp2IL/LibCpp2IL/WasmDisassembler → `net8.0;netstandard2.0`,
  Disarm `System.Memory` 4.5.5→4.6.3. Таргетинг-паки net6.0/net8.0
  (App.Ref/Desktop/AspNet/Host 6.0.36/8.0.31) докачаны в фид.
