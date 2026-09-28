"""Live SCADA dashboard for the Modbus tank digital twin."""

from datetime import datetime
from pathlib import Path
import sys

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from pymodbus.client import ModbusTcpClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRECTORY = PROJECT_ROOT / "src"

if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

from modbus_map import (  # noqa: E402
    ALARM_NAMES,
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
    REGISTER_COUNT,
    decode_percent,
    encode_percent,
)


st.set_page_config(
    page_title="Tank Control SCADA",
    page_icon="🏭",
    layout="wide",
)


st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    .status-card {
        padding: 1rem;
        border-radius: 0.6rem;
        border: 1px solid #3b4453;
        background-color: #151b26;
        margin-bottom: 1rem;
    }

    .tank-shell {
        height: 280px;
        width: 180px;
        margin: auto;
        border: 7px solid #606b7b;
        border-top: 3px solid #606b7b;
        border-radius: 8px 8px 20px 20px;
        position: relative;
        overflow: hidden;
        background-color: #111722;
    }

    .tank-water {
        position: absolute;
        bottom: 0;
        width: 100%;
        background: linear-gradient(
            180deg,
            #2ea8ff,
            #005aa7
        );
        transition: height 0.6s ease;
    }

    .tank-label {
        position: absolute;
        width: 100%;
        top: 44%;
        text-align: center;
        color: white;
        font-size: 1.8rem;
        font-weight: bold;
        text-shadow: 1px 1px 4px black;
        z-index: 2;
    }

    .connected {
        color: #35d07f;
        font-weight: bold;
    }

    .disconnected {
        color: #ff5252;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def create_client() -> ModbusTcpClient:
    """Create a Modbus TCP client."""

    return ModbusTcpClient(
        host=HOST,
        port=PORT,
        timeout=2,
    )


def read_registers() -> list[int]:
    """Read the complete Modbus register table."""

    client = create_client()

    try:
        if not client.connect():
            raise ConnectionError(
                "Could not connect to the Modbus TCP server."
            )

        response = client.read_holding_registers(
            address=0,
            count=REGISTER_COUNT,
            device_id=DEVICE_ID,
        )

        if response.isError():
            raise RuntimeError(
                f"Modbus read returned an error: {response}"
            )

        return response.registers

    finally:
        client.close()


def write_register(
    address: int,
    value: int,
) -> None:
    """Write one value to a Modbus register."""

    client = create_client()

    try:
        if not client.connect():
            raise ConnectionError(
                "Could not connect to the Modbus TCP server."
            )

        response = client.write_register(
            address=address,
            value=value,
            device_id=DEVICE_ID,
        )

        if response.isError():
            raise RuntimeError(
                f"Modbus write failed at address {address}."
            )

    finally:
        client.close()


def apply_operator_settings(
    mode_name: str,
    setpoint_percent: float,
    manual_pump_percent: float,
    outlet_valve_percent: float,
) -> None:
    """Write operator settings to the controller."""

    mode_value = 1 if mode_name == "Automatic" else 0

    write_register(HR_MODE, mode_value)

    write_register(
        HR_SETPOINT,
        encode_percent(setpoint_percent),
    )

    write_register(
        HR_MANUAL_PUMP,
        encode_percent(manual_pump_percent),
    )

    write_register(
        HR_OUTLET_VALVE,
        encode_percent(outlet_valve_percent),
    )


def initialise_session_state() -> None:
    """Create dashboard history storage."""

    if "process_history" not in st.session_state:
        st.session_state.process_history = []

    if "operator_message" not in st.session_state:
        st.session_state.operator_message = ""


def display_alarm(alarm_code: int, shutdown: bool) -> None:
    """Display the current alarm state."""

    alarm_name = ALARM_NAMES.get(
        alarm_code,
        "UNKNOWN ALARM",
    )

    if shutdown:
        st.error(
            f"🚨 SAFETY SHUTDOWN LATCHED — {alarm_name}"
        )
    elif alarm_code in (4, 5):
        st.error(f"🚨 {alarm_name}")
    elif alarm_code in (1, 2):
        st.warning(f"⚠️ {alarm_name}")
    elif alarm_code == 3:
        st.error("🛑 EMERGENCY STOP ACTIVE")
    else:
        st.success("✅ SYSTEM NORMAL")


def create_level_chart(
    history: pd.DataFrame,
) -> go.Figure:
    """Create the tank-level trend chart."""

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=history["time"],
            y=history["tank_level"],
            name="Tank level",
            mode="lines",
            line={
                "color": "#2e86ff",
                "width": 3,
            },
        )
    )

    figure.add_trace(
        go.Scatter(
            x=history["time"],
            y=history["setpoint"],
            name="Setpoint",
            mode="lines",
            line={
                "color": "white",
                "width": 2,
                "dash": "dash",
            },
        )
    )

    figure.add_hline(
        y=75,
        line_dash="dot",
        line_color="orange",
        annotation_text="High alarm",
    )

    figure.add_hline(
        y=80,
        line_dash="dot",
        line_color="red",
        annotation_text="High-high trip",
    )

    figure.add_hline(
        y=35,
        line_dash="dot",
        line_color="#e0b341",
        annotation_text="Low alarm",
    )

    figure.update_layout(
        title="Tank Level Trend",
        xaxis_title="Time",
        yaxis_title="Level (%)",
        yaxis_range=[0, 100],
        height=400,
        margin={
            "l": 40,
            "r": 30,
            "t": 60,
            "b": 40,
        },
        legend={
            "orientation": "h",
            "y": 1.12,
        },
    )

    return figure


