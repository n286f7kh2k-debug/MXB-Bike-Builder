using System.Text.Json;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Profile;

internal sealed record GameFileLinkSettings(
    string GameInstallDirectory = "",
    string UserDataDirectory = "",
    string ModsDirectory = "",
    string BikesDirectory = "",
    string RiderDirectory = "",
    string HelmetsDirectory = "",
    string BootsDirectory = "",
    string PaintsDirectory = "");

internal static class GameFileLinks
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    public static GameFileLinkSettings Load()
    {
        try
        {
            var path = SettingsPath();
            if (!File.Exists(path)) return new();
            return JsonSerializer.Deserialize<GameFileLinkSettings>(File.ReadAllText(path), JsonOptions) ?? new();
        }
        catch
        {
            return new();
        }
    }

    public static async Task SaveAsync(GameFileLinkSettings settings, CancellationToken cancellationToken = default)
    {
        var path = SettingsPath();
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temp = path + ".tmp";
        await File.WriteAllTextAsync(temp, JsonSerializer.Serialize(Normalize(settings), JsonOptions), cancellationToken);
        File.Move(temp, path, overwrite: true);
    }

    public static GameFileLinkSettings AutoFill(GameFileLinkSettings current, MXBikesEnvironment env)
    {
        var game = FirstExisting(current.GameInstallDirectory, env.GameInstallDirectory);
        var user = FirstExisting(current.UserDataDirectory, env.UserDataDirectory);
        var mods = FirstExisting(current.ModsDirectory, env.ModsDirectory,
            !string.IsNullOrWhiteSpace(user) ? Path.Combine(user, "mods") : "");
        var bikes = FirstExisting(current.BikesDirectory,
            !string.IsNullOrWhiteSpace(mods) ? Path.Combine(mods, "bikes") : "",
            !string.IsNullOrWhiteSpace(game) ? Path.Combine(game, "bikes") : "");
        var rider = FirstExisting(current.RiderDirectory,
            !string.IsNullOrWhiteSpace(mods) ? Path.Combine(mods, "rider") : "",
            !string.IsNullOrWhiteSpace(game) ? Path.Combine(game, "rider") : "");
        var helmets = FirstExisting(current.HelmetsDirectory,
            !string.IsNullOrWhiteSpace(rider) ? Path.Combine(rider, "helmets") : "");
        var boots = FirstExisting(current.BootsDirectory,
            !string.IsNullOrWhiteSpace(rider) ? Path.Combine(rider, "boots") : "");
        var paints = FirstExisting(current.PaintsDirectory,
            !string.IsNullOrWhiteSpace(bikes) ? Path.Combine(bikes, "paints") : "");

        return Normalize(new(game, user, mods, bikes, rider, helmets, boots, paints));
    }

    public static IReadOnlyList<MXContentItem> ScanManualBikes(GameFileLinkSettings? settings = null)
    {
        settings ??= Load();
        var root = ResolveBikesDirectory(settings);
        if (string.IsNullOrWhiteSpace(root) || !Directory.Exists(root)) return Array.Empty<MXContentItem>();

        var items = new Dictionary<string, MXContentItem>(StringComparer.OrdinalIgnoreCase);
        try
        {
            foreach (var directory in Directory.EnumerateDirectories(root))
            {
                var id = Path.GetFileName(directory);
                if (string.IsNullOrWhiteSpace(id)) continue;
                items[id] = new MXContentItem(
                    "BIKE",
                    id,
                    id,
                    directory,
                    false,
                    true);
            }

            foreach (var package in Directory.EnumerateFiles(root, "*.pkz", SearchOption.TopDirectoryOnly))
            {
                var id = Path.GetFileNameWithoutExtension(package);
                if (string.IsNullOrWhiteSpace(id) || items.ContainsKey(id)) continue; // same-name folder wins
                items[id] = new MXContentItem(
                    "BIKE",
                    id,
                    id,
                    package,
                    true,
                    IsZip(package));
            }
        }
        catch
        {
            // A single inaccessible manual folder should not take down the Garage.
        }

        return items.Values.OrderBy(x => x.DisplayName, StringComparer.OrdinalIgnoreCase).ToArray();
    }

    public static string ResolveBikesDirectory(GameFileLinkSettings settings)
    {
        if (Directory.Exists(settings.BikesDirectory)) return settings.BikesDirectory;
        if (Directory.Exists(settings.ModsDirectory))
        {
            var path = Path.Combine(settings.ModsDirectory, "bikes");
            if (Directory.Exists(path)) return path;
        }
        if (Directory.Exists(settings.GameInstallDirectory))
        {
            var path = Path.Combine(settings.GameInstallDirectory, "bikes");
            if (Directory.Exists(path)) return path;
        }
        return settings.BikesDirectory;
    }

    public static bool Exists(string path) => !string.IsNullOrWhiteSpace(path) && (Directory.Exists(path) || File.Exists(path));

    private static GameFileLinkSettings Normalize(GameFileLinkSettings s) => new(
        Clean(s.GameInstallDirectory),
        Clean(s.UserDataDirectory),
        Clean(s.ModsDirectory),
        Clean(s.BikesDirectory),
        Clean(s.RiderDirectory),
        Clean(s.HelmetsDirectory),
        Clean(s.BootsDirectory),
        Clean(s.PaintsDirectory));

    private static string FirstExisting(params string[] candidates)
    {
        foreach (var value in candidates)
        {
            var cleaned = Clean(value);
            if (!string.IsNullOrWhiteSpace(cleaned) && (Directory.Exists(cleaned) || File.Exists(cleaned))) return cleaned;
        }
        return candidates.Select(Clean).FirstOrDefault(x => !string.IsNullOrWhiteSpace(x)) ?? string.Empty;
    }

    private static string Clean(string? value)
    {
        if (string.IsNullOrWhiteSpace(value)) return string.Empty;
        var trimmed = value.Trim().Trim('"');
        try { return Path.GetFullPath(trimmed); }
        catch { return trimmed; }
    }

    private static bool IsZip(string path)
    {
        try
        {
            using var stream = File.OpenRead(path);
            Span<byte> header = stackalloc byte[4];
            return stream.Read(header) == 4 && header[0] == 0x50 && header[1] == 0x4B;
        }
        catch { return false; }
    }

    private static string SettingsPath()
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(local, "MXB Race Day Live", "settings", "game-file-links.json");
    }
}
