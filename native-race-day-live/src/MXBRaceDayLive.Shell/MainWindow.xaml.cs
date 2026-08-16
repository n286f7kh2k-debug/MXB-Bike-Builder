using System.Windows;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using System.Windows.Threading;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Shell;

public partial class MainWindow : Window
{
    private const string UpdateManifestUrl =
        "https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/native-rebuild/native-race-day-live/updates/latest.json";

    private readonly FeatureManager _features;
    private readonly JsonProfileStore _profiles;
    private readonly MXBikesService _mxbikes;
    private readonly HotUpdateService _updates;
    private readonly RaceDayContext _context;
    private readonly DispatcherTimer _autoUpdateTimer;
    private bool _loaded;

    public MainWindow()
    {
        InitializeComponent();

        _features = new FeatureManager();
        _profiles = new JsonProfileStore();
        _mxbikes = new MXBikesService();
        _updates = new HotUpdateService(UpdateManifestUrl, () => _features.CurrentVersion);
        _context = new RaceDayContext(_mxbikes, _profiles, _updates);

        _features.ViewChanged += (_, view) =>
        {
            FeatureHost.Content = view;
            FeatureVersionText.Text = $"Profile v{_features.CurrentVersion}";
            StartupOverlay.Visibility = Visibility.Collapsed;
        };
        _updates.UpdateStatusChanged += (_, status) =>
            Dispatcher.BeginInvoke(() => UpdateStatusText.Text = status);
        _updates.ActivateModuleAsync = async (path, _, cancellationToken) =>
            await _features.LoadAsync(path, _context, cancellationToken);

        _autoUpdateTimer = new DispatcherTimer { Interval = TimeSpan.FromMinutes(20) };
        _autoUpdateTimer.Tick += async (_, _) => await _updates.CheckAndApplyAsync();

        Loaded += MainWindow_Loaded;
        Closed += MainWindow_Closed;
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        if (_loaded) return;
        _loaded = true;

        try
        {
            StartupText.Text = "Detecting MX Bikes…";
            await SyncInitialMXBikesIdentityAsync();

            StartupText.Text = "Loading native profile…";
            await LoadProfileFeatureAsync();

            _autoUpdateTimer.Start();
            await _updates.CheckAndApplyAsync();
        }
        catch (Exception ex)
        {
            StartupText.Text = "Native startup failed: " + ex.Message;
            UpdateStatusText.Text = "Startup error · current files were not modified";
        }
    }

    private async Task SyncInitialMXBikesIdentityAsync()
    {
        var env = await _mxbikes.DetectEnvironmentAsync();
        var hasGame = !string.IsNullOrWhiteSpace(env.GameExecutable) && File.Exists(env.GameExecutable);
        var hasProfile = !string.IsNullOrWhiteSpace(env.ProfileIniPath) && File.Exists(env.ProfileIniPath);

        if (hasGame && hasProfile)
        {
            MxbDot.Fill = Brush("#2BD672");
            MxbStatusText.Text = $"MX Bikes: {env.ActiveProfileName}";

            // On a brand-new Race Day Live profile, seed identity from the real active MX Bikes
            // profile instead of inventing duplicate information. User edits will win later.
            var selection = await _mxbikes.ReadActiveSelectionAsync();
            var rider = _profiles.Current;
            var changed = false;
            if (string.Equals(rider.DisplayName, "Rider Profile", StringComparison.OrdinalIgnoreCase)
                && !string.IsNullOrWhiteSpace(env.ActiveProfileName))
            {
                rider = rider with { DisplayName = env.ActiveProfileName };
                changed = true;
            }
            if ((string.IsNullOrWhiteSpace(rider.RacingNumber) || rider.RacingNumber == "---")
                && !string.IsNullOrWhiteSpace(selection.RaceNumber))
            {
                rider = rider with { RacingNumber = selection.RaceNumber };
                changed = true;
            }
            if (changed) await _profiles.SaveAsync(rider);
        }
        else if (hasGame)
        {
            MxbDot.Fill = Brush("#F4C542");
            MxbStatusText.Text = "MX Bikes: game found · profile not found";
        }
        else
        {
            MxbDot.Fill = Brush("#607887");
            MxbStatusText.Text = "MX Bikes: not detected";
        }
    }

    private async Task LoadProfileFeatureAsync()
    {
        var bundled = Path.Combine(AppContext.BaseDirectory, "Modules", "Bundled", "MXBRaceDayLive.Profile.dll");
        var active = _updates.ResolveActiveModule(bundled);
        try
        {
            await _features.LoadAsync(active, _context);
        }
        catch when (!string.Equals(active, bundled, StringComparison.OrdinalIgnoreCase))
        {
            // A damaged previously-downloaded module must never brick startup.
            await _features.LoadAsync(bundled, _context);
        }
    }

    private void MenuButton_Click(object sender, RoutedEventArgs e)
    {
        if (MenuButton.ContextMenu is null) return;
        MenuButton.ContextMenu.PlacementTarget = MenuButton;
        MenuButton.ContextMenu.Placement = PlacementMode.Bottom;
        MenuButton.ContextMenu.IsOpen = true;
    }

    private async void CheckForUpdates_Click(object sender, RoutedEventArgs e) =>
        await _updates.CheckAndApplyAsync();

    private async void LaunchMXBikes_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            UpdateStatusText.Text = "Launching MX Bikes…";
            await _mxbikes.LaunchGameAsync();
            UpdateStatusText.Text = "MX Bikes launched";
        }
        catch (Exception ex)
        {
            UpdateStatusText.Text = "MX Bikes launch failed · " + ex.Message;
        }
    }

    private void Exit_Click(object sender, RoutedEventArgs e) => Close();

    private async void MainWindow_Closed(object? sender, EventArgs e)
    {
        _autoUpdateTimer.Stop();
        _updates.Dispose();
        await _features.DisposeAsync();
    }

    private static SolidColorBrush Brush(string hex) =>
        new((Color)ColorConverter.ConvertFromString(hex)!);
}
