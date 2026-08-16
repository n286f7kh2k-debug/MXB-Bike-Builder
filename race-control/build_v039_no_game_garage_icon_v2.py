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
anchor="app=app.replace('NativeRendererError','GarageModelError')\np.write_text(app,encoding='utf-8')"
patched="""app=app.replace('NativeRendererError','GarageModelError')
app=app.replace('from .native_renderer import MXBNativeRenderer, GarageModelError','from .in_app_garage import InAppGarageRenderer, GarageModelError')
app=app.replace('from .native_renderer import MXBNativeRenderer, NativeRendererError','from .in_app_garage import InAppGarageRenderer, GarageModelError')
app=app.replace('self.native_renderer','self.garage_renderer')
app=app.replace('native_renderer','garage_renderer')
app=app.replace('MXBNativeRenderer','InAppGarageRenderer')
app=app.replace('command=lambda:start_live_renderer(True)','command=lambda:draw_garage3d(True)')
app=app.replace('start_live_renderer(False)','draw_garage3d(False)')
app=re.sub(r\"render_host=tk\\.Frame\\(preview_wrap,bg='#050607',height=350,cursor='crosshair'\\); render_host\\.pack\\(fill='x',padx=1,pady=\\(0,1\\)\\); render_host\\.pack_propagate\\(False\\)\",\"render_host=tk.Canvas(preview_wrap,bg='#050607',height=350,highlightthickness=0,cursor='fleur'); render_host.pack(fill='x',padx=1,pady=(0,1))\",app,count=1)
app=app.replace(\"render_fallback.pack(fill='both',expand=True)\",\"render_fallback.place(relx=.5,rely=.5,anchor='center')\")
app=app.replace(\"text='RELOAD 3D'\",\"text='RESET 3D VIEW'\")
app=re.sub(r\"(?m)^        tk\\.Button\\(live_controls,text='PAUSE 3D'.*\\n\",'',app,count=1)
app=re.sub(r\"(?m)^        if self\\.garage_renderer\\.supported and self\\.game_bridge\\.game_found\\(\\):.*\\n        else:render_status\\.configure\\(.*\\n\",\"        self.after_idle(lambda:draw_garage3d(True))\\n\",app,count=1)
p.write_text(app,encoding='utf-8')"""
if anchor not in src:
    raise SystemExit('v0.3.9 stale renderer anchor missing')
src=src.replace(anchor,patched,1)
labels={
"assert 'native_renderer' not in app.lower()":"assert 'native_renderer' not in app.lower(), 'gate:native_renderer_removed'",
"assert 'MXBNativeRenderer' not in app and 'start_live_renderer' not in app":"assert 'MXBNativeRenderer' not in app and 'start_live_renderer' not in app, 'gate:legacy_renderer_callbacks_removed'",
"assert 'mxbikes.exe' not in inapp.lower() and 'subprocess' not in inapp.lower() and \"'-testing'\" not in inapp":"assert 'mxbikes.exe' not in inapp.lower() and 'subprocess' not in inapp.lower() and \"'-testing'\" not in inapp, 'gate:no_external_process_in_inapp_renderer'",
"assert 'InAppGarageRenderer' in app and 'tk.Canvas' in app and \"RESET 3D VIEW\" in app":"assert 'InAppGarageRenderer' in app and 'tk.Canvas' in app and \"RESET 3D VIEW\" in app, 'gate:garage_canvas_and_controls'",
"assert 'Race Day Live will NOT launch MX Bikes' in app":"assert 'Race Day Live will NOT launch MX Bikes' in app, 'gate:no_game_launch_user_message'",
"assert 'apply_selection' in app and 'profile.ini' in app":"assert 'apply_selection' in app and 'profile.ini' in app, 'gate:native_profile_sync_preserved'",
"assert \"APP_ID='MXBRaceDayLive.Desktop.v3'\" in wint":"assert \"APP_ID='MXBRaceDayLive.Desktop.v3'\" in wint, 'gate:windows_app_id_v3'",
"assert 'shortcut_icon_location' in wint and 'IconLocation' in wint and 'ensure_desktop_shortcut' in wint":"assert 'shortcut_icon_location' in wint and 'IconLocation' in wint and 'ensure_desktop_shortcut' in wint, 'gate:shortcut_icon_source'",
"assert 'best_icon' in task and 'WM_SETICON' in task and 'ICON_BIG' in task and 'ICON_SMALL' in task":"assert 'best_icon' in task and 'WM_SETICON' in task and 'ICON_BIG' in task and 'ICON_SMALL' in task, 'gate:taskbar_hwnd_icon'",
"assert \"APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v3'\" in app":"assert \"APP_USER_MODEL_ID='MXBRaceDayLive.Desktop.v3'\" in app, 'gate:app_user_model_id_v3'",
"assert 'check_for_update' in app and 'launch_update' in app and 'api.github.com/repos/' in up":"assert 'check_for_update' in app and 'launch_update' in app and 'api.github.com/repos/' in up, 'gate:updater_preserved'",
"assert 'JOIN RACE SERVER' in app and 'member_quote' in app and 'fastest_lap_pool' in app":"assert 'JOIN RACE SERVER' in app and 'member_quote' in app and 'fastest_lap_pool' in app, 'gate:race_membership_economics_preserved'",
"assert 'TrackMediaResolver' in app and 'MXGameBridge' in app":"assert 'TrackMediaResolver' in app and 'MXGameBridge' in app, 'gate:track_and_game_bridge_preserved'",
}
for old_assert,new_assert in labels.items():
    src=src.replace(old_assert,new_assert)
exec(compile(src,'build_v039_no_game_garage_icon_v2.py','exec'),{'__name__':'__main__','__file__':str(src_path)})
