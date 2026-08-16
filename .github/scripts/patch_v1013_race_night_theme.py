from pathlib import Path

p = Path('native-race-day-live/src/MXBRaceDayLive.Profile/ProfileHomeFeature.cs')
s = p.read_text(encoding='utf-8')


def replace_once(old: str, new: str):
    global s
    if old not in s:
        raise SystemExit('Missing expected block:\n' + old[:240])
    s = s.replace(old, new, 1)

# Effects support.
replace_once('using System.Windows.Media;\nusing System.Windows.Shapes;', 'using System.Windows.Media;\nusing System.Windows.Media.Effects;\nusing System.Windows.Shapes;')

# Main page: same content/layout, richer game-menu surface.
s = s.replace('_pageHost = new Grid { Background = Brush("#04101B") };', '_pageHost = new Grid { Background = PageBackground() };')
s = s.replace('Background = Brush("#04101B")\n        };\n\n        var stack = new StackPanel { Margin = new Thickness(34, 26, 34, 34) };', 'Background = Brushes.Transparent\n        };\n\n        var stack = new StackPanel { Margin = new Thickness(26, 22, 26, 32) };', 1)

old_banner = '''        var banner = new Border
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
        profileStack.Children.Add(banner);'''

new_banner = '''        var banner = new Border
        {
            Height = 220,
            CornerRadius = new CornerRadius(15, 15, 0, 0),
            Background = HeroBackground(),
            BorderBrush = Brush("#0A7FC3"),
            BorderThickness = new Thickness(0, 0, 0, 1),
            ClipToBounds = true
        };
        var bannerGrid = new Grid();
        banner.Child = bannerGrid;

        bannerGrid.Children.Add(new Ellipse
        {
            Width = 520,
            Height = 520,
            Fill = new RadialGradientBrush(Color("#1B9DFF"), Color("#00121F")) { RadiusX = 0.72, RadiusY = 0.72 },
            Opacity = 0.18,
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Center,
            Margin = new Thickness(0, 0, -180, 0),
            IsHitTestVisible = false
        });
        bannerGrid.Children.Add(new Polygon
        {
            Points = new PointCollection(new[] { new Point(620, -40), new Point(790, -40), new Point(560, 260), new Point(410, 260) }),
            Fill = Brush("#009BFF"),
            Opacity = 0.13,
            IsHitTestVisible = false
        });
        bannerGrid.Children.Add(new Polygon
        {
            Points = new PointCollection(new[] { new Point(760, -40), new Point(835, -40), new Point(605, 260), new Point(540, 260) }),
            Fill = Brush("#24C8FF"),
            Opacity = 0.10,
            IsHitTestVisible = false
        });

        var brand = new StackPanel { Margin = new Thickness(28, 24, 0, 0), VerticalAlignment = VerticalAlignment.Top };
        brand.Children.Add(new TextBlock
        {
            Text = "MXB",
            Foreground = Brush("#F7FBFF"),
            FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic,
            FontSize = 44,
            CharacterSpacing = -25
        });
        var liveRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(2, -8, 0, 0) };
        liveRow.Children.Add(new TextBlock
        {
            Text = "RACE DAY ",
            Foreground = Brush("#DCEAF4"),
            FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic,
            FontSize = 20
        });
        liveRow.Children.Add(new TextBlock
        {
            Text = "LIVE",
            Foreground = Brush("#0AAEFF"),
            FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic,
            FontSize = 25,
            Effect = Glow("#008DFF", 16, 0.55)
        });
        brand.Children.Add(liveRow);
        bannerGrid.Children.Add(brand);

        bannerGrid.Children.Add(new TextBlock
        {
            Text = $"#{rider.RacingNumber}",
            Foreground = Brush("#0AAEFF"),
            FontFamily = new FontFamily("Segoe UI Black"),
            FontStyle = FontStyles.Italic,
            FontSize = 76,
            Opacity = 0.16,
            Margin = new Thickness(0, 0, 30, 10),
            HorizontalAlignment = HorizontalAlignment.Right,
            VerticalAlignment = VerticalAlignment.Bottom,
            IsHitTestVisible = false
        });
        profileStack.Children.Add(banner);'''
replace_once(old_banner, new_banner)

# Identity visual hierarchy.
s = s.replace('var identity = new Grid { Margin = new Thickness(24, 18, 24, 22) };', 'var identity = new Grid { Margin = new Thickness(24, 16, 24, 20) };', 1)
s = s.replace('avatar.Children.Add(new Ellipse { Fill = Brush("#0B2C42"), Stroke = Brush("#079CFF"), StrokeThickness = 2 });', 'avatar.Children.Add(new Ellipse { Fill = new LinearGradientBrush(Color("#0D3551"), Color("#06131F"), 45), Stroke = Brush("#0AAEFF"), StrokeThickness = 2, Effect = Glow("#008DFF", 14, 0.34) });', 1)
s = s.replace('FontFamily = new FontFamily("Segoe UI Black"),\n            FontSize = 30', 'FontFamily = new FontFamily("Segoe UI Black"),\n            FontStyle = FontStyles.Italic,\n            FontSize = 32', 1)
s = s.replace('Foreground = Brush("#F4C542"),\n            FontFamily = new FontFamily("Segoe UI Black"),\n            FontSize = 16,', 'Foreground = Brush("#0AAEFF"),\n            FontFamily = new FontFamily("Segoe UI Black"),\n            FontStyle = FontStyles.Italic,\n            FontSize = 19,', 1)

