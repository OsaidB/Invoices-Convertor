from pydantic import BaseModel, Field
from typing import List, Optional


class InvoiceRequest(BaseModel):
    url: str
    originalId: Optional[int] = None


class PendingInvoiceItem(BaseModel):
    description: str
    quantity: float
    unitPrice: float = Field(..., alias="unit_price")
    totalPrice: float = Field(..., alias="total_price")
    materialId: Optional[int] = None

    class Config:
        populate_by_name = True


class PendingInvoice(BaseModel):
    id: Optional[int] = None
    date: str
    netTotal: float
    total: Optional[float] = None
    worksiteName: str
    worksiteId: Optional[int] = None
    items: List[PendingInvoiceItem]
    totalMatch: Optional[bool] = None
    pdfUrl: str
    confirmed: bool
    parsedAt: Optional[str] = None
    reprocessedFromId: Optional[int] = None

    class Config:
        populate_by_name = True
        from_attributes = True
