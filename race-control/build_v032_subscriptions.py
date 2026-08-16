from pathlib import Path
import hashlib, json, py_compile, re, shutil, sqlite3, tempfile, zipfile

BASE = Path('race-control/releases/MXB_Race_Day_Live_v0_3_1_UPDATE.zip')
SUBS = Path('race-control/subscriptions_v032.py')
OUT = Path('race-control/releases/MXB_Race_Day_Live_v0_3_2_UPDATE.zip')
NOTES = ('MXB Race Day Live v0.3.2: adds automated rider memberships with Pit Pass, Race Pass and Factory Pass tiers, '
         'daily discounted Community-race allowances, automatic member wallet rebates, subscription status/usage tracking, '
         'and provider-ready recurring billing fields. Cash/Premier pricing, the $3 Community purse/fast-lap economics, verified '
         'MX Bikes Shop artwork, in-app updates and automatic restart are preserved.')

if not BASE.exists() or not zipfile.is_zipfile(BASE):
    raise SystemExit('Published v0.3.1 base is missing or invalid')
if not SUBS.exists():
    raise SystemExit('Subscription engine source is missing')

work = Path(tempfile.mkdtemp(prefix='mxb_v032_'))
with zipfile.ZipFile(BASE) as z:
    z.extractall(work)
shutil.copy2(SUBS, work/'src/subscriptions.py')

# Version markers.
p = work/'src/config.py'
s = p.read_text(encoding='utf-8')
s = re.sub(r"VERSION\s*=\s*['\"][^'\"]+['\"]", "VERSION = '0.3.2'", s)
p.write_text(s, encoding='utf-8')

p = work/'src/__init__.py'
s = p.read_text(encoding='utf-8') if p.exists() else ''
s = re.sub(r"__version__\s*=\s*['\"][^'\"]+['\"]", "__version__ = '0.3.2'", s) if '__version__' in s else s + "\n__version__ = '0.3.2'\n"
p.write_text(s, encoding='utf-8')

p = work/'src/updater.py'
s = p.read_text(encoding='utf-8')
s = re.sub(r'MXB-Race-Day-Live-Updater/[0-9.]+', 'MXB-Race-Day-Live-Updater/0.3.2', s)
p.write_text(s, encoding='utf-8')

# Patch rider UI and signup flow.
p = work/'src/app.py'
app = p.read_text(encoding='utf-8')

pricing_import = 'from .pricing import apply_low_entry_pricing\n'
sub_import = ('from .subscriptions import (PLANS, ensure_subscription_schema, get_subscription, usage_today, member_quote,\n'
              '                            record_member_use, activate_demo_subscription, cancel_auto_renew,\n'
              '                            admin_membership_metrics)\n')
if sub_import not in app:
    if pricing_import not in app:
        raise SystemExit('Could not locate subscription import anchor')
    app = app.replace(pricing_import, pricing_import + sub_import, 1)

old_start = "super().__init__(); seed(); self.conn=connect(); apply_low_entry_pricing(self.conn); self.settings=load_settings(); self.current_rider='Welchy'"
new_start = "super().__init__(); seed(); self.conn=connect(); apply_low_entry_pricing(self.conn); ensure_subscription_schema(self.conn); self.settings=load_settings(); self.current_rider='Welchy'"
if old_start in app:
    app = app.replace(old_start, new_start, 1)
elif new_start not in app:
    raise SystemExit('Could not locate startup subscription hook')

old_nav = "for label,key in [('OVERVIEW','OVERVIEW'),('MY RACES','RACES'),('WALLET','WALLET'),('PROFILE SETTINGS','SETTINGS')]:"
new_nav = "for label,key in [('OVERVIEW','OVERVIEW'),('MY RACES','RACES'),('WALLET','WALLET'),('MEMBERSHIP','MEMBERSHIP'),('PROFILE SETTINGS','SETTINGS')]:"
if old_nav in app:
    app = app.replace(old_nav, new_nav, 1)
elif new_nav not in app:
    raise SystemExit('Could not locate profile subnav')

