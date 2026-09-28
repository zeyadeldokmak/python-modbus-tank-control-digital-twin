# Tank-Control Digital Twin Requirements

## System purpose

The system shall simulate, control and monitor an industrial water-tank process entirely in software.

## Functional requirements

| ID | Requirement |
|---|---|
| FR-01 | The system shall represent the tank level from 0% to 100%. |
| FR-02 | The model shall accept pump and outlet-valve commands from 0% to 100%. |
| FR-03 | The model shall calculate inflow, outflow and net flow. |
| FR-04 | The tank volume shall remain between empty and full capacity. |
| FR-05 | The system shall support manual and automatic operating modes. |
| FR-06 | Automatic mode shall use PI control to maintain a level setpoint. |
| FR-07 | The system shall detect high, low and equipment-fault conditions. |
| FR-08 | Safety interlocks shall place the plant in a safe operating state. |
| FR-09 | Process data shall be available through Modbus TCP registers. |
| FR-10 | A dashboard shall display process values, alarms and trends. |
| FR-11 | Simulation results and events shall be recorded in CSV format. |
| FR-12 | Normal and fault behaviour shall be verified using automated tests. |

## Day 1 acceptance criteria

- The tank level remains between 0% and 100%.
- Pump and valve commands remain between 0% and 100%.
- The tank responds dynamically to inflow and outflow.
- The simulation produces a CSV log.
- The simulation produces a tank-level graph.