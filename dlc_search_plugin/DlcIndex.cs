using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using BepInEx.Logging;

namespace DlcRecursiveSearch;

/// <summary>
/// Index of external DLC files (dlc_*.png, dlc_*.wav, nsfw_dlc.dat) found
/// anywhere under the game root. Shallowest path wins, ties break by
/// ordinal order; duplicates are reported. Read-only: nothing is ever
/// written into the game root.
/// </summary>
internal static class DlcIndex
{
    private static readonly object Sync = new object();
    private static Dictionary<string, string> _byName =
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    private static FileSystemWatcher _watcher;
    private static Timer _debounce;
    private static string _root;
    private static ManualLogSource _log;

    public static string Root => _root;

    public static int Count
    {
        get { lock (Sync) { return _byName.Count; } }
    }

    public static void Build(string gameRoot, ManualLogSource log)
    {
        _root = gameRoot;
        _log = log;
        CleanupLegacyState(gameRoot);
        Rescan();
        try
        {
            _watcher = new FileSystemWatcher(gameRoot)
            {
                IncludeSubdirectories = true,
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite
                               | NotifyFilters.DirectoryName
            };
            _watcher.Created += OnFsEvent;
            _watcher.Deleted += OnFsEvent;
            _watcher.Renamed += OnFsRenamed;
            _watcher.Changed += OnFsEvent;
            _watcher.EnableRaisingEvents = true;
        }
        catch (Exception e)
        {
            log.LogWarning($"FileSystemWatcher disabled: {e.Message}");
        }
    }

    private static void OnFsEvent(object s, FileSystemEventArgs e) => ScheduleRescan();

    private static void OnFsRenamed(object s, RenamedEventArgs e) => ScheduleRescan();

    private static void OnTimer(object state) => Rescan();

    private static void ScheduleRescan()
    {
        lock (Sync)
        {
            if (_debounce != null)
                _debounce.Dispose();
            _debounce = new Timer(OnTimer, null, 1500, Timeout.Infinite);
        }
    }

    public static void Rescan()
    {
        var found = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
        try
        {
            foreach (var file in Directory.EnumerateFiles(_root, "*", SearchOption.AllDirectories))
            {
                var name = Path.GetFileName(file);
                if (!IsIndexed(name))
                    continue;
                if (!found.TryGetValue(name, out var list))
                {
                    list = new List<string>();
                    found[name] = list;
                }
                list.Add(file);
            }
        }
        catch (Exception e) when (e is UnauthorizedAccessException || e is IOException)
        {
            _log.LogWarning($"Scan cut short: {e.Message}");
        }

        var byName = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var kv in found)
        {
            var ordered = kv.Value
                .OrderBy(p => p.Count(c => c == Path.DirectorySeparatorChar))
                .ThenBy(p => p, StringComparer.Ordinal)
                .ToArray();
            byName[kv.Key] = ordered[0];
            if (ordered.Length > 1)
                _log.LogWarning($"Duplicate '{kv.Key}' in {ordered.Length} places, using '{ordered[0]}': {string.Join(", ", ordered.Skip(1))}");
        }

        lock (Sync)
        {
            _byName = byName;
        }
        _log.LogInfo($"DLC index: {byName.Count} file(s) under '{_root}'");
    }

    public static bool IsIndexed(string fileName)
    {
        if (fileName.Equals("nsfw_dlc.dat", StringComparison.OrdinalIgnoreCase))
            return true;
        if (!fileName.StartsWith("dlc_", StringComparison.OrdinalIgnoreCase))
            return false;
        var ext = Path.GetExtension(fileName);
        return ext.Equals(".png", StringComparison.OrdinalIgnoreCase)
               || ext.Equals(".wav", StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>Full path for an indexed file name, or null.</summary>
    public static string Find(string fileName)
    {
        lock (Sync)
        {
            return _byName.TryGetValue(fileName, out var path) ? path : null;
        }
    }

    /// <summary>
    /// Remove the state file left by v1.0.x (root-copy tracker).
    /// Root copies themselves are NOT deleted automatically: the user may
    /// have put real files there. Duplicates are reported as warnings
    /// by Rescan so they can be cleaned by hand.
    /// </summary>
    private static void CleanupLegacyState(string gameRoot)
    {
        try
        {
            var cfgDir = Path.Combine(gameRoot, "BepInEx", "config");
            var state = Path.Combine(cfgDir, "DlcRecursiveSearch.managed.txt");
            if (File.Exists(state))
            {
                File.Delete(state);
                _log.LogInfo("Removed legacy managed-copies state (v1.0.x); root is now read-only");
            }
        }
        catch (Exception e)
        {
            _log.LogWarning($"Legacy state cleanup failed: {e.Message}");
        }
    }
}
