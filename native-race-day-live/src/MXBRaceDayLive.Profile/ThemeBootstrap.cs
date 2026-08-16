using System.Runtime.CompilerServices;
using System.Runtime.CompilerServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Shapes;

namespace MXBRaceDayLive.Profile;

internal static class ThemeBootstrap
{
    private static readonly ConditionalWeakTable<DependencyObject, object> Themed = new();
    private static readonly object Marker = new();

    [ModuleInitializer]
    internal static void Initialize()
    {
        EventManager.RegisterClassHandler(
            typeof(Grid),
            FrameworkElement.LoadedEvent,
            new RoutedEventHandler(OnGridLoaded),
            true);
    }

    private static void OnGridLoaded(object sender, RoutedEventArgs e)
    {
        if (sender is not Grid grid) return;
        if (Themed.TryGetValue(grid, out _)) return;
        Themed.Add(grid, Marker);

        try
        {
            ApplyBackdrop(grid);
            ApplyTree(grid);
        }
        catch
        {
            // Theme decoration must never block the feature module from loading.
        }
    }

    private static void ApplyBackdrop(Grid grid)
    {
        var hasDirectScroll = grid.Children.OfType<ScrollViewer>().Any();
        if (!hasDirectScroll) return;

        if (grid.Children.OfType<Rectangle>().Any(x => Equals(x.Tag, "RDL_THEME_BACKDROP"))) return;

        var art = new Rectangle
        {
            Tag = "RDL_THEME_BACKDROP",
            Fill = ThemeArt.HeaderBrush(),
            Opacity = 0.15,
            IsHitTestVisible = false,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            VerticalAlignment = VerticalAlignment.Top,
            Height = 310,
            Effect = new BlurEffect { Radius = 8 }
        };
        Panel.SetZIndex(art, -20);
        grid.Children.Insert(0, art);
    }

    private static void ApplyTree(DependencyObject root)
    {
        foreach (var border in Descendants<Border>(root))
        {
            ApplyCardSkin(border);
            ApplyHeaderSkin(border);
        }

        foreach (var button in Descendants<Button>(root))
        {
            button.BorderBrush = Brush("#00AFFF");
            button.BorderThickness = new Thickness(1.15);
            button.Background = Gradient("#0B3557", "#061521");
            button.Foreground = Brushes.White;
            button.FontFamily = new FontFamily("Segoe UI Semibold");
            button.Effect = Glow("#008CFF", 12, 0.22);
        }

        foreach (var box in Descendants<TextBox>(root))
        {
            box.Background = Brush("#020B12");
            box.BorderBrush = Brush("#087FB8");
            box.Foreground = Brushes.White;
        }

        foreach (var text in Descendants<TextBlock>(root))
        {
            var value = text.Text?.Trim().ToUpperInvariant() ?? string.Empty;
            if (value is "GARAGE" or "SETTINGS" or "MY RACES" or "MX BIKES GARAGE" or "GAME FILE LINKS")
            {
                text.FontFamily = new FontFamily("Segoe UI Black");
                text.FontStyle = FontStyles.Italic;
                text.Foreground = Brushes.White;
                text.Effect = Glow("#008CFF", 10, 0.24);
            }
        }

        foreach (var grid in Descendants<Grid>(root))
        {
            if (ContainsText(grid, "MX BIKES LOADOUT"))
                ApplyImageCard(grid, ThemeArt.RiderBrush(), "RDL_THEME_GARAGE", 0xA8);
            else if (ContainsText(grid, "GAME FILE LINKS") && ContainsText(grid, "OPEN SETTINGS"))
                ApplyImageCard(grid, ThemeArt.LiveBrush(), "RDL_THEME_SETTINGS", 0xAA);
        }
    }

    private static void ApplyCardSkin(Border border)
    {
        if (border.CornerRadius.TopLeft < 8 || border.BorderThickness.Left <= 0) return;
        border.BorderBrush = Brush("#00AFFF");
        border.BorderThickness = new Thickness(Math.Max(1.35, border.BorderThickness.Left));
        border.Effect = Glow("#008CFF", 20, 0.30);
    }

    private static void ApplyHeaderSkin(Border border)
    {
        // Existing profile hero. Size remains untouched.
        if (Math.Abs(border.Height - 286) < 0.5 && border.Child is Grid hero)
        {
            if (!hero.Children.OfType<Rectangle>().Any(x => Equals(x.Tag, "RDL_THEME_HERO")))
            {
                hero.Children.Add(new Rectangle
                {
                    Tag = "RDL_THEME_HERO",
                    Fill = ThemeArt.HeaderBrush(),
                    Opacity = 1.0,
                    IsHitTestVisible = false
                });
            }
            border.BorderBrush = Brush("#00BFFF");
            border.Effect = Glow("#009CFF", 26, 0.42);
            return;
        }

        // Existing Garage/Settings/model page headers. Their padding/height do not change.
        if (border.Padding.Left >= 26 && border.Padding.Top >= 17 && border.Child is Grid pageHeader)
        {
            border.Background = ThemeArt.LiveBrush();
            border.BorderBrush = Brush("#00BFFF");
            border.BorderThickness = new Thickness(0, 0, 0, 2);
            border.Effect = Glow("#008CFF", 18, 0.30);
            if (!pageHeader.Children.OfType<Rectangle>().Any(x => Equals(x.Tag, "RDL_THEME_PAGE_HEADER")))
            {
                pageHeader.Children.Insert(0, new Rectangle
                {
                    Tag = "RDL_THEME_PAGE_HEADER",
                    Fill = Brush("#A5030D16"),
                    IsHitTestVisible = false
                });
            }
        }
    }

    private static void ApplyImageCard(Grid grid, ImageBrush image, string tag, byte overlayAlpha)
    {
        if (grid.Children.OfType<Rectangle>().Any(x => Equals(x.Tag, tag))) return;
        grid.Background = image;
        grid.Children.Insert(0, new Rectangle
        {
            Tag = tag,
            Fill = Brush($"#{overlayAlpha:X2}03111D"),
            IsHitTestVisible = false
        });
    }

    private static bool ContainsText(DependencyObject root, string text) =>
        Descendants<TextBlock>(root).Any(x => string.Equals(x.Text?.Trim(), text, StringComparison.OrdinalIgnoreCase));

    private static IEnumerable<T> Descendants<T>(DependencyObject root) where T : DependencyObject
    {
        var count = VisualTreeHelper.GetChildrenCount(root);
        for (var i = 0; i < count; i++)
        {
            var child = VisualTreeHelper.GetChild(root, i);
            if (child is T typed) yield return typed;
            foreach (var nested in Descendants<T>(child)) yield return nested;
        }
    }

    private static LinearGradientBrush Gradient(string top, string bottom) =>
        new((Color)ColorConverter.ConvertFromString(top)!, (Color)ColorConverter.ConvertFromString(bottom)!, 90);

    private static DropShadowEffect Glow(string color, double radius, double opacity) => new()
    {
        Color = (Color)ColorConverter.ConvertFromString(color)!,
        BlurRadius = radius,
        ShadowDepth = 0,
        Opacity = opacity
    };

    private static SolidColorBrush Brush(string hex) =>
        new((Color)ColorConverter.ConvertFromString(hex)!);
}
