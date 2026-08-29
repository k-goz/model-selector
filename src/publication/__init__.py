"""发布产物的组装、签名与差异能力。"""

from .artifacts import build_catalog_signature, compare_catalogs

__all__ = ["build_catalog_signature", "compare_catalogs"]
