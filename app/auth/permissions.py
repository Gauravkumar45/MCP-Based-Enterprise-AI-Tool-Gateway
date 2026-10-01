"""Role-Based Access Control (RBAC) permissions and default role mappings."""

from enum import Enum


class PermissionName(str, Enum):
    """System permissions required to invoke specific enterprise gateway tools."""

    DATABASE_READ = "database.read"
    DOCUMENTS_SEARCH = "documents.search"
    CUSTOMER_READ = "customer.read"
    INVOICE_READ = "invoice.read"
    ORDER_READ = "order.read"
    SYSTEM_STATUS = "system.status"
    KPI_CALCULATE = "kpi.calculate"
    AUDIT_READ = "audit.read"


class RoleName(str, Enum):
    """Standard enterprise roles."""

    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    AGENT = "agent"


# Default permission matrix
DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    RoleName.ADMIN.value: [
        PermissionName.DATABASE_READ.value,
        PermissionName.DOCUMENTS_SEARCH.value,
        PermissionName.CUSTOMER_READ.value,
        PermissionName.INVOICE_READ.value,
        PermissionName.ORDER_READ.value,
        PermissionName.SYSTEM_STATUS.value,
        PermissionName.KPI_CALCULATE.value,
        PermissionName.AUDIT_READ.value,
    ],
    RoleName.ANALYST.value: [
        PermissionName.DATABASE_READ.value,
        PermissionName.DOCUMENTS_SEARCH.value,
        PermissionName.CUSTOMER_READ.value,
        PermissionName.INVOICE_READ.value,
        PermissionName.ORDER_READ.value,
        PermissionName.KPI_CALCULATE.value,
    ],
    RoleName.AGENT.value: [
        PermissionName.DATABASE_READ.value,
        PermissionName.DOCUMENTS_SEARCH.value,
        PermissionName.CUSTOMER_READ.value,
        PermissionName.INVOICE_READ.value,
        PermissionName.ORDER_READ.value,
        PermissionName.SYSTEM_STATUS.value,
        PermissionName.KPI_CALCULATE.value,
    ],
    RoleName.VIEWER.value: [
        PermissionName.DOCUMENTS_SEARCH.value,
        PermissionName.SYSTEM_STATUS.value,
    ],
}
