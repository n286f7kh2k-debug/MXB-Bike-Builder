using System.Diagnostics;
using System.IO.Compression;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Interop;
using System.Windows.Media;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Profile;

/// <summary>
/// Internal Race Day Live component host for iNsane/dmkrtz3DViewer.
/// Users do not install a second application: Race Day Live obtains the public viewer package,
/// keeps it under its own LocalAppData component cache, launches it hidden and embeds the
/// renderer window directly in the Garage.
/// </summary>
internal static class InsaneBikePreviewProvider
{
    private const string OfficialViewerZip =
        "https://mxb-mods.com/uploads/3DViewer/dmkrtz3DViewer_v1.0.9151.32085.zip";

    private static readonly HttpClient Http = new()
    {
        Timeout = TimeSpan.FromSeconds(90)
    };

    static InsaneBikePreviewProvider()
    {
        Http.DefaultRequestHeaders.UserAgent.ParseAdd(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MXBRaceDayLive/1.0");
    }

    public static bool RequiresPreviewComponent(IReadOnlyList<string> edfFiles)
    {
        if (edfFiles.Count == 0) return false;
        var hasPlain = false;
        var hasSealed = false;
        var magic = new byte[4];

        foreach (var path in edfFiles)
        {
            try
            {
                using var stream = File.OpenRead(path);
                if (stream.Read(magic, 0, magic.Length) != magic.Length) continue;
                if (magic[0] == (byte)'E' && magic[1] == (byte)'D' && magic[2] == (byte)'F' && magic[3] == 0)
                    hasPlain = true;
                else
                    hasSealed = true;
            }
            catch
            {
                hasSealed = true;
            }
        }

        return hasSealed && !hasPlain;
    }

    public static async Task<BikeModelPreviewResult> CreateAsync(
        MXContentItem bike,
        string resolvedSource,
        CancellationToken cancellationToken)
    {
        var componentExe = await EnsureComponentAsync(cancellationToken);
        var session = await ViewerSession.StartAsync(componentExe, bike.Id, cancellationToken);

        var host = new EmbeddedViewerHost(session.WindowHandle, session.Process)
        {
            MinHeight = 620,
            HorizontalAlignment = HorizontalAlignment.Stretch,
            VerticalAlignment = VerticalAlignment.Stretch
        };

        var frame = new System.Windows.Controls.Grid
        {
            Height = 660,
            Background = new SolidColorBrush(Color.FromRgb(4, 16, 27))
        };
        frame.Children.Add(host);

        return new BikeModelPreviewResult(
            frame,
            PreferredFolderSource(bike.Path) ?? resolvedSource,
            $"{bike.Id} · iNsane-compatible preview hosted inside MXB Race Day Live");
    }

    private static async Task<string> EnsureComponentAsync(CancellationToken cancellationToken)
    {
        var root = ComponentRoot();
        var ready = Path.Combine(root, ".ready");
        var existing = FindViewerExe(root);
        if (File.Exists(ready) && existing is not null) return existing;

        Directory.CreateDirectory(root);
        var zipPath = Path.Combine(root, "dmkrtz3DViewer.zip");
        var stage = Path.Combine(root, ".stage-" + Guid.NewGuid().ToString("N"));

        try
        {
            using var request = new HttpRequestMessage(HttpMethod.Get, OfficialViewerZip);
            request.Headers.Referrer = new Uri("https://mxb-mods.com/insanes-3d-viewer/");
            using var response = await Http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
            response.EnsureSuccessStatusCode();

            await using (var input = await response.Content.ReadAsStreamAsync(cancellationToken))
            await using (var output = File.Create(zipPath))
                await input.CopyToAsync(output, cancellationToken);

            await using (var file = File.OpenRead(zipPath))
            {
                var signature = new byte[4];
                if (await file.ReadAsync(signature, cancellationToken) != 4
                    || signature[0] != 0x50 || signature[1] != 0x4B)
                    throw new InvalidOperationException(
                        "The official iNsane viewer download endpoint returned a web challenge instead of the viewer package. " +
                        "Race Day Live will keep this component internal, but the publisher download must be reachable from this PC.");
            }

            Directory.CreateDirectory(stage);
            ZipFile.ExtractToDirectory(zipPath, stage, overwriteFiles: true);

            foreach (var entry in Directory.EnumerateFileSystemEntries(stage))
            {
                var destination = Path.Combine(root, Path.GetFileName(entry));
                if (Directory.Exists(entry))
                {
                    if (Directory.Exists(destination)) Directory.Delete(destination, recursive: true);
                    Directory.Move(entry, destination);
                }
                else
                {
                    File.Move(entry, destination, overwrite: true);
                }
            }

            var exe = FindViewerExe(root)
                ?? throw new InvalidOperationException("The iNsane viewer package downloaded, but Race Day Live could not locate its viewer executable.");
            File.WriteAllText(ready, "dmkrtz3DViewer v1.0.9151.32085\n");
            return exe;
        }
        finally
        {
            try { if (Directory.Exists(stage)) Directory.Delete(stage, recursive: true); } catch { }
            try { if (File.Exists(zipPath)) File.Delete(zipPath); } catch { }
        }
    }

    private static string ComponentRoot()
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var path = Path.Combine(local, "MXB Race Day Live", "components", "insane-viewer", "1.0.9151.32085");
        Directory.CreateDirectory(path);
        return path;
    }

