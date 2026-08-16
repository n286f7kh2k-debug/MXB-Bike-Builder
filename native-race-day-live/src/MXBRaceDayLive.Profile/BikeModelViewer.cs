using System.Diagnostics;
using System.IO.Compression;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Media3D;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Profile;

internal sealed record BikeModelPreviewResult(
    FrameworkElement View,
    string SourcePath,
    string ModelDescription);

internal static class BikeModelViewer
{
    private const string AssetManifestUrl =
        "https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/native-rebuild/native-race-day-live/updates/viewer-assets.json";

    private static readonly HttpClient Http = new()
    {
        Timeout = TimeSpan.FromSeconds(45)
    };

    public static async Task<BikeModelPreviewResult> CreateAsync(
        MXContentItem bike,
        CancellationToken cancellationToken = default)
    {
        var bundle = await Task.Run(() => ResolveBundle(bike), cancellationToken);
        if (FrostBikePreviewProvider.RequiresFrost(bundle.EdfFiles))
            return await FrostBikePreviewProvider.CreateAsync(bike, bundle.SourcePath, cancellationToken);

        var decoder = await EnsureDecoderAsync(cancellationToken);
        var decoded = await DecodeAsync(decoder, bundle, cancellationToken);
        var viewport = BuildViewport(decoded);
        var modelDescription = string.Join(", ", bundle.EdfFiles.Select(Path.GetFileName));
        return new BikeModelPreviewResult(viewport, bundle.SourcePath, modelDescription);
    }

