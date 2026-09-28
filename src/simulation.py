"""Run and plot the Day 1 open-loop tank simulation."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plant_model import TankPlant


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIRECTORY = PROJECT_ROOT / "logs"
IMAGE_DIRECTORY = PROJECT_ROOT / "images"

LOG_DIRECTORY.mkdir(exist_ok=True)
IMAGE_DIRECTORY.mkdir(exist_ok=True)


def run_simulation() -> pd.DataFrame:
    """Run a fixed-command open-loop tank simulation."""

    tank = TankPlant(
        capacity_litres=1000.0,
        maximum_inflow_lps=8.0,
        maximum_outflow_lps=10.0,
        level_percent=20.0,
    )

    duration_seconds = 600
    time_step_seconds = 1.0

    pump_command_percent = 50.0
    outlet_valve_percent = 50.0

    records: list[dict[str, float]] = []

    for time_seconds in np.arange(
        0.0,
        duration_seconds + time_step_seconds,
        time_step_seconds,
    ):
        result = tank.step(
            pump_command_percent=pump_command_percent,
            outlet_valve_percent=outlet_valve_percent,
            time_step_seconds=time_step_seconds,
        )

        records.append(
            {
                "time_seconds": time_seconds,
                **result,
            }
        )

    return pd.DataFrame(records)


def save_results(results: pd.DataFrame) -> None:
    """Save the simulation data and response graph."""

    csv_path = LOG_DIRECTORY / "day1_plant_simulation.csv"
    image_path = IMAGE_DIRECTORY / "day1_tank_response.png"

    results.to_csv(csv_path, index=False)

    figure, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(10, 7),
        sharex=True,
    )

    axes[0].plot(
        results["time_seconds"],
        results["level_percent"],
        color="royalblue",
        linewidth=2,
        label="Tank level",
    )

    axes[0].set_ylabel("Level (%)")
    axes[0].set_ylim(0, 100)
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(
        results["time_seconds"],
        results["inflow_lps"],
        label="Inflow",
        color="seagreen",
    )

    axes[1].plot(
        results["time_seconds"],
        results["outflow_lps"],
        label="Outflow",
        color="darkorange",
    )

    axes[1].set_xlabel("Time (seconds)")
    axes[1].set_ylabel("Flow (L/s)")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    figure.suptitle("Open-Loop Tank Process Simulation")
    figure.tight_layout()
    figure.savefig(image_path, dpi=180)
    plt.close(figure)

    print("Simulation completed successfully.")
    print(f"Initial level: {results['level_percent'].iloc[0]:.2f}%")
    print(f"Final level:   {results['level_percent'].iloc[-1]:.2f}%")
    print(f"CSV log:       {csv_path}")
    print(f"Graph:         {image_path}")


if __name__ == "__main__":
    simulation_results = run_simulation()
    save_results(simulation_results)