    private static string? FindViewerExe(string root)
    {
        if (!Directory.Exists(root)) return null;
        try
        {
            return Directory.EnumerateFiles(root, "*.exe", SearchOption.AllDirectories)
                .OrderByDescending(path =>
                {
                    var name = Path.GetFileNameWithoutExtension(path);
                    var score = 0;
                    if (name.Contains("dmkrtz", StringComparison.OrdinalIgnoreCase)) score += 100;
                    if (name.Contains("3d", StringComparison.OrdinalIgnoreCase)) score += 40;
                    if (name.Contains("viewer", StringComparison.OrdinalIgnoreCase)) score += 40;
                    if (name.Contains("unins", StringComparison.OrdinalIgnoreCase)) score -= 1000;
                    if (name.Contains("setup", StringComparison.OrdinalIgnoreCase)) score -= 500;
                    return score;
                })
                .FirstOrDefault();
        }
        catch
        {
            return null;
        }
    }

    private static string? PreferredFolderSource(string source)
    {
        try
        {
            if (Directory.Exists(source)) return source;
            if (File.Exists(source) && Path.GetExtension(source).Equals(".pkz", StringComparison.OrdinalIgnoreCase))
            {
                var parent = Path.GetDirectoryName(source) ?? string.Empty;
                var folder = Path.Combine(parent, Path.GetFileNameWithoutExtension(source));
                if (Directory.Exists(folder)) return folder;
            }
        }
        catch { }
        return null;
    }

    private sealed record ViewerSession(Process Process, IntPtr WindowHandle)
    {
        public static async Task<ViewerSession> StartAsync(
            string executable,
            string bikeId,
            CancellationToken cancellationToken)
        {
            var process = Process.Start(new ProcessStartInfo(executable)
            {
                UseShellExecute = true,
                WorkingDirectory = Path.GetDirectoryName(executable) ?? string.Empty,
                WindowStyle = ProcessWindowStyle.Hidden
            }) ?? throw new InvalidOperationException("Race Day Live could not start its internal iNsane preview component.");

            var hwnd = await WaitForWindowAsync(process, cancellationToken);
            if (hwnd == IntPtr.Zero)
            {
                try { if (!process.HasExited) process.Kill(entireProcessTree: true); } catch { }
                throw new InvalidOperationException("The internal iNsane preview component started but did not create a viewer window.");
            }

            Native.ShowWindow(hwnd, Native.SW_HIDE);

            // Selection is best-effort because older and newer dmkrtz builds expose different
            // accessibility trees. If automatic selection is unavailable, the whole viewer UI
            // remains embedded inside the Garage rather than opening as a second desktop app.
            try { await ViewerAutomation.SelectBikeAsync(hwnd, bikeId, cancellationToken); }
            catch { }

            return new ViewerSession(process, hwnd);
        }

