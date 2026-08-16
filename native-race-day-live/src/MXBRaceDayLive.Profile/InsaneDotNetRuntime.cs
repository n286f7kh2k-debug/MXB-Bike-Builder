using System.Diagnostics;
using System.Net.Http;

namespace MXBRaceDayLive.Profile;

/// <summary>
/// Provides the framework-dependent iNsane viewer with its own private .NET 6 Desktop Runtime.
/// Nothing is installed machine-wide and no administrator rights are required.
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
            psi.ArgumentList.Add("windowsdesktop");
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
            if (process.ExitCode != 0 || !IsReady(root))
            {
                var detail = string.IsNullOrWhiteSpace(stderr) ? stdout : stderr;
                throw new InvalidOperationException(
                    "Race Day Live could not prepare the private .NET 6 runtime required by the built-in iNsane viewer. " +
                    (string.IsNullOrWhiteSpace(detail) ? string.Empty : detail.Trim()));
            }

            return root;
        }
        finally
        {
            try { if (File.Exists(temp)) File.Delete(temp); } catch { }
            try { if (File.Exists(script)) File.Delete(script); } catch { }
        }
    }

    private static bool IsReady(string root) =>
        File.Exists(Path.Combine(root, "dotnet.exe"))
        && Directory.Exists(Path.Combine(root, "shared", "Microsoft.NETCore.App", RuntimeVersion))
        && Directory.Exists(Path.Combine(root, "shared", "Microsoft.WindowsDesktop.App", RuntimeVersion));

    private static string RuntimeRoot()
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return Path.Combine(local, "MXB Race Day Live", "components", "dotnet", "6.0.36-x64-desktop");
    }
}
