from pathlib import Path
import subprocess
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FOLDER = PROJECT_ROOT / "src"
IMAGE_FOLDER = PROJECT_ROOT / "images"
LOG_FOLDER = PROJECT_ROOT / "logs"


def run_python_file(filename: str) -> subprocess.CompletedProcess:
    """Run one project script from the main project folder."""

    return subprocess.run(
        [sys.executable, str(SOURCE_FOLDER / filename)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def check_csv_file(filename: str) -> None:
    """Check that a CSV result exists and contains valid data."""

    csv_path = LOG_FOLDER / filename

    assert csv_path.exists(), f"{filename} was not created"

    results = pd.read_csv(csv_path)

    assert not results.empty, f"{filename} contains no results"
    assert len(results.columns) >= 3, f"{filename} has too few columns"
    assert len(results) >= 10, f"{filename} has too few result rows"


def test_required_project_files_exist():
    required_files = [
        SOURCE_FOLDER / "plant_model.py",
        SOURCE_FOLDER / "controller.py",
        SOURCE_FOLDER / "safety_system.py",
        SOURCE_FOLDER / "modbus_map.py",
        SOURCE_FOLDER / "modbus_server.py",
        SOURCE_FOLDER / "modbus_client_test.py",
        PROJECT_ROOT / "dashboard" / "app.py",
    ]

    for file_path in required_files:
        assert file_path.exists(), f"Missing file: {file_path.name}"


def test_day1_open_loop_simulation():
    result = run_python_file("simulation.py")

    assert result.returncode == 0, result.stderr
    assert "successfully" in result.stdout.lower()

    check_csv_file("day1_plant_simulation.csv")

    image_path = IMAGE_FOLDER / "day1_tank_response.png"
    assert image_path.exists(), "Day 1 graph was not created"


def test_day2_pi_control_simulation():
    result = run_python_file("day2_control_simulation.py")

    assert result.returncode == 0, result.stderr
    assert "successfully" in result.stdout.lower()

    check_csv_file("day2_pi_control.csv")

    image_path = IMAGE_FOLDER / "day2_pi_control.png"
    assert image_path.exists(), "Day 2 graph was not created"


def test_day3_safety_simulation():
    result = run_python_file("day3_safety_simulation.py")

    assert result.returncode == 0, result.stderr
    assert "successfully" in result.stdout.lower()

    check_csv_file("day3_safety_simulation.csv")

    image_path = IMAGE_FOLDER / "day3_safety_response.png"
    assert image_path.exists(), "Day 3 graph was not created"


def test_dashboard_file_is_not_empty():
    dashboard_path = PROJECT_ROOT / "dashboard" / "app.py"

    dashboard_code = dashboard_path.read_text(encoding="utf-8")

    assert "streamlit" in dashboard_code.lower()
    assert "modbus" in dashboard_code.lower()
    assert len(dashboard_code) > 500