# invoice_processor/models/schemas.py

from pydantic import BaseModel
from typing import List
from typing import List, Optional


class InvoiceRequest(BaseModel):
    url: str
    originalId: int | None = None  # optional field


class PendingInvoiceItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    total_price: float


class PendingInvoice(BaseModel):
    date: str
    netTotal: float
    total: float
    worksiteName: str
    worksiteId: Optional[int] = None  
    items: List[PendingInvoiceItem]
    totalMatch: bool
    pdfUrl: str
    confirmed: bool
    parsedAt: Optional[str] = None
    reprocessedFromId: Optional[int] = None
