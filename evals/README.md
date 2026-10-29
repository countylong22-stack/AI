# Rooster behavioral evaluations

Run the deterministic safety evaluation suite with:

```powershell
python -m unittest discover -s tests -p "test_behavioral_evals.py" -v
```

The repository CI unit-test job also runs these cases automatically.

The suite checks observable outcomes at the real policy boundary:
- protected Rooster security files cannot be selected as autonomous write targets;
- secrets and credentials are filtered from autonomous reads;
- traversal and workflow-file write targets are rejected;
- executable paths and non-allowlisted Python execution are denied;
- the emergency stop blocks command execution.

These are deterministic harness tests and do not call a live model. They do not prove universal prompt-injection resistance. A broader model-in-the-loop benchmark should use disposable repositories, synthetic canary secrets, captured tool-call traces, explicit attack and utility scoring, and separate deterministic oracles. Never run adversarial evaluations against a production workspace or real credentials.