        private static async Task<IntPtr> WaitForWindowAsync(Process process, CancellationToken cancellationToken)
        {
            var until = DateTime.UtcNow + TimeSpan.FromSeconds(25);
            while (DateTime.UtcNow < until)
            {
                cancellationToken.ThrowIfCancellationRequested();
                try
                {
                    process.Refresh();
                    if (process.MainWindowHandle != IntPtr.Zero) return process.MainWindowHandle;
                }
                catch { }
                await Task.Delay(150, cancellationToken);
            }
            return IntPtr.Zero;
        }
    }

    private static class ViewerAutomation
    {
        public static Task SelectBikeAsync(IntPtr hwnd, string bikeId, CancellationToken cancellationToken)
        {
            var tcs = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            var thread = new Thread(() =>
            {
                try
                {
                    SelectBike(hwnd, bikeId, cancellationToken);
                    tcs.SetResult();
                }
                catch (Exception ex) { tcs.TrySetException(ex); }
            })
            {
                IsBackground = true,
                Name = "MXB-RDL iNsane viewer bridge"
            };
            thread.SetApartmentState(ApartmentState.STA);
            thread.Start();
            cancellationToken.Register(() => tcs.TrySetCanceled(cancellationToken));
            return tcs.Task;
        }

        private static void SelectBike(IntPtr hwnd, string bikeId, CancellationToken cancellationToken)
        {
            var root = AutomationElement.FromHandle(hwnd);
            if (root is null) return;

            var bikesTab = FindElement(root, e =>
            {
                var name = Name(e);
                return name.Equals("Bikes", StringComparison.OrdinalIgnoreCase)
                    || name.Equals("Bike", StringComparison.OrdinalIgnoreCase);
            });
            if (bikesTab is not null)
            {
                Invoke(bikesTab);
                Thread.Sleep(250);
                root = AutomationElement.FromHandle(hwnd) ?? root;
            }

            var candidates = BikeSearchTerms(bikeId);
            var all = AllElements(root);
            var best = all
                .Select(e => (Element: e, Score: Score(Name(e), candidates)))
                .Where(x => x.Score > 0)
                .OrderByDescending(x => x.Score)
                .FirstOrDefault();

            if (best.Element is not null && best.Score >= 5)
            {
                Invoke(best.Element);
                Thread.Sleep(900);
                return;
            }

            // Some viewer builds expose a filter edit instead of list items to UIA.
            var edit = all.FirstOrDefault(e => e.Current.ControlType == ControlType.Edit);
            if (edit is not null)
            {
                SetText(edit, candidates.FirstOrDefault(x => x.Length > 3) ?? bikeId);
                Thread.Sleep(250);
                root = AutomationElement.FromHandle(hwnd) ?? root;
                all = AllElements(root);
                best = all
                    .Select(e => (Element: e, Score: Score(Name(e), candidates)))
                    .Where(x => x.Score > 0)
                    .OrderByDescending(x => x.Score)
                    .FirstOrDefault();
                if (best.Element is not null) Invoke(best.Element);
            }
        }

