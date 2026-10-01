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
        text_content = str(last_message).lower()

        # Check if this generation is for synthesis
        last_str = str(last_message)
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
            if any(
                g in text_content
                for g in [
                    "hello",
                    "hi",
                    "hey",
                    "greeting",
                    "good morning",
                    "good afternoon",
                    "help",
                    "who are you",
                    "what can you do",
                ]
            ):
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
            fallback_text = (
                "I am your Enterprise AI Analytics Copilot. I reviewed your query, but no enterprise tool is required or matched for this request.\n\n"
                "I specialize in enterprise data operations: database analytics, customer lookup, invoice management, internal policy search, and KPI calculations.\n\n"
                "Please let me know how I can assist with enterprise data or analytics!"
            )
            return ChatResult(
                generations=[ChatGeneration(message=AIMessage(content=fallback_text))]
            )

        # Check if query is a greeting or general capability question
        is_greeting = any(
            re.search(rf"\b{g}\b", text_content)
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

        # Plan & Tool selection heuristics for realistic queries
        selected_tool: str | None = None
        tool_args: dict[str, Any] = {}

        if any(
            term in text_content
            for term in [
                "top 5 customers",
                "top customers",
                "highest revenue",
                "customer revenue",
                "customers by revenue",
                "database tables",
            ]
        ):
            selected_tool = "query_database"
            tool_args = {
                "query": "SELECT name, lifetime_value FROM customers ORDER BY lifetime_value DESC LIMIT 5"
            }
        elif "customer" in text_content and ("cust-" in text_content or "get" in text_content):
            match = re.search(r"cust-\d+", text_content, re.IGNORECASE)
            cid = match.group(0).upper() if match else "CUST-1001"
            selected_tool = "get_customer"
            tool_args = {"customer_id": cid}
        elif "invoice" in text_content:
            match = re.search(r"inv-\d{4}-\d+", text_content, re.IGNORECASE)
            inv_id = match.group(0).upper() if match else "INV-2024-001"
            selected_tool = "get_invoice"
            tool_args = {"invoice_id": inv_id}
        elif "order" in text_content and ("ord-" in text_content or "tracking" in text_content):
            match = re.search(r"ord-\d+", text_content, re.IGNORECASE)
            oid = match.group(0).upper() if match else "ORD-9001"
            selected_tool = "get_order"
            tool_args = {"order_id": oid}
        elif any(
            k in text_content for k in ["kpi", "mrr", "revenue metric", "average order value"]
        ):
            metric = "revenue"
            if "aov" in text_content or "average order" in text_content:
                metric = "aov"
            elif "churn" in text_content:
                metric = "churn_rate"
            elif "active customers" in text_content:
                metric = "active_customers"
            selected_tool = "calculate_kpi"
            tool_args = {"metric_name": metric, "period": "last_month"}
        elif any(
            k in text_content
            for k in ["policy", "document", "sla", "runbook", "search", "security"]
        ):
            selected_tool = "search_documents"
            tool_args = {"query": str(last_message), "top_k": 3}
        elif "system status" in text_content or "health" in text_content:
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
