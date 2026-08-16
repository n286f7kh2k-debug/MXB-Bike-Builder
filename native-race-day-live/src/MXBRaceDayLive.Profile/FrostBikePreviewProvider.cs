using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Interop;
using System.Windows.Media;
using Microsoft.Win32;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Profile;

/// <summary>
/// Uses the user's installed MXB App/Frost renderer for bike geometry that is sealed on disk.
/// Race Day Live drives only Frost's normal public UI controls; it never opens MX Bikes and
/// never attempts to unseal creator-protected EDF bytes itself.
/// </summary>
internal static class FrostBikePreviewProvider
{
    public static bool RequiresFrost(IReadOnlyList<string> edfFiles)
    {
        if (edfFiles.Count == 0) return false;
        var hasPlain = false;
        var hasSealed = false;
        foreach (var path in edfFiles)
        {
            try
            {
                using var stream = File.OpenRead(path);
                Span<byte> magic = stackalloc byte[4];
                if (stream.Read(magic) != 4) continue;
                if (magic.SequenceEqual(new byte[] { (byte)'E', (byte)'D', (byte)'F', 0 })) hasPlain = true;
                else hasSealed = true;
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
        var session = await FrostSession.AttachAsync(bike.Id, cancellationToken);
        var host = new FrostWindowHost(session.WindowHandle, session.OwnsProcess ? session.Process : null)
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

        var source = PreferredFolderSource(bike.Path) ?? resolvedSource;
        return new BikeModelPreviewResult(
            frame,
            source,
            $"{bike.Id} · sealed MX Bikes geometry rendered by installed MXB App/Frost");
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

    private sealed record FrostSession(Process Process, IntPtr WindowHandle, bool OwnsProcess)
    {
        public static async Task<FrostSession> AttachAsync(string bikeId, CancellationToken cancellationToken)
        {
            var existing = FindRunningProcess();
            var owns = false;
            var process = existing;
            if (process is null)
            {
                var exe = FindExecutable();
                if (string.IsNullOrWhiteSpace(exe))
                    throw new InvalidOperationException(
                        "This bike uses sealed EDF geometry. Race Day Live can render it through the installed MXB App/Frost renderer, but MXB App was not found on this PC.");

                process = Process.Start(new ProcessStartInfo(exe)
                {
                    UseShellExecute = true,
                    WorkingDirectory = Path.GetDirectoryName(exe) ?? string.Empty
                }) ?? throw new InvalidOperationException("MXB App/Frost could not be started for the sealed-bike preview.");
                owns = true;
            }

            var hwnd = await WaitForWindowAsync(process, cancellationToken);
            if (hwnd == IntPtr.Zero)
                throw new InvalidOperationException("MXB App/Frost started, but its main window could not be found.");

            // Keep the renderer off the desktop while Race Day Live aims it at the clicked bike.
            Native.ShowWindow(hwnd, Native.SW_HIDE);
            try
            {
                await FrostAutomation.SelectBikeAsync(hwnd, bikeId, cancellationToken);
            }
            catch
            {
                Native.ShowWindow(hwnd, Native.SW_SHOW);
                throw;
            }

            return new FrostSession(process, hwnd, owns);
        }

        private static Process? FindRunningProcess()
        {
            foreach (var p in Process.GetProcesses())
            {
                try
                {
                    if (p.HasExited) continue;
                    var name = p.ProcessName;
                    if (name.Equals("MXB App", StringComparison.OrdinalIgnoreCase)
                        || name.Equals("mxb-app", StringComparison.OrdinalIgnoreCase))
                    {
                        p.Refresh();
                        if (p.MainWindowHandle != IntPtr.Zero) return p;
                    }
                }
                catch { }
            }
            return null;
        }

        private static string? FindExecutable()
        {
            var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            var candidates = new[]
            {
                Path.Combine(local, "Programs", "MXB App", "MXB App.exe"),
                Path.Combine(local, "Programs", "mxb-app", "MXB App.exe"),
                Path.Combine(local, "MXB App", "MXB App.exe"),
                Path.Combine(local, "Programs", "MXB.App", "MXB App.exe")
            };
            foreach (var candidate in candidates)
                if (File.Exists(candidate)) return candidate;

            foreach (var hive in new[] { Registry.CurrentUser, Registry.LocalMachine })
            {
                try
                {
                    using var uninstall = hive.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall");
                    if (uninstall is null) continue;
                    foreach (var subName in uninstall.GetSubKeyNames())
                    {
                        using var sub = uninstall.OpenSubKey(subName);
                        var display = sub?.GetValue("DisplayName")?.ToString() ?? string.Empty;
                        if (!display.Contains("MXB App", StringComparison.OrdinalIgnoreCase)) continue;

                        var location = (sub?.GetValue("InstallLocation")?.ToString() ?? string.Empty).Trim('"');
                        if (!string.IsNullOrWhiteSpace(location))
                        {
                            var exe = Path.Combine(location, "MXB App.exe");
                            if (File.Exists(exe)) return exe;
                        }

                        var icon = (sub?.GetValue("DisplayIcon")?.ToString() ?? string.Empty).Trim('"');
                        if (icon.EndsWith(".exe", StringComparison.OrdinalIgnoreCase) && File.Exists(icon)) return icon;
                    }
                }
                catch { }
            }

            // Last resort: search only a few likely shallow LocalAppData folders, never the whole drive.
            try
            {
                foreach (var dir in Directory.EnumerateDirectories(local)
                             .Where(d => Path.GetFileName(d).Contains("mxb", StringComparison.OrdinalIgnoreCase)))
                {
                    var exe = Directory.EnumerateFiles(dir, "MXB App.exe", SearchOption.AllDirectories).FirstOrDefault();
                    if (!string.IsNullOrWhiteSpace(exe)) return exe;
                }
            }
            catch { }
            return null;
        }

        private static async Task<IntPtr> WaitForWindowAsync(Process process, CancellationToken cancellationToken)
        {
            var until = DateTime.UtcNow + TimeSpan.FromSeconds(20);
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

    private static class FrostAutomation
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
                catch (Exception ex)
                {
                    tcs.SetException(ex);
                }
            })
            {
                IsBackground = true,
                Name = "MXB-RDL Frost UI bridge"
            };
            thread.SetApartmentState(ApartmentState.STA);
            thread.Start();
            cancellationToken.Register(() => tcs.TrySetCanceled(cancellationToken));
            return tcs.Task;
        }

        private static void SelectBike(IntPtr hwnd, string bikeId, CancellationToken cancellationToken)
        {
            var root = AutomationElement.FromHandle(hwnd)
                ?? throw new InvalidOperationException("Race Day Live could not access the MXB App/Frost window.");

            var studio = WaitElement(root, e => Name(e).Equals("Studio", StringComparison.OrdinalIgnoreCase), TimeSpan.FromSeconds(15), cancellationToken);
            Invoke(studio);
            Thread.Sleep(350);

            root = AutomationElement.FromHandle(hwnd) ?? root;
            var designer = FindElement(root, e => Name(e).Equals("Designer", StringComparison.OrdinalIgnoreCase));
            if (designer is not null) Invoke(designer);
            Thread.Sleep(350);

            root = AutomationElement.FromHandle(hwnd) ?? root;
            var destination = WaitElement(
                root,
                e => e.Current.ControlType == ControlType.Button
                     && (Name(e).Contains("Bike livery", StringComparison.OrdinalIgnoreCase)
                         || Name(e).Contains("bikes/", StringComparison.OrdinalIgnoreCase)),
                TimeSpan.FromSeconds(8),
                cancellationToken);
            Invoke(destination);
            Thread.Sleep(250);

            root = AutomationElement.FromHandle(hwnd) ?? root;
            var combo = WaitElement(
                root,
                e => e.Current.ControlType == ControlType.ComboBox
                     || (e.Current.ControlType == ControlType.Button && LooksLikeBikeId(Name(e))),
                TimeSpan.FromSeconds(5),
                cancellationToken);
            Invoke(combo);
            Thread.Sleep(250);

            root = AutomationElement.FromHandle(hwnd) ?? root;
            var search = WaitElement(root, e => e.Current.ControlType == ControlType.Edit, TimeSpan.FromSeconds(5), cancellationToken);
            SetText(search, bikeId);
            Thread.Sleep(300);

            root = AutomationElement.FromHandle(hwnd) ?? root;
            var option = WaitElement(
                root,
                e => Name(e).Equals(bikeId, StringComparison.OrdinalIgnoreCase),
                TimeSpan.FromSeconds(6),
                cancellationToken);
            Invoke(option);

            // Let Frost's WebGL viewer finish loading before Race Day Live reparents the window.
            Thread.Sleep(1200);
        }

        private static bool LooksLikeBikeId(string name) =>
            name.StartsWith("MX1OEM_", StringComparison.OrdinalIgnoreCase)
            || name.StartsWith("MX2OEM_", StringComparison.OrdinalIgnoreCase)
            || name.Contains("OEM_20", StringComparison.OrdinalIgnoreCase);

        private static AutomationElement WaitElement(
            AutomationElement root,
            Func<AutomationElement, bool> predicate,
            TimeSpan timeout,
            CancellationToken cancellationToken)
        {
            var until = DateTime.UtcNow + timeout;
            do
            {
                cancellationToken.ThrowIfCancellationRequested();
                var found = FindElement(root, predicate);
                if (found is not null) return found;
                Thread.Sleep(150);
            } while (DateTime.UtcNow < until);

            throw new InvalidOperationException(
                "MXB App/Frost is installed and running, but Race Day Live could not aim its Studio renderer at this bike automatically.");
        }

        private static AutomationElement? FindElement(AutomationElement root, Func<AutomationElement, bool> predicate)
        {
            try
            {
                if (predicate(root)) return root;
                var all = root.FindAll(TreeScope.Descendants, Condition.TrueCondition);
                for (var i = 0; i < all.Count; i++)
                {
                    try { if (predicate(all[i])) return all[i]; }
                    catch (ElementNotAvailableException) { }
                }
            }
            catch (ElementNotAvailableException) { }
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
                if (element.TryGetCurrentPattern(InvokePattern.Pattern, out var pattern))
                {
                    ((InvokePattern)pattern).Invoke();
                    return;
                }
                if (element.TryGetCurrentPattern(ExpandCollapsePattern.Pattern, out var expand))
                {
                    ((ExpandCollapsePattern)expand).Expand();
                    return;
                }
                if (element.TryGetCurrentPattern(SelectionItemPattern.Pattern, out var select))
                {
                    ((SelectionItemPattern)select).Select();
                    return;
                }
                element.SetFocus();
                Native.SendEnter();
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException($"MXB App/Frost control '{Name(element)}' could not be activated.", ex);
            }
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

            element.SetFocus();
            Native.SendCtrlA();
            Native.SendUnicode(value);
        }
    }

