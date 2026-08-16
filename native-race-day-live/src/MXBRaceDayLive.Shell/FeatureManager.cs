using System.Reflection;
using System.Runtime.Loader;
using System.Windows;
using MXBRaceDayLive.Contracts;

namespace MXBRaceDayLive.Shell;

public sealed class FeatureManager : IAsyncDisposable
{
    private FeatureLoadContext? _loadContext;
    private IRaceDayFeature? _feature;
    private WeakReference? _oldContext;

    public FrameworkElement? CurrentView { get; private set; }
    public Version CurrentVersion => _feature?.Version ?? new Version(0, 0, 0);
    public event EventHandler<FrameworkElement>? ViewChanged;

    public async Task LoadAsync(string assemblyPath, IRaceDayContext context, CancellationToken cancellationToken = default)
    {
        if (!File.Exists(assemblyPath)) throw new FileNotFoundException("Race Day Live feature module was not found.", assemblyPath);

        var nextContext = new FeatureLoadContext(assemblyPath);
        IRaceDayFeature? nextFeature = null;
        FrameworkElement? nextView = null;
        try
        {
            var assembly = nextContext.LoadFromAssemblyPath(Path.GetFullPath(assemblyPath));
            var type = assembly.GetTypes().FirstOrDefault(t => !t.IsAbstract && typeof(IRaceDayFeature).IsAssignableFrom(t));
            if (type is null) throw new InvalidOperationException("The module does not contain an IRaceDayFeature implementation.");
            nextFeature = (IRaceDayFeature?)Activator.CreateInstance(type)
                          ?? throw new InvalidOperationException("The feature module could not be created.");
            nextView = nextFeature.CreateView(context);
            await nextFeature.OnActivatedAsync(cancellationToken);
        }
        catch
        {
            nextFeature?.Dispose();
            nextContext.Unload();
            throw;
        }

        var oldFeature = _feature;
        var oldContext = _loadContext;
        _feature = nextFeature;
        _loadContext = nextContext;
        CurrentView = nextView;
        ViewChanged?.Invoke(this, nextView);

        if (oldFeature is not null)
        {
            try { await oldFeature.OnDeactivatedAsync(cancellationToken); } catch { }
            try { oldFeature.Dispose(); } catch { }
        }
        if (oldContext is not null)
        {
            _oldContext = new WeakReference(oldContext);
            oldContext.Unload();
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_feature is not null)
        {
            try { await _feature.OnDeactivatedAsync(); } catch { }
            try { _feature.Dispose(); } catch { }
        }
        _feature = null;
        CurrentView = null;
        _loadContext?.Unload();
        _loadContext = null;
    }

    private sealed class FeatureLoadContext : AssemblyLoadContext
    {
        private readonly AssemblyDependencyResolver _resolver;

        public FeatureLoadContext(string mainAssemblyPath) : base(isCollectible: true)
        {
            _resolver = new AssemblyDependencyResolver(mainAssemblyPath);
        }

        protected override Assembly? Load(AssemblyName assemblyName)
        {
            if (assemblyName.Name == typeof(IRaceDayFeature).Assembly.GetName().Name) return null;
            var path = _resolver.ResolveAssemblyToPath(assemblyName);
            return path is null ? null : LoadFromAssemblyPath(path);
        }
    }
}
