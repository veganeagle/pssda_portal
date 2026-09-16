import duckdb
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'processed')
EMPLOYER_CANONICAL = os.path.join(DATA_DIR, 'employer', 'employers_canonical.parquet')

con = duckdb.connect(database=':memory:')

# Register all data files
for file in os.listdir(DATA_DIR):
    if file.endswith(".parquet"):
        view_name = os.path.splitext(file)[0]
        con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM '{os.path.join(DATA_DIR, file)}'")
# canonical employers (subfolder)
if os.path.exists(EMPLOYER_CANONICAL):
    con.execute(f"CREATE OR REPLACE VIEW employers_canonical AS SELECT * FROM '{EMPLOYER_CANONICAL}'")

def query(sql: str, params: list | None = None):
    return con.execute(sql, params or []).fetchdf()
