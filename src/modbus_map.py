"""Modbus TCP register definitions for the tank digital twin."""

HOST = "127.0.0.1"
PORT = 5020
DEVICE_ID = 1

PERCENT_SCALE = 100

# Writable command registers.
HR_MODE = 0
HR_SETPOINT = 1
HR_MANUAL_PUMP = 2
HR_OUTLET_VALVE = 3
HR_EMERGENCY_STOP = 4
HR_RESET_REQUEST = 5

# Process-value registers.
HR_TANK_LEVEL = 10
HR_ACTUAL_PUMP = 11
HR_INFLOW = 12
HR_OUTFLOW = 13
HR_ALARM_CODE = 14
HR_SHUTDOWN_LATCHED = 15
HR_ACTIVE_MODE = 16
HR_HEARTBEAT = 17

REGISTER_COUNT = 18

ALARM_NAMES = {
    0: "NORMAL",
    1: "LOW LEVEL",
    2: "HIGH LEVEL",
    3: "EMERGENCY STOP",
    4: "HIGH-HIGH LEVEL TRIP",
    5: "LOW-LOW LEVEL TRIP",
}


def encode_percent(value: float) -> int:
    """Convert a percentage or flow value to a Modbus register."""

    limited_value = max(0.0, min(value, 655.35))
    return int(round(limited_value * PERCENT_SCALE))


def decode_percent(register_value: int) -> float:
    """Convert a scaled Modbus register into a decimal value."""

    return register_value / PERCENT_SCALE


def initial_register_values() -> list[int]:
    """Return the initial register-table contents."""

    registers = [0] * REGISTER_COUNT

    registers[HR_MODE] = 1
    registers[HR_SETPOINT] = encode_percent(60.0)
    registers[HR_MANUAL_PUMP] = encode_percent(35.0)
    registers[HR_OUTLET_VALVE] = encode_percent(50.0)
    registers[HR_EMERGENCY_STOP] = 0
    registers[HR_RESET_REQUEST] = 0

    return registers