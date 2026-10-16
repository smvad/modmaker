using BepInEx;
using BepInEx.Configuration;
using BepInEx.Unity.IL2CPP;
using HarmonyLib;

namespace DlcRecursiveSearch;

[BepInPlugin("ledhearts.dlc.recursive-search", "DLC Recursive Search", "1.1.0")]
public class Plugin : BasePlugin
{
    private ConfigEntry<bool> _enabled;

    public override void Load()
    {
        _enabled = Config.Bind("General", "EnableRecursiveSearch", true,
            "Search dlc_* assets and nsfw_dlc.dat in all subfolders of the game root.");

        DlcIndex.Build(Paths.GameRootPath, Log);

        var harmony = new Harmony("ledhearts.dlc.recursive-search");
        Patches.ApplyAll(harmony, Log, () => _enabled.Value);

        Log.LogInfo($"DLC Recursive Search loaded, index holds {DlcIndex.Count} file(s)");
    }
}
