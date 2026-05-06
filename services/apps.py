from django.apps import AppConfig
import threading
import time
import os
import logging

logger = logging.getLogger(__name__)

# Flag untuk memastikan monitoring hanya berjalan sekali
_monitoring_started = False
_monitoring_lock = threading.Lock()


class ServicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'services'

    def ready(self):
        """
        Method ini akan dipanggil ketika Django sudah siap.
        Digunakan untuk memulai thread monitoring background.
        """
        # Hanya jalankan sekali, jangan di reloader thread
        if os.environ.get('RUN_MAIN') != 'true':
            return

        # 🔥 Mulai thread monitoring
        self.start_monitoring_thread()

    def start_monitoring_thread(self):
        """Memulai thread monitoring di background"""
        global _monitoring_started

        with _monitoring_lock:
            if _monitoring_started:
                logger.info("Monitoring thread already started, skipping...")
                return
            _monitoring_started = True

        # 🔥 Monitoring interval (detik) - default 5 menit
        # Bisa diubah dari settings atau environment variable
        from django.conf import settings
        interval = getattr(settings, 'MONITORING_INTERVAL_SECONDS', 300)  # 300 = 5 menit

        # 🔥 Apakah monitoring diaktifkan?
        enabled = getattr(settings, 'MONITORING_ENABLED', True)

        if not enabled:
            logger.info("Monitoring is disabled by settings.")
            return

        logger.info(f"Starting monitoring thread with interval of {interval} seconds")

        def monitoring_loop():
            """Loop monitoring yang berjalan di background thread"""
            logger.info("Monitoring thread started successfully")
            
            # Tunggu 10 detik sebelum mulai monitoring pertama kali
            # (agar Django benar-benar siap)
            time.sleep(10)

            while True:
                try:
                    logger.info("Running scheduled service status check...")
                    
                    # 🔥 Panggil fungsi monitoring dari utils.py
                    from .utils import check_all_services, check_device_statuses
                    
                    # Cek semua service
                    check_all_services()
                    
                    # Cek status device (ESP32)
                    check_device_statuses()
                    
                    logger.info("Service status check completed successfully")
                    
                except ImportError as e:
                    logger.error(f"Failed to import monitoring functions: {e}")
                except Exception as e:
                    logger.error(f"Error during monitoring check: {e}", exc_info=True)

                # Tunggu sampai interval berikutnya
                time.sleep(interval)

        # 🔥 Jalankan thread daemon (akan berhenti ketika Django berhenti)
        thread = threading.Thread(target=monitoring_loop, daemon=True)
        thread.name = "ServiceMonitoringThread"
        thread.start()
        logger.info("Monitoring thread initialized and started")

