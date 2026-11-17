"""Egyszerű, szálbiztos memóriabeli tároló (újraindításkor kiürül)."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from app.fermentation import Feeding


@dataclass
class Starter:
    id: int
    name: str
    flour_type: str
    feedings: list[Feeding] = field(default_factory=list)

    @property
    def last_feeding(self) -> Feeding | None:
        return max(self.feedings, key=lambda f: f.fed_at, default=None)


class StarterStore:
    def __init__(self) -> None:
        self._starters: dict[int, Starter] = {}
        self._next_id = 1
        self._lock = Lock()

    def create(self, name: str, flour_type: str) -> Starter:
        with self._lock:
            starter = Starter(id=self._next_id, name=name, flour_type=flour_type)
            self._starters[starter.id] = starter
            self._next_id += 1
            return starter

    def all_starters(self) -> list[Starter]:
        with self._lock:
            return sorted(self._starters.values(), key=lambda s: s.id)

    def get(self, starter_id: int) -> Starter | None:
        return self._starters.get(starter_id)

    def add_feeding(self, starter_id: int, feeding: Feeding) -> None:
        with self._lock:
            self._starters[starter_id].feedings.append(feeding)