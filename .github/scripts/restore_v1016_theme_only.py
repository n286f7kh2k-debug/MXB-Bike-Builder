from pathlib import Path
import subprocess

BASE = "939318499872eab8f1fc04a08d9351227c645baa"
PROFILE = Path("native-race-day-live/src/MXBRaceDayLive.Profile/ProfileHomeFeature.cs")
PROJECT = Path("native-race-day-live/src/MXBRaceDayLive.Profile/MXBRaceDayLive.Profile.csproj")

# Restore the exact pre-v1.0.15 layout first.
source = subprocess.check_output(
    ["git", "show", f"{BASE}:{PROFILE.as_posix()}"],
    text=True,
    encoding="utf-8",
)

# Theme-only enhancement: use the EXISTING profile banner as artwork in the EXISTING banner.
needle = """        var bannerGrid = new Grid();
        banner.Child = bannerGrid;

        // Stadium glow.
"""
replacement = """        var bannerGrid = new Grid();
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
"""
if needle not in source:
    raise SystemExit("Could not find existing banner insertion point")
source = source.replace(needle, replacement, 1)

# Theme-only enhancement: use the existing avatar image in the same existing avatar slot.
old_avatar = """        var avatar = new Grid { Width = 96, Height = 96, Margin = new Thickness(0, 0, 20, 0) };
        avatar.Children.Add(new Ellipse { Fill = new LinearGradientBrush(Color("#0D3551"), Color("#06131F"), 45), Stroke = Brush("#0AAEFF"), StrokeThickness = 2, Effect = Glow("#008DFF", 14, 0.34) });
        avatar.Children.Add(new TextBlock
        {
            Text = Initials(rider.DisplayName),
            Foreground = Brushes.White,
            FontFamily = new FontFamily("Segoe UI Black"),
            FontSize = 28,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center
        });
"""
new_avatar = """        var avatar = new Grid { Width = 96, Height = 96, Margin = new Thickness(0, 0, 20, 0) };
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
"""
if old_avatar not in source:
    raise SystemExit("Could not find existing avatar block")
source = source.replace(old_avatar, new_avatar, 1)

# Add an image helper without changing layout or navigation.
helper_anchor = """    private static string Friendly(string value) =>
        string.Join(' ', (value ?? string.Empty).Replace('_', ' ').Replace('-', ' ').Split(' ', StringSplitOptions.RemoveEmptyEntries));

    private static void AddRaceNightBackdrop(Grid host)
"""
helper = """    private static string Friendly(string value) =>
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
                Stretch = Stretch.UniformToFill,
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
"""
if helper_anchor not in source:
    raise SystemExit("Could not find helper insertion point")
source = source.replace(helper_anchor, helper, 1)

PROFILE.write_text(source, encoding="utf-8")

project = PROJECT.read_text(encoding="utf-8")
project = project.replace("<Version>1.0.15</Version>", "<Version>1.0.16</Version>")
PROJECT.write_text(project, encoding="utf-8")

print("Restored pre-v1.0.15 layout and applied theme-only image treatment as v1.0.16")
