from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import folium
import matplotlib.pyplot as plt

Coord = Tuple[float, float]


def build_route_html(case: Dict[str, Any], nodes: List[Dict[str, Any]], solution: Dict[str, Any], geometry: Dict[str, Dict[str, Any]], output_path: str | Path) -> None:
    center = [case["depot"]["lat"], case["depot"]["lon"]]
    m = folium.Map(location=center, zoom_start=13)

    folium.Marker(
        center,
        popup=f"Depot<br>{case['depot'].get('address', '')}",
        icon=folium.Icon(color="black")
    ).add_to(m)

    folium.Marker(
        [case["incinerator"]["lat"], case["incinerator"]["lon"]],
        popup=f"Incinerator<br>{case['incinerator'].get('address', '')}",
        icon=folium.Icon(color="red")
    ).add_to(m)

    for b in case["bins"]:
        folium.CircleMarker(
            [b["lat"], b["lon"]],
            radius=5,
            popup=f"{b['id']}<br>{b.get('address', '')}<br>demand={b['demand_liters']}L",
            fill=True
        ).add_to(m)

    colors = ["blue", "green", "purple", "orange", "cadetblue", "darkred"]

    for idx, route in enumerate(solution["routes"]):
        color = colors[idx % len(colors)]
        for a, b in zip(route[:-1], route[1:]):
            edge = geometry.get(f"{a}->{b}", {})
            coords = edge.get("coords") or [
                (nodes[a]["lat"], nodes[a]["lon"]),
                (nodes[b]["lat"], nodes[b]["lon"]),
            ]
            is_fallback = edge.get("is_fallback", True)

            popup_text = f"Truck {idx+1}: {nodes[a]['id']} → {nodes[b]['id']}"
            if is_fallback:
                popup_text += "<br><b>Fallback segment (not true road geometry)</b>"

            folium.PolyLine(
                coords,
                color=color,
                weight=2.5 if not is_fallback else 1.5,
                opacity=0.8 if not is_fallback else 0.4,
                dash_array="8,8" if is_fallback else None,
                popup=popup_text,
            ).add_to(m)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_path))


def build_route_png(case: Dict[str, Any], nodes: List[Dict[str, Any]], solution: Dict[str, Any], geometry: Dict[str, Dict[str, Any]], output_path: str | Path) -> None:
    plt.figure(figsize=(10, 8))
    plt.scatter(case["depot"]["lon"], case["depot"]["lat"], marker="s", s=120, label="Depot")
    plt.scatter(case["incinerator"]["lon"], case["incinerator"]["lat"], marker="^", s=120, label="Incinerator")

    for b in case["bins"]:
        plt.scatter(b["lon"], b["lat"], s=20)
        plt.text(b["lon"], b["lat"], b["id"], fontsize=6)

    colors = ["C0", "C1", "C2", "C3", "C4", "C5"]

    for idx, route in enumerate(solution["routes"]):
        color = colors[idx % len(colors)]
        for a, b in zip(route[:-1], route[1:]):
            edge = geometry.get(f"{a}->{b}", {})
            coords = edge.get("coords") or [
                (nodes[a]["lat"], nodes[a]["lon"]),
                (nodes[b]["lat"], nodes[b]["lon"]),
            ]
            is_fallback = edge.get("is_fallback", True)

            lats = [c[0] for c in coords]
            lons = [c[1] for c in coords]

            if is_fallback:
                plt.plot(lons, lats, linestyle="--", linewidth=0.8, alpha=0.4)
            else:
                plt.plot(lons, lats, linewidth=1.0)

    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Waste Fleet Routes")
    plt.legend()
    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()

def plot_ga_convergence(best_history: List[float], avg_history: List[float], output_path: str | Path, title: str = "GA Convergence") -> None:
    plt.figure(figsize=(8, 5))
    plt.plot(range(1, len(best_history) + 1), best_history, label="Best cost")
    plt.plot(range(1, len(avg_history) + 1), avg_history, label="Average cost")
    plt.xlabel("Generation")
    plt.ylabel("Cost")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_bo_history(bo_history: List[Dict[str, Any]], output_path: str | Path, title: str = "BO Tuning Progress") -> None:
    objs = [x["objective"] for x in bo_history]
    running_best = []
    cur = float("inf")
    for v in objs:
        cur = min(cur, v)
        running_best.append(cur)

    plt.figure(figsize=(8, 5))
    plt.plot(range(1, len(objs) + 1), objs, marker="o", label="Trial objective")
    plt.plot(range(1, len(running_best) + 1), running_best, label="Best so far")
    plt.xlabel("BO Trial")
    plt.ylabel("Objective")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()

def plot_bo_history(bo_history: List[Dict[str, Any]], output_path: str | Path, title: str = "BO Tuning Progress") -> None:
    objs = [x["objective"] for x in bo_history]
    running_best = []
    cur = float("inf")
    for v in objs:
        cur = min(cur, v)
        running_best.append(cur)

    plt.figure(figsize=(8, 5))
    plt.plot(range(1, len(objs) + 1), objs, marker="o", label="Trial objective")
    plt.plot(range(1, len(running_best) + 1), running_best, label="Best so far")
    plt.xlabel("BO Trial")
    plt.ylabel("Objective")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_ga_convergence(best_history: List[float], avg_history: List[float], output_path: str | Path, title: str = "GA Convergence") -> None:
    plt.figure(figsize=(8, 5))
    plt.plot(range(1, len(best_history) + 1), best_history, label="Best cost")
    plt.plot(range(1, len(avg_history) + 1), avg_history, label="Average cost")
    plt.xlabel("Generation")
    plt.ylabel("Cost")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_benchmark_comparison(summary: Dict[str, Any], output_path: str | Path) -> None:
    methods = ["Greedy", "GA Only", "GA + BO"]
    obj = [
        summary["main_case"]["greedy"]["objective"],
        summary["main_case"]["ga_only"]["objective"],
        summary["main_case"]["ga_bo"]["objective"],
    ]
    dist = [
        summary["main_case"]["greedy"]["total_distance_km"],
        summary["main_case"]["ga_only"]["total_distance_km"],
        summary["main_case"]["ga_bo"]["total_distance_km"],
    ]
    tmin = [
        summary["main_case"]["greedy"]["total_time_min"],
        summary["main_case"]["ga_only"]["total_time_min"],
        summary["main_case"]["ga_bo"]["total_time_min"],
    ]

    plt.figure(figsize=(10, 6))
    x = np.arange(len(methods))
    width = 0.25

    plt.bar(x - width, obj, width, label="Objective")
    plt.bar(x, dist, width, label="Distance (km)")
    plt.bar(x + width, tmin, width, label="Time (min)")

    plt.xticks(x, methods)
    plt.ylabel("Value")
    plt.title("Benchmark Comparison")
    plt.legend()
    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=200)
    plt.close()