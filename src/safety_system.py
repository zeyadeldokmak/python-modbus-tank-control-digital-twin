"""Alarm and safety-interlock logic for the tank digital twin."""

from dataclasses import dataclass
from enum import Enum


class TripReason(str, Enum):
    """Possible causes of an emergency shutdown."""

    NONE = "NONE"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    HIGH_HIGH_LEVEL = "HIGH_HIGH_LEVEL"
    LOW_LOW_LEVEL = "LOW_LOW_LEVEL"


@dataclass
class SafetySystem:
    """Monitor tank conditions and apply safety interlocks."""

    low_alarm_threshold: float = 35.0
    low_low_trip_threshold: float = 15.0
    high_alarm_threshold: float = 75.0
    high_high_trip_threshold: float = 80.0

    def __post_init__(self) -> None:
        self.shutdown_latched = False
        self.trip_reason = TripReason.NONE

    def evaluate(
        self,
        level_percent: float,
        emergency_stop: bool,
        equipment_fault: bool,
        reset_request: bool,
    ) -> dict[str, bool | str]:
        """Evaluate alarms, trips and reset requests."""

        low_alarm = (
            level_percent <= self.low_alarm_threshold
        )

        low_low_trip = (
            level_percent <= self.low_low_trip_threshold
        )

        high_alarm = (
            level_percent >= self.high_alarm_threshold
        )

        high_high_trip = (
            level_percent >= self.high_high_trip_threshold
        )

        active_trip = TripReason.NONE

        if emergency_stop:
            active_trip = TripReason.EMERGENCY_STOP
        elif high_high_trip:
            active_trip = TripReason.HIGH_HIGH_LEVEL
        elif low_low_trip:
            active_trip = TripReason.LOW_LOW_LEVEL

        if active_trip != TripReason.NONE:
            self.shutdown_latched = True
            self.trip_reason = active_trip

        reset_performed = False

        safe_level_for_reset = (
            level_percent > self.low_low_trip_threshold
            and level_percent < self.high_high_trip_threshold
        )

        if (
            reset_request
            and active_trip == TripReason.NONE
            and safe_level_for_reset
        ):
            self.shutdown_latched = False
            self.trip_reason = TripReason.NONE
            reset_performed = True

        if self.shutdown_latched:
            alarm_status = f"TRIP: {self.trip_reason.value}"
        elif equipment_fault:
            alarm_status = "PUMP FAULT"
        elif high_alarm:
            alarm_status = "HIGH LEVEL"
        elif low_alarm:
            alarm_status = "LOW LEVEL"
        else:
            alarm_status = "NORMAL"

        return {
            "low_alarm": low_alarm,
            "low_low_trip": low_low_trip,
            "high_alarm": high_alarm,
            "high_high_trip": high_high_trip,
            "equipment_fault": equipment_fault,
            "emergency_stop": emergency_stop,
            "shutdown_latched": self.shutdown_latched,
            "trip_reason": self.trip_reason.value,
            "alarm_status": alarm_status,
            "reset_performed": reset_performed,
        }

    def apply_interlocks(
        self,
        requested_pump_percent: float,
        requested_outlet_valve_percent: float,
    ) -> tuple[float, float]:
        """Apply safe outputs during a latched shutdown."""

        if not self.shutdown_latched:
            return (
                requested_pump_percent,
                requested_outlet_valve_percent,
            )

        safe_pump_percent = 0.0

        if self.trip_reason == TripReason.HIGH_HIGH_LEVEL:
            safe_outlet_valve_percent = 100.0
        else:
            safe_outlet_valve_percent = 0.0

        return (
            safe_pump_percent,
            safe_outlet_valve_percent,
        )
    