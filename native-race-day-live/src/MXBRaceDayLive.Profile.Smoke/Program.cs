using System.IO;
using System.Windows;
using MXBRaceDayLive.Contracts;
using MXBRaceDayLive.Profile;

internal static class Program
{
    [STAThread]
    private static async Task<int> Main()
    {
        var temp = Path.Combine(Path.GetTempPath(), "mxb-rdl-profile-smoke-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(temp);
        Directory.CreateDirectory(Path.Combine(temp, "mods"));
        Directory.CreateDirectory(Path.Combine(temp, "profiles", "Smoke"));
        var profileIni = Path.Combine(temp, "profiles", "Smoke", "profile.ini");
        await File.WriteAllTextAsync(profileIni, "[info]\nbikeid = smoke_bike\npaint = smoke_paint\nrace_number = 311\n");

        var app = new Application();
        try
        {
            var profile = new SmokeProfileStore(new RiderProfile(
                "Welchy", "311", "", "Ohio", "Smoke test rider",
                "", "", 3124, "450 Pro", 96, "A+", 42));
            var mxbikes = new SmokeMXBikes(temp, profileIni);
            var updates = new SmokeUpdates();
            var context = new SmokeContext(mxbikes, profile, updates);

            using var feature = new ProfileHomeFeature();
            var view = feature.CreateView(context)
                       ?? throw new InvalidOperationException("Profile CreateView returned null.");
            if (view.ActualWidth < 0)
                throw new InvalidOperationException("Impossible WPF view state.");

            await feature.OnActivatedAsync();
            await feature.OnDeactivatedAsync();
            Console.WriteLine($"PROFILE_RUNTIME_SMOKE_OK v{feature.Version}");
            return 0;
        }
        finally
        {
            app.Shutdown();
            try { Directory.Delete(temp, true); } catch { }
        }
    }

    private sealed class SmokeContext(IMXBikesService mxbikes, IProfileStore profile, IUpdateService updates) : IRaceDayContext
    {
        public IMXBikesService MXBikes { get; } = mxbikes;
        public IProfileStore Profile { get; } = profile;
        public IUpdateService Updates { get; } = updates;
    }

    private sealed class SmokeProfileStore(RiderProfile current) : IProfileStore
    {
        public RiderProfile Current { get; private set; } = current;
        public Task SaveAsync(RiderProfile profile, CancellationToken cancellationToken = default)
        {
            Current = profile;
            return Task.CompletedTask;
        }
    }

    private sealed class SmokeUpdates : IUpdateService
    {
        public event EventHandler<string>? UpdateStatusChanged;
        public Task CheckAndApplyAsync(CancellationToken cancellationToken = default)
        {
            UpdateStatusChanged?.Invoke(this, "smoke");
            return Task.CompletedTask;
        }
    }

    private sealed class SmokeMXBikes(string root, string profileIni) : IMXBikesService
    {
        public event EventHandler<MXBikesEnvironment>? EnvironmentChanged;
        public event EventHandler<MXBikeSelection>? SelectionChanged;
        public event EventHandler? ContentChanged;

        public Task<MXBikesEnvironment> DetectEnvironmentAsync(CancellationToken cancellationToken = default)
        {
            var env = new MXBikesEnvironment(
                "", root, root, Path.Combine(root, "mods"), "Smoke", profileIni, false);
            EnvironmentChanged?.Invoke(this, env);
            return Task.FromResult(env);
        }

        public Task<MXBikeSelection> ReadActiveSelectionAsync(CancellationToken cancellationToken = default)
        {
            var value = new MXBikeSelection(
                "smoke_bike", "smoke_paint", "", "", "", "", "", "", "", "", "", "", "", "", "", "311", "Welchy");
            SelectionChanged?.Invoke(this, value);
            return Task.FromResult(value);
        }

        public Task ApplySelectionAsync(MXBikeSelection selection, CancellationToken cancellationToken = default) => Task.CompletedTask;
        public Task<IReadOnlyList<MXContentItem>> ScanInstalledContentAsync(CancellationToken cancellationToken = default)
            => Task.FromResult<IReadOnlyList<MXContentItem>>(Array.Empty<MXContentItem>());
        public Task LaunchGameAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;
        public Task LaunchRaceAsync(string host, int port, string? password = null, CancellationToken cancellationToken = default) => Task.CompletedTask;
    }
}