# Game-like card and page backgrounds everywhere without changing sections.
s = s.replace('var page = new Grid { Background = Brush("#04101B") };', 'var page = new Grid { Background = PageBackground() };')

# Settings input/button treatment.
s = s.replace('Background = Brush("#04101B"),\n                Foreground = Brush("#F2F7FB"),\n                BorderBrush = Brush("#155273"),\n                BorderThickness = new Thickness(1),', 'Background = Brush("#030E18"),\n                Foreground = Brush("#F7FBFF"),\n                BorderBrush = Brush("#0A5D8E"),\n                BorderThickness = new Thickness(1),', 1)
s = s.replace('Background = Brush("#0A2235"),\n                Foreground = Brush("#F2F7FB"),\n                BorderBrush = Brush("#155273"),', 'Background = ButtonBackground(),\n                Foreground = Brush("#F7FBFF"),\n                BorderBrush = Brush("#0A78B7"),', 1)
s = s.replace('Background = Brush(color),\n            Foreground = Brush("#F2F7FB"),\n            BorderBrush = Brush("#155273"),', 'Background = color == "#0A4F78" ? AccentButtonBackground() : ButtonBackground(),\n            Foreground = Brush("#F7FBFF"),\n            BorderBrush = Brush("#0A78B7"),', 1)

# Garage gets stronger race-night contrast.
s = s.replace('root.Background = new LinearGradientBrush(Color("#0A2D44"), Color("#06131F"), 35);', 'root.Background = new LinearGradientBrush(Color("#0C3A57"), Color("#030D17"), 35);', 1)
s = s.replace('Fill = Brush("#0A7FC3"), Opacity = 0.15', 'Fill = Brush("#0AAEFF"), Opacity = 0.20', 1)
s = s.replace('Fill = Brush("#17B7FF"), Opacity = 0.13', 'Fill = Brush("#24C8FF"), Opacity = 0.16', 1)

# Bike tiles inherit the new game-card language.
old_tile = '''            Background = selected ? Brush("#0B3149") : Brush("#071A29"),
            BorderBrush = selected ? Brush("#079CFF") : Brush("#155273"),
            BorderThickness = new Thickness(selected ? 2 : 1),
            CornerRadius = new CornerRadius(14),'''
new_tile = '''            Background = selected ? new LinearGradientBrush(Color("#0C3F61"), Color("#061522"), 40) : PanelBackground(),
            BorderBrush = selected ? Brush("#14B8FF") : Brush("#0A5A89"),
            BorderThickness = new Thickness(selected ? 2 : 1),
            CornerRadius = new CornerRadius(13),
            Effect = selected ? Glow("#008DFF", 18, 0.34) : Glow("#003D66", 12, 0.16),'''
replace_once(old_tile, new_tile)

# Page header: same controls/content, game HUD treatment.
replace_once('''        var top = new Border
        {
            Background = Brush("#061725"),
            BorderBrush = Brush("#155273"),
            BorderThickness = new Thickness(0, 0, 0, 1),
            Padding = new Thickness(30, 22, 30, 20)
        };''', '''        var top = new Border
        {
            Background = new LinearGradientBrush(Color("#071E30"), Color("#030D17"), 0),
            BorderBrush = Brush("#0A75AE"),
            BorderThickness = new Thickness(0, 0, 0, 1),
            Padding = new Thickness(28, 19, 28, 18),
            Effect = Glow("#004E78", 12, 0.16)
        };''')
s = s.replace('Background = Brush("#0A2235"),\n            Foreground = Brush("#F2F7FB"),\n            BorderBrush = Brush("#155273"),', 'Background = ButtonBackground(),\n            Foreground = Brush("#F7FBFF"),\n            BorderBrush = Brush("#0A78B7"),', 1)

# Cards, section titles and stat cards: global theme pass.
old_card = '''    private static Border Card(Thickness margin) => new()
    {
        Background = Brush("#071A29"),
        BorderBrush = Brush("#155273"),
        BorderThickness = new Thickness(1),
        CornerRadius = new CornerRadius(18),
        Margin = margin
    };'''
new_card = '''    private static Border Card(Thickness margin) => new()
    {
        Background = PanelBackground(),
        BorderBrush = Brush("#0A5A89"),
        BorderThickness = new Thickness(1),
        CornerRadius = new CornerRadius(14),
        Margin = margin,
        Effect = Glow("#003D66", 14, 0.16)
    };'''
