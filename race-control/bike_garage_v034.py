from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


class BikeGarageError(RuntimeError):
    pass


def _ini_value(text, section, key, default=''):
    in_section = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('[') and line.endswith(']'):
            in_section = line[1:-1].strip().lower() == section.lower()
            continue
        if in_section and '=' in raw:
            left, right = raw.split('=', 1)
            if left.strip().lower() == key.lower():
                return right.strip()
    return default


def _update_info_section(text, values):
    lines = text.splitlines()
    section_start = None
    section_end = len(lines)
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.lower() == '[info]':
            section_start = i
            continue
        if section_start is not None and i > section_start and line.startswith('[') and line.endswith(']'):
            section_end = i
            break
    if section_start is None:
        if lines and lines[-1].strip():
            lines.append('')
        lines.append('[info]')
        section_start = len(lines) - 1
        section_end = len(lines)

    key_lines = {}
    for i in range(section_start + 1, section_end):
        if '=' in lines[i]:
            key = lines[i].split('=', 1)[0].strip().lower()
            key_lines[key] = i

    inserts = []
    for key, value in values.items():
        k = key.lower()
        line = f'{key}={value}'
        if k in key_lines:
            lines[key_lines[k]] = line
        else:
            inserts.append(line)
    if inserts:
        lines[section_end:section_end] = inserts
    return '\n'.join(lines) + '\n'


def _unique(items):
    out, seen = [], set()
    for value in items:
        value = str(value or '').strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key); out.append(value)
    return out


def _file_stems(paths):
    vals = []
    for root in paths:
        try:
            if root.is_dir():
                vals.extend(p.stem for p in root.iterdir() if p.is_file() and p.suffix.lower() == '.pnt')
        except Exception:
            pass
    return _unique(vals)


