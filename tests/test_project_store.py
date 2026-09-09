import os
import tempfile
import unittest

from production.store import ProjectStore


class ProjectStoreTests(unittest.TestCase):
    def test_sqlite_store_round_trip_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            os.environ["REEL_CREW_DB"] = f"{directory}/projects.db"
            store = ProjectStore()
            saved = store.save("night-run", {"title": "Night Run", "roster": []})
            self.assertEqual(saved["storage"], "sqlite")
            self.assertEqual(store.get("night-run")["title"], "Night Run")
            self.assertEqual(store.events("night-run")[0]["type"], "project.saved")


if __name__ == "__main__":
    unittest.main()
