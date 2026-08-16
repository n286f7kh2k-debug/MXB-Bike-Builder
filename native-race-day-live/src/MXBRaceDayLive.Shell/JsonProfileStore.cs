using System.Text.Json;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Shell;

public sealed class JsonProfileStore : IProfileStore
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };
    private readonly string _path;

    public RiderProfile Current { get; private set; }

    public JsonProfileStore()
    {
        var root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MXB Race Day Live");
        Directory.CreateDirectory(root);
        _path = Path.Combine(root, "profile.json");
        Current = Load() ?? DefaultProfile();
    }

    public async Task SaveAsync(RiderProfile profile, CancellationToken cancellationToken = default)
    {
        var temp = _path + ".tmp";
        await File.WriteAllTextAsync(temp, JsonSerializer.Serialize(profile, JsonOptions), cancellationToken);
        File.Move(temp, _path, true);
        Current = profile;
    }

    private RiderProfile? Load()
    {
        try
        {
            if (!File.Exists(_path)) return null;
            return JsonSerializer.Deserialize<RiderProfile>(File.ReadAllText(_path));
        }
        catch
        {
            return null;
        }
    }

    private static RiderProfile DefaultProfile() => new(
        DisplayName: "Rider Profile",
        RacingNumber: "---",
        Team: "",
        Region: "",
        Bio: "Connected to MX Bikes. Profile customization comes next.",
        AvatarPath: "",
        BannerPath: "",
        SkillRating: 1500,
        SkillClass: "Unranked",
        EtiquetteScore: 1000,
        EtiquetteGrade: "A",
        OverallRank: 0);
}
