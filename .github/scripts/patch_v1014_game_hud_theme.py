from pathlib import Path
import re

path = Path('native-race-day-live/src/MXBRaceDayLive.Profile/ProfileHomeFeature.cs')
s = path.read_text(encoding='utf-8')

# Add a dramatic, purely visual backdrop behind the existing content.
s = s.replace(
    '_pageHost = new Grid { Background = PageBackground() };\n        _profileView = new ScrollViewer',
    '_pageHost = new Grid { Background = PageBackground(), ClipToBounds = true };\n        AddRaceNightBackdrop(_pageHost);\n        _profileView = new ScrollViewer',
    1,
)

# Replace only the existing profile banner visual; no new section is introduced.
hero_pattern = re.compile(r'''        var banner = new Border\n        \{.*?        profileStack\.Children\.Add\(banner\);''', re.S)
hero = r'''        var banner = new Border
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
        profileStack.Children.Add(banner);'''
s, n = hero_pattern.subn(hero, s, count=1)
if n != 1:
    raise SystemExit('Could not replace profile banner')

# Existing Settings card: same function, much more game-like treatment.
settings_pattern = re.compile(r'''    private Border BuildSettingsCard\(\)\n    \{.*?\n    \}\n\n    private void OpenSettings''', re.S)
settings = r'''    private Border BuildSettingsCard()
    {
        var card = Card(new Thickness(6, 0, 6, 0));
        card.MinHeight = 176;
        card.Cursor = Cursors.Hand;
        card.ToolTip = "Open Race Day Live settings";
        card.MouseLeftButtonUp += (_, _) => OpenSettings();
        card.ClipToBounds = true;

        var root = new Grid { Background = FeatureCardBackground("#0B3150", "#06131F") };
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

    private void OpenSettings'''
s, n = settings_pattern.subn(settings, s, count=1)
if n != 1:
    raise SystemExit('Could not replace settings card')

# Existing Garage card: same functionality, visually much stronger.
garage_pattern = re.compile(r'''    private Border BuildGarageCard\(\)\n    \{.*?\n    \}\n\n    private async Task OpenBikeLibraryAsync''', re.S)
garage = r'''    private Border BuildGarageCard()
    {
        var card = Card(new Thickness(0, 0, 6, 0));
        card.MinHeight = 176;
        card.ClipToBounds = true;
        card.Cursor = Cursors.Hand;
        card.ToolTip = "Open the MX Bikes bike library inside Race Day Live";
        card.MouseLeftButtonUp += async (_, _) => await OpenBikeLibraryAsync();

        var root = new Grid { Background = FeatureCardBackground("#0B3557", "#040F19") };
        card.Child = root;
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

    private async Task OpenBikeLibraryAsync'''
s, n = garage_pattern.subn(garage, s, count=1)
if n != 1:
    raise SystemExit('Could not replace garage card')

# Stronger card chrome everywhere, while retaining all existing controls/content.
card_pattern = re.compile(r'''    private static Border Card\(Thickness margin\) => new\(\)\n    \{.*?\n    \};''', re.S)
card = r'''    private static Border Card(Thickness margin) => new()
    {
        Background = PanelBackground(),
        BorderBrush = Brush("#0B6B9F"),
        BorderThickness = new Thickness(1.25),
        CornerRadius = new CornerRadius(11),
        Margin = margin,
        Effect = Glow("#0066A4", 18, 0.24),
        SnapsToDevicePixels = true
    };'''
s, n = card_pattern.subn(card, s, count=1)
if n != 1:
    raise SystemExit('Could not replace card helper')

# Replace section title with a more obvious racing title bar.
section_pattern = re.compile(r'''    private static FrameworkElement SectionTitle\(string title, string subtitle\)\n    \{.*?\n    \}\n\n    private static void AddStat''', re.S)
section = r'''    private static FrameworkElement SectionTitle(string title, string subtitle)
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

    private static void AddStat'''
s, n = section_pattern.subn(section, s, count=1)
if n != 1:
    raise SystemExit('Could not replace section title')

# HUD-style existing stat cards.
stat_pattern = re.compile(r'''    private static void AddStat\(Grid grid, int col, string title, string value, string valueColor\)\n    \{.*?\n    \}\n\n    private static TextBlock Label''', re.S)
stat = r'''    private static void AddStat(Grid grid, int col, string title, string value, string valueColor)
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

    private static TextBlock Label'''
s, n = stat_pattern.subn(stat, s, count=1)
if n != 1:
    raise SystemExit('Could not replace stat helper')

# Add visual-only helper methods immediately before PageBackground.
needle = '    private static Brush PageBackground()\n'
helpers = r'''    private static void AddRaceNightBackdrop(Grid host)
    {
        var canvas = new Canvas { IsHitTestVisible = false, Opacity = 1.0 };
        Panel.SetZIndex(canvas, -10);

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
        brush.GradientStops.Add(new GradientStop(Color("#071724"), 0.48));
        brush.GradientStops.Add(new GradientStop(Color(bottom), 1.00));
        return brush;
    }

'''
if needle not in s:
    raise SystemExit('PageBackground helper not found')
s = s.replace(needle, helpers + needle, 1)

# Make the overall page and panels visibly darker and more contrasty.
s = s.replace('new GradientStop(Color("#020914"), 0.00)', 'new GradientStop(Color("#01050B"), 0.00)')
s = s.replace('new GradientStop(Color("#04131F"), 0.42)', 'new GradientStop(Color("#031422"), 0.38)')
s = s.replace('new GradientStop(Color("#061827"), 1.00)', 'new GradientStop(Color("#071D2F"), 1.00)')
s = s.replace('new GradientStop(Color("#091D2C"), 0.00)', 'new GradientStop(Color("#0A2132"), 0.00)')
s = s.replace('new GradientStop(Color("#040F19"), 1.00)', 'new GradientStop(Color("#020A11"), 1.00)')
s = s.replace('new GradientStop(Color("#07121D"), 0.00)', 'new GradientStop(Color("#02070D"), 0.00)')
s = s.replace('new GradientStop(Color("#0A3552"), 0.44)', 'new GradientStop(Color("#0A4166"), 0.42)')
s = s.replace('new GradientStop(Color("#020B13"), 1.00)', 'new GradientStop(Color("#01060A"), 1.00)')

path.write_text(s, encoding='utf-8')
print('Applied stronger existing-app game HUD theme')
