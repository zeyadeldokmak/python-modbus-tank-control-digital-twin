"""Verify alarms, safety interlocks and injected tank faults."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from controller import OperatingMode, TankLevelController
from plant_model import TankPlant
from safety_system import SafetySystem


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIRECTORY = PROJECT_ROOT / "logs"
IMAGE_DIRECTORY = PROJECT_ROOT / "images"

LOG_DIRECTORY.mkdir(exist_ok=True)
IMAGE_DIRECTORY.mkdir(exist_ok=True)


def run_safety_simulation() -> pd.DataFrame:
    """Run normal, fault and emergency operating scenarios."""

    tank = TankPlant(
        capacity_litres=1000.0,
        maximum_inflow_lps=8.0,
        maximum_outflow_lps=10.0,
        level_percent=55.0,
    )

    controller = TankLevelController(
        setpoint_percent=60.0,
        manual_output_percent=35.0,
        mode=OperatingMode.AUTOMATIC,
    )

    safety = SafetySystem(
        low_alarm_threshold=35.0,
        low_low_trip_threshold=15.0,
        high_alarm_threshold=75.0,
        high_high_trip_threshold=80.0,
    )

    duration_seconds = 2400
    time_step_seconds = 1.0
    normal_outlet_valve_percent = 50.0

    records: list[dict[str, float | bool | str]] = []

    for time_seconds in np.arange(
        0.0,
        duration_seconds + time_step_seconds,
        time_step_seconds,
    ):
        # Injected pump failure.
        pump_fault_active = (
            300 <= time_seconds < 380
        )

        # Operator emergency-stop test.
        emergency_stop_active = (
            750 <= time_seconds < 800
        )

        # Biased sensor reports 30% below the real level.
        sensor_bias_fault_active = (
            1100 <= time_seconds < 1350
        )

        # Controlled reset requests after each trip.
        reset_request = time_seconds in (820, 1360)

        if sensor_bias_fault_active:
            measured_level_percent = max(
                0.0,
                tank.level_percent - 30.0,
            )
        else:
            measured_level_percent = tank.level_percent

        control_result = controller.update(
            measured_level_percent=measured_level_percent,
            time_step_seconds=time_step_seconds,
        )

        requested_pump_percent = float(
            control_result["pump_command_percent"]
        )

        safety_result = safety.evaluate(
            level_percent=tank.level_percent,
            emergency_stop=emergency_stop_active,
            equipment_fault=pump_fault_active,
            reset_request=reset_request,
        )

        # Clear stored PI action following a successful reset.
        if safety_result["reset_performed"]:
            controller.pi_controller.reset()

            control_result = controller.update(
                measured_level_percent=measured_level_percent,
                time_step_seconds=time_step_seconds,
            )

            requested_pump_percent = float(
                control_result["pump_command_percent"]
            )

        (
            interlocked_pump_percent,
            actual_outlet_valve_percent,
        ) = safety.apply_interlocks(
            requested_pump_percent=requested_pump_percent,
            requested_outlet_valve_percent=(
                normal_outlet_valve_percent
            ),
        )

        # A failed pump produces no flow regardless of its command.
        if pump_fault_active:
            actual_pump_percent = 0.0
        else:
            actual_pump_percent = interlocked_pump_percent

        plant_result = tank.step(
            pump_command_percent=actual_pump_percent,
            outlet_valve_percent=actual_outlet_valve_percent,
            time_step_seconds=time_step_seconds,
        )

        records.append(
            {
                "time_seconds": time_seconds,
                "true_level_percent": (
                    plant_result["level_percent"]
                ),
                "measured_level_percent": (
                    measured_level_percent
                ),
                "setpoint_percent": (
                    controller.setpoint_percent
                ),
                "requested_pump_percent": (
                    requested_pump_percent
                ),
                "actual_pump_percent": (
                    actual_pump_percent
                ),
                "outlet_valve_percent": (
                    actual_outlet_valve_percent
                ),
                "inflow_lps": plant_result["inflow_lps"],
                "outflow_lps": plant_result["outflow_lps"],
                "pump_fault": pump_fault_active,
                "sensor_bias_fault": (
                    sensor_bias_fault_active
                ),
                "emergency_stop": emergency_stop_active,
                "low_alarm": safety_result["low_alarm"],
                "low_low_trip": (
                    safety_result["low_low_trip"]
                ),
                "high_alarm": safety_result["high_alarm"],
                "high_high_trip": (
                    safety_result["high_high_trip"]
                ),
                "shutdown_latched": (
                    safety_result["shutdown_latched"]
                ),
                "trip_reason": safety_result["trip_reason"],
                "alarm_status": safety_result["alarm_status"],
                "reset_request": reset_request,
                "reset_performed": (
                    safety_result["reset_performed"]
                ),
            }
        )

    return pd.DataFrame(records)


def save_results(results: pd.DataFrame) -> None:
    """Save the Day 3 log and safety-response graph."""

    csv_path = LOG_DIRECTORY / "day3_safety_simulation.csv"
    image_path = IMAGE_DIRECTORY / "day3_safety_response.png"

    results.to_csv(csv_path, index=False)

    figure, axes = plt.subplots(
        nrows=4,
        ncols=1,
        figsize=(13, 12),
        sharex=True,
    )

    axes[0].plot(
        results["time_seconds"],
        results["true_level_percent"],
        color="royalblue",
        linewidth=2,
        label="True tank level",
    )

    axes[0].plot(
        results["time_seconds"],
        results["measured_level_percent"],
        color="orange",
        linestyle="--",
        label="Measured level",
    )

    axes[0].plot(
        results["time_seconds"],
        results["setpoint_percent"],
        color="black",
        linestyle=":",
        label="Setpoint",
    )

    axes[0].axhline(
        75,
        color="darkorange",
        linestyle="--",
        label="High alarm",
    )

    axes[0].axhline(
        80,
        color="red",
        linestyle="--",
        label="High-high trip",
    )

    axes[0].axhline(
        35,
        color="goldenrod",
        linestyle="--",
        label="Low alarm",
    )

    axes[0].axhline(
        15,
        color="darkred",
        linestyle="--",
        label="Low-low trip",
    )

    axes[0].set_ylabel("Level (%)")
    axes[0].set_ylim(0, 100)
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(
        loc="upper right",
        ncol=2,
        fontsize=8,
    )

    axes[1].plot(
        results["time_seconds"],
        results["requested_pump_percent"],
        color="purple",
        label="Requested pump",
    )

    axes[1].plot(
        results["time_seconds"],
        results["actual_pump_percent"],
        color="green",
        linestyle="--",
        label="Actual pump",
    )

    axes[1].set_ylabel("Pump output (%)")
    axes[1].set_ylim(0, 105)
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    axes[2].plot(
        results["time_seconds"],
        results["outlet_valve_percent"],
        color="teal",
        label="Outlet valve",
    )

    axes[2].set_ylabel("Valve position (%)")
    axes[2].set_ylim(0, 105)
    axes[2].grid(True, alpha=0.3)
    axes[2].legend()

    axes[3].step(
        results["time_seconds"],
        results["pump_fault"].astype(int),
        where="post",
        label="Pump fault",
    )

    axes[3].step(
        results["time_seconds"],
        results["emergency_stop"].astype(int) * 2,
        where="post",
        label="Emergency stop",
    )

    axes[3].step(
        results["time_seconds"],
        results["sensor_bias_fault"].astype(int) * 3,
        where="post",
        label="Sensor bias",
    )

    axes[3].step(
        results["time_seconds"],
        results["low_alarm"].astype(int) * 4,
        where="post",
        label="Low alarm",
    )

    axes[3].step(
        results["time_seconds"],
        results["high_alarm"].astype(int) * 5,
        where="post",
        label="High alarm",
    )

    axes[3].step(
        results["time_seconds"],
        results["shutdown_latched"].astype(int) * 6,
        where="post",
        color="red",
        linewidth=2,
        label="Shutdown latched",
    )

    axes[3].set_xlabel("Time (seconds)")
    axes[3].set_ylabel("Event indicators")
    axes[3].set_yticks([])
    axes[3].grid(True, alpha=0.3)
    axes[3].legend(
        loc="upper right",
        ncol=3,
        fontsize=8,
    )

    for axis in axes:
        axis.axvspan(
            300,
            380,
            color="grey",
            alpha=0.12,
        )

        axis.axvspan(
            750,
            800,
            color="red",
            alpha=0.10,
        )

        axis.axvspan(
            1100,
            1350,
            color="orange",
            alpha=0.10,
        )

    figure.suptitle(
        "Tank Safety System: Alarms, Interlocks and Fault Injection"
    )

    figure.tight_layout()
    figure.savefig(image_path, dpi=180)
    plt.close(figure)

    emergency_trip_detected = (
        results["trip_reason"]
        == "EMERGENCY_STOP"
    ).any()

    high_high_trip_detected = (
        results["trip_reason"]
        == "HIGH_HIGH_LEVEL"
    ).any()

    print("Day 3 safety simulation completed successfully.")
    print(
        "Pump fault detected:       "
        f"{results['pump_fault'].any()}"
    )
    print(
        "Low-level alarm detected:  "
        f"{results['low_alarm'].any()}"
    )
    print(
        "Emergency trip detected:   "
        f"{emergency_trip_detected}"
    )
    print(
        "High-high trip detected:   "
        f"{high_high_trip_detected}"
    )
    print(
        "Final shutdown latched:    "
        f"{results['shutdown_latched'].iloc[-1]}"
    )
    print(
        "Final tank level:          "
        f"{results['true_level_percent'].iloc[-1]:.2f}%"
    )
    print(f"CSV log:                    {csv_path}")
    print(f"Graph:                      {image_path}")


if __name__ == "__main__":
    simulation_results = run_safety_simulation()
    save_results(simulation_results)