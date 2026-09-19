# Ackermann simulator changes: what changed and why

Updated: 2026-09-19, Asia/Kolkata  
Project: `tasks/task1/ackermann_kinodynamic_sim`

The first section records the earlier Scenario 0 repair. The dated section at
the end records the later multi-goal implementation and TCP/path-display fixes.
Temporary debug logging and test artifacts are kept outside the repository.

## The original failure

The old client sent `Q\n`, called `read()` once, and expected that single read
to contain the complete `CONFIG` and `GRID` responses. TCP is a continuous
ordered byte stream, so a read can contain only part of a message, an early
`TELEMETRY` message, or several messages together. Scenario 0 has a 500 by 500
grid, much larger than the old 16 KB receive buffer.

The direct symptom was `Map: 0x0 resolution: 0m`. The client then planned with
missing map and pose data, so its result was not valid.

## Reliable TCP input and output

`readLine()` keeps an internal `pending` buffer. It appends every socket read
until it finds a newline, returns one complete protocol line, and preserves
extra bytes for the next line. It retries interrupted reads (`EINTR`). This is
used both while waiting for CONFIG and GRID and later for TELEMETRY.

`sendMessage()` loops until all bytes of a `Q`, `TRAJ`, or `CTRL` message have
been sent. It retries interrupted sends and uses `MSG_NOSIGNAL` so a closed
server connection does not terminate the client unexpectedly.

## CONFIG and GRID checks

The client now waits until it has received both CONFIG and GRID. CONFIG must
parse successfully with positive map dimensions and resolution. GRID must have
exactly the number of cells it declares, and that count must equal `rows * cols`.
If any check fails, the client exits instead of starting Hybrid A* with invalid
data. The map variables are initialized, preventing accidental use of
uninitialized values.

## Planned trajectory upload

After initial planning and after every replan, the client sends a `TRAJ`
message containing `x y yaw v` for each path sample. The supplied simulator
already supports this message and draws the path in its visualizer. Vehicle
motion still comes only from `CTRL` commands.

## Hybrid A* changes

The simulator limits steering changes to 1 radian per second. The planner now
uses the same limit while propagating every motion primitive. Previously it
assumed steering could change instantly, which can create paths the simulated
vehicle cannot follow. The state stores the actual rate-limited steering angle;
the requested primitive steering remains in `delta_used` for search cost and
path reconstruction.

The active A* node is copied before adding successors. A vector can reallocate
when a successor is appended, making a reference to its current element invalid.
Copying prevents this undefined behavior.

Each primitive contains five 0.1-second integration steps. Collision checking
checks every step, but the old returned path kept only each primitive endpoint.
The path now contains every checked integration sample, giving the tracker and
visualizer the same dense trajectory that was collision-checked.

## Tracker changes

The controller uses the nearest dense reference sample to calculate cross-track
and heading errors. The lateral steering sign was corrected: if the rear axle
is left of the path, the correction must steer right toward it. It also adds the
next planned steering value as feed-forward, then uses feedback to remove the
remaining error:

```text
steering = planned steering - 0.5 * cross-track error + heading error
```

For reverse segments, heading error is evaluated in the reverse driving
direction. Reverse support exists in the planner and controller, but the
successful Scenario 0 route was forward-only.

## Stopping and replanning

The simulator reports success only when position error is below 0.40 m, yaw
error is below 0.30 rad, and speed is below 0.2 m/s. When the position and yaw
conditions are met, the client commands `CTRL 0 0` so the car actually stops.

When tracking error exceeds the existing replan thresholds, the client stops,
plans from the current telemetry pose, uploads the new trajectory, and restarts
tracking. It also sends a stop before closing the socket and returns success
only after confirmed goal telemetry.

## Scenario 0 result

The cleaned implementation was built with CMake and run against the supplied
Scenario 0 simulator. Both client and simulator confirmed the goal. The run had
no collision, finished with 0.374171 m position error, 0.0763 rad yaw error,
and 0 m/s final speed. It reached the goal 8.45 simulation seconds after the
first client telemetry. No replan was needed.

## What remained to test after the initial Scenario 0 repair

Scenario 0 verifies connection, complete map transfer, planning, trajectory
upload, tracking, stopping, collision checking, and the goal check for this
map. It does not prove reverse tracking, direction changes, recovery replanning,
or Scenarios 1 through 3. Those require separate simulator runs.

---

# 2026-09-19 — Multi-goal navigation and incomplete trajectory repair

