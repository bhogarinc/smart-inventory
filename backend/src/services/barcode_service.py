"""
Barcode generation service for SKU management.
"""
import base64
import io
from typing import Optional

import barcode
from barcode.writer import ImageWriter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.product import Product
from src.schemas.product import BarcodeResponse


class BarcodeService:
    """Service for generating and managing barcodes."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_barcode(
        self,
        product_id: str,
        barcode_type: str = "code128",
    ) -> BarcodeResponse:
        """Generate a barcode image for a product."""
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Use existing barcode or generate from SKU
        barcode_data = product.barcode or product.sku

        # Generate barcode image
        barcode_class = barcode.get_barcode_class(barcode_type)
        barcode_instance = barcode_class(barcode_data, writer=ImageWriter())

        # Render to bytes
        buffer = io.BytesIO()
        barcode_instance.write(buffer, options={
            "module_width": 0.4,
            "module_height": 15.0,
            "font_size": 10,
            "text_distance": 5.0,
            "quiet_zone": 6.5,
        })
        buffer.seek(0)

        # Encode to base64
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Update product barcode if not set
        if not product.barcode:
            product.barcode = barcode_data
            await self.db.flush()

        return BarcodeResponse(
            product_id=product.id,
            sku=product.sku,
            barcode=barcode_data,
            barcode_image_base64=image_base64,
        )

    async def lookup_by_barcode(self, barcode_value: str) -> Optional[Product]:
        """Look up a product by its barcode."""
        result = await self.db.execute(
            select(Product).where(Product.barcode == barcode_value)
        )
        return result.scalar_one_or_none()
