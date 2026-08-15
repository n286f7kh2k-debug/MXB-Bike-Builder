"""One-time v0.3.0 pricing migration for affordable community races."""

COMMUNITY_LOW_ENTRY_FEE = 3.00
COMMUNITY_MAIN_PER_RIDER = 1.00
COMMUNITY_FAST_LAP_PER_RIDER = 0.25
COMMUNITY_PLATFORM_PER_RIDER = 1.75
MIGRATION_KEY = 'pricing_ladder_v030'

# Legacy seeded names are removed after the canonical row exists because the older
# database seeder may recreate them on later startups.
LEGACY_TO_COMMUNITY = {
    'Rookie': ('Rookie $5 Gate Drop', 'Rookie Community Gate Drop'),
    'Amateur': ('Amateur $8 Gate Drop', 'Amateur Community Gate Drop'),
    'Expert': ('Expert $12 Sprint', 'Expert Community Sprint'),
    'Pro': ('Pro $20 Warm-Up', 'Pro Community Warm-Up'),
}


def _has_paid_registration(conn, race_id):
    row = conn.execute(
        "SELECT 1 FROM registrations WHERE race_id=? AND payment_status='PAID' LIMIT 1",
        (race_id,),
    ).fetchone()
    return bool(row)


def apply_low_entry_pricing(conn):
    """Make Low Entry races $3 once, then only clean legacy rows on later startups.

    The database seeder in older installed builds may recreate its legacy named Low Entry
    races on startup. After the first migration we preserve admin edits to the canonical
    non-legacy row and remove only newly re-seeded legacy duplicates that have no paid entry.
    """
    migrated = conn.execute("SELECT 1 FROM meta WHERE key=?", (MIGRATION_KEY,)).fetchone() is not None

    with conn:
        for skill, (legacy_name, community_name) in LEGACY_TO_COMMUNITY.items():
            rows = list(conn.execute(
                """SELECT id,name,entry_fee FROM races
                   WHERE skill_class=? AND lobby_tier='Low Entry' AND status='REGISTRATION'
                   ORDER BY id""",
                (skill,),
            ))
            legacy = [r for r in rows if r['name'] == legacy_name]
            canonical = [r for r in rows if r['name'] != legacy_name]

            if not migrated:
                target = canonical[0] if canonical else (legacy[0] if legacy else None)
                if target:
                    conn.execute(
                        """UPDATE races SET name=?, entry_fee=?, prize_contribution=?,
                                  fast_lap_contribution=?, platform_fee=? WHERE id=?""",
                        (
                            community_name,
                            COMMUNITY_LOW_ENTRY_FEE,
                            COMMUNITY_MAIN_PER_RIDER,
                            COMMUNITY_FAST_LAP_PER_RIDER,
                            COMMUNITY_PLATFORM_PER_RIDER,
                            target['id'],
                        ),
                    )
                    canonical_id = target['id']
                else:
                    canonical_id = None
            else:
                canonical_id = canonical[0]['id'] if canonical else None

            # Old seed() can recreate a legacy row on every startup. Remove only safe,
            # unregistered duplicates; never delete a row with a paid rider attached.
            if canonical_id is not None:
                for row in legacy:
                    if row['id'] != canonical_id and not _has_paid_registration(conn, row['id']):
                        conn.execute('DELETE FROM races WHERE id=?', (row['id'],))

        if not migrated:
            conn.execute(
                "INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO NOTHING",
                (MIGRATION_KEY, '3-dollar-community'),
            )
