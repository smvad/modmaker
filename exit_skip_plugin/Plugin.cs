using System;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using BepInEx;
using BepInEx.Configuration;
using BepInEx.Logging;
using BepInEx.Unity.IL2CPP;
using HarmonyLib;
using UnityEngine;

namespace ExitSkip;

[BepInPlugin("ledhearts.exit.skip", "Exit Skip", "1.0.5")]
public class Plugin : BasePlugin
{
    internal static ManualLogSource L;
    internal static ConfigEntry<bool> Enabled;
    private static volatile bool _forceQuit;
    private static bool _captchaWas;
    private static bool _horrorWas;
    private static long _captchaSince;
    private static long _horrorSince;
    // Буфер после появления экрана: клик/нажатие, которым экран открыли,
    // не должны сразу же его пропускать.
    private const long GraceMs = 1000;
    // Клавиши-переключатели: у них младший бит GetAsyncKeyState — это
    // состояние (вкл/выкл, NumLock обычно включён), а не факт нажатия.
    private static readonly int[] ToggleKeys = { 0x14, 0x90, 0x91 };

    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int vKey);

    public override void Load()
    {
        L = Log;
        Enabled = Config.Bind("General", "Enabled", true,
            "Skip the exit captcha / ТАК И ЗНАЛ screen with any key or mouse button.");
        try
        {
            var gameAsm = AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(a => a.GetName().Name.Equals("Assembly-CSharp", StringComparison.Ordinal));
            if (gameAsm == null)
            {
                L.LogError("Assembly-CSharp not loaded, ExitSkip disabled");
                return;
            }
            var harmony = new Harmony("ledhearts.exit.skip");
            int applied = 0;
            foreach (var t in gameAsm.GetTypes())
            {
                if (t.FullName != "AIVisualNovel.UI.VNSceneSetup")
                    continue;
                applied += Patch(harmony, t, "Update",
                    typeof(Plugin).GetMethod(nameof(UpdatePostfix), BindingFlags.Static | BindingFlags.NonPublic), postfix: true);
                applied += Patch(harmony, t, "OpenExitCaptcha",
                    typeof(Plugin).GetMethod(nameof(OpenPrefix), BindingFlags.Static | BindingFlags.NonPublic), postfix: false);
                applied += Patch(harmony, t, "PlayExitHorrorCo",
                    typeof(Plugin).GetMethod(nameof(HorrorPrefix), BindingFlags.Static | BindingFlags.NonPublic), postfix: false);
            }
            L.LogInfo($"Exit Skip loaded, patches: {applied}/3 (enabled={Enabled.Value})");
        }
        catch (Exception e)
        {
            L.LogError($"ExitSkip failed: {e}");
        }
    }

    private static int Patch(Harmony harmony, Type type, string methodName, MethodInfo patch, bool postfix)
    {
        var target = type.GetMethods(BindingFlags.Public | BindingFlags.NonPublic
                                     | BindingFlags.Instance | BindingFlags.Static)
            .FirstOrDefault(m => m.Name.Equals(methodName, StringComparison.Ordinal)
                                 && m.GetParameters().Length == 0);
        if (target == null)
        {
            L.LogError($"Target not found: {type.FullName}.{methodName}");
            return 0;
        }
        if (postfix)
            harmony.Patch(target, postfix: new HarmonyMethod(patch));
        else
            harmony.Patch(target, prefix: new HarmonyMethod(patch));
        L.LogInfo($"Patched {type.FullName}.{target.Name} (static={target.IsStatic})");
        return 1;
    }

    private static bool OpenPrefix()
    {
        // After a skip, the Exit menu button quits directly instead of reopening the captcha.
        if (!Enabled.Value || !_forceQuit)
            return true;
        try
        {
            L.LogInfo("ExitSkip: exit requested after skip, quitting directly");
            Application.Quit();
        }
        catch (Exception e)
        {
            L.LogWarning($"ExitSkip quit failed: {e.GetType().Name}: {e.Message}");
        }
        return false;
    }

    private static bool HorrorPrefix()
    {
        if (!Enabled.Value || !_forceQuit)
            return true;
        return false;
    }

    private static void UpdatePostfix(object __instance)
    {
        try
        {
            if (!Enabled.Value || __instance == null)
                return;
            GameObject panel = null;
            try
            {
                panel = __instance.GetType().GetProperty("exitCaptchaPanel")
                    ?.GetValue(__instance, null) as GameObject;
            }
            catch (Exception e)
            {
                L.LogWarning($"ExitSkip panel lookup failed: {e.GetType().Name}: {e.Message}");
                return;
            }
            bool captchaActive = panel != null && panel.activeInHierarchy;
            GameObject horror = FindHorror();
            bool horrorActive = horror != null && horror.activeInHierarchy;
            if (!captchaActive && !horrorActive)
            {
                _captchaWas = false;
                _horrorWas = false;
                return;
            }
            long now = Environment.TickCount64;
            if (captchaActive && !_captchaWas)
            {
                _captchaWas = true;
                _captchaSince = now;
                PrimeKeys(); // swallow presses that opened the screen
            }
            if (horrorActive && !_horrorWas)
            {
                _horrorWas = true;
                _horrorSince = now;
                PrimeKeys(); // the captcha click must not skip the horror
            }
            if (!captchaActive)
                _captchaWas = false;
            if (!horrorActive)
                _horrorWas = false;
            if ((captchaActive && now - _captchaSince < GraceMs)
                || (horrorActive && now - _horrorSince < GraceMs))
                return; // буфер: даём экрану показаться
            int vk = AnyKeyPressed();
            if (vk < 0)
                return;
            _forceQuit = true;
            L.LogInfo($"ExitSkip: skip pressed (vk=0x{vk:X2}, horror={horrorActive}, captcha={captchaActive}), quitting");
            try { if (horror != null) horror.SetActive(false); }
            catch (Exception e) { L.LogWarning($"ExitSkip hide horror failed: {e.GetType().Name}: {e.Message}"); }
            try { if (panel != null) panel.SetActive(false); }
            catch (Exception e) { L.LogWarning($"ExitSkip hide captcha failed: {e.GetType().Name}: {e.Message}"); }
            try { Application.Quit(); }
            catch (Exception e) { L.LogWarning($"ExitSkip quit failed: {e.GetType().Name}: {e.Message}"); }
        }
        catch (Exception e)
        {
            L.LogWarning($"ExitSkip update failed: {e.GetType().Name}: {e.Message}");
        }
    }

    private static GameObject FindHorror()
    {
        try
        {
            foreach (var go in UnityEngine.Object.FindObjectsOfType<GameObject>())
            {
                if (go != null && go.name.Contains("Horror"))
                    return go;
            }
        }
        catch (Exception e)
        {
            L.LogWarning($"ExitSkip horror scan failed: {e.GetType().Name}: {e.Message}");
        }
        return null;
    }

    private static void PrimeKeys()
    {
        try
        {
            for (int v = 1; v <= 254; v++)
            {
                if (Array.IndexOf(ToggleKeys, v) >= 0)
                    continue;
                GetAsyncKeyState(v);
            }
        }
        catch { }
    }

    // Код нажатой с прошлого опроса клавиши/кнопки, или -1.
    private static int AnyKeyPressed()
    {
        try
        {
            for (int v = 1; v <= 254; v++)
            {
                if (Array.IndexOf(ToggleKeys, v) >= 0)
                    continue;
                if ((GetAsyncKeyState(v) & 1) != 0)
                    return v;
            }
        }
        catch (Exception e)
        {
            L.LogWarning($"ExitSkip key poll failed: {e.GetType().Name}: {e.Message}");
        }
        return -1;
    }
}
