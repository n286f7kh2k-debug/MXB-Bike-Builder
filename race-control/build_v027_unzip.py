import runpy
import subprocess
import zipfile

_original_extractall = zipfile.ZipFile.extractall

def _safe_extractall(self, path=None, members=None, pwd=None):
    if self.filename:
        self.close()
        subprocess.run(['unzip', '-o', str(self.filename), '-d', str(path)], check=True)
        return
    return _original_extractall(self, path=path, members=members, pwd=pwd)

zipfile.ZipFile.extractall = _safe_extractall
runpy.run_path('race-control/build_v027.py', run_name='__main__')
