from django.apps import AppConfig
import threading
import time
import os


class ServicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'services'

    def ready(self):
        if os.environ.get('RUN_MAIN') != 'true':
            return

        from .checker import run_monitoring

        def loop():
            while True:
                try:
                    run_monitoring()
                except Exception as e:
                    print("MONITOR ERROR:", e)

                time.sleep(10)

        t = threading.Thread(target=loop)
        t.daemon = True
        t.start()