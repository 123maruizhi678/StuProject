"""客户研判 5 表。"""

from app.models.customer.product import Product
from app.models.customer.customer_source import CustomerSource
from app.models.customer.customer_info import CustomerInfo
from app.models.customer.research_rule import ResearchRule
from app.models.customer.research_result import ResearchResult

__all__ = [
    "Product",
    "CustomerSource",
    "CustomerInfo",
    "ResearchRule",
    "ResearchResult",
]
