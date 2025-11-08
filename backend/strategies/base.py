from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Type
from pydantic import BaseModel

@dataclass
class Bar:
    ts: float  # epoch seconds
    o: float
    h: float
    l: float
    c: float
    v: Optional[float] = None

class BacktestContext:
    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.position = 0.0
        self.cash = 0.0
        self.meta: Dict[str, Any] = {}

class Strategy:
    """
    Drop-in plugin base.
    REQUIRED: 'name', 'on_bar'
    OPTIONAL: 'Params' (Pydantic), 'doc'
    """
    name: str = "unnamed"
    doc: str = ""
    Params: Optional[Type[BaseModel]] = None

    def __init__(self, params: Dict[str, Any] | None = None):
        self.params = params or {}
        if self.Params is not None:
            self.params = self.Params(**self.params).model_dump()

    def on_start(self, ctx: BacktestContext) -> None:
        pass

    def on_bar(self, bar: Bar, ctx: BacktestContext) -> None:
        raise NotImplementedError

    def on_stop(self, ctx: BacktestContext) -> None:
        pass
