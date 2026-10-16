using System;
using System.Linq;
using System.Reflection;
using BepInEx.Logging;
using HarmonyLib;
using UnityEngine;

namespace DlcRecursiveSearch;

/// <summary>
/// Harmony patches. Targets are resolved by reflection over the game's
/// Assembly-CSharp so the plugin survives namespace/refactoring drift
/// as long as method names stay.
///
/// Sprite/audio prefixes load the indexed file directly from its subfolder
/// and skip the vanilla root-only loader (return false). When we have
/// nothing to offer, they return true so vanilla behaviour (including its
/// warnings) is untouched. Nothing is ever written to the game root.
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
        DlcLoaders.Init(log);

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

    // ---- sprite: direct load from index, skip vanilla on success ----
    // __0 = first string arg by position (param name may differ per build).

    public static bool SpritePrefixInstance(object __instance, string __0, ref Sprite __result)
    {
        return SpritePrefix(__0, ref __result);
    }

    public static bool SpritePrefixStatic(string __0, ref Sprite __result)
    {
        return SpritePrefix(__0, ref __result);
    }

    private static bool SpritePrefix(string baseName, ref Sprite __result)
    {
        try
        {
            if (!IsEnabled() || string.IsNullOrEmpty(baseName))
                return true;
            if (!baseName.StartsWith("dlc_", StringComparison.OrdinalIgnoreCase))
                return true; // not ours: vanilla behaviour untouched
            var path = DlcIndex.Find(baseName + ".png");
            if (path == null)
                return true; // let vanilla emit its warning
            if (DlcLoaders.TryLoadSprite(path, out var sprite) && sprite != null)
            {
                __result = sprite;
                _log.LogDebug($"'{baseName}.png' loaded directly from '{path}'");
                return false; // skip vanilla loader
            }
            return true; // corrupt file: fall back to vanilla warning
        }
        catch (Exception e)
        {
            _log.LogWarning($"SpritePrefix failed: {e.Message}");
            return true;
        }
    }

    // ---- audio: same trick, we parse the WAV ourselves ----

    public static bool AudioPrefixInstance(object __instance, string __0, ref AudioClip __result)
    {
        return AudioPrefix(__0, ref __result);
    }

    public static bool AudioPrefixStatic(string __0, ref AudioClip __result)
    {
        return AudioPrefix(__0, ref __result);
    }

    private static bool AudioPrefix(string baseName, ref AudioClip __result)
    {
        try
        {
            if (!IsEnabled() || string.IsNullOrEmpty(baseName))
                return true;
            if (!baseName.StartsWith("dlc_", StringComparison.OrdinalIgnoreCase))
                return true;
            var path = DlcIndex.Find(baseName + ".wav");
            if (path == null)
                return true;
            if (DlcLoaders.TryLoadAudio(path, out var clip) && clip != null)
            {
                __result = clip;
                _log.LogDebug($"'{baseName}.wav' loaded directly from '{path}'");
                return false;
            }
            return true;
        }
        catch (Exception e)
        {
            _log.LogWarning($"AudioPrefix failed: {e.Message}");
            return true;
        }
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
}