replace_once(old_card, new_card)

old_section = '''    private static FrameworkElement SectionTitle(string title, string subtitle)
    {
        var stack = new StackPanel { Margin = new Thickness(2, 0, 0, 10) };
        stack.Children.Add(Label(title, 18, "#F2F7FB", true));
        if (!string.IsNullOrWhiteSpace(subtitle)) stack.Children.Add(Label(subtitle, 11, "#88A5BA", false, new Thickness(0, 3, 0, 0)));
        return stack;
    }'''
new_section = '''    private static FrameworkElement SectionTitle(string title, string subtitle)
    {
        var row = new Grid { Margin = new Thickness(2, 2, 0, 11) };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(4) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.Children.Add(new Border
        {
            Width = 3,
            Margin = new Thickness(0, 2, 0, 2),
            CornerRadius = new CornerRadius(2),
            Background = Brush("#0AAEFF"),
            Effect = Glow("#008DFF", 12, 0.50)
        });
        var stack = new StackPanel { Margin = new Thickness(10, 0, 0, 0) };
        var heading = Label(title, 18, "#F7FBFF", true);
        heading.FontFamily = new FontFamily("Segoe UI Black");
        heading.FontStyle = FontStyles.Italic;
        stack.Children.Add(heading);
        if (!string.IsNullOrWhiteSpace(subtitle)) stack.Children.Add(Label(subtitle, 10.5, "#7899AE", false, new Thickness(0, 2, 0, 0)));
        Grid.SetColumn(stack, 1);
        row.Children.Add(stack);
        return row;
    }'''
replace_once(old_section, new_section)

old_stat = '''        var stack = new StackPanel { Margin = new Thickness(17, 14, 17, 14) };
        stack.Children.Add(Label(title, 10, "#88A5BA", true));
        stack.Children.Add(Label(value, 15, valueColor, true, new Thickness(0, 5, 0, 0)));
        card.Child = stack;'''
new_stat = '''        var root = new Grid { Margin = new Thickness(16, 13, 16, 13) };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var statTitle = Label(title, 9.5, "#7899AE", true);
        root.Children.Add(statTitle);
        var statValue = Label(value, 15.5, valueColor, true, new Thickness(0, 5, 0, 0));
        statValue.FontFamily = new FontFamily("Segoe UI Black");
        Grid.SetRow(statValue, 1);
        root.Children.Add(statValue);
        card.Child = root;'''
replace_once(old_stat, new_stat)

# Snapshot cards get a compact game-HUD accent but no new information.
s = s.replace('stack.Children.Add(Label(kicker, 10, "#079CFF", true));', 'var kickerText = Label(kicker, 9.5, "#0AAEFF", true);\n        kickerText.FontFamily = new FontFamily("Segoe UI Black");\n        kickerText.FontStyle = FontStyles.Italic;\n        stack.Children.Add(kickerText);', 1)

# Add shared theme primitives before Brush/Color helpers.
marker = '    private static SolidColorBrush Brush(string hex) => new(Color(hex));\n    private static Color Color(string hex) => (Color)ColorConverter.ConvertFromString(hex)!;'
replacement = '''    private static Brush PageBackground()
    {
        var brush = new LinearGradientBrush { StartPoint = new Point(0, 0), EndPoint = new Point(1, 1) };
        brush.GradientStops.Add(new GradientStop(Color("#020914"), 0.00));
        brush.GradientStops.Add(new GradientStop(Color("#04131F"), 0.42));
        brush.GradientStops.Add(new GradientStop(Color("#02101B"), 0.72));
        brush.GradientStops.Add(new GradientStop(Color("#061827"), 1.00));
        return brush;
    }

    private static Brush PanelBackground()
    {
        var brush = new LinearGradientBrush { StartPoint = new Point(0, 0), EndPoint = new Point(1, 1) };
        brush.GradientStops.Add(new GradientStop(Color("#091D2C"), 0.00));
        brush.GradientStops.Add(new GradientStop(Color("#061521"), 0.52));
        brush.GradientStops.Add(new GradientStop(Color("#040F19"), 1.00));
        return brush;
    }

    private static Brush HeroBackground()
    {
        var brush = new LinearGradientBrush { StartPoint = new Point(0, 0), EndPoint = new Point(1, 1) };
        brush.GradientStops.Add(new GradientStop(Color("#07121D"), 0.00));
        brush.GradientStops.Add(new GradientStop(Color("#0A3552"), 0.44));
        brush.GradientStops.Add(new GradientStop(Color("#06243A"), 0.70));
        brush.GradientStops.Add(new GradientStop(Color("#020B13"), 1.00));
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
    private static Color Color(string hex) => (Color)ColorConverter.ConvertFromString(hex)!;'''
replace_once(marker, replacement)

p.write_text(s, encoding='utf-8')
print('Applied Race Night theme pass without adding/removing sections.')
