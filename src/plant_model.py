"""Dynamic model of a software-simulated industrial water tank."""

from dataclasses import dataclass
from math import sqrt


@dataclass
class TankPlant:
    """Represent a tank with controlled inflow and gravity-driven outflow."""

    capacity_litres: float = 1000.0
    maximum_inflow_lps: float = 8.0
    maximum_outflow_lps: float = 10.0
    level_percent: float = 20.0

    def __post_init__(self) -> None:
        if self.capacity_litres <= 0:
            raise ValueError("Tank capacity must be greater than zero.")

        self.level_percent = self._clamp(
            self.level_percent,
            minimum=0.0,
            maximum=100.0,
        )

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        """Limit a value to a specified range."""
        return max(minimum, min(value, maximum))

    @property
    def volume_litres(self) -> float:
        """Return the current water volume."""
        return self.capacity_litres * self.level_percent / 100.0

    def step(
        self,
        pump_command_percent: float,
        outlet_valve_percent: float,
        time_step_seconds: float,
    ) -> dict[str, float]:
        """Advance the tank simulation by one time step."""

        if time_step_seconds <= 0:
            raise ValueError("Time step must be greater than zero.")

        pump_command_percent = self._clamp(
            pump_command_percent,
            minimum=0.0,
            maximum=100.0,
        )

        outlet_valve_percent = self._clamp(
            outlet_valve_percent,
            minimum=0.0,
            maximum=100.0,
        )

        level_fraction = self.level_percent / 100.0

        inflow_lps = (
            self.maximum_inflow_lps
            * pump_command_percent
            / 100.0
        )

        outflow_lps = (
            self.maximum_outflow_lps
            * outlet_valve_percent
            / 100.0
            * sqrt(level_fraction)
        )

        new_volume_litres = (
            self.volume_litres
            + (inflow_lps - outflow_lps)
            * time_step_seconds
        )

        new_volume_litres = self._clamp(
            new_volume_litres,
            minimum=0.0,
            maximum=self.capacity_litres,
        )

        self.level_percent = (
            new_volume_litres
            / self.capacity_litres
            * 100.0
        )

        return {
            "level_percent": self.level_percent,
            "volume_litres": new_volume_litres,
            "inflow_lps": inflow_lps,
            "outflow_lps": outflow_lps,
            "net_flow_lps": inflow_lps - outflow_lps,
            "pump_command_percent": pump_command_percent,
            "outlet_valve_percent": outlet_valve_percent,
        }