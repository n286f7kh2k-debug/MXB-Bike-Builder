using System.Net.Http;
using System.Net.Http.Headers;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;

namespace MXBRaceDayLive.Profile;

/// <summary>
/// Compatibility bridge for Race Day Live shells that predate the cache-busting updater fix.
/// It keeps the existing installed EXE and uses the same hot-module update path.
/// Once a newer module replaces this one the timer stops itself so the old load context can unload.
/// </summary>
internal static class UpdateRecoveryBridge
{
    private static readonly string ModuleVersion =
        typeof(UpdateRecoveryBridge).Assembly.GetName().Version is { } v
            ? $"{v.Major}.{v.Minor}.{v.Build}"
            : "1.0.18";

    [ModuleInitializer]
    internal static void Initialize()
    {
        var app = Application.Current;
        if (app?.Dispatcher is null) return;
        app.Dispatcher.BeginInvoke(Start, DispatcherPriority.ApplicationIdle);
    }

    private static void Start()
    {
        var window = Application.Current?.MainWindow;
        if (window is null) return;

        var updaterField = window.GetType().GetField(
            "_updates",
            BindingFlags.Instance | BindingFlags.NonPublic);
        var updater = updaterField?.GetValue(window);
        if (updater is null) return;

        ForceNoCacheHeaders(updater.GetType());

        var checkMethod = updater.GetType().GetMethod(
            "CheckAndApplyAsync",
            BindingFlags.Instance | BindingFlags.Public,
            binder: null,
            types: new[] { typeof(CancellationToken) },
            modifiers: null);
        if (checkMethod is null) return;

        DispatcherTimer? timer = null;

        async Task PulseAsync()
        {
            try
            {
                // If another module version is already active, detach this bridge so its old
                // collectible AssemblyLoadContext is not kept alive by the DispatcherTimer.
                if (window.FindName("FeatureVersionText") is TextBlock versionText
                    && !versionText.Text.Contains(ModuleVersion, StringComparison.OrdinalIgnoreCase))
                {
                    timer?.Stop();
                    return;
                }

                if (checkMethod.Invoke(updater, new object[] { CancellationToken.None }) is Task task)
                    await task;
            }
            catch
            {
                // Recovery must never interfere with the profile UI. The next pulse retries.
            }
        }

        timer = new DispatcherTimer(DispatcherPriority.Background)
        {
            Interval = TimeSpan.FromMinutes(2)
        };
        timer.Tick += async (_, _) => await PulseAsync();
        timer.Start();

        _ = PulseAsync();
    }

    private static void ForceNoCacheHeaders(Type updaterType)
    {
        try
        {
            var clientField = updaterType.GetField(
                "Client",
                BindingFlags.Static | BindingFlags.NonPublic);
            if (clientField?.GetValue(null) is not HttpClient client) return;

            client.DefaultRequestHeaders.CacheControl = new CacheControlHeaderValue
            {
                NoCache = true,
                NoStore = true,
                MaxAge = TimeSpan.Zero
            };
            if (!client.DefaultRequestHeaders.Pragma.Any(x =>
                    string.Equals(x.Name, "no-cache", StringComparison.OrdinalIgnoreCase)))
            {
                client.DefaultRequestHeaders.Pragma.ParseAdd("no-cache");
            }
        }
        catch
        {
            // Newer shells already have cache-busting built in and do not need this bridge.
        }
    }
}
