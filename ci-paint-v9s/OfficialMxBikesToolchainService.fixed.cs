using ImageMagick;
using MXBRaceDayLive.PaintCreator.Models;
using System.IO.Compression;
using System.Text;

namespace MXBRaceDayLive.PaintCreator.Services;

public sealed record OfficialPaintTemplateAsset(
    PaintTargetType Target,
    string PsdPath,
    string PreviewPngPath,
    int Width,
    int Height,
    string SourceUrl,
    string DisplayName);

/// <summary>
/// Downloads and caches the public MX Bikes authoring files that PiBoSo publishes.
/// The stock rider uses rider.psd and mxb_rider_template.FBX as the authoritative paint/model pair.
/// </summary>
public sealed class OfficialMxBikesToolchainService
{
    public const string TemplatesUrl = "https://www.mx-bikes.com/downloads/templates.zip";
    public const string RiderModelTemplatesUrl = "https://www.mx-bikes.com/downloads/mxb_rider_templates.zip";
    public const string PaintEdUrl = "https://www.kartracing-pro.com/downloads/painted.zip";

    private static readonly HttpClient Http = CreateHttpClient();
    private static readonly SemaphoreSlim Gate = new(1, 1);

    public async Task<OfficialPaintTemplateAsset> EnsurePaintTemplateAsync(PaintTargetType target, PaintCreatorContext context, CancellationToken cancellationToken = default)
    {
        string fileName = target switch
        {
            PaintTargetType.Rider => "rider.psd",
            PaintTargetType.Helmet => "helmet.psd",
            PaintTargetType.Gloves => "gloves.psd",
            PaintTargetType.Boots => "boots.psd",
            _ => throw new NotSupportedException($"PiBoSo stock template mapping is not configured for {target}.")
        };

        await Gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            string root = GetToolRoot(context);
            string templatesRoot = Path.Combine(root, "templates");
            string psdPath = Path.Combine(templatesRoot, fileName);
            if (!File.Exists(psdPath))
                await DownloadAndExtractRequiredAsync(TemplatesUrl, templatesRoot, cancellationToken, fileName).ConfigureAwait(false);
            if (!File.Exists(psdPath)) throw new InvalidDataException($"PiBoSo templates.zip did not contain {fileName}.");

            string previewRoot = Path.Combine(root, "template-preview");
            Directory.CreateDirectory(previewRoot);
            string previewPath = Path.Combine(previewRoot, Path.GetFileNameWithoutExtension(fileName) + ".png");
            string sourceStamp = Path.Combine(previewRoot, Path.GetFileNameWithoutExtension(fileName) + ".source");
            if (!IsPreviewCurrent(psdPath, previewPath, sourceStamp))
            {
                RenderPsdComposite(psdPath, previewPath);
                await File.WriteAllTextAsync(sourceStamp,
                    $"source={psdPath}\nlength={new FileInfo(psdPath).Length}\nlastwrite={File.GetLastWriteTimeUtc(psdPath).Ticks}\n",
                    Encoding.UTF8, cancellationToken).ConfigureAwait(false);
            }

            using var image = new MagickImage(previewPath);
            int width = checked((int)image.Width);
            int height = checked((int)image.Height);
            if (width < 512 || height < 512) throw new InvalidDataException($"{fileName} rendered to an unexpected {width}×{height} canvas.");
            return new OfficialPaintTemplateAsset(target, psdPath, previewPath, width, height, TemplatesUrl, $"PIBOSO {fileName.ToUpperInvariant()}");
        }
        finally { Gate.Release(); }
    }

    public async Task<string> EnsureRiderFbxAsync(PaintCreatorContext context, CancellationToken cancellationToken = default)
    {
        await Gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            string root = GetToolRoot(context);
            string riderRoot = Path.Combine(root, "rider-model-template");
            string fbxPath = Path.Combine(riderRoot, "mxb_rider_template.FBX");
            if (!File.Exists(fbxPath))
                await DownloadAndExtractRequiredAsync(RiderModelTemplatesUrl, riderRoot, cancellationToken, "mxb_rider_template.FBX").ConfigureAwait(false);
            if (!File.Exists(fbxPath)) throw new InvalidDataException("PiBoSo mxb_rider_templates.zip did not contain mxb_rider_template.FBX.");
            return fbxPath;
        }
        finally { Gate.Release(); }
    }

    public async Task<string> EnsurePaintEdAsync(PaintCreatorContext context, CancellationToken cancellationToken = default)
    {
        // A user-provided/local PaintEd always wins. This lets Race Day Live use the exact PiBoSo PaintEd copy selected by the user.
        if (!string.IsNullOrWhiteSpace(context.PaintEdPath) && File.Exists(context.PaintEdPath)) return context.PaintEdPath;

        await Gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            string root = GetToolRoot(context);
            string paintedRoot = Path.Combine(root, "PaintEd");
            string exePath = Path.Combine(paintedRoot, "painted.exe");
            if (!File.Exists(exePath))
                await DownloadAndExtractRequiredAsync(PaintEdUrl, paintedRoot, cancellationToken, "painted.exe").ConfigureAwait(false);
            if (!File.Exists(exePath)) throw new InvalidDataException("PiBoSo painted.zip did not contain painted.exe.");
            context.PaintEdPath = exePath;
            return exePath;
        }
        finally { Gate.Release(); }
    }

    public static string GetToolRoot(PaintCreatorContext context)
    {
        string projectRoot = !string.IsNullOrWhiteSpace(context.ProjectRoot)
            ? context.ProjectRoot
            : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "MXBRaceDayLive", "PaintCreator");
        return Path.Combine(projectRoot, "OfficialMXB", "PiBoSo");
    }

    private static async Task DownloadAndExtractRequiredAsync(string url, string destinationRoot, CancellationToken cancellationToken, params string[] requiredFileNames)
    {
        Directory.CreateDirectory(destinationRoot);
        string tempRoot = Path.Combine(Path.GetTempPath(), "MXBRaceDayLive", "OfficialMXB", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(tempRoot);
        try
        {
            string zipPath = Path.Combine(tempRoot, "package.zip");
            using (var response = await Http.GetAsync(url, HttpCompletionOption.ResponseHeadersRead, cancellationToken).ConfigureAwait(false))
            {
                response.EnsureSuccessStatusCode();
                await using var input = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
                await using var output = File.Create(zipPath);
                await input.CopyToAsync(output, cancellationToken).ConfigureAwait(false);
            }

            using var archive = ZipFile.OpenRead(zipPath);
            foreach (string required in requiredFileNames)
            {
                var entry = archive.Entries.FirstOrDefault(e => string.Equals(Path.GetFileName(e.FullName), required, StringComparison.OrdinalIgnoreCase));
                if (entry == null) throw new InvalidDataException($"Official MX Bikes package {url} did not contain {required}.");
                string targetPath = Path.Combine(destinationRoot, required);
                string pending = targetPath + ".new";
                entry.ExtractToFile(pending, overwrite: true);
                if (new FileInfo(pending).Length == 0) throw new InvalidDataException($"Official MX Bikes file {required} was empty.");
                File.Move(pending, targetPath, overwrite: true);
            }

            string manifest = Path.Combine(destinationRoot, "official-source.txt");
            await File.WriteAllTextAsync(manifest,
                $"source={url}\nfetched_utc={DateTime.UtcNow:O}\nfiles={string.Join(",", requiredFileNames)}\n",
                Encoding.UTF8, cancellationToken).ConfigureAwait(false);
        }
        finally { try { Directory.Delete(tempRoot, recursive: true); } catch { } }
    }

    private static void RenderPsdComposite(string psdPath, string previewPath)
    {
        string pending = previewPath + ".new.png";
        using var images = new MagickImageCollection();
        images.Read(psdPath);
        if (images.Count == 0) throw new InvalidDataException($"Could not read the PiBoSo PSD: {Path.GetFileName(psdPath)}.");

        // PSD frame 0 is Photoshop's composite at the document canvas size. Using Merge() here is wrong:
        // layer offsets can enlarge the image beyond the real 2048x2048/2048x1024 MX Bikes template canvas.
        using var flattened = images[0].Clone();
        flattened.Format = MagickFormat.Png32;
        flattened.Write(pending);
        File.Move(pending, previewPath, overwrite: true);
    }

    private static bool IsPreviewCurrent(string psdPath, string previewPath, string stampPath)
    {
        try
        {
            if (!File.Exists(previewPath) || !File.Exists(stampPath)) return false;
            string stamp = File.ReadAllText(stampPath);
            return stamp.Contains($"length={new FileInfo(psdPath).Length}", StringComparison.Ordinal) &&
                   stamp.Contains($"lastwrite={File.GetLastWriteTimeUtc(psdPath).Ticks}", StringComparison.Ordinal);
        }
        catch { return false; }
    }

    private static HttpClient CreateHttpClient()
    {
        var client = new HttpClient { Timeout = TimeSpan.FromSeconds(90) };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("MXBRaceDayLive-PaintCreator/9.0");
        return client;
    }
}
