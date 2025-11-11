from __future__ import annotations
import importlib, inspect, pkgutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Type, Optional
from pydantic import BaseModel
from .base import Strategy

@dataclass
class StrategySpec:
    key: str
    cls: Type[Strategy]
    doc: str
    params_schema: Optional[dict]

class StrategyRegistry:
    def __init__(self, package: str = "strategies"):
        self.package = package
        self._specs: Dict[str, StrategySpec] = {}

    def list(self) -> list[StrategySpec]:
        return [self._specs[k] for k in sorted(self._specs)]

    def get(self, key: str) -> StrategySpec:
        if key not in self._specs:
            raise KeyError(f"Unknown strategy '{key}'")
        return self._specs[key]

    def build(self, key: str, params: dict | None = None) -> Strategy:
        return self.get(key).cls(params=params)

    def reload(self) -> None:
        self._specs.clear()
        pkg = importlib.import_module(self.package)
        pkg_path = Path(pkg.__file__).parent
        for m in pkgutil.iter_modules([str(pkg_path)]):
            if m.name.startswith("_") or m.name in ("base", "plugin_loader"):
                continue
            module_name = f"{self.package}.{m.name}"
            try:
                mod = importlib.import_module(module_name)
            except Exception as e:
                print(f"[strategy-loader] failed to import {module_name}: {e}")
                continue
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if not issubclass(obj, Strategy) or obj is Strategy:
                    continue
                key = getattr(obj, "name", "") or obj.__name__
                if key in self._specs:
                    print(f"[strategy-loader] duplicate key '{key}' in {module_name}, skipping")
                    continue
                params_schema = None
                Params = getattr(obj, "Params", None)
                if Params is not None and inspect.isclass(Params) and issubclass(Params, BaseModel):
                    params_schema = Params.model_json_schema()
                doc = getattr(obj, "doc", "") or (obj.__doc__ or "").strip()
                self._specs[key] = StrategySpec(key=key, cls=obj, doc=doc, params_schema=params_schema)

REGISTRY = StrategyRegistry()
REGISTRY.reload()

def load_strategies() -> list[Type[Strategy]]:
    """Load all available strategy classes."""
    REGISTRY.reload()
    return [spec.cls for spec in REGISTRY.list()]
