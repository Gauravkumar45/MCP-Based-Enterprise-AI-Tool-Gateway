"""Database seed script populating RBAC entities, business records, and knowledge base documents."""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.auth.permissions import DEFAULT_ROLE_PERMISSIONS, PermissionName
from app.core.security import hash_password
from app.database.models import (
    Customer,
    Document,
    Invoice,
    Order,
    Permission,
    Role,
    User,
)
from app.database.session import session_scope


async def seed_database() -> None:
    """Populate database with initial roles, permissions, users, documents, and business data."""
    async with session_scope() as session:
        print("[SEED] Starting database seeding...")

        # 1. Seed Permissions
        permissions_map: dict[str, Permission] = {}
        for perm_enum in PermissionName:
            stmt = select(Permission).where(Permission.name == perm_enum.value)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                perm = Permission(
                    name=perm_enum.value,
                    description=f"Permission granting access to {perm_enum.value}",
                )
                session.add(perm)
                permissions_map[perm_enum.value] = perm
            else:
                permissions_map[perm_enum.value] = existing

        await session.flush()
        print(f"[SEED] Seeded/verified {len(permissions_map)} permissions.")

        # 2. Seed Roles and Mappings
        roles_map: dict[str, Role] = {}
        for role_name, perm_names in DEFAULT_ROLE_PERMISSIONS.items():
            from sqlalchemy.orm import selectinload

            stmt = (
                select(Role).options(selectinload(Role.permissions)).where(Role.name == role_name)
            )
            role = (await session.execute(stmt)).scalar_one_or_none()
            if not role:
                role = Role(
                    name=role_name,
                    description=f"Enterprise {role_name.capitalize()} Role",
                )
                session.add(role)
                await session.flush()
                # Re-query with eager loading
                stmt = (
                    select(Role)
                    .options(selectinload(Role.permissions))
                    .where(Role.name == role_name)
                )
                role = (await session.execute(stmt)).scalar_one()

            # Assign permissions
            current_perms = {p.name for p in role.permissions}
            for p_name in perm_names:
                if p_name not in current_perms and p_name in permissions_map:
                    role.permissions.append(permissions_map[p_name])

            roles_map[role_name] = role

        await session.flush()
        print(f"[SEED] Seeded/verified {len(roles_map)} roles.")

        # 3. Seed Users
        users_to_create = [
            ("admin", "admin@enterprise.internal", "Password123!", "admin"),
            ("analyst", "analyst@enterprise.internal", "Password123!", "analyst"),
            ("viewer", "viewer@enterprise.internal", "Password123!", "viewer"),
            ("copilot_agent", "agent@enterprise.internal", "Password123!", "agent"),
        ]

        for username, email, password, role_name in users_to_create:
            stmt = select(User).options(selectinload(User.roles)).where(User.username == username)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if not user:
                user = User(
                    username=username,
                    email=email,
                    hashed_password=hash_password(password),
                    is_active=True,
                )
                user.roles.append(roles_map[role_name])
                session.add(user)
                print(f"[SEED] Created user: {username} (role: {role_name})")

        # 4. Seed Enterprise Customers
        sample_customers = [
            ("CUST-1001", "Acme Corporation", "billing@acme.com", "enterprise", 450000.0, "active"),
            (
                "CUST-1002",
                "Globex Industrial",
                "finance@globex.com",
                "enterprise",
                320000.0,
                "active",
            ),
            ("CUST-1003", "Initech Software", "peter@initech.com", "premium", 185000.0, "active"),
            (
                "CUST-1004",
                "Umbrella Pharmaceuticals",
                "procure@umbrella.corp",
                "enterprise",
                620000.0,
                "active",
            ),
            (
                "CUST-1005",
                "Cyberdyne Systems",
                "ops@cyberdyne.io",
                "enterprise",
                540000.0,
                "active",
            ),
            ("CUST-1006", "Hooli Tech", "gavin@hooli.xyz", "premium", 210000.0, "active"),
            ("CUST-1007", "Pied Piper", "richard@piedpiper.com", "standard", 45000.0, "active"),
            (
                "CUST-1008",
                "Massive Dynamic",
                "walter@massivedynamic.com",
                "enterprise",
                390000.0,
                "active",
            ),
            (
                "CUST-1009",
                "Wayne Enterprises",
                "bruce@wayne-ent.com",
                "enterprise",
                890000.0,
                "active",
            ),
            ("CUST-1010", "Stark Industries", "tony@stark.org", "enterprise", 950000.0, "active"),
        ]

        for cid, name, email, tier, ltv, status in sample_customers:
            stmt = select(Customer).where(Customer.customer_id == cid)
            cust = (await session.execute(stmt)).scalar_one_or_none()
            if not cust:
                session.add(
                    Customer(
                        customer_id=cid,
                        name=name,
                        email=email,
                        tier=tier,
                        lifetime_value=ltv,
                        status=status,
                    )
                )

        await session.flush()
        print("[SEED] Seeded enterprise customers.")

        # 5. Seed Invoices and Orders
        now = datetime.now(UTC)
        sample_invoices = [
            (
                "INV-2024-001",
                "CUST-1010",
                125000.0,
                "paid",
                now - timedelta(days=15),
                now - timedelta(days=45),
            ),
            (
                "INV-2024-002",
                "CUST-1009",
                98000.0,
                "paid",
                now - timedelta(days=20),
                now - timedelta(days=50),
            ),
            (
                "INV-2024-003",
                "CUST-1004",
                82000.0,
                "paid",
                now - timedelta(days=10),
                now - timedelta(days=40),
            ),
            (
                "INV-2024-004",
                "CUST-1005",
                75000.0,
                "pending",
                now + timedelta(days=15),
                now - timedelta(days=15),
            ),
            (
                "INV-2024-005",
                "CUST-1001",
                64000.0,
                "paid",
                now - timedelta(days=5),
                now - timedelta(days=35),
            ),
            (
                "INV-2024-006",
                "CUST-1008",
                53000.0,
                "overdue",
                now - timedelta(days=5),
                now - timedelta(days=60),
            ),
            (
                "INV-2024-007",
                "CUST-1002",
                41000.0,
                "paid",
                now - timedelta(days=25),
                now - timedelta(days=55),
            ),
            (
                "INV-2024-008",
                "CUST-1006",
                32000.0,
                "paid",
                now - timedelta(days=18),
                now - timedelta(days=48),
            ),
            (
                "INV-2024-009",
                "CUST-1003",
                27000.0,
                "paid",
                now - timedelta(days=12),
                now - timedelta(days=42),
            ),
            (
                "INV-2024-010",
                "CUST-1007",
                12000.0,
                "pending",
                now + timedelta(days=20),
                now - timedelta(days=10),
            ),
        ]

        for inv_id, cust_id, amount, inv_status, due_date, issued_date in sample_invoices:
            stmt = select(Invoice).where(Invoice.invoice_id == inv_id)
            inv = (await session.execute(stmt)).scalar_one_or_none()
            if not inv:
                session.add(
                    Invoice(
                        invoice_id=inv_id,
                        customer_id=cust_id,
                        amount=amount,
                        currency="USD",
                        status=inv_status,
                        due_date=due_date,
                        issued_date=issued_date,
                    )
                )

        sample_orders = [
            ("ORD-9001", "CUST-1010", 125000.0, "delivered", 10, "TRK-STARK-01"),
            ("ORD-9002", "CUST-1009", 98000.0, "delivered", 8, "TRK-WAYNE-02"),
            ("ORD-9003", "CUST-1004", 82000.0, "shipped", 15, "TRK-UMBR-03"),
            ("ORD-9004", "CUST-1005", 75000.0, "processing", 4, "TRK-CYBER-04"),
            ("ORD-9005", "CUST-1001", 64000.0, "delivered", 12, "TRK-ACME-05"),
        ]

        for ord_id, cust_id, total, ord_status, items, trk in sample_orders:
            stmt = select(Order).where(Order.order_id == ord_id)
            order = (await session.execute(stmt)).scalar_one_or_none()
            if not order:
                session.add(
                    Order(
                        order_id=ord_id,
                        customer_id=cust_id,
                        total_amount=total,
                        status=ord_status,
                        items_count=items,
                        tracking_number=trk,
                    )
                )

        await session.flush()
        print("[SEED] Seeded invoices and orders.")

        # 6. Seed Knowledge Base Documents
        sample_documents = [
            (
                "DOC-SEC-001",
                "Enterprise MCP Gateway Security Policy",
                "All external agents must authenticate via signed JWT tokens carrying RBAC scopes. Tools with database access require read-only query validation through AST parsers. Data mutations like DROP, ALTER, and DELETE are strictly forbidden. Rate limits are set to 10 requests per minute by default.",
                "security",
                "wiki/infosec/mcp_policy.md",
            ),
            (
                "DOC-OPS-002",
                "High Availability Architecture and Disaster Recovery",
                "The MCP Gateway is deployed across multiple availability zones behind a layer-7 load balancer. PostgreSQL read-replicas handle analytics and query_database workloads, while Redis clusters provide sub-millisecond rate limit enforcement.",
                "architecture",
                "wiki/ops/ha_architecture.md",
            ),
            (
                "DOC-FIN-003",
                "Enterprise Billing and SLA Terms 2024",
                "Enterprise tier accounts (e.g. Stark Industries, Wayne Enterprises, Acme Corp) receive dedicated 99.99% availability SLAs, 30-day payment terms, and custom rate limits for LLM agent integrations.",
                "finance",
                "wiki/legal/sla_2024.md",
            ),
            (
                "DOC-RUN-004",
                "Incident Runbook: Database Latency Spikes",
                "In case of elevated query latency exceeding 500ms, examine slow query logs in pg_stat_statements. Check active connections in connection pool. The gateway will automatically trigger TOOL_TIMEOUT if execution exceeds 10 seconds.",
                "runbook",
                "wiki/runbooks/db_latency.md",
            ),
        ]

        for doc_id, title, content, cat, src in sample_documents:
            stmt = select(Document).where(Document.document_id == doc_id)
            doc = (await session.execute(stmt)).scalar_one_or_none()
            if not doc:
                session.add(
                    Document(
                        document_id=doc_id,
                        title=title,
                        content=content,
                        category=cat,
                        source=src,
                    )
                )

        await session.flush()
        print("[SEED] Seeded knowledge base documents.")
        print("[SEED] Database seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_database())
