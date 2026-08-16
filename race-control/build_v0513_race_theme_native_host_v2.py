from pathlib import Path

base = Path('race-control/build_v0513_race_theme_native_host.py')
source = base.read_text(encoding='utf-8')
old = '''for route in ("show('UPCOMING')", "show('CHAMPIONSHIPS')", "show('GARAGE')", "show('LIVE')", "show('RESULTS')"):
    assert route in ui, 'gate:route:'+route
'''
new = '''for route_pair in (
    "('PROFILE', 'PROFILE'",
    "('FIND A RACE', 'UPCOMING'",
    "('CHAMPIONSHIPS', 'CHAMPIONSHIPS'",
    "('GARAGE', 'GARAGE'",
    "('LIVE', 'LIVE'",
    "('RESULTS', 'RESULTS'",
):
    assert route_pair in primary, 'gate:primary_route:'+route_pair
'''
if old not in source:
    raise SystemExit('v0.5.13 route gate patch anchor missing')
source = source.replace(old, new, 1)
exec(compile(source, str(base), 'exec'), {'__name__': '__main__'})
