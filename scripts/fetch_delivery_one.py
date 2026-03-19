"""Fetch delivery data for a single stock. Usage: python scripts/fetch_delivery_one.py SYMBOL"""
import sys
from momentum_edge.db.session import SessionLocal
from momentum_edge.data.delivery import bootstrap_delivery

symbol = sys.argv[1]
db = SessionLocal()
try:
    bootstrap_delivery(db, symbols=[symbol], skip_existing=False)
finally:
    db.close()
