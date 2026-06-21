"""
Huey task queue configuration.
Uses Redis when REDIS_URL is set, falls back to SQLite for local dev.
"""
import os
from huey import RedisHuey, SqliteHuey

REDIS_URL = os.environ.get('REDIS_URL', '')

if REDIS_URL:
    huey = RedisHuey('mortacc', url=REDIS_URL)
else:
    # SQLite — file lives alongside the project
    _db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'huey.db')
    huey = SqliteHuey('mortacc', filename=_db_path)
