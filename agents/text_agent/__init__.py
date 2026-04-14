"""Text Agent - A2A compliant customer service agent."""

from .knowledge_base import (
    ProductInfo,
    TroubleshootingEntry,
    analyze_situation,
    get_product_by_sku,
    search_products,
    search_troubleshooting,
)

__all__ = [
    "ProductInfo",
    "TroubleshootingEntry",
    "analyze_situation",
    "get_product_by_sku",
    "search_products",
    "search_troubleshooting",
]
