from pathlib import Path

src_path=Path('race-control/build_v039_no_game_garage_icon.py')
src=src_path.read_text(encoding='utf-8')
old="app=app.replace('try:self.native_renderer.stop()\\n        except Exception:pass\\n','')"
new="app=re.sub(r'(?m)^        try:self\\.native_renderer\\.stop\\(\\)\\n        except Exception:pass\\n','',app)"
if old not in src:
    raise SystemExit('v0.3.9 indentation patch anchor missing')
src=src.replace(old,new,1)
old2="app=app.replace(\"if getattr(self,'current_page',None)=='GARAGE' and page!='GARAGE':\\n            try:self.native_renderer.stop()\\n            except Exception:pass\\n\",'')"
new2="app=re.sub(r\"(?m)^        if getattr\\(self,'current_page',None\\)=='GARAGE' and page!='GARAGE':\\n            try:self\\.native_renderer\\.stop\\(\\)\\n            except Exception:pass\\n\",'',app)"
if old2 in src:
    src=src.replace(old2,new2,1)
# Replace every stale attribute in the generated app after the old cleanup blocks are removed.
anchor="app=app.replace('NativeRendererError','GarageModelError')\np.write_text(app,encoding='utf-8')"
patched="app=app.replace('NativeRendererError','GarageModelError')\napp=app.replace('self.native_renderer','self.garage_renderer')\np.write_text(app,encoding='utf-8')"
if anchor not in src:
    raise SystemExit('v0.3.9 stale renderer anchor missing')
src=src.replace(anchor,patched,1)
exec(compile(src,'build_v039_no_game_garage_icon_v2.py','exec'),{'__name__':'__main__','__file__':str(src_path)})
