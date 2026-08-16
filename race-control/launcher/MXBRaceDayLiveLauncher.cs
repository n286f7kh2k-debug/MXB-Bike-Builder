using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;

[assembly: AssemblyTitle("MXB Race Day Live")]
[assembly: AssemblyDescription("MXB Race Day Live desktop launcher")]
[assembly: AssemblyCompany("MXB Race Day Live")]
[assembly: AssemblyProduct("MXB Race Day Live")]
[assembly: AssemblyCopyright("MXB Race Day Live")]
[assembly: AssemblyVersion("0.5.11.0")]
[assembly: AssemblyFileVersion("0.5.11.0")]

internal static class Program
{
    private static string Quote(string value)
    {
        if (value == null) return "\"\"";
        return "\"" + value.Replace("\"", "\\\"") + "\"";
    }

    private static string RuntimePath(string root)
    {
        string hint = Path.Combine(root, "assets", "bin", "rdl_runtime.txt");
        try
        {
            if (File.Exists(hint))
            {
                string raw = File.ReadAllText(hint).Trim().Trim('"');
                if (!String.IsNullOrWhiteSpace(raw))
                {
                    string candidate = Path.IsPathRooted(raw) ? raw : Path.GetFullPath(Path.Combine(root, raw));
                    if (File.Exists(candidate)) return candidate;
                }
            }
        }
        catch { }

        string venv = Path.Combine(root, ".venv", "Scripts", "pythonw.exe");
        if (File.Exists(venv)) return venv;
        string local = Path.Combine(root, "pythonw.exe");
        if (File.Exists(local)) return local;
        return null;
    }

    [STAThread]
    private static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        string app = Path.Combine(root, "app.py");
        string runtime = RuntimePath(root);
        if (runtime == null || !File.Exists(app)) return 2;

        var pieces = new List<string> { Quote(app) };
        if (args != null)
        {
            foreach (string arg in args) pieces.Add(Quote(arg));
        }

        var psi = new ProcessStartInfo
        {
            FileName = runtime,
            Arguments = String.Join(" ", pieces.ToArray()),
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden
        };

        try
        {
            using (Process child = Process.Start(psi))
            {
                if (child == null) return 3;
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch
        {
            return 4;
        }
    }
}
