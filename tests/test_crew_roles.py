import unittest

from production.crew import _score
from production.planner import break_down
from production.roles import derive_roles, infer_brief

SCRIPT = """INT. APARTMENT - NIGHT
MAYA loads a gun. A dog barks outside. Rain hammers the window.

EXT. CITY STREET - NIGHT
Maya drives the car through rain as a crowd of passengers runs after her.

INT. DINER - DAY
Customers watch Maya confront JOHN. A song plays on the jukebox.
"""


class RoleDerivationTests(unittest.TestCase):
    def setUp(self):
        self.scenes = break_down(SCRIPT)
        self.roles = derive_roles(self.scenes)

    def test_core_crafts_are_staffable_from_the_corpus(self):
        staffable = {r.category for r in self.roles if r.staffable}
        self.assertLessEqual({"director", "producer", "cinematographer", "editor"}, staffable)
        for role in self.roles:
            if role.staffable:
                self.assertIsNotNone(role.category, role.role)

    def test_departments_outside_the_dataset_are_reported_not_dropped(self):
        """The armorer is required by the script and absent from IMDb's crafts.
        Silently omitting it would make the crew plan look complete when it is not."""
        unstaffable = {r.role for r in self.roles if not r.in_corpus}
        self.assertIn("Armorer", unstaffable)          # "loads a gun"
        self.assertIn("Gaffer", unstaffable)           # night scenes
        self.assertIn("Animal Wrangler", unstaffable)  # "a dog barks"
        for role in self.roles:
            if not role.in_corpus:
                self.assertIsNone(role.category, role.role)

    def test_the_writer_is_marked_attached_not_missing_from_the_dataset(self):
        writer = next(r for r in self.roles if r.role == "Writer")
        self.assertTrue(writer.in_corpus)      # IMDb does cover writers
        self.assertFalse(writer.staffable)     # but the script is already written
        self.assertEqual(writer.priority, "attached")

    def test_every_flagged_role_cites_scene_evidence_or_is_universal(self):
        for role in self.roles:
            if role.priority == "required":
                self.assertTrue(role.reason, role.role)

    def test_brief_is_deterministic(self):
        first = infer_brief(SCRIPT, self.scenes)
        second = infer_brief(SCRIPT, break_down(SCRIPT))
        self.assertEqual(first.genres, second.genres)
        self.assertEqual(first.scene_count, 3)


class ScoreTests(unittest.TestCase):
    ROW = {"genre_credits": 6, "avg_rating": 7.0, "reach": 180_000,
           "most_recent": 2025, "credits": 12}

    def test_score_is_bounded_and_components_sum_to_it(self):
        total, components = _score(self.ROW, best_genre=6, best_reach=180_000, genres=["Horror"])
        self.assertLessEqual(total, 100.0)
        self.assertGreaterEqual(total, 0.0)
        self.assertAlmostEqual(total, round(sum(c.points for c in components), 1), places=1)

    def test_empty_pool_does_not_divide_by_zero(self):
        total, _ = _score(self.ROW, best_genre=0, best_reach=0, genres=[])
        self.assertGreaterEqual(total, 0.0)

    def test_more_genre_credits_outrank_fewer_all_else_equal(self):
        strong, _ = _score({**self.ROW, "genre_credits": 6}, 6, 180_000, ["Horror"])
        weak, _ = _score({**self.ROW, "genre_credits": 2}, 6, 180_000, ["Horror"])
        self.assertGreater(strong, weak)


if __name__ == "__main__":
    unittest.main()
