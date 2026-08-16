using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Shapes;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Profile;

public sealed class ProfileHomeFeature : IRaceDayFeature
{
    private IRaceDayContext? _context;
    private TextBlock? _garageBikeText;
    private TextBlock? _garagePaintText;
    private TextBlock? _garageSyncText;
    private Grid? _pageHost;
    private ScrollViewer? _profileView;
    private FrameworkElement? _bikeLibraryView;
    private FrameworkElement? _bikeModelView;
    private FrameworkElement? _settingsView;
    private FileSystemWatcher? _profileWatcher;
    private FileSystemWatcher? _globalWatcher;
    private CancellationTokenSource? _watchRefreshCts;
    private CancellationTokenSource? _modelLoadCts;
    private readonly object _watchGate = new();
    private bool _selectionHooked;

    public string Id => "profile-home";
    public Version Version => new(1, 0, 4);

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
        CancelModelLoad();
        return Task.CompletedTask;
    }

    public void Dispose()
    {
        UnhookSelection();
        DisposeWatchers();
        CancelQueuedRefresh();
        CancelModelLoad();
        _context = null;
        _pageHost = null;
        _profileView = null;
        _bikeLibraryView = null;
        _bikeModelView = null;
        _settingsView = null;
    }

    private FrameworkElement Build(RiderProfile rider)
    {
        _pageHost = new Grid { Background = PageBackground(), ClipToBounds = true };
        AddRaceNightBackdrop(_pageHost);
        _profileView = new ScrollViewer
        {
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            Background = Brushes.Transparent
        };

        var stack = new StackPanel { Margin = new Thickness(26, 22, 26, 32) };
        _profileView.Content = stack;
        _pageHost.Children.Add(_profileView);

        var profileCard = Card(new Thickness(0, 0, 0, 18));
        var profileStack = new StackPanel();
        profileCard.Child = profileStack;

        var banner = new Border
        {
            Height = 286,
            CornerRadius = new CornerRadius(12, 12, 0, 0),
            Background = HeroBackground(),
            BorderBrush = Brush("#0AAEFF"),
            BorderThickness = new Thickness(0, 0, 0, 2),
            ClipToBounds = true,
            Effect = Glow("#0077CC", 24, 0.30)
        };
        var bannerGrid = new Grid();
        banner.Child = bannerGrid;

        // Theme-only artwork: keep the existing layout, but let the existing profile banner
        // become the cinematic background instead of ignoring it.
        var bannerArt = TryImageBrush(rider.BannerPath);
        if (bannerArt is not null)
        {
            bannerGrid.Children.Add(new Rectangle
            {
                Fill = bannerArt,
                Opacity = 0.88,
                IsHitTestVisible = false
            });
            bannerGrid.Children.Add(new Rectangle
            {
                Fill = new LinearGradientBrush
                {
                    StartPoint = new Point(0, 0),
                    EndPoint = new Point(1, 0),
                    GradientStops = new GradientStopCollection
                    {
                        new GradientStop(Color("#E9010710"), 0.00),
                        new GradientStop(Color("#9A03121E"), 0.38),
                        new GradientStop(Color("#4A03121E"), 0.70),
                        new GradientStop(Color("#C7020911"), 1.00)
                    }
                },
                IsHitTestVisible = false
            });
        }

        // Stadium glow.
        bannerGrid.Children.Add(new Ellipse
        {
            Width = 650,
            Height = 650,
            Fill = new RadialGradientBrush(Color("#19B8FF"), Color("#00101B")) { RadiusX = 0.72, RadiusY = 0.72 },
            Opacity = 0.22,
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, -210, -70),
            IsHitTestVisible = false
        });

        // Racing slash graphics.
        bannerGrid.Children.Add(new Polygon
        {
            Points = new PointCollection(new[] { new Point(520, -20), new Point(700, -20), new Point(455, 310), new Point(285, 310) }),
            Fill = Brush("#007FD0"), Opacity = 0.22, IsHitTestVisible = false
        });
        bannerGrid.Children.Add(new Polygon
        {
            Points = new PointCollection(new[] { new Point(675, -20), new Point(755, -20), new Point(510, 310), new Point(440, 310) }),
            Fill = Brush("#18C4FF"), Opacity = 0.18, IsHitTestVisible = false
        });

        // Stadium lights across the upper-right edge.
        var lightRow = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Top,
            Margin = new Thickness(0, 22, 28, 0)
        };
        for (var i = 0; i < 8; i++)
        {
            lightRow.Children.Add(new Ellipse
            {
                Width = 8,
                Height = 8,
                Margin = new Thickness(5, 0, 5, 0),
                Fill = Brush(i % 3 == 0 ? "#7FDBFF" : "#F6FBFF"),
                Effect = Glow("#BFEAFF", 18, 0.95)
            });
        }
        bannerGrid.Children.Add(lightRow);

        // Stylized dirt/track silhouette along the bottom of the existing banner.
        bannerGrid.Children.Add(new Polygon
        {
            Points = new PointCollection(new[]
            {
                new Point(-30, 246), new Point(135, 226), new Point(255, 246), new Point(385, 214),
                new Point(520, 241), new Point(690, 205), new Point(860, 238), new Point(1110, 210),
                new Point(1400, 244), new Point(1400, 310), new Point(-30, 310)
            }),
            Fill = Brush("#020810"), Opacity = 0.90, IsHitTestVisible = false
        });
        bannerGrid.Children.Add(new Polyline
        {
            Points = new PointCollection(new[]
            {
                new Point(-20, 243), new Point(135, 223), new Point(255, 243), new Point(385, 211),
                new Point(520, 238), new Point(690, 202), new Point(860, 235), new Point(1110, 207), new Point(1400, 241)
            }),
            Stroke = Brush("#0AAEFF"), StrokeThickness = 2, Opacity = 0.55, IsHitTestVisible = false
        });

        // Roost / atmosphere particles.
        var roost = new Canvas { IsHitTestVisible = false, Opacity = 0.60 };
        var dots = new (double x, double y, double r)[]
        {
            (430,196,4),(458,178,2),(483,205,3),(508,172,2),(536,196,5),(568,165,2),
            (602,193,3),(633,153,2),(663,181,4),(700,143,2),(733,171,3),(770,132,2),
            (814,160,4),(852,120,2),(900,151,3),(952,111,2)
        };
        foreach (var d in dots)
        {
            var dot = new Ellipse { Width = d.r * 2, Height = d.r * 2, Fill = Brush("#DCE9F2"), Opacity = 0.55 };
            Canvas.SetLeft(dot, d.x); Canvas.SetTop(dot, d.y); roost.Children.Add(dot);
        }
        bannerGrid.Children.Add(roost);

        var brand = new StackPanel { Margin = new Thickness(30, 30, 0, 0), VerticalAlignment = VerticalAlignment.Top };
        var mxb = new TextBlock
        {
            Text = "MXB",
            Foreground = Brush("#F7FBFF"),
            FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic,
            FontSize = 58,
            Effect = Glow("#001827", 8, 0.85)
        };
        brand.Children.Add(mxb);
        var liveRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(2, -11, 0, 0) };
        liveRow.Children.Add(new TextBlock
        {
            Text = "RACE DAY ", Foreground = Brush("#EAF4FA"), FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic, FontSize = 24
        });
        liveRow.Children.Add(new TextBlock
        {
            Text = "LIVE", Foreground = Brush("#0AB9FF"), FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic, FontSize = 31, Effect = Glow("#009CFF", 20, 0.85)
        });
        brand.Children.Add(liveRow);
        brand.Children.Add(new TextBlock
        {
            Text = "RACE  •  COMPETE  •  EARN",
            Foreground = Brush("#88AFC4"), FontFamily = new FontFamily("Segoe UI Semibold"),
            FontSize = 10, Margin = new Thickness(5, 7, 0, 0)
        });
        bannerGrid.Children.Add(brand);

        var heroIdentity = new StackPanel
        {
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 40, 34, 0)
        };
        heroIdentity.Children.Add(new TextBlock
        {
            Text = rider.DisplayName.ToUpperInvariant(), Foreground = Brush("#FFFFFF"),
            FontFamily = new FontFamily("Segoe UI Black"), FontStyle = FontStyles.Italic,
            FontSize = 28, HorizontalAlignment = HorizontalAlignment.Right,
            Effect = Glow("#000000", 8, 0.8)
        });
        heroIdentity.Children.Add(new TextBlock
        {
            Text = $"#{rider.RacingNumber}", Foreground = Brush("#0AB9FF"),
            FontFamily = new FontFamily("Segoe UI Black"), FontStyle = FontStyles.Italic,
            FontSize = 84, Margin = new Thickness(0, -10, 0, 0), HorizontalAlignment = HorizontalAlignment.Right,
            Effect = Glow("#008CFF", 24, 0.55)
        });
        bannerGrid.Children.Add(heroIdentity);

        // Reference-exact hero artwork sits on top of the old procedural art.
        // This changes only the skin; banner size and page geometry stay untouched.
        bannerGrid.Children.Add(new Rectangle
        {
            Fill = ThemeArt.HeaderBrush(),
            Opacity = 1.0,
            IsHitTestVisible = false
        });
        profileStack.Children.Add(banner);

        var identity = new Grid { Margin = new Thickness(24, 16, 24, 20) };
        identity.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(118) });
        identity.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        identity.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var avatar = new Grid { Width = 96, Height = 96, Margin = new Thickness(0, 0, 20, 0) };
        var avatarArt = TryImageBrush(rider.AvatarPath);
        Brush avatarFill = avatarArt is not null
            ? avatarArt
            : new LinearGradientBrush(Color("#0D3551"), Color("#06131F"), 45);
        avatar.Children.Add(new Ellipse { Fill = avatarFill, Stroke = Brush("#0AAEFF"), StrokeThickness = 2.5, Effect = Glow("#00A8FF", 18, 0.48) });
        if (avatarArt is null)
        {
            avatar.Children.Add(new TextBlock
            {
                Text = Initials(rider.DisplayName),
                Foreground = Brushes.White,
                FontFamily = new FontFamily("Segoe UI Black"),
                FontSize = 28,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Center
            });
        }
        Grid.SetColumn(avatar, 0);
        identity.Children.Add(avatar);

        var info = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
        var nameRow = new StackPanel { Orientation = Orientation.Horizontal };
        nameRow.Children.Add(new TextBlock
        {
            Text = rider.DisplayName,
            Foreground = Brushes.White,
            FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic,
            FontSize = 32
        });
        nameRow.Children.Add(new TextBlock
        {
            Text = $"   #{rider.RacingNumber}",
            Foreground = Brush("#0AAEFF"),
            FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic,
            FontSize = 19,
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
        var settingsCard = BuildSettingsCard();
        Grid.SetColumn(settingsCard, 1);
        garageRow.Children.Add(settingsCard);
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

        return _pageHost;
    }

    private Border BuildSettingsCard()
    {
        var card = Card(new Thickness(6, 0, 6, 0));
        card.MinHeight = 176;
        card.Cursor = Cursors.Hand;
        card.ToolTip = "Open Race Day Live settings";
        card.MouseLeftButtonUp += (_, _) => OpenSettings();
        card.ClipToBounds = true;

        var root = new Grid { Background = ThemeArt.LiveBrush() };
        root.Children.Add(new Rectangle
        {
            Fill = Brush("#A904111D"),
            IsHitTestVisible = false
        });
        root.Children.Add(new Polygon
        {
            Points = new PointCollection(new[] { new Point(185, -20), new Point(270, -20), new Point(150, 200), new Point(70, 200) }),
            Fill = Brush("#0AAEFF"), Opacity = 0.12, IsHitTestVisible = false
        });
        root.Children.Add(new TextBlock
        {
            Text = "SETTINGS", Foreground = Brush("#0AAEFF"), FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic, FontSize = 34, Opacity = 0.08,
            HorizontalAlignment = HorizontalAlignment.Right, VerticalAlignment = VerticalAlignment.Bottom,
            Margin = new Thickness(0,0,10,-2), IsHitTestVisible = false
        });
        var stack = new StackPanel { Margin = new Thickness(18, 15, 18, 15) };
        var title = Label("SETTINGS", 10, "#8DB4CA", true); title.FontStyle = FontStyles.Italic;
        stack.Children.Add(title);
        var links = Label("GAME FILE LINKS", 18, "#F4FAFD", true, new Thickness(0, 22, 0, 6));
        links.FontFamily = new FontFamily("Segoe UI Black"); links.FontStyle = FontStyles.Italic;
        stack.Children.Add(links);
        stack.Children.Add(Label("Manually link MX Bikes, bikes, rider and gear folders.", 10, "#86A6B8"));
        var open = Label("OPEN SETTINGS  ›", 9, "#0AB9FF", true, new Thickness(0, 24, 0, 0));
        open.Effect = Glow("#008DFF", 12, 0.45); stack.Children.Add(open);
        root.Children.Add(stack);
        card.Child = root;
        return card;
    }

    private void OpenSettings()
    {
        var host = _pageHost;
        var profile = _profileView;
        if (host is null || profile is null) return;

        CancelModelLoad();
        profile.Visibility = Visibility.Collapsed;
        if (_bikeLibraryView is not null) { host.Children.Remove(_bikeLibraryView); _bikeLibraryView = null; }
        if (_bikeModelView is not null) { host.Children.Remove(_bikeModelView); _bikeModelView = null; }
        if (_settingsView is not null) host.Children.Remove(_settingsView);

        var page = new Grid { Background = PageBackground() };
        page.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        page.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        page.Children.Add(BuildPageHeader("‹  BACK TO PROFILE", CloseSettings, "SETTINGS", "Race Day Live configuration and MX Bikes file links."));

        var scroll = new ScrollViewer
        {
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled
        };
        var body = new StackPanel { Margin = new Thickness(32, 26, 32, 40) };
        scroll.Content = body;
        Grid.SetRow(scroll, 1);
        page.Children.Add(scroll);

        body.Children.Add(SectionTitle("GAME FILE LINKS", "Set these manually when auto-detection does not match the user's MX Bikes installation. Saved links take priority in the Garage."));

        var saved = GameFileLinks.Load();
        var fields = new Dictionary<string, TextBox>(StringComparer.OrdinalIgnoreCase);

        void AddPathRow(string key, string title, string help, string value)
        {
            var card = Card(new Thickness(0, 0, 0, 10));
            var grid = new Grid { Margin = new Thickness(18, 14, 18, 14) };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(190) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            card.Child = grid;

            var left = new StackPanel { VerticalAlignment = VerticalAlignment.Center };
            left.Children.Add(Label(title, 11, "#F2F7FB", true));
            var helper = Label(help, 9, "#688596", false, new Thickness(0, 3, 12, 0));
            helper.TextWrapping = TextWrapping.Wrap;
            left.Children.Add(helper);
            grid.Children.Add(left);

            var editWrap = new Grid { Margin = new Thickness(10, 0, 10, 0) };
            editWrap.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            editWrap.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            var box = new TextBox
            {
                Text = value ?? string.Empty,
                Background = Brush("#030E18"),
                Foreground = Brush("#F7FBFF"),
                BorderBrush = Brush("#0A5D8E"),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(10, 7, 10, 7),
                FontSize = 11,
                VerticalContentAlignment = VerticalAlignment.Center
            };
            fields[key] = box;
            editWrap.Children.Add(box);
            var status = Label(GameFileLinks.Exists(box.Text) ? "LINK FOUND" : (string.IsNullOrWhiteSpace(box.Text) ? "NOT SET" : "PATH NOT FOUND"), 8.5,
                GameFileLinks.Exists(box.Text) ? "#2BD672" : "#F4C542", true, new Thickness(2, 5, 0, 0));
            Grid.SetRow(status, 1);
            editWrap.Children.Add(status);
            box.TextChanged += (_, _) =>
            {
                var ok = GameFileLinks.Exists(box.Text);
                status.Text = ok ? "LINK FOUND" : (string.IsNullOrWhiteSpace(box.Text) ? "NOT SET" : "PATH NOT FOUND");
                status.Foreground = Brush(ok ? "#2BD672" : "#F4C542");
            };
            Grid.SetColumn(editWrap, 1);
            grid.Children.Add(editWrap);

            var browse = new Button
            {
                Content = "BROWSE",
                Background = ButtonBackground(),
                Foreground = Brush("#F7FBFF"),
                BorderBrush = Brush("#0A78B7"),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(13, 8, 13, 8),
                Cursor = Cursors.Hand,
                VerticalAlignment = VerticalAlignment.Center
            };
            browse.Click += (_, _) =>
            {
                var dialog = new Microsoft.Win32.OpenFolderDialog
                {
                    Title = "Select " + title,
                    Multiselect = false
                };
                if (!string.IsNullOrWhiteSpace(box.Text) && Directory.Exists(box.Text)) dialog.InitialDirectory = box.Text;
                if (dialog.ShowDialog() == true) box.Text = dialog.FolderName;
            };
            Grid.SetColumn(browse, 2);
            grid.Children.Add(browse);
            body.Children.Add(card);
        }

        AddPathRow("game", "MX Bikes Install", "Folder containing mxbikes.exe and stock game content.", saved.GameInstallDirectory);
        AddPathRow("user", "MX Bikes User Data", "Usually Documents\\PiBoSo\\MX Bikes.", saved.UserDataDirectory);
        AddPathRow("mods", "Mods Folder", "Root MX Bikes mods folder.", saved.ModsDirectory);
        AddPathRow("bikes", "Bikes Folder", "Folder containing installed bike folders and PKZ files.", saved.BikesDirectory);
        AddPathRow("rider", "Rider Folder", "Root rider content folder.", saved.RiderDirectory);
        AddPathRow("helmets", "Helmets Folder", "Installed helmet models and paints.", saved.HelmetsDirectory);
        AddPathRow("boots", "Boots Folder", "Installed boot models and paints.", saved.BootsDirectory);
        AddPathRow("paints", "Paints Folder", "Optional custom paint/library location.", saved.PaintsDirectory);

        var actions = new WrapPanel { Margin = new Thickness(0, 12, 0, 0) };
        var feedback = Label("", 10, "#88A5BA", true, new Thickness(14, 9, 0, 0));

        GameFileLinkSettings ReadFields() => new(
            fields["game"].Text,
            fields["user"].Text,
            fields["mods"].Text,
            fields["bikes"].Text,
            fields["rider"].Text,
            fields["helmets"].Text,
            fields["boots"].Text,
            fields["paints"].Text);

        void WriteFields(GameFileLinkSettings s)
        {
            fields["game"].Text = s.GameInstallDirectory;
            fields["user"].Text = s.UserDataDirectory;
            fields["mods"].Text = s.ModsDirectory;
            fields["bikes"].Text = s.BikesDirectory;
            fields["rider"].Text = s.RiderDirectory;
            fields["helmets"].Text = s.HelmetsDirectory;
            fields["boots"].Text = s.BootsDirectory;
            fields["paints"].Text = s.PaintsDirectory;
        }

        Button ActionButton(string text, string color = "#0A2235") => new()
        {
            Content = text,
            Background = color == "#0A4F78" ? AccentButtonBackground() : ButtonBackground(),
            Foreground = Brush("#F7FBFF"),
            BorderBrush = Brush("#0A78B7"),
            BorderThickness = new Thickness(1),
            Padding = new Thickness(16, 9, 16, 9),
            Margin = new Thickness(0, 0, 9, 9),
            Cursor = Cursors.Hand
        };

        var auto = ActionButton("AUTO-FILL FROM MX BIKES");
        auto.Click += async (_, _) =>
        {
            if (_context is null) return;
            try
            {
                feedback.Text = "DETECTING MX BIKES…";
                var env = await _context.MXBikes.DetectEnvironmentAsync();
                WriteFields(GameFileLinks.AutoFill(ReadFields(), env));
                feedback.Text = "AUTO-FILL COMPLETE";
                feedback.Foreground = Brush("#2BD672");
            }
            catch (Exception ex)
            {
                feedback.Text = "AUTO-FILL FAILED · " + ex.Message;
                feedback.Foreground = Brush("#FF5964");
            }
        };
        actions.Children.Add(auto);

        var clear = ActionButton("CLEAR LINKS");
        clear.Click += (_, _) =>
        {
            WriteFields(new());
            feedback.Text = "LINKS CLEARED · SAVE TO APPLY";
            feedback.Foreground = Brush("#F4C542");
        };
        actions.Children.Add(clear);

        var save = ActionButton("SAVE & RESCAN", "#0A4F78");
        save.Click += async (_, _) =>
        {
            try
            {
                feedback.Text = "SAVING…";
                await GameFileLinks.SaveAsync(ReadFields());
                var count = GameFileLinks.ScanManualBikes().Count;
                feedback.Text = $"SAVED · {count} MANUALLY LINKED BIKE ENTRIES FOUND";
                feedback.Foreground = Brush("#2BD672");
            }
            catch (Exception ex)
            {
                feedback.Text = "SAVE FAILED · " + ex.Message;
                feedback.Foreground = Brush("#FF5964");
            }
        };
        actions.Children.Add(save);
        actions.Children.Add(feedback);
        body.Children.Add(actions);

        var note = Card(new Thickness(0, 18, 0, 0));
        var noteStack = new StackPanel { Margin = new Thickness(18) };
        noteStack.Children.Add(Label("MANUAL LINKS OVERRIDE AUTO-DETECTION", 10, "#079CFF", true));
        var noteBody = Label("The Garage uses the manually linked Bikes folder first for matching bike IDs. Auto-detected game content is still kept as a fallback, so users can mix stock and mod locations safely.", 10.5, "#88A5BA", false, new Thickness(0, 6, 0, 0));
        noteBody.TextWrapping = TextWrapping.Wrap;
        noteStack.Children.Add(noteBody);
        note.Child = noteStack;
        body.Children.Add(note);

        _settingsView = page;
        host.Children.Add(page);
    }

    private void CloseSettings()
    {
        var host = _pageHost;
        var profile = _profileView;
        if (host is null || profile is null) return;
        if (_settingsView is not null)
        {
            host.Children.Remove(_settingsView);
            _settingsView = null;
        }
        profile.Visibility = Visibility.Visible;
    }

    private Border BuildGarageCard()
    {
        var card = Card(new Thickness(0, 0, 6, 0));
        card.MinHeight = 176;
        card.ClipToBounds = true;
        card.Cursor = Cursors.Hand;
        card.ToolTip = "Open the MX Bikes bike library inside Race Day Live";
        card.MouseLeftButtonUp += async (_, _) => await OpenBikeLibraryAsync();

        var root = new Grid { Background = ThemeArt.RiderBrush() };
        card.Child = root;
        root.Children.Add(new Rectangle
        {
            Fill = Brush("#9A03111D"),
            IsHitTestVisible = false
        });
        root.Children.Add(new Polygon
        {
            Points = new PointCollection(new[] { new Point(160, -20), new Point(255, -20), new Point(115, 205), new Point(25, 205) }),
            Fill = Brush("#007ECC"), Opacity = 0.20, IsHitTestVisible = false
        });
        root.Children.Add(new Polygon
        {
            Points = new PointCollection(new[] { new Point(225, -20), new Point(270, -20), new Point(130, 205), new Point(92, 205) }),
            Fill = Brush("#1CC8FF"), Opacity = 0.17, IsHitTestVisible = false
        });
        root.Children.Add(new TextBlock
        {
            Text = "GARAGE", Foreground = Brush("#0AAEFF"), FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic, FontSize = 38, Opacity = 0.08,
            HorizontalAlignment = HorizontalAlignment.Right, VerticalAlignment = VerticalAlignment.Bottom,
            Margin = new Thickness(0,0,10,-3), IsHitTestVisible = false
        });

        var content = new Grid { Margin = new Thickness(18, 14, 18, 15) };
        content.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        content.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        content.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.Children.Add(content);

        var header = new Grid();
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var garageTitle = Label("GARAGE", 10, "#F7FBFF", true); garageTitle.FontStyle = FontStyles.Italic;
        header.Children.Add(garageTitle);
        _garageSyncText = Label("CONNECTING…", 8.5, "#0AB9FF", true);
        Grid.SetColumn(_garageSyncText, 1); header.Children.Add(_garageSyncText); content.Children.Add(header);

        var bikeStack = new StackPanel { VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 10, 0, 7) };
        bikeStack.Children.Add(Label("MX BIKES LOADOUT", 8.5, "#7FA5BA", true));
        _garageBikeText = Label("READING GAME PROFILE…", 18, "#FFFFFF", true, new Thickness(0, 4, 0, 0));
        _garageBikeText.FontFamily = new FontFamily("Segoe UI Black"); _garageBikeText.FontStyle = FontStyles.Italic;
        _garageBikeText.TextTrimming = TextTrimming.CharacterEllipsis; bikeStack.Children.Add(_garageBikeText);
        _garagePaintText = Label("", 10, "#90AFC0", false, new Thickness(0, 4, 0, 0));
        _garagePaintText.TextTrimming = TextTrimming.CharacterEllipsis; bikeStack.Children.Add(_garagePaintText);
        Grid.SetRow(bikeStack, 1); content.Children.Add(bikeStack);

        var footer = new Border { BorderBrush = Brush("#0A5A89"), BorderThickness = new Thickness(0, 1, 0, 0), Padding = new Thickness(0, 8, 0, 0) };
        var footerLabel = Label("OPEN MX BIKES BIKE LIBRARY  ›", 8.5, "#0AB9FF", true);
        footerLabel.Effect = Glow("#008DFF", 10, 0.40); footer.Child = footerLabel;
        Grid.SetRow(footer, 2); content.Children.Add(footer);
        return card;
    }

    private async Task OpenBikeLibraryAsync()
    {
        var context = _context;
        var host = _pageHost;
        var profileView = _profileView;
        if (context is null || host is null || profileView is null) return;

        CancelModelLoad();
        profileView.Visibility = Visibility.Collapsed;
        if (_bikeModelView is not null)
        {
            host.Children.Remove(_bikeModelView);
            _bikeModelView = null;
        }
        if (_bikeLibraryView is not null) host.Children.Remove(_bikeLibraryView);

        var loading = BuildBikeLibraryShell();
        _bikeLibraryView = loading;
        host.Children.Add(loading);

        var body = (loading as Grid)?.Tag as StackPanel;
        if (body is null) return;
        body.Children.Clear();
        body.Children.Add(Label("SCANNING MX BIKES BIKE LIBRARY…", 14, "#88A5BA", true, new Thickness(0, 26, 0, 0)));

        try
        {
            var current = await context.MXBikes.ReadActiveSelectionAsync();
            var content = await context.MXBikes.ScanInstalledContentAsync();
            var bikeMap = content
                .Where(x => string.Equals(x.ContentType, "BIKE", StringComparison.OrdinalIgnoreCase))
                .GroupBy(x => x.Id, StringComparer.OrdinalIgnoreCase)
                .ToDictionary(g => g.Key, g => g.First(), StringComparer.OrdinalIgnoreCase);
            foreach (var manual in GameFileLinks.ScanManualBikes())
                bikeMap[manual.Id] = manual; // manual Settings link wins
            var bikes = bikeMap.Values
                .OrderBy(x => Friendly(x.DisplayName), StringComparer.OrdinalIgnoreCase)
                .ToArray();

            body.Children.Clear();
            body.Children.Add(BuildLibrarySummary(bikes.Length, current));

            if (bikes.Length == 0)
            {
                var empty = Card(new Thickness(0, 16, 0, 0));
                empty.Child = new StackPanel
                {
                    Margin = new Thickness(22),
                    Children =
                    {
                        Label("NO BIKES FOUND", 17, "#F2F7FB", true),
                        Label("Race Day Live did not find bike entries in the MX Bikes install/mod bike folders.", 12, "#88A5BA", false, new Thickness(0, 6, 0, 0))
                    }
                };
                body.Children.Add(empty);
                return;
            }

            var wrap = new WrapPanel { Margin = new Thickness(0, 16, 0, 0) };
            foreach (var bike in bikes) wrap.Children.Add(BuildBikeTile(bike, current));
            body.Children.Add(wrap);
        }
        catch (Exception ex)
        {
            body.Children.Clear();
            body.Children.Add(ErrorCard("BIKE LIBRARY COULD NOT LOAD", ex.Message));
        }
    }

    private FrameworkElement BuildBikeLibraryShell()
    {
        var page = new Grid { Background = PageBackground() };
        page.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        page.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        page.Children.Add(BuildPageHeader("‹  BACK TO PROFILE", CloseBikeLibrary, "MX BIKES GARAGE", "Installed bikes loaded directly into Race Day Live — MX Bikes stays closed."));

        var scroll = new ScrollViewer
        {
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled
        };
        var body = new StackPanel { Margin = new Thickness(32, 26, 32, 36) };
        scroll.Content = body;
        Grid.SetRow(scroll, 1);
        page.Children.Add(scroll);
        page.Tag = body;
        return page;
    }

    private FrameworkElement BuildLibrarySummary(int bikeCount, MXBikeSelection current)
    {
        var summary = Card(new Thickness(0));
        summary.Background = new LinearGradientBrush(Color("#0A2D44"), Color("#06131F"), 25);
        var grid = new Grid { Margin = new Thickness(22, 18, 22, 18) };
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        summary.Child = grid;

        var left = new StackPanel();
        left.Children.Add(Label("CURRENT MX BIKES BIKE", 9, "#079CFF", true));
        left.Children.Add(Label(string.IsNullOrWhiteSpace(current.BikeId) ? "NO BIKE SELECTED" : Friendly(current.BikeId), 20, "#F2F7FB", true, new Thickness(0, 5, 0, 0)));
        left.Children.Add(Label(string.IsNullOrWhiteSpace(current.BikePaint) ? "Default paint" : Friendly(current.BikePaint), 11, "#88A5BA", false, new Thickness(0, 3, 0, 0)));
        grid.Children.Add(left);

        var right = new StackPanel { VerticalAlignment = VerticalAlignment.Center, HorizontalAlignment = HorizontalAlignment.Right };
        right.Children.Add(Label("BIKES FOUND", 9, "#88A5BA", true));
        right.Children.Add(Label(bikeCount.ToString(), 25, "#2BD672", true));
        Grid.SetColumn(right, 1);
        grid.Children.Add(right);
        return summary;
    }

    private FrameworkElement BuildBikeTile(MXContentItem bike, MXBikeSelection current)
    {
        var selected = string.Equals(bike.Id, current.BikeId, StringComparison.OrdinalIgnoreCase);
        var card = new Border
        {
            Width = 260,
            MinHeight = 148,
            Margin = new Thickness(0, 0, 14, 14),
            Padding = new Thickness(17),
            Background = selected ? ThemeArt.RiderBrush() : PanelBackground(),
            BorderBrush = selected ? Brush("#14B8FF") : Brush("#0A5A89"),
            BorderThickness = new Thickness(selected ? 2 : 1),
            CornerRadius = new CornerRadius(13),
            Effect = selected ? Glow("#008DFF", 18, 0.34) : Glow("#003D66", 12, 0.16),
            Cursor = Cursors.Hand,
            ToolTip = "View this bike's actual installed MX Bikes 3D model"
        };
        card.MouseLeftButtonUp += async (_, _) => await OpenBikeModelAsync(bike);

        var stack = new StackPanel();
        card.Child = stack;
        var header = new Grid();
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.Children.Add(Label(selected ? "CURRENT BIKE" : "MX BIKES BIKE", 8.5, selected ? "#2BD672" : "#079CFF", true));
        var package = Label(bike.IsPackaged ? "PKZ" : "FOLDER", 8, bike.IsReadableByRaceDayLive ? "#88A5BA" : "#F4C542", true);
        Grid.SetColumn(package, 1);
        header.Children.Add(package);
        stack.Children.Add(header);

        var bikeName = Label(Friendly(bike.DisplayName), 16, "#F2F7FB", true, new Thickness(0, 12, 0, 5));
        bikeName.TextWrapping = TextWrapping.Wrap;
        stack.Children.Add(bikeName);
        stack.Children.Add(Label(bike.IsReadableByRaceDayLive ? "Installed · exact source linked" : "Installed · protected package", 10, bike.IsReadableByRaceDayLive ? "#88A5BA" : "#F4C542"));
        stack.Children.Add(Label("VIEW 3D MODEL  ›", 9, "#079CFF", true, new Thickness(0, 13, 0, 0)));
        return card;
    }

    private async Task OpenBikeModelAsync(MXContentItem bike)
    {
        var host = _pageHost;
        if (host is null) return;

        CancelModelLoad();
        _modelLoadCts = new CancellationTokenSource();
        var token = _modelLoadCts.Token;

        if (_bikeLibraryView is not null) host.Children.Remove(_bikeLibraryView);
        if (_bikeModelView is not null) host.Children.Remove(_bikeModelView);

        var page = new Grid { Background = PageBackground() };
        page.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        page.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        page.Children.Add(BuildPageHeader("‹  BACK TO GARAGE", CloseBikeModel, Friendly(bike.DisplayName), "Exact installed MX Bikes source · in-app 3D viewer"));

        var scroll = new ScrollViewer
        {
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled
        };
        var body = new StackPanel { Margin = new Thickness(32, 24, 32, 34) };
        body.Children.Add(Label("RESOLVING INSTALLED BIKE → EDF MODEL…", 14, "#079CFF", true));
        body.Children.Add(Label(bike.Path, 10, "#88A5BA", false, new Thickness(0, 7, 0, 0)));
        scroll.Content = body;
        Grid.SetRow(scroll, 1);
        page.Children.Add(scroll);

        _bikeModelView = page;
        host.Children.Add(page);

        try
        {
            var result = await BikeModelViewer.CreateAsync(bike, token);
            token.ThrowIfCancellationRequested();
            body.Children.Clear();
            body.Children.Add(ModelLinkCard(result.SourcePath, result.ModelDescription));
            body.Children.Add(result.View);
            body.Children.Add(Label("DRAG TO ROTATE  •  MOUSE WHEEL TO ZOOM", 9, "#5E8299", true, new Thickness(2, 10, 0, 0)));
        }
        catch (OperationCanceledException)
        {
        }
        catch (Exception ex)
        {
            if (token.IsCancellationRequested) return;
            body.Children.Clear();
            body.Children.Add(ModelLinkCard(bike.Path, "Model unavailable"));
            body.Children.Add(ErrorCard("EXACT 3D MODEL COULD NOT LOAD", ex.Message));
        }
    }

    private FrameworkElement ModelLinkCard(string sourcePath, string modelDescription)
    {
        var card = Card(new Thickness(0, 0, 0, 16));
        var stack = new StackPanel { Margin = new Thickness(20, 16, 20, 16) };
        stack.Children.Add(Label("MX BIKES SOURCE", 9, "#079CFF", true));
        var source = Label(sourcePath, 11, "#C5D5E0", false, new Thickness(0, 5, 0, 10));
        source.TextWrapping = TextWrapping.Wrap;
        stack.Children.Add(source);
        stack.Children.Add(Label("RESOLVED 3D MODEL", 9, "#079CFF", true));
        var model = Label(modelDescription, 11, "#F2F7FB", true, new Thickness(0, 5, 0, 0));
        model.TextWrapping = TextWrapping.Wrap;
        stack.Children.Add(model);
        card.Child = stack;
        return card;
    }

    private FrameworkElement BuildPageHeader(string backText, Action backAction, string titleText, string subtitleText)
    {
        var top = new Border
        {
            Background = ThemeArt.LiveBrush(),
            BorderBrush = Brush("#00BFFF"),
            BorderThickness = new Thickness(0, 0, 0, 1),
            Padding = new Thickness(28, 19, 28, 18),
            Effect = Glow("#004E78", 12, 0.16)
        };
        var grid = new Grid();
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        top.Child = grid;
        grid.Children.Add(new Rectangle
        {
            Fill = Brush("#B2040E18"),
            IsHitTestVisible = false
        });

        var back = new Button
        {
            Content = backText,
            Background = ButtonBackground(),
            Foreground = Brush("#F7FBFF"),
            BorderBrush = Brush("#0A78B7"),
            BorderThickness = new Thickness(1),
            Padding = new Thickness(16, 9, 16, 9),
            Cursor = Cursors.Hand,
            FontFamily = new FontFamily("Segoe UI Semibold")
        };
        back.Click += (_, _) => backAction();
        grid.Children.Add(back);

        var title = new StackPanel { Margin = new Thickness(24, 0, 0, 0), VerticalAlignment = VerticalAlignment.Center };
        title.Children.Add(Label(titleText, 24, "#F2F7FB", true));
        title.Children.Add(Label(subtitleText, 11, "#88A5BA", false, new Thickness(0, 3, 0, 0)));
        Grid.SetColumn(title, 1);
        grid.Children.Add(title);
        return top;
    }

    private FrameworkElement ErrorCard(string title, string message)
    {
        var error = Card(new Thickness(0, 16, 0, 0));
        var stack = new StackPanel { Margin = new Thickness(22) };
        stack.Children.Add(Label(title, 17, "#FF5964", true));
        var body = Label(message, 12, "#88A5BA", false, new Thickness(0, 6, 0, 0));
        body.TextWrapping = TextWrapping.Wrap;
        stack.Children.Add(body);
        error.Child = stack;
        return error;
    }

    private void CloseBikeModel()
    {
        CancelModelLoad();
        var host = _pageHost;
        if (host is null) return;
        if (_bikeModelView is not null)
        {
            host.Children.Remove(_bikeModelView);
            _bikeModelView = null;
        }
        if (_bikeLibraryView is not null && !host.Children.Contains(_bikeLibraryView))
            host.Children.Add(_bikeLibraryView);
    }

    private void CloseBikeLibrary()
    {
        CancelModelLoad();
        var host = _pageHost;
        var profile = _profileView;
        if (host is null || profile is null) return;
        if (_bikeModelView is not null)
        {
            host.Children.Remove(_bikeModelView);
            _bikeModelView = null;
        }
        if (_bikeLibraryView is not null)
        {
            host.Children.Remove(_bikeLibraryView);
            _bikeLibraryView = null;
        }
        profile.Visibility = Visibility.Visible;
    }

    private void CancelModelLoad()
    {
        _modelLoadCts?.Cancel();
        _modelLoadCts?.Dispose();
        _modelLoadCts = null;
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
                _profileWatcher.Changed += (_, _) => QueueRefresh(false);
                _profileWatcher.Created += (_, _) => QueueRefresh(false);
                _profileWatcher.Renamed += (_, _) => QueueRefresh(false);
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
                _globalWatcher.Changed += (_, _) => QueueRefresh(true);
                _globalWatcher.Created += (_, _) => QueueRefresh(true);
                _globalWatcher.Renamed += (_, _) => QueueRefresh(true);
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
        _profileWatcher?.Dispose(); _profileWatcher = null;
        _globalWatcher?.Dispose(); _globalWatcher = null;
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
        Background = PanelBackground(),
        BorderBrush = Brush("#00AFFF"),
        BorderThickness = new Thickness(1.55),
        CornerRadius = new CornerRadius(11),
        Margin = margin,
        Effect = Glow("#008CFF", 22, 0.36),
        SnapsToDevicePixels = true
    };

    private static FrameworkElement SnapshotCard(string kicker, string title, string subtitle, int column)
    {
        var card = Card(column == 0 ? new Thickness(0, 0, 9, 0) : new Thickness(9, 0, 0, 0));
        var stack = new StackPanel { Margin = new Thickness(22) };
        var kickerText = Label(kicker, 9.5, "#0AAEFF", true);
        kickerText.FontFamily = new FontFamily("Segoe UI Black");
        kickerText.FontStyle = FontStyles.Italic;
        stack.Children.Add(kickerText);
        stack.Children.Add(Label(title, 17, "#F2F7FB", true, new Thickness(0, 7, 0, 6)));
        stack.Children.Add(Label(subtitle, 12, "#88A5BA"));
        card.Child = stack;
        Grid.SetColumn(card, column);
        return card;
    }

    private static FrameworkElement SectionTitle(string title, string subtitle)
    {
        var row = new Grid { Margin = new Thickness(1, 3, 0, 11) };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(7) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.Children.Add(new Border
        {
            Width = 5, Margin = new Thickness(0, 1, 0, 1), CornerRadius = new CornerRadius(2),
            Background = Brush("#0AB9FF"), Effect = Glow("#009CFF", 16, 0.75)
        });
        var stack = new StackPanel { Margin = new Thickness(12, 0, 0, 0) };
        var heading = Label(title, 20, "#FFFFFF", true);
        heading.FontFamily = new FontFamily("Segoe UI Black"); heading.FontStyle = FontStyles.Italic;
        heading.Effect = Glow("#001523", 6, 0.8); stack.Children.Add(heading);
        if (!string.IsNullOrWhiteSpace(subtitle)) stack.Children.Add(Label(subtitle, 10.5, "#7EA1B5", false, new Thickness(0, 2, 0, 0)));
        Grid.SetColumn(stack, 1); row.Children.Add(stack); return row;
    }

    private static void AddStat(Grid grid, int col, string title, string value, string valueColor)
    {
        var card = Card(new Thickness(col == 0 ? 0 : 6, 0, col == 3 ? 0 : 6, 0));
        card.Background = FeatureCardBackground(col == 0 ? "#12314A" : "#0A2437", "#050F18");
        var root = new Grid { Margin = new Thickness(0) };
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(5) });
        root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        root.Children.Add(new Border
        {
            Background = Brush(col == 0 ? "#F4C542" : col == 1 ? "#2BD672" : "#0AAEFF"),
            CornerRadius = new CornerRadius(10, 0, 0, 10), Effect = Glow(col == 0 ? "#F4C542" : "#0AAEFF", 12, 0.35)
        });
        var stack = new StackPanel { Margin = new Thickness(14, 13, 14, 14) };
        var statTitle = Label(title, 9, "#7699AD", true); statTitle.FontStyle = FontStyles.Italic; stack.Children.Add(statTitle);
        var statValue = Label(value, 16, valueColor, true, new Thickness(0, 5, 0, 0));
        statValue.FontFamily = new FontFamily("Segoe UI Black"); statValue.FontStyle = FontStyles.Italic; stack.Children.Add(statValue);
        Grid.SetColumn(stack, 1); root.Children.Add(stack); card.Child = root; Grid.SetColumn(card, col); grid.Children.Add(card);
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

    private static ImageBrush? TryImageBrush(string? path)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path)) return null;
        try
        {
            var bitmap = new System.Windows.Media.Imaging.BitmapImage();
            bitmap.BeginInit();
            bitmap.CacheOption = System.Windows.Media.Imaging.BitmapCacheOption.OnLoad;
            bitmap.UriSource = new Uri(path, UriKind.Absolute);
            bitmap.EndInit();
            bitmap.Freeze();
            var brush = new ImageBrush(bitmap)
            {
                Stretch = Stretch.Uniform,
                AlignmentX = AlignmentX.Center,
                AlignmentY = AlignmentY.Center
            };
            brush.Freeze();
            return brush;
        }
        catch
        {
            return null;
        }
    }

    private static void AddRaceNightBackdrop(Grid host)
    {
        var canvas = new Canvas { IsHitTestVisible = false, Opacity = 1.0 };
        Panel.SetZIndex(canvas, -10);

        var themeBackdrop = new Rectangle
        {
            Width = 1600,
            Height = 360,
            Fill = ThemeArt.HeaderBrush(),
            Opacity = 0.20,
            Effect = new BlurEffect { Radius = 10 }
        };
        Canvas.SetLeft(themeBackdrop, 0);
        Canvas.SetTop(themeBackdrop, -70);
        canvas.Children.Add(themeBackdrop);

        var glow = new Ellipse
        {
            Width = 900, Height = 900,
            Fill = new RadialGradientBrush(Color("#087FC4"), Color("#01070D")) { RadiusX = 0.72, RadiusY = 0.72 },
            Opacity = 0.13
        };
        Canvas.SetLeft(glow, -330); Canvas.SetTop(glow, -430); canvas.Children.Add(glow);

        var slash1 = new Polygon
        {
            Points = new PointCollection(new[] { new Point(930,-80), new Point(1160,-80), new Point(650,920), new Point(470,920) }),
            Fill = Brush("#006BAA"), Opacity = 0.055
        };
        canvas.Children.Add(slash1);
        var slash2 = new Polygon
        {
            Points = new PointCollection(new[] { new Point(1110,-80), new Point(1205,-80), new Point(720,920), new Point(650,920) }),
            Fill = Brush("#11C4FF"), Opacity = 0.045
        };
        canvas.Children.Add(slash2);

        for (var i = 0; i < 12; i++)
        {
            var line = new Border { Height = 1, Width = 1600, Background = Brush("#0C4564"), Opacity = 0.055 };
            Canvas.SetLeft(line, 0); Canvas.SetTop(line, 70 + i * 72); canvas.Children.Add(line);
        }
        host.Children.Add(canvas);
    }

    private static Brush FeatureCardBackground(string top, string bottom)
    {
        var brush = new LinearGradientBrush { StartPoint = new Point(0, 0), EndPoint = new Point(1, 1) };
        brush.GradientStops.Add(new GradientStop(Color(top), 0.00));
        brush.GradientStops.Add(new GradientStop(Color("#073252"), 0.34));
        brush.GradientStops.Add(new GradientStop(Color("#061522"), 0.66));
        brush.GradientStops.Add(new GradientStop(Color(bottom), 1.00));
        return brush;
    }

    private static Brush PageBackground()
    {
        var brush = new LinearGradientBrush { StartPoint = new Point(0, 0), EndPoint = new Point(1, 1) };
        brush.GradientStops.Add(new GradientStop(Color("#01050B"), 0.00));
        brush.GradientStops.Add(new GradientStop(Color("#031422"), 0.38));
        brush.GradientStops.Add(new GradientStop(Color("#02101B"), 0.72));
        brush.GradientStops.Add(new GradientStop(Color("#071D2F"), 1.00));
        return brush;
    }

    private static Brush PanelBackground()
    {
        var brush = new LinearGradientBrush { StartPoint = new Point(0, 0), EndPoint = new Point(1, 1) };
        brush.GradientStops.Add(new GradientStop(Color("#0B2B45"), 0.00));
        brush.GradientStops.Add(new GradientStop(Color("#06192A"), 0.48));
        brush.GradientStops.Add(new GradientStop(Color("#01070D"), 1.00));
        return brush;
    }

    private static Brush HeroBackground()
    {
        var brush = new LinearGradientBrush { StartPoint = new Point(0, 0), EndPoint = new Point(1, 1) };
        brush.GradientStops.Add(new GradientStop(Color("#02070D"), 0.00));
        brush.GradientStops.Add(new GradientStop(Color("#0A4166"), 0.42));
        brush.GradientStops.Add(new GradientStop(Color("#06243A"), 0.70));
        brush.GradientStops.Add(new GradientStop(Color("#01060A"), 1.00));
        return brush;
    }

    private static Brush ButtonBackground()
    {
        var brush = new LinearGradientBrush { StartPoint = new Point(0, 0), EndPoint = new Point(0, 1) };
        brush.GradientStops.Add(new GradientStop(Color("#0B2E46"), 0.00));
        brush.GradientStops.Add(new GradientStop(Color("#061725"), 1.00));
        return brush;
    }

    private static Brush AccentButtonBackground()
    {
        var brush = new LinearGradientBrush { StartPoint = new Point(0, 0), EndPoint = new Point(1, 0) };
        brush.GradientStops.Add(new GradientStop(Color("#006DCC"), 0.00));
        brush.GradientStops.Add(new GradientStop(Color("#00A7FF"), 1.00));
        return brush;
    }

    private static DropShadowEffect Glow(string color, double radius, double opacity) => new()
    {
        Color = Color(color),
        BlurRadius = radius,
        ShadowDepth = 0,
        Opacity = opacity
    };

    private static SolidColorBrush Brush(string hex) => new(Color(hex));
    private static Color Color(string hex) => (Color)ColorConverter.ConvertFromString(hex)!;
}
