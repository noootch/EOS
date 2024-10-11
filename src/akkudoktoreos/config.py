import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ValidationError

EOS_DIR = "EOS_DIR"
ENCODING = "UTF-8"
CONFIG_FILE_NAME = "EOS.config.json"
DEFAULT_CONFIG_FILE = Path(__file__).parent.joinpath("default.config.json")


class FolderConfig(BaseModel):
    "Folder configuration"

    output: str
    cache: str


class EOSConfig(BaseModel):
    "EOS dependent config"

    prediction_hours: int
    optimization_hours: int
    penalty: int
    available_charging_rates_in_percentage: list[float]


class BaseConfig(BaseModel):
    "The base configuration."

    directories: FolderConfig
    eos: EOSConfig


class AppConfig(BaseConfig):
    "The app config."

    working_dir: Path

    def run_setup(self) -> None:
        "Run app setup."
        print("Checking directory settings and creating missing directories...")
        for key, value in self.directories.model_dump().items():
            if not isinstance(value, str):
                continue
            path = self.working_dir / value
            if path.is_dir():
                print(f"'{key}': {path}")
                continue
            print(f"Creating directory '{key}': {path}")
            os.makedirs(path, exist_ok=True)


class SetupIncomplete(Exception):
    "Class for all setup related exceptions"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r") as f_in:
        return json.load(f_in)


def _merge_json(default_data: dict[str, Any], custom_data: dict[str, Any]) -> dict[str, Any]:
    merged_data = {}
    for key, default_value in default_data.items():
        if key in custom_data:
            custom_value = custom_data[key]
            if isinstance(default_value, dict) and isinstance(custom_value, dict):
                merged_data[key] = _merge_json(default_value, custom_value)
            elif type(default_value) is type(custom_value):
                merged_data[key] = custom_value
            else:
                # use default value if types differ
                merged_data[key] = default_value
        else:
            merged_data[key] = default_value
    return merged_data


def _config_update_available(merged_data: dict[str, Any], custom_data: dict[str, Any]) -> bool:
    if merged_data.keys() != custom_data.keys():
        return True

    for key in merged_data:
        value1 = merged_data[key]
        value2 = custom_data[key]

        if isinstance(value1, dict) and isinstance(value2, dict):
            if _config_update_available(value1, value2):
                return True
        elif value1 != value2:
            return True
    return False


def get_config_file(path: Path, copy_default: bool) -> Path:
    "Get the valid config file path."
    config = path.resolve() / CONFIG_FILE_NAME
    if config.is_file():
        print(f"Using configuration from: {config}")
        return config

    if not path.is_dir():
        print(f"Path does not exist: {path}. Using default configuration...")
        return DEFAULT_CONFIG_FILE

    if not copy_default:
        print("No custom configuration provided. Using default configuration...")
        return DEFAULT_CONFIG_FILE

    try:
        return Path(shutil.copy2(DEFAULT_CONFIG_FILE, config))
    except Exception as exc:
        print(f"Could not copy default config: {exc}. Using default copy...")
    return DEFAULT_CONFIG_FILE


def _merge_and_update(custom_config: Path, update_outdated: bool = False) -> bool:
    if custom_config == DEFAULT_CONFIG_FILE:
        return False
    default_data = _load_json(DEFAULT_CONFIG_FILE)
    custom_data = _load_json(custom_config)
    merged_data = _merge_json(default_data, custom_data)

    if not _config_update_available(merged_data, custom_data):
        print(f"Custom config {custom_config} is up-to-date...")
        return False
    print(f"Custom config {custom_config} is outdated...")
    if update_outdated:
        with custom_config.open("w") as f_out:
            json.dump(merged_data, f_out, indent=2)
        return True
    return False


def load_config(
    working_dir: Path, copy_default: bool = False, update_outdated: bool = True
) -> AppConfig:
    "Load AppConfig from provided path or use default.config.json"
    # make sure working_dir is always a full path
    working_dir = working_dir.resolve()

    config = get_config_file(working_dir, copy_default)
    _merge_and_update(config, update_outdated)

    with config.open("r", encoding=ENCODING) as f_in:
        try:
            base_config = BaseConfig.model_validate(json.load(f_in))
            return AppConfig.model_validate(
                {"working_dir": working_dir, **base_config.model_dump()}
            )
        except ValidationError as exc:
            raise ValueError(f"Configuration {config} is incomplete or not valid: {exc}")


def get_working_dir() -> Path:
    "Get necessary paths for app startup."
    custom_dir = os.getenv(EOS_DIR)
    if custom_dir is None:
        working_dir = Path.cwd()
        print(f"No custom directory provided. Setting working directory to: {working_dir}")
    else:
        working_dir = Path(custom_dir).resolve()
        print(f"Custom directory provided. Setting working directory to: {working_dir}")
    return working_dir


def get_start_enddate(
    prediction_hours: int, startdate: Optional[datetime] = None
) -> tuple[str, str]:
    ############
    # Parameter
    ############
    if startdate is None:
        date = (datetime.now().date() + timedelta(hours=prediction_hours)).strftime("%Y-%m-%d")
        date_now = datetime.now().strftime("%Y-%m-%d")
    else:
        date = (startdate + timedelta(hours=prediction_hours)).strftime("%Y-%m-%d")
        date_now = startdate.strftime("%Y-%m-%d")
    return date_now, date
