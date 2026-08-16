from pathlib import Path
src=Path('race-control/build_v039_no_game_garage_icon_v2.py').read_text(encoding='utf-8')
# Patch the generated app immediately before it is written so no old attribute survives.
needle="app=app.replace('NativeRendererError','GarageModelError')\np.write_text(app,encoding='utf-8')"
replacement="app=app.replace('NativeRendererError','GarageModelError')\napp=app.replace('self.native_renderer','self.garage_renderer')\np.write_text(app,encoding='utf-8')"
if needle not in src:raise SystemExit('v3 patch anchor missing')
src=src.replace(needle,replacement,1)
exec(compile(src,'build_v039_no_game_garage_icon_v3.py','exec'),{'__name__':'__main__','__file__':'race-control/build_v039_no_game_garage_icon_v3.py'})
