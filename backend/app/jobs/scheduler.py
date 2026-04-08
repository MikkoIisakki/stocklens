"""APScheduler entry point — dispatches daily ingest and scoring jobs.

Populated in task 1.5 (daily ingest scheduler).
"""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler

from app.common.logging import configure_logging

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging()
    scheduler = BlockingScheduler()
    # Jobs registered in task 1.5
    logger.info("Scheduler starting (no jobs registered yet)")
    scheduler.start()


if __name__ == "__main__":
    main()
