from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

STEAM_APP_ID = '655500'
DIRECT_CONNECT_FLAG = '-directconnect'
READY_SESSION_STATES = {'RUNNING', 'LIVE', 'STARTED', 'RACING'}


class GameBridgeError(RuntimeError):
    pass


def _row_dict(row):
    if row is None:
        return None
    try:
        return {k: row[k] for k in row.keys()}
    except Exception:
        return dict(row)


def _setting(conn, key, default=''):
    try:
        row = conn.execute('SELECT value FROM admin_settings WHERE key=?', (key,)).fetchone()
        return str(row['value'] if row else default)
    except Exception:
        return str(default)


def ensure_game_bridge_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS race_launch_targets (
        race_id INTEGER PRIMARY KEY,
        host TEXT,
        game_port INTEGER,
        server_name TEXT,
        status TEXT NOT NULL DEFAULT 'PREPARED',
        updated_at TEXT NOT NULL,
        FOREIGN KEY(race_id) REFERENCES races(id)
    )''')
    defaults = {
        'mx_public_server_host': '',
        'mx_game_exe_override': '',
        'mx_one_click_join': 'true',
        'mx_require_selected_bike': 'true',
    }
    for key, value in defaults.items():
        conn.execute('INSERT OR IGNORE INTO admin_settings(key,value) VALUES(?,?)', (key, value))
    conn.commit()


def list_synced_bikes(conn):
    try:
        rows = conn.execute('''SELECT content_id,display_name,path,last_seen
                               FROM game_content
                               WHERE UPPER(content_type) IN ('BIKE','BIKES')
                               ORDER BY display_name COLLATE NOCASE''').fetchall()
    except Exception:
        return []
    out = []
    seen = set()
    for row in rows:
        item = _row_dict(row)
        content_id = str(item.get('content_id') or '').strip()
        display = str(item.get('display_name') or content_id).strip()
        key = content_id.lower() or display.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        item['content_id'] = content_id
        item['display_name'] = display
        out.append(item)
    return out


def selected_race_bike(conn, race_id, rider_id):
    try:
        row = conn.execute('''SELECT game_bike_name,game_bike_short
                              FROM registrations
                              WHERE race_id=? AND rider_id=?''', (race_id, rider_id)).fetchone()
    except Exception:
        row = None
    if not row:
        return None
    name = str(row['game_bike_name'] or '').strip()
    short = str(row['game_bike_short'] or '').strip()
    if not name and not short:
        return None
    return {'display_name': name or short, 'content_id': short or name}


def save_race_bike(conn, race_id, rider_id, content_id, display_name):
    reg = conn.execute('SELECT id FROM registrations WHERE race_id=? AND rider_id=?', (race_id, rider_id)).fetchone()
    if not reg:
        raise GameBridgeError('You must be registered for this race before selecting a race bike.')
    content_id = str(content_id or '').strip()
    display_name = str(display_name or content_id).strip()
    if not content_id:
        raise GameBridgeError('Choose a synced MX Bikes bike first.')
    valid = conn.execute('''SELECT 1 FROM game_content
                            WHERE UPPER(content_type) IN ('BIKE','BIKES') AND content_id=?''', (content_id,)).fetchone()
    if not valid:
        raise GameBridgeError('That bike is no longer in the synced MX Bikes bike library. Run game sync and choose again.')
    conn.execute('''UPDATE registrations SET game_bike_name=?,game_bike_short=?
                    WHERE race_id=? AND rider_id=?''', (display_name, content_id, race_id, rider_id))
    try:
        conn.execute('UPDATE riders SET game_bike_id=? WHERE id=?', (content_id, rider_id))
    except Exception:
        pass
    conn.commit()
    return {'display_name': display_name, 'content_id': content_id}


def _candidate_steam_roots():
    roots = []
    env_roots = [os.environ.get('PROGRAMFILES(X86)'), os.environ.get('PROGRAMFILES')]
    for root in env_roots:
        if root:
            roots.append(Path(root) / 'Steam')
    for common in (r'C:\Program Files (x86)\Steam', r'C:\Program Files\Steam'):
        roots.append(Path(common))
    if os.name == 'nt':
        try:
            import winreg
            for hive, subkey, value_name in (
                (winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath'),
                (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Valve\Steam', 'InstallPath'),
            ):
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        value, _ = winreg.QueryValueEx(key, value_name)
                    if value:
                        roots.append(Path(str(value)))
                except Exception:
                    pass
        except Exception:
            pass
    unique = []
    seen = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _steam_libraries(root):
    libs = [Path(root)]
    vdf = Path(root) / 'steamapps' / 'libraryfolders.vdf'
    try:
        text = vdf.read_text(encoding='utf-8', errors='ignore')
        for value in re.findall(r'"path"\s+"([^"]+)"', text, flags=re.I):
            libs.append(Path(value.replace('\\\\', '\\')))
    except Exception:
        pass
    out, seen = [], set()
    for lib in libs:
        key = str(lib).lower()
        if key not in seen:
            seen.add(key); out.append(lib)
    return out


def find_mxbikes_exe(conn):
    override = _setting(conn, 'mx_game_exe_override', '').strip().strip('"')
    if override and Path(override).is_file():
        return Path(override)

    # Reuse paths already discovered by MXRaceAgent before scanning Windows.
    candidates = []
    try:
        for row in conn.execute('SELECT path FROM game_content ORDER BY last_seen DESC LIMIT 100'):
            raw = str(row['path'] or '').strip()
            if raw:
                p = Path(raw)
                candidates.append(p)
                candidates.extend(list(p.parents)[:7])
    except Exception:
        pass
    try:
        for row in conn.execute('SELECT value FROM game_sync_state'):
            raw = str(row['value'] or '').strip().strip('"')
            if raw and ('mx bikes' in raw.lower() or 'mxbikes' in raw.lower()):
                p = Path(raw)
                candidates.append(p)
                candidates.extend(list(p.parents)[:7])
    except Exception:
        pass
    for base in candidates:
        try:
            if base.is_file() and base.name.lower() == 'mxbikes.exe':
                return base
            exe = base / 'mxbikes.exe'
            if exe.is_file():
                return exe
        except Exception:
            pass

    for steam_root in _candidate_steam_roots():
        for lib in _steam_libraries(steam_root):
            exe = lib / 'steamapps' / 'common' / 'MX Bikes' / 'mxbikes.exe'
            if exe.is_file():
                return exe

    found = shutil.which('mxbikes.exe')
    return Path(found) if found else None


def find_steam_exe():
    for root in _candidate_steam_roots():
        exe = root / 'steam.exe'
        if exe.is_file():
            return exe
    found = shutil.which('steam.exe')
    return Path(found) if found else None


def publish_race_target(conn, race_id, host=None):
    ensure_game_bridge_schema(conn)
    try:
        race_id = int(race_id['id'])
    except Exception:
        race_id = int(race_id)
    session = conn.execute('SELECT * FROM race_sessions WHERE race_id=?', (race_id,)).fetchone()
    if not session:
        raise GameBridgeError('The MX Bikes race server has not been prepared yet.')
    public_host = str(host if host is not None else _setting(conn, 'mx_public_server_host', '')).strip()
    port = int(session['game_port'] or 0)
    state = str(session['status'] or 'PREPARED').upper()
    race = conn.execute('SELECT name FROM races WHERE id=?', (race_id,)).fetchone()
    name = str(race['name'] if race else 'MXB Race Day Live')
    now = datetime.now().replace(microsecond=0).isoformat()
    conn.execute('''INSERT INTO race_launch_targets(race_id,host,game_port,server_name,status,updated_at)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(race_id) DO UPDATE SET
                    host=excluded.host,game_port=excluded.game_port,server_name=excluded.server_name,
                    status=excluded.status,updated_at=excluded.updated_at''',
                 (race_id, public_host, port, name, state, now))
    conn.commit()
    return race_launch_target(conn, race_id)


def race_launch_target(conn, race_id):
    ensure_game_bridge_schema(conn)
    row = conn.execute('SELECT * FROM race_launch_targets WHERE race_id=?', (race_id,)).fetchone()
    target = _row_dict(row) if row else None
    session = conn.execute('SELECT * FROM race_sessions WHERE race_id=?', (race_id,)).fetchone()
    if session:
        s = _row_dict(session)
        if target is None:
            target = {
                'race_id': race_id,
                'host': _setting(conn, 'mx_public_server_host', '').strip(),
                'game_port': int(s.get('game_port') or 0),
                'server_name': '',
                'status': str(s.get('status') or 'PREPARED').upper(),
            }
        else:
            target['game_port'] = int(s.get('game_port') or target.get('game_port') or 0)
            target['status'] = str(s.get('status') or target.get('status') or 'PREPARED').upper()
    if target is None:
        return {'race_id': race_id, 'host': '', 'game_port': 0, 'status': 'NOT_PREPARED', 'ready': False, 'endpoint': ''}
    host = str(target.get('host') or _setting(conn, 'mx_public_server_host', '')).strip()
    port = int(target.get('game_port') or 0)
    state = str(target.get('status') or 'PREPARED').upper()
    endpoint = f'{host}:{port}' if host and port else ''
    target.update(host=host, game_port=port, status=state, endpoint=endpoint,
                  ready=bool(endpoint and state in READY_SESSION_STATES))
    return target


class MXGameBridge:
    def __init__(self, conn):
        self.conn = conn
        ensure_game_bridge_schema(conn)

    def bikes(self):
        return list_synced_bikes(self.conn)

    def selected_bike(self, race_id, rider_id):
        return selected_race_bike(self.conn, race_id, rider_id)

    def select_bike(self, race_id, rider_id, content_id, display_name):
        return save_race_bike(self.conn, race_id, rider_id, content_id, display_name)

    def game_exe(self):
        return find_mxbikes_exe(self.conn)

    def game_found(self):
        return self.game_exe() is not None

    def launch_game(self):
        exe = self.game_exe()
        if exe:
            subprocess.Popen([str(exe)], cwd=str(exe.parent))
            return {'mode': 'exe', 'path': str(exe)}
        steam = find_steam_exe()
        if steam:
            subprocess.Popen([str(steam), '-applaunch', STEAM_APP_ID], cwd=str(steam.parent))
            return {'mode': 'steam', 'path': str(steam)}
        raise GameBridgeError('MX Bikes was not found. Run the MX Bikes sync or set the game executable in Profile Settings.')

    def target(self, race_id):
        return race_launch_target(self.conn, race_id)

    def publish_target(self, race_id):
        return publish_race_target(self.conn, race_id)

    def launch_race(self, race_id, rider_id):
        reg = self.conn.execute('SELECT id FROM registrations WHERE race_id=? AND rider_id=?', (race_id, rider_id)).fetchone()
        if not reg:
            raise GameBridgeError('You are not registered for this race.')
        if _setting(self.conn, 'mx_require_selected_bike', 'true').lower() == 'true':
            if not self.selected_bike(race_id, rider_id):
                raise GameBridgeError('Select and save your race bike before joining the server.')
        target = self.target(race_id)
        if not target.get('ready'):
            if not target.get('host'):
                raise GameBridgeError('The race server address has not been published yet.')
            raise GameBridgeError('The race server is not open yet.')
        exe = self.game_exe()
        if not exe:
            raise GameBridgeError('MX Bikes was not found. Run game sync first.')
        endpoint = target['endpoint']
        subprocess.Popen([str(exe), DIRECT_CONNECT_FLAG, endpoint], cwd=str(exe.parent))
        return {'mode': 'directconnect', 'endpoint': endpoint, 'path': str(exe)}

    def status(self, race_id, rider_id=None):
        target = self.target(race_id)
        selected = self.selected_bike(race_id, rider_id) if rider_id is not None else None
        return {
            'game_found': self.game_found(),
            'bike_count': len(self.bikes()),
            'selected_bike': selected,
            'target': target,
            'ready': bool(target.get('ready')),
        }