Date: 2026-09-19, Asia/Kolkata. First completed verification: 13:13 local time.
Project: `tasks/task1/ackermann_kinodynamic_sim`.

## What you reported

The displayed path ended halfway along long legs, particularly start-to-1 and
5-to-6. The car continued moving and eventually collided. These were two
different problems, so fixing only the drawing would not fix the collision.

## 1. Send the actual waypoint list and visit it in order

Files: `include/tcp_protocol.hpp`, `src/simulator.cpp`,
`apps/candidate_template.cpp`.

The server now sends a newline-terminated `WAYPOINTS` message along with `CONFIG`
and `GRID`. The client waits for all three complete messages before planning.
It uses the coordinates supplied by the simulator; it does not hard-code a
Scenario 3 route. Scenarios without waypoints still use the single final goal.

The planner solves one full leg at a time. Intermediate waypoints require only
position (within 0.8 m for the client, inside the server's 1.2 m acceptance
radius). They do not require an arbitrary heading. The final target still
requires position error below 0.40 m, heading error below 0.30 rad, and final
speed below 0.2 m/s. The server checks waypoints in order rather than marking
later points reached just because the car happens to pass nearby.

The visualizer shows the complete **current leg**, not every future leg at once.
The next leg is planned and displayed after the current waypoint is reached.

## 2. Fix the path that disappeared halfway

Files: `include/simulator.hpp`, `src/simulator.cpp`.

Previously the server treated one socket read as a whole message. Its roughly
4 KB buffer often held only the first 137–140 samples of a longer `TRAJ` line.
It displayed that prefix and lost the remaining samples. The client still
followed its full local path, which explains why it drove past the drawn line.

The server now keeps an input buffer across simulation ticks. It waits for the
newline before parsing a trajectory and replaces the displayed path only after
the entire line has parsed successfully. Extra complete lines and partial tails
are preserved. Invalid trajectory records do not replace the previous path.

Outgoing server messages also use a persistent buffer. A short nonblocking
`send()` leaves the unsent suffix queued for the next tick, instead of losing
part of `CONFIG`, `GRID`, or telemetry. A disconnect clears the buffers and
commands zero speed. The client logs uploaded sample counts and the path's end
coordinate; the server logs the received count so truncation is easy to spot.

## 3. Keep clearance around obstacles

File: `apps/candidate_template.cpp`.

A diagnostic run reproduced the collision near the lower end of the wall on
the way to waypoint 6. Just before collision, cross-track error was only about
0.028 m. The old planner allowed paths too close to the obstacle for even this
small tracking difference.

The planner's collision footprint now has one grid-cell margin on all sides
(0.20 m on this map). This makes it choose a path with room for small tracking
and numerical errors. It does not move or remove obstacles, weaken the
simulator's collision test, or change the reverse penalty/controller gains.
This margin is a practical buffer, not a proof of collision avoidance on all maps.

## 4. Stop before planning the next leg

File: `apps/candidate_template.cpp`.

Sending a stop command and immediately planning from an old moving pose can
give the next path the wrong starting state. The client now waits until
telemetry confirms both speed and steering are near zero, then starts planning
from that measured pose. Planning runs asynchronously while the main loop
continues reading telemetry and sending `CTRL 0 0` at the telemetry rate.

Once the complete path is ready, the client uploads it, resets the tracking
index, and resumes motion. Replanning uses the same stop/wait/plan sequence.
An empty path or the 250,000-node search limit stops the client safely; it does
not count as success and does not authorize skipping a reachable waypoint.

## 5. Handle the wall at waypoint 7 as requested

Files: `apps/candidate_template.cpp`, `include/occupancy_grid.hpp`,
`src/occupancy_grid.cpp`, `src/simulator.cpp`.

Waypoint 7 is at `(0, 0)`, inside the horizontal wall. Its entire 1.2 m
acceptance circle is occupied, so reaching it would require a collision.
The waypoint and map are deliberately unchanged.

After reaching waypoint 6, the car stops. The client checks the next target's
whole acceptance circle, not just its center cell. If no free part exists, it
sends `SKIP_WAYPOINT 7`. The server independently checks the same map condition,
that 7 is the next unfinished waypoint, and that the car is stopped. It never
allows cancellation of the final waypoint. The client waits for the server's
confirmation before proceeding to waypoint 8.

The check works on the current intermediate waypoint; it is not a hard-coded
instruction to skip index 7 regardless of the map. If that region becomes free,
the client must attempt to reach it normally. A partially free acceptance
circle cannot be cancelled by this rule.

