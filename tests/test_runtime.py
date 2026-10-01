import unittest

from rooster_engine.runtime import RuntimeBudget, RuntimeLimits


class RuntimeBudgetTests(unittest.TestCase):
    def test_step_limit_is_enforced(self):
        budget = RuntimeBudget(RuntimeLimits(max_steps=2))
        budget.begin_step()
        budget.begin_step()
        with self.assertRaises(RuntimeError):
            budget.begin_step()

    def test_failure_limit_is_enforced(self):
        budget = RuntimeBudget(RuntimeLimits(max_failures=1))
        budget.record_failure()
        with self.assertRaises(RuntimeError):
            budget.begin_step()

    def test_invalid_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            RuntimeLimits(max_steps=0)
        with self.assertRaises(ValueError):
            RuntimeLimits(max_failures=-1)
        with self.assertRaises(ValueError):
            RuntimeLimits(max_duration_seconds=0)


if __name__ == "__main__":
    unittest.main()
