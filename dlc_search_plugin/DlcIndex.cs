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
/// ordinal order; duplicates are reported. Files copied into the root by
/// the plugin are tracked in a state file so stale copies are removed and
/// user-modified files are never touched.
/// </summary>
internal static class DlcIndex
{
    private sealed class ManagedEntry
    {
        public string Source;
        public long Size;
        public long MtimeUtcTicks;
    }

    private static readonly object Sync = new object();
    private static Dictionary<string, string> _byName =
        new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    private static readonly Dictionary<string, ManagedEntry> Managed =
        new Dictionary<string, ManagedEntry>(StringComparer.OrdinalIgnoreCase);
    private static FileSystemWatcher _watcher;
    private static Timer _debounce;
    private static string _root;
    private static string _statePath;
    private static ManualLogSource _log;

    public static string Root => _root;

    public static int Count
    {
        get { lock (Sync) { return _byName.Count; } }
    }

    public static void Build(string gameRoot, string statePath, ManualLogSource log)
    {
        _root = gameRoot;
        _statePath = statePath;
        _log = log;
        LoadState();
        Rescan();
        try
        {
            _watcher = new FileSystemWatcher(gameRoot)
            {
                IncludeSubdirectories = true,
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite
                               | NotifyFilters.DirectoryName
            };
            _watcher.Created += (_, __) => ScheduleRescan();
            _watcher.Deleted += (_, __) => ScheduleRescan();
            _watcher.Renamed += (_, __) => ScheduleRescan();
            _watcher.Changed += (_, __) => ScheduleRescan();
            _watcher.EnableRaisingEvents = true;
        }
        catch (Exception e)
        {
            log.LogWarning($"FileSystemWatcher disabled: {e.Message}");
        }
    }

    private static void ScheduleRescan()
    {
        lock (Sync)
        {
            _debounce?.Dispose();
            _debounce = new Timer(_ => Rescan(), null, 1500, Timeout.Infinite);
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
        ReconcileManaged();
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
    /// Make sure root/fileName exists and matches the index winner.
    /// Returns the root path when usable, else null.
    /// </summary>
    public static string EnsureRootCopy(string fileName)
    {
        var root = _root;
        if (root == null)
            return null;
        var dest = Path.Combine(root, fileName);
        var source = Find(fileName);
        lock (Sync)
        {
            if (source != null && SamePath(source, dest))
                return dest; // winner already lives in root
            if (source == null)
            {
                // No source anywhere: drop our stale copy if it is still ours.
                if (Managed.TryGetValue(fileName, out var stale) && IsOurs(dest, stale))
                    DeleteManaged(fileName, dest);
                return File.Exists(dest) ? dest : null;
            }
            if (Managed.TryGetValue(fileName, out var entry))
            {
                if (!IsOurs(dest, entry))
                {
                    // User replaced our copy: hands off, their file wins.
                    Managed.Remove(fileName);
                    SaveState();
                    _log.LogInfo($"'{fileName}' taken over by user, keeping their file");
                    return dest;
                }
                if (SourceMatches(source, entry))
                    return dest; // fresh already
            }
            else if (File.Exists(dest))
            {
                return dest; // user's own root file wins, don't overwrite
            }
            File.Copy(source, dest, true);
            Managed[fileName] = Stat(source);
            SaveState();
            return dest;
        }
    }

    private static void ReconcileManaged()
    {
        lock (Sync)
        {
            foreach (var name in Managed.Keys.ToArray())
            {
                var dest = Path.Combine(_root, name);
                var entry = Managed[name];
                if (!IsOurs(dest, entry))
                {
                    Managed.Remove(name); // taken over or deleted by user
                    continue;
                }
                // Recorded source still exists but changed under us.
                if (File.Exists(entry.Source) && !SourceMatches(entry.Source, entry))
                {
                    Refresh(name, dest, entry.Source);
                    continue;
                }
                // A different source became the index winner.
                var winner = _byName.TryGetValue(name, out var w) ? w : null;
                if (winner != null && !SamePath(winner, dest) && !SourceMatches(winner, entry))
                {
                    Refresh(name, dest, winner);
                    continue;
                }
                if (!File.Exists(entry.Source) && winner == null)
                {
                    // True orphan: our root copy is the only trace left.
                    DeleteManaged(name, dest);
                }
                // Else: keep tracking (the root copy may itself be the winner).
            }
            SaveState();
        }
    }

    private static void Refresh(string name, string dest, string source)
    {
        try
        {
            File.Copy(source, dest, true);
            Managed[name] = Stat(source);
            _log.LogInfo($"Refreshed '{name}' from '{source}'");
        }
        catch (Exception e)
        {
            _log.LogWarning($"Refresh of '{name}' failed: {e.Message}");
        }
    }

    private static ManagedEntry Stat(string source)
    {
        var fi = new FileInfo(source);
        return new ManagedEntry { Source = source, Size = fi.Length, MtimeUtcTicks = fi.LastWriteTimeUtc.Ticks };
    }

    private static bool SourceMatches(string source, ManagedEntry entry)
    {
        try
        {
            var fi = new FileInfo(source);
            return entry.Source.Equals(source, StringComparison.OrdinalIgnoreCase)
                   && entry.Size == fi.Length
                   && entry.MtimeUtcTicks == fi.LastWriteTimeUtc.Ticks;
        }
        catch { return false; }
    }

    private static bool IsOurs(string dest, ManagedEntry entry)
    {
        try
        {
            var fi = new FileInfo(dest);
            if (!fi.Exists)
                return false;
            return entry.Size == fi.Length && entry.MtimeUtcTicks == fi.LastWriteTimeUtc.Ticks;
        }
        catch { return false; }
    }

    private static void DeleteManaged(string name, string dest)
    {
        try
        {
            File.Delete(dest);
            _log.LogInfo($"Removed stale '{name}' (source gone)");
        }
        catch (Exception e)
        {
            _log.LogWarning($"Could not remove stale '{name}': {e.Message}");
        }
        Managed.Remove(name);
    }

    private static bool SamePath(string a, string b)
    {
        return string.Equals(
            Path.GetFullPath(a).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
            Path.GetFullPath(b).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
            StringComparison.OrdinalIgnoreCase);
    }

    private static void LoadState()
    {
        try
        {
            if (_statePath == null || !File.Exists(_statePath))
                return;
            foreach (var line in File.ReadAllLines(_statePath))
            {
                var parts = line.Split('|');
                if (parts.Length != 4)
                    continue;
                if (!long.TryParse(parts[2], out var size) || !long.TryParse(parts[3], out var ticks))
                    continue;
                Managed[parts[0]] = new ManagedEntry { Source = parts[1], Size = size, MtimeUtcTicks = ticks };
            }
        }
        catch (Exception e)
        {
            _log.LogWarning($"State load failed: {e.Message}");
        }
    }

    private static void SaveState()
    {
        try
        {
            if (_statePath == null)
                return;
            Directory.CreateDirectory(Path.GetDirectoryName(_statePath));
            File.WriteAllLines(_statePath, Managed.Select(kv =>
                $"{kv.Key}|{kv.Value.Source}|{kv.Value.Size}|{kv.Value.MtimeUtcTicks}"));
        }
        catch (Exception e)
        {
            _log.LogWarning($"State save failed: {e.Message}");
        }
    }
}
