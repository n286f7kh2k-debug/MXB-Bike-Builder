using System.Runtime.CompilerServices;

namespace MXBRaceDayLive.Profile;

/// <summary>
/// Prepares the private .NET 6 Desktop Runtime once when the hot-loaded profile module starts.
/// Child processes, including the embedded iNsane viewer, inherit these process-scoped variables.
/// No machine-wide runtime installation is performed.
/// </summary>
internal static class InsaneRuntimeModuleBootstrap
{
    [ModuleInitializer]
    internal static void Initialize()
    {
        try
        {
            var runtimeRoot = InsaneDotNetRuntime
                .EnsureAsync(CancellationToken.None)
                .ConfigureAwait(false)
                .GetAwaiter()
                .GetResult();

            Environment.SetEnvironmentVariable("DOTNET_ROOT", runtimeRoot, EnvironmentVariableTarget.Process);
            Environment.SetEnvironmentVariable("DOTNET_ROOT_X64", runtimeRoot, EnvironmentVariableTarget.Process);
            Environment.SetEnvironmentVariable("DOTNET_MULTILEVEL_LOOKUP", "0", EnvironmentVariableTarget.Process);
        }
        catch
        {
            // Keep the profile module loadable if the Microsoft runtime endpoint is temporarily unavailable.
            // The Garage's viewer error path will remain available instead of taking down Race Day Live.
        }
    }
}
