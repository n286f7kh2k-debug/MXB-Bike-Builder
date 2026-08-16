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
app=app.replace('self.native_renderer','self.garage_renderer')
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
exec(compile(src,'build_v039_no_game_garage_icon_v2.py','exec'),{'__name__':'__main__','__file__':str(src_path)})
