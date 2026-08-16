using System.Diagnostics;
using System.Text.RegularExpressions;
using Microsoft.Win32;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Shell;

public sealed class MXBikesService : IMXBikesService
{
    public event EventHandler<MXBikesEnvironment>? EnvironmentChanged;
    public event EventHandler<MXBikeSelection>? SelectionChanged;
    public event EventHandler? ContentChanged;

    public async Task<MXBikesEnvironment> DetectEnvironmentAsync(CancellationToken cancellationToken = default)
    {
        var env = await Task.Run(DetectEnvironment, cancellationToken);
        EnvironmentChanged?.Invoke(this, env);
        return env;
    }

    public async Task<MXBikeSelection> ReadActiveSelectionAsync(CancellationToken cancellationToken = default)
    {
        var env = await DetectEnvironmentAsync(cancellationToken);
        var selection = await Task.Run(() => ReadSelection(env.ProfileIniPath), cancellationToken);
        SelectionChanged?.Invoke(this, selection);
        return selection;
    }

    public async Task ApplySelectionAsync(MXBikeSelection selection, CancellationToken cancellationToken = default)
    {
        var env = await DetectEnvironmentAsync(cancellationToken);
        if (string.IsNullOrWhiteSpace(env.ProfileIniPath) || !File.Exists(env.ProfileIniPath))
            throw new InvalidOperationException("MX Bikes profile.ini was not found.");

        await Task.Run(() => WriteSelection(env.ProfileIniPath, selection), cancellationToken);
        SelectionChanged?.Invoke(this, selection);
    }

    public async Task<IReadOnlyList<MXContentItem>> ScanInstalledContentAsync(CancellationToken cancellationToken = default)
    {
        var env = await DetectEnvironmentAsync(cancellationToken);
        var result = await Task.Run(() => ScanContent(env), cancellationToken);
        ContentChanged?.Invoke(this, EventArgs.Empty);
        return result;
    }

    public async Task LaunchGameAsync(CancellationToken cancellationToken = default)
    {
        var env = await DetectEnvironmentAsync(cancellationToken);
        if (string.IsNullOrWhiteSpace(env.GameExecutable) || !File.Exists(env.GameExecutable))
            throw new InvalidOperationException("MX Bikes executable was not found.");

        Process.Start(new ProcessStartInfo(env.GameExecutable)
        {
            WorkingDirectory = env.GameInstallDirectory,
            UseShellExecute = true
        });
    }

    public async Task LaunchRaceAsync(string host, int port, string? password = null, CancellationToken cancellationToken = default)
    {
        var env = await DetectEnvironmentAsync(cancellationToken);
        if (string.IsNullOrWhiteSpace(env.GameExecutable) || !File.Exists(env.GameExecutable))
            throw new InvalidOperationException("MX Bikes executable was not found.");

        var args = $"-directconnect {Quote(host)} {port}";
        if (!string.IsNullOrWhiteSpace(password)) args += $" {Quote(password)}";
        Process.Start(new ProcessStartInfo(env.GameExecutable, args)
        {
            WorkingDirectory = env.GameInstallDirectory,
            UseShellExecute = false
        });
    }

    private static MXBikesEnvironment DetectEnvironment()
    {
        var userRoot = FindUserRoot();
        var globalIni = Path.Combine(userRoot, "global.ini");
        var globalText = SafeRead(globalIni);
        var activeProfile = IniValue(globalText, "profile", "lastprofile");
        if (string.IsNullOrWhiteSpace(activeProfile)) activeProfile = IniValue(globalText, "profile", "nickname");

        var profiles = Path.Combine(userRoot, "profiles");
        if (string.IsNullOrWhiteSpace(activeProfile) && Directory.Exists(profiles))
        {
            var candidates = Directory.EnumerateDirectories(profiles)
                .Where(p => File.Exists(Path.Combine(p, "profile.ini"))).Take(2).ToArray();
            if (candidates.Length == 1) activeProfile = Path.GetFileName(candidates[0]);
        }

        var profileIni = string.IsNullOrWhiteSpace(activeProfile)
            ? string.Empty
            : Path.Combine(profiles, activeProfile, "profile.ini");

        var mods = IniValue(globalText, "mods", "folder").Trim().Trim('"');
        if (string.IsNullOrWhiteSpace(mods)) mods = Path.Combine(userRoot, "mods");
        mods = Environment.ExpandEnvironmentVariables(mods);

        var exe = FindGameExecutable();
        var install = string.IsNullOrWhiteSpace(exe) ? string.Empty : Path.GetDirectoryName(exe) ?? string.Empty;
        var running = Process.GetProcessesByName("mxbikes").Length > 0;

        return new MXBikesEnvironment(exe, install, userRoot, mods, activeProfile, profileIni, running);
    }

