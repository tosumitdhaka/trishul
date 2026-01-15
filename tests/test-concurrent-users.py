# test/test_concurrent.py
import sys
import threading
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from core.parser import MibParser
from services.config_service import Config

def test_concurrent():
    mib_file = Path("../mib_files/mibs/IF-MIB.mib")
    
    results = {}
    
    def parse_job(user_id):
        config = Config()
        parser = MibParser(config)
        df = parser.parse_file(str(mib_file))
        results[user_id] = len(df)
        print(f"User {user_id}: {len(df)} records")
    
    # Start 3 concurrent users
    threads = [threading.Thread(target=parse_job, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Verify all succeeded
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    assert all(count > 0 for count in results.values()), "Some users got 0 records"
    assert len(set(results.values())) == 1, f"Users got different counts: {results}"
    
    print(f"✅ SUCCESS: All users got {results[0]} records")

if __name__ == "__main__":
    test_concurrent()
