import unittest

from production.planner import plan_production
from production.schema import ProductionPlanRequest


SCRIPT = """INT. APARTMENT - NIGHT
MAYA enters with a bloody coat. A dog barks outside.

EXT. CITY STREET - NIGHT
Maya drives the car through rain as two passengers run after her.

INT. DINER - DAY
Customers watch Maya confront JOHN. They fight near the kitchen fire.
"""


class ProductionPlannerTests(unittest.TestCase):
    def test_plan_balances_budget_and_extracts_scenes(self):
        plan = plan_production(ProductionPlanRequest(
            title="Night Run", screenplay=SCRIPT, total_budget=500_000,
            target_shoot_days=3, revised_budget=450_000,
        ))
        self.assertEqual(len(plan.scenes), 3)
        self.assertEqual(sum(line.amount for line in plan.budget), 500_000)
        self.assertEqual(plan.summary["night_scenes"], 2)
        self.assertEqual(plan.summary["exterior_scenes"], 1)
        self.assertEqual(plan.change_impact.budget_delta, -50_000)
        self.assertTrue(any(r.area == "safety" for r in plan.risks))

    def test_plan_without_scene_headings_is_still_actionable(self):
        plan = plan_production(ProductionPlanRequest(
            screenplay="A quiet room. Someone opens the door and finds an old photograph.",
            total_budget=25_000, target_shoot_days=1,
        ))
        self.assertEqual(len(plan.scenes), 1)
        self.assertEqual(plan.schedule[0].scene_numbers, [1])


if __name__ == "__main__":
    unittest.main()
