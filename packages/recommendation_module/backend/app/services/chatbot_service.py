import re

from .groq_service import generate_llm_response
from .rag_service import retrieve_relevant_chunks, format_retrieved_knowledge
from .application_context_service import get_application_context
from .anomaly_query_service import (
    get_latest_anomaly_for_app,
    get_anomalies_by_time_window,
    get_anomaly_counts_for_app,
)
from .test_comparison_service import (
    extract_cycle_numbers,
    extract_requested_metrics,
    get_test_cycle_comparison,
)
# Chat history and session storage removed for stateless chatbot


# ---------------------------------------------------------------------------
# Deterministic post-processing (runs locally — no extra API calls, no cost)
# ---------------------------------------------------------------------------

_UNKNOWN_LINE_PATTERN = re.compile(
    r"(?im)^.*\b("
    r"unknown|not identified|not specified|not provided|not detected|"
    r"not available|no information|no schema|no explicit|not found|"
    r"unspecified|undetermined|not documented|no data (was |is )?(found|available)"
    r")\b.*$\n?"
)


def _clean_llm_answer(text: str) -> str:
    """Deterministic, free (no API cost) safety net: strip unknown/unspecified
    lines the model may still produce despite prompt rules. Tables and other
    markdown structure are left intact — the frontend renders them properly."""
    if not text:
        return text
    original = text
    cleaned = _UNKNOWN_LINE_PATTERN.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()

    # Safety net: if cleaning stripped everything, don't return an empty
    # answer — fall back to the original text rather than showing nothing.
    if not cleaned:
        return original.strip()

    return cleaned


def _trim_to_complete_sentence(text: str) -> str:
    """If the model's output was cut off by max_tokens, trim back to the
    last fully-formed sentence/bullet so nothing reads as broken mid-word."""
    if not text:
        return text
    text = text.rstrip()
    if text.endswith((".", "!", "?", ":", ")", "`")):
        return text
    last_break = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
    if last_break != -1 and last_break > len(text) * 0.5:
        return text[: last_break + 1].strip()
    return text.strip()


def detect_question_type(question):
    q = question.lower().strip()

    anomaly_keywords = [
        "anomal",          # stem — catches anomaly / anomalies / anomalous
        "diagnostic",
        "issue",
        "problem",
        "abnormal",
        "root cause",
        "what happened",
        "went wrong",
        "detected",
        "why is there",
        "why did",
    ]

    test_keywords = [
        "compare test",
        "test comparison",
        "compare cycle",
        "test cycle",
        "compare results",
        "compare runs",
        "compare tests",
    ]

    if any(keyword in q for keyword in anomaly_keywords):
        return "anomaly"

    if any(keyword in q for keyword in test_keywords):
        return "test_comparison"

    return "application"


COUNT_KEYWORDS = [
    "how many", "how much", "total anomal", "count of anomal",
    "number of anomal", "until now", "so far", "to date", "to-date",
]


def is_count_question(question: str) -> bool:
    q = question.lower().strip()
    return any(k in q for k in COUNT_KEYWORDS)


def build_chatbot_context(app_id):
    return get_application_context(app_id)


def _is_known(value) -> bool:
    """Treat None, empty string, and case-insensitive 'unknown' as unset."""
    if value is None:
        return False
    text = str(value).strip().lower()
    return text != "" and text != "unknown"


def build_application_system_prompt():
    return (
        "You are Chamora, an AI assistant that provides customized recommendations "
        "for the user's selected application. "
        "Answer ONLY questions that are directly related to the provided application data, documents, or context. "
        "If the user asks a general knowledge question unrelated to this application "
        "(such as 'What is AI?', 'What is ML?', or any topic not in the application context), "
        "respond ONLY with: 'Chamora aims to provide customized answers for application related questions'. "
        "Be practical, clear, and specific. "
        "STRICT RULES: "
        "1) Only mention facts explicitly given to you below — never guess, infer, or speculate about anything not stated. "
        "2) Never use the words 'unknown', 'not specified', 'not provided', or similar — if something wasn't given to you, do not bring it up at all. "
        "3) Structure your answer with markdown: use a short heading, 4-6 detailed bullet points or a comparison table where relevant, and enough explanation that each point is genuinely useful — not just a one-line label. "
        "4) Do not artificially shorten your answer. Use the space you need to be genuinely helpful, while staying strictly grounded in the facts given."
    )


