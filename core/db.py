import sqlite3, os, csv

class EvidenceDB:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._ensure_schema()

    def _conn(self):
        return sqlite3.connect(self.path)

    def _ensure_schema(self):
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                tester TEXT,
                test_case TEXT,
                window_title TEXT,
                process TEXT,
                dpi TEXT,
                screen_size TEXT,
                image_path TEXT,
                sha256 TEXT,
                caption TEXT
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                step_no INTEGER,
                text TEXT
            )
            """)
            con.commit()

    def add_capture(self, row: dict):
        with self._conn() as con:
            cols = ("ts","tester","test_case","window_title","process","dpi","screen_size","image_path","sha256","caption")
            values = [row.get(k,"") for k in cols]
            con.execute(f"INSERT INTO captures ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", values)
            con.commit()

    def add_step(self, ts: str, step_no: int, text: str):
        with self._conn() as con:
            con.execute("INSERT INTO steps (ts, step_no, text) VALUES (?,?,?)",(ts, step_no, text))
            con.commit()

    def fetch_captures(self):
        with self._conn() as con:
            cur = con.cursor()
            cur.execute("SELECT ts, tester, test_case, window_title, image_path, sha256, caption FROM captures ORDER BY id DESC")
            return cur.fetchall()

    def export_captures_csv(self, csv_path: str):
        rows = self.fetch_captures()
        header = ["Timestamp","Tester","TestCase","WindowTitle","ImagePath","SHA256","Caption"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in rows:
                w.writerow(r)