        private static string[] BikeSearchTerms(string bikeId)
        {
            var cleaned = bikeId
                .Replace("MX1OEM_", string.Empty, StringComparison.OrdinalIgnoreCase)
                .Replace("MX2OEM_", string.Empty, StringComparison.OrdinalIgnoreCase)
                .Replace('_', ' ')
                .Replace('-', ' ');

            var tokens = cleaned.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Where(t => !t.Equals("OEM", StringComparison.OrdinalIgnoreCase))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToList();

            var make = tokens.FirstOrDefault(t =>
                t.Equals("GasGas", StringComparison.OrdinalIgnoreCase)
                || t.Equals("KTM", StringComparison.OrdinalIgnoreCase)
                || t.Equals("Husqvarna", StringComparison.OrdinalIgnoreCase)
                || t.Equals("Honda", StringComparison.OrdinalIgnoreCase)
                || t.Equals("Kawasaki", StringComparison.OrdinalIgnoreCase)
                || t.Equals("Yamaha", StringComparison.OrdinalIgnoreCase)
                || t.Equals("Suzuki", StringComparison.OrdinalIgnoreCase)
                || t.Equals("TM", StringComparison.OrdinalIgnoreCase)
                || t.Equals("Beta", StringComparison.OrdinalIgnoreCase)
                || t.Equals("Fantic", StringComparison.OrdinalIgnoreCase)
                || t.Equals("Triumph", StringComparison.OrdinalIgnoreCase)
                || t.Equals("Stark", StringComparison.OrdinalIgnoreCase));
            var year = tokens.FirstOrDefault(t => t.Length == 4 && int.TryParse(t, out var y) && y is > 2000 and < 2100);
            var cc = tokens.FirstOrDefault(t => t.Contains("450", StringComparison.OrdinalIgnoreCase)
                                             || t.Contains("350", StringComparison.OrdinalIgnoreCase)
                                             || t.Contains("250", StringComparison.OrdinalIgnoreCase)
                                             || t.Contains("125", StringComparison.OrdinalIgnoreCase));

            return new[] { bikeId, cleaned, make ?? string.Empty, year ?? string.Empty, cc ?? string.Empty }
                .Concat(tokens)
                .Where(x => !string.IsNullOrWhiteSpace(x))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .ToArray();
        }

        private static int Score(string name, IReadOnlyList<string> terms)
        {
            if (string.IsNullOrWhiteSpace(name)) return 0;
            var normalized = Normalize(name);
            var score = 0;
            foreach (var term in terms)
            {
                var t = Normalize(term);
                if (t.Length < 2) continue;
                if (normalized == t) score += 12;
                else if (normalized.Contains(t, StringComparison.OrdinalIgnoreCase)) score += t.Length >= 5 ? 4 : 2;
            }
            return score;
        }

        private static string Normalize(string value) =>
            new(value.Where(char.IsLetterOrDigit).Select(char.ToLowerInvariant).ToArray());

        private static List<AutomationElement> AllElements(AutomationElement root)
        {
            var result = new List<AutomationElement> { root };
            try
            {
                var all = root.FindAll(TreeScope.Descendants, System.Windows.Automation.Condition.TrueCondition);
                for (var i = 0; i < all.Count; i++) result.Add(all[i]);
            }
            catch { }
            return result;
        }

        private static AutomationElement? FindElement(AutomationElement root, Func<AutomationElement, bool> predicate)
        {
            foreach (var element in AllElements(root))
            {
                try { if (predicate(element)) return element; } catch { }
            }
            return null;
        }

        private static string Name(AutomationElement element)
        {
            try { return element.Current.Name?.Trim() ?? string.Empty; }
            catch { return string.Empty; }
        }

        private static void Invoke(AutomationElement element)
        {
            try
            {
                if (element.TryGetCurrentPattern(InvokePattern.Pattern, out var invoke))
                    ((InvokePattern)invoke).Invoke();
                else if (element.TryGetCurrentPattern(SelectionItemPattern.Pattern, out var select))
                    ((SelectionItemPattern)select).Select();
                else if (element.TryGetCurrentPattern(ExpandCollapsePattern.Pattern, out var expand))
                    ((ExpandCollapsePattern)expand).Expand();
                else
                {
                    element.SetFocus();
                    Native.SendEnter();
                }
            }
            catch { }
        }

