from pathlib import Path
import hashlib, json, py_compile, re, shutil, tempfile, zipfile, urllib.request, urllib.parse

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_2_8_UPDATE.zip')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_2_9_UPDATE.zip')
NOTES = ('MXB Race Day Live v0.2.9: Find a Race artwork now uses verified MX Bikes Shop products only. '
         'The six seeded venues are explicitly matched to their real MX Bikes Shop track releases; '
         'all fuzzy/mirror fallback matching is disabled, stale track thumbnails are cleared, and '
         'the working live updater, error recovery, and automatic restart path are preserved.')

if not BASE.exists() or not zipfile.is_zipfile(BASE):
    raise SystemExit(f'Missing/invalid base update: {BASE}')

work = Path(tempfile.mkdtemp(prefix='mxb_v029_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)

# Publication-time verification. The shipped app contains no source guessing.
def fetch_image(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 MXB-Race-Day-Live-Build/0.2.9',
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
        'Cache-Control': 'no-cache',
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read(8 * 1024 * 1024)
            ctype = (r.headers.get('Content-Type') or '').lower()
            final = r.geturl()
        if len(data) < 10000 or not ctype.startswith('image/'):
            print('IMAGE VERIFY REJECT', url, ctype, len(data))
            return None
        return final, ctype, len(data)
    except Exception as exc:
        print('IMAGE VERIFY FAIL', url, repr(exc))
        return None

# Candidates come from the exact MX Bikes Shop-origin Millville artwork filename.
# Only a network-verified MX Bikes Shop asset is written into the app.
millville_candidates = [
    'https://cdn.mxbikes-shop.com/wp-content/uploads/2024/07/track_image_millville_1200x1200.jpg',
    'https://cdn.mxbikes-shop.com/wp-content/uploads/2024/07/track_image_millville_1200x1200-jpg.webp',
    'https://mxbikes-shop.com/wp-content/uploads/2024/07/track_image_millville_1200x1200.jpg',
]
millville_image = ''
for candidate in millville_candidates:
    result = fetch_image(candidate)
    if result:
        millville_image = result[0]
        print('MILLVILLE VERIFIED', *result)
        break
if not millville_image:
    raise SystemExit('Could not verify exact MX Bikes Shop Millville artwork; refusing to publish.')

known_images = [
    'https://cdn.mxbikes-shop.com/wp-content/uploads/2025/07/track_image-2.jpg',
    'https://cdn.mxbikes-shop.com/wp-content/uploads/2025/05/track_image-3.jpg',
    'https://cdn.mxbikes-shop.com/wp-content/uploads/2025/01/track_image.jpg',
    'https://cdn.mxbikes-shop.com/wp-content/uploads/2023/01/thumbnailfinal-copie-1.png',
]
for url in known_images:
    result = fetch_image(url)
    if not result:
        raise SystemExit('Pinned MX Bikes Shop artwork failed verification: ' + url)
    print('SHOP IMAGE VERIFIED', *result)

# Version markers.
cfg = work / 'src/config.py'
s = cfg.read_text(encoding='utf-8')
s = re.sub(r"VERSION\s*=\s*['\"][^'\"]+['\"]", "VERSION = '0.2.9'", s)
cfg.write_text(s, encoding='utf-8')
init = work / 'src/__init__.py'
init.write_text("__version__ = '0.2.9'\n", encoding='utf-8')

# Keep UPDATE button recoverable after any failed update (idempotent repair).
app_path = work / 'src/app.py'
app = app_path.read_text(encoding='utf-8')
old_err = "except Exception as e:self.after(0,lambda:(self.update_btn.configure(state='normal',text='UPDATE'),messagebox.showerror('Update Failed',str(e))))"
new_err = """except Exception as e:\n                msg=str(e)\n                def fail(msg=msg):\n                    self.update_btn.configure(state='normal',text='UPDATE')\n                    messagebox.showerror('Update Failed',msg)\n                self.after(0,fail)"""
if old_err in app:
    app = app.replace(old_err, new_err)
app_path.write_text(app, encoding='utf-8')

# Patch track-media resolution so Find a Race never guesses again.
tm_path = work / 'src/track_media.py'
tm = tm_path.read_text(encoding='utf-8')
tm = tm.replace('MXB-Race-Day-Live/0.2.8', 'MXB-Race-Day-Live/0.2.9')

# Remove every legacy/mirror search endpoint and fallback path from the shipped
# source, not just from the active resolver. MX Bikes Shop is the only source.
tm = re.sub(
    r"SHOP_SEARCH_ENDPOINTS\s*=\s*\(.*?\)\n",
    "SHOP_SEARCH_ENDPOINTS = ('https://mxbikes-shop.com/wp-json/wp/v2/search',)\n",
    tm, count=1, flags=re.S,
)

def _replace_method(text, name, body, next_name):
    start = text.index(f'    def {name}(')
    end = text.index(f'\n    def {next_name}(', start)
    return text[:start] + body.rstrip() + '\n' + text[end:]

# These methods are intentionally disabled. Exact seeded venue mappings below
# are the sole way Find a Race resolves artwork.
if '    def _search_candidates(' in tm and '    def _search_html_fallback(' in tm:
    tm = _replace_method(
        tm, '_search_candidates',
        '''    def _search_candidates(self, query: str):
        return []
''',
        '_search_html_fallback'
    )
if '    def _search_html_fallback(' in tm and '    def _find_source(' in tm:
    tm = _replace_method(
        tm, '_search_html_fallback',
        '''    def _search_html_fallback(self, query: str):
        return []
''',
        '_find_source'
    )

start = tm.index('DIRECT_TRACK_SOURCES = {')
end = tm.index('\nTRACK_MEDIA_CACHE_EPOCH', start)
verified_block = r'''DIRECT_TRACK_SOURCES = {
    ('MX', 'Millville Club'): ('2024 ARLMX RD7 – MILLVILLE', 'https://mxbikes-shop.com/downloads/2024-arlmx-rd7-millville/'),
    ('MX', 'Spring Creek'): ('2024 ARLMX RD7 – MILLVILLE', 'https://mxbikes-shop.com/downloads/2024-arlmx-rd7-millville/'),
    ('MX', 'RedBud Club'): ('2025 ARLMX RD6 – BUCHANAN', 'https://mxbikes-shop.com/downloads/2025-arlmx-rd6-buchanan/'),
    ('MX', 'RedBud'): ('2025 ARLMX RD6 – BUCHANAN', 'https://mxbikes-shop.com/downloads/2025-arlmx-rd6-buchanan/'),
    ('MX', 'Fox Raceway'): ('2025 ARLMX RD1 – PALA', 'https://mxbikes-shop.com/downloads/2025-arlmx-rd1-pala/'),
    ('MX', 'Pala Finale'): ('2025 ARLMX RD1 – PALA', 'https://mxbikes-shop.com/downloads/2025-arlmx-rd1-pala/'),
    ('SX', 'Anaheim Stadium'): ('2025 FXR ARL Supercross Series presented by MotoOption Rd 1', 'https://mxbikes-shop.com/downloads/2025-fxr-arl-supercross-series-presented-by-motooption-round-1/'),
    ('SX', 'Anaheim 1'): ('2025 FXR ARL Supercross Series presented by MotoOption Rd 1', 'https://mxbikes-shop.com/downloads/2025-fxr-arl-supercross-series-presented-by-motooption-round-1/'),
    ('SX', 'Anaheim'): ('2025 FXR ARL Supercross Series presented by MotoOption Rd 1', 'https://mxbikes-shop.com/downloads/2025-fxr-arl-supercross-series-presented-by-motooption-round-1/'),
    ('SX', 'San Diego Stadium'): ('2023 ARL SX ROUND 02 – SAN DIEGO', 'https://www.mxbikes-shop.com/downloads/2023-arl-sx-round-02-san-diego/'),
    ('SX', 'San Diego'): ('2023 ARL SX ROUND 02 – SAN DIEGO', 'https://www.mxbikes-shop.com/downloads/2023-arl-sx-round-02-san-diego/'),
}

DIRECT_TRACK_IMAGES = {
    ('MX', 'Millville Club'): '__MILLVILLE_IMAGE__',
    ('MX', 'Spring Creek'): '__MILLVILLE_IMAGE__',
    ('MX', 'RedBud Club'): 'https://cdn.mxbikes-shop.com/wp-content/uploads/2025/07/track_image-2.jpg',
    ('MX', 'RedBud'): 'https://cdn.mxbikes-shop.com/wp-content/uploads/2025/07/track_image-2.jpg',
    ('MX', 'Fox Raceway'): 'https://cdn.mxbikes-shop.com/wp-content/uploads/2025/05/track_image-3.jpg',
    ('MX', 'Pala Finale'): 'https://cdn.mxbikes-shop.com/wp-content/uploads/2025/05/track_image-3.jpg',
    ('SX', 'Anaheim Stadium'): 'https://cdn.mxbikes-shop.com/wp-content/uploads/2025/01/track_image.jpg',
    ('SX', 'Anaheim 1'): 'https://cdn.mxbikes-shop.com/wp-content/uploads/2025/01/track_image.jpg',
    ('SX', 'Anaheim'): 'https://cdn.mxbikes-shop.com/wp-content/uploads/2025/01/track_image.jpg',
    ('SX', 'San Diego Stadium'): 'https://cdn.mxbikes-shop.com/wp-content/uploads/2023/01/thumbnailfinal-copie-1.png',
    ('SX', 'San Diego'): 'https://cdn.mxbikes-shop.com/wp-content/uploads/2023/01/thumbnailfinal-copie-1.png',
}

VERIFIED_SHOP_HOSTS = {'mxbikes-shop.com', 'www.mxbikes-shop.com'}
VERIFIED_IMAGE_HOSTS = VERIFIED_SHOP_HOSTS | {'cdn.mxbikes-shop.com'}
'''
tm = tm[:start] + verified_block + tm[end:]
tm = tm.replace('__MILLVILLE_IMAGE__', millville_image)
tm = re.sub(r"TRACK_MEDIA_CACHE_EPOCH\s*=\s*['\"][^'\"]+['\"]", "TRACK_MEDIA_CACHE_EPOCH = 'v029-mxb-shop-pinned-images-only'", tm)

# Remove mirror/search guessing entirely. Unmapped tracks show the placeholder.
method_start = tm.index('    def _find_source(self, discipline: str, track: str):')
method_end = tm.index('\n    def _download_image', method_start)
method = '''    def _find_source(self, discipline: str, track: str):\n        direct = DIRECT_TRACK_SOURCES.get((discipline.upper(), track))\n        return direct if direct else ('', '')\n'''
tm = tm[:method_start] + method + tm[method_end:]

# Add strict helpers: only shop-hosted image URLs are accepted.
insert_at = tm.index('\n\nclass TrackMediaResolver:')
helpers = r'''


def _shop_host(url: str):
    try:
        return (urllib.parse.urlparse(url).hostname or '').lower()
    except Exception:
        return ''


def _normal_title(text: str):
    text = html.unescape(text or '').lower().replace('–', '-').replace('—', '-')
    return ' '.join(re.findall(r'[a-z0-9]+', text))


def _extract_page_title(page_html: str):
    pats = [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        r'<h1[^>]*>(.*?)</h1>',
        r'<title[^>]*>(.*?)</title>',
    ]
    for pat in pats:
        m = re.search(pat, page_html, re.I | re.S)
        if m:
            value = re.sub(r'<[^>]+>', ' ', m.group(1))
            value = html.unescape(re.sub(r'\s+', ' ', value)).strip()
            value = re.sub(r'\s*[-|–]\s*MX Bikes Shop\s*$', '', value, flags=re.I).strip()
            if value:
                return value
    return ''


def _verified_source(expected_title: str, source_url: str, page_html: str):
    if _shop_host(source_url) not in VERIFIED_SHOP_HOSTS:
        return False
    actual = _extract_page_title(page_html)
    a, e = _normal_title(actual), _normal_title(expected_title)
    return bool(a and e and (a == e or a.startswith(e + ' ') or e.startswith(a + ' ')))


def _verified_image(url: str):
    return bool(url and _shop_host(url) in VERIFIED_IMAGE_HOSTS and 'wp-content/uploads/' in url)
'''
tm = tm[:insert_at] + helpers + tm[insert_at:]

# Replace runtime page scraping with direct pinned artwork only.
old = """                    with _request(source, timeout=15) as r:\n                        page = r.read(3 * 1024 * 1024).decode('utf-8', errors='replace')\n                    image_url = _extract_meta_image(page)\n                    local = self._download_image(image_url, discipline, track) if image_url else ''"""
new = """                    image_url = DIRECT_TRACK_IMAGES.get((discipline, track), '')
                    if not _verified_image(image_url):
                        media.status = 'NOT_FOUND'; media.resolved_at = _now(); self._save(media); return media
                    local = self._download_image(image_url, discipline, track)"""
if old not in tm:
    raise SystemExit('Could not locate resolve image block in base track_media.py')
tm = tm.replace(old, new, 1)

tm_path.write_text(tm, encoding='utf-8')

required = ['app.py','src/app.py','src/config.py','src/updater.py','src/track_media.py','src/__init__.py','Start MXB Race Day Live.vbs']
for rel in required:
    if not (work / rel).exists():
        raise SystemExit(f'Final update missing {rel}')

# Regression gates: update system + restart must survive every feature release.
up = (work / 'src/updater.py').read_text(encoding='utf-8')
app = (work / 'src/app.py').read_text(encoding='utf-8')
tm = tm_path.read_text(encoding='utf-8')
assert '_manifest_from_github_api' in up
assert 'schedule_restart' in up
assert 'def do_update' in app and 'launch_update(z)' in app
assert 'def fail(msg=msg)' in app and "state='normal'" in app
assert 'mxb-mods.com' not in tm and 'mymxb.com' not in tm
assert "return direct if direct else ('', '')" in tm
assert 'v029-mxb-shop-pinned-images-only' in tm
assert '__MILLVILLE_IMAGE__' not in tm
assert "DIRECT_TRACK_IMAGES.get((discipline, track), '')" in tm
assert "page = r.read(3 * 1024 * 1024)" not in tm
for venue in ('Millville Club','RedBud Club','Fox Raceway','Anaheim Stadium','Spring Creek','San Diego Stadium'):
    assert venue in tm
for rel in ('app.py','src/app.py','src/config.py','src/updater.py','src/track_media.py'):
    py_compile.compile(str(work / rel), doraise=True)

OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(work.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            z.write(p, p.relative_to(work).as_posix())
with zipfile.ZipFile(OUT) as z:
    names = set(z.namelist())
    missing = [x for x in required if x not in names]
    if missing:
        raise SystemExit('Built ZIP incomplete: ' + ', '.join(missing))

digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
manifest = {
    'version': '0.2.9',
    'url': 'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_2_9_UPDATE.zip',
    'sha256': digest,
    'notes': NOTES,
}
Path('race-control/latest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print('Built', OUT, digest)
