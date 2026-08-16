from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path


class MXExtensionError(RuntimeError):
    pass


def _now():
    return datetime.now().replace(microsecond=0).isoformat()


def _row_id(conn, username):
    row=conn.execute('SELECT id FROM riders WHERE username=?',(username,)).fetchone()
    return int(row['id']) if row else None


def ensure_extension_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS game_profile_state (
        rider_id INTEGER PRIMARY KEY,
        profile_name TEXT,
        profile_ini TEXT,
        mods_root TEXT,
        selection_json TEXT NOT NULL DEFAULT '{}',
        selection_hash TEXT NOT NULL DEFAULT '',
        synced_at TEXT NOT NULL,
        FOREIGN KEY(rider_id) REFERENCES riders(id)
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS race_loadouts (
        race_id INTEGER NOT NULL,
        rider_id INTEGER NOT NULL,
        selection_json TEXT NOT NULL,
        selection_hash TEXT NOT NULL,
        bike_id TEXT,
        bike_paint TEXT,
        captured_at TEXT NOT NULL,
        PRIMARY KEY(race_id,rider_id),
        FOREIGN KEY(race_id) REFERENCES races(id),
        FOREIGN KEY(rider_id) REFERENCES riders(id)
    )''')
    conn.commit()


class MXExtensionService:
    """Low-overhead two-way bridge between Race Day Live and MX Bikes' real profile/content state.

    The worker thread only stats already-resolved paths. All SQLite and profile reads/writes
    remain on the Tk/main thread, so the bridge does not violate SQLite/Tk thread affinity.
    """

    def __init__(self,conn,garage,game_bridge,username=''):
        self.conn=conn
        self.garage=garage
        self.game_bridge=game_bridge
        self.username=username
        ensure_extension_schema(conn)
        self._stop=threading.Event()
        self._thread=None
        self._paths_lock=threading.Lock()
        self._watch_paths={}
        self._fingerprints={}
        self._events=deque(maxlen=64)
        self._events_lock=threading.Lock()
        self.refresh_watch_paths()

    def rider_id(self):
        return _row_id(self.conn,self.username)

    def refresh_watch_paths(self):
        paths={}
        try:
            p=self.garage.profile_ini()
            if p:paths['profile']=Path(p)
        except Exception:pass
        try:paths['global']=Path(self.garage.global_ini())
        except Exception:pass
        try:
            mods=Path(self.garage.mods_root())
            paths['mods']=mods
            paths['bikes']=mods/'bikes'
            paths['rider']=mods/'rider'
        except Exception:pass
        with self._paths_lock:
            self._watch_paths=paths
            self._fingerprints={k:self._stat_sig(p) for k,p in paths.items()}
        return {k:str(v) for k,v in paths.items()}

    @staticmethod
    def _stat_sig(path):
        try:
            st=Path(path).stat()
            return (int(st.st_mtime_ns),int(st.st_size),bool(Path(path).is_dir()))
        except Exception:
            return (0,0,False)

    def start(self):
        if self._thread and self._thread.is_alive():return
        self._stop.clear()
        self._thread=threading.Thread(target=self._watch_loop,name='RDL-MXB-Extension',daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _push(self,kind,path=''):
        with self._events_lock:
            if any(e.get('kind')==kind for e in self._events):return
            self._events.append({'kind':kind,'path':str(path),'at':time.time()})

    def _watch_loop(self):
        while not self._stop.wait(1.0):
            with self._paths_lock:
                paths=dict(self._watch_paths); old=dict(self._fingerprints)
            changed={}
            for key,path in paths.items():
                sig=self._stat_sig(path)
                if sig!=old.get(key):changed[key]=sig
            if not changed:continue
            with self._paths_lock:self._fingerprints.update(changed)
            if 'profile' in changed:self._push('profile',paths.get('profile',''))
            if any(k in changed for k in ('global','mods','bikes','rider')):
                self._push('content',paths.get('mods',''))

    def drain_events(self):
        with self._events_lock:
            out=list(self._events); self._events.clear()
        return out

    def sync_profile_state(self,force=False):
        rider_id=self.rider_id()
        if rider_id is None:return {'changed':False,'selection':{},'reason':'no rider'}
        selection=self.garage.read_selection()
        payload=json.dumps(selection,sort_keys=True,separators=(',',':'))
        digest=hashlib.sha256(payload.encode('utf-8')).hexdigest()
        row=self.conn.execute('SELECT selection_hash FROM game_profile_state WHERE rider_id=?',(rider_id,)).fetchone()
        changed=force or not row or str(row['selection_hash'] or '')!=digest
        if changed:
            profile=self.garage.profile_ini()
            self.conn.execute('''INSERT INTO game_profile_state(rider_id,profile_name,profile_ini,mods_root,selection_json,selection_hash,synced_at)
                                 VALUES(?,?,?,?,?,?,?)
                                 ON CONFLICT(rider_id) DO UPDATE SET profile_name=excluded.profile_name,
                                 profile_ini=excluded.profile_ini,mods_root=excluded.mods_root,selection_json=excluded.selection_json,
                                 selection_hash=excluded.selection_hash,synced_at=excluded.synced_at''',
                              (rider_id,self.garage.profile_name(),str(profile or ''),str(self.garage.mods_root()),payload,digest,_now()))
            bike=str(selection.get('bikeid') or '')
            try:self.conn.execute('UPDATE riders SET game_bike_id=?,bike_model=? WHERE id=?',(bike,self.garage.bike_display(bike),rider_id))
            except Exception:pass
            self.conn.commit()
        return {'changed':changed,'selection':selection,'hash':digest}

    def content_changed(self):
        self.garage.invalidate_cache()
        try:self.game_bridge.invalidate_cache()
        except Exception:pass
        self.refresh_watch_paths()

    def mirror_selection(self,selection):
        self.garage.apply_selection(selection)
        return self.sync_profile_state(force=True)

    def capture_race_loadout(self,race_id,rider_id,bike_override=None,bike_display=None):
        selection=self.garage.read_selection()
        if bike_override:
            selection['bikeid']=str(bike_override)
        payload=json.dumps(selection,sort_keys=True,separators=(',',':'))
        digest=hashlib.sha256(payload.encode('utf-8')).hexdigest()
        self.conn.execute('''INSERT INTO race_loadouts(race_id,rider_id,selection_json,selection_hash,bike_id,bike_paint,captured_at)
                             VALUES(?,?,?,?,?,?,?)
                             ON CONFLICT(race_id,rider_id) DO UPDATE SET selection_json=excluded.selection_json,
                             selection_hash=excluded.selection_hash,bike_id=excluded.bike_id,bike_paint=excluded.bike_paint,captured_at=excluded.captured_at''',
                          (int(race_id),int(rider_id),payload,digest,str(selection.get('bikeid') or ''),str(selection.get('paint') or ''),_now()))
        self.conn.commit()
        if selection.get('bikeid'):
            self.game_bridge.select_bike(race_id,rider_id,selection['bikeid'],bike_display or self.garage.bike_display(selection['bikeid']))
        return selection

    def race_loadout(self,race_id,rider_id):
        row=self.conn.execute('SELECT selection_json FROM race_loadouts WHERE race_id=? AND rider_id=?',(int(race_id),int(rider_id))).fetchone()
        if not row:return None
        try:return json.loads(row['selection_json'])
        except Exception:return None

    def prepare_join(self,race_id,rider_id):
        selection=self.race_loadout(race_id,rider_id)
        if selection is None:
            selection=self.capture_race_loadout(race_id,rider_id)
        # Apply the complete saved bike + paint + rider kit to the native MX Bikes profile
        # immediately before direct-connect so the game launches with the Race Day loadout.
        self.garage.apply_selection(selection)
        self.sync_profile_state(force=True)
        return selection

    def status(self):
        rider_id=self.rider_id()
        row=self.conn.execute('SELECT * FROM game_profile_state WHERE rider_id=?',(rider_id,)).fetchone() if rider_id else None
        return {
            'linked':bool(self.garage.profile_ini()),
            'profile':self.garage.profile_name(),
            'profile_ini':str(self.garage.profile_ini() or ''),
            'mods_root':str(self.garage.mods_root()),
            'synced_at':str(row['synced_at'] if row else ''),
        }