old_route = "if self.profile_section=='WALLET': return self._profile_wallet(r)\n        if self.profile_section=='SETTINGS': return self._profile_settings(r)"
new_route = "if self.profile_section=='WALLET': return self._profile_wallet(r)\n        if self.profile_section=='MEMBERSHIP': return self._profile_membership(r)\n        if self.profile_section=='SETTINGS': return self._profile_settings(r)"
if old_route in app:
    app = app.replace(old_route, new_route, 1)
elif new_route not in app:
    raise SystemExit('Could not locate profile membership route')

membership_page = r'''
    def _profile_membership(self,r):
        body=self._scrollable(self.content,pady=(0,24))
        sub=get_subscription(self.conn,r['id']); used=usage_today(self.conn,r['id'])
        tk.Label(body,text='RACE MEMBERSHIP',fg=TEXT,bg=BG,font=('Segoe UI Black',20)).pack(anchor='w',pady=(4,2))
        tk.Label(body,text='Save on Community races with automatic daily limits. Cash and Premier events always keep their normal entry price.',fg=MUTED,bg=BG,font=('Segoe UI',10),wraplength=1050,justify='left').pack(anchor='w',pady=(0,12))
        status=self.card(body); status.pack(fill='x',pady=(0,12))
        if sub and sub.get('active') and sub.get('plan'):
            plan=sub['plan']; remaining=max(0,int(plan['daily_races'])-used)
            tk.Label(status,text=f"{plan['name'].upper()} • ACTIVE",fg=GREEN,bg=PANEL,font=('Segoe UI Black',14)).pack(anchor='w',padx=16,pady=(14,3))
            tk.Label(status,text=f"${plan['monthly_price']:.2f}/month  •  Community ${plan['community_price']:.2f}  •  {remaining}/{plan['daily_races']} member-priced races remaining today",fg=TEXT,bg=PANEL,font=('Segoe UI Semibold',10)).pack(anchor='w',padx=16,pady=(0,4))
            try: renewal=datetime.fromisoformat(sub['current_period_end']).strftime('%b %d, %Y')
            except Exception: renewal=sub.get('current_period_end','—')
            renew='AUTO-RENEW ON' if int(sub.get('auto_renew') or 0) else 'AUTO-RENEW OFF'
            tk.Label(status,text=f"{renew}  •  Current period through {renewal}  •  Provider: {sub.get('provider') or 'NOT CONNECTED'}",fg=MUTED,bg=PANEL,font=('Segoe UI',9)).pack(anchor='w',padx=16,pady=(0,10))
            if int(sub.get('auto_renew') or 0):
                tk.Button(status,text='TURN OFF AUTO-RENEW',command=lambda:self._cancel_membership_renewal(r['id']),bg=PANEL2,fg=TEXT,relief='flat',font=('Segoe UI Semibold',9),padx=12,pady=8,cursor='hand2').pack(anchor='w',padx=16,pady=(0,14))
        else:
            tk.Label(status,text='NO ACTIVE MEMBERSHIP',fg=MUTED,bg=PANEL,font=('Segoe UI Black',13)).pack(anchor='w',padx=16,pady=(14,3))
            tk.Label(status,text='Pick a plan below. Membership discounts are enforced automatically at race signup.',fg=MUTED,bg=PANEL,font=('Segoe UI',9)).pack(anchor='w',padx=16,pady=(0,14))

        plans=tk.Frame(body,bg=BG); plans.pack(fill='x')
        for key in ('PIT','RACE','FACTORY'):
            plan=PLANS[key]
            card=self.card(plans); card.pack(side='left',fill='both',expand=True,padx=(0,8) if key!='FACTORY' else 0)
            tk.Label(card,text=plan['name'].upper(),fg=ACCENT if key!='FACTORY' else GOLD,bg=PANEL,font=('Segoe UI Black',14)).pack(anchor='w',padx=16,pady=(15,2))
            tk.Label(card,text=f"${plan['monthly_price']:.2f} / MONTH",fg=TEXT,bg=PANEL,font=('Segoe UI Black',20)).pack(anchor='w',padx=16)
            tk.Label(card,text=f"{plan['daily_races']} discounted Community race{'s' if plan['daily_races']!=1 else ''} per day",fg=TEXT,bg=PANEL,font=('Segoe UI Semibold',9)).pack(anchor='w',padx=16,pady=(8,2))
            tk.Label(card,text=f"Member Community entry: ${plan['community_price']:.2f}",fg=GREEN,bg=PANEL,font=('Segoe UI Black',10)).pack(anchor='w',padx=16,pady=2)
            tk.Label(card,text='After the daily allowance: normal $3 Community price. Cash/Premier: normal price.',fg=MUTED,bg=PANEL,font=('Segoe UI',8),wraplength=290,justify='left').pack(anchor='w',padx=16,pady=(2,10))
            active=bool(sub and sub.get('active') and sub.get('plan_key')==key)
            label='CURRENT PLAN' if active else ('SWITCH TO '+plan['name'].upper() if sub and sub.get('active') else 'ACTIVATE DEMO '+plan['name'].upper())
            tk.Button(card,text=label,state='disabled' if active else 'normal',command=lambda k=key:self._activate_membership_demo(r['id'],k),bg=GREEN if active else ACCENT,fg='white',relief='flat',font=('Segoe UI Black',9),pady=9,cursor='hand2').pack(fill='x',padx=14,pady=(2,14))

        note=self.card(body); note.pack(fill='x',pady=(12,0))
        tk.Label(note,text='AUTOMATION STATUS',fg=ACCENT,bg=PANEL,font=('Segoe UI Black',11)).pack(anchor='w',padx=16,pady=(14,5))
        tk.Label(note,text='Daily member limits, member pricing, wallet rebates, plan status, usage tracking and renewal periods are automatic. The app wallet and membership billing are still in DEMO MODE until a real recurring-payment provider is connected; production billing will use the provider fields already built into this system.',fg=MUTED,bg=PANEL,font=('Segoe UI',9),wraplength=1040,justify='left').pack(anchor='w',padx=16,pady=(0,14))

    def _activate_membership_demo(self,rider_id,plan_key):
        plan=PLANS[plan_key]
        if not messagebox.askyesno('Membership Demo',f"Activate {plan['name']} in DEMO billing mode?\n\nProduction recurring billing is not connected yet."):
            return
        activate_demo_subscription(self.conn,rider_id,plan_key)
        messagebox.showinfo('Membership',f"{plan['name']} is active in DEMO mode. Daily member pricing is now enforced automatically.")
        self._set_profile_section('MEMBERSHIP')

    def _cancel_membership_renewal(self,rider_id):
        cancel_auto_renew(self.conn,rider_id)
        messagebox.showinfo('Membership','Auto-renew is off. Membership remains active through the current period.')
        self._set_profile_section('MEMBERSHIP')

'''
marker = '    def _profile_settings(self,r):\n'
if '    def _profile_membership(self,r):\n' not in app:
    if marker not in app:
        raise SystemExit('Could not locate membership page insertion point')
    app = app.replace(marker, membership_page + marker, 1)

