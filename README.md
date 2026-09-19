# Robo-PS

This repository contains the problem statements for the robotics.

## Objective

Solve as many problems as possible from both problem-set PDFs. Some problems may be challenging depending on the solver's experience and skill level.

## Questions and Support

For doubts or clarification regarding the problems, contact:

* +91 8559079096
* +91 9451864348

## Demo

Watch the demo here: [https://youtu.be/MHBbmQdaJFQ](https://youtu.be/MHBbmQdaJFQ)

## Run the V3 Swarm Drone Stress Test

Watch the V3 swarm-drone demo: [https://youtu.be/nDXQZR_oe2g](https://youtu.be/nDXQZR_oe2g)

From any directory on this machine, launch the visual V3 workload inside the
`Robotic-PS` repository with 35 packages at startup and all runtime parameters
specified explicitly:

```sh
cd ~/Robotic-PS/swarm_drone && python3 -B scripts/run_v3_hard_visual.py --minutes 40 --time-scale 5 --seed 42 --initial-packages 35 --arrival-interval 5 --burst-size 10 --burst-interval 60 --log-dir results/logs
```

This runner always uses the V3 algorithm. Add `--headless` to run without the
simulation window or playback delay.

See the [swarm drone README](swarm_drone/README.md) for installation steps,
runtime options, and additional workloads.
