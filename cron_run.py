"""Cron entry point for Railway — runs pipeline then disposes all DB connections."""

import sys
from loguru import logger

def main():
    from momentum_edge.db.session import SessionLocal, engine
    from momentum_edge.pipeline.runner import run_pipeline
    from momentum_edge.utils.date_utils import prev_trading_day

    target_date = prev_trading_day()
    logger.info(f"[CRON] Starting pipeline for {target_date}")

    db = SessionLocal()
    try:
        run_pipeline(db, target_date)
        logger.info("[CRON] Pipeline completed successfully")
    except Exception as e:
        logger.error(f"[CRON] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()
        engine.dispose()
        logger.info("[CRON] DB connections disposed — process exiting")


if __name__ == "__main__":
    main()
