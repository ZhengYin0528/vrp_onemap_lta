# VRP OneMap LTA: Waste Route Optimisation

This project develops an AI-inspired route optimisation pipeline for waste collection in Singapore. It combines a Genetic Algorithm (GA) with Bayesian Optimisation (BO) to generate efficient collection routes while incorporating map and traffic-related data from OneMap and LTA-based sources.

## Project Objective

The goal of this project is to optimise waste collection truck routes by improving the visiting sequence of bins and reducing operational cost. The model considers factors such as travel time, distance, penalties, and fleet constraints.

## Features

* Genetic Algorithm for route optimisation
* Bayesian Optimisation for tuning GA settings
* Configurable study area and fleet settings
* OneMap and LTA data integration
* Route visualisation and benchmark comparison
* Output of route maps, convergence plots, and solution summaries

## Project Structure

```text
vrp_onemap_lta/
├── src/
│   ├── benchmark.py
│   ├── case_generator.py
│   ├── config.py
│   ├── cost_builder.py
│   ├── ga_bo_solver.py
│   ├── lta_client.py
│   ├── onemap_client.py
│   ├── utils.py
│   └── visualize.py
├── outputs/
│   ├── benchmark_comparison.png
│   ├── benchmark_summary.json
│   ├── best_solution.json
│   ├── bo_tuning_progress.png
│   ├── case.json
│   ├── ga_bo_convergence.png
│   ├── ga_only_convergence.png
│   ├── matrix_summary.json
│   ├── route_map.html
│   ├── route_map.png
│   └── small_case.json
├── config_template.json
├── requirements.txt
└── run_pipeline.py
```

## Requirements

* Python 3.10 or above recommended
* Required Python packages are listed in `requirements.txt`

Install dependencies using:

```bash
pip install -r requirements.txt
```

## Configuration

This repository does not include the real local credentials file.

To run the project:

1. Copy `config_template.json`
2. Rename the copied file to `config.json`
3. Replace the placeholder values with your own credentials and settings

Example:

```bash
cp config_template.json config.json
```

Then edit `config.json` with your actual:

* OneMap email
* OneMap password
* LTA account key

## How to Run

Run the full pipeline with:

```bash
python run_pipeline.py
```

## Outputs

The pipeline generates results in the `outputs/` folder, including:

* route maps
* convergence plots
* benchmark comparison plots
* solution summaries in JSON format

These outputs help evaluate the performance of the optimisation model and visualise the final route design.

## Notes

* `config.json` is intentionally excluded from the repository for security reasons
* `config_template.json` is provided as a safe reference file
* Generated outputs included in this repository are sample results from the current project setup
* The model is based on estimated or simulated waste bin locations for research and prototyping purposes

## Research Context

This project was developed as part of an undergraduate UROP-related study on sustainable and AI-inspired route optimisation for waste collection. The work focuses on methodology development rather than full operational deployment.

## Author

Tong Zheng Yin
National University of Singapore
