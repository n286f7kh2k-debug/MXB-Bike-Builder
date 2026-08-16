using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Profile;

public sealed class ProfileHomeFeature : IRaceDayFeature
{
    private IRaceDayContext? _context;
    private TextBlock? _garageBikeText;
    private TextBlock? _garagePaintText;
    private TextBlock? _garageSyncText;
    private FileSystemWatcher? _profileWatcher;
    private FileSystemWatcher? _globalWatcher;
    private CancellationTokenSource? _watchRefreshCts;
    private readonly object _watchGate = new();
    private bool _selectionHooked;

    public string Id => "profile-home";
    public Version Version => new(1, 0, 2);

    public FrameworkElement CreateView(IRaceDayContext context)
    {
        _context = context;
        return Build(context.Profile.Current);
    }

    public async Task OnActivatedAsync(CancellationToken cancellationToken = default)
    {
        if (_context is null) return;
        if (!_selectionHooked)
        {
            _context.MXBikes.SelectionChanged += MXBikes_SelectionChanged;
            _selectionHooked = true;
        }

        await RefreshMXBStateAsync(reconfigureWatchers: true, cancellationToken);
    }

    public Task OnDeactivatedAsync(CancellationToken cancellationToken = default)
    {
        UnhookSelection();
        DisposeWatchers();
        CancelQueuedRefresh();
        return Task.CompletedTask;
    }

    public void Dispose()
    {
        UnhookSelection();
        DisposeWatchers();
        CancelQueuedRefresh();
        _context = null;
    }

