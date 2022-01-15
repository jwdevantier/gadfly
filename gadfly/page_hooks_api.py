from pathlib import Path
from typing import Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from gadfly.config import Config


class PagePreCompileHookFn:
    def __call__(self, page_path: Path, config: "Config", extra_vars: Dict) -> bool:
        ...


class PagePostCompileHookFn:
    def __call__(self, page_path: Path, config: "Config", page_content: str) -> Optional[str]:
        ...


__all__ = [
    "PagePreCompileHookFn",
    "PagePostCompileHookFn",
]