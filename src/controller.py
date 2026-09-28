"""PI control and operating-mode logic for the tank digital twin."""

from dataclasses import dataclass
from enum import Enum


class OperatingMode(Enum):
    """Available tank-controller operating modes."""

    MANUAL = "MANUAL"
    AUTOMATIC = "AUTOMATIC"


@dataclass
class PIController:
    """Proportional-integral controller with output limiting."""

    proportional_gain: float = 1.0
    integral_gain: float = 0.005
    minimum_output: float = 0.0
    maximum_output: float = 100.0

    def __post_init__(self) -> None:
        self.integral = 0.0

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        """Limit a value to a specified range."""
        return max(minimum, min(value, maximum))

    def reset(self) -> None:
        """Clear the stored integral term."""
        self.integral = 0.0

    def update(
        self,
        setpoint: float,
        measured_value: float,
        time_step_seconds: float,
    ) -> dict[str, float]:
        """Calculate the next PI-controller output."""

        if time_step_seconds <= 0:
            raise ValueError("Time step must be greater than zero.")

        error = setpoint - measured_value
        proportional_term = self.proportional_gain * error

        candidate_integral = (
            self.integral
            + error * time_step_seconds
        )

        candidate_output = (
            proportional_term
            + self.integral_gain * candidate_integral
        )

        # Conditional integration prevents integral windup.
        integration_allowed = (
            self.minimum_output
            < candidate_output
            < self.maximum_output
        )

        if (
            candidate_output >= self.maximum_output
            and error < 0
        ):
            integration_allowed = True

        if (
            candidate_output <= self.minimum_output
            and error > 0
        ):
            integration_allowed = True

        if integration_allowed:
            self.integral = candidate_integral

        integral_term = self.integral_gain * self.integral

        unrestricted_output = (
            proportional_term
            + integral_term
        )

        controller_output = self._clamp(
            unrestricted_output,
            minimum=self.minimum_output,
            maximum=self.maximum_output,
        )

        return {
            "setpoint": setpoint,
            "measured_value": measured_value,
            "error": error,
            "proportional_term": proportional_term,
            "integral_term": integral_term,
            "controller_output": controller_output,
        }


@dataclass
class TankLevelController:
    """Control the tank pump in manual or automatic mode."""

    setpoint_percent: float = 60.0
    manual_output_percent: float = 35.0
    mode: OperatingMode = OperatingMode.MANUAL

    def __post_init__(self) -> None:
        self.pi_controller = PIController()

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return max(minimum, min(value, maximum))

    def set_mode(self, new_mode: OperatingMode) -> None:
        """Change the controller operating mode."""

        if new_mode != self.mode:
            self.mode = new_mode

            if new_mode == OperatingMode.AUTOMATIC:
                self.pi_controller.reset()

    def update(
        self,
        measured_level_percent: float,
        time_step_seconds: float,
    ) -> dict[str, float | str]:
        """Return the pump command for the current mode."""

        if self.mode == OperatingMode.MANUAL:
            pump_command = self._clamp(
                self.manual_output_percent,
                minimum=0.0,
                maximum=100.0,
            )

            return {
                "mode": self.mode.value,
                "setpoint_percent": self.setpoint_percent,
                "error_percent": (
                    self.setpoint_percent
                    - measured_level_percent
                ),
                "proportional_term": 0.0,
                "integral_term": 0.0,
                "pump_command_percent": pump_command,
            }

        control_result = self.pi_controller.update(
            setpoint=self.setpoint_percent,
            measured_value=measured_level_percent,
            time_step_seconds=time_step_seconds,
        )

        return {
            "mode": self.mode.value,
            "setpoint_percent": self.setpoint_percent,
            "error_percent": control_result["error"],
            "proportional_term": (
                control_result["proportional_term"]
            ),
            "integral_term": control_result["integral_term"],
            "pump_command_percent": (
                control_result["controller_output"]
            ),
        }