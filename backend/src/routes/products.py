"""
Product management routes with barcode support.
"""
import math
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.product import Product, ProductCategory, ProductStatus
from src.models.user import User, UserRole
from src.schemas.product import (
    BarcodeGenerateRequest,
    BarcodeResponse,
    ProductCategoryCreate,
    ProductCategoryResponse,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from src.services.auth_service import get_current_user, require_role
from src.services.barcode_service import BarcodeService

router = APIRouter()


# --- Categories ---

@router.get("/categories", response_model=list[ProductCategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all product categories."""
    result = await db.execute(
        select(ProductCategory).where(ProductCategory.is_active == True).order_by(ProductCategory.name)
    )
    categories = result.scalars().all()
    return [ProductCategoryResponse.model_validate(c) for c in categories]


@router.post("/categories", response_model=ProductCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    request: ProductCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create a new product category."""
    category = ProductCategory(
        id=str(uuid4()),
        **request.model_dump(),
    )
    db.add(category)
    await db.flush()
    return ProductCategoryResponse.model_validate(category)


# --- Products ---

@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[str] = None,
    status_filter: Optional[ProductStatus] = Query(None, alias="status"),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List products with pagination and filters."""
    query = select(Product)

    if category_id:
        query = query.where(Product.category_id == category_id)
    if status_filter:
        query = query.where(Product.status == status_filter)
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Product.name.ilike(search_filter))
            | (Product.sku.ilike(search_filter))
            | (Product.barcode.ilike(search_filter))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Product.name)
    result = await db.execute(query)
    products = result.scalars().all()

    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific product by ID."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse.model_validate(product)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    request: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
):
    """Create a new product."""
    existing = await db.execute(select(Product).where(Product.sku == request.sku))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with SKU '{request.sku}' already exists",
        )

    product = Product(
        id=str(uuid4()),
        **request.model_dump(),
    )
    db.add(product)
    await db.flush()
    return ProductResponse.model_validate(product)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    request: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.WAREHOUSE_MANAGER)),
):
    """Update a product."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await db.flush()
    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Discontinue a product (soft delete)."""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.status = ProductStatus.DISCONTINUED
    await db.flush()


# --- Barcode ---

@router.post("/barcode/generate", response_model=BarcodeResponse)
async def generate_barcode(
    request: BarcodeGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a barcode for a product."""
    service = BarcodeService(db)
    try:
        return await service.generate_barcode(request.product_id, request.barcode_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/barcode/lookup/{barcode_value}", response_model=ProductResponse)
async def lookup_barcode(
    barcode_value: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Look up a product by barcode value (for barcode scanning)."""
    service = BarcodeService(db)
    product = await service.lookup_by_barcode(barcode_value)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found for this barcode")
    return ProductResponse.model_validate(product)