def build_application_user_prompt(context, question, retrieved_knowledge):
    containers = context["containers"]
    primary_container = containers[0]["name"] if containers else None
    primary_image = containers[0]["image"] if containers else None

    tech_stack = context["tech_stack"]
    evidence_list = tech_stack.get("evidence", [])
    evidence = ", ".join(evidence_list) if evidence_list else None

    safe_retrieved_knowledge = retrieved_knowledge[:1800]

    app_lines = [f"- Name: {context['app_name']}", f"- ID: {context['app_id']}"]
    if _is_known(context.get("domain")):
        app_lines.append(f"- Domain: {context['domain']}")
    if _is_known(context.get("environment")):
        app_lines.append(f"- Environment: {context['environment']}")
    app_lines.append(f"- User: {context['user_name']} ({context['user_id']})")
    if _is_known(context.get("repo_url")):
        app_lines.append(f"- Repo URL: {context['repo_url']}")

    tech_lines = []
    if _is_known(tech_stack.get("frontend")):
        tech_lines.append(f"- Frontend: {tech_stack['frontend']}")
    if _is_known(tech_stack.get("backend")):
        tech_lines.append(f"- Backend: {tech_stack['backend']}")
    if _is_known(tech_stack.get("database")):
        tech_lines.append(f"- Database: {tech_stack['database']}")
    if _is_known(evidence):
        tech_lines.append(f"- Evidence: {evidence}")
    tech_block = "\n".join(tech_lines) if tech_lines else None

    container_lines = []
    if _is_known(primary_container):
        container_lines.append(f"- Primary Container: {primary_container}")
    if _is_known(primary_image):
        container_lines.append(f"- Image: {primary_image}")
    container_block = "\n".join(container_lines) if container_lines else None

    sections = [f"Application Context\n" + "\n".join(app_lines)]
    if tech_block:
        sections.append(f"Technology Stack\n{tech_block}")
    sections.append(
        "Runtime Metrics\n"
        f"- CPU Usage: {context['metrics']['cpu_percent']}%\n"
        f"- Memory Usage: {context['metrics']['memory_percent']}%\n"
        f"- Memory Used: {context['metrics']['memory_used']}\n"
        f"- Memory Total: {context['metrics']['memory_total']}"
    )
    if container_block:
        sections.append(f"Container\n{container_block}")
    sections.append(f"Current Mode\n- {context['mode']}")
    if safe_retrieved_knowledge and safe_retrieved_knowledge.strip():
        sections.append(f"Retrieved Knowledge Base Content\n{safe_retrieved_knowledge}")
    sections.append(f"User Question\n{question}")
    sections.append(
        "Instructions\n"
        "- Only state facts explicitly listed above. Do not guess, infer, or mention anything not given.\n"
        "- Do not say a field is unknown, unspecified, or not provided — if it's missing above, skip it entirely, silently.\n"
        "- Use markdown formatting freely — headings, tables, and bullets are all welcome where they help clarity.\n"
        "- Be complete and helpful, but avoid unnecessary repetition or filler.\n"
        "FINAL REMINDER: Do not speculate about what the application does, its typical use cases, "
        "or its likely architecture. Only repeat facts given above. If unsure whether to include "
        "something, leave it out."
    )

    return "\n\n".join(sections).strip()


