from pathlib import Path

import requests

from akkudoktoreos.config import load_config


def test_server(server):
    """
    Test the server
    """
    result = requests.get(f"{server}/gesamtlast_simple?year_energy=2000&")
    assert result.status_code == 200
    config = load_config(Path.cwd())
    assert len(result.json()) == config.eos.prediction_hours
