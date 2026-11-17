"""
Egyszerűsített modell:
* referencia: 1:1:1 etetés (anyakovász:liszt:víz) 24 °C-on kb. 6 óra alatt ér csúcsra;
* minden 8 °C hűlés megduplázza, minden 8 °C melegedés megfelezi ezt az időt;
* nagyobb hígítás (pl. 1:5:5) logaritmikusan hosszabb felfutást jelent;
* a sűrűbb (alacsony hidratációjú) kovász lassabban dolgozik.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

REFERENCE_TEMP_C = 24.0
REFERENCE_PEAK_HOURS = 6.0
DOUBLING_DEGREES = 8.0
MIN_TEMP_C = 4.0
MAX_TEMP_C = 40.0
MAX_SUGGESTED_RATIO = 20


class FeedingError(ValueError):
    """Érvénytelen etetési adatok."""


class Stage(str, Enum):
    WAKING = "WAKING"
    RISING = "RISING"
    PEAK = "PEAK"
    FALLING = "FALLING"
    HUNGRY = "HUNGRY"


STAGE_LABELS = {
    Stage.WAKING: "Ébredezik 😴",
    Stage.RISING: "Emelkedik 📈",
    Stage.PEAK: "Csúcson – mehet a tésztába! 🎉",
    Stage.FALLING: "Már esik, siess vele 📉",
    Stage.HUNGRY: "Éhes, etesd meg! 🍽️",
}

# (felső határ a csúcsidőhöz viszonyított haladásban, szakasz)
STAGE_THRESHOLDS = (
    (0.5, Stage.WAKING),
    (0.9, Stage.RISING),
    (1.25, Stage.PEAK),
    (2.0, Stage.FALLING),
)


@dataclass(frozen=True)
class Feeding:
    starter_g: float
    flour_g: float
    water_g: float
    temp_c: float
    fed_at: datetime


@dataclass(frozen=True)
class StarterStatus:
    stage: Stage
    label: str
    hours_since_feeding: float
    peak_hours: float
    peak_at: datetime
    progress: float


@dataclass(frozen=True)
class FeedingPlan:
    feed_at: datetime
    peak_hours: float


def validate(feeding: Feeding) -> None:
    if feeding.starter_g <= 0:
        raise FeedingError("Az anyakovász mennyisége legyen pozitív.")
    if feeding.flour_g <= 0 or feeding.water_g <= 0:
        raise FeedingError("A liszt és a víz mennyisége legyen pozitív.")
    if not MIN_TEMP_C <= feeding.temp_c <= MAX_TEMP_C:
        raise FeedingError(f"A hőmérséklet {MIN_TEMP_C:g}–{MAX_TEMP_C:g} °C között legyen.")


def hydration_percent(feeding: Feeding) -> float:
    return round(feeding.water_g / feeding.flour_g * 100, 1)


def dilution_ratio(feeding: Feeding) -> float:
    return (feeding.flour_g + feeding.water_g) / feeding.starter_g


def temperature_factor(temp_c: float) -> float:
    return 2 ** ((REFERENCE_TEMP_C - temp_c) / DOUBLING_DEGREES)


def hydration_factor(hydration: float) -> float:
    return max(0.8, min(1.3, 1 + (100 - hydration) * 0.003))


def dilution_factor(dilution: float) -> float:
    # 1:1:1 etetésnél a hígítás 2, ekkor a szorzó pontosan 1.
    return math.log2(1 + dilution) / math.log2(3)


def peak_hours(feeding: Feeding) -> float:
    """Hány óra múlva éri el a kovász a csúcsát az etetés után."""
    validate(feeding)
    hours = (
        REFERENCE_PEAK_HOURS
        * dilution_factor(dilution_ratio(feeding))
        * temperature_factor(feeding.temp_c)
        * hydration_factor(hydration_percent(feeding))
    )
    return round(hours, 2)


def status(feeding: Feeding, now: datetime) -> StarterStatus:
    """A kovász aktuális állapota az utolsó etetés alapján."""
    peak = peak_hours(feeding)
    elapsed = max(0.0, (now - feeding.fed_at).total_seconds() / 3600)
    progress = elapsed / peak
    stage = next((s for limit, s in STAGE_THRESHOLDS if progress < limit), Stage.HUNGRY)
    return StarterStatus(
        stage=stage,
        label=STAGE_LABELS[stage],
        hours_since_feeding=round(elapsed, 2),
        peak_hours=peak,
        peak_at=feeding.fed_at + timedelta(hours=peak),
        progress=round(progress, 3),
    )


def plan_feeding(
    starter_g: float, flour_g: float, water_g: float, temp_c: float, target_at: datetime
) -> FeedingPlan:
    """Mikor kell etetni, hogy a kovász a megadott időpontra érjen csúcsra."""
    template = Feeding(starter_g, flour_g, water_g, temp_c, fed_at=target_at)
    peak = peak_hours(template)
    return FeedingPlan(feed_at=target_at - timedelta(hours=peak), peak_hours=peak)


def suggest_ratio(hours_available: float, temp_c: float) -> dict:
    """Melyik 1:x:x arány ér csúcsra a rendelkezésre álló idő alatt."""
    if hours_available <= 0:
        raise FeedingError("A rendelkezésre álló idő legyen pozitív.")

    def peak_for(x: int) -> float:
        return peak_hours(Feeding(10, 10 * x, 10 * x, temp_c, fed_at=datetime.min))

    best_x, best_peak = 1, peak_for(1)
    for x in range(2, MAX_SUGGESTED_RATIO + 1):
        peak = peak_for(x)
        if abs(peak - hours_available) < abs(best_peak - hours_available):
            best_x, best_peak = x, peak

    warning = None
    if best_peak > hours_available * 1.25:
        warning = "Ezen a hőmérsékleten még 1:1:1 aránnyal sem lesz kész időben – keress melegebb helyet!"
    elif best_peak < hours_available * 0.75:
        warning = "Ennyi időre még 1:20:20 arány mellett is túlérik – tedd egy időre hűtőbe!"

    return {
        "ratio": f"1:{best_x}:{best_x}",
        "x": best_x,
        "peak_hours": best_peak,
        "temp_c": temp_c,
        "warning": warning,
    }
