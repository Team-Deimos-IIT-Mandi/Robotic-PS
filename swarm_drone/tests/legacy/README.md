# Legacy API tests

This folder preserves historical tests without presenting them as the active
scheduling interface.

## Files

- `__init__.py`: makes legacy tests discoverable as a subpackage.
- `test_assignment_fsm.py`: 28 historical cases for a rule-based assignment
  FSM, old policy entry points, charging calendars, preparation, telemetry,
  ownership, replay, and deadline handling. Imports `swarm_drone.simulation`
  but calls removed APIs such as `assign_packages_fsm`, `schedule_packages`,
  `assign_packages_baseline`, and `mission_departure_energy` on that module.

These cases currently error rather than validate the new assignment modules.
Their previous execution produced 30 error records across 28 cases because
some cases contain subtests. They are intentionally retained and remain
included in repository-wide discovery.

The current scheduler entry point is
`swarm_drone.assignment.schedule_packages`; the current physical transition
module is `swarm_drone.fsm`. Neither means the old scheduling API is restored.
For active regression commands, see [the parent README](../README.md).
