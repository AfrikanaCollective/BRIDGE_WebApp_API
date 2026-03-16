from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

csv_path = BASE_DIR / "data" / "mongo_pages.csv"

mongo_pages = pd.read_csv(csv_path)