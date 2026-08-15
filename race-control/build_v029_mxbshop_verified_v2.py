from pathlib import Path
import runpy, tempfile

src = Path('race-control/build_v029_mxbshop_verified.py').read_text(encoding='utf-8')
start = src.index('# Keep UPDATE button recoverable after any failed update')
end = src.index('# Patch track-media resolution', start)
replacement = """# Preserve a known-good in-app update flow. Replacing the whole method prevents\n# feature releases from regressing detection, failure recovery, or restart.\napp_path = work / 'src/app.py'\napp = app_path.read_text(encoding='utf-8')\ndo_start = app.index('    def do_update(self):')\ndo_end = app.index('\\ndef main():', do_start)\nknown_good_do_update = r'''    def do_update(self):\n        self.update_btn.configure(state='disabled',text='REFRESHING UPDATE FEED…')\n        def worker():\n            try:\n                m=check_for_update()\n                if not m.get('available'):\n                    self.after(0,lambda:(self.update_btn.configure(state='normal',text='UPDATE'),messagebox.showinfo('MXB Race Day Live',f'You are on the latest version: v{VERSION}')))\n                    return\n                self.after(0,lambda:self.update_btn.configure(text=f\"DOWNLOADING {m['version']}…\"))\n                z=download_update(m)\n                launch_update(z)\n                def close_for_update():\n                    try:self.update_btn.configure(text='INSTALLING & RESTARTING…')\n                    except Exception:pass\n                    self.after(300,self._on_close)\n                self.after(0,close_for_update)\n            except Exception as e:\n                msg=str(e)\n                def fail(msg=msg):\n                    self.update_btn.configure(state='normal',text='UPDATE')\n                    messagebox.showerror('Update Failed',msg)\n                self.after(0,fail)\n        threading.Thread(target=worker,daemon=True).start()\n'''\napp = app[:do_start] + known_good_do_update + app[do_end:]\napp_path.write_text(app, encoding='utf-8')\n\n"""
patched = src[:start] + replacement + src[end:]
out = Path(tempfile.gettempdir()) / 'build_v029_mxbshop_verified_patched.py'
out.write_text(patched, encoding='utf-8')
compile(patched, str(out), 'exec')
runpy.run_path(str(out), run_name='__main__')