# Find a Race cards: show member price when today's allowance is available.
old_card = "            tk.Label(top,text=f\"${race['entry_fee']:.2f}\",fg=GOLD,bg=PANEL,font=('Segoe UI Black',14)).pack(side='right')"
new_card = "            quote=member_quote(self.conn,rider['id'],race); price_text=(f\"${quote['member_price']:.2f} MEMBER\" if quote['eligible'] else f\"${race['entry_fee']:.2f}\")\n            tk.Label(top,text=price_text,fg=GREEN if quote['eligible'] else GOLD,bg=PANEL,font=('Segoe UI Black',14)).pack(side='right')"
if old_card in app:
    app = app.replace(old_card, new_card, 1)
elif 'price_text=(f"${quote[\'member_price\']:.2f} MEMBER"' not in app:
    raise SystemExit('Could not locate Find a Race member-price label')

# Race detail action button uses member price when available.
old_btn = "        already=self.conn.execute('SELECT 1 FROM registrations WHERE race_id=? AND rider_id=?',(race['id'],rider['id'])).fetchone()\n        if already:text,state,color='✓ YOU ARE REGISTERED','disabled',GREEN\n        elif ok:text,state,color=f\"ENTER RACE • ${race['entry_fee']:.2f}\",'normal',ACCENT"
new_btn = "        quote=member_quote(self.conn,rider['id'],race)\n        already=self.conn.execute('SELECT 1 FROM registrations WHERE race_id=? AND rider_id=?',(race['id'],rider['id'])).fetchone()\n        if already:text,state,color='✓ YOU ARE REGISTERED','disabled',GREEN\n        elif ok and quote['eligible']:text,state,color=f\"ENTER RACE • MEMBER ${quote['member_price']:.2f}\",'normal',GREEN\n        elif ok:text,state,color=f\"ENTER RACE • ${race['entry_fee']:.2f}\",'normal',ACCENT"
if old_btn in app:
    app = app.replace(old_btn, new_btn, 1)
