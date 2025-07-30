from pydantic import BaseModel, Field
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
    netTotal: float = Field(..., alias="net_total")
    total: float
    worksiteName: str = Field(..., alias="worksite_name")
    worksiteId: Optional[int] = Field(default=None, alias="worksite_id")
    items: List[PendingInvoiceItem]
    totalMatch: bool = Field(..., alias="total_match")
    pdfUrl: str = Field(..., alias="pdf_url")
    confirmed: bool
    parsedAt: Optional[str] = Field(default=None, alias="parsed_at")
    reprocessedFromId: Optional[int] = Field(default=None, alias="reprocessed_from_id")

    class Config:
        allow_population_by_field_name = True
        orm_mode = True
