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
        with self.assertRaises(ValueError):
            RuntimeLimits(max_output_chars=0)
        with self.assertRaises(ValueError):
            RuntimeLimits(max_write_bytes=0)


if __name__ == "__main__":
    unittest.main()

    def test_output_budget_is_enforced(self):
        budget = RuntimeBudget(RuntimeLimits(max_output_chars=5))
        budget.record_output(5)
        with self.assertRaises(RuntimeError):
            budget.record_output(1)

    def test_write_budget_is_enforced(self):
        budget = RuntimeBudget(RuntimeLimits(max_write_bytes=5))
        budget.record_write(5)
        with self.assertRaises(RuntimeError):
            budget.record_write(1)
