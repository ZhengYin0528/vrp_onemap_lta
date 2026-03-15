from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.benchmark import build_benchmark_summary, save_benchmark_summary
from src.case_generator import generate_case, generate_small_validation_case, save_case
from src.config import load_config
from src.cost_builder import build_adjusted_cost_matrix, build_nodes, build_route_matrices, save_matrix_summary
from src.ga_bo_solver import GABORouter, save_solution
from src.lta_client import LTAClient
from src.onemap_client import OneMapClient
from src.visualize import (
    build_route_html,
    build_route_png,
    plot_benchmark_comparison,
    plot_bo_history,
    plot_ga_convergence,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--use-live-api", action="store_true", help="Call live OneMap and LTA APIs")
    args = parser.parse_args()

    cfg = load_config(args.config)
    output_dir = Path(cfg.get("output_dir", "outputs"))
    output_dir.mkdir(parents=True, exist_ok=True)

    onemap = OneMapClient(
        email=cfg["onemap_email"],
        password=cfg["onemap_password"],
        cache_dir=output_dir / ".cache",
    )
    lta = LTAClient(account_key=cfg["lta_account_key"])

    # Main case
    case = generate_case(cfg, onemap, use_live_api=args.use_live_api)
    save_case(case, output_dir / "case.json")

    nodes = build_nodes(case)
    base = build_route_matrices(
        nodes,
        onemap_client=onemap,
        use_live_api=args.use_live_api,
        cache_dir=output_dir / ".cache",
    )
    snapshot = lta.fetch_snapshot(use_live_api=args.use_live_api)
    adjusted = build_adjusted_cost_matrix(base, nodes, snapshot, cfg["cost_weights"])
    save_matrix_summary(output_dir / "matrix_summary.json", nodes, adjusted)

    router = GABORouter(case, adjusted, cfg["cost_weights"], seed=cfg["ga_bo"].get("ga_seed", 42))

    greedy = router.solve_greedy()
    ga_only = router.solve_ga_only(
        generations=cfg["ga_bo"].get("final_ga_generations", 120),
        population=cfg["ga_bo"].get("final_ga_population", 80),
    )
    ga_bo = router.tune_and_solve(
        bo_iterations=cfg["ga_bo"].get("bo_iterations", 8),
        final_generations=cfg["ga_bo"].get("final_ga_generations", 120),
        final_population=cfg["ga_bo"].get("final_ga_population", 80),
    )

    # Small validation case
    small_case = generate_small_validation_case(cfg, onemap, use_live_api=args.use_live_api)
    save_case(small_case, output_dir / "small_case.json")

    small_nodes = build_nodes(small_case)
    small_base = build_route_matrices(
        small_nodes,
        onemap_client=onemap,
        use_live_api=args.use_live_api,
        cache_dir=output_dir / ".cache_small",
    )
    small_adjusted = build_adjusted_cost_matrix(small_base, small_nodes, snapshot, cfg["cost_weights"])
    small_router = GABORouter(small_case, small_adjusted, cfg["cost_weights"], seed=123)

    exact_small = small_router.solve_exact_small(max_bins=6)
    greedy_small = small_router.solve_greedy()
    ga_only_small = small_router.solve_ga_only(generations=80, population=40)
    ga_bo_small = small_router.tune_and_solve(bo_iterations=6, final_generations=80, final_population=40)

    small_validation = {
        "exact": exact_small,
        "greedy": {
            "objective": greedy_small["objective"],
            "total_distance_km": sum(greedy_small["route_distance_km"]),
            "total_time_min": sum(greedy_small["route_time_min"]),
        },
        "ga_only": {
            "objective": ga_only_small["objective"],
            "total_distance_km": sum(ga_only_small["route_distance_km"]),
            "total_time_min": sum(ga_only_small["route_time_min"]),
        },
        "ga_bo": {
            "objective": ga_bo_small["objective"],
            "total_distance_km": sum(ga_bo_small["route_distance_km"]),
            "total_time_min": sum(ga_bo_small["route_time_min"]),
        },
    }

    benchmark_summary = build_benchmark_summary(greedy, ga_only, ga_bo, exact_small=small_validation)
    save_benchmark_summary(benchmark_summary, output_dir / "benchmark_summary.json")

    metadata = {
        "api_mode": "live" if args.use_live_api else "offline",
        "travel_time_priority": True,
        "num_nodes": len(nodes),
        "num_bins": len(case["bins"]),
        "num_trucks": case["fleet"]["num_trucks"],
        "truck_capacity_liters": case["fleet"]["truck_capacity_liters"],
        "total_demand_liters": round(sum(b["demand_liters"] for b in case["bins"]), 2),
        "snapshot_source": snapshot.get("source", "unknown"),
    }

    solution_out = {
        "metadata": metadata,
        "greedy": greedy,
        "ga_only": ga_only,
        "ga_bo": ga_bo,
        "small_case_validation": small_validation,
    }
    save_solution(solution_out, output_dir / "best_solution.json")

    build_route_html(case, nodes, ga_bo, base["geometry"], output_dir / "route_map.html")
    build_route_png(case, nodes, ga_bo, base["geometry"], output_dir / "route_map.png")

    plot_ga_convergence(
        ga_only["best_history"],
        ga_only["avg_history"],
        output_dir / "ga_only_convergence.png",
        title="GA Only Convergence",
    )
    plot_ga_convergence(
        ga_bo["best_history"],
        ga_bo["avg_history"],
        output_dir / "ga_bo_convergence.png",
        title="GA + BO Convergence",
    )
    plot_bo_history(
        ga_bo["bo_history"],
        output_dir / "bo_tuning_progress.png",
        title="Bayesian Optimization Progress",
    )
    plot_benchmark_comparison(
        benchmark_summary,
        output_dir / "benchmark_comparison.png",
    )

    print(json.dumps({
        "status": "ok",
        "output_dir": str(output_dir.resolve()),
        "greedy_objective": greedy["objective"],
        "ga_only_objective": ga_only["objective"],
        "ga_bo_objective": ga_bo["objective"],
        "files": [
            str((output_dir / "case.json").resolve()),
            str((output_dir / "small_case.json").resolve()),
            str((output_dir / "best_solution.json").resolve()),
            str((output_dir / "benchmark_summary.json").resolve()),
            str((output_dir / "route_map.html").resolve()),
            str((output_dir / "route_map.png").resolve()),
            str((output_dir / "ga_only_convergence.png").resolve()),
            str((output_dir / "ga_bo_convergence.png").resolve()),
            str((output_dir / "bo_tuning_progress.png").resolve()),
            str((output_dir / "benchmark_comparison.png").resolve()),
        ],
    }, indent=2))


if __name__ == "__main__":
    main()