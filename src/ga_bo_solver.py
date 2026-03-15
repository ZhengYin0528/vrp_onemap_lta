from __future__ import annotations

import itertools
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy.stats import norm
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern, WhiteKernel


@dataclass
class DecodeResult:
    objective: float
    routes: List[List[int]]
    route_costs: List[float]
    route_distance_km: List[float]
    route_time_min: List[float]
    route_loads: List[float]


class GABORouter:
    def __init__(self, case: Dict[str, Any], adjusted: Dict[str, Any], weights: Dict[str, float], seed: int = 42):
        self.case = case
        self.cost = np.array(adjusted["cost"], dtype=float)
        self.distance_km = np.array(adjusted["distance_km"], dtype=float)
        self.time_minutes = np.array(adjusted["time_minutes"], dtype=float)
        self.weights = weights
        self.rng = random.Random(seed)

        self.depot_idx = 0
        self.incinerator_idx = 1
        self.bin_node_indices = list(range(2, 2 + len(case["bins"])))
        self.demands = {
            idx: case["bins"][idx - 2]["demand_liters"] for idx in self.bin_node_indices
        }
        self.num_trucks = case["fleet"]["num_trucks"]
        self.truck_capacity = case["fleet"]["truck_capacity_liters"]

    def _split_perm(self, perm: List[int]) -> List[List[int]]:
        chunks = [[] for _ in range(self.num_trucks)]
        loads = [0.0] * self.num_trucks

        for node in perm:
            demand = self.demands[node]
            placed = False
            order = sorted(range(self.num_trucks), key=lambda i: loads[i])
            for i in order:
                if loads[i] + demand <= self.truck_capacity:
                    chunks[i].append(node)
                    loads[i] += demand
                    placed = True
                    break
            if not placed:
                order = sorted(range(self.num_trucks), key=lambda i: loads[i])
                chunks[order[0]].append(node)
                loads[order[0]] += demand
        return chunks

    def decode(self, perm: List[int]) -> DecodeResult:
        truck_bins = self._split_perm(perm)
        total_obj = 0.0
        routes = []
        route_costs = []
        route_distance_km = []
        route_time_min = []
        route_loads = []

        for chunk in truck_bins:
            if not chunk:
                routes.append([self.depot_idx, self.depot_idx])
                route_costs.append(0.0)
                route_distance_km.append(0.0)
                route_time_min.append(0.0)
                route_loads.append(0.0)
                continue

            cur = self.depot_idx
            load = 0.0
            obj = 0.0
            dist = 0.0
            tmin = 0.0
            truck_route = [self.depot_idx]

            for node in chunk:
                demand = self.demands[node]
                if load + demand > self.truck_capacity:
                    obj += self.cost[cur, self.incinerator_idx]
                    dist += self.distance_km[cur, self.incinerator_idx]
                    tmin += self.time_minutes[cur, self.incinerator_idx]
                    truck_route.append(self.incinerator_idx)
                    cur = self.incinerator_idx
                    load = 0.0

                obj += self.cost[cur, node]
                dist += self.distance_km[cur, node]
                tmin += self.time_minutes[cur, node]
                truck_route.append(node)
                cur = node
                load += demand

            if cur != self.incinerator_idx and load > 0:
                obj += self.cost[cur, self.incinerator_idx]
                dist += self.distance_km[cur, self.incinerator_idx]
                tmin += self.time_minutes[cur, self.incinerator_idx]
                truck_route.append(self.incinerator_idx)
                cur = self.incinerator_idx

            obj += self.cost[cur, self.depot_idx]
            dist += self.distance_km[cur, self.depot_idx]
            tmin += self.time_minutes[cur, self.depot_idx]
            truck_route.append(self.depot_idx)

            total_obj += obj
            routes.append(truck_route)
            route_costs.append(float(obj))
            route_distance_km.append(float(dist))
            route_time_min.append(float(tmin))
            route_loads.append(float(sum(self.demands[n] for n in chunk)))

        return DecodeResult(
            objective=float(total_obj),
            routes=routes,
            route_costs=route_costs,
            route_distance_km=route_distance_km,
            route_time_min=route_time_min,
            route_loads=route_loads,
        )

    def solve_greedy(self) -> Dict[str, Any]:
        unvisited = set(self.bin_node_indices)
        truck_chunks = [[] for _ in range(self.num_trucks)]
        truck_loads = [0.0] * self.num_trucks
        truck_pos = [self.depot_idx] * self.num_trucks

        while unvisited:
            progress = False
            for t in range(self.num_trucks):
                feasible = [
                    n for n in unvisited
                    if truck_loads[t] + self.demands[n] <= self.truck_capacity
                ]
                if not feasible:
                    continue
                nxt = min(feasible, key=lambda n: self.cost[truck_pos[t], n])
                truck_chunks[t].append(nxt)
                truck_loads[t] += self.demands[nxt]
                truck_pos[t] = nxt
                unvisited.remove(nxt)
                progress = True
                if not unvisited:
                    break

            if not progress:
                t = min(range(self.num_trucks), key=lambda i: truck_loads[i])
                nxt = min(unvisited, key=lambda n: self.cost[truck_pos[t], n])
                truck_chunks[t].append(nxt)
                truck_loads[t] += self.demands[nxt]
                truck_pos[t] = nxt
                unvisited.remove(nxt)

        perm = []
        for chunk in truck_chunks:
            perm.extend(chunk)

        dec = self.decode(perm)
        return {
            "method": "greedy",
            "objective": dec.objective,
            "routes": dec.routes,
            "route_costs": dec.route_costs,
            "route_distance_km": dec.route_distance_km,
            "route_time_min": dec.route_time_min,
            "route_loads": dec.route_loads,
            "perm": perm,
        }

    def solve_exact_small(self, max_bins: int = 6) -> Dict[str, Any]:
        if len(self.bin_node_indices) > max_bins:
            return {
                "status": "skipped",
                "reason": f"Too many bins for brute force ({len(self.bin_node_indices)} > {max_bins})"
            }

        best_perm = None
        best_dec = None

        for perm in itertools.permutations(self.bin_node_indices):
            dec = self.decode(list(perm))
            if best_dec is None or dec.objective < best_dec.objective:
                best_dec = dec
                best_perm = list(perm)

        return {
            "status": "ok",
            "method": "exact_bruteforce",
            "objective": best_dec.objective,
            "routes": best_dec.routes,
            "route_costs": best_dec.route_costs,
            "route_distance_km": best_dec.route_distance_km,
            "route_time_min": best_dec.route_time_min,
            "route_loads": best_dec.route_loads,
            "perm": best_perm,
        }

    def _init_population(self, pop_size: int) -> List[List[int]]:
        pop = []
        base = self.bin_node_indices[:]
        for _ in range(pop_size):
            x = base[:]
            self.rng.shuffle(x)
            pop.append(x)
        return pop

    def _tournament(self, pop: List[List[int]], scores: List[float], k: int = 3) -> List[int]:
        idxs = self.rng.sample(range(len(pop)), k)
        idxs.sort(key=lambda i: scores[i])
        return pop[idxs[0]][:]

    def _ordered_crossover(self, a: List[int], b: List[int]) -> Tuple[List[int], List[int]]:
        n = len(a)
        i, j = sorted(self.rng.sample(range(n), 2))
        child1 = [None] * n
        child2 = [None] * n
        child1[i:j] = a[i:j]
        child2[i:j] = b[i:j]

        def fill(child, donor):
            pos = j
            for gene in donor[j:] + donor[:j]:
                if gene not in child:
                    if pos >= n:
                        pos = 0
                    child[pos] = gene
                    pos += 1
            return child

        return fill(child1, b), fill(child2, a)

    def _mutate(self, x: List[int], mutation_rate: float) -> None:
        if self.rng.random() < mutation_rate:
            i, j = self.rng.sample(range(len(x)), 2)
            x[i], x[j] = x[j], x[i]

    def run_ga(
        self,
        population: int,
        generations: int,
        crossover_rate: float,
        mutation_rate: float,
        elite_count: int
    ) -> Dict[str, Any]:
        pop = self._init_population(population)
        best_perm = None
        best_dec = None

        best_history = []
        avg_history = []

        for _ in range(generations):
            decs = [self.decode(p) for p in pop]
            scores = [d.objective for d in decs]

            best_history.append(float(np.min(scores)))
            avg_history.append(float(np.mean(scores)))

            elite_idx = np.argsort(scores)[:elite_count]
            new_pop = [pop[i][:] for i in elite_idx]

            gen_best_idx = int(np.argmin(scores))
            if best_dec is None or scores[gen_best_idx] < best_dec.objective:
                best_dec = decs[gen_best_idx]
                best_perm = pop[gen_best_idx][:]

            while len(new_pop) < population:
                p1 = self._tournament(pop, scores)
                p2 = self._tournament(pop, scores)
                if self.rng.random() < crossover_rate:
                    c1, c2 = self._ordered_crossover(p1, p2)
                else:
                    c1, c2 = p1[:], p2[:]
                self._mutate(c1, mutation_rate)
                self._mutate(c2, mutation_rate)
                new_pop.append(c1)
                if len(new_pop) < population:
                    new_pop.append(c2)
            pop = new_pop[:population]

        return {
            "best_perm": best_perm,
            "best_decode": best_dec,
            "best_history": best_history,
            "avg_history": avg_history,
            "params": {
                "population": population,
                "generations": generations,
                "crossover_rate": crossover_rate,
                "mutation_rate": mutation_rate,
                "elite_count": elite_count,
            }
        }

    def _sample_params(self) -> Dict[str, float]:
        return {
            "population": self.rng.randint(30, 90),
            "generations": self.rng.randint(40, 100),
            "crossover_rate": self.rng.uniform(0.70, 0.95),
            "mutation_rate": self.rng.uniform(0.03, 0.25),
            "elite_count": self.rng.randint(2, 8),
        }

    def _params_to_x(self, p: Dict[str, float]) -> np.ndarray:
        return np.array([
            p["population"],
            p["generations"],
            p["crossover_rate"],
            p["mutation_rate"],
            p["elite_count"],
        ], dtype=float)

    def _x_to_params(self, x: np.ndarray) -> Dict[str, float]:
        return {
            "population": int(np.clip(round(x[0]), 30, 90)),
            "generations": int(np.clip(round(x[1]), 40, 120)),
            "crossover_rate": float(np.clip(x[2], 0.65, 0.98)),
            "mutation_rate": float(np.clip(x[3], 0.01, 0.30)),
            "elite_count": int(np.clip(round(x[4]), 1, 10)),
        }

    def _expected_improvement(self, X: np.ndarray, model: GaussianProcessRegressor, y_best: float) -> np.ndarray:
        mu, sigma = model.predict(X, return_std=True)
        sigma = np.maximum(sigma, 1e-9)
        z = (y_best - mu) / sigma
        return (y_best - mu) * norm.cdf(z) + sigma * norm.pdf(z)

    def solve_ga_only(self, generations: int = 120, population: int = 80) -> Dict[str, Any]:
        out = self.run_ga(
            population=population,
            generations=generations,
            crossover_rate=0.85,
            mutation_rate=0.10,
            elite_count=4,
        )
        dec = out["best_decode"]
        return {
            "method": "ga_only",
            "objective": dec.objective,
            "routes": dec.routes,
            "route_costs": dec.route_costs,
            "route_distance_km": dec.route_distance_km,
            "route_time_min": dec.route_time_min,
            "route_loads": dec.route_loads,
            "best_perm": out["best_perm"],
            "best_history": out["best_history"],
            "avg_history": out["avg_history"],
            "params": out["params"],
        }

    def tune_and_solve(self, bo_iterations: int, final_generations: int, final_population: int) -> Dict[str, Any]:
        X_list: List[np.ndarray] = []
        y_list: List[float] = []
        tested_params: List[Dict[str, float]] = []

        init_points = 4
        for _ in range(init_points):
            p = self._sample_params()
            out = self.run_ga(**p)
            score = out["best_decode"].objective
            X_list.append(self._params_to_x(p))
            y_list.append(score)
            tested_params.append(p)

        for _ in range(max(0, bo_iterations - init_points)):
            X = np.vstack(X_list)
            y = np.array(y_list)
            kernel = Matern(nu=2.5) + WhiteKernel(noise_level=1e-5)
            gp = GaussianProcessRegressor(kernel=kernel, normalize_y=True, random_state=0)
            gp.fit(X, y)

            candidates = np.vstack([self._params_to_x(self._sample_params()) for _ in range(60)])
            ei = self._expected_improvement(candidates, gp, float(np.min(y)))
            best_cand = candidates[int(np.argmax(ei))]
            p = self._x_to_params(best_cand)
            out = self.run_ga(**p)
            score = out["best_decode"].objective
            X_list.append(self._params_to_x(p))
            y_list.append(score)
            tested_params.append(p)

        best_idx = int(np.argmin(y_list))
        tuned = tested_params[best_idx].copy()
        tuned["generations"] = final_generations
        tuned["population"] = final_population

        final = self.run_ga(**tuned)
        dec = final["best_decode"]
        return {
            "method": "ga_bo",
            "best_params": tuned,
            "bo_history": [{"params": p, "objective": y} for p, y in zip(tested_params, y_list)],
            "objective": dec.objective,
            "routes": dec.routes,
            "route_costs": dec.route_costs,
            "route_distance_km": dec.route_distance_km,
            "route_time_min": dec.route_time_min,
            "route_loads": dec.route_loads,
            "best_perm": final["best_perm"],
            "best_history": final["best_history"],
            "avg_history": final["avg_history"],
        }


def save_solution(solution: Dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(solution, f, ensure_ascii=False, indent=2)