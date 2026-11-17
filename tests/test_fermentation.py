from datetime import datetime, timedelta, timezone

import pytest

from app import fermentation as fm

T0 = datetime(2026, 11, 17, 8, 0, tzinfo=timezone.utc)


def feeding(starter=10, flour=10, water=10, temp=24.0, fed_at=T0):
    return fm.Feeding(starter_g=starter, flour_g=flour, water_g=water, temp_c=temp, fed_at=fed_at)


def test_reference_feeding_peaks_in_six_hours():
    assert fm.peak_hours(feeding()) == pytest.approx(6.0)


@pytest.mark.parametrize("temp, expected", [(16, 12.0), (24, 6.0), (32, 3.0)])
def test_temperature_doubles_time_every_8_degrees(temp, expected):
    assert fm.peak_hours(feeding(temp=temp)) == pytest.approx(expected)


def test_bigger_dilution_takes_longer():
    one = fm.peak_hours(feeding())
    two = fm.peak_hours(feeding(flour=20, water=20))
    five = fm.peak_hours(feeding(flour=50, water=50))
    assert one < two < five


def test_stiff_starter_is_slower_than_liquid():
    stiff = feeding(flour=20, water=10)
    liquid = feeding(flour=10, water=20)
    assert fm.peak_hours(stiff) > fm.peak_hours(liquid)


def test_hydration_percent():
    assert fm.hydration_percent(feeding(flour=20, water=10)) == 50.0


@pytest.mark.parametrize(
    "kwargs",
    [{"starter": 0}, {"flour": -1}, {"water": 0}, {"temp": 2}, {"temp": 45}],
)
def test_invalid_feeding_is_rejected(kwargs):
    with pytest.raises(fm.FeedingError):
        fm.peak_hours(feeding(**kwargs))


@pytest.mark.parametrize(
    "hours_later, stage",
    [
        (2, fm.Stage.WAKING),
        (4, fm.Stage.RISING),
        (6, fm.Stage.PEAK),
        (9, fm.Stage.FALLING),
        (15, fm.Stage.HUNGRY),
    ],
)
def test_status_stages(hours_later, stage):
    result = fm.status(feeding(), T0 + timedelta(hours=hours_later))
    assert result.stage is stage
    assert result.label == fm.STAGE_LABELS[stage]


def test_status_peak_time_and_progress():
    result = fm.status(feeding(), T0 + timedelta(hours=3))
    assert result.peak_at == T0 + timedelta(hours=6)
    assert result.progress == pytest.approx(0.5)
    assert result.hours_since_feeding == pytest.approx(3.0)


def test_plan_feeding_hits_peak_at_target():
    target = T0 + timedelta(hours=20)
    plan = fm.plan_feeding(10, 50, 50, 22, target)
    assert plan.feed_at == target - timedelta(hours=plan.peak_hours)
    fed = feeding(flour=50, water=50, temp=22, fed_at=plan.feed_at)
    assert fm.status(fed, target).stage is fm.Stage.PEAK


def test_suggest_ratio_reference_cases():
    assert fm.suggest_ratio(6, 24)["x"] == 1
    assert fm.suggest_ratio(12, 24)["x"] == 4


def test_suggest_ratio_more_time_means_bigger_ratio():
    assert fm.suggest_ratio(20, 24)["x"] > fm.suggest_ratio(10, 24)["x"]


def test_suggest_ratio_warns_when_too_cold():
    result = fm.suggest_ratio(6, 8)
    assert result["x"] == 1
    assert result["warning"] is not None


def test_suggest_ratio_rejects_non_positive_hours():
    with pytest.raises(fm.FeedingError):
        fm.suggest_ratio(0, 24)
