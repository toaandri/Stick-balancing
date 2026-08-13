import pytest

from config import (
    ControllerParams,
    SystemParams,
    from_dict,
    load_controller_defaults,
    load_defaults,
    load_yaml,
)


def test_defaults_load():
    params = load_defaults()
    assert isinstance(params, SystemParams)
    assert params.N == 1
    assert params.cart_max_force == 100.0
    assert params.n_state == 4
    params.validate()


def test_controller_defaults_load():
    params = load_controller_defaults()
    assert isinstance(params, ControllerParams)
    assert params.type == "pid"
    params.validate()


def test_from_dict_rejects_unknown():
    with pytest.raises(ValueError):
        from_dict(SystemParams, {"cart_masss": 1.0})


def test_from_dict_roundtrip():
    data = {"cart_mass": 3.0, "N": 5, "sim_time": 10.0}
    params = from_dict(SystemParams, data)
    assert params.cart_mass == 3.0
    assert params.N == 5
    assert params.n_state == 12


def test_validation():
    with pytest.raises(ValueError):
        SystemParams(N=0).validate()
    with pytest.raises(ValueError):
        SystemParams(initial_condition="bogus").validate()


def test_yaml_loader(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("system:\n  N: 2\n", encoding="utf-8")
    raw = load_yaml(p)
    assert raw["system"]["N"] == 2


def test_experiments_yaml_present():
    from pathlib import Path

    raw = load_yaml(Path(__file__).resolve().parents[1] / "config" / "experiments.yaml")
    assert len(raw["experiments"]) == 3