using System.Security.Cryptography;
using System.Text.Json;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Shell;

public sealed class HotUpdateService : IUpdateService, IDisposable
{
    private static readonly HttpClient Client = new() { Timeout = TimeSpan.FromSeconds(30) };
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

    // The shell supplies this callback. A verified module is activated inside the already-open
    // window first. Only after that succeeds is it saved as the startup module.
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
        if (!await _gate.WaitAsync(0, cancellationToken)) return;
        try
        {
            Status("Checking for updates…");
            var json = await Client.GetStringAsync(_manifestUrl, cancellationToken);
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
            var bytes = await Client.GetByteArrayAsync(manifest.ModuleUrl, cancellationToken);
            var digest = Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
            if (!CryptographicOperations.FixedTimeEquals(
                    Convert.FromHexString(digest), Convert.FromHexString(manifest.Sha256.Trim())))
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

            // This is the important no-restart transaction. The new feature must successfully
            // construct and render before the persisted pointer changes.
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
            // The active module was not switched permanently if activation failed.
            Status("Update failed · current version kept");
            System.Diagnostics.Debug.WriteLine(ex);
        }
        finally
        {
            _gate.Release();
        }
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
