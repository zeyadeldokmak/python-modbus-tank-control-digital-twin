"""Self-checking Modbus TCP client for the tank digital twin."""

import time

from pymodbus.client import ModbusTcpClient

from modbus_map import (
    ALARM_NAMES,
    DEVICE_ID,
    HOST,
    HR_ACTIVE_MODE,
    HR_ACTUAL_PUMP,
    HR_ALARM_CODE,
    HR_EMERGENCY_STOP,
    HR_HEARTBEAT,
    HR_INFLOW,
    HR_MODE,
    HR_OUTFLOW,
    HR_OUTLET_VALVE,
    HR_RESET_REQUEST,
    HR_SETPOINT,
    HR_SHUTDOWN_LATCHED,
    HR_TANK_LEVEL,
    PORT,
    REGISTER_COUNT,
    decode_percent,
    encode_percent,
)


def read_registers(
    client: ModbusTcpClient,
) -> list[int]:
    """Read and validate the complete register table."""

    response = client.read_holding_registers(
        address=0,
        count=REGISTER_COUNT,
        device_id=DEVICE_ID,
    )

    if response.isError():
        raise RuntimeError(
            f"Modbus read failed: {response}"
        )

    return response.registers


def display_process_values(
    registers: list[int],
) -> None:
    """Display decoded process information."""

    alarm_code = registers[HR_ALARM_CODE]

    print()
    print("Current tank process values")
    print("---------------------------")
    print(
        "Tank level:      "
        f"{decode_percent(registers[HR_TANK_LEVEL]):.2f}%"
    )
    print(
        "Pump output:     "
        f"{decode_percent(registers[HR_ACTUAL_PUMP]):.2f}%"
    )
    print(
        "Inflow:          "
        f"{decode_percent(registers[HR_INFLOW]):.2f} L/s"
    )
    print(
        "Outflow:         "
        f"{decode_percent(registers[HR_OUTFLOW]):.2f} L/s"
    )
    print(
        "Mode:            "
        f"{'AUTOMATIC' if registers[HR_ACTIVE_MODE] else 'MANUAL'}"
    )
    print(
        "Alarm:           "
        f"{ALARM_NAMES.get(alarm_code, 'UNKNOWN')}"
    )
    print(
        "Shutdown:        "
        f"{bool(registers[HR_SHUTDOWN_LATCHED])}"
    )
    print(
        "Heartbeat:       "
        f"{registers[HR_HEARTBEAT]}"
    )


def write_register(
    client: ModbusTcpClient,
    address: int,
    value: int,
) -> None:
    """Write one register and check the response."""

    response = client.write_register(
        address=address,
        value=value,
        device_id=DEVICE_ID,
    )

    if response.isError():
        raise RuntimeError(
            f"Modbus write failed at address {address}"
        )


def run_test() -> None:
    """Run the Modbus communication verification."""

    errors = 0

    client = ModbusTcpClient(
        host=HOST,
        port=PORT,
        timeout=3,
    )

    if not client.connect():
        print("FAIL: Could not connect to the Modbus server.")
        print("Start modbus_server.py in the first terminal.")
        return

    print("PASS: Connected to the Modbus TCP server.")

    try:
        initial_registers = read_registers(client)
        initial_heartbeat = initial_registers[HR_HEARTBEAT]

        display_process_values(initial_registers)

        # Select automatic mode and send a 65% setpoint.
        write_register(client, HR_MODE, 1)
        write_register(
            client,
            HR_SETPOINT,
            encode_percent(65.0),
        )
        write_register(
            client,
            HR_OUTLET_VALVE,
            encode_percent(50.0),
        )

        time.sleep(2)

        automatic_registers = read_registers(client)

        if automatic_registers[HR_ACTIVE_MODE] == 1:
            print("PASS: Automatic mode command accepted.")
        else:
            print("FAIL: Automatic mode was not accepted.")
            errors += 1

        if (
            automatic_registers[HR_SETPOINT]
            == encode_percent(65.0)
        ):
            print("PASS: 65% setpoint written successfully.")
        else:
            print("FAIL: Setpoint register is incorrect.")
            errors += 1

        if (
            automatic_registers[HR_HEARTBEAT]
            != initial_heartbeat
        ):
            print("PASS: Server heartbeat is updating.")
        else:
            print("FAIL: Server heartbeat did not update.")
            errors += 1

        # Test emergency-stop handling.
        write_register(client, HR_EMERGENCY_STOP, 1)
        time.sleep(1)

        emergency_registers = read_registers(client)

        if (
            emergency_registers[HR_ACTUAL_PUMP] == 0
            and emergency_registers[
                HR_SHUTDOWN_LATCHED
            ] == 1
        ):
            print(
                "PASS: Emergency stop disabled the pump "
                "and latched shutdown."
            )
        else:
            print("FAIL: Emergency-stop response incorrect.")
            errors += 1

        # Remove emergency stop and request a controlled reset.
        write_register(client, HR_EMERGENCY_STOP, 0)
        write_register(client, HR_RESET_REQUEST, 1)

        time.sleep(1)

        reset_registers = read_registers(client)

        if reset_registers[HR_SHUTDOWN_LATCHED] == 0:
            print("PASS: Controlled reset cleared shutdown.")
        else:
            print("FAIL: Shutdown remained latched.")
            errors += 1

        # Restore the normal 60% setpoint.
        write_register(
            client,
            HR_SETPOINT,
            encode_percent(60.0),
        )

        display_process_values(reset_registers)

        if errors == 0:
            print()
            print(
                "PASS: All Modbus TCP tests completed "
                "successfully."
            )
        else:
            print()
            print(
                f"FAIL: {errors} Modbus TCP test(s) failed."
            )

    finally:
        client.close()


if __name__ == "__main__":
    run_test()