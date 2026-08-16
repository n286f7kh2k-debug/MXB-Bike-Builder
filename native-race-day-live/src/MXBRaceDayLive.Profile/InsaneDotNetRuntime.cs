using System.Diagnostics;
using System.Net.Http;

namespace MXBRaceDayLive.Profile;

/// <summary>
/// Provides the framework-dependent iNsane viewer with its own private .NET 6 runtime stack.
/// Both the base Microsoft.NETCore.App runtime and Microsoft.WindowsDesktop.App runtime are
/// provisioned into Race Day Live's LocalAppData folder. Nothing is installed machine-wide.
/// </summary>
internal static class InsaneDotNetRuntime
{
    private const string RuntimeVersion = "6.0.36";
    private const string InstallScriptUrl = "https://dot.net/v1/dotnet-install.ps1";

    private static readonly HttpClient Http = new()
    {
        Timeout = TimeSpan.FromSeconds(90)
    };

    public static async Task<string> EnsureAsync(CancellationToken cancellationToken)
    {
        var root = RuntimeRoot();
        if (IsReady(root)) return root;

        Directory.CreateDirectory(root);
        var script = Path.Combine(root, "dotnet-install.ps1");
        var temp = script + ".tmp";

        try
        {
            var bytes = await Http.GetByteArrayAsync(InstallScriptUrl, cancellationToken);
            await File.WriteAllBytesAsync(temp, bytes, cancellationToken);
            File.Move(temp, script, overwrite: true);

            // The portable WindowsDesktop ZIP is not a safe assumption for the base runtime.
            // iNsane requires Microsoft.NETCore.App as well, so install both into the same
            // private root. Each step is idempotent and dotnet-install skips files already there.
            if (!HasCoreRuntime(root))
                await RunInstallerAsync(script, root, "dotnet", cancellationToken);

            if (!HasDesktopRuntime(root))
                await RunInstallerAsync(script, root, "windowsdesktop", cancellationToken);

            if (!IsReady(root))
            {
                var diagnostics = RuntimeDiagnostics(root);
                throw new InvalidOperationException(
                    "Race Day Live finished the private .NET 6 setup, but the runtime stack is incomplete. " + diagnostics);
            }

            return root;
        }
        finally
        {
            try { if (File.Exists(temp)) File.Delete(temp); } catch { }
            try { if (File.Exists(script)) File.Delete(script); } catch { }
        }
    }

    private static async Task RunInstallerAsync(
        string script,
        string root,
        string runtime,
        CancellationToken cancellationToken)
    {
        var psi = new ProcessStartInfo("powershell.exe")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            WorkingDirectory = root
        };
        psi.ArgumentList.Add("-NoLogo");
        psi.ArgumentList.Add("-NoProfile");
        psi.ArgumentList.Add("-NonInteractive");
        psi.ArgumentList.Add("-ExecutionPolicy");
        psi.ArgumentList.Add("Bypass");
        psi.ArgumentList.Add("-File");
        psi.ArgumentList.Add(script);
        psi.ArgumentList.Add("-Runtime");
        psi.ArgumentList.Add(runtime);
        psi.ArgumentList.Add("-Version");
        psi.ArgumentList.Add(RuntimeVersion);
        psi.ArgumentList.Add("-Architecture");
        psi.ArgumentList.Add("x64");
        psi.ArgumentList.Add("-InstallDir");
        psi.ArgumentList.Add(root);
        psi.ArgumentList.Add("-NoPath");

        using var process = Process.Start(psi)
            ?? throw new InvalidOperationException("Race Day Live could not start its private .NET runtime bootstrapper.");

        var stdoutTask = process.StandardOutput.ReadToEndAsync(cancellationToken);
        var stderrTask = process.StandardError.ReadToEndAsync(cancellationToken);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromMinutes(3));

        try
        {
            await process.WaitForExitAsync(timeout.Token);
        }
        catch
        {
            try { if (!process.HasExited) process.Kill(entireProcessTree: true); } catch { }
            throw;
        }

        var stdout = await stdoutTask;
        var stderr = await stderrTask;

        // dotnet-install writes normal progress text to both streams in some PowerShell hosts.
        // Only a non-zero exit code is an installer failure; final correctness is verified by
        // inspecting the runtime folders after both installers have run.
        if (process.ExitCode != 0)
        {
            var detail = string.Join(Environment.NewLine,
                new[] { stderr, stdout }.Where(x => !string.IsNullOrWhiteSpace(x))).Trim();
            throw new InvalidOperationException(
                $"Race Day Live could not install its private .NET 6 {runtime} runtime. " +
                (string.IsNullOrWhiteSpace(detail) ? $"Installer exit code: {process.ExitCode}." : detail));
        }
    }

    private static bool IsReady(string root) =>
        File.Exists(Path.Combine(root, "dotnet.exe"))
        && HasCoreRuntime(root)
        && HasDesktopRuntime(root)
        && HasHostFxr(root);

    private static bool HasCoreRuntime(string root) =>
        HasRuntimeFamily(Path.Combine(root, "shared", "Microsoft.NETCore.App"));

    private static bool HasDesktopRuntime(string root) =>
        HasRuntimeFamily(Path.Combine(root, "shared", "Microsoft.WindowsDesktop.App"));

    private static bool HasHostFxr(string root) =>
        HasRuntimeFamily(Path.Combine(root, "host", "fxr"));

    private static bool HasRuntimeFamily(string familyRoot)
    {
        try
        {
            if (!Directory.Exists(familyRoot)) return false;
            return Directory.EnumerateDirectories(familyRoot)
                .Select(Path.GetFileName)
                .Any(version => version is not null && version.StartsWith("6.0.", StringComparison.OrdinalIgnoreCase));
        }
        catch
        {
            return false;
        }
    }

    private static string RuntimeDiagnostics(string root)
    {
        static string Versions(string path)
        {
            try
            {
                if (!Directory.Exists(path)) return "missing";
                var versions = Directory.EnumerateDirectories(path)
                    .Select(Path.GetFileName)
                    .Where(x => !string.IsNullOrWhiteSpace(x));
                return string.Join(", ", versions);
            }
            catch
            {
                return "unreadable";
            }
        }

        return $"dotnet.exe={(File.Exists(Path.Combine(root, "dotnet.exe")) ? "found" : "missing")}; " +
               $"NETCore=[{Versions(Path.Combine(root, "shared", "Microsoft.NETCore.App"))}]; " +
               $"WindowsDesktop=[{Versions(Path.Combine(root, "shared", "Microsoft.WindowsDesktop.App"))}]; " +
               $"hostfxr=[{Versions(Path.Combine(root, "host", "fxr"))}].";
    }

    private static string RuntimeRoot()
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(local, "MXB Race Day Live", "components", "dotnet", "6.0.36-x64-desktop");
    }
}
