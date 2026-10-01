"""Interactive Streamlit UI for the MCP-Based Enterprise AI Tool Gateway & Analytics Copilot."""

import json
from typing import Any

import httpx
import pandas as pd
import streamlit as st

GATEWAY_URL = "http://localhost:8080"

st.set_page_config(
    page_title="Enterprise MCP Tool Gateway",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def api_request(
    method: str,
    path: str,
    token: str | None = None,
    json_data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    """Execute HTTP request against the Gateway API."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(
                method=method,
                url=f"{GATEWAY_URL}{path}",
                headers=headers,
                json=json_data,
                params=params,
            )
            return resp.status_code, resp.json()
    except Exception as e:
        return 500, {"error": "CONNECTION_FAILED", "message": str(e)}


# -------------------------------------------------------------
# Session State Initialization
# -------------------------------------------------------------
if "token" not in st.session_state:
    st.session_state.token = None
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def login_user(username: str, password: str = "Password123!") -> bool:
    """Authenticate and store token in session state."""
    status_code, data = api_request("POST", "/auth/login", json_data={"username": username, "password": password})
    if status_code == 200:
        st.session_state.token = data["access_token"]
        st.session_state.user_info = data
        return True
    st.error(f"Login failed: {data.get('detail', 'Unknown error')}")
    return False


# Auto-login as Analyst by default if not logged in
if not st.session_state.token:
    login_user("analyst")


# -------------------------------------------------------------
# Sidebar: Role Switcher & User Profile
# -------------------------------------------------------------
with st.sidebar:
    st.title("🛡️ Enterprise Gateway")
    st.caption("Model Context Protocol (MCP) Control Center")

    # Gateway Health Probe
    h_code, h_data = api_request("GET", "/health")
    if h_code == 200:
        st.success("🟢 Gateway: Online (Port 8080)")
    else:
        st.error(f"🔴 Gateway: Offline ({h_data.get('message', 'Unreachable')})")

    st.divider()

    st.subheader("👤 Role & Identity Switcher")
    st.caption("Switch active role to test RBAC privilege boundaries:")

    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        if st.button("Analyst", use_container_width=True, type="primary" if st.session_state.user_info and "analyst" in st.session_state.user_info.get("roles", []) else "secondary"):
            login_user("analyst")
            st.rerun()
    with col_r2:
        if st.button("Admin", use_container_width=True, type="primary" if st.session_state.user_info and "admin" in st.session_state.user_info.get("roles", []) else "secondary"):
            login_user("admin")
            st.rerun()
    with col_r3:
        if st.button("Viewer", use_container_width=True, type="primary" if st.session_state.user_info and "viewer" in st.session_state.user_info.get("roles", []) else "secondary"):
            login_user("viewer")
            st.rerun()

    # Active Profile Card
    if st.session_state.user_info:
        u = st.session_state.user_info
        st.markdown(f"**Username:** `{u.get('username')}`")
        st.markdown(f"**Roles:** `{', '.join(u.get('roles', []))}`")
        with st.expander("🔑 Granted Permissions"):
            for p in u.get("permissions", []):
                st.write(f"- `{p}`")

    st.divider()

    # Custom Login
    with st.expander("Custom Login"):
        c_user = st.text_input("Username", key="c_user")
        c_pass = st.text_input("Password", type="password", key="c_pass")
        if st.button("Login"):
            if login_user(c_user, c_pass):
                st.success("Authenticated!")
                st.rerun()


# -------------------------------------------------------------
# Main Application Tabs
# -------------------------------------------------------------
tab_chat, tab_tools, tab_sql, tab_audit = st.tabs([
    "💬 AI Analytics Copilot",
    "🧰 MCP Tool Catalog",
    "🛡️ SQL Safety Guard Sandbox",
    "📜 Immutable Audit Ledger",
])


# =============================================================
# TAB 1: AI Analytics Copilot
# =============================================================
with tab_chat:
    st.header("🤖 Enterprise AI Analytics Copilot")
    st.markdown(
        "Interact with the LangGraph agent. Tools are **dynamically discovered** via MCP and executed under **strict RBAC authorization**."
    )

    # Prompt suggestions
    st.caption("Quick Prompt Suggestions:")
    col_p1, col_p2, col_p3 = st.columns(3)
    selected_prompt: str | None = None
    with col_p1:
        if st.button("📊 Top 5 Customers by Revenue"):
            selected_prompt = "What were the top 5 customers by revenue last month?"
    with col_p2:
        if st.button("📜 Search Rate Limit Security Policy"):
            selected_prompt = "What is our enterprise security policy regarding rate limits?"
    with col_p3:
        if st.button("💰 Calculate Monthly Revenue"):
            selected_prompt = "Calculate the total revenue KPI for last month"

    # Display chat history
    for item in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(item["query"])
        with st.chat_message("assistant"):
            if item.get("plan"):
                with st.expander("🧠 LangGraph Planner Reasoning"):
                    st.info(item["plan"])
            if item.get("selected_tools"):
                with st.expander("🛠️ Executed MCP Tools"):
                    st.json(item["selected_tools"])
            if item.get("tool_results"):
                with st.expander("📦 Raw Structured Tool Result"):
                    st.json(item["tool_results"])
            st.markdown(item["final_response"])

    # Chat input
    user_input = st.chat_input("Ask a business question or request tool execution...")
    active_query = selected_prompt or user_input

    if active_query:
        with st.chat_message("user"):
            st.write(active_query)

        with st.chat_message("assistant"):
            with st.spinner("Agent discovering tools, planning, and executing via MCP..."):
                status_code, resp = api_request(
                    "POST",
                    "/agent/chat",
                    token=st.session_state.token,
                    json_data={"query": active_query},
                )

            if status_code == 200:
                if resp.get("plan"):
                    with st.expander("🧠 LangGraph Planner Reasoning", expanded=True):
                        st.info(resp["plan"])
                if resp.get("selected_tools"):
                    with st.expander("🛠️ Executed MCP Tools", expanded=True):
                        st.json(resp["selected_tools"])
                if resp.get("tool_results"):
                    with st.expander("📦 Raw Structured Tool Result"):
                        st.json(resp["tool_results"])

                st.markdown(resp["final_response"])

                st.session_state.chat_history.append({
                    "query": active_query,
                    "plan": resp.get("plan"),
                    "selected_tools": resp.get("selected_tools"),
                    "tool_results": resp.get("tool_results"),
                    "final_response": resp.get("final_response"),
                })
            else:
                err_msg = resp.get("message", resp.get("detail", "Error executing agent"))
                st.error(f"Execution Error: {err_msg}")


# =============================================================
# TAB 2: MCP Tool Catalog
# =============================================================
with tab_tools:
    st.header("🧰 Discovered Enterprise MCP Tools")
    st.markdown("Tools exposed through the Model Context Protocol based on your **active role permissions**.")

    t_code, tools_data = api_request("GET", "/tools", token=st.session_state.token)
    if t_code == 200 and tools_data:
        st.info(f"Discovered **{len(tools_data)} authorized tools** for current user.")

        for tool in tools_data:
            with st.container(border=True):
                col_t1, col_t2, col_t3, col_t4 = st.columns([3, 1, 1, 1])
                with col_t1:
                    st.subheader(f"`{tool['name']}`")
                    st.write(tool["description"])
                with col_t2:
                    st.metric("Risk Level", tool["risk_level"].upper())
                with col_t3:
                    st.metric("Timeout", f"{tool['timeout_seconds']}s")
                with col_t4:
                    st.metric("Required Perm", tool["required_permission"])

                with st.expander("Inspect JSON Schema"):
                    st.json(tool.get("input_schema", {}))
    else:
        st.warning("No tools authorized for current credentials or gateway unreachable.")


# =============================================================
# TAB 3: SQL Safety Guard Sandbox
# =============================================================
with tab_sql:
    st.header("🛡️ SQL Safety & AST Validation Sandbox")
    st.markdown("Test the **SQLGlot AST parser** against malicious or destructive SQL queries in real time.")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.subheader("Test Query")
        sample_choice = st.selectbox(
            "Quick Attack Samples:",
            [
                "Custom Query",
                "DROP TABLE users;",
                "SELECT * FROM customers; DROP TABLE audit_logs; --",
                "SELECT * FROM pg_shadow;",
                "UPDATE users SET is_active = false;",
                "DELETE FROM invoices WHERE amount > 0;",
                "SELECT name, tier, lifetime_value FROM customers ORDER BY lifetime_value DESC LIMIT 5",
            ],
        )

        default_sql = (
            "SELECT name, tier, lifetime_value FROM customers ORDER BY lifetime_value DESC LIMIT 5"
            if sample_choice == "Custom Query"
            else sample_choice
        )
        sql_input = st.text_area("SQL Statement:", value=default_sql, height=120)
        run_sql = st.button("Execute Safety Verification", type="primary")

    with col_s2:
        st.subheader("AST Security Evaluation")
        if run_sql:
            with st.spinner("Analyzing AST and checking policy..."):
                exec_code, exec_data = api_request(
                    "POST",
                    "/tools/query_database/execute",
                    token=st.session_state.token,
                    json_data={"arguments": {"query": sql_input, "limit": 10}},
                )

            if exec_code == 200 and "error" not in exec_data:
                st.success("✅ Query Approved & Executed (Safe Read-Only SELECT)")
                st.metric("Rows Returned", exec_data.get("row_count", 0))
                st.metric("Execution Latency", f"{exec_data.get('execution_time_ms', 0)} ms")
                if exec_data.get("rows"):
                    st.dataframe(pd.DataFrame(exec_data["rows"]), use_container_width=True)
            else:
                st.error("🚨 QUERY BLOCKED BY GATEWAY SAFETY GUARD")
                err_detail = exec_data.get("message") or exec_data.get("detail", str(exec_data))
                st.code(err_detail, language="text")


# =============================================================
# TAB 4: Immutable Audit Ledger
# =============================================================
with tab_audit:
    st.header("📜 Immutable Audit Ledger")
    st.markdown("Cryptographically hashed and timestamped trace of every tool invocation attempt.")

    col_a1, col_a2 = st.columns([1, 4])
    with col_a1:
        refresh_audit = st.button("🔄 Refresh Ledger")
        status_filter = st.selectbox("Status Filter", ["All", "SUCCESS", "FAILED", "DENIED"])

    with col_a2:
        params: dict[str, Any] = {"limit": 50}
        if status_filter != "All":
            params["status"] = status_filter

        a_code, a_data = api_request("GET", "/audit/logs", token=st.session_state.token, params=params)

        if a_code == 200 and a_data.get("items"):
            items = a_data["items"]
            df = pd.DataFrame(items)
            df = df[["timestamp", "tool_name", "user_id", "execution_status", "latency_ms", "request_id", "input_hash"]]
            st.dataframe(df, use_container_width=True, height=500)
        elif a_code == 403:
            st.warning("🔒 Access Restricted: Current role lacks `audit.read` permission. Switch to the **Admin** role in the sidebar.")
        else:
            st.info("No audit logs found or gateway unreachable.")