    private sealed class FrostWindowHost : HwndHost
    {
        private readonly IntPtr _external;
        private readonly Process? _ownedProcess;
        private IntPtr _container;
        private IntPtr _originalParent;
        private nint _originalStyle;
        private nint _originalExStyle;

        public FrostWindowHost(IntPtr external, Process? ownedProcess)
        {
            _external = external;
            _ownedProcess = ownedProcess;
        }

        protected override HandleRef BuildWindowCore(HandleRef hwndParent)
        {
            _container = Native.CreateWindowEx(
                0, "static", string.Empty,
                Native.WS_CHILD | Native.WS_VISIBLE | Native.WS_CLIPCHILDREN | Native.WS_CLIPSIBLINGS,
                0, 0, 800, 600,
                hwndParent.Handle, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero);
            if (_container == IntPtr.Zero) throw new InvalidOperationException("Race Day Live could not create the sealed-bike preview host.");

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
                if (_external != IntPtr.Zero && Native.IsWindow(_external))
                {
                    Native.SetParent(_external, _originalParent);
                    Native.SetWindowLongPtr(_external, Native.GWL_STYLE, _originalStyle);
                    Native.SetWindowLongPtr(_external, Native.GWL_EXSTYLE, _originalExStyle);
                    if (_ownedProcess is null || !_ownedProcess.HasExited)
                        Native.ShowWindow(_external, Native.SW_HIDE);
                }
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
        [DllImport("user32.dll")] internal static extern bool IsWindow(IntPtr hwnd);
        [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")] private static extern IntPtr GetWindowLongPtr64(IntPtr hwnd, int index);
        [DllImport("user32.dll", EntryPoint = "GetWindowLongW")] private static extern int GetWindowLong32(IntPtr hwnd, int index);
        [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")] private static extern IntPtr SetWindowLongPtr64(IntPtr hwnd, int index, IntPtr value);
        [DllImport("user32.dll", EntryPoint = "SetWindowLongW")] private static extern int SetWindowLong32(IntPtr hwnd, int index, int value);
        [DllImport("user32.dll")] private static extern uint SendInput(uint count, INPUT[] inputs, int size);

        internal static nint GetWindowLongPtr(IntPtr hwnd, int index) => IntPtr.Size == 8 ? GetWindowLongPtr64(hwnd, index) : new IntPtr(GetWindowLong32(hwnd, index));
        internal static nint SetWindowLongPtr(IntPtr hwnd, int index, nint value) => IntPtr.Size == 8 ? SetWindowLongPtr64(hwnd, index, value) : new IntPtr(SetWindowLong32(hwnd, index, value.ToInt32()));

        internal static void SendCtrlA()
        {
            SendKey(VK_CONTROL, false); SendKey(VK_A, false); SendKey(VK_A, true); SendKey(VK_CONTROL, true);
        }

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