    private static string FindUserRoot()
    {
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var docs = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
        var candidates = new[]
        {
            Path.Combine(docs, "PiBoSo", "MX Bikes"),
            Path.Combine(home, "Documents", "PiBoSo", "MX Bikes"),
            Path.Combine(home, "OneDrive", "Documents", "PiBoSo", "MX Bikes")
        }.Distinct(StringComparer.OrdinalIgnoreCase);

        return candidates.FirstOrDefault(p => File.Exists(Path.Combine(p, "global.ini")) || Directory.Exists(Path.Combine(p, "profiles")))
               ?? candidates.First();
    }

    private static string FindGameExecutable()
    {
        foreach (var root in SteamRoots())
        {
            var direct = Path.Combine(root, "steamapps", "common", "MX Bikes", "mxbikes.exe");
            if (File.Exists(direct)) return direct;

            var libraries = Path.Combine(root, "steamapps", "libraryfolders.vdf");
            if (!File.Exists(libraries)) continue;
            foreach (Match match in Regex.Matches(SafeRead(libraries), "\\\"path\\\"\\s+\\\"(?<p>[^\\\"]+)\\\"", RegexOptions.IgnoreCase))
            {
                var lib = match.Groups["p"].Value.Replace("\\\\", "\\");
                var candidate = Path.Combine(lib, "steamapps", "common", "MX Bikes", "mxbikes.exe");
                if (File.Exists(candidate)) return candidate;
            }
        }
        return string.Empty;
    }

    private static IEnumerable<string> SteamRoots()
    {
        var roots = new List<string>();
        try
        {
            var value = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam")?.GetValue("SteamPath")?.ToString();
            if (!string.IsNullOrWhiteSpace(value)) roots.Add(value);
        }
        catch { }
        roots.Add(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Steam"));
        return roots.Where(Directory.Exists).Distinct(StringComparer.OrdinalIgnoreCase);
    }

    private static MXBikeSelection ReadSelection(string path)
    {
        var text = SafeRead(path);
        string V(string key) => IniValue(text, "info", key);
        return new MXBikeSelection(
            V("bikeid"), V("paint"), V("bike_font"), V("rider"), V("suit_paint"), V("suit_font"),
            V("helmet"), V("helmet_paint"), V("goggles_paint"), V("helmet_cam"), V("gloves_paint"),
            V("boots"), V("boots_paint"), V("protection"), V("protection_paint"), V("race_number"), V("suit_name"));
    }

    private static void WriteSelection(string path, MXBikeSelection s)
    {
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            ["bikeid"] = s.BikeId, ["paint"] = s.BikePaint, ["bike_font"] = s.BikeFont,
            ["rider"] = s.RiderModel, ["suit_paint"] = s.RiderPaint, ["suit_font"] = s.RiderFont,
            ["helmet"] = s.HelmetModel, ["helmet_paint"] = s.HelmetPaint, ["goggles_paint"] = s.GogglesPaint,
            ["helmet_cam"] = s.HelmetCamera, ["gloves_paint"] = s.GlovesPaint,
            ["boots"] = s.BootsModel, ["boots_paint"] = s.BootsPaint,
            ["protection"] = s.ProtectionModel, ["protection_paint"] = s.ProtectionPaint,
            ["race_number"] = s.RaceNumber, ["suit_name"] = s.SuitName
        };

        var original = File.ReadAllText(path);
        var backup = Path.Combine(Path.GetDirectoryName(path)!, "profile.race_day_live_backup.ini");
        if (!File.Exists(backup)) File.Copy(path, backup);
        var updated = UpdateInfoSection(original, map);
        var temp = path + ".rdltmp";
        File.WriteAllText(temp, updated);
        File.Move(temp, path, true);
    }