def build_anomaly_system_prompt():
    return (
        "You are Chamora in diagnostic mode. "
        "Explain anomalies using the provided application context and anomaly records. "
        "Focus on what happened, likely cause, impact, and actionable next steps. "
        "STRICT RULES: "
        "1) Only mention facts explicitly given to you below — never guess or speculate. "
        "2) Never use the words 'unknown', 'not specified', 'not provided', or similar — if missing, skip it silently. "
        "3) Structure your answer with markdown: use a short heading, 4-6 detailed bullet points or a comparison table where relevant, and enough explanation that each point is genuinely useful — not just a one-line label. "
        "4) Do not artificially shorten your answer. Use the space you need to be genuinely helpful, while staying strictly grounded in the facts given."
    )


def build_anomaly_user_prompt(
    context: dict,
    anomaly_records: list[dict],
    question: str,
    counts: dict,
) -> str:
    """counts must come from get_anomaly_counts_for_app — a real DB aggregate,
    never from len(anomaly_records), which may be paginated/capped."""
    trimmed_records = anomaly_records[:3]
    total = counts.get("total", 0)
    severity_summary = ", ".join(
        f"{v} {k}" for k, v in counts.items() if k != "total"
    ) or "n/a"

    if not trimmed_records:
        anomaly_text = "No anomaly records were found for the requested time window."
    else:
        parts = []
        for idx, record in enumerate(trimmed_records, start=1):
            evidence = record.get("evidence", {})
            if isinstance(evidence, dict):
                evidence_items = list(evidence.items())[:5]
                evidence_text = ", ".join([f"{k}={v}" for k, v in evidence_items])
            else:
                evidence_text = str(evidence)[:300]

            parts.append(
                f"""Record {idx}
- Time: {record.get("window_timestamp")}
- Severity: {record.get("severity")}
- Score: {record.get("score")}
- Root Cause: {record.get("root_cause")}
- Evidence: {evidence_text}"""
            )
        anomaly_text = "\n\n".join(parts)

    app_lines = [f"- Name: {context['app_name']}", f"- ID: {context['app_id']}"]
    if _is_known(context.get("domain")):
        app_lines.append(f"- Domain: {context['domain']}")
    if _is_known(context.get("environment")):
        app_lines.append(f"- Environment: {context['environment']}")
    app_lines.append("- Current Mode: diagnostic")

    return f"""
Application Context
{chr(10).join(app_lines)}

Anomaly Records
- Total anomalies recorded for this application (all time): {total} ({severity_summary})
- Showing the {len(trimmed_records)} most relevant record(s) below as examples.

{anomaly_text}

User Question
{question}

Instructions
- The "Total anomalies recorded" figure above is authoritative for any count/total question — never infer a count from how many records are listed in detail.
- Explain what happened clearly, using the detailed records as illustrative examples only.
<<<<<<< HEAD
- Only state facts explicitly given above — do not guess or speculate.
- Do not say a field is unknown, unspecified, or not provided — if missing, skip it silently.
- Use markdown formatting freely — headings, tables, and bullets are all welcome where they help clarity.
=======
- Mention the requested time window if relevant.
- Interpret severity, score, root cause, and evidence.
>>>>>>> 8af87fd (Update application management endpoints and clean up unused recommendation module)
- Give actionable recommendations.
- Be complete and helpful, but avoid unnecessary repetition or filler.
""".strip()


def build_test_comparison_system_prompt():
    return (
        "You are Chamora, an AI assistant for application-specific test analysis. "
        "Use the supplied comparison data to explain the differences clearly and practically. "
        "STRICT RULES: "
        "1) Only mention facts explicitly given to you below — never guess or speculate. "
        "2) Never use the words 'unknown', 'not specified', 'not provided', or similar — if missing, skip it silently. "
        "3) Use clean markdown formatting — a comparison table is often the clearest way to present metric differences. "
        "4) Be thorough but efficient — give a complete, well-organized answer, not padding."
    )