elif "MEMBER ${quote['member_price']:.2f}" not in app:
    raise SystemExit('Could not locate race-details member button')

# Signup dialog calculates member quote before showing the wallet/entry summary.
old_signup = "        bal=wallet_balance(self.conn,rider['id']); paid,purse=current_purse(self.conn,race['id']); fast=fastest_lap_pool(self.conn,race['id'])\n        dlg=tk.Toplevel(self);"
new_signup = "        quote=member_quote(self.conn,rider['id'],race); member_entry=quote['member_price'] if quote['eligible'] else float(race['entry_fee'])\n        bal=wallet_balance(self.conn,rider['id']); paid,purse=current_purse(self.conn,race['id']); fast=fastest_lap_pool(self.conn,race['id'])\n        dlg=tk.Toplevel(self);"
if old_signup in app:
    app = app.replace(old_signup, new_signup, 1)
elif "member_entry=quote['member_price']" not in app:
    raise SystemExit('Could not locate signup member quote hook')

old_summary = "        for lab,val,col in [('WALLET',f'${bal:,.2f}',TEXT),('ENTRY',f\"${race['entry_fee']:.2f}\",GOLD),('CURRENT PURSE',f'${purse:,.2f}',GOLD),('FASTEST LAP',f'${fast:,.2f}',GREEN)]:"
new_summary = "        for lab,val,col in [('WALLET',f'${bal:,.2f}',TEXT),('ENTRY',f\"${member_entry:.2f}\",GREEN if quote['eligible'] else GOLD),('CURRENT PURSE',f'${purse:,.2f}',GOLD),('FASTEST LAP',f'${fast:,.2f}',GREEN)]:"
if old_summary in app:
    app = app.replace(old_summary, new_summary, 1)
elif "('${member_entry:.2f}'" in app:
    pass

# Explain full wallet authorization + instant rebate in the current wallet architecture.
old_policy = "        tk.Label(dlg,text='ALL SALES ARE FINAL — NO REFUNDS. The final purse and fastest-lap bonus will be shown and locked before racing begins.',fg=GOLD,bg=PANEL,justify='left',font=('Segoe UI Semibold',9),padx=12,pady=12,wraplength=480).pack(fill='x',padx=24)"
new_policy = "        if quote['eligible']:\n            tk.Label(dlg,text=f\"{quote['plan']['name'].upper()} MEMBER PRICE • SAVE ${quote['discount']:.2f} • {quote['remaining_today']} MEMBER-PRICED RACE(S) REMAIN TODAY AFTER THIS ENTRY. The wallet registers the normal race amount first, then returns your member savings instantly so purse funding stays exact.\",fg=GREEN,bg=PANEL,justify='left',font=('Segoe UI Semibold',9),padx=12,pady=12,wraplength=480).pack(fill='x',padx=24,pady=(0,8))\n        tk.Label(dlg,text='ALL SALES ARE FINAL — NO REFUNDS. The final purse and fastest-lap bonus will be shown and locked before racing begins.',fg=GOLD,bg=PANEL,justify='left',font=('Segoe UI Semibold',9),padx=12,pady=12,wraplength=480).pack(fill='x',padx=24)"
if old_policy in app:
    app = app.replace(old_policy, new_policy, 1)
