using System.Collections.Generic;
using BepInEx;
using BepInEx.Unity.IL2CPP;
using UnityEngine;

namespace GalleryUnlock;

[BepInPlugin("ledhearts.gallery.unlock-temp", "Gallery Unlock (temp)", "1.0.0")]
public class Plugin : BasePlugin
{
    // Full CG list: chapters 01+02 backgroundImage cg_* (20 шт).
    private static readonly string[] Cgs = new[]
    {
        "cg_cafeteria_first", "cg_first_wakeup", "cg_kiv_corridor", "cg_kiv_fall",
        "cg_kiv_good_end", "cg_kiv_manga", "cg_kiv_strangle", "cg_milly_forgot",
        "cg_milly_hacked_hug", "cg_milly_hug", "cg_milly_pat", "cg_milly_sad",
        "cg_milly_shutdown", "cg_milly_true_hug", "cg_other_classroom", "cg_tower",
        "cg_violetta_bump", "cg_violetta_library_sleep", "cg_violetta_warning", "cg_zoo_end",
    };

    public override void Load()
    {
        int opened = 0;
        foreach (var cg in Cgs)
        {
            var prefsKey = "vn_var_cg_seen_" + cg;
            if (PlayerPrefs.GetInt(prefsKey, 0) != 1)
                PlayerPrefs.SetInt(prefsKey, 1);
            opened++;
        }

        // vn_tracked_vars хранит сырые имена без префикса vn_var_.
        var raw = PlayerPrefs.GetString("vn_tracked_vars", "");
        var have = new HashSet<string>(raw.Split(',', System.StringSplitOptions.RemoveEmptyEntries));
        bool changed = false;
        foreach (var cg in Cgs)
        {
            var name = "cg_seen_" + cg;
            if (have.Add(name)) changed = true;
        }
        if (changed)
            PlayerPrefs.SetString("vn_tracked_vars", string.Join(",", have));
        PlayerPrefs.Save();

        var check = PlayerPrefs.GetString("vn_tracked_vars", "");
        Log.LogInfo($"GalleryUnlock: set {opened}/20 cg_seen vars, tracked_vars now {check.Split(',').Length} entries");
    }
}