def create_process_chart(
    history: pd.DataFrame,
) -> go.Figure:
    """Create pump and flow trend charts."""

    figure = make_subplots(
        specs=[[{"secondary_y": True}]]
    )

    figure.add_trace(
        go.Scatter(
            x=history["time"],
            y=history["pump_output"],
            name="Pump output",
            line={
                "color": "#b15cff",
                "width": 3,
            },
        ),
        secondary_y=False,
    )

    figure.add_trace(
        go.Scatter(
            x=history["time"],
            y=history["inflow"],
            name="Inflow",
            line={
                "color": "#28c76f",
                "width": 2,
            },
        ),
        secondary_y=True,
    )

    figure.add_trace(
        go.Scatter(
            x=history["time"],
            y=history["outflow"],
            name="Outflow",
            line={
                "color": "#ff9f43",
                "width": 2,
            },
        ),
        secondary_y=True,
    )

    figure.update_yaxes(
        title_text="Pump output (%)",
        range=[0, 100],
        secondary_y=False,
    )

    figure.update_yaxes(
        title_text="Flow (L/s)",
        range=[0, 8],
        secondary_y=True,
    )

    figure.update_layout(
        title="Pump and Flow Trends",
        xaxis_title="Time",
        height=400,
        margin={
            "l": 40,
            "r": 40,
            "t": 60,
            "b": 40,
        },
        legend={
            "orientation": "h",
            "y": 1.12,
        },
    )

    return figure


initialise_session_state()

st.title("🏭 Modbus TCP Tank-Control Digital Twin")
st.caption(
    "Live SCADA monitoring and control through Modbus TCP"
)


with st.sidebar:
    st.header("Operator Controls")

    with st.form("operator_controls"):
        selected_mode = st.selectbox(
            "Operating mode",
            options=["Automatic", "Manual"],
            index=0,
        )

        selected_setpoint = st.slider(
            "Tank-level setpoint (%)",
            min_value=0.0,
            max_value=100.0,
            value=60.0,
            step=1.0,
        )

        selected_manual_pump = st.slider(
            "Manual pump output (%)",
            min_value=0.0,
            max_value=100.0,
            value=35.0,
            step=1.0,
        )

        selected_outlet_valve = st.slider(
            "Outlet valve position (%)",
            min_value=0.0,
            max_value=100.0,
            value=50.0,
            step=1.0,
        )

        settings_submitted = st.form_submit_button(
            "Apply Settings",
            use_container_width=True,
            type="primary",
        )

    if settings_submitted:
        try:
            apply_operator_settings(
                mode_name=selected_mode,
                setpoint_percent=selected_setpoint,
                manual_pump_percent=selected_manual_pump,
                outlet_valve_percent=(
                    selected_outlet_valve
                ),
            )

            st.session_state.operator_message = (
                "Settings applied successfully."
            )

        except Exception as error:
            st.session_state.operator_message = str(error)

    st.divider()
    st.subheader("Safety Controls")

    if st.button(
        "🛑 Activate Emergency Stop",
        use_container_width=True,
        type="primary",
    ):
        try:
            write_register(HR_EMERGENCY_STOP, 1)
            st.session_state.operator_message = (
                "Emergency stop activated."
            )
        except Exception as error:
            st.session_state.operator_message = str(error)

    if st.button(
        "Release Emergency Stop",
        use_container_width=True,
    ):
        try:
            write_register(HR_EMERGENCY_STOP, 0)
            st.session_state.operator_message = (
                "Emergency stop released. "
                "Press Controlled Reset."
            )
        except Exception as error:
            st.session_state.operator_message = str(error)

    if st.button(
        "🔄 Controlled Reset",
        use_container_width=True,
    ):
        try:
            write_register(HR_RESET_REQUEST, 1)
            st.session_state.operator_message = (
                "Reset request sent."
            )
        except Exception as error:
            st.session_state.operator_message = str(error)

    if st.button(
        "Clear Trend History",
        use_container_width=True,
    ):
        st.session_state.process_history = []
        st.session_state.operator_message = (
            "Trend history cleared."
        )

    if st.session_state.operator_message:
        st.info(st.session_state.operator_message)