elif 'MEMBER PRICE • SAVE' not in app:
    raise SystemExit('Could not locate signup membership explanation')

# Confirm button: preserve the existing full registration, then return member savings and record usage.
old_confirm = """        def confirm():
            try:newbal=register_with_wallet(self.conn,rider['id'],race['id'],ack.get())
            except ValueError as exc:messagebox.showerror('Race Entry',str(exc),parent=dlg); return
            now=datetime.now().replace(microsecond=0).isoformat()
            self.conn.execute('INSERT INTO payment_transactions(rider_id,race_id,provider,provider_ref,amount,status,created_at) VALUES(?,?,?,?,?,?,?)',(rider['id'],race['id'],'RACE_WALLET',None,race['entry_fee'],'PAID',now)); self.conn.commit()
            dlg.destroy(); messagebox.showinfo('Gate Reserved',f"You are officially registered.\nWallet remaining: ${newbal:,.2f}"); self.open_race_details(race['id'])
        tk.Button(dlg,text=f"CONFIRM ENTRY • ${race['entry_fee']:.2f}",command=confirm,bg=ACCENT,fg='white',relief='flat',font=('Segoe UI Black',11),pady=10,cursor='hand2').pack(fill='x',padx=24)
"""
new_confirm = """        def confirm():
            try:
                newbal=register_with_wallet(self.conn,rider['id'],race['id'],ack.get())
                if quote['eligible'] and quote['discount']>0:
                    wallet_credit(self.conn,rider['id'],quote['discount'],kind='SUBSCRIPTION_REBATE',provider='MEMBERSHIP',note=f"{quote['plan']['name']} Community race savings")
                    record_member_use(self.conn,rider['id'],race['id'],quote)
                    newbal=wallet_balance(self.conn,rider['id'])
            except ValueError as exc:messagebox.showerror('Race Entry',str(exc),parent=dlg); return
            except Exception as exc:messagebox.showerror('Membership','Race registered, but the membership rebate could not be completed: '+str(exc),parent=dlg); return
            now=datetime.now().replace(microsecond=0).isoformat()
            self.conn.execute('INSERT INTO payment_transactions(rider_id,race_id,provider,provider_ref,amount,status,created_at) VALUES(?,?,?,?,?,?,?)',(rider['id'],race['id'],'RACE_WALLET',None,race['entry_fee'],'PAID',now)); self.conn.commit()
            dlg.destroy(); messagebox.showinfo('Gate Reserved',f"You are officially registered.\nWallet remaining: ${newbal:,.2f}"); self.open_race_details(race['id'])
        confirm_text=f"CONFIRM MEMBER ENTRY • ${member_entry:.2f}" if quote['eligible'] else f"CONFIRM ENTRY • ${race['entry_fee']:.2f}"
        tk.Button(dlg,text=confirm_text,command=confirm,bg=GREEN if quote['eligible'] else ACCENT,fg='white',relief='flat',font=('Segoe UI Black',11),pady=10,cursor='hand2').pack(fill='x',padx=24)
"""
if old_confirm in app:
    app = app.replace(old_confirm, new_confirm, 1)
elif 'SUBSCRIPTION_REBATE' not in app:
    raise SystemExit('Could not locate signup transaction block')

p.write_text(app, encoding='utf-8')

required = ['app.py','src/app.py','src/config.py','src/updater.py','src/pricing.py','src/track_media.py','src/subscriptions.py','src/__init__.py','Start MXB Race Day Live.vbs']
for rel in required:
    if not (work/rel).exists():
        raise SystemExit('Final update missing '+rel)

# Regression gates for every system the user has already validated.
up = (work/'src/updater.py').read_text(encoding='utf-8')
tm = (work/'src/track_media.py').read_text(encoding='utf-8')
pr = (work/'src/pricing.py').read_text(encoding='utf-8')
app = (work/'src/app.py').read_text(encoding='utf-8')
subs = (work/'src/subscriptions.py').read_text(encoding='utf-8')
for marker in ('_manifest_from_github_api','schedule_restart'):
    if marker not in up: raise SystemExit('Updater regression: '+marker)