Cancelled waypoints have a separate `cancelled` flag, not `visited=true`. Logs
say `SKIPPED (blocked acceptance area, not reached)` and the visualizer draws
them gray with a slash. Final success includes the skipped count and still
requires reaching the final pose at low speed.

Important: this is the requested local cancellation policy. Finishing with
waypoint 7 skipped is **not** the same as satisfying an original requirement
to physically visit all eight waypoints. The server's completion policy was
explicitly extended to accept verified cancellations; collision checks and
final pose tolerances remain unchanged.

## 6. Logging and documentation

The client prints leg transitions, path lengths/endpoints, cancellation
acknowledgements, and a final summary with position error, yaw error, speed,
elapsed simulation time since its first telemetry, replan count, and maximum
absolute cross-track error measured during tracking. Per-cycle diagnostic
spam is not kept in the repository.

`README.md` documents the new messages and cancellation policy. Rebuild both
server and client together; an old server does not send the new `WAYPOINTS`
message. Temporary build directories, diagnostic scripts, and test logs are
under `/tmp`, not added to the repository. The existing project `build/` was
also rebuilt so normal launch commands use the updated binaries. No map
geometry or waypoint coordinate was changed.

## Validation

Tests use the actual simulator/client TCP loop with Qt's offscreen rendering.
This validates closed-loop behavior and the data supplied to the renderer; it
is not a claim that a visible desktop animation was manually watched.

- Clean CMake build: passed.
- Goal-region check: only Scenario 3 waypoint 7 has a fully blocked 1.2 m
  acceptance circle. A synthetic occupied center with free surrounding area
  correctly does not qualify for cancellation.
- TCP regression: a 1,000-point trajectory split into 701-byte chunks was not
  applied before the newline; afterward the server received all 1,000 points.
  Complete 250,000-cell grid transfer and malformed trajectory rejection passed.
- Skip rejection: early skip of 7, skip of reachable waypoint 1, and skip of
  final waypoint 8 were all rejected.
- First closed-loop Scenario 0 run: success, no collision, no skipped targets,
  position error 0.374171 m, yaw error 0.0763 rad, final speed 0 m/s,
  8.50 simulation seconds from first client telemetry, 0 replans,
  maximum absolute CTE 0.0386412 m. Server time including startup: 9.25 s.
- First closed-loop Scenario 3 run: success under the cancellation policy,
  no collision, reached 1–6 and 8, skipped only 7; position error 0.383615 m,
  yaw error 0.1967 rad, final speed 0 m/s, 169.45 simulation seconds from first
  client telemetry, 0 replans, maximum absolute CTE 0.0767543 m.
  Server time including startup: 170.40 s.
- Scenario 3 uploaded/received sample counts matched on every leg:
  261, 141, 161, 166, 141, 216, 451. In particular the full path to 6 was
  received, and the final path to 8 contained all 451 samples.

First-run logs: `/tmp/ackermann-s0-clearance/` and
`/tmp/ackermann-s3-clearance/`. TCP regression log:
`/tmp/ackermann-protocol-test.log`. These are temporary local evidence, not
version-controlled deliverables. Scenarios 1 and 2 and broader reverse/recovery
behavior have not been validated by these runs.

## 2026-09-19 — Requested 5x simulation speed

Files: `apps/simulator_node.cpp`, `include/simulator.hpp`, `src/simulator.cpp`,
and `README.md`.

You stopped the repeat run and requested five simulated seconds per real
second. The default time scale is now 5, with an optional third argument:
`./simulator_node 8091 3 5`. Pass `1` instead for normal speed. Invalid scales
(non-numbers, zero, negative, or above 20) are rejected with an error.

The physics timestep remains 0.05 simulated seconds. Increasing it to 0.25
would make the car jump farther between collision checks and change numerical
behavior. Instead, the main loop targets one 0.05-second step every 0.01 real
seconds. A monotonic-clock deadline includes time spent rendering and handling
TCP; the visualizer's old 50 ms wait is replaced by a minimal event-processing
wait. Requested speed still depends on the computer keeping up with the work.

Telemetry and controls remain 20 Hz in simulation time (about 100 Hz in real
time at 5x). The client has no fixed real-time sleep and processes each telemetry
update, including sending stop commands while the planner is working.

The earlier Scenario 0 repository-repeat run passed. The Scenario 3 repeat was
interrupted at your request, so it is not counted as a completed test.

5x validation completed at approximately 13:19 Asia/Kolkata:

