# GRIDMIND AI — Native Desktop Edition

GRIDMIND AI is a native energy-management desktop application built with Python and PySide6. It reads the included trained scikit-learn model and UCI household meter data, runs the forecasting and solar-first dispatch logic locally, and stores simulation history in SQLite. It does not start a web server, open a browser, or connect to physical grid equipment.

## Run in VS Code

1. Open the `GRIDMIND_AI` folder in VS Code.
2. Open **Terminal → New Terminal** and make sure the terminal is at the project root (the folder containing this README).
3. Use the project environment and install dependencies. This project uses Python 3.13 for its saved model. If `.venv` already exists, keep it and run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `.venv` does not exist, create it with Python 3.13 first:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. Launch the native application from the VS Code terminal at the project root:

```powershell
.\.venv\Scripts\python.exe main.py
```

This opens the desktop window directly. It does not open an HTML page, browser, or local web server. You can activate the environment and use `python main.py` instead if preferred.

The saved model and prepared hourly data are included. To retrain the model from the project root, run `python backend/train_model.py`; to rebuild the hourly CSV from the included original UCI text file, run `python backend/prepare_dataset.py`.

## Desktop modules

- **Energy dashboard:** demand, simulated solar output, battery SOC, grid import, renewable share, estimated carbon, historical demand, and forecast charts.
- **AI demand forecasting:** future 24-hour forecast, chronological validation actual-versus-predicted chart, and model metrics.
- **Microgrid control:** solar-first, battery-second, grid-last dispatch outlook and energy balance.
- **Scenario simulation:** adjust solar capacity, battery capacity, initial SOC, demand multiplier, and grid availability; compare dispatch with the baseline and save the run to SQLite.
- **GRIDMIND assistant:** a local rule-based assistant using current application state. It is not an LLM. Chat history is stored locally.
- **System monitoring:** simulated asset capacities, current dispatch state, and constraint alerts. Values are not physical telemetry.

Model inference, forecast evaluation, scenario runs, and chat responses run in background Qt threads so the interface stays responsive.

## Project layout

```text
GRIDMIND_AI/
  main.py
  requirements.txt
  frontend/                 # PySide6 windows, pages, charts, styles, workers
  backend/
    data_loader.py
    forecasting.py
    orchestration.py
    chatbot.py
    storage.py
    desktop_service.py
    train_model.py
    prepare_dataset.py
    data/
    models/
```

SQLite state is stored in `backend/data/gridmind.sqlite3`. The existing model is `backend/models/gridmind_demand.joblib`; its evaluation metadata is next to it in `performance.json`.

## Model and data

The forecaster is the existing `HistGradientBoostingRegressor`, trained on 34,589 hourly means aggregated from the UCI **Individual household electric power consumption** data. Its chronological holdout metrics are MAE 0.321 kW, RMSE 0.461 kW, MAPE 42.4%, and R² 0.575 on the household series. The training series covers December 2006 through November 2010.

Dataset: [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption), Georges Hebrail and Alice Berard, DOI [10.24432/C58K54](https://doi.org/10.24432/C58K54), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Operating assumptions and limitations

- Historical measured household demand is scaled to a representative demo-site load; the scaled series is not a second meter measurement.
- Solar output follows a deterministic daylight curve. Battery dispatch, grid import, renewable share, and carbon are modeled values.
- No live weather feed, physical sensors, utility connection, or hardware control is present.
- MAPE is sensitive to the small household loads in the source data; inspect MAE, RMSE, and R² with it.
- This edition runs locally as a native Qt desktop application and has no cloud deployment requirement.

## Existing web version archive

The prior React/FastAPI implementation and a pre-conversion SQLite backup are preserved in the sibling `GRIDMIND_AI_legacy_web_backup` folder. The native desktop launch path does not import or start that web stack.
