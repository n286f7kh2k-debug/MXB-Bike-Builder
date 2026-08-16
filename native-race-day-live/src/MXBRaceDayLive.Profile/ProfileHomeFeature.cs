using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Profile;

public sealed class ProfileHomeFeature : IRaceDayFeature
{
    private IRaceDayContext? _context;

    public string Id => "profile-home";
    public Version Version => new(1, 0, 1);

    public FrameworkElement CreateView(IRaceDayContext context)
    {
        _context = context;
        return Build(context.Profile.Current);
    }

    public Task OnActivatedAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;
    public Task OnDeactivatedAsync(CancellationToken cancellationToken = default) => Task.CompletedTask;
    public void Dispose() => _context = null;

    private static FrameworkElement Build(RiderProfile rider)
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

        stack.Children.Add(SectionTitle("GARAGE", ""));
        stack.Children.Add(new Border
        {
            Background = Brush("#071A29"),
            BorderBrush = Brush("#155273"),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(18),
            MinHeight = 110,
            Margin = new Thickness(0, 0, 0, 18)
        });

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

    private static SolidColorBrush Brush(string hex) => new(Color(hex));
    private static Color Color(string hex) => (Color)ColorConverter.ConvertFromString(hex)!;
}
