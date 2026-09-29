# Low-Cost Irrigation Prediction

> Work in Progress

This project explores whether low-cost weather variables and historical irrigation records can help predict whether a standard irrigation event will occur on the following day.

It is an exploratory machine-learning project built with Python, pandas, and a real precision-irrigation field-trial dataset. The project is incomplete and has not been validated for operational agricultural decision-making.

## Project scope

The current analysis focuses on **Zone 1** and reframes the task as a binary classification problem:

- **Input:** Daily weather variables and rolling weather features
- **Target:** Whether a standard irrigation event occurs on the next day (`0` = no, `1` = yes)
- **Training period:** February–May 2025
- **Primary test period:** June–July 2025
- **Late-season review period:** August–September 2025

The project currently includes exploratory data analysis, target construction, chronological data splitting, and initial feature engineering. Model training, evaluation, and validation are still in progress.

## Data source and attribution

This project uses processed data from:

> *Soil Moisture, Irrigation Actuator and Weather Dataset from a Multi-Sector Precision-Irrigation Field Trial (Arnesano, Apulia, Italy, 2025).*

The source dataset documents five irrigation sectors monitored between February and September 2025 in Arnesano, Apulia, Italy. It includes sensor telemetry, reconstructed irrigation events, weather variables, and processed per-sector tables.

The source data provider's documentation and processing pipeline are included for reference. This repository does **not** claim ownership of the original dataset, field trial, irrigation-event reconstruction pipeline, or underlying farm telemetry.

Publication status, DOI, and contributor information for the source dataset have not been independently verified in this repository.

## Current analysis

The current Notebook:

1. Loads the merged Zone 1 dataset.
2. Checks data shape, column types, missing values, and irrigation activity.
3. Uses reconstructed `standard_irrigation` events to create a next-day irrigation label.
4. Aggregates weather data to a daily level.
5. Creates weather-based features, including:
   - temperature
   - humidity
   - rainfall
   - pressure
   - wind speed
   - solar radiation
   - 3-day and 7-day rainfall totals
   - rolling temperature, humidity, and radiation averages
6. Uses chronological train/test splits rather than random splitting.
7. Examines late-season data quality and distribution changes.

## Important data-quality findings

The exploratory analysis identified limitations that affect modelling:

- Zone 1 standard irrigation events stop after 13 July 2025, while other sectors continue to contain irrigation events later in the season.
- The August–September Zone 1 period contains no positive standard-irrigation labels, so it is not suitable as the main binary-classification test set.
- Soil-moisture values show an abnormal shift to `-20` after 6 September 2025 in Zone 1.
- High sensor availability does not necessarily indicate usable sensor values.
- The dataset is relatively small for machine learning: the current feature-engineered daily dataset contains roughly 224 usable observations.

These issues are treated as unresolved analytical limitations, not as evidence that irrigation was unnecessary during the later period.

## Repository structure

```text
├── notebooks/
│   └── 01_data_exploration.ipynb
│
├── data/
│   ├── merged/
│   │   └── dataset_zone_1.csv ... dataset_zone_5.csv
│   └── irrigation_events/
│       ├── final_irrigation_events.csv
│       └── sector_statistics_report.csv
│
├── source_dataset_documentation/
│   ├── README_source_dataset.md
│   ├── DATA_DICTIONARY.md
│   └── processing_pipeline/
│       ├── 00_irrigation_actuators_cleaning.py
│       ├── 01_merge_datasets.py
│       ├── 02_preprocessing.py
│       └── config.py
│
└── README.md
```

Large raw telemetry files are intentionally excluded from this repository because they exceed GitHub's normal upload limits. The included data files are sufficient to reproduce the current exploratory Notebook.

## Run the Notebook

```bash
python -m venv .venv
source .venv/bin/activate
pip install pandas matplotlib numpy jupyter
jupyter notebook
```

Then open:

```text
notebooks/01_data_exploration.ipynb
```

## Planned next steps

- Complete a majority-class baseline.
- Train a logistic-regression classifier.
- Evaluate precision, recall, F1 score, and confusion matrix.
- Compare results with a second model.
- Test whether weather-only features provide useful predictive signal.
- Decide how to handle the Zone 1 late-season regime change.
- Extend the analysis to other irrigation sectors.
- Document all modelling choices and limitations.

## Limitations and responsible use

This repository is for learning and exploratory research purposes only.

The current work should not be used to automate irrigation, determine water application rates, control agricultural equipment, or make production-farm decisions. It has not been validated against agronomic outcomes, operational constraints, or independent field data.
