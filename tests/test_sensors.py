from rhb_led_driver.sensors import SensorState


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


def test_stale_value_falls_back_to_default():
    clock = Clock()
    s = SensorState(clock=clock)
    s.on_osc("/pressure", 42.0)
    assert s.get("accumulator_pressure") == 42.0
    clock.t += 10
    assert s.get("accumulator_pressure", -1) == -1


def test_bad_value_is_dropped():
    s = SensorState()
    s.on_osc("/pressure", "nan-ish")
    assert s.get("accumulator_pressure") is None


def test_button_rise_survives_quick_release():
    clock = Clock()
    s = SensorState(clock=clock)
    s.on_osc("/poof_button", 1)
    clock.t += 0.1
    s.on_osc("/poof_button", 0)
    clock.t += 0.1
    assert abs(s.since_rise("poof_button") - 0.2) < 1e-9
