using System;
using System.IO;
using System.Linq;
using System.Reflection;
using BepInEx.Logging;
using HarmonyLib;

namespace DlcRecursiveSearch;

/// <summary>
/// Harmony patches. Targets are resolved by reflection over the game's
/// Assembly-CSharp so the plugin survives namespace/refactoring drift
/// as long as method names stay.
/// </summary>
internal static class Patches
{
    private static ManualLogSource _log;
    private static Func<bool> _enabled;

    public static int Applied { get; private set; }

    public static void ApplyAll(Harmony harmony, ManualLogSource log, Func<bool> enabled)
    {
        _log = log;
        _enabled = enabled;

        var gameAsm = AppDomain.CurrentDomain.GetAssemblies()
            .FirstOrDefault(a => a.GetName().Name.Equals("Assembly-CSharp", StringComparison.Ordinal));
        if (gameAsm == null)
        {
            log.LogError("Assembly-CSharp not loaded, patches skipped");
            return;
        }

        PatchFirst(harmony, gameAsm, "LoadExternalDLCSprite",
            typeof(Patches).GetMethod(nameof(SpritePrefixInstance)),
            typeof(Patches).GetMethod(nameof(SpritePrefixStatic)));
        PatchFirst(harmony, gameAsm, "LoadExternalDLCAudio",
            typeof(Patches).GetMethod(nameof(AudioPrefixInstance)),
            typeof(Patches).GetMethod(nameof(AudioPrefixStatic)));
        PatchFirst(harmony, gameAsm, "IsNSFWDLCOwned",
            typeof(Patches).GetMethod(nameof(NsfwPostfixInstance)),
            typeof(Patches).GetMethod(nameof(NsfwPostfixStatic)));

        log.LogInfo($"Patches applied: {Applied}/3 (sprite, audio, nsfw)");
    }

    private static void PatchFirst(Harmony harmony, Assembly gameAsm, string methodName,
        MethodInfo instancePatch, MethodInfo staticPatch)
    {
        foreach (var type in gameAsm.GetTypes())
        {
            var target = type.GetMethods(BindingFlags.Public | BindingFlags.NonPublic
                                         | BindingFlags.Instance | BindingFlags.Static)
                .FirstOrDefault(m => m.Name.Equals(methodName, StringComparison.Ordinal)
                                     && !m.IsGenericMethodDefinition);
            if (target == null)
                continue;
            var patch = target.IsStatic ? staticPatch : instancePatch;
            try
            {
                if (patch.Name.Contains("Postfix"))
                    harmony.Patch(target, postfix: new HarmonyMethod(patch));
                else
                    harmony.Patch(target, prefix: new HarmonyMethod(patch));
                Applied++;
                _log.LogInfo($"Patched {type.FullName}.{target} (static={target.IsStatic})");
                return;
            }
            catch (Exception e)
            {
                _log.LogError($"Failed to patch {type.FullName}.{methodName}: {e.Message}");
            }
        }
        _log.LogError($"Target not found: {methodName}");
    }

    // ---- sprite: ensure root copy, let the original loader do its job ----

    public static void SpritePrefixInstance(object __instance, string spriteName)
    {
        EnsureRootCopy(spriteName, ".png");
    }

    public static void SpritePrefixStatic(string spriteName)
    {
        EnsureRootCopy(spriteName, ".png");
    }

    // ---- audio: same trick, original parses WAV itself ----

    public static void AudioPrefixInstance(object __instance, string clipName)
    {
        EnsureRootCopy(clipName, ".wav");
    }

    public static void AudioPrefixStatic(string clipName)
    {
        EnsureRootCopy(clipName, ".wav");
    }

    // ---- nsfw flag: OR the original result with recursive search ----

    public static void NsfwPostfixInstance(object __instance, ref bool __result)
    {
        NsfwPostfix(ref __result);
    }

    public static void NsfwPostfixStatic(ref bool __result)
    {
        NsfwPostfix(ref __result);
    }

    private static void NsfwPostfix(ref bool result)
    {
        if (result || !IsEnabled())
            return;
        if (DlcIndex.Find("nsfw_dlc.dat") != null)
        {
            result = true;
            _log.LogInfo("nsfw_dlc.dat resolved via recursive search");
        }
    }

    private static bool IsEnabled()
    {
        try { return _enabled?.Invoke() ?? true; }
        catch { return true; }
    }

    internal static void EnsureRootCopy(string baseName, string extension)
    {
        try
        {
            if (!IsEnabled() || string.IsNullOrEmpty(baseName))
                return;
            if (!baseName.StartsWith("dlc_", StringComparison.OrdinalIgnoreCase))
                return; // not ours: original behaviour untouched
            var root = DlcIndex.EnsureRootCopy(baseName + extension);
            if (root != null)
                _log.LogDebug($"'{baseName + extension}' available at '{root}'");
        }
        catch (Exception e)
        {
            _log.LogWarning($"EnsureRootCopy failed: {e.Message}");
        }
    }
}
