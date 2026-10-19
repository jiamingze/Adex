"""Isolate module registration windows without weakening the production limiter."""
import hashlib
import os
import psycopg
import pytest


@pytest.fixture(scope='module', autouse=True)
def isolated_registration_window():
    # All HTTP fixtures use one loopback source IP. Independent modules must not
    # accidentally spend each other's registration quota; within-module limits remain real.
    name = os.environ['ADEX_PG_DB']
    assert name.startswith('adex_test_'), 'Never reset quota in a user database'
    with psycopg.connect(host=os.environ['ADEX_PG_HOST'], port=os.environ['ADEX_PG_PORT'],
                          dbname=name, user='adex_admin', password=os.environ['ADEX_ADMIN_PASSWORD'], autocommit=True) as conn:
        conn.execute('DELETE FROM app.login_limits WHERE bucket=%s',
                     (hashlib.sha256(b'register:127.0.0.1').hexdigest(),))