    private static BikeBundle ResolveBundle(MXContentItem bike)
    {
        if (string.IsNullOrWhiteSpace(bike.Path))
            throw new InvalidOperationException("This MX Bikes bike has no source path attached to it.");

        var source = bike.Path;
        var roots = new List<string>();
        var sourceParts = new List<string>();
        var packageWasLocked = false;

        static void AddRoot(List<string> list, string? path)
        {
            if (string.IsNullOrWhiteSpace(path) || !Directory.Exists(path)) return;
            if (!list.Contains(path, StringComparer.OrdinalIgnoreCase)) list.Add(path);
        }

        if (Directory.Exists(source))
        {
            AddRoot(roots, source);
            sourceParts.Add(source);

            var siblingPkz = source.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + ".pkz";
            if (File.Exists(siblingPkz))
            {
                sourceParts.Insert(0, siblingPkz);
                try
                {
                    AddRoot(roots, ExtractReadablePkz(siblingPkz));
                }
                catch (InvalidOperationException)
                {
                    packageWasLocked = true;
                }
            }
        }
        else if (File.Exists(source) && string.Equals(Path.GetExtension(source), ".pkz", StringComparison.OrdinalIgnoreCase))
        {
            sourceParts.Add(source);

            var parent = Path.GetDirectoryName(source) ?? string.Empty;
            var companion = Path.Combine(parent, Path.GetFileNameWithoutExtension(source));
            if (Directory.Exists(companion))
            {
                AddRoot(roots, companion);
                sourceParts.Add(companion);
            }

            try
            {
                AddRoot(roots, ExtractReadablePkz(source));
            }
            catch (InvalidOperationException)
            {
                packageWasLocked = true;
            }
        }
        else if (File.Exists(source) && string.Equals(Path.GetExtension(source), ".edf", StringComparison.OrdinalIgnoreCase))
        {
            var parent = Path.GetDirectoryName(source)
                ?? throw new InvalidOperationException("The EDF source folder could not be resolved.");
            AddRoot(roots, parent);
            sourceParts.Add(source);
        }
        else
        {
            throw new FileNotFoundException("The installed MX Bikes bike source no longer exists.", source);
        }

        var edfs = roots
            .SelectMany(VisibleEdfs)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        if (edfs.Count == 0)
        {
            if (packageWasLocked && roots.Count > 0)
            {
                throw new InvalidOperationException(
                    "Race Day Live found both the creator-locked PKZ and its companion bike folder, but that folder does not contain a readable EDF model. " +
                    "This bike needs the locked-PKZ reader path Frost uses rather than a ZIP extractor.");
            }
            if (packageWasLocked)
            {
                throw new InvalidOperationException(
                    "Race Day Live found the creator-locked PKZ, but no same-named companion bike folder with readable EDF geometry was found. " +
                    "This bike needs the locked-PKZ reader path Frost uses.");
            }
            throw new InvalidOperationException("The linked bike source contains no readable MX Bikes EDF model geometry.");
        }

        string? geom = null;
        foreach (var root in roots)
        {
            geom = Directory.EnumerateFiles(root, "*.geom", SearchOption.AllDirectories)
                .OrderBy(x => Path.GetFileName(x).Length)
                .ThenBy(x => x, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault();
            if (!string.IsNullOrWhiteSpace(geom)) break;
        }

        var workingRoot = roots.FirstOrDefault() ?? Path.GetDirectoryName(edfs[0]) ?? string.Empty;
        var sourceDescription = string.Join("  +  ", sourceParts.Distinct(StringComparer.OrdinalIgnoreCase));
        return new BikeBundle(sourceDescription, workingRoot, edfs, geom);
    }

    private static List<string> VisibleEdfs(string root)
    {
        static int Score(string path)
        {
            var name = Path.GetFileName(path).ToLowerInvariant();
            var score = 0;
            if (name == "model.edf") score += 1000;
            if (name.Contains("bike")) score += 80;
            if (name.Contains("wheel")) score += 30;
            return score;
        }

        return Directory.EnumerateFiles(root, "*.edf", SearchOption.AllDirectories)
            .Where(path =>
            {
                var name = Path.GetFileName(path).ToLowerInvariant();
                return !name.EndsWith("_s.edf", StringComparison.OrdinalIgnoreCase)
                    && !name.StartsWith("c_", StringComparison.OrdinalIgnoreCase)
                    && !name.Contains("shadow", StringComparison.OrdinalIgnoreCase);
            })
            .OrderByDescending(Score)
            .ThenBy(path => Path.GetFileName(path).Length)
            .ThenBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static string ExtractReadablePkz(string packagePath)
    {
        var cache = CacheRoot("pkz");
        var info = new FileInfo(packagePath);
        var key = Sha256Text($"{Path.GetFullPath(packagePath).ToLowerInvariant()}|{info.Length}|{info.LastWriteTimeUtc.Ticks}");
        var destination = Path.Combine(cache, key);
        var ready = Path.Combine(destination, ".ready");
        if (File.Exists(ready)) return destination;

        try
        {
            using var archive = ZipFile.OpenRead(packagePath);
            var stage = destination + ".stage-" + Guid.NewGuid().ToString("N");
            Directory.CreateDirectory(stage);
            try
            {
                foreach (var entry in archive.Entries)
                {
                    if (string.IsNullOrWhiteSpace(entry.Name)) continue;
                    var ext = Path.GetExtension(entry.Name);
                    if (!string.Equals(ext, ".edf", StringComparison.OrdinalIgnoreCase)
                        && !string.Equals(ext, ".geom", StringComparison.OrdinalIgnoreCase))
                        continue;
                    if (entry.Length > 256L * 1024L * 1024L) continue;

                    var relative = entry.FullName.Replace('/', Path.DirectorySeparatorChar);
                    var target = Path.GetFullPath(Path.Combine(stage, relative));
                    var stageRoot = Path.GetFullPath(stage) + Path.DirectorySeparatorChar;
                    if (!target.StartsWith(stageRoot, StringComparison.OrdinalIgnoreCase)) continue;

                    Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                    entry.ExtractToFile(target, overwrite: true);
                }

                if (Directory.Exists(destination)) Directory.Delete(destination, recursive: true);
                Directory.Move(stage, destination);
                File.WriteAllText(ready, "ok\n");
            }
            finally
            {
                if (Directory.Exists(stage)) Directory.Delete(stage, recursive: true);
            }
        }
        catch (InvalidDataException)
        {
            throw new InvalidOperationException("This MX Bikes PKZ is creator-protected/non-ZIP.");
        }

        return destination;
    }

    private static async Task<string> EnsureDecoderAsync(CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, AssetManifestUrl);
        request.Headers.CacheControl = new System.Net.Http.Headers.CacheControlHeaderValue { NoCache = true };
        using var response = await Http.SendAsync(request, cancellationToken);
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync(cancellationToken);
        var manifest = JsonSerializer.Deserialize<ViewerAssetManifest>(json, JsonOptions)
            ?? throw new InvalidOperationException("The 3D viewer asset manifest is invalid.");

        if (string.IsNullOrWhiteSpace(manifest.DecoderUrl) || string.IsNullOrWhiteSpace(manifest.Sha256))
            throw new InvalidOperationException("The 3D viewer decoder channel is not configured.");

        var tools = CacheRoot("tools");
        var decoder = Path.Combine(tools, "mxb_asset_decoder.exe");
        if (File.Exists(decoder) && string.Equals(Sha256File(decoder), manifest.Sha256, StringComparison.OrdinalIgnoreCase))
            return decoder;

        var bytes = await Http.GetByteArrayAsync(manifest.DecoderUrl, cancellationToken);
        var actual = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        if (!string.Equals(actual, manifest.Sha256, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("The MX Bikes 3D decoder failed SHA-256 verification.");

        var temp = decoder + ".tmp";
        await File.WriteAllBytesAsync(temp, bytes, cancellationToken);
        File.Move(temp, decoder, overwrite: true);

        if (!string.IsNullOrWhiteSpace(manifest.NoticeUrl))
        {
            try
            {
                var notice = await Http.GetStringAsync(manifest.NoticeUrl, cancellationToken);
                await File.WriteAllTextAsync(Path.Combine(tools, "Frost-mxb-app-MIT.txt"), notice, cancellationToken);
            }
            catch
            {
                // The notice is also shipped beside the decoder in the update channel.
            }
        }

        return decoder;
    }

    private static async Task<DecodedModel> DecodeAsync(
        string decoderPath,
        BikeBundle bundle,
        CancellationToken cancellationToken)
    {
        var stamp = new StringBuilder("bike|");
        foreach (var path in bundle.EdfFiles.Append(bundle.GeomFile).Where(x => !string.IsNullOrWhiteSpace(x)))
        {
            var info = new FileInfo(path!);
            stamp.Append(Path.GetFullPath(path!).ToLowerInvariant()).Append('|')
                .Append(info.Length).Append('|').Append(info.LastWriteTimeUtc.Ticks).Append('|');
        }

        var decodedDir = CacheRoot("decoded");
        var output = Path.Combine(decodedDir, Sha256Text(stamp.ToString()) + ".json.gz");
        if (!File.Exists(output))
        {
            var temp = output + ".tmp";
            var psi = new ProcessStartInfo(decoderPath)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardError = true,
                RedirectStandardOutput = true,
                WorkingDirectory = bundle.RootPath
            };
            psi.ArgumentList.Add("bike");
            psi.ArgumentList.Add(temp);
            psi.ArgumentList.Add(bundle.GeomFile ?? "-");
            foreach (var edf in bundle.EdfFiles) psi.ArgumentList.Add(edf);

            using var process = new Process { StartInfo = psi };
            process.Start();
            var stderrTask = process.StandardError.ReadToEndAsync(cancellationToken);
            var stdoutTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
            using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            timeout.CancelAfter(TimeSpan.FromSeconds(60));
            try
            {
                await process.WaitForExitAsync(timeout.Token);
            }
            catch
            {
                try { if (!process.HasExited) process.Kill(entireProcessTree: true); } catch { }
                throw;
            }

            var stderr = await stderrTask;
            var stdout = await stdoutTask;
            if (process.ExitCode != 0)
            {
                if (File.Exists(temp)) File.Delete(temp);
                throw new InvalidOperationException(
                    string.IsNullOrWhiteSpace(stderr) ?
                    (string.IsNullOrWhiteSpace(stdout) ? "The EDF decoder could not read this bike model." : stdout.Trim()) : stderr.Trim());
            }
            File.Move(temp, output, overwrite: true);
        }

        return await Task.Run(() => ReadDecoded(output), cancellationToken);
    }

    private static DecodedModel ReadDecoded(string path)
    {
        using var file = File.OpenRead(path);
        using var gzip = new GZipStream(file, CompressionMode.Decompress);
        return JsonSerializer.Deserialize<DecodedModel>(gzip, JsonOptions)
            ?? throw new InvalidOperationException("The decoded MX Bikes model data is invalid.");
    }

    private static FrameworkElement BuildViewport(DecodedModel decoded)
    {
        if (!string.Equals(decoded.Format, "MXB-RDL-EDF-1", StringComparison.Ordinal)
            || decoded.Nodes is null || decoded.Nodes.Count == 0)
            throw new InvalidOperationException("The selected EDF contains no renderable MX Bikes geometry.");

        var scene = new Model3DGroup();
        scene.Children.Add(new AmbientLight(System.Windows.Media.Color.FromRgb(82, 96, 110)));
        scene.Children.Add(new DirectionalLight(Colors.White, new Vector3D(-0.5, -1.0, -1.0)));
        scene.Children.Add(new DirectionalLight(System.Windows.Media.Color.FromRgb(90, 170, 225), new Vector3D(0.8, -0.3, 0.4)));

        var material = new MaterialGroup();
        material.Children.Add(new DiffuseMaterial(new SolidColorBrush(System.Windows.Media.Color.FromRgb(124, 145, 158))));
        material.Children.Add(new SpecularMaterial(new SolidColorBrush(System.Windows.Media.Color.FromRgb(230, 242, 250)), 45));
        material.Freeze();

        var min = new Point3D(double.PositiveInfinity, double.PositiveInfinity, double.PositiveInfinity);
        var max = new Point3D(double.NegativeInfinity, double.NegativeInfinity, double.NegativeInfinity);
        var geometryCount = 0;

        foreach (var node in decoded.Nodes)
        {
            if (node.Positions is null || node.Positions.Count < 9 || node.Indices is null || node.Indices.Count < 3)
                continue;

            var points = new Point3DCollection(node.Positions.Count / 3);
            for (var i = 0; i + 2 < node.Positions.Count; i += 3)
            {
                var x = node.Positions[i];
                var y = node.Positions[i + 1];
                var z = node.Positions[i + 2];
                if (!double.IsFinite(x) || !double.IsFinite(y) || !double.IsFinite(z)) continue;
                var point = new Point3D(x, y, z);
                points.Add(point);
                min.X = Math.Min(min.X, x); min.Y = Math.Min(min.Y, y); min.Z = Math.Min(min.Z, z);
                max.X = Math.Max(max.X, x); max.Y = Math.Max(max.Y, y); max.Z = Math.Max(max.Z, z);
            }
            if (points.Count < 3) continue;

            var indices = new Int32Collection();
            for (var i = 0; i + 2 < node.Indices.Count; i += 3)
            {
                var a = node.Indices[i];
                var b = node.Indices[i + 1];
                var c = node.Indices[i + 2];
                if (a >= points.Count || b >= points.Count || c >= points.Count) continue;
                indices.Add((int)a); indices.Add((int)b); indices.Add((int)c);
            }
            if (indices.Count < 3) continue;

            var mesh = new MeshGeometry3D
            {
                Positions = points,
                TriangleIndices = indices
            };

            if (node.Normals is { Count: > 2 } && node.Normals.Count / 3 == points.Count)
            {
                var normals = new Vector3DCollection(points.Count);
                for (var i = 0; i + 2 < node.Normals.Count; i += 3)
                    normals.Add(new Vector3D(node.Normals[i], node.Normals[i + 1], node.Normals[i + 2]));
                mesh.Normals = normals;
            }
            mesh.Freeze();

            scene.Children.Add(new GeometryModel3D(mesh, material) { BackMaterial = material });
            geometryCount++;
        }

        if (geometryCount == 0 || !double.IsFinite(min.X) || !double.IsFinite(max.X))
            throw new InvalidOperationException("The EDF decoder returned no usable bike triangles.");

        var center = new Point3D(
            (min.X + max.X) * 0.5,
            (min.Y + max.Y) * 0.5,
            (min.Z + max.Z) * 0.5);
        var size = Math.Max(max.X - min.X, Math.Max(max.Y - min.Y, max.Z - min.Z));
        if (!double.IsFinite(size) || size <= 0.0001) size = 1.0;

        var yaw = new AxisAngleRotation3D(new Vector3D(0, 1, 0), 0);
        var pitch = new AxisAngleRotation3D(new Vector3D(1, 0, 0), 0);
        var transforms = new Transform3DGroup();
        transforms.Children.Add(new RotateTransform3D(yaw, center));
        transforms.Children.Add(new RotateTransform3D(pitch, center));
        scene.Transform = transforms;

        var camera = new PerspectiveCamera { FieldOfView = 38 };
        var distance = size * 2.25;
        void PositionCamera()
        {
            camera.Position = new Point3D(center.X, center.Y + size * 0.12, center.Z + distance);
            camera.LookDirection = new Vector3D(0, -size * 0.12, -distance);
            camera.UpDirection = new Vector3D(0, 1, 0);
            camera.NearPlaneDistance = Math.Max(0.001, size / 1000.0);
            camera.FarPlaneDistance = Math.Max(1000.0, size * 50.0);
        }
        PositionCamera();

        var viewport = new Viewport3D { Camera = camera, ClipToBounds = true };
        viewport.Children.Add(new ModelVisual3D { Content = scene });

        var frame = new Border
        {
            Background = new LinearGradientBrush(
                System.Windows.Media.Color.FromRgb(7, 26, 41),
                System.Windows.Media.Color.FromRgb(3, 10, 17), 90),
            BorderBrush = new SolidColorBrush(System.Windows.Media.Color.FromRgb(21, 82, 115)),
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(16),
            ClipToBounds = true,
            MinHeight = 520,
            Child = viewport
        };

        var dragging = false;
        Point last = default;
        viewport.MouseLeftButtonDown += (_, e) =>
        {
            dragging = true;
            last = e.GetPosition(viewport);
            viewport.CaptureMouse();
        };
        viewport.MouseLeftButtonUp += (_, _) =>
        {
            dragging = false;
            viewport.ReleaseMouseCapture();
        };
        viewport.MouseMove += (_, e) =>
        {
            if (!dragging) return;
            var current = e.GetPosition(viewport);
            var dx = current.X - last.X;
            var dy = current.Y - last.Y;
            yaw.Angle += dx * 0.45;
            pitch.Angle = Math.Clamp(pitch.Angle - dy * 0.35, -70, 70);
            last = current;
        };
        viewport.MouseWheel += (_, e) =>
        {
            distance *= e.Delta > 0 ? 0.88 : 1.14;
            distance = Math.Clamp(distance, size * 0.75, size * 8.0);
            PositionCamera();
        };

        return frame;
    }

    private static string CacheRoot(string child)
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var root = Path.Combine(local, "MXB Race Day Live", "cache", "native-viewer", child);
        Directory.CreateDirectory(root);
        return root;
    }

    private static string Sha256File(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static string Sha256Text(string value) =>
        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(value))).ToLowerInvariant();

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    private sealed record BikeBundle(
        string SourcePath,
        string RootPath,
        IReadOnlyList<string> EdfFiles,
        string? GeomFile);

    private sealed class ViewerAssetManifest
    {
        public string DecoderUrl { get; set; } = string.Empty;
        public string Sha256 { get; set; } = string.Empty;
        public string NoticeUrl { get; set; } = string.Empty;
    }

    private sealed class DecodedModel
    {
        public string Format { get; set; } = string.Empty;
        public string Mode { get; set; } = string.Empty;
        public List<DecodedNode> Nodes { get; set; } = new();
    }

    private sealed class DecodedNode
    {
        public string Name { get; set; } = string.Empty;
        public List<double> Positions { get; set; } = new();
        public List<double> Normals { get; set; } = new();
        public List<uint> Indices { get; set; } = new();
    }
}
