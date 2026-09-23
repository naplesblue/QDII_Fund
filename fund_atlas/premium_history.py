"""Observed price/IOPV premiums, never reconstructed from historical NAV."""
import datetime as dt
import math
import sqlite3
from contextlib import contextmanager
from .shared_cache import TZ, trading_day


class PremiumHistory:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS premium_samples (
                code TEXT NOT NULL, quote_ts INTEGER NOT NULL, collected_at REAL NOT NULL,
                price REAL NOT NULL, iopv REAL NOT NULL, premium REAL NOT NULL,
                PRIMARY KEY(code, quote_ts))''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        try:
            with db:
                yield db
        finally:
            db.close()

    def append(self, funds, collected_at):
        rows = []
        for f in funds:
            try:
                price, iopv = float(f['price']), float(f['iopv'])
                ts = int(f['quote_timestamp'])
                stamp = dt.datetime.fromtimestamp(ts, TZ)
                current = dt.datetime.fromtimestamp(collected_at, TZ)
                day = str(f['quote_date']).replace('-', '')
                # Reject nonfinite, mismatched, future or delayed/stale observations.
                if not all(math.isfinite(n) and n > 0 for n in (price, iopv)):
                    continue
                if stamp.date() != current.date() or day != stamp.strftime('%Y%m%d'):
                    continue
                if not trading_day(stamp.date()) or not -5 <= collected_at - ts <= 1200:
                    continue
                minutes = stamp.hour * 60 + stamp.minute
                if not (570 <= minutes <= 690 or 780 <= minutes <= 900):
                    continue
                rows.append((f['code'], ts, collected_at, price, iopv, (price / iopv - 1) * 100))
            except (KeyError, TypeError, ValueError, OverflowError, OSError):
                continue
        with self.connect() as db:
            before = db.total_changes
            db.executemany('INSERT OR IGNORE INTO premium_samples VALUES (?,?,?,?,?,?)', rows)
            return db.total_changes - before

    def read(self, code, days, now):
        with self.connect() as db:
            rows = db.execute('''SELECT quote_ts, premium, price, iopv FROM premium_samples
                WHERE code=? AND quote_ts>=? AND quote_ts<=? ORDER BY quote_ts''',
                (code, now - days * 86400, now)).fetchall()
        return [{'time': r[0], 'premium': round(r[1], 4), 'price': r[2], 'iopv': r[3]} for r in rows]
