"""Modular LLM provider abstraction supporting OpenAI, custom providers, and deterministic offline engine."""

import json
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.core.config import get_settings
from app.core.logging import logger


class EnterpriseMockLLM(BaseChatModel):
    """Deterministic, production-ready fallback LLM for offline development, CI/CD, and testing.

    Analyzes user intent and discovered tool schemas to generate structured tool calls and synthesis.
    """

    model_name: str = "mock-enterprise-llm"

    @property
    def _llm_type(self) -> str:
        return "enterprise_mock_llm"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        last_message = messages[-1].content if messages else ""
        last_str = str(last_message)
        text_content = last_str.lower()

        # Extract actual user query from prompt if wrapped in agent prompt
        raw_query = text_content
        match_uq = re.search(r"User Query:\s*(.+?)(?:\n|$)", last_str, re.IGNORECASE)
        if match_uq:
            raw_query = match_uq.group(1).strip().lower()

        # Check if this generation is for synthesis with tool results
        if "TOOL_RESULTS:" in last_str or "tool_results" in text_content:
            try:
                # Extract and format table
                return ChatResult(
                    generations=[
                        ChatGeneration(
                            message=AIMessage(
                                content=(
                                    "### Executive Analytics Report\n\n"
                                    "Based on verified data retrieved through the Enterprise MCP Gateway:\n\n"
                                    f"```json\n{last_str[:1200]}\n```\n\n"
                                    "**Compliance Status**: All queries executed under read-only transaction mode and logged to immutable audit ledger."
                                )
                            )
                        )
                    ]
                )
            except Exception:
                pass

        # Check if this generation is for conversational synthesis (no tools called)
        if "Enterprise AI Analytics Copilot" in last_str and "TOOL_RESULTS:" not in last_str:
            is_actual_greeting = any(
                re.search(rf"\b{g}\b", raw_query)
                for g in [
                    "hello",
                    "hi",
                    "hey",
                    "greetings",
                    "good morning",
                    "good afternoon",
                    "good evening",
                    "who are you",
                    "what can you do",
                    "help",
                    "menu",
                ]
            )
            if is_actual_greeting:
                greeting_text = (
                    "👋 **Hello! Welcome to the Enterprise AI Tool Gateway.**\n\n"
                    "I am your **Enterprise AI Analytics Copilot**, securely connected to backend systems via the Model Context Protocol (MCP).\n\n"
                    "Here are the approved enterprise capabilities available to you:\n\n"
                    "- 📊 **Database Analytics (`query_database`)**: Query PostgreSQL customer, revenue, and transaction tables with automatic AST read-only validation.\n"
                    "- 👥 **Customer Details (`get_customer`)**: Retrieve customer profile, tier, and lifetime value.\n"
                    "- 🧾 **Invoices & Orders (`get_invoice`, `get_order`)**: Inspect billing statuses, line items, and fulfillment tracking.\n"
                    "- 📜 **Policy & Knowledge Search (`search_documents`)**: Semantic search across internal compliance, SLA, and security policies.\n"
                    "- 📈 **KPI Calculation (`calculate_kpi`)**: Compute MRR, churn rate, average order value (AOV), and customer growth.\n"
                    "- ⚙️ **System Telemetry (`get_system_status`)**: Check PostgreSQL, Redis, and Gateway operational health.\n\n"
                    "**Zero-Trust Security**: All queries are evaluated against your user role permissions, protected by AST SQL safety parsing, and logged to an immutable audit ledger.\n\n"
                    "💡 *Try asking:*\n"
                    "- *'What were the top 5 customers by revenue last month?'*\n"
                    "- *'Find the latest invoice for customer CUST-1001.'*\n"
                    "- *'What is our enterprise security policy regarding rate limits?'*"
                )
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(content=greeting_text))]
                )

            user_question_display = match_uq.group(1).strip() if match_uq else raw_query
            fallback_text = (
                f'I reviewed your question: **"{user_question_display}"**.\n\n'
                "I was unable to match this request to an approved enterprise tool or database query. "
                "As your Enterprise AI Analytics Copilot, I can help you with:\n\n"
                "- 📊 **Database Analytics**: e.g., *'Show top 5 customers by revenue'*, *'Query customers table'*\n"
                "- 🧾 **Invoices & Orders**: e.g., *'Find latest invoice for CUST-1001'*, *'Check order ORD-9001'*\n"
                "- 📜 **Policies & Security**: e.g., *'What is our enterprise security policy regarding rate limits?'*\n"
                "- 📈 **KPI Metrics**: e.g., *'Calculate total revenue KPI'* or *'What is our churn rate?'*\n"
                "- ⚙️ **System Status**: e.g., *'Check system status'*\n\n"
                "Please try rephrasing your question using one of the enterprise domains above!"
            )
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=fallback_text))]
            )

        # 3. Check if query is a greeting or general capability question in planner
        is_greeting = any(
            re.search(rf"\b{g}\b", raw_query)
            for g in [
                "hello",
                "hi",
                "hey",
                "greetings",
                "good morning",
                "good afternoon",
                "good evening",
                "who are you",
                "what can you do",
                "help",
                "menu",
            ]
        )
        if is_greeting:
            plan = "User greeted or requested general capabilities. Provide a welcoming introduction to the Enterprise AI Copilot and summarize available tools without invoking backend tools."
            greeting_payload: dict[str, Any] = {
                "plan": plan,
                "tool_calls": [],
            }
            return ChatResult(
                generations=[
                    ChatGeneration(message=AIMessage(content=json.dumps(greeting_payload)))
                ]
            )

        # 4. Robust Intent Parsing & Tool Selection
        selected_tool: str | None = None
        tool_args: dict[str, Any] = {}

        # Raw SQL query detection
        sql_match = re.search(r"\b(select\s+.+?\s+from\s+.+?)(?:;|$)", raw_query, re.IGNORECASE)
        if sql_match:
            selected_tool = "query_database"
            raw_sql = sql_match.group(1).strip()
            if "limit" not in raw_sql.lower():
                raw_sql += " LIMIT 10"
            tool_args = {"query": raw_sql}

        # Customer & Revenue database queries
        elif any(
            k in raw_query
            for k in [
                "top 5 customer",
                "top customer",
                "top 10 customer",
                "top 5 customers",
                "top customers",
                "highest revenue",
                "customer revenue",
                "customers by revenue",
                "best customer",
                "most valuable",
                "lifetime value",
                "ltv",
            ]
        ):
            selected_tool = "query_database"
            tool_args = {
                "query": "SELECT name, lifetime_value FROM customers ORDER BY lifetime_value DESC LIMIT 5"
            }

        elif any(
            k in raw_query
            for k in [
                "customers",
                "customer list",
                "all customers",
                "show customers",
                "list customers",
                "customer database",
                "database tables",
                "database",
            ]
        ):
            match_cid = re.search(r"cust-\d+", raw_query, re.IGNORECASE)
            if match_cid:
                selected_tool = "get_customer"
                tool_args = {"customer_id": match_cid.group(0).upper()}
            else:
                selected_tool = "query_database"
                tool_args = {
                    "query": "SELECT id, name, email, tier, lifetime_value FROM customers ORDER BY lifetime_value DESC LIMIT 10"
                }

        elif any(k in raw_query for k in ["customer", "client", "account"]) and any(
            k in raw_query
            for k in ["detail", "get", "find", "lookup", "who is", "profile", "cust-"]
        ):
            match_cid = re.search(r"cust-\d+", raw_query, re.IGNORECASE)
            cid = match_cid.group(0).upper() if match_cid else "CUST-1001"
            selected_tool = "get_customer"
            tool_args = {"customer_id": cid}

        # Invoice inquiries -> get_invoice
        elif any(k in raw_query for k in ["invoice", "invoices", "bill", "billing", "inv-"]):
            match_inv = re.search(r"inv-\d{4}-\d+", raw_query, re.IGNORECASE)
            inv_id = match_inv.group(0).upper() if match_inv else "INV-2024-001"
            selected_tool = "get_invoice"
            tool_args = {"invoice_id": inv_id}

        # Order inquiries -> get_order
        elif any(
            k in raw_query
            for k in ["order", "orders", "ord-", "tracking", "shipment", "fulfillment"]
        ):
            match_ord = re.search(r"ord-\d+", raw_query, re.IGNORECASE)
            oid = match_ord.group(0).upper() if match_ord else "ORD-9001"
            selected_tool = "get_order"
            tool_args = {"order_id": oid}

        # KPI inquiries -> calculate_kpi
        elif any(
            k in raw_query
            for k in [
                "kpi",
                "mrr",
                "revenue metric",
                "average order",
                "aov",
                "churn",
                "active customer",
                "metric",
                "metrics",
                "calculate revenue",
            ]
        ):
            metric = "revenue"
            if "aov" in raw_query or "average order" in raw_query:
                metric = "aov"
            elif "churn" in raw_query:
                metric = "churn_rate"
            elif "active" in raw_query:
                metric = "active_customers"
            selected_tool = "calculate_kpi"
            tool_args = {"metric_name": metric, "period": "last_month"}

        # Document & Policy search -> search_documents
        elif any(
            k in raw_query
            for k in [
                "policy",
                "policies",
                "document",
                "documents",
                "sla",
                "runbook",
                "search",
                "security",
                "rate limit",
                "rate limits",
                "reimbursement",
                "expense",
                "terms",
                "rules",
                "compliance",
                "wiki",
            ]
        ):
            selected_tool = "search_documents"
            tool_args = {"query": str(raw_query), "top_k": 3}

        # System health & status -> get_system_status
        elif any(
            k in raw_query
            for k in [
                "system",
                "status",
                "health",
                "uptime",
                "telemetry",
                "diagnostics",
                "ping",
                "gateway",
            ]
        ):
            selected_tool = "get_system_status"
            tool_args = {}

        if selected_tool:
            plan = f"Plan: Identify intent and call tool '{selected_tool}' with parameters: {json.dumps(tool_args)}"
            tool_payload: dict[str, Any] = {
                "plan": plan,
                "tool_calls": [{"name": selected_tool, "arguments": tool_args}],
            }
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=json.dumps(tool_payload)))]
            )

        # Fallback direct response formatted as valid JSON plan
        fallback_plan = "Direct conversational response — no enterprise tool required or matched for this request."
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(content=json.dumps({"plan": fallback_plan, "tool_calls": []}))
                )
            ]
        )


def get_llm() -> BaseChatModel:
    """Instantiate configured LLM provider (OpenAI or deterministic mock fallback)."""
    settings = get_settings()

    if (
        settings.OPENAI_API_KEY
        and settings.OPENAI_API_KEY.strip()
        and not settings.OPENAI_API_KEY.startswith("test")
    ):
        try:
            from langchain_openai import ChatOpenAI

            logger.info("Initializing Live OpenAI LLM with model: %s", settings.OPENAI_MODEL)
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,  # type: ignore[arg-type]
                base_url=settings.OPENAI_BASE_URL,
                temperature=0.0,
            )
        except Exception as e:
            logger.warning("Failed to initialize ChatOpenAI: %s. Using EnterpriseMockLLM.", e)

    logger.info("Using EnterpriseMockLLM for reliable deterministic execution.")
    return EnterpriseMockLLM()
