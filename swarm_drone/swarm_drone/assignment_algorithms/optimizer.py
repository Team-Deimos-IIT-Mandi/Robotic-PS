from functools import lru_cache


def find_max_coverage_assignment(matrix, pending_packages, dispatch_budget=None,
                                 cost_first=False):
    best_assignment = None
    best_coverage = -1
    best_urgent_coverage = -1
    best_min_slack = -float('inf')
    best_total_slack = -float('inf')
    best_total_cost = float('inf')
    search_steps = 0
    max_steps = 50000
    visited = {}

    packages_list = (sorted(pending_packages, key=lambda package: (
        not any(c.get("urgent", False) for c in matrix[package.id]["candidates"]),
        package.deadline, package.id,
    )) if dispatch_budget is not None else pending_packages)

    candidates_by_package = [sorted(matrix[p.id]["candidates"], key=lambda c: c["cost"])
                             for p in packages_list]
    drone_bits = {drone_id: 1 << index for index, drone_id in enumerate(sorted({
        c["drone_id"] for candidates in candidates_by_package for c in candidates
    }))}
    compact_candidates = [[(drone_bits[c["drone_id"]], c["cost"],
                            not c.get("requires_dispatch", False) or c.get("urgent", False),
                            c.get("urgent", False)) for c in candidates]
                          for candidates in candidates_by_package]
    suffix_drones = [0] * (len(packages_list) + 1)
    for index in range(len(packages_list) - 1, -1, -1):
        suffix_drones[index] = suffix_drones[index + 1]
        for bit, _, _, _ in compact_candidates[index]:
            suffix_drones[index] |= bit

    @lru_cache(maxsize=None)
    def remaining_info(idx, assigned_mask):
        """Bounds depend only on remaining packages and occupied drones."""
        if idx == len(packages_list):
            return 0, 0, 0, ()
        flexible, normal, urgent, costs = remaining_info(idx + 1, assigned_mask)
        choices = [c for c in compact_candidates[idx] if not c[0] & assigned_mask]
        if choices:
            is_flexible = any(c[2] for c in choices)
            flexible += int(is_flexible)
            normal += int(not is_flexible)
            urgent += int(any(c[3] for c in choices))
            costs = tuple(sorted((choices[0][1],) + costs))
        return flexible, normal, urgent, costs

    def search(idx, current_assignment, assigned_drones, coverage, min_slack, total_slack, total_cost, departures,
               assigned_mask=0):
        nonlocal best_assignment, best_coverage, best_urgent_coverage, best_min_slack, best_total_slack, best_total_cost, search_steps

        search_steps += 1
        if search_steps > max_steps:
            return
        if cost_first:
            state = (idx, assigned_mask, departures)
            urgent_coverage = sum(c.get("urgent", False) for _, c in current_assignment)
            previous = visited.get(state)
            if previous is not None:
                previous_urgent, previous_cost, previous_min_slack, previous_total_slack = previous
                if (previous_urgent > urgent_coverage
                        or (previous_urgent == urgent_coverage and previous_cost < total_cost)
                        or (previous_urgent == urgent_coverage and previous_cost == total_cost
                            and previous_min_slack >= min_slack and previous_total_slack >= total_slack)):
                    return
            visited[state] = (urgent_coverage, total_cost, min_slack, total_slack)

        packages_remaining = len(packages_list) - idx
        remaining_drones = (suffix_drones[idx] & ~assigned_mask).bit_count()
        max_possible_coverage = coverage + min(packages_remaining, remaining_drones)
        flexible, normal, remaining_urgent, relaxed_costs = remaining_info(idx, assigned_mask)
        if dispatch_budget is not None:
            max_possible_coverage = min(
                max_possible_coverage,
                coverage + flexible + min(normal, max(0, dispatch_budget - departures)),
            )

        if max_possible_coverage < best_coverage:
            return
        if cost_first and best_assignment is not None and max_possible_coverage == best_coverage:
            needed = best_coverage - coverage
            urgent_coverage = sum(c.get("urgent", False) for _, c in current_assignment)
            max_urgent = urgent_coverage + min(needed, remaining_urgent)
            if (max_urgent < best_urgent_coverage or len(relaxed_costs) < needed
                    or (max_urgent == best_urgent_coverage
                        and total_cost + sum(relaxed_costs[:needed]) > best_total_cost)):
                return

        if idx == len(packages_list):
            update = False
            urgent_coverage = sum(c.get("urgent", False) for _, c in current_assignment)
            if coverage > best_coverage:
                update = True
            elif coverage == best_coverage:
                if cost_first:
                    update = (-urgent_coverage, total_cost, -min_slack, -total_slack) < (
                        -best_urgent_coverage, best_total_cost, -best_min_slack, -best_total_slack,
                    )
                elif min_slack > best_min_slack:
                    update = True
                elif min_slack == best_min_slack:
                    if total_slack > best_total_slack:
                        update = True
                    elif total_slack == best_total_slack:
                        if total_cost < best_total_cost:
                            update = True

            if update:
                best_coverage = coverage
                best_urgent_coverage = urgent_coverage
                best_min_slack = min_slack
                best_total_slack = total_slack
                best_total_cost = total_cost
                best_assignment = current_assignment.copy()
            return

        package = packages_list[idx]

        sorted_candidates = candidates_by_package[idx]

        for candidate in sorted_candidates:
            drone_id = candidate["drone_id"]
            departure = int(candidate.get("requires_dispatch", False))
            if (dispatch_budget is not None and departure and not candidate.get("urgent", False)
                    and departures >= dispatch_budget):
                continue
            if drone_id not in assigned_drones:
                slack = candidate["slack"]
                cost = candidate["cost"]

                new_min_slack = min(min_slack, slack) if coverage > 0 else slack

                current_assignment.append((package, candidate))
                assigned_drones.add(drone_id)

                search(idx + 1, current_assignment, assigned_drones, coverage + 1, new_min_slack, total_slack + slack, total_cost + cost, departures + departure,
                       assigned_mask | drone_bits[drone_id])

                assigned_drones.remove(drone_id)
                current_assignment.pop()

        search(idx + 1, current_assignment, assigned_drones, coverage, min_slack, total_slack, total_cost, departures,
               assigned_mask)

    search(0, [], set(), 0, -float('inf'), 0, 0, 0)

    return best_assignment
