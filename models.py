from pydantic import BaseModel, Field

class TranslatedInvoiceOutput(BaseModel):
    """Enforces standard English schema output from native Chinese documents."""
    vendor_name: str = Field(
        description="The name of the company issuing the invoice. Translate this name into English if it is in Chinese characters (e.g., convert '北京科技有限公司' to 'Beijing Technology Co., Ltd.')."
    )
    invoice_id: str = Field(
        description="The unique invoice reference number or identifier code (发票号码)."
    )
    invoice_date: str = Field(
        description="The date of issue formatted strictly as YYYY-MM-DD."
    )
    total_amount: float = Field(
        description="The final total balance due on the invoice, parsed as a float number."
    )
    currency: str = Field(
        description="The three-letter standard ISO currency code (e.g., CNY for Chinese Yuan, USD, etc.)."
    )
    line_item_summary: str = Field(
        description="A concise English summary of the goods or services rendered, translated from the Chinese description column."
    )