    private static IReadOnlyList<MXContentItem> ScanContent(MXBikesEnvironment env)
    {
        var items = new List<MXContentItem>();
        foreach (var root in new[] { env.GameInstallDirectory, env.ModsDirectory }.Where(Directory.Exists))
        {
            ScanCategory(root, "bikes", "BIKE", items);
            ScanCategory(Path.Combine(root, "rider"), "helmets", "HELMET", items);
            ScanCategory(Path.Combine(root, "rider"), "riders", "RIDER", items);
            ScanCategory(Path.Combine(root, "rider"), "boots", "BOOTS", items);
        }
        return items.GroupBy(i => $"{i.ContentType}:{i.Id}", StringComparer.OrdinalIgnoreCase).Select(g => g.Last()).ToArray();
    }

    private static void ScanCategory(string root, string folder, string type, List<MXContentItem> items)
    {
        var dir = Path.Combine(root, folder);
        if (!Directory.Exists(dir)) return;
        foreach (var sub in Directory.EnumerateDirectories(dir))
            items.Add(new MXContentItem(type, Path.GetFileName(sub), Path.GetFileName(sub), sub, false, true));
        foreach (var file in Directory.EnumerateFiles(dir, "*.pkz"))
            items.Add(new MXContentItem(type, Path.GetFileNameWithoutExtension(file), Path.GetFileNameWithoutExtension(file), file, true, IsZip(file)));
    }

    private static bool IsZip(string path)
    {
        try
        {
            using var stream = File.OpenRead(path);
            Span<byte> header = stackalloc byte[4];
            return stream.Read(header) == 4 && header.SequenceEqual(new byte[] { 0x50, 0x4B, 0x03, 0x04 });
        }
        catch { return false; }
    }

    private static string IniValue(string text, string section, string key)
    {
        var active = false;
        foreach (var raw in text.Split('\n'))
        {
            var line = raw.Trim();
            if (line.StartsWith('[') && line.EndsWith(']'))
            {
                active = string.Equals(line[1..^1].Trim(), section, StringComparison.OrdinalIgnoreCase);
                continue;
            }
            if (!active) continue;
            var split = raw.IndexOf('=');
            if (split < 0) continue;
            if (string.Equals(raw[..split].Trim(), key, StringComparison.OrdinalIgnoreCase)) return raw[(split + 1)..].Trim();
        }
        return string.Empty;
    }

    private static string UpdateInfoSection(string text, IReadOnlyDictionary<string, string> values)
    {
        var lines = text.Replace("\r\n", "\n").Split('\n').ToList();
        var start = lines.FindIndex(l => l.Trim().Equals("[info]", StringComparison.OrdinalIgnoreCase));
        if (start < 0) { if (lines.Count > 0 && lines[^1].Length > 0) lines.Add(""); lines.Add("[info]"); start = lines.Count - 1; }
        var end = lines.FindIndex(start + 1, l => l.Trim().StartsWith('[') && l.Trim().EndsWith(']'));
        if (end < 0) end = lines.Count;

        foreach (var pair in values)
        {
            var index = -1;
            for (var i = start + 1; i < end; i++)
            {
                var eq = lines[i].IndexOf('=');
                if (eq >= 0 && lines[i][..eq].Trim().Equals(pair.Key, StringComparison.OrdinalIgnoreCase)) { index = i; break; }
            }
            if (index >= 0) lines[index] = $"{pair.Key}={pair.Value}";
            else { lines.Insert(end, $"{pair.Key}={pair.Value}"); end++; }
        }
        return string.Join(Environment.NewLine, lines);
    }

    private static string SafeRead(string path)
    {
        try { return File.Exists(path) ? File.ReadAllText(path) : string.Empty; }
        catch { return string.Empty; }
    }

    private static string Quote(string value) => $"\"{(value ?? string.Empty).Replace("\"", "\\\"")}\"";
}