- Scenario 0: success without collision, position error 0.336667 m, yaw error
  0.0891 rad, speed 0 m/s, 8.50 simulated seconds, no replans, max CTE
  0.0244574 m. This run overlapped the Scenario 3 test and took 4.325 real
  seconds including connection/setup. A standalone repeat still took 4.224 s,
  so concurrent load was not the main bottleneck (see rendering fix below).
- Scenario 3: success with only waypoint 7 skipped, no collision, position
  error 0.370491 m, yaw error 0.1029 rad, speed 0 m/s, no replans,
  max CTE 0.0600989 m. Client interval: 210.90 simulated seconds in 42.238 real
  seconds (approximately 4.99x including connection/setup). Simulator total
  including startup: 215.85 simulated seconds. Counts matched on all legs:
  261, 141, 161, 166, 141, 211, 446.
- Time-scale values `0`, `abc`, and `nan` were rejected before opening a server.

The extra simulated time compared with the 1x test includes planning while
the vehicle is stopped: the same real computation time counts as more
simulation time at 5x. Paths can also differ slightly because TCP/controller
scheduling changes the measured pose at intermediate stops.

Logs: `/tmp/ackermann-s0-5x/` and `/tmp/ackermann-s3-5x/`.

### Rendering bottleneck fixed (13:21 local time)

Scenario 0's dense obstacle grid was redrawn cell by cell on every frame.
This prevented the original renderer from keeping up with 100 real-time ticks
per second. The renderer now caches the static grid/obstacle background once
and copies that image for later frames. The path, vehicle, history, waypoint
statuses, and HUD are still redrawn each frame. Physics and collision checks
still use the original map on every tick; only drawing is cached.

After caching, Scenario 0 passed in 8.65 simulated seconds / 1.770 real seconds
including client connection/setup (approximately 4.89x). Position error was
0.336667 m, yaw error 0.0891 rad, speed 0 m/s, no collision, no replans, and
maximum CTE 0.0244574 m. Logs: `/tmp/ackermann-s0-5x-cached/`.

The final cached-renderer Scenario 3 test also passed: 209.15 simulated seconds
in 41.883 real seconds (approximately 4.99x), no collision, waypoint 7 alone
skipped, position error 0.370491 m, yaw error 0.1029 rad, final speed 0 m/s,
0 replans, maximum CTE 0.0600989 m. All seven trajectory upload/receive counts
matched (261, 141, 161, 166, 141, 211, 446). Logs:
`/tmp/ackermann-s3-5x-cached/`. Both final tests were headless/offscreen; the
test processes were shut down after collecting the result.

## 2026-09-19 — Requested cleanup

Removed the temporary test scripts, diagnostic source copies, standalone test
binaries, temporary build directories, and logs created for this work under
`/tmp`. The log paths above are historical references; those files have now
been deleted. The measured results remain recorded here.

Removed the newly added explanatory source comments, the unused
`WaypointResponse::parse` helper, the now-unused client `<thread>` include,
and unnecessary whitespace. Kept required safety/error/status messages,
functional fixes, 5x pacing, README launch instructions, this change record,
and the existing project build directory. Unrelated files were not removed.

## 2026-09-19 — Scenario 1 validation

Tested the current rebuilt client and simulator on Scenario 1 at 5x speed with
offscreen rendering. No source code was changed for this test. Hybrid A*
expanded 38,397 nodes and uploaded a complete 171-sample trajectory.

The run completed without collision or replanning. Final position error was
0.364524 m, yaw error was 0.2232 rad relative to the requested 1.5708 rad
(90-degree) heading, final speed was 0 m/s, and maximum absolute cross-track
error was 0.0308981 m. The client measured 30.25 simulated seconds from its
first telemetry; the server reported success at 35.2 simulated seconds
including startup. The temporary test logs were deleted after recording these
results.

## 2026-09-19 — Scenario 2 validation

Tested the current rebuilt client and simulator on Scenario 2 at 5x speed with
offscreen rendering. No source code was changed for this test. Hybrid A*
expanded 113,372 nodes and uploaded a complete 506-sample trajectory; the
server received all 506 samples.

The slalom run completed without collision or replanning. Final position error
was 0.363472 m, yaw error was 0.0438 rad, final speed was 0 m/s, and maximum
absolute cross-track error was 0.0473679 m. The client measured 87.30 simulated
seconds from its first telemetry, and the server reported success at 92.25
simulated seconds including startup. The complete command took approximately
19 real seconds, including startup and planning. The temporary test logs were
deleted after recording these results.