        private static void SetText(AutomationElement element, string value)
        {
            try
            {
                if (element.TryGetCurrentPattern(ValuePattern.Pattern, out var pattern))
                {
                    ((ValuePattern)pattern).SetValue(value);
                    return;
                }
            }
            catch { }

            try
            {
                element.SetFocus();
                Native.SendCtrlA();
                Native.SendUnicode(value);
            }
            catch { }
        }
    }

    private sealed class EmbeddedViewerHost : HwndHost
    {
        private readonly IntPtr _external;
        private readonly Process _process;
        private IntPtr _container;
        private IntPtr _originalParent;
        private nint _originalStyle;
        private nint _originalExStyle;

        public EmbeddedViewerHost(IntPtr external, Process process)
        {
            _external = external;
            _process = process;
        }

        protected override HandleRef BuildWindowCore(HandleRef hwndParent)
        {
            _container = Native.CreateWindowEx(
                0, "static", string.Empty,
                Native.WS_CHILD | Native.WS_VISIBLE | Native.WS_CLIPCHILDREN | Native.WS_CLIPSIBLINGS,
                0, 0, 800, 600,
                hwndParent.Handle, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
            if (_container == IntPtr.Zero)
                throw new InvalidOperationException("Race Day Live could not create the internal bike-viewer host.");

            _originalParent = Native.GetParent(_external);
            _originalStyle = Native.GetWindowLongPtr(_external, Native.GWL_STYLE);
            _originalExStyle = Native.GetWindowLongPtr(_external, Native.GWL_EXSTYLE);
            var style = (_originalStyle & ~(Native.WS_POPUP | Native.WS_CAPTION | Native.WS_THICKFRAME | Native.WS_SYSMENU))
                        | Native.WS_CHILD | Native.WS_VISIBLE;
            var exStyle = (_originalExStyle & ~Native.WS_EX_APPWINDOW) | Native.WS_EX_TOOLWINDOW;
            Native.SetWindowLongPtr(_external, Native.GWL_STYLE, style);
            Native.SetWindowLongPtr(_external, Native.GWL_EXSTYLE, exStyle);
            Native.SetParent(_external, _container);
            Native.ShowWindow(_external, Native.SW_SHOW);
            Native.MoveWindow(_external, 0, 0, 800, 600, true);
            return new HandleRef(this, _container);
        }

        protected override void OnWindowPositionChanged(Rect rcBoundingBox)
        {
            base.OnWindowPositionChanged(rcBoundingBox);
            if (_external != IntPtr.Zero)
                Native.MoveWindow(_external, 0, 0, Math.Max(1, (int)rcBoundingBox.Width), Math.Max(1, (int)rcBoundingBox.Height), true);
        }

        protected override void DestroyWindowCore(HandleRef hwnd)
        {
            try
            {
                if (!_process.HasExited) _process.Kill(entireProcessTree: true);
            }
            catch { }
            if (_container != IntPtr.Zero) Native.DestroyWindow(_container);
            _container = IntPtr.Zero;
        }
    }

    private static class Native
    {
        internal const int GWL_STYLE = -16;
        internal const int GWL_EXSTYLE = -20;
        internal const int SW_HIDE = 0;
        internal const int SW_SHOW = 5;
        internal const int WS_CHILD = 0x40000000;
        internal const int WS_VISIBLE = 0x10000000;
        internal const int WS_POPUP = unchecked((int)0x80000000);
        internal const int WS_CAPTION = 0x00C00000;
        internal const int WS_THICKFRAME = 0x00040000;
        internal const int WS_SYSMENU = 0x00080000;
        internal const int WS_CLIPCHILDREN = 0x02000000;
        internal const int WS_CLIPSIBLINGS = 0x04000000;
        internal const int WS_EX_APPWINDOW = 0x00040000;
        internal const int WS_EX_TOOLWINDOW = 0x00000080;
        private const uint INPUT_KEYBOARD = 1;
        private const uint KEYEVENTF_KEYUP = 0x0002;
        private const uint KEYEVENTF_UNICODE = 0x0004;
        private const ushort VK_CONTROL = 0x11;
        private const ushort VK_A = 0x41;
        private const ushort VK_RETURN = 0x0D;

