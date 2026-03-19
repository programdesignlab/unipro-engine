"""
Railway cron entry point.
Runs daily at 10:30 UTC (4:00 PM IST) Mon-Fri.

Usage: python -m momentum_edge.pipeline.cron
"""
import sys
from datetime import date
from loguru import logger

def main():
    """Run the daily pipeline + send email digest."""
    from momentum_edge.db.session import SessionLocal
    from momentum_edge.pipeline.runner import run_pipeline
    from momentum_edge.utils.date_utils import is_trading_day, prev_trading_day

    today = date.today()
    target = prev_trading_day(today)

    if not is_trading_day(today):
        logger.info(f"Not a trading day ({today}), skipping pipeline")
        return

    logger.info(f"=== Daily Cron — {today} (pipeline for {target}) ===")

    db = SessionLocal()
    try:
        run_pipeline(db, target)

        # Send email digest
        try:
            from momentum_edge.notifications.sender import send_daily_digest
            send_daily_digest(db, target)
        except Exception as e:
            logger.error(f"Email digest failed: {e}")

        logger.info("Daily cron complete")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        # Send alert email
        try:
            from momentum_edge.notifications.sender import send_alert
            send_alert(f"Pipeline failed for {target}: {e}")
        except Exception:
            pass
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
