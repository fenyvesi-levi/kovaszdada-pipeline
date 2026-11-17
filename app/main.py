"""Kovászdada – FastAPI alkalmazás (HTTP réteg)."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from app import fermentation as fm
from app.models import FeedingIn, PlanIn, StarterCreate
from app.store import Starter, StarterStore

APP_VERSION = os.getenv("APP_VERSION", "dev")
STATIC_DIR = Path(__file__).parent / "static"
FUTURE_TOLERANCE = timedelta(minutes=5)


def _utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _feeding_out(f: fm.Feeding) -> dict:
    peak = fm.peak_hours(f)
    return {
        "starter_g": f.starter_g,
        "flour_g": f.flour_g,
        "water_g": f.water_g,
        "temp_c": f.temp_c,
        "fed_at": f.fed_at.isoformat(),
        "hydration_percent": fm.hydration_percent(f),
        "peak_hours": peak,
        "peak_at": (f.fed_at + timedelta(hours=peak)).isoformat(),
    }


def _status_out(f: fm.Feeding, now: datetime) -> dict:
    s = fm.status(f, now)
    return {
        "stage": s.stage.value,
        "label": s.label,
        "hours_since_feeding": s.hours_since_feeding,
        "peak_hours": s.peak_hours,
        "peak_at": s.peak_at.isoformat(),
        "progress": s.progress,
    }


def _starter_out(starter: Starter, now: datetime) -> dict:
    last = starter.last_feeding
    return {
        "id": starter.id,
        "name": starter.name,
        "flour_type": starter.flour_type,
        "feedings_count": len(starter.feedings),
        "last_feeding": _feeding_out(last) if last else None,
        "status": _status_out(last, now) if last else None,
    }


def _seed_demo(store: StarterStore) -> None:
    now = datetime.now(timezone.utc)
    bubi = store.create("Bubi", "BL-80 fehér")
    store.add_feeding(bubi.id, fm.Feeding(20, 40, 40, 23.0, now - timedelta(hours=3)))
    rozi = store.create("Rozsdás Rozi", "RL-90 rozs")
    store.add_feeding(rozi.id, fm.Feeding(10, 10, 10, 24.0, now - timedelta(hours=14)))


def create_app(seed: bool | None = None) -> FastAPI:
    if seed is None:
        seed = os.getenv("SEED_DEMO", "true").lower() == "true"

    app = FastAPI(
        title="Kovászdada",
        version=APP_VERSION,
        description="Kovászgondozó: etetésnapló, csúcsidő-becslés, sütéstervező.",
    )
    store = StarterStore()
    if seed:
        _seed_demo(store)
    app.state.store = store

    @app.exception_handler(fm.FeedingError)
    async def feeding_error_handler(_: Request, exc: fm.FeedingError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    def get_starter_or_404(starter_id: int) -> Starter:
        starter = store.get(starter_id)
        if starter is None:
            raise HTTPException(status_code=404, detail="Nincs ilyen kovász.")
        return starter

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": APP_VERSION, "starters": len(store.all_starters())}

    @app.get("/api/starters")
    def list_starters() -> list[dict]:
        now = _utc(None)
        return [_starter_out(s, now) for s in store.all_starters()]

    @app.post("/api/starters", status_code=201)
    def create_starter(body: StarterCreate) -> dict:
        starter = store.create(body.name, body.flour_type)
        return _starter_out(starter, _utc(None))

    @app.get("/api/starters/{starter_id}")
    def get_starter(starter_id: int) -> dict:
        starter = get_starter_or_404(starter_id)
        out = _starter_out(starter, _utc(None))
        out["feedings"] = [_feeding_out(f) for f in starter.feedings]
        return out

    @app.post("/api/starters/{starter_id}/feedings", status_code=201)
    def add_feeding(starter_id: int, body: FeedingIn) -> dict:
        get_starter_or_404(starter_id)
        now = _utc(None)
        fed_at = _utc(body.fed_at)
        if fed_at > now + FUTURE_TOLERANCE:
            raise HTTPException(status_code=422, detail="Az etetés ideje nem lehet a jövőben.")
        feeding = fm.Feeding(body.starter_g, body.flour_g, body.water_g, body.temp_c, fed_at)
        fm.validate(feeding)
        store.add_feeding(starter_id, feeding)
        return _feeding_out(feeding)

    @app.get("/api/starters/{starter_id}/status")
    def starter_status(starter_id: int) -> dict:
        starter = get_starter_or_404(starter_id)
        last = starter.last_feeding
        if last is None:
            raise HTTPException(status_code=409, detail="Ennek a kovásznak még nincs etetése.")
        return {"starter_id": starter.id, "name": starter.name, **_status_out(last, _utc(None))}

    @app.post("/api/plan")
    def plan(body: PlanIn) -> dict:
        target = _utc(body.target_at)
        result = fm.plan_feeding(body.starter_g, body.flour_g, body.water_g, body.temp_c, target)
        return {
            "target_at": target.isoformat(),
            "feed_at": result.feed_at.isoformat(),
            "peak_hours": result.peak_hours,
            "already_late": result.feed_at < _utc(None),
        }

    @app.get("/api/suggest-ratio")
    def suggest_ratio(
        hours: float = Query(gt=0, le=48, description="Hány óra múlva sütnél"),
        temp_c: float = Query(ge=4, le=40, description="Szobahőmérséklet °C"),
    ) -> dict:
        return fm.suggest_ratio(hours, temp_c)

    return app


app = create_app()
