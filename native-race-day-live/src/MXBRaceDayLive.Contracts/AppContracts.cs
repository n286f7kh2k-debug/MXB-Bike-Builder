using System.Windows;

namespace MXBRaceDayLive.Contracts;

public interface IRaceDayFeature : IDisposable
{
    string Id { get; }
    Version Version { get; }
    FrameworkElement CreateView(IRaceDayContext context);
    Task OnActivatedAsync(CancellationToken cancellationToken = default);
    Task OnDeactivatedAsync(CancellationToken cancellationToken = default);
}

public interface IRaceDayContext
{
    IMXBikesService MXBikes { get; }
    IProfileStore Profile { get; }
    IUpdateService Updates { get; }
}

public interface IProfileStore
{
    RiderProfile Current { get; }
    Task SaveAsync(RiderProfile profile, CancellationToken cancellationToken = default);
}

public sealed record RiderProfile(
    string DisplayName,
    string RacingNumber,
    string Team,
    string Region,
    string Bio,
    string AvatarPath,
    string BannerPath,
    int SkillRating,
    string SkillClass,
    int EtiquetteScore,
    string EtiquetteGrade,
    int OverallRank);

public sealed record MXBikeSelection(
    string BikeId,
    string BikePaint,
    string BikeFont,
    string RiderModel,
    string RiderPaint,
    string RiderFont,
    string HelmetModel,
    string HelmetPaint,
    string GogglesPaint,
    string HelmetCamera,
    string GlovesPaint,
    string BootsModel,
    string BootsPaint,
    string ProtectionModel,
    string ProtectionPaint,
    string RaceNumber,
    string SuitName);

public sealed record MXBikesEnvironment(
    string GameExecutable,
    string GameInstallDirectory,
    string UserDataDirectory,
    string ModsDirectory,
    string ActiveProfileName,
    string ProfileIniPath,
    bool GameRunning);

public sealed record MXContentItem(
    string ContentType,
    string Id,
    string DisplayName,
    string Path,
    bool IsPackaged,
    bool IsReadableByRaceDayLive);

public interface IMXBikesService
{
    event EventHandler<MXBikesEnvironment>? EnvironmentChanged;
    event EventHandler<MXBikeSelection>? SelectionChanged;
    event EventHandler? ContentChanged;

    Task<MXBikesEnvironment> DetectEnvironmentAsync(CancellationToken cancellationToken = default);
    Task<MXBikeSelection> ReadActiveSelectionAsync(CancellationToken cancellationToken = default);
    Task ApplySelectionAsync(MXBikeSelection selection, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<MXContentItem>> ScanInstalledContentAsync(CancellationToken cancellationToken = default);
    Task LaunchGameAsync(CancellationToken cancellationToken = default);
    Task LaunchRaceAsync(string host, int port, string? password = null, CancellationToken cancellationToken = default);
}

public sealed record UpdateManifest(
    string Version,
    string ModuleUrl,
    string Sha256,
    string FeatureAssembly,
    string Notes);

public interface IUpdateService
{
    event EventHandler<string>? UpdateStatusChanged;
    Task CheckAndApplyAsync(CancellationToken cancellationToken = default);
}
