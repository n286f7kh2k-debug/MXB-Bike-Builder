from __future__ import annotations

import importlib
import json
import os
import py_compile
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


class HotUpdateError(RuntimeError):
    pass


def _install_root():
    return Path(__file__).resolve().parent.parent


def _safe_rel(name):
    rel=Path(name)
    if rel.is_absolute() or '..' in rel.parts:
        raise HotUpdateError(f'Unsafe path in update package: {name}')
    return rel


def _compile_tree(root):
    for py in Path(root).rglob('*.py'):
        if '__pycache__' in py.parts:continue
        py_compile.compile(str(py),doraise=True)


def install_hot_update(update_zip,install_dir=None):
    """Atomically overlays an update while Race Day Live remains open.

    A rollback copy is kept until the refreshed runtime has loaded successfully.
    User data under AppData/Documents is never part of this install tree.
    """
    update_zip=Path(update_zip).resolve()
    install=Path(install_dir or _install_root()).resolve()
    if not update_zip.is_file() or not zipfile.is_zipfile(update_zip):
        raise HotUpdateError('Downloaded update is not a valid ZIP package.')
    work=Path(tempfile.mkdtemp(prefix='mxb_rdl_hot_stage_'))
    backup=Path(tempfile.mkdtemp(prefix='mxb_rdl_hot_backup_'))
    created=[]; replaced=[]
    try:
        with zipfile.ZipFile(update_zip) as z:
            for info in z.infolist():_safe_rel(info.filename)
            z.extractall(work)
        required=('app.py','src/app.py','src/config.py','src/updater.py')
        missing=[x for x in required if not (work/x).is_file()]
        if missing:raise HotUpdateError('Update package is incomplete: '+', '.join(missing))
        _compile_tree(work)
        files=[p for p in sorted(work.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
        for src in files:
            rel=src.relative_to(work)
            dst=install/rel
            dst.parent.mkdir(parents=True,exist_ok=True)
            if dst.exists():
                save=backup/rel; save.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(dst,save); replaced.append(rel.as_posix())
            else:
                created.append(rel.as_posix())
            tmp=dst.with_name(dst.name+'.mxbhot')
            try:
                shutil.copy2(src,tmp)
                os.replace(tmp,dst)
            finally:
                try:tmp.unlink(missing_ok=True)
                except Exception:pass
        tx={'install':str(install),'backup':str(backup),'created':created,'replaced':replaced,
            'changed':[p.relative_to(work).as_posix() for p in files]}
        (backup/'transaction.json').write_text(json.dumps(tx,indent=2),encoding='utf-8')
        return tx
    except Exception:
        shutil.rmtree(backup,ignore_errors=True)
        raise
    finally:
        shutil.rmtree(work,ignore_errors=True)
        try:update_zip.unlink(missing_ok=True)
        except Exception:pass


def rollback_hot_update(tx):
    install=Path(tx['install']); backup=Path(tx['backup'])
    for rel in tx.get('created',[]):
        try:(install/rel).unlink(missing_ok=True)
        except Exception:pass
    for rel in tx.get('replaced',[]):
        src=backup/rel; dst=install/rel
        if not src.is_file():continue
        dst.parent.mkdir(parents=True,exist_ok=True)
        tmp=dst.with_name(dst.name+'.mxbrollback')
        try:
            shutil.copy2(src,tmp); os.replace(tmp,dst)
        finally:
            try:tmp.unlink(missing_ok=True)
            except Exception:pass


def finalize_hot_update(tx):
    try:shutil.rmtree(Path(tx['backup']),ignore_errors=True)
    except Exception:pass


def _module_for_path(rel):
    p=Path(rel)
    if p.suffix!='.py':return None
    if p.as_posix()=='app.py':return None
    if not p.parts or p.parts[0]!='src':return None
    parts=list(p.with_suffix('').parts)
    if parts[-1]=='__init__':parts=parts[:-1]
    return '.'.join(parts) if parts else None


def _reload_changed_modules(changed,skip_hot_core=True):
    modules=[]
    for rel in changed:
        name=_module_for_path(rel)
        if name and name not in modules:modules.append(name)
    # App last. Config/services first. Stable hot_reload core is intentionally not
    # reloaded while its own transaction is executing.
    modules=[m for m in modules if m!='src.app' and (not skip_hot_core or m!='src.hot_reload')]
    priority=['src.config','src.runtime_perf','src.pricing','src.subscriptions','src.track_media','src.windows_integration',
              'src.windows_taskbar','src.game_bridge','src.bike_garage','src.in_app_garage','src.mx_extension','src.updater']
    ordered=[m for m in priority if m in modules]+[m for m in modules if m not in priority]
    for name in ordered:
        try:
            if name in sys.modules:importlib.reload(sys.modules[name])
            else:importlib.import_module(name)
        except ModuleNotFoundError:
            pass
    appmod=importlib.reload(sys.modules['src.app']) if 'src.app' in sys.modules else importlib.import_module('src.app')
    return appmod


def refresh_running_app(app,tx,target_version):
    """Load newly installed code into the existing Tk root; the process/window stays open."""
    snapshot={
        'page':getattr(app,'current_page','PROFILE'),
        'profile_section':getattr(app,'profile_section','OVERVIEW'),
        'race_filter':getattr(app,'race_filter','ALL'),
        'geometry':app.geometry() if hasattr(app,'geometry') else '',
    }
    try:
        importlib.invalidate_caches()
        appmod=_reload_changed_modules(tx.get('changed',[]))
        new_cls=getattr(appmod,'RaceDayLiveApp')
        app.__class__=new_cls
        hook=getattr(app,'_after_hot_reload',None)
        if not callable(hook):raise HotUpdateError('Updated UI does not expose the hot-refresh lifecycle hook.')
        hook(str(target_version),snapshot)
        finalize_hot_update(tx)
        return True
    except Exception as first:
        try:
            rollback_hot_update(tx)
            importlib.invalidate_caches()
            appmod=_reload_changed_modules(tx.get('changed',[]))
            old_cls=getattr(appmod,'RaceDayLiveApp')
            app.__class__=old_cls
            hook=getattr(app,'_after_hot_reload',None)
            if callable(hook):hook(getattr(sys.modules.get('src.config'),'VERSION',''),snapshot)
        except Exception:
            pass
        finally:
            finalize_hot_update(tx)
        raise HotUpdateError(f'Hot refresh failed and the previous files were restored: {first}') from first
