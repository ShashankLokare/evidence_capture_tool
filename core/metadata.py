from dataclasses import dataclass, asdict
import json, os, time

@dataclass
class SessionInfo:
    test_case_id: str
    title: str
    build: str
    environment: str
    tester: str
    tracker_id: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

def session_root(base_dir: str, session: SessionInfo) -> str:
    safe_tc = session.test_case_id.replace(os.sep, "_")
    date = time.strftime("%Y-%m-%d")
    path = os.path.join(base_dir, f"{date}_TC_{safe_tc}")
    os.makedirs(path, exist_ok=True)
    return path
