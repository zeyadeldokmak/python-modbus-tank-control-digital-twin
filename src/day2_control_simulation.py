"""Simulate manual and automatic PI tank-level control."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from controller import OperatingMode, TankLevelController
from plant_model import TankPlant


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIRECTORY = PROJECT_ROOT / "logs"
IMAGE_DIRECTORY = PROJECT_ROOT / "images"

LOG_DIRECTORY.mkdir(exist_ok=True)
IMAGE_DIRECTORY.mkdir(exist_ok=True)


def run_control_simulation() -> pd.DataFrame:
    """Run the manual-to-automatic control simulation."""

    tank = TankPlant(
        capacity_litres=1000.0,
        maximum_inflow_lps=8.0,
        maximum_outflow_lps=10.0,
        level_percent=20.0,
    )

    controller = TankLevelController(
        setpoint_percent=60.0,
        manual_output_percent=35.0,
        mode=OperatingMode.MANUAL,
    )

    duration_seconds = 1400
    automatic_start_seconds = 200
    time_step_seconds = 1.0
    outlet_valve_percent = 50.0

    records: list[dict[str, float | str]] = []

    for time_seconds in np.arange(
        0.0,
        duration_seconds + time_step_seconds,
        time_step_seconds,
    ):
        if time_seconds >= automatic_start_seconds:
            controller.set_mode(OperatingMode.AUTOMATIC)

        control_result = controller.update(
            measured_level_percent=tank.level_percent,
            time_step_seconds=time_step_seconds,
        )

        plant_result = tank.step(
            pump_command_percent=float(
                control_result["pump_command_percent"]
            ),
            outlet_valve_percent=outlet_valve_percent,
            time_step_seconds=time_step_seconds,
        )

        records.append(
            {
                "time_seconds": time_seconds,
                "mode": control_result["mode"],
                "setpoint_percent": (
                    control_result["setpoint_percent"]
                ),
                "level_percent": (
                    plant_result["level_percent"]
                ),
                "error_percent": (
                    control_result["error_percent"]
                ),
                "pump_command_percent": (
                    control_result["pump_command_percent"]
                ),
                "proportional_term": (
                    control_result["proportional_term"]
                ),
                "integral_term": (
                    control_result["integral_term"]
                ),
                "inflow_lps": plant_result["inflow_lps"],
                "outflow_lps": plant_result["outflow_lps"],
                "net_flow_lps": plant_result["net_flow_lps"],
                "outlet_valve_percent": (
                    outlet_valve_percent
                ),
            }
        )

    return pd.DataFrame(records)


def save_results(results: pd.DataFrame) -> None:
    """Save the Day 2 CSV log and control-response graph."""

    csv_path = LOG_DIRECTORY / "day2_pi_control.csv"
    image_path = IMAGE_DIRECTORY / "day2_pi_control.png"

    results.to_csv(csv_path, index=False)

    figure, axes = plt.subplots(
        nrows=3,
        ncols=1,
        figsize=(11, 9),
        sharex=True,
    )

    axes[0].plot(
        results["time_seconds"],
        results["level_percent"],
        color="royalblue",
        linewidth=2,
        label="Tank level",
    )

    axes[0].plot(
        results["time_seconds"],
        results["setpoint_percent"],
        color="black",
        linestyle="--",
        label="Setpoint",
    )

    axes[0].set_ylabel("Level (%)")
    axes[0].set_ylim(0, 100)
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(
        results["time_seconds"],
        results["pump_command_percent"],
        color="purple",
        linewidth=2,
        label="Pump command",
    )

    axes[1].set_ylabel("Pump output (%)")
    axes[1].set_ylim(0, 100)
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    axes[2].plot(
        results["time_seconds"],
        results["inflow_lps"],
        color="seagreen",
        label="Inflow",
    )

    axes[2].plot(
        results["time_seconds"],
        results["outflow_lps"],
        color="darkorange",
        label="Outflow",
    )

    axes[2].set_xlabel("Time (seconds)")
    axes[2].set_ylabel("Flow (L/s)")
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()

    for axis in axes:
        axis.axvline(
            x=200,
            color="red",
            linestyle=":",
            linewidth=2,
            label="Automatic mode starts",
        )

    axes[0].text(
        20,
        92,
        "MANUAL",
        color="darkred",
        fontweight="bold",
    )

    axes[0].text(
        220,
        92,
        "AUTOMATIC",
        color="darkgreen",
        fontweight="bold",
    )

    figure.suptitle(
        "Tank Level Control: Manual and Automatic PI Modes"
    )

    figure.tight_layout()
    figure.savefig(image_path, dpi=180)
    plt.close(figure)

    automatic_results = results[
        results["mode"] == OperatingMode.AUTOMATIC.value
    ]

    final_level = results["level_percent"].iloc[-1]
    final_output = results["pump_command_percent"].iloc[-1]
    maximum_level = automatic_results["level_percent"].max()

    print("Day 2 control simulation completed successfully.")
    print(f"Final tank level:  {final_level:.2f}%")
    print(f"Final pump output: {final_output:.2f}%")
    print(f"Maximum level:     {maximum_level:.2f}%")
    print(f"CSV log:           {csv_path}")
    print(f"Graph:             {image_path}")


if __name__ == "__main__":
    simulation_results = run_control_simulation()
    save_results(simulation_results)