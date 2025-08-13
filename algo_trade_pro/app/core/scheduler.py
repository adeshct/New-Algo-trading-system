import threading
import time
import schedule
from datetime import datetime

from app.services.logger import get_logger
from app.services.reporters import generate_daily_excel_report
from app.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class TaskScheduler:
    """
    Background scheduler that runs daily and time-based jobs using the schedule module.
    """

    def __init__(self):
        self.running = False
        self.thread = None
        self._lock = threading.Lock()

    def _init_schedule(self):
        """Initializes scheduled jobs based on config"""

        # Daily report generation
        schedule.every().day.at(settings.DAILY_REPORT_TIME).do(self.run_daily_report)

        # Add more jobs here as needed
        # schedule.every(1).hours.do(self.clean_temp_files)

        logger.info(f"Scheduled task: daily report at {settings.DAILY_REPORT_TIME}")

    def run(self):
        """Scheduler loop to run in a background thread"""
        with self._lock:
            if self.running:
                logger.warning("Scheduler is already running.")
                return

            logger.info("Starting task scheduler thread...")
            self.running = True

        self._init_schedule()

        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(5)

        logger.info("Scheduler thread stopped.")

    def stop(self):
        """Stop the running scheduler"""
        with self._lock:
            self.running = False

    def is_running(self):
        return self.running

    # === Scheduled Job Handlers === #

    def run_daily_report(self):
        """Triggered daily to generate trade report"""
        logger.info("Running daily report generation job...")
        try:
            generate_daily_excel_report()
            logger.info("Daily report generated successfully.")
        except Exception as e:
            logger.error(f"Failed to generate daily report: {e}")

    def clean_temp_files(self):
        """(Optional) Clean temporary files (example stub)"""
        logger.info("Running temporary file cleaner...")
        # TODO: Implement actual file cleanup