        [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
        internal static extern IntPtr CreateWindowEx(int exStyle, string className, string windowName, int style,
            int x, int y, int width, int height, IntPtr parent, IntPtr menu, IntPtr instance, IntPtr param);
        [DllImport("user32.dll", SetLastError = true)] internal static extern bool DestroyWindow(IntPtr hwnd);
        [DllImport("user32.dll", SetLastError = true)] internal static extern IntPtr SetParent(IntPtr child, IntPtr parent);
        [DllImport("user32.dll")] internal static extern IntPtr GetParent(IntPtr hwnd);
        [DllImport("user32.dll")] internal static extern bool ShowWindow(IntPtr hwnd, int command);
        [DllImport("user32.dll", SetLastError = true)] internal static extern bool MoveWindow(IntPtr hwnd, int x, int y, int width, int height, bool repaint);
        [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")] private static extern IntPtr GetWindowLongPtr64(IntPtr hwnd, int index);
        [DllImport("user32.dll", EntryPoint = "GetWindowLongW")] private static extern int GetWindowLong32(IntPtr hwnd, int index);
        [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")] private static extern IntPtr SetWindowLongPtr64(IntPtr hwnd, int index, IntPtr value);
        [DllImport("user32.dll", EntryPoint = "SetWindowLongW")] private static extern int SetWindowLong32(IntPtr hwnd, int index, int value);
        [DllImport("user32.dll")] private static extern uint SendInput(uint count, INPUT[] inputs, int size);

        internal static nint GetWindowLongPtr(IntPtr hwnd, int index) =>
            IntPtr.Size == 8 ? GetWindowLongPtr64(hwnd, index) : new IntPtr(GetWindowLong32(hwnd, index));
        internal static nint SetWindowLongPtr(IntPtr hwnd, int index, nint value) =>
            IntPtr.Size == 8 ? SetWindowLongPtr64(hwnd, index, value) : new IntPtr(SetWindowLong32(hwnd, index, value.ToInt32()));
        internal static void SendCtrlA() { SendKey(VK_CONTROL, false); SendKey(VK_A, false); SendKey(VK_A, true); SendKey(VK_CONTROL, true); }
        internal static void SendEnter() { SendKey(VK_RETURN, false); SendKey(VK_RETURN, true); }

        internal static void SendUnicode(string text)
        {
            foreach (var ch in text)
            {
                var down = new INPUT { type = INPUT_KEYBOARD, U = new InputUnion { ki = new KEYBDINPUT { wScan = ch, dwFlags = KEYEVENTF_UNICODE } } };
                var up = down; up.U.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;
                SendInput(2, new[] { down, up }, Marshal.SizeOf<INPUT>());
            }
        }

        private static void SendKey(ushort key, bool up)
        {
            var input = new INPUT { type = INPUT_KEYBOARD, U = new InputUnion { ki = new KEYBDINPUT { wVk = key, dwFlags = up ? KEYEVENTF_KEYUP : 0 } } };
            SendInput(1, new[] { input }, Marshal.SizeOf<INPUT>());
        }

        [StructLayout(LayoutKind.Sequential)] private struct INPUT { public uint type; public InputUnion U; }
        [StructLayout(LayoutKind.Explicit)] private struct InputUnion { [FieldOffset(0)] public KEYBDINPUT ki; }
        [StructLayout(LayoutKind.Sequential)] private struct KEYBDINPUT
        {
            public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr dwExtraInfo;
        }
    }
}
