# Rooster Autonomous Engineer Security Boundary

Rooster Autonomous Engineer is designed for controlled autonomy, not unrestricted execution.

## Core rules

1. **Deny by default.** A tool must be registered with `RoosterGuard` and have an explicit permission/risk policy before it can run.
2. **Human approval for higher-risk actions.** Approvals are tied to the exact action ID, expire, and are consumed after one successful authorization.
3. **Emergency stop wins.** When the stop is active, guarded actions are rejected until an operator explicitly resets it.
4. **Sandbox writes.** Automated file writes are confined to `.rooster/sandbox` and path traversal is rejected.
5. **No arbitrary shell by default.** Any future command runner must use argument arrays, `shell=False`, explicit executable allowlists, bounded timeouts/output, and a workspace-restricted working directory.
6. **Network deny by default.** Future network tools must use explicit destination allowlists, bounded timeouts and request sizes, and must not expose credentials.
7. **Audit every decision.** Authorization, approval, execution, failure, checkpoints, and emergency-stop events are recorded. Audit records are hash-chained.
8. **Verify before claiming success.** A task is only considered verified when the configured checks produce observable evidence.
9. **Protect the safety boundary.** Changes to guard, approval, emergency-stop, and security configuration should remain operator-controlled repository changes.
10. **Checkpoint before change.** Recovery snapshots exclude Git metadata and Rooster's own runtime state; symlinks are preserved rather than followed.

## Reporting a security issue

Do not include credentials, access tokens, private keys, or other secrets in an issue. Describe the affected component, reproduction steps, expected behavior, and observed behavior.