@st.fragment(run_every=1.0)
def live_dashboard() -> None:
    """Refresh live measurements once every second."""

    try:
        registers = read_registers()

    except Exception as error:
        st.markdown(
            '<p class="disconnected">'
            "● MODBUS SERVER DISCONNECTED"
            "</p>",
            unsafe_allow_html=True,
        )

        st.error(str(error))
        st.info(
            "Start `src/modbus_server.py` in the first "
            "VS Code terminal."
        )
        return

    tank_level = decode_percent(
        registers[HR_TANK_LEVEL]
    )

    pump_output = decode_percent(
        registers[HR_ACTUAL_PUMP]
    )

    inflow = decode_percent(
        registers[HR_INFLOW]
    )

    outflow = decode_percent(
        registers[HR_OUTFLOW]
    )

    setpoint = decode_percent(
        registers[HR_SETPOINT]
    )

    outlet_valve = decode_percent(
        registers[HR_OUTLET_VALVE]
    )

    alarm_code = registers[HR_ALARM_CODE]

    shutdown_latched = bool(
        registers[HR_SHUTDOWN_LATCHED]
    )

    emergency_stop = bool(
        registers[HR_EMERGENCY_STOP]
    )

    automatic_mode = bool(
        registers[HR_ACTIVE_MODE]
    )

    heartbeat = registers[HR_HEARTBEAT]

    st.markdown(
        '<p class="connected">'
        "● MODBUS SERVER CONNECTED"
        "</p>",
        unsafe_allow_html=True,
    )

    display_alarm(
        alarm_code=alarm_code,
        shutdown=shutdown_latched,
    )

    timestamp = datetime.now().strftime("%H:%M:%S")

    st.session_state.process_history.append(
        {
            "time": timestamp,
            "tank_level": tank_level,
            "setpoint": setpoint,
            "pump_output": pump_output,
            "inflow": inflow,
            "outflow": outflow,
        }
    )

    st.session_state.process_history = (
        st.session_state.process_history[-180:]
    )

    tank_column, value_column = st.columns(
        [1, 2],
        gap="large",
    )

    with tank_column:
        st.subheader("Tank Overview")

        st.markdown(
            f"""
            <div class="tank-shell">
                <div class="tank-label">
                    {tank_level:.1f}%
                </div>
                <div
                    class="tank-water"
                    style="height: {tank_level}%;">
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.progress(
            int(max(0, min(tank_level, 100))),
            text=f"Tank level: {tank_level:.2f}%",
        )

    with value_column:
        st.subheader("Live Process Values")

        first_row = st.columns(3)

        first_row[0].metric(
            "Tank Level",
            f"{tank_level:.2f}%",
            f"{tank_level - setpoint:.2f}% vs SP",
        )

        first_row[1].metric(
            "Level Setpoint",
            f"{setpoint:.2f}%",
        )

        first_row[2].metric(
            "Pump Output",
            f"{pump_output:.2f}%",
        )

        second_row = st.columns(3)

        second_row[0].metric(
            "Inflow",
            f"{inflow:.2f} L/s",
        )

        second_row[1].metric(
            "Outflow",
            f"{outflow:.2f} L/s",
        )

        second_row[2].metric(
            "Outlet Valve",
            f"{outlet_valve:.2f}%",
        )

        st.markdown("#### Controller Status")

        status_table = pd.DataFrame(
            {
                "Item": [
                    "Operating mode",
                    "Alarm state",
                    "Emergency stop",
                    "Shutdown latched",
                    "Server heartbeat",
                ],
                "Status": [
                    (
                        "AUTOMATIC"
                        if automatic_mode
                        else "MANUAL"
                    ),
                    ALARM_NAMES.get(
                        alarm_code,
                        "UNKNOWN",
                    ),
                    (
                        "ACTIVE"
                        if emergency_stop
                        else "Released"
                    ),
                    (
                        "YES"
                        if shutdown_latched
                        else "No"
                    ),
                    heartbeat,
                ],
            }
        )

        st.dataframe(
            status_table,
            hide_index=True,
            use_container_width=True,
        )

    history = pd.DataFrame(
        st.session_state.process_history
    )

    st.divider()
    st.subheader("Live Process Trends")

    level_chart, process_chart = st.columns(2)

    with level_chart:
        st.plotly_chart(
            create_level_chart(history),
            use_container_width=True,
            key="level_trend_chart",
        )

    with process_chart:
        st.plotly_chart(
            create_process_chart(history),
            use_container_width=True,
            key="process_trend_chart",
        )

    st.caption(
        f"Last update: {timestamp} | "
        f"Modbus device: {HOST}:{PORT} | "
        f"Device ID: {DEVICE_ID}"
    )


live_dashboard()