"""Modbus TCP server for the tank-control digital twin."""

import asyncio

from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from controller import OperatingMode, TankLevelController
from modbus_map import (
    DEVICE_ID,
    HOST,
    HR_ACTIVE_MODE,
    HR_ACTUAL_PUMP,
    HR_ALARM_CODE,
    HR_EMERGENCY_STOP,
    HR_HEARTBEAT,
    HR_INFLOW,
    HR_MANUAL_PUMP,
    HR_MODE,
    HR_OUTFLOW,
    HR_OUTLET_VALVE,
    HR_RESET_REQUEST,
    HR_SETPOINT,
    HR_SHUTDOWN_LATCHED,
    HR_TANK_LEVEL,
    PORT,
    decode_percent,
    encode_percent,
    initial_register_values,
)
from plant_model import TankPlant
from safety_system import SafetySystem


UPDATE_INTERVAL_SECONDS = 0.2
SIMULATION_TIME_STEP_SECONDS = 1.0


def determine_alarm_code(
    safety_result: dict[str, bool | str],
) -> int:
    """Convert the safety state into a Modbus alarm code."""

    trip_reason = safety_result["trip_reason"]

    if trip_reason == "EMERGENCY_STOP":
        return 3

    if trip_reason == "HIGH_HIGH_LEVEL":
        return 4

    if trip_reason == "LOW_LOW_LEVEL":
        return 5

    if safety_result["high_alarm"]:
        return 2

    if safety_result["low_alarm"]:
        return 1

    return 0


async def process_update_task(
    server: ModbusTcpServer,
) -> None:
    """Run the tank model and update the Modbus registers."""

    tank = TankPlant(
        capacity_litres=1000.0,
        maximum_inflow_lps=8.0,
        maximum_outflow_lps=10.0,
        level_percent=50.0,
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

    heartbeat = 0

    while True:
        command_registers = await server.async_getValues(
            device_id=DEVICE_ID,
            func_code=3,
            address=0,
            count=6,
        )

        mode_register = command_registers[HR_MODE]
        setpoint_register = command_registers[HR_SETPOINT]
        manual_pump_register = command_registers[
            HR_MANUAL_PUMP
        ]
        outlet_valve_register = command_registers[
            HR_OUTLET_VALVE
        ]
        emergency_stop_register = command_registers[
            HR_EMERGENCY_STOP
        ]
        reset_register = command_registers[
            HR_RESET_REQUEST
        ]

        if mode_register == 1:
            selected_mode = OperatingMode.AUTOMATIC
        else:
            selected_mode = OperatingMode.MANUAL

        controller.set_mode(selected_mode)

        controller.setpoint_percent = max(
            0.0,
            min(
                100.0,
                decode_percent(setpoint_register),
            ),
        )

        controller.manual_output_percent = max(
            0.0,
            min(
                100.0,
                decode_percent(manual_pump_register),
            ),
        )

        requested_outlet_valve = max(
            0.0,
            min(
                100.0,
                decode_percent(outlet_valve_register),
            ),
        )

        emergency_stop = (
            emergency_stop_register != 0
        )

        reset_request = reset_register != 0

        control_result = controller.update(
            measured_level_percent=tank.level_percent,
            time_step_seconds=SIMULATION_TIME_STEP_SECONDS,
        )

        requested_pump = float(
            control_result["pump_command_percent"]
        )

        safety_result = safety.evaluate(
            level_percent=tank.level_percent,
            emergency_stop=emergency_stop,
            equipment_fault=False,
            reset_request=reset_request,
        )

        if safety_result["reset_performed"]:
            controller.pi_controller.reset()

            await server.async_setValues(
                device_id=DEVICE_ID,
                func_code=3,
                address=HR_RESET_REQUEST,
                values=[0],
            )

            control_result = controller.update(
                measured_level_percent=tank.level_percent,
                time_step_seconds=(
                    SIMULATION_TIME_STEP_SECONDS
                ),
            )

            requested_pump = float(
                control_result["pump_command_percent"]
            )

        (
            actual_pump,
            actual_outlet_valve,
        ) = safety.apply_interlocks(
            requested_pump_percent=requested_pump,
            requested_outlet_valve_percent=(
                requested_outlet_valve
            ),
        )

        plant_result = tank.step(
            pump_command_percent=actual_pump,
            outlet_valve_percent=actual_outlet_valve,
            time_step_seconds=SIMULATION_TIME_STEP_SECONDS,
        )

        alarm_code = determine_alarm_code(safety_result)

        heartbeat = (heartbeat + 1) % 65536

        process_values = [
            encode_percent(plant_result["level_percent"]),
            encode_percent(actual_pump),
            encode_percent(plant_result["inflow_lps"]),
            encode_percent(plant_result["outflow_lps"]),
            alarm_code,
            int(safety_result["shutdown_latched"]),
            int(selected_mode == OperatingMode.AUTOMATIC),
            heartbeat,
        ]

        await server.async_setValues(
            device_id=DEVICE_ID,
            func_code=3,
            address=HR_TANK_LEVEL,
            values=process_values,
        )

        await asyncio.sleep(UPDATE_INTERVAL_SECONDS)


async def run_server() -> None:
    """Create and run the Modbus TCP server."""

    device = SimDevice(
        DEVICE_ID,
        SimData(
            0,
            datatype=DataType.REGISTERS,
            values=initial_register_values(),
        ),
    )

    server = ModbusTcpServer(
        device,
        address=(HOST, PORT),
    )

    process_task = asyncio.create_task(
        process_update_task(server)
    )

    print("Modbus TCP tank server started.")
    print(f"Address: {HOST}:{PORT}")
    print(f"Device ID: {DEVICE_ID}")
    print("Press Ctrl+C to stop the server.")

    try:
        await server.serve_forever()
    finally:
        process_task.cancel()

        try:
            await process_task
        except asyncio.CancelledError:
            pass

        await server.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("\nModbus TCP server stopped.")