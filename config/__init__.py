import os

# Re-export DATABASE_PATH so 'from config import DATABASE_PATH' works
# even when the config/ package shadows config.py
DATABASE_PATH = os.getenv('DATABASE_PATH', 'stocks.db')
