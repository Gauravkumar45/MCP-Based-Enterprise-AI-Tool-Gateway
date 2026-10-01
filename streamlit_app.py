"""Enterprise AI Platform & MCP Control Plane Dashboard."""

import os
from typing import Any

import httpx
import pandas as pd
import streamlit as st

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8080").rstrip("/")

st.set_page_config(
    page_title="Enterprise AI Gateway",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .kpi-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .kpi-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 1.25rem 1rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: rgba(56, 189, 248, 0.3);
    }
    .kpi-label {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 0.5rem;
    }
    .kpi-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #F8FAFC;
        line-height: 1.2;
    }
    .kpi-sub {
        font-size: 0.8rem;
        color: #64748B;
        margin-top: 0.35rem;
    }

    .badge {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        font-size: 0.72rem;
        font-weight: 600;
        border-radius: 6px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .badge-success { background: rgba(34, 197, 94, 0.15); color: #4ADE80; border: 1px solid rgba(34, 197, 94, 0.3); }
    .badge-danger { background: rgba(239, 68, 68, 0.15); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-info { background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.3); }
    .badge-warning { background: rgba(234, 179, 8, 0.15); color: #FACC15; border: 1px solid rgba(234, 179, 8, 0.3); }

    .tool-call-banner {
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-left: 4px solid #38BDF8;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0 1rem 0;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
    }

    .empty-state {
        text-align: center;
        padding: 2.5rem 1rem;
        background: rgba(15, 23, 42, 0.4);
        border: 1px dashed rgba(255, 255, 255, 0.12);
        border-radius: 10px;
        color: #94A3B8;
        margin: 1rem 0;
    }
</style>
""",
    unsafe_allow_html=True,
)


def api_request(
    method: str,
    path: str,
    token: str | None = None,
    json_data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    """Execute authenticated HTTP request against FastAPI Gateway."""
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


if "token" not in st.session_state:
    st.session_state.token = None
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def login_user(username: str, password: str = "Password123!") -> bool:
    """Authenticate and store bearer token in session state."""
    username = username.strip()
    if not username:
        st.error("Please enter a valid username.")
        return False
    status_code, data = api_request(
        "POST", "/auth/login", json_data={"username": username, "password": password}
    )
    if status_code == 200:
        st.session_state.token = data["access_token"]
        st.session_state.user_info = data
        return True
    st.error(f"Login failed: {data.get('detail', 'Invalid credentials')}")
    return False


if not st.session_state.token:
    login_user("analyst")


with st.sidebar:
    st.markdown("### Enterprise AI Gateway")
    st.caption("Operations & Control Plane")

    h_code, _ = api_request("GET", "/health")
    if h_code == 200:
        st.markdown(
            '<span class="badge badge-success">Gateway Online (Port 8080)</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="badge badge-danger">Gateway Unreachable</span>',
            unsafe_allow_html=True,
        )

    st.divider()

    st.markdown("**Active Persona**")
    roles = st.session_state.user_info.get("roles", []) if st.session_state.user_info else []

    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        if st.button(
            "Analyst",
            use_container_width=True,
            type="primary" if "analyst" in roles else "secondary",
        ):
            login_user("analyst")
            st.rerun()
    with col_r2:
        if st.button(
            "Admin",
            use_container_width=True,
            type="primary" if "admin" in roles else "secondary",
        ):
            login_user("admin")
            st.rerun()
    with col_r3:
        if st.button(
            "Viewer",
            use_container_width=True,
            type="primary" if "viewer" in roles else "secondary",
        ):
            login_user("viewer")
            st.rerun()

    if st.session_state.user_info:
        u = st.session_state.user_info
        st.caption(f"Authenticated as **`{u.get('username')}`**")

    with st.expander("Switch Account"):
        c_user = st.text_input("Username", value="analyst", key="c_user")
        c_pass = st.text_input("Password", value="Password123!", type="password", key="c_pass")
        if st.button("Authenticate", use_container_width=True):
            if login_user(c_user, c_pass):
                st.success(f"Authenticated as {c_user}!")
                st.rerun()

    st.divider()

    nav_options = ["Dashboard", "AI Assistant", "MCP Tools", "Analytics"]

    if "admin" in roles:
        nav_options.extend(["Tool Executions", "Audit Ledger"])
    elif "analyst" in roles:
        nav_options.append("Tool Executions")

    nav_options.extend(["My Usage", "Architecture & Settings"])

    selected_nav = st.radio(
        "Navigation",
        options=nav_options,
        label_visibility="collapsed",
    )


def render_kpi(label: str, value: Any, sub: str = "") -> str:
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """


# Dashboard
if selected_nav == "Dashboard":
    st.title("Platform Operations")
    st.caption("Real-time telemetry, tool invocation health, and token economics.")

    d_code, d_data = api_request("GET", "/analytics/dashboard", token=st.session_state.token)

    if d_code == 200:
        kpi_cols = st.columns(6)
        with kpi_cols[0]:
            st.markdown(
                render_kpi(
                    "Total Tool Calls", f"{d_data['total_tool_calls']:,}", "All-time invocations"
                ),
                unsafe_allow_html=True,
            )
        with kpi_cols[1]:
            st.markdown(
                render_kpi("Successful", f"{d_data['successful_tool_calls']:,}", "Zero errors"),
                unsafe_allow_html=True,
            )
        with kpi_cols[2]:
            st.markdown(
                render_kpi(
                    "Failed / Denied", f"{d_data['failed_tool_calls']:,}", "Blocked by policy / AST"
                ),
                unsafe_allow_html=True,
            )
        with kpi_cols[3]:
            st.markdown(
                render_kpi("Active MCP Tools", d_data["active_tools"], "Discovered & verified"),
                unsafe_allow_html=True,
            )
        with kpi_cols[4]:
            st.markdown(
                render_kpi(
                    "Avg Tool Latency", f"{d_data['avg_tool_latency_ms']} ms", "Gateway + Tool"
                ),
                unsafe_allow_html=True,
            )
        with kpi_cols[5]:
            st.markdown(
                render_kpi(
                    "Estimated LLM Cost",
                    f"${d_data['estimated_llm_cost']:.4f}",
                    f"{d_data['total_tokens_used']:,} tokens",
                ),
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        row1_c1, row1_c2 = st.columns(2)

        with row1_c1:
            st.subheader("Tool Invocations by Name")
            tool_counts = d_data.get("tool_usage_counts", {})
            if tool_counts:
                df_tools = pd.DataFrame(
                    list(tool_counts.items()), columns=["Tool Name", "Executions"]
                ).set_index("Tool Name")
                st.bar_chart(df_tools, color="#38BDF8")
            else:
                st.info(
                    "No tool executions recorded yet. Run a prompt in the AI Assistant to generate telemetry."
                )

        with row1_c2:
            st.subheader("Execution Latency by Tool (ms)")
            tool_lat = d_data.get("latency_by_tool", {})
            if tool_lat:
                df_lat = pd.DataFrame(
                    list(tool_lat.items()), columns=["Tool Name", "Avg Latency (ms)"]
                ).set_index("Tool Name")
                st.bar_chart(df_lat, color="#818CF8")
            else:
                st.info("Latency benchmarks will populate following tool execution.")

        row2_c1, row2_c2 = st.columns(2)

        with row2_c1:
            st.subheader("Execution Status Breakdown")
            status_map = d_data.get("status_breakdown", {})
            if status_map:
                df_status = pd.DataFrame(
                    list(status_map.items()), columns=["Status", "Count"]
                ).set_index("Status")
                st.bar_chart(df_status, color="#34D399")
            else:
                st.info("No status distribution data available.")

        with row2_c2:
            st.subheader("Daily Token Consumption Trend")
            token_trend = d_data.get("token_usage_trend", [])
            if token_trend:
                df_tokens = pd.DataFrame(token_trend)
                df_tokens_plot = df_tokens.set_index("date")[
                    ["input_tokens", "output_tokens", "total_tokens"]
                ]
                st.line_chart(df_tokens_plot)
            else:
                st.info("Token trend graphs will render as the Copilot answers queries.")
    else:
        st.error(f"Failed to load operational metrics: {d_data.get('message', 'Unreachable')}")


# AI Assistant
elif selected_nav == "AI Assistant":
    st.title("Enterprise AI Copilot")
    st.caption(
        "Capabilities are discovered dynamically via MCP with AST validation, RBAC, and audit logging."
    )

    st.caption("Quick Business Prompts:")
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    selected_prompt: str | None = None
    with col_p1:
        if st.button("Top 5 Customers by Revenue", use_container_width=True):
            selected_prompt = "What were the top 5 customers by revenue last month?"
    with col_p2:
        if st.button("Lookup Invoice CUST-1001", use_container_width=True):
            selected_prompt = "Find the latest invoice for customer CUST-1001."
    with col_p3:
        if st.button("Rate Limit Security Policy", use_container_width=True):
            selected_prompt = "What is our enterprise security policy regarding rate limits?"
    with col_p4:
        if st.button("Calculate Revenue KPI", use_container_width=True):
            selected_prompt = "Calculate the total revenue KPI for last month"

    def render_execution_trace(
        plan: str | None,
        tools: list[dict[str, Any]] | None,
        results: list[dict[str, Any]] | None,
        error: str | None = None,
        tokens_used: int | None = None,
        cost: float | None = None,
    ) -> None:
        with st.expander("Agent Execution Trace", expanded=False):
            st.markdown(
                """
            ```
            User Query ──► Agent Planning ──► MCP Tool Discovery ──► Tool Selection
                             ▲                                           │
                             │                                           ▼
            Final Response ◄─┴─ Tool Result ◄─── Tool Execution ◄─── Authorization
            ```
            """
            )
            col_t1, col_t2 = st.columns(2)
            has_tools = bool(tools and len(tools) > 0)
            with col_t1:
                st.markdown("**1. Agent Planning & Intent Analysis:**")
                st.info(plan or "Direct conversational response - no enterprise tool required.")
                st.markdown("**2. MCP Discovered & Selected Tool(s):**")
                if has_tools:
                    st.json(tools)
                else:
                    st.caption(
                        "No enterprise tools required. Query routed to conversational synthesis."
                    )
            with col_t2:
                st.markdown("**3. Backend Authorization & Execution Status:**")
                if has_tools:
                    if error:
                        st.error(f"Authorization / Execution Blocked:\n{error}")
                    else:
                        st.success(
                            "RBAC Verified: User holds required permission\n"
                            "SQL AST Verified: Strictly read-only\n"
                            "Rate Limit Quota: OK"
                        )
                else:
                    st.caption("Tool execution bypassed - direct conversational response.")
                st.markdown("**4. Raw Structured MCP Results:**")
                if has_tools:
                    st.json(results or [])
                else:
                    st.caption("No tool results - answer synthesized directly.")

            if tokens_used is not None:
                st.caption(
                    f"Tokens Consumed: `{tokens_used:,}` | Estimated Cost: `${cost or 0.0:.6f}`"
                )

    for item in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(item["query"])
        with st.chat_message("assistant"):
            if item.get("selected_tools"):
                for t in item["selected_tools"]:
                    st.markdown(
                        f"""
                        <div class="tool-call-banner">
                            <b>Tool Invoked</b>: <code>{t.get("name")}</code><br>
                            Authorization Verified &nbsp;|&nbsp; Schema Validated &nbsp;|&nbsp; Audited
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            render_execution_trace(
                item.get("plan"),
                item.get("selected_tools"),
                item.get("tool_results"),
                item.get("execution_error"),
                item.get("tokens_used"),
                item.get("estimated_cost"),
            )
            st.markdown(item["final_response"])

    user_input = st.chat_input("Ask a business question or request tool execution...")
    active_query = selected_prompt or user_input

    if active_query:
        with st.chat_message("user"):
            st.write(active_query)

        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            with status_placeholder.container():
                st.markdown(
                    '<span class="badge badge-info">Planning & discovering MCP tools...</span>',
                    unsafe_allow_html=True,
                )

            status_code, resp = api_request(
                "POST",
                "/agent/chat",
                token=st.session_state.token,
                json_data={"query": active_query},
            )
            status_placeholder.empty()

            if status_code == 200:
                if resp.get("selected_tools"):
                    for t in resp["selected_tools"]:
                        st.markdown(
                            f"""
                            <div class="tool-call-banner">
                                <b>Tool Invoked</b>: <code>{t.get("name")}</code><br>
                                Authorization Verified &nbsp;|&nbsp; AST Safety Checked &nbsp;|&nbsp; Executed in {resp.get("latency_ms", 0)}ms
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                render_execution_trace(
                    resp.get("plan"),
                    resp.get("selected_tools"),
                    resp.get("tool_results"),
                    resp.get("execution_error"),
                    resp.get("tokens_used"),
                    resp.get("estimated_cost"),
                )
                st.markdown(resp["final_response"])

                st.session_state.chat_history.append(
                    {
                        "query": active_query,
                        "plan": resp.get("plan"),
                        "selected_tools": resp.get("selected_tools"),
                        "tool_results": resp.get("tool_results"),
                        "execution_error": resp.get("execution_error"),
                        "final_response": resp.get("final_response"),
                        "tokens_used": resp.get("tokens_used"),
                        "estimated_cost": resp.get("estimated_cost"),
                    }
                )
            elif status_code == 429:
                err_detail = resp.get("detail", "Rate or token limit exceeded.")
                st.error(f"Quota Restricted: {err_detail}")
            else:
                err_msg = resp.get("message", resp.get("detail", "Error executing agent"))
                st.error(f"Execution Error: {err_msg}")


# MCP Tools
elif selected_nav == "MCP Tools":
    st.title("MCP Tool Catalog")
    st.caption("Inspect approved enterprise tools registered on the Model Context Protocol server.")

    t_code, t_stats = api_request("GET", "/analytics/tool-stats", token=st.session_state.token)

    if t_code == 200 and isinstance(t_stats, list):
        for tool in t_stats:
            with st.container(border=True):
                col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([3, 1, 1, 1, 1])
                with col_h1:
                    st.subheader(f"`{tool['name']}`")
                    st.write(tool["description"])
                with col_h2:
                    risk_color = (
                        "badge-danger"
                        if tool["risk_level"] == "high"
                        else "badge-warning"
                        if tool["risk_level"] == "medium"
                        else "badge-success"
                    )
                    st.markdown(
                        f'<span class="badge {risk_color}">{tool["risk_level"].upper()} RISK</span>',
                        unsafe_allow_html=True,
                    )
                    st.caption(f"Timeout: {tool['timeout_seconds']}s")
                with col_h3:
                    st.metric("Total Calls", f"{tool['execution_count']:,}")
                with col_h4:
                    st.metric("Success Rate", f"{tool['success_rate']:.1f}%")
                with col_h5:
                    st.metric("Avg Latency", f"{tool['avg_latency_ms']} ms")

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    st.caption(f"Required RBAC Permission: **`{tool['required_permission']}`**")
                with col_b2:
                    with st.expander("Inspect JSON Input Schema"):
                        st.json(tool.get("input_schema", {}))
    else:
        st.error("Failed to load MCP tool statistics.")


# Analytics
elif selected_nav == "Analytics":
    st.title("System Observability")
    st.caption(
        "Detailed breakdown of LLM token costs, latency trends, and enterprise tool execution."
    )

    d_code, d_data = api_request("GET", "/analytics/dashboard", token=st.session_state.token)

    if d_code == 200:
        tab_ai, tab_system = st.tabs(["Model & Token Analytics", "Tool Latency & Reliability"])

        with tab_ai:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Total Platform Tokens", f"{d_data['total_tokens_used']:,}")
            with c2:
                st.metric("Total Estimated LLM Spend", f"${d_data['estimated_llm_cost']:.4f}")
            with c3:
                st.metric("Total Tool Invocations", f"{d_data['total_tool_calls']:,}")

            st.subheader("Daily Token Ingestion & Output Trend")
            token_trend = d_data.get("token_usage_trend", [])
            if token_trend:
                df_t = pd.DataFrame(token_trend).set_index("date")
                st.area_chart(df_t[["input_tokens", "output_tokens"]])
            else:
                st.info("Token ingestion charts will render as queries are processed.")

        with tab_system:
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.subheader("Tool Execution Volume")
                t_counts = d_data.get("tool_usage_counts", {})
                if t_counts:
                    st.bar_chart(
                        pd.DataFrame(list(t_counts.items()), columns=["Tool", "Count"]).set_index(
                            "Tool"
                        )
                    )
                else:
                    st.info("No tool calls recorded.")
            with col_s2:
                st.subheader("Average Latency Benchmarks")
                t_lat = d_data.get("latency_by_tool", {})
                if t_lat:
                    st.bar_chart(
                        pd.DataFrame(
                            list(t_lat.items()), columns=["Tool", "Latency (ms)"]
                        ).set_index("Tool")
                    )
                else:
                    st.info("No latency benchmarks recorded.")
    else:
        st.error("Failed to load analytics data.")


# Tool Executions
elif selected_nav == "Tool Executions":
    st.title("Tool Execution Ledger")
    st.caption("Inspect every tool execution dispatched through the MCP Gateway.")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        f_tool = st.text_input("Filter by Tool Name", value="")
    with col_f2:
        f_status = st.selectbox("Filter by Status", options=["ALL", "SUCCESS", "FAILED", "DENIED"])
    with col_f3:
        f_limit = st.slider("Max Results", min_value=10, max_value=100, value=25)

    params: dict[str, Any] = {"limit": f_limit}
    if f_tool.strip():
        params["tool_name"] = f_tool.strip()
    if f_status != "ALL":
        params["status"] = f_status

    ex_code, ex_rows = api_request(
        "GET",
        "/analytics/executions",
        token=st.session_state.token,
        params=params,
    )

    if ex_code == 200 and isinstance(ex_rows, list):
        if ex_rows:
            df_ex = pd.DataFrame(ex_rows)
            st.dataframe(
                df_ex[
                    [
                        "timestamp",
                        "tool_name",
                        "execution_status",
                        "latency_ms",
                        "user_id",
                        "request_id",
                    ]
                ],
                use_container_width=True,
                column_config={
                    "latency_ms": st.column_config.NumberColumn("Latency (ms)", format="%.2f ms"),
                    "timestamp": st.column_config.DatetimeColumn(
                        "Timestamp", format="YYYY-MM-DD HH:mm:ss"
                    ),
                },
            )
        else:
            st.info("No execution records match the specified filters.")
    else:
        st.error("Failed to load tool executions.")


# Audit Ledger
elif selected_nav == "Audit Ledger":
    st.title("Security Audit Ledger")
    st.caption(
        "Cryptographically hashed parameter audit logs for governance, zero-trust tracking, and forensics."
    )

    a_code, a_logs = api_request("GET", "/audit?limit=50", token=st.session_state.token)
    if a_code == 200 and isinstance(a_logs, list):
        if a_logs:
            df_audit = pd.DataFrame(a_logs)
            st.dataframe(
                df_audit[
                    [
                        "timestamp",
                        "request_id",
                        "user_id",
                        "tool_name",
                        "execution_status",
                        "latency_ms",
                        "input_hash",
                    ]
                ],
                use_container_width=True,
                column_config={
                    "input_hash": st.column_config.TextColumn("SHA-256 Parameter Hash"),
                    "latency_ms": st.column_config.NumberColumn("Latency", format="%.2f ms"),
                },
            )
        else:
            st.info("Audit ledger is empty.")
    elif a_code == 403:
        st.warning(
            "Access Restricted: The audit ledger is only accessible to users with the admin role."
        )
    else:
        st.error("Failed to load audit records.")


# My Usage
elif selected_nav == "My Usage":
    st.title("My Usage & Token Quota")
    st.caption("Track personal daily token limits, request volume, and estimated LLM costs.")

    u_code, u_data = api_request("GET", "/analytics/user-usage", token=st.session_state.token)

    if u_code == 200:
        col_q1, col_q2, col_q3, col_q4 = st.columns(4)
        with col_q1:
            st.markdown(
                render_kpi(
                    "Today's Tokens",
                    f"{u_data['today_tokens']:,}",
                    f"Limit: {u_data['daily_limit']:,}",
                ),
                unsafe_allow_html=True,
            )
        with col_q2:
            st.markdown(
                render_kpi(
                    "Tokens Remaining",
                    f"{u_data['tokens_remaining']:,}",
                    f"{u_data['percent_used']}% consumed",
                ),
                unsafe_allow_html=True,
            )
        with col_q3:
            st.markdown(
                render_kpi(
                    "Total Requests",
                    f"{u_data['total_requests']:,}",
                    f"Avg {u_data['avg_tokens_per_request']} tok/req",
                ),
                unsafe_allow_html=True,
            )
        with col_q4:
            st.markdown(
                render_kpi(
                    "Estimated Spend",
                    f"${u_data['estimated_cost']:.4f}",
                    f"Month: {u_data['month_tokens']:,} tokens",
                ),
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader("Daily Token Quota Status")
        progress_val = min(1.0, max(0.0, u_data["percent_used"] / 100.0))
        st.progress(progress_val)

        if u_data.get("is_exceeded"):
            st.error(
                f"Daily Quota Exceeded: You have consumed {u_data['today_tokens']:,} of your "
                f"{u_data['daily_limit']:,} daily token allowance. Additional requests are restricted."
            )
        elif u_data.get("is_warning"):
            st.warning(
                f"Approaching Quota: You have used {u_data['percent_used']}% of your daily token limit."
            )
        else:
            st.success(f"Quota healthy: {u_data['tokens_remaining']:,} tokens available for today.")

        st.divider()

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.subheader("Token Usage by Model")
            models_data = u_data.get("usage_by_model", {})
            if models_data:
                st.bar_chart(
                    pd.DataFrame(list(models_data.items()), columns=["Model", "Tokens"]).set_index(
                        "Model"
                    )
                )
            else:
                st.info("No model-specific token usage recorded yet.")

        with col_m2:
            st.subheader("Recent Daily Consumption")
            history = u_data.get("daily_history", [])
            if history:
                df_h = pd.DataFrame(history).set_index("date")
                st.line_chart(df_h["tokens"])
            else:
                st.info("Daily history will appear following AI usage.")

    else:
        st.error("Failed to load user token quota.")


# Architecture & Settings
elif selected_nav == "Architecture & Settings":
    st.title("System Architecture & Settings")
    st.caption("Runtime parameters, security guardrails, and model pricing tables.")

    tab_arch, tab_pricing, tab_claims = st.tabs(
        ["Architecture & Flow", "Model Pricing", "Session Claims"]
    )

    with tab_arch:
        st.markdown(
            """
        ```
                            ┌────────────────────────┐
                            │    Streamlit Control   │
                            │   Plane (Port 8501)    │
                            └───────────┬────────────┘
                                        │
                                        ▼
                            ┌────────────────────────┐
                            │    FastAPI Gateway     │
                            │    JWT Auth / RBAC     │
                            │     (Port 8080)        │
                            └───────────┬────────────┘
                                        │
                                        ▼
                            ┌────────────────────────┐
                            │    LangGraph Agent     │
                            │  Planner / Synthesizer │
                            └───────────┬────────────┘
                                        │
                                 MCP Protocol (SSE)
                                        │
                                        ▼
                      ┌──────────────────────────────────┐
                      │         MCP Tool Gateway         │
                      │  • Discovery      • RBAC         │
                      │  • AST SQL Guard  • Rate Limiter │
                      │  • Token Tracker  • Audit Ledger │
                      └─────────────────┬────────────────┘
                                        │
                    ┌───────────────────┼────────────────────┐
                    ▼                   ▼                    ▼
             PostgreSQL 16        Document Search      Internal APIs
             (Customer / Inv)     (Enterprise Wiki)    (KPIs & Health)
        ```
        """
        )

    with tab_pricing:
        st.subheader("Configured Model Pricing (Per 1 Million Tokens)")
        pricing_rows = [
            {"Model": "gpt-4o-mini", "Input / 1M": "$0.15", "Output / 1M": "$0.60"},
            {"Model": "gpt-4o", "Input / 1M": "$2.50", "Output / 1M": "$10.00"},
            {"Model": "gpt-3.5-turbo", "Input / 1M": "$0.50", "Output / 1M": "$1.50"},
            {"Model": "mock-enterprise-llm", "Input / 1M": "$0.05", "Output / 1M": "$0.15"},
        ]
        st.table(pd.DataFrame(pricing_rows))

    with tab_claims:
        if st.session_state.user_info:
            st.json(st.session_state.user_info)
        else:
            st.info("No active session.")
