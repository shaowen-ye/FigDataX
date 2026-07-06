"""Calibration: exactness, RMSE, log/reciprocal domain guards, precision."""

import numpy as np
import pytest

from scripts.figdatax import (calibrate_axes_multipoint, calibrate_axes,
                              AxisCalibration, CalibrationError)


def test_linear_exact():
    cal = calibrate_axes_multipoint([100, 200, 300], [0, 10, 20],
                                    [300, 200, 100], [0, 5, 10])
    dx, dy = cal.pixel_to_data(200, 200)
    assert dx == pytest.approx(10, abs=1e-9)
    assert dy == pytest.approx(5, abs=1e-9)
    assert cal.x_rmse < 1e-9 and cal.y_rmse < 1e-9


def test_inverse_roundtrip():
    cal = calibrate_axes_multipoint([80, 560], [0, 10], [360, 40], [0, 25])
    px, py = cal.data_to_pixel(7.5, 18.0)
    dx, dy = cal.pixel_to_data(px, py)
    assert dx == pytest.approx(7.5, abs=1e-6)
    assert dy == pytest.approx(18.0, abs=1e-6)


def test_serialization_roundtrip():
    cal = calibrate_axes_multipoint([0, 100], [1, 100], [100, 0], [0, 50], x_log=True)
    d = cal.to_dict()
    cal2 = AxisCalibration.from_dict(d)
    assert cal2.pixel_to_data(50, 50) == pytest.approx(cal.pixel_to_data(50, 50))


def test_log_guard_raises_on_nonpositive():
    with pytest.raises(CalibrationError):
        calibrate_axes_multipoint([0, 100], [0, 100], [100, 0], [1, 100], x_log=True)


def test_reciprocal_guard_raises_on_zero():
    with pytest.raises(CalibrationError):
        calibrate_axes_multipoint([0, 100], [0, 100], [100, 0], [1, 10],
                                  x_transform="reciprocal")


def test_length_mismatch_raises():
    with pytest.raises(CalibrationError):
        calibrate_axes_multipoint([0, 100], [0], [100, 0], [0, 10])


def test_small_magnitude_precision_not_rounded():
    # Values ~1e-6 must survive — the old round(,4) destroyed them.
    cal = calibrate_axes_multipoint([0, 100], [1e-6, 5e-6], [100, 0], [0, 1])
    dx, _ = cal.pixel_to_data(50, 50)
    assert dx == pytest.approx(3e-6, rel=1e-6)


def test_log_scale_recovers_values():
    cal = calibrate_axes([80, 40, 560, 360], (0, 10), (1, 1000), y_log=True)
    # bottom pixel (360) -> y_min=1, top pixel (40) -> y_max=1000
    _, y_bottom = cal.pixel_to_data(80, 360)
    _, y_top = cal.pixel_to_data(80, 40)
    assert y_bottom == pytest.approx(1, rel=1e-6)
    assert y_top == pytest.approx(1000, rel=1e-6)
