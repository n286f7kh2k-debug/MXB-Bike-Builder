"""MXB Race Day Live v0.3.2 membership/subscription engine.

The membership discount applies only to Community / Low Entry races.  The normal
race economics remain intact: the full race is registered first, then the member
savings are returned as an immediate wallet rebate.  That means purse and fastest-
lap funding never depend on a discounted registration amount.
"""
from datetime import datetime, timedelta

PLANS = {
    'PIT': {
        'name': 'Pit Pass',
        'monthly_price': 9.99,
        'daily_races': 1,
        'community_price': 2.50,
        'badge': 'PIT PASS',
    },
    'RACE': {
        'name': 'Race Pass',
        'monthly_price': 19.99,
        'daily_races': 2,
        'community_price': 2.25,
        'badge': 'RACE PASS',
    },
    'FACTORY': {
        'name': 'Factory Pass',
        'monthly_price': 34.99,
        'daily_races': 3,
        'community_price': 2.00,
        'badge': 'FACTORY PASS',
    },
}


def _now():
    return datetime.now().replace(microsecond=0)


def _iso(dt):
    return dt.isoformat()


def _rowdict(row):
    return dict(row) if row is not None else None


def ensure_subscription_schema(conn):
    with conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS membership_subscriptions(
            rider_id INTEGER PRIMARY KEY,
            plan_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            provider TEXT,
            provider_subscription_id TEXT,
            current_period_start TEXT NOT NULL,
            current_period_end TEXT NOT NULL,
            auto_renew INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS membership_usage(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rider_id INTEGER NOT NULL,
            race_id INTEGER NOT NULL,
            plan_key TEXT NOT NULL,
            usage_date TEXT NOT NULL,
            regular_price REAL NOT NULL,
            member_price REAL NOT NULL,
            discount_amount REAL NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(rider_id,race_id)
        );
        CREATE INDEX IF NOT EXISTS idx_membership_usage_day
            ON membership_usage(rider_id,usage_date);
        ''')


def _refresh_demo_renewal(conn, row):
    """Keep DEMO subscriptions testable without pretending a real card was charged.

    Production payment providers should update the same row from their successful
    renewal event.  DEMO renewals simply advance the period for local testing.
    """
    if not row or str(row['status']).upper() != 'ACTIVE':
        return row
    try:
        end = datetime.fromisoformat(row['current_period_end'])
    except Exception:
        return row
    now = _now()
    if end > now:
        return row
    if int(row['auto_renew'] or 0) and str(row['provider'] or '').upper() == 'DEMO':
        start = now
        finish = now + timedelta(days=30)
        with conn:
            conn.execute('''UPDATE membership_subscriptions
                            SET current_period_start=?,current_period_end=?,updated_at=?
                            WHERE rider_id=?''',
                         (_iso(start), _iso(finish), _iso(now), row['rider_id']))
        return conn.execute('SELECT * FROM membership_subscriptions WHERE rider_id=?',
                            (row['rider_id'],)).fetchone()
    with conn:
        conn.execute("UPDATE membership_subscriptions SET status='EXPIRED',updated_at=? WHERE rider_id=?",
                     (_iso(now), row['rider_id']))
    return conn.execute('SELECT * FROM membership_subscriptions WHERE rider_id=?',
                        (row['rider_id'],)).fetchone()


def get_subscription(conn, rider_id):
    ensure_subscription_schema(conn)
    row = conn.execute('SELECT * FROM membership_subscriptions WHERE rider_id=?',
                       (rider_id,)).fetchone()
    row = _refresh_demo_renewal(conn, row)
    if not row:
        return None
    data = _rowdict(row)
    plan = PLANS.get(str(data.get('plan_key') or '').upper())
    data['plan'] = plan
    data['active'] = bool(plan and str(data.get('status') or '').upper() == 'ACTIVE')
    return data


def usage_today(conn, rider_id):
    ensure_subscription_schema(conn)
    today = _now().date().isoformat()
    row = conn.execute('SELECT COUNT(*) n FROM membership_usage WHERE rider_id=? AND usage_date=?',
                       (rider_id,today)).fetchone()
    return int(row['n'] if row else 0)


def member_quote(conn, rider_id, race):
    """Return the member price for this race, or normal pricing when unavailable."""
    regular = round(float(race['entry_fee']), 2)
    result = {
        'eligible': False,
        'regular_price': regular,
        'member_price': regular,
        'discount': 0.0,
        'plan_key': None,
        'plan': None,
        'used_today': 0,
        'daily_limit': 0,
        'remaining_today': 0,
        'reason': '',
    }
    if str(race['lobby_tier']) != 'Low Entry':
        result['reason'] = 'Cash and Premier races use standard entry pricing.'
        return result
    sub = get_subscription(conn, rider_id)
    if not sub or not sub.get('active') or not sub.get('plan'):
        result['reason'] = 'No active membership.'
        return result
    plan = sub['plan']
    used = usage_today(conn, rider_id)
    limit = int(plan['daily_races'])
    result.update(plan_key=sub['plan_key'], plan=plan, used_today=used,
                  daily_limit=limit, remaining_today=max(0,limit-used))
    if used >= limit:
        result['reason'] = 'Daily member-race allowance used; standard entry applies.'
        return result
    member = min(regular, round(float(plan['community_price']),2))
    # Never discount below the race-funded prize components.
    funded = round(float(race['prize_contribution'] or 0) + float(race['fast_lap_contribution'] or 0),2)
    member = max(member, funded)
    discount = round(max(0.0, regular-member), 2)
    if discount <= 0:
        result['reason'] = 'Standard entry is already at or below the member price.'
        return result
    result.update(eligible=True, member_price=member, discount=discount,
                  remaining_today=max(0,limit-used))
    return result


def record_member_use(conn, rider_id, race_id, quote):
    if not quote or not quote.get('eligible') or quote.get('discount',0) <= 0:
        return False
    now = _now(); today = now.date().isoformat()
    with conn:
        conn.execute('''INSERT OR IGNORE INTO membership_usage(
            rider_id,race_id,plan_key,usage_date,regular_price,member_price,discount_amount,created_at
        ) VALUES(?,?,?,?,?,?,?,?)''',
        (rider_id,race_id,quote['plan_key'],today,quote['regular_price'],
         quote['member_price'],quote['discount'],_iso(now)))
    return True


def activate_demo_subscription(conn, rider_id, plan_key):
    """Activate a 30-day DEMO plan. Real billing provider replaces this activation path."""
    key = str(plan_key or '').upper()
    if key not in PLANS:
        raise ValueError('Unknown membership plan.')
    ensure_subscription_schema(conn)
    now = _now(); end = now + timedelta(days=30)
    with conn:
        conn.execute('''INSERT INTO membership_subscriptions(
            rider_id,plan_key,status,provider,provider_subscription_id,
            current_period_start,current_period_end,auto_renew,created_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(rider_id) DO UPDATE SET
            plan_key=excluded.plan_key,status='ACTIVE',provider=excluded.provider,
            provider_subscription_id=NULL,current_period_start=excluded.current_period_start,
            current_period_end=excluded.current_period_end,auto_renew=1,updated_at=excluded.updated_at''',
        (rider_id,key,'ACTIVE','DEMO',None,_iso(now),_iso(end),1,_iso(now),_iso(now)))
    return get_subscription(conn,rider_id)


def cancel_auto_renew(conn, rider_id):
    ensure_subscription_schema(conn)
    with conn:
        conn.execute('UPDATE membership_subscriptions SET auto_renew=0,updated_at=? WHERE rider_id=?',
                     (_iso(_now()),rider_id))
    return get_subscription(conn,rider_id)


def admin_membership_metrics(conn):
    ensure_subscription_schema(conn)
    active = list(conn.execute("SELECT plan_key,COUNT(*) n FROM membership_subscriptions WHERE status='ACTIVE' GROUP BY plan_key"))
    counts = {str(r['plan_key']).upper(): int(r['n']) for r in active}
    mrr = sum(PLANS[k]['monthly_price'] * counts.get(k,0) for k in PLANS)
    return {'active_subscribers': sum(counts.values()), 'mrr': round(mrr,2), 'by_plan': counts}