def build_test_comparison_user_prompt(context, comparison_data, metrics, question):
    selected_metrics = []
    metrics_map = comparison_data.get("metrics", {})

    for metric in metrics:
        if metric in metrics_map:
            data = metrics_map[metric]
            selected_metrics.append(
                f"- {metric}: baseline={data['baseline']}, target={data['target']}, "
                f"difference={data['difference']}, difference_percent={data['difference_percent']}%"
            )

    selected_text = "\n".join(selected_metrics) or "- No requested metrics found in comparison data"

    app_lines = [f"- Name: {context['app_name']}", f"- ID: {context['app_id']}"]
    if _is_known(context.get("domain")):
        app_lines.append(f"- Domain: {context['domain']}")
    if _is_known(context.get("environment")):
        app_lines.append(f"- Environment: {context['environment']}")

    return f"""
Application Context
{chr(10).join(app_lines)}

Comparison Summary
- {comparison_data.get("summary", "No summary available")}
- Regression Detected: {comparison_data.get("regression_detected", False)}

Requested Metric Comparison
{selected_text}

User Question
{question}

Instructions
- Explain the comparison clearly. A markdown table (metric | baseline | target | % change) is a good way to present this.
- Mention regressions or improvements.
- Only state facts explicitly given above — do not guess or speculate.
- Do not say a field is unknown, unspecified, or not provided — if missing, skip it silently.
- Be complete and helpful, but avoid unnecessary repetition or filler.
""".strip()


def handle_application_question(app_id, question, user_id=None):
    context = build_chatbot_context(app_id)

    retrieved_chunks = retrieve_relevant_chunks(app_id, question, top_k=2)
    retrieved_knowledge = format_retrieved_knowledge(retrieved_chunks)

    system_prompt = build_application_system_prompt()
    user_prompt = build_application_user_prompt(context, question, retrieved_knowledge)

    try:
        answer = generate_llm_response(system_prompt, user_prompt)
        print("=== RAW LLM OUTPUT ===")
        print(repr(answer))
        print("=== RAW LENGTH:", len(answer) if answer else 0, "===")

        answer = _clean_llm_answer(answer)
        print("=== AFTER CLEAN ===")
        print(repr(answer))
        print("=== AFTER CLEAN LENGTH:", len(answer) if answer else 0, "===")

        answer = _trim_to_complete_sentence(answer)
        print("=== AFTER TRIM ===")
        print(repr(answer))
        print("=== AFTER TRIM LENGTH:", len(answer) if answer else 0, "===")
    except Exception as e:
        print("=== LLM CALL FAILED:", repr(e), "===")
        answer = ""

    if not answer or not answer.strip():
        print("=== FALLING BACK TO DETERMINISTIC ANSWER ===")
        answer_parts = [f"{context['app_name']}"]
        if _is_known(context.get("domain")):
            answer_parts.append(f"is a {context['domain']} application")
        if _is_known(context.get("environment")):
            answer_parts.append(f"running in the {context['environment']} environment")
        base = " ".join(answer_parts) + "."

        tech_bits = []
        if _is_known(context["tech_stack"].get("frontend")):
            tech_bits.append(f"{context['tech_stack']['frontend']} on the frontend")
        if _is_known(context["tech_stack"].get("backend")):
            tech_bits.append(f"{context['tech_stack']['backend']} on the backend")
        tech_sentence = f" It currently appears to use {' and '.join(tech_bits)}." if tech_bits else ""

        metrics_sentence = (
            f" Current CPU usage is {context['metrics']['cpu_percent']}% and memory "
            f"usage is {context['metrics']['memory_percent']}%."
        )

        answer = base + tech_sentence + metrics_sentence

    return {
        "answer": answer,
        "mode": context["mode"],
    }

