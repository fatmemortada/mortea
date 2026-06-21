from django.apps import AppConfig
import os
import sys


class ClientsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clients'

    def ready(self):
        # Never start scheduler during management commands
        mgmt_commands = {
            'migrate', 'makemigrations', 'collectstatic', 'shell',
            'createsuperuser', 'dbshell', 'test', 'check', 'showmigrations',
            'sqlmigrate', 'dumpdata', 'loaddata', 'inspectdb',
        }
        if len(sys.argv) > 1 and sys.argv[1] in mgmt_commands:
            return

        import logging
        logger = logging.getLogger(__name__)

        # In dev with runserver: only start in the reloader process (RUN_MAIN=true)
        # In production with gunicorn: GUNICORN_MASTER=true env var is set in Dockerfile
        should_start = (
            os.environ.get('RUN_MAIN') == 'true'
            or os.environ.get('GUNICORN_MASTER', '').lower() == 'true'
        )
        if should_start:
            try:
                from . import scheduler
                scheduler.start()
            except Exception:
                logger.exception("Scheduler failed to start")
