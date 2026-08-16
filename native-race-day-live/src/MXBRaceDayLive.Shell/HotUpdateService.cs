using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Shell;

public sealed class HotUpdateService : IUpdateService, IDisposable
{
    private static readonly HttpClient Client = CreateClient();
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true, WriteIndented = true };
    private readonly string _manifestUrl;
    private readonly string _moduleRoot;
    private readonly Func<Version> _currentVersion;
    private readonly SemaphoreSlim _gate = new(1, 1);

    public HotUpdateService(string manifestUrl, Func<Version> currentVersion)
    {
        _manifestUrl = manifestUrl;
        _currentVersion = currentVersion;
        _moduleRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "MXB Race Day Live", "modules", "profile-home");
        Directory.CreateDirectory(_moduleRoot);
    }

    public event EventHandler<string>? UpdateStatusChanged;

    public Func<string, Version, CancellationToken, Task>? ActivateModuleAsync { get; set; }

    public string ResolveActiveModule(string bundledModule)
    {
        try
        {
            var pointer = Path.Combine(_moduleRoot, "current.json");
            if (File.Exists(pointer))
            {
                var active = JsonSerializer.Deserialize<ActiveModule>(File.ReadAllText(pointer), JsonOptions);
                if (active is not null && File.Exists(active.Path)) return active.Path;
            }
        }
        catch { }
        return bundledModule;
    }

    public async Task CheckAndApplyAsync(CancellationToken cancellationToken = default)
    {
        if (!await _gate.WaitAsync(0, cancellationToken))
        {
            Status("Update check already running…");
            return;
        }

        try
        {
            Status("Checking for updates…");

            // raw.githubusercontent.com is intentionally cacheable. A fixed latest.json URL can
            // therefore return the previous manifest for several minutes after a release. Every
            // check gets a unique query token and explicit no-cache headers so manual checks are
            // actually live checks.
            var manifestRequestUrl = CacheBust(
                _manifestUrl,
                DateTimeOffset.UtcNow.ToUnixTimeMilliseconds().ToString());
            var manifestBytes = await DownloadNoCacheAsync(manifestRequestUrl, cancellationToken);
            var json = Encoding.UTF8.GetString(manifestBytes).TrimStart('\uFEFF');
            var manifest = JsonSerializer.Deserialize<UpdateManifest>(json, JsonOptions)
                           ?? throw new InvalidOperationException("The update manifest is invalid.");
            if (!Version.TryParse(manifest.Version, out var next))
                throw new InvalidOperationException("The update version is invalid.");

            var current = _currentVersion();
            if (next <= current)
            {
                Status($"Up to date · v{current}");
                return;
            }
            if (string.IsNullOrWhiteSpace(manifest.ModuleUrl) || string.IsNullOrWhiteSpace(manifest.Sha256))
                throw new InvalidOperationException("The update package information is incomplete.");
            if (ActivateModuleAsync is null)
                throw new InvalidOperationException("The live module activator is unavailable.");

            Status($"Downloading v{next}…");
            var expectedSha = manifest.Sha256.Trim().ToLowerInvariant();
            if (expectedSha.Length != 64)
                throw new InvalidOperationException("The update SHA-256 value is invalid.");

            // Versioned module URLs should already be immutable, but the SHA token also prevents
            // any stale intermediary response from being reused after a republish/correction.
            var moduleRequestUrl = CacheBust(
                manifest.ModuleUrl,
                $"{next}-{expectedSha[..12]}");
            var bytes = await DownloadNoCacheAsync(moduleRequestUrl, cancellationToken);
            var digest = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
            if (!CryptographicOperations.FixedTimeEquals(
                    Convert.FromHexString(digest), Convert.FromHexString(expectedSha)))
                throw new InvalidOperationException("The downloaded update failed SHA-256 verification.");

            var versionDir = Path.Combine(_moduleRoot, next.ToString());
            Directory.CreateDirectory(versionDir);
            var assemblyName = Path.GetFileName(manifest.FeatureAssembly);
            if (string.IsNullOrWhiteSpace(assemblyName) || !assemblyName.EndsWith(".dll", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("The feature assembly name is invalid.");

            var staged = Path.Combine(versionDir, assemblyName + ".staging");
            var final = Path.Combine(versionDir, assemblyName);
            await File.WriteAllBytesAsync(staged, bytes, cancellationToken);
            File.Move(staged, final, true);

            Status($"Applying v{next} live…");
            await ActivateModuleAsync(final, next, cancellationToken);

            var pointer = Path.Combine(_moduleRoot, "current.json");
            var pointerTemp = pointer + ".tmp";
            await File.WriteAllTextAsync(pointerTemp,
                JsonSerializer.Serialize(new ActiveModule(next.ToString(), final), JsonOptions), cancellationToken);
            File.Move(pointerTemp, pointer, true);
            Status($"Updated live to v{next} · no restart");
            CleanupOldVersions(final);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            Status("Update check cancelled");
        }
        catch (Exception ex)
        {
            var reason = ex.Message.Replace('\r', ' ').Replace('\n', ' ').Trim();
            if (reason.Length > 170) reason = reason[..167] + "…";
            Status(string.IsNullOrWhiteSpace(reason)
                ? "Update failed · current version kept"
                : $"Update failed · {reason}");
            System.Diagnostics.Debug.WriteLine(ex);
        }
        finally
        {
            _gate.Release();
        }
    }

    private static HttpClient CreateClient()
    {
        var client = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
        client.DefaultRequestHeaders.UserAgent.ParseAdd("MXB-Race-Day-Live-Updater/1.0");
        return client;
    }

    private static async Task<byte[]> DownloadNoCacheAsync(string url, CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.CacheControl = new CacheControlHeaderValue
        {
            NoCache = true,
            NoStore = true,
            MaxAge = TimeSpan.Zero
        };
        request.Headers.Pragma.ParseAdd("no-cache");

        using var response = await Client.SendAsync(
            request,
            HttpCompletionOption.ResponseHeadersRead,
            cancellationToken);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsByteArrayAsync(cancellationToken);
    }

    private static string CacheBust(string url, string token)
    {
        var separator = url.Contains('?', StringComparison.Ordinal) ? '&' : '?';
        return $"{url}{separator}rdl={Uri.EscapeDataString(token)}";
    }

    private void CleanupOldVersions(string keepPath)
    {
        try
        {
            var keepDir = Path.GetDirectoryName(keepPath);
            var dirs = new DirectoryInfo(_moduleRoot).EnumerateDirectories()
                .OrderByDescending(d => d.LastWriteTimeUtc).ToArray();
            foreach (var dir in dirs.Skip(3))
            {
                if (string.Equals(dir.FullName, keepDir, StringComparison.OrdinalIgnoreCase)) continue;
                try { dir.Delete(true); } catch { }
            }
        }
        catch { }
    }

    private void Status(string value) => UpdateStatusChanged?.Invoke(this, value);
    public void Dispose() => _gate.Dispose();
    private sealed record ActiveModule(string Version, string Path);
}