class MXBikeGarage:
    """Reads/writes the same MX Bikes profile selections used by the in-game Bike Selection screen."""

    PROFILE_KEYS = (
        'bikeid', 'paint', 'bike_font', 'rider', 'helmet', 'helmet_paint', 'goggles_paint',
        'helmet_cam', 'suit_paint', 'suit_font', 'boots', 'boots_paint', 'gloves_paint',
        'protection', 'protection_paint', 'race_number', 'suit_name',
    )

    def __init__(self, conn, game_bridge, username=''):
        self.conn = conn
        self.game_bridge = game_bridge
        self.username = username

    def _rider_row(self):
        try:
            return self.conn.execute('SELECT * FROM riders WHERE username=?', (self.username,)).fetchone()
        except Exception:
            return None

    def _user_roots(self):
        home = Path.home()
        roots = [
            home / 'Documents' / 'PiBoSo' / 'MX Bikes',
            home / 'OneDrive' / 'Documents' / 'PiBoSo' / 'MX Bikes',
        ]
        userprofile = os.environ.get('USERPROFILE')
        if userprofile:
            roots.extend([
                Path(userprofile) / 'Documents' / 'PiBoSo' / 'MX Bikes',
                Path(userprofile) / 'OneDrive' / 'Documents' / 'PiBoSo' / 'MX Bikes',
            ])
        out, seen = [], set()
        for p in roots:
            k = str(p).lower()
            if k not in seen:
                seen.add(k); out.append(p)
        return out

    def user_root(self):
        candidates = self._user_roots()
        for root in candidates:
            if (root / 'global.ini').is_file() or (root / 'profiles').is_dir() or (root / 'mods').is_dir():
                return root
        return candidates[0]

    def global_ini(self):
        return self.user_root() / 'global.ini'

    def profile_name(self):
        rider = self._rider_row()
        if rider:
            try:
                value = str(rider['game_profile_name'] or '').strip()
                if value:
                    return value
            except Exception:
                pass
        try:
            text = self.global_ini().read_text(encoding='utf-8', errors='ignore')
            for key in ('lastprofile', 'nickname'):
                value = _ini_value(text, 'profile', key, '').strip()
                if value:
                    return value
        except Exception:
            pass
        profiles = self.user_root() / 'profiles'
        try:
            dirs = [p for p in profiles.iterdir() if p.is_dir() and (p / 'profile.ini').is_file()]
            if len(dirs) == 1:
                return dirs[0].name
        except Exception:
            pass
        return ''

    def profile_ini(self):
        name = self.profile_name()
        if not name:
            return None
        path = self.user_root() / 'profiles' / name / 'profile.ini'
        return path if path.is_file() else None

    def read_selection(self):
        path = self.profile_ini()
        values = {key: '' for key in self.PROFILE_KEYS}
        if not path:
            return values
        text = path.read_text(encoding='utf-8', errors='ignore')
        for key in self.PROFILE_KEYS:
            values[key] = _ini_value(text, 'info', key, '')
        return values

    def apply_selection(self, values):
        path = self.profile_ini()
        if not path:
            raise BikeGarageError('MX Bikes profile.ini was not found. Launch MX Bikes once, choose the correct profile, then sync again.')
        current = path.read_text(encoding='utf-8', errors='ignore')
        backup = path.with_name('profile.race_day_live_backup.ini')
        if not backup.exists():
            shutil.copy2(path, backup)
        clean = {key: str(values.get(key, '') or '').strip() for key in self.PROFILE_KEYS if key in values}
        updated = _update_info_section(current, clean)
        tmp = path.with_suffix('.race_day_live_tmp')
        tmp.write_text(updated, encoding='utf-8')
        os.replace(tmp, path)
        rider = self._rider_row()
        if rider:
            try:
                self.conn.execute('UPDATE riders SET game_bike_id=?,bike_model=? WHERE id=?',
                                  (clean.get('bikeid', ''), self.bike_display(clean.get('bikeid', '')), rider['id']))
                self.conn.commit()
            except Exception:
                pass
        return path

    def install_root(self):
        exe = self.game_bridge.game_exe()
        return exe.parent if exe else None

    def mods_root(self):
        global_path = self.global_ini()
        try:
            text = global_path.read_text(encoding='utf-8', errors='ignore')
            raw = _ini_value(text, 'mods', 'folder', '').strip().strip('"')
            if raw:
                return Path(os.path.expandvars(raw))
        except Exception:
            pass
        return self.user_root() / 'mods'

    def _roots(self):
        roots = []
        install = self.install_root()
        if install:
            roots.append(install)
        mods = self.mods_root()
        roots.append(mods)
        out, seen = [], set()
        for p in roots:
            k = str(p).lower()
            if k not in seen:
                seen.add(k); out.append(p)
        return out

    def _bike_dirs(self, bike_id):
        return [root / 'bikes' / bike_id for root in self._roots()]

    def _rider_dirs(self, rider_id):
        paths = []
        for root in self._roots():
            paths.extend([root / 'rider' / 'riders' / rider_id, root / 'rider'])
        return paths

    def bike_records(self):
        records = {}
        try:
            for row in self.conn.execute("SELECT content_id,display_name,path FROM game_content WHERE UPPER(content_type) IN ('BIKE','BIKES')"):
                bid = str(row['content_id'] or '').strip()
                if bid:
                    records[bid.lower()] = {'id': bid, 'display': str(row['display_name'] or bid).strip(), 'category': '', 'path': str(row['path'] or '')}
        except Exception:
            pass
        for root in self._roots():
            base = root / 'bikes'
            try:
                for folder in base.iterdir():
                    if folder.is_dir():
                        key = folder.name.lower()
                        records.setdefault(key, {'id': folder.name, 'display': folder.name, 'category': '', 'path': str(folder)})
            except Exception:
                pass
        for rec in records.values():
            rec['category'] = self.bike_category(rec['id']) or 'OTHER'
        return sorted(records.values(), key=lambda x: (x['category'].lower(), x['display'].lower()))

    def bike_category(self, bike_id):
        for folder in self._bike_dirs(bike_id):
            try:
                for ini in list(folder.glob('*.ini'))[:12]:
                    text = ini.read_text(encoding='utf-8', errors='ignore')
                    match = re.search(r'^\s*category\s*=\s*(.+?)\s*$', text, flags=re.I | re.M)
                    if match:
                        return match.group(1).strip()
            except Exception:
                pass
        return ''

    def bike_display(self, bike_id):
        bike_id = str(bike_id or '').strip()
        for rec in self.bike_records():
            if rec['id'].lower() == bike_id.lower():
                return rec['display']
        return bike_id

    def categories(self):
        return _unique(rec['category'] for rec in self.bike_records()) or ['OTHER']

    def bikes_for_category(self, category):
        recs = self.bike_records()
        matches = [r for r in recs if r['category'].lower() == str(category or '').lower()]
        return matches or recs

    def bike_paints(self, bike_id):
        paths = [folder / 'paints' for folder in self._bike_dirs(bike_id)]
        return _unique([''] + _file_stems(paths))

    def _model_dirs(self, rel_parts, defaults):
        vals = list(defaults)
        for root in self._roots():
            base = root.joinpath(*rel_parts)
            try:
                vals.extend(p.name for p in base.iterdir() if p.is_dir())
            except Exception:
                pass
        return _unique(vals)

    def rider_models(self):
        return self._model_dirs(('rider', 'riders'), ('default_mx', 'default'))

    def helmet_models(self):
        return self._model_dirs(('rider', 'helmets'), ('default',))

    def boot_models(self):
        return self._model_dirs(('rider', 'boots'), ('default',))

    def protection_models(self):
        vals = ['default', 'none']
        for parts in (('rider','protections'), ('rider','protection')):
            vals.extend(self._model_dirs(parts, ()))
        return _unique(vals)

    def rider_paints(self, rider_id):
        paths = []
        for root in self._roots():
            paths.extend([root/'rider'/'riders'/rider_id/'paints', root/'rider'/'paints'])
        return _unique([''] + _file_stems(paths))

    def gloves_paints(self, rider_id):
        paths = []
        for root in self._roots():
            paths.extend([root/'rider'/'riders'/rider_id/'gloves', root/'rider'/'gloves'])
        return _unique([''] + _file_stems(paths))

    def helmet_paints(self, helmet_id):
        paths = []
        for root in self._roots():
            paths.extend([root/'rider'/'helmets'/helmet_id/'paints', root/'rider'/'helmets'/helmet_id])
        return _unique([''] + _file_stems(paths))

    def goggles_paints(self, helmet_id):
        paths = []
        for root in self._roots():
            paths.extend([root/'rider'/'helmets'/helmet_id/'goggles', root/'rider'/'goggles'])
        return _unique([''] + _file_stems(paths))

    def boot_paints(self, boot_id):
        paths = []
        for root in self._roots():
            paths.extend([root/'rider'/'boots'/boot_id/'paints', root/'rider'/'boots'/boot_id])
        return _unique([''] + _file_stems(paths))

    def protection_paints(self, protection_id):
        paths = []
        for root in self._roots():
            for base in ('protections','protection'):
                paths.extend([root/'rider'/base/protection_id/'paints', root/'rider'/base/protection_id])
        return _unique([''] + _file_stems(paths))

    def fonts(self, kind='bike'):
        vals = ['', 'default', 'default_black', 'default_white']
        for root in self._roots():
            candidates = [root/'fonts', root/'rider'/'fonts']
            if kind == 'bike':
                candidates.append(root/'bikes'/'fonts')
            for base in candidates:
                try:
                    vals.extend(p.stem for p in base.iterdir() if p.is_file() and p.suffix.lower() in ('.fnt','.pnt','.ini'))
                except Exception:
                    pass
        return _unique(vals)

    def helmet_cams(self):
        return ['', 'none', 'default']

    def garage_picture(self, bike_id):
        for folder in self._bike_dirs(bike_id):
            try:
                for ini in list(folder.glob('*.ini'))[:12]:
                    text = ini.read_text(encoding='utf-8', errors='ignore')
                    match = re.search(r'^\s*garage_pic\s*=\s*(.+?)\s*$', text, flags=re.I | re.M)
                    if match:
                        candidate = folder / match.group(1).strip().strip('"')
                        if candidate.is_file():
                            return candidate
                for pattern in ('garage.*', 'preview.*', 'bike.*'):
                    for candidate in folder.glob(pattern):
                        if candidate.suffix.lower() in ('.png','.jpg','.jpeg','.bmp','.tga','.webp'):
                            return candidate
            except Exception:
                pass
        return None

    def diagnostics(self):
        return {
            'user_root': str(self.user_root()),
            'profile': self.profile_name(),
            'profile_ini': str(self.profile_ini() or ''),
            'mods_root': str(self.mods_root()),
            'install_root': str(self.install_root() or ''),
            'bikes': len(self.bike_records()),
        }