def handle_anomaly_question(app_id, question, user_id=None):
    context = build_chatbot_context(app_id)
    latest_state = get_latest_anomaly_for_app(app_id)

    # Always get the real, DB-aggregated count first — independent of any
    # row cap or windowing on the detail query below.
    counts = get_anomaly_counts_for_app(app_id)

    if is_count_question(question):
        total = counts.get("total", 0)
        if total == 0:
            answer = "No anomalies have been recorded for this application yet."
        else:
            breakdown = ", ".join(
                f"{v} {k.lower()}" for k, v in counts.items() if k != "total"
            )
            answer = f"**{total}** anomalies have been recorded so far ({breakdown})."
        return {
            "answer": answer,
            "mode": latest_state.get("mode", "advisory"),
        }

    anomaly_records = get_anomalies_by_time_window(app_id, question)

    if not anomaly_records and counts.get("total", 0) == 0:
        answer = "No anomaly records were found for the requested time window."
        return {
            "answer": answer,
            "mode": latest_state.get("mode", "advisory"),
        }

    system_prompt = build_anomaly_system_prompt()
    user_prompt = build_anomaly_user_prompt(context, anomaly_records, question, counts)

    try:
        answer = generate_llm_response(system_prompt, user_prompt)
        answer = _clean_llm_answer(answer)
        answer = _trim_to_complete_sentence(answer)
    except Exception:
        answer = ""

    if not answer or not answer.strip():
        breakdown = ", ".join(
            f"{v} {k.lower()}" for k, v in counts.items() if k != "total"
        )
        answer = (
            f"There have been **{counts.get('total', 0)}** anomalies recorded for this "
            f"application so far ({breakdown}). Please try rephrasing your question for more detail."
        )

    return {
        "answer": answer,
        "mode": latest_state.get("mode", "diagnostic"),
    }


def handle_test_comparison_question(app_id, question, user_id=None):
    context = build_chatbot_context(app_id)
    cycle_a, cycle_b = extract_cycle_numbers(question)
    metrics = extract_requested_metrics(question)

    if cycle_a is None or cycle_b is None or not metrics:
        answer = (
            "Please specify which test cycles you want to compare and which metrics "
            "you want to focus on, such as response time, throughput, error rate, CPU, or memory.\n\n"
            "Example: Compare cycle 2 and cycle 5 for response time and throughput."
        )
        return {
            "answer": answer,
            "mode": "advisory",
        }

    comparison_data = get_test_cycle_comparison(app_id, cycle_a, cycle_b, metrics)

    system_prompt = build_test_comparison_system_prompt()
    user_prompt = build_test_comparison_user_prompt(context, comparison_data, metrics, question)

    try:
        answer = generate_llm_response(system_prompt, user_prompt)
        answer = _clean_llm_answer(answer)
        answer = _trim_to_complete_sentence(answer)
    except Exception:
        answer = ""

    if not answer or not answer.strip():
        selected_metrics = []
        for metric in metrics:
            if metric in comparison_data["metrics"]:
                data = comparison_data["metrics"][metric]
                selected_metrics.append(
                    f"- {metric}: baseline={data['baseline']}, target={data['target']}, "
                    f"difference={data['difference']}, difference_percent={data['difference_percent']}%"
                )

        metrics_text = "\n".join(selected_metrics)

        answer = (
            f"{comparison_data['summary']}\n\n"
            f"Requested metric comparison:\n{metrics_text}\n\n"
            f"Regression detected: {'Yes' if comparison_data['regression_detected'] else 'No'}."
        )

    return {
        "answer": answer,
        "mode": "advisory",
    }


def handle_chatbot_question(app_id, question, user_id=None):
    question_type = detect_question_type(question)

    if question_type == "anomaly":
        return handle_anomaly_question(app_id, question, user_id)

    if question_type == "test_comparison":
        return handle_test_comparison_question(app_id, question, user_id)

    return handle_application_question(app_id, question, user_id)


def generate_demo_chat_response(app_id, question):
    return handle_chatbot_question(app_id, question)