    private FrameworkElement Build(RiderProfile rider)
    {
        var root = new ScrollViewer
        {
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            Background = Brush("#04101B")
        };

        var stack = new StackPanel { Margin = new Thickness(34, 26, 34, 34) };
        root.Content = stack;

        var profileCard = Card(new Thickness(0, 0, 0, 18));
        var profileStack = new StackPanel();
        profileCard.Child = profileStack;

        var banner = new Border
        {
            Height = 210,
            CornerRadius = new CornerRadius(18, 18, 0, 0),
            Background = new LinearGradientBrush(Color("#0A4F78"), Color("#061725"), 0),
            ClipToBounds = true
        };
        var bannerGrid = new Grid();
        banner.Child = bannerGrid;
        bannerGrid.Children.Add(new TextBlock
        {
            Text = "MXB RACE DAY LIVE",
            Foreground = Brush("#2E84B2"),
            FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic,
            FontSize = 30,
            Margin = new Thickness(26),
            VerticalAlignment = VerticalAlignment.Top
        });
        profileStack.Children.Add(banner);

        var identity = new Grid { Margin = new Thickness(24, 18, 24, 22) };
        identity.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(118) });
        identity.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        identity.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var avatar = new Grid { Width = 96, Height = 96, Margin = new Thickness(0, 0, 20, 0) };
        avatar.Children.Add(new Ellipse { Fill = Brush("#0B2C42"), Stroke = Brush("#079CFF"), StrokeThickness = 2 });
        avatar.Children.Add(new TextBlock
        {
            Text = Initials(rider.DisplayName),
            Foreground = Brushes.White,
            FontFamily = new FontFamily("Segoe UI Black"),
            FontSize = 28,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center
        });
        Grid.SetColumn(avatar, 0);
        identity.Children.Add(avatar);

        var info = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
        var nameRow = new StackPanel { Orientation = Orientation.Horizontal };
        nameRow.Children.Add(new TextBlock
        {
            Text = rider.DisplayName,
            Foreground = Brushes.White,
            FontFamily = new FontFamily("Segoe UI Black"),
            FontSize = 30
        });
        nameRow.Children.Add(new TextBlock
        {
            Text = $"   #{rider.RacingNumber}",
            Foreground = Brush("#F4C542"),
            FontFamily = new FontFamily("Segoe UI Black"),
            FontSize = 16,
            VerticalAlignment = VerticalAlignment.Center
        });
        info.Children.Add(nameRow);
        info.Children.Add(new TextBlock
        {
            Text = string.Join("  •  ", new[] { rider.Team, rider.Region }.Where(x => !string.IsNullOrWhiteSpace(x))),
            Foreground = Brush("#88A5BA"),
            FontSize = 13,
            Margin = new Thickness(0, 5, 0, 10)
        });
        info.Children.Add(new TextBlock
        {
            Text = string.IsNullOrWhiteSpace(rider.Bio) ? "Your MX Bikes racing profile lives here." : rider.Bio,
            Foreground = Brush("#C5D5E0"),
            FontSize = 13,
            TextWrapping = TextWrapping.Wrap,
            MaxWidth = 700
        });
        Grid.SetColumn(info, 1);
        identity.Children.Add(info);

        var rank = new StackPanel { VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(22, 0, 0, 0) };
        rank.Children.Add(Label("OVERALL RANK", 11, "#88A5BA", true));
        rank.Children.Add(Label(rider.OverallRank > 0 ? $"#{rider.OverallRank}" : "UNRANKED", 25, "#F4C542", true));
        Grid.SetColumn(rank, 2);
        identity.Children.Add(rank);
        profileStack.Children.Add(identity);
        stack.Children.Add(profileCard);

        var stats = new Grid { Margin = new Thickness(0, 0, 0, 18) };
        for (var i = 0; i < 4; i++) stats.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        AddStat(stats, 0, "SKILL", $"{rider.SkillClass.ToUpperInvariant()}  •  {rider.SkillRating} MMR", "#F4C542");
        AddStat(stats, 1, "ETIQUETTE", $"{rider.EtiquetteGrade}  •  {rider.EtiquetteScore}", "#2BD672");
        AddStat(stats, 2, "CAREER STARTS", "0", "#F2F7FB");
        AddStat(stats, 3, "WINS / PODIUMS", "0 / 0", "#F2F7FB");
        stack.Children.Add(stats);

        var garageRow = new Grid { Margin = new Thickness(0, 0, 0, 18) };
        for (var i = 0; i < 4; i++) garageRow.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        var garageCard = BuildGarageCard();
        Grid.SetColumn(garageCard, 0);
        garageRow.Children.Add(garageCard);
        stack.Children.Add(garageRow);

        stack.Children.Add(SectionTitle("MY RACES", "Your registered and completed races will live with your rider profile."));
        var races = Card(new Thickness(0, 0, 0, 18));
        var racesStack = new StackPanel { Margin = new Thickness(22) };
        races.Child = racesStack;
        racesStack.Children.Add(Label("NO REGISTERED RACES YET", 16, "#F2F7FB", true));
        racesStack.Children.Add(Label("We’ll add Find a Race and registration after this native foundation is stable.", 12, "#88A5BA"));
        stack.Children.Add(races);

        var snapshot = new Grid();
        snapshot.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        snapshot.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        snapshot.Children.Add(SnapshotCard("NEXT RACE", "NO RACE REGISTERED", "Your next race will appear here.", 0));
        snapshot.Children.Add(SnapshotCard("LATEST RESULT", "NO RESULTS YET", "Completed results will appear here.", 1));
        stack.Children.Add(snapshot);

        return root;
    }

    private Border BuildGarageCard()
    {
        var card = Card(new Thickness(0, 0, 6, 0));
        card.MinHeight = 176;
        card.ClipToBounds = true;

        var root = new Grid();
        card.Child = root;
        root.Background = new LinearGradientBrush(Color("#0A2D44"), Color("#06131F"), 35);

        var slash1 = new Polygon
        {
            Points = new PointCollection(new[] { new Point(205, -15), new Point(280, -15), new Point(150, 190), new Point(82, 190) }),
            Fill = Brush("#0A7FC3"),
            Opacity = 0.15,
            IsHitTestVisible = false
        };
        var slash2 = new Polygon
        {
            Points = new PointCollection(new[] { new Point(255, -15), new Point(295, -15), new Point(165, 190), new Point(128, 190) }),
            Fill = Brush("#17B7FF"),
            Opacity = 0.13,
            IsHitTestVisible = false
        };
        root.Children.Add(slash1);
        root.Children.Add(slash2);

        var content = new Grid { Margin = new Thickness(17, 14, 17, 15) };
        content.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        content.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        content.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.Children.Add(content);

        var header = new Grid();
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.Children.Add(Label("GARAGE", 11, "#F2F7FB", true));
        _garageSyncText = Label("CONNECTING…", 9, "#079CFF", true);
        Grid.SetColumn(_garageSyncText, 1);
        header.Children.Add(_garageSyncText);
        Grid.SetRow(header, 0);
        content.Children.Add(header);

        var bikeStack = new StackPanel { VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 11, 0, 8) };
        bikeStack.Children.Add(Label("MX BIKES LOADOUT", 9, "#88A5BA", true));
        _garageBikeText = Label("READING GAME PROFILE…", 18, "#F2F7FB", true, new Thickness(0, 4, 0, 0));
        _garageBikeText.TextTrimming = TextTrimming.CharacterEllipsis;
        bikeStack.Children.Add(_garageBikeText);
        _garagePaintText = Label("", 10, "#88A5BA", false, new Thickness(0, 4, 0, 0));
        _garagePaintText.TextTrimming = TextTrimming.CharacterEllipsis;
        bikeStack.Children.Add(_garagePaintText);
        Grid.SetRow(bikeStack, 1);
        content.Children.Add(bikeStack);

        var footer = new Border
        {
            BorderBrush = Brush("#155273"),
            BorderThickness = new Thickness(0, 1, 0, 0),
            Padding = new Thickness(0, 8, 0, 0)
        };
        footer.Child = Label("GAME PROFILE → RACE DAY LIVE", 8.5, "#5E8299", true);
        Grid.SetRow(footer, 2);
        content.Children.Add(footer);

        return card;
    }

    private async Task RefreshMXBStateAsync(bool reconfigureWatchers, CancellationToken cancellationToken)
    {
        var context = _context;
        if (context is null) return;

        try
        {
            var env = await context.MXBikes.DetectEnvironmentAsync(cancellationToken);
            if (reconfigureWatchers) ConfigureWatchers(env);

            if (string.IsNullOrWhiteSpace(env.ProfileIniPath) || !File.Exists(env.ProfileIniPath))
            {
                SetGarageState("NO ACTIVE PROFILE", "MX Bikes profile.ini was not found", "NOT LINKED", "#FF5964");
                return;
            }

            var selection = await context.MXBikes.ReadActiveSelectionAsync(cancellationToken);
            ApplySelection(selection);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
        }
        catch
        {
            SetGarageState("MX BIKES UNAVAILABLE", "Waiting for the game profile", "RETRYING", "#F4C542");
        }
    }

    private void MXBikes_SelectionChanged(object? sender, MXBikeSelection selection) => ApplySelection(selection);

    private void ApplySelection(MXBikeSelection selection)
    {
        var bike = string.IsNullOrWhiteSpace(selection.BikeId) ? "NO BIKE SELECTED" : Friendly(selection.BikeId);
        var paint = string.IsNullOrWhiteSpace(selection.BikePaint) ? "Default paint" : Friendly(selection.BikePaint);
        SetGarageState(bike, paint, "AUTO-SYNC ACTIVE", "#2BD672");
    }

    private void SetGarageState(string bike, string paint, string status, string statusColor)
    {
        void Apply()
        {
            if (_garageBikeText is not null) _garageBikeText.Text = bike;
            if (_garagePaintText is not null) _garagePaintText.Text = paint;
            if (_garageSyncText is not null)
            {
                _garageSyncText.Text = status;
                _garageSyncText.Foreground = Brush(statusColor);
            }
        }

        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is null || dispatcher.CheckAccess()) Apply();
        else dispatcher.BeginInvoke(Apply);
    }

    private void ConfigureWatchers(MXBikesEnvironment env)
    {
        DisposeWatchers();

        if (!string.IsNullOrWhiteSpace(env.ProfileIniPath))
        {
            var profileDir = Path.GetDirectoryName(env.ProfileIniPath);
            var profileName = Path.GetFileName(env.ProfileIniPath);
            if (!string.IsNullOrWhiteSpace(profileDir) && Directory.Exists(profileDir))
            {
                _profileWatcher = new FileSystemWatcher(profileDir, profileName)
                {
                    NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.Size | NotifyFilters.FileName,
                    EnableRaisingEvents = true
                };
                _profileWatcher.Changed += (_, _) => QueueRefresh(reconfigureWatchers: false);
                _profileWatcher.Created += (_, _) => QueueRefresh(reconfigureWatchers: false);
                _profileWatcher.Renamed += (_, _) => QueueRefresh(reconfigureWatchers: false);
            }
        }

        if (!string.IsNullOrWhiteSpace(env.UserDataDirectory))
        {
            var globalIni = Path.Combine(env.UserDataDirectory, "global.ini");
            var globalDir = Path.GetDirectoryName(globalIni);
            if (!string.IsNullOrWhiteSpace(globalDir) && Directory.Exists(globalDir))
            {
                _globalWatcher = new FileSystemWatcher(globalDir, "global.ini")
                {
                    NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.Size | NotifyFilters.FileName,
                    EnableRaisingEvents = true
                };
                _globalWatcher.Changed += (_, _) => QueueRefresh(reconfigureWatchers: true);
                _globalWatcher.Created += (_, _) => QueueRefresh(reconfigureWatchers: true);
                _globalWatcher.Renamed += (_, _) => QueueRefresh(reconfigureWatchers: true);
            }
        }
    }

    private void QueueRefresh(bool reconfigureWatchers)
    {
        CancellationTokenSource cts;
        lock (_watchGate)
        {
            _watchRefreshCts?.Cancel();
            _watchRefreshCts?.Dispose();
            _watchRefreshCts = new CancellationTokenSource();
            cts = _watchRefreshCts;
        }

        _ = Task.Run(async () =>
        {
            try
            {
                await Task.Delay(350, cts.Token);
                await RefreshMXBStateAsync(reconfigureWatchers, cts.Token);
            }
            catch (OperationCanceledException)
            {
            }
        });
    }

    private void CancelQueuedRefresh()
    {
        lock (_watchGate)
        {
            _watchRefreshCts?.Cancel();
            _watchRefreshCts?.Dispose();
            _watchRefreshCts = null;
        }
    }

    private void DisposeWatchers()
    {
        _profileWatcher?.Dispose();
        _profileWatcher = null;
        _globalWatcher?.Dispose();
        _globalWatcher = null;
    }

    private void UnhookSelection()
    {
        if (_selectionHooked && _context is not null)
        {
            _context.MXBikes.SelectionChanged -= MXBikes_SelectionChanged;
            _selectionHooked = false;
        }
    }

    private static Border Card(Thickness margin) => new()
    {
        Background = Brush("#071A29"),
        BorderBrush = Brush("#155273"),
        BorderThickness = new Thickness(1),
        CornerRadius = new CornerRadius(18),
        Margin = margin
    };

    private static FrameworkElement SnapshotCard(string kicker, string title, string subtitle, int column)
    {
        var card = Card(column == 0 ? new Thickness(0, 0, 9, 0) : new Thickness(9, 0, 0, 0));
        var stack = new StackPanel { Margin = new Thickness(22) };
        stack.Children.Add(Label(kicker, 10, "#079CFF", true));
        stack.Children.Add(Label(title, 17, "#F2F7FB", true, new Thickness(0, 7, 0, 6)));
        stack.Children.Add(Label(subtitle, 12, "#88A5BA"));
        card.Child = stack;
        Grid.SetColumn(card, column);
        return card;
    }

    private static FrameworkElement SectionTitle(string title, string subtitle)
    {
        var stack = new StackPanel { Margin = new Thickness(2, 0, 0, 10) };
        stack.Children.Add(Label(title, 18, "#F2F7FB", true));
        if (!string.IsNullOrWhiteSpace(subtitle))
            stack.Children.Add(Label(subtitle, 11, "#88A5BA", false, new Thickness(0, 3, 0, 0)));
        return stack;
    }

    private static void AddStat(Grid grid, int col, string title, string value, string valueColor)
    {
        var card = Card(new Thickness(col == 0 ? 0 : 6, 0, col == 3 ? 0 : 6, 0));
        var stack = new StackPanel { Margin = new Thickness(17, 14, 17, 14) };
        stack.Children.Add(Label(title, 10, "#88A5BA", true));
        stack.Children.Add(Label(value, 15, valueColor, true, new Thickness(0, 5, 0, 0)));
        card.Child = stack;
        Grid.SetColumn(card, col);
        grid.Children.Add(card);
    }

    private static TextBlock Label(string text, double size, string color, bool bold = false, Thickness? margin = null) => new()
    {
        Text = text,
        Foreground = Brush(color),
        FontSize = size,
        FontFamily = new FontFamily(bold ? "Segoe UI Semibold" : "Segoe UI"),
        Margin = margin ?? new Thickness(0)
    };

    private static string Initials(string name)
    {
        var parts = (name ?? string.Empty).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        if (parts.Length == 0) return "RDL";
        return string.Concat(parts.Take(2).Select(p => char.ToUpperInvariant(p[0])));
    }

    private static string Friendly(string value) =>
        string.Join(' ', (value ?? string.Empty).Replace('_', ' ').Replace('-', ' ').Split(' ', StringSplitOptions.RemoveEmptyEntries));

    private static SolidColorBrush Brush(string hex) => new(Color(hex));
    private static Color Color(string hex) => (Color)ColorConverter.ConvertFromString(hex)!;
}
