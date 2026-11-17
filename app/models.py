"""Bejövő kérések sémái (Pydantic)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StarterCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=40, description="A kovász neve, pl. Bubi")
    flour_type: str = Field(default="BL-80 fehér", min_length=1, max_length=40)


class FeedingIn(BaseModel):
    starter_g: float = Field(gt=0, le=5000, description="Anyakovász grammban")
    flour_g: float = Field(gt=0, le=5000, description="Liszt grammban")
    water_g: float = Field(gt=0, le=5000, description="Víz grammban")
    temp_c: float = Field(ge=4, le=40, description="Szobahőmérséklet °C-ban")
    fed_at: datetime | None = Field(default=None, description="Etetés ideje; ha üres: most")


class PlanIn(BaseModel):
    starter_g: float = Field(gt=0, le=5000)
    flour_g: float = Field(gt=0, le=5000)
    water_g: float = Field(gt=0, le=5000)
    temp_c: float = Field(ge=4, le=40)
    target_at: datetime = Field(description="Mikorra legyen csúcson (dagasztás ideje)")