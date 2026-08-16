using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace MXBRaceDayLive.Profile;

// Theme art is a real embedded JPEG resource so hot-module activation never depends on
// decoding large source-code Base64 payloads.
internal static class ThemeArt
{
    private const string ResourceName = "MXBRaceDayLive.Profile.Assets.reference-header.jpg";
    private static readonly Lazy<ImageSource> HeaderImage =
        new(LoadImage, LazyThreadSafetyMode.ExecutionAndPublication);

    public static ImageBrush HeaderBrush() => NewBrush(new Rect(0.00, 0.00, 1.00, 1.00));
    public static ImageBrush RiderBrush() => NewBrush(new Rect(0.25, 0.00, 0.45, 1.00));
    public static ImageBrush LiveBrush() => NewBrush(new Rect(0.57, 0.00, 0.43, 1.00));
    public static ImageBrush LogoBrush() => NewBrush(new Rect(0.00, 0.00, 0.38, 1.00));

    private static ImageBrush NewBrush(Rect viewbox)
    {
        var brush = new ImageBrush(HeaderImage.Value)
        {
            Stretch = Stretch.UniformToFill,
            AlignmentX = AlignmentX.Center,
            AlignmentY = AlignmentY.Center,
            ViewboxUnits = BrushMappingMode.RelativeToBoundingBox,
            Viewbox = viewbox
        };
        brush.Freeze();
        return brush;
    }

    private static ImageSource LoadImage()
    {
        using var stream = typeof(ThemeArt).Assembly.GetManifestResourceStream(ResourceName)
            ?? throw new InvalidOperationException($"Theme image resource was not found: {ResourceName}");
        var bitmap = new BitmapImage();
        bitmap.BeginInit();
        bitmap.CacheOption = BitmapCacheOption.OnLoad;
        bitmap.StreamSource = stream;
        bitmap.EndInit();
        bitmap.Freeze();
        return bitmap;
    }
}
