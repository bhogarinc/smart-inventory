"""
Initial data seed script for SmartInventory.
Run with: python -m src.seeds.initial_seed
"""
import asyncio
from uuid import uuid4

from sqlalchemy import select

from src.config import settings
from src.database import async_session_factory, init_db
from src.models.product import Product, ProductCategory
from src.models.user import User, UserRole
from src.models.warehouse import Warehouse
from src.services.auth_service import hash_password


async def seed_data():
    """Seed initial data into the database."""
    await init_db()

    async with async_session_factory() as session:
        # Check if data already exists
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return

        print("Seeding initial data...")

        # Create admin user
        admin = User(
            id=str(uuid4()),
            email="admin@smartinventory.com",
            hashed_password=hash_password("Admin123!@#"),
            first_name="System",
            last_name="Admin",
            role=UserRole.ADMIN,
        )
        session.add(admin)

        # Create warehouse manager
        manager = User(
            id=str(uuid4()),
            email="manager@smartinventory.com",
            hashed_password=hash_password("Manager123!@#"),
            first_name="Warehouse",
            last_name="Manager",
            role=UserRole.WAREHOUSE_MANAGER,
        )
        session.add(manager)

        # Create API consumer
        api_user = User(
            id=str(uuid4()),
            email="api@smartinventory.com",
            hashed_password=hash_password("ApiUser123!@#"),
            first_name="ERP",
            last_name="Integration",
            role=UserRole.API_CONSUMER,
        )
        session.add(api_user)

        # Create warehouses
        warehouses = [
            Warehouse(
                id=str(uuid4()),
                name="Main Distribution Center",
                code="WH-MAIN",
                address="1234 Distribution Blvd",
                city="Dallas",
                state="TX",
                country="US",
                zip_code="75201",
                capacity=50000,
                is_primary=True,
                manager_name="John Smith",
                manager_email="john.smith@smartinventory.com",
                phone="+1-214-555-0100",
                latitude=32.7767,
                longitude=-96.7970,
            ),
            Warehouse(
                id=str(uuid4()),
                name="East Coast Warehouse",
                code="WH-EAST",
                address="5678 Logistics Ave",
                city="Newark",
                state="NJ",
                country="US",
                zip_code="07102",
                capacity=30000,
                manager_name="Sarah Johnson",
                manager_email="sarah.johnson@smartinventory.com",
                phone="+1-973-555-0200",
                latitude=40.7357,
                longitude=-74.1724,
            ),
            Warehouse(
                id=str(uuid4()),
                name="West Coast Fulfillment",
                code="WH-WEST",
                address="9012 Pacific Way",
                city="Los Angeles",
                state="CA",
                country="US",
                zip_code="90001",
                capacity=40000,
                manager_name="Mike Chen",
                manager_email="mike.chen@smartinventory.com",
                phone="+1-213-555-0300",
                latitude=34.0522,
                longitude=-118.2437,
            ),
        ]
        for wh in warehouses:
            session.add(wh)

        # Create product categories
        electronics = ProductCategory(
            id=str(uuid4()), name="Electronics", description="Electronic devices and accessories"
        )
        clothing = ProductCategory(
            id=str(uuid4()), name="Clothing", description="Apparel and fashion items"
        )
        home_garden = ProductCategory(
            id=str(uuid4()), name="Home & Garden", description="Home improvement and garden supplies"
        )
        sports = ProductCategory(
            id=str(uuid4()), name="Sports & Outdoors", description="Sports equipment and outdoor gear"
        )
        for cat in [electronics, clothing, home_garden, sports]:
            session.add(cat)

        # Create sample products
        products = [
            Product(
                id=str(uuid4()),
                sku="ELEC-LAPTOP-001",
                barcode="8901234567890",
                name='ProBook Laptop 15.6"',
                description="High-performance laptop with 16GB RAM, 512GB SSD",
                category_id=electronics.id,
                unit_price=899.99,
                cost_price=650.00,
                weight=2.1,
                weight_unit="kg",
                min_stock_level=20,
                max_stock_level=500,
                reorder_point=50,
                reorder_quantity=100,
                lead_time_days=14,
                supplier_name="TechSupply Inc.",
            ),
            Product(
                id=str(uuid4()),
                sku="ELEC-PHONE-001",
                barcode="8901234567891",
                name="SmartPhone X Pro",
                description="Latest smartphone with 128GB storage",
                category_id=electronics.id,
                unit_price=699.99,
                cost_price=450.00,
                weight=0.2,
                weight_unit="kg",
                min_stock_level=50,
                max_stock_level=2000,
                reorder_point=200,
                reorder_quantity=500,
                lead_time_days=10,
                supplier_name="MobileWorld Ltd.",
            ),
            Product(
                id=str(uuid4()),
                sku="CLOTH-TSHIRT-001",
                barcode="8901234567892",
                name="Premium Cotton T-Shirt",
                description="100% organic cotton t-shirt, multiple colors",
                category_id=clothing.id,
                unit_price=29.99,
                cost_price=8.50,
                weight=0.2,
                weight_unit="kg",
                min_stock_level=100,
                max_stock_level=5000,
                reorder_point=500,
                reorder_quantity=1000,
                lead_time_days=21,
                supplier_name="FashionFab Co.",
            ),
            Product(
                id=str(uuid4()),
                sku="HOME-LAMP-001",
                barcode="8901234567893",
                name="Smart LED Desk Lamp",
                description="Adjustable brightness, USB charging port",
                category_id=home_garden.id,
                unit_price=49.99,
                cost_price=18.00,
                weight=1.5,
                weight_unit="kg",
                min_stock_level=30,
                max_stock_level=800,
                reorder_point=100,
                reorder_quantity=200,
                lead_time_days=14,
                supplier_name="HomeStyle Supplies",
            ),
            Product(
                id=str(uuid4()),
                sku="SPORT-YOGA-001",
                barcode="8901234567894",
                name="Premium Yoga Mat",
                description="Non-slip, eco-friendly yoga mat 6mm thick",
                category_id=sports.id,
                unit_price=39.99,
                cost_price=12.00,
                weight=1.2,
                weight_unit="kg",
                min_stock_level=50,
                max_stock_level=1500,
                reorder_point=200,
                reorder_quantity=400,
                lead_time_days=18,
                supplier_name="FitGear International",
            ),
        ]
        for prod in products:
            session.add(prod)

        await session.commit()
        print(f"Seeded: 3 users, {len(warehouses)} warehouses, 4 categories, {len(products)} products")
        print("Default credentials:")
        print("  Admin: admin@smartinventory.com / Admin123!@#")
        print("  Manager: manager@smartinventory.com / Manager123!@#")


if __name__ == "__main__":
    asyncio.run(seed_data())
