using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Profile;

// Compatibility shim for the v1.0.7 call site. The Garage no longer depends on Frost.
// Sealed-bike previews are now owned by Race Day Live's internal iNsane component host.
internal static class FrostBikePreviewProvider
{
    public static bool RequiresFrost(IReadOnlyList<string> edfFiles) =>
        InsaneBikePreviewProvider.RequiresPreviewComponent(edfFiles);

    public static Task<BikeModelPreviewResult> CreateAsync(
        MXContentItem bike,
        string resolvedSource,
        CancellationToken cancellationToken) =>
        InsaneBikePreviewProvider.CreateAsync(bike, resolvedSource, cancellationToken);
}
