"""Automated end-to-end demo simulating enterprise agent interactions, RBAC security, and audit trails."""

import asyncio
import json
import time

from sqlalchemy import desc, select

from app.agent.graph import EnterpriseAgent
from app.auth.permissions import DEFAULT_ROLE_PERMISSIONS
from app.core.security import create_access_token
from app.database.models import AuditLog
from app.database.session import session_scope
from app.mcp.client import EnterpriseMCPClient


def print_banner(title: str) -> None:
    print("\n" + "=" * 75)
    print(f"  {title.upper()}")
    print("=" * 75)


async def run_enterprise_demo() -> None:
    """Run full enterprise demo scenarios."""
    print_banner("MCP-Based Enterprise AI Tool Gateway — Interactive Demonstration")
    print("Initializing components and tokens...")

    # Issue realistic JWT tokens for roles
    analyst_token = create_access_token(
        user_id="user-analyst-bob",
        username="analyst_bob",
        roles=["analyst"],
        permissions=DEFAULT_ROLE_PERMISSIONS["analyst"],
    )
    viewer_token = create_access_token(
        user_id="user-viewer-alice",
        username="viewer_alice",
        roles=["viewer"],
        permissions=DEFAULT_ROLE_PERMISSIONS["viewer"],
    )

    agent = EnterpriseAgent()

    # -------------------------------------------------------------
    # Scenario 1: Authorized Analyst — Database Analytics Flow
    # -------------------------------------------------------------
    print_banner("Scenario 1: Authorized Analyst — Top Customers Analysis")
    query_1 = "What were the top 5 customers by revenue last month?"
    print(f"User (Analyst): '{query_1}'")
    print("\nExecuting LangGraph Agent -> MCP Gateway pipeline...")

    t0 = time.perf_counter()
    res1 = await agent.run(query=query_1, auth_token=analyst_token)
    latency1 = (time.perf_counter() - t0) * 1000

    print(f"\n[✓] Agent Completed in {latency1:.2f}ms")
    print(f" - Discovered & Selected Tool: {res1['selected_tools'][0]['name']}")
    print(f" - Generated Parameters: {res1['selected_tools'][0]['arguments']}")
    print(f" - Status: {res1['status']}")
    print("\n[Executive Agent Output]:\n")
    print(res1["final_response"])

    # -------------------------------------------------------------
    # Scenario 2: Enterprise Knowledge Discovery — Document Search
    # -------------------------------------------------------------
    print_banner("Scenario 2: Enterprise Knowledge Discovery — Policy Retrieval")
    query_2 = "What is our enterprise security policy regarding rate limits?"
    print(f"User (Analyst): '{query_2}'")

    res2 = await agent.run(query=query_2, auth_token=analyst_token)
    print(f"\n[✓] Discovered & Selected Tool: {res2['selected_tools'][0]['name']}")
    print(
        f" - Tool Results Found: {len(res2['tool_results'][0]['result'].get('results', []))} documents"
    )
    print("\n[Executive Agent Output]:\n")
    print(res2["final_response"])

    # -------------------------------------------------------------
    # Scenario 3: Unauthorized Access Prevention (RBAC Enforcement)
    # -------------------------------------------------------------
    print_banner("Scenario 3: Zero-Trust RBAC Enforcement (Viewer Access Attempt)")
    query_3 = "Show me all database tables and customers by revenue"
    print(f"User (Viewer Alice): '{query_3}'")
    print("Viewer permissions: ['documents.search', 'system.status']")
    print("Target tool: 'query_database' (Requires 'database.read')")

    res3 = await agent.run(query=query_3, auth_token=viewer_token)
    print("\n[✓] Backend Security Result:")
    print(f" - Execution Error: {res3['execution_error']}")
    print("\n[Agent Safe Response]:\n")
    print(res3["final_response"])

    # -------------------------------------------------------------
    # Scenario 4: AST SQL Injection / Mutation Attack Defense
    # -------------------------------------------------------------
    print_banner("Scenario 4: SQL Injection & Mutation Defense via AST Validator")
    malicious_query = "SELECT * FROM customers; DROP TABLE audit_logs; --"
    print(f"Attacker attempts injection payload: '{malicious_query}'")

    client = EnterpriseMCPClient(token=analyst_token)
    attack_res = await client.call_tool("query_database", {"query": malicious_query})
    print("\n[✓] Gateway Security Defense Triggered:")
    print(json.dumps(attack_res, indent=2))

    # -------------------------------------------------------------
    # Scenario 5: PostgreSQL Immutable Audit Ledger Verification
    # -------------------------------------------------------------
    print_banner("Scenario 5: Immutable Audit Ledger Verification")
    print("Inspecting PostgreSQL 'audit_logs' table for latest invocation records...")

    async with session_scope() as session:
        stmt = select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(5)
        logs = (await session.execute(stmt)).scalars().all()

        print("\nLatest 5 Audit Records in Database:")
        print(f"{'REQUEST ID':<38} {'TOOL':<18} {'USER':<18} {'STATUS':<10} {'LATENCY'}")
        print("-" * 95)
        for log in logs:
            user = log.user_id or "anonymous"
            print(
                f"{log.request_id:<38} {log.tool_name:<18} {user:<18} {log.execution_status:<10} {log.latency_ms:.2f}ms"
            )

    print_banner("Demonstration Complete: All Systems Verified")


if __name__ == "__main__":
    asyncio.run(run_enterprise_demo())
