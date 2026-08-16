from pathlib import Path

source_path = Path('race-control/build_v035_native_3d.py')
source = source_path.read_text(encoding='utf-8')
needle = 'new_preview="""'
replacement = 'new_preview=r"""'
if needle not in source:
    raise SystemExit('Could not locate v0.3.5 preview generator string')
source = source.replace(needle, replacement, 1)
code = compile(source, str(source_path), 'exec')
ns = {'__name__': '__main__', '__file__': str(source_path)}
exec(code, ns, ns)
