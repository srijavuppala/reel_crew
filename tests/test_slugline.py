import unittest

from production.planner import break_down
from production.roles import derive_roles


def parse_one(heading: str):
    return break_down(heading + "\nMaria lights a cigarette. A dog barks outside.\n")[0]


class SluglineTests(unittest.TestCase):
    def test_every_dash_variant_yields_the_same_scene(self):
        """Final Draft, Word and PDF exports emit en/em dashes. A separator that
        only understands "-" silently loses the time of day, which costs the
        production its night lighting package."""
        for heading in ("INT. CAFE - NIGHT", "INT. CAFE — NIGHT",
                        "INT. CAFE – NIGHT", "INT. CAFE -- NIGHT"):
            with self.subTest(heading=heading):
                scene = parse_one(heading)
                self.assertEqual(scene.time_of_day, "NIGHT")
                self.assertEqual(scene.location, "CAFE")
                self.assertEqual(scene.interior_exterior, "INT")

    def test_night_scenes_reach_the_crew_list_whatever_dash_was_typed(self):
        for heading in ("EXT. ALLEY - NIGHT", "EXT. ALLEY — NIGHT"):
            with self.subTest(heading=heading):
                roles = derive_roles(break_down(heading + "\nShe runs.\n"))
                flagged = {r.role for r in roles}
                self.assertIn("Gaffer", flagged)
                self.assertIn("Key Grip", flagged)

    def test_hyphenated_location_names_are_not_split(self):
        scene = parse_one("INT. SPANISH-AMERICAN HALL - DAY")
        self.assertEqual(scene.location, "SPANISH-AMERICAN HALL")
        self.assertEqual(scene.time_of_day, "DAY")

    def test_extended_time_vocabulary(self):
        self.assertEqual(parse_one("EXT. ROOFTOP — MAGIC HOUR").time_of_day, "MAGIC HOUR")
        self.assertEqual(parse_one("INT. KITCHEN - MORNING").time_of_day, "MORNING")

    def test_unrecognised_time_is_reported_not_guessed(self):
        self.assertEqual(parse_one("INT. VOID - WHENEVER").time_of_day, "UNSPECIFIED")

    def test_one_definition_of_night_across_modules(self):
        """planner prices night as schedule risk and roles turns it into crew.
        If the two sets drift, a script gets billed for night without being staffed for it."""
        from production.planner import NIGHT_TIMES as planner_nights
        from production.roles import NIGHT_TIMES as roles_nights
        self.assertIs(planner_nights, roles_nights)


if __name__ == "__main__":
    unittest.main()
