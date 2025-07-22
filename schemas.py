# invoice_parser/models/schemas.py

from pydantic import BaseModel
from typing import List


class InvoiceRequest(BaseModel):
    url: str


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
    items: List[PendingInvoiceItem]
    totalMatch: bool
    pdfUrl: str
    confirmed: bool
    parsedAt: str