for marker in ('DIRECT_TRACK_IMAGES','v029-mxb-shop-pinned-images-only','mxbikes-shop.com'):
    if marker not in tm: raise SystemExit('Track-art regression: '+marker)
for marker in ('COMMUNITY_LOW_ENTRY_FEE = 3.00','COMMUNITY_MAIN_PER_RIDER = 1.00','COMMUNITY_FAST_LAP_PER_RIDER = 0.25','COMMUNITY_PLATFORM_PER_RIDER = 1.75'):
    if marker not in pr: raise SystemExit('Community economics regression: '+marker)
for marker in ("display_riders=max(paid,int(race['min_riders']))", "purse_text=f'${display_purse:,.0f}{grow}'", "fast_text=f'${display_fast:,.0f}{grow}'"):
    if marker not in app: raise SystemExit('Community purse display regression: '+marker)
for marker in ('Pit Pass','Race Pass','Factory Pass','membership_subscriptions','membership_usage','member_quote','record_member_use'):
    if marker not in subs: raise SystemExit('Subscription engine regression: '+marker)
for marker in ("('MEMBERSHIP','MEMBERSHIP')", 'def _profile_membership', 'SUBSCRIPTION_REBATE', 'ensure_subscription_schema(self.conn)', "MEMBER ${quote['member_price']:.2f}"):
    if marker not in app: raise SystemExit('Subscription UI/transaction regression: '+marker)

for rel in ('app.py','src/app.py','src/config.py','src/updater.py','src/pricing.py','src/track_media.py','src/subscriptions.py'):
    py_compile.compile(str(work/rel), doraise=True)

# Functional membership economics / daily-limit tests using an isolated database.
conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row
ns={}; exec(compile(subs,'subscriptions.py','exec'),ns)
ns['ensure_subscription_schema'](conn)
race={'id':1,'entry_fee':3.0,'lobby_tier':'Low Entry','prize_contribution':1.0,'fast_lap_contribution':0.25}
cash={'id':2,'entry_fee':25.0,'lobby_tier':'Cash','prize_contribution':10.0,'fast_lap_contribution':2.0}
for key,price,limit in [('PIT',2.50,1),('RACE',2.25,2),('FACTORY',2.00,3)]:
    conn.execute('DELETE FROM membership_usage'); conn.commit()
    ns['activate_demo_subscription'](conn,311,key)
    q=ns['member_quote'](conn,311,race)
    assert q['eligible'] and q['member_price']==price and q['daily_limit']==limit, (key,q)
    assert q['member_price'] >= race['prize_contribution']+race['fast_lap_contribution']
    for i in range(limit):
        rr=dict(race); rr['id']=100+i
        q=ns['member_quote'](conn,311,rr); assert q['eligible']; ns['record_member_use'](conn,311,rr['id'],q)
    q=ns['member_quote'](conn,311,{'id':999,**{k:v for k,v in race.items() if k!='id'}})
    assert not q['eligible'] and q['member_price']==3.0
    qc=ns['member_quote'](conn,311,cash); assert not qc['eligible'] and qc['member_price']==25.0
print('SUBSCRIPTIONS VERIFIED', {k:(v['monthly_price'],v['daily_races'],v['community_price']) for k,v in ns['PLANS'].items()})

with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED) as z:
    for f in sorted(work.rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts:
            z.write(f, f.relative_to(work).as_posix())
with zipfile.ZipFile(OUT) as z:
    names=set(z.namelist()); missing=[x for x in required if x not in names]
    if missing: raise SystemExit('Packaged ZIP incomplete: '+', '.join(missing))

digest=hashlib.sha256(OUT.read_bytes()).hexdigest()
Path('race-control/latest.json').write_text(json.dumps({
    'version':'0.3.2',
    'url':'https://raw.githubusercontent.com/n286f7kh2k-debug/MXB-Bike-Builder/main/race-control/releases/MXB_Race_Day_Live_v0_3_2_UPDATE.zip',
    'sha256':digest,
    'notes':NOTES,
},indent=2)+'\n',encoding='utf-8')
print('BUILT',OUT,digest)
