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


def build_application_system_prompt():
    return (
        "You are Chamora, an AI assistant that provides customized recommendations "
        "for the user's selected application. "
        "Answer ONLY questions that are directly related to the provided application data, documents, or context. "
        "If the user asks a general knowledge question unrelated to this application "
        "(such as 'What is AI?', 'What is ML?', or any topic not in the application context), "
        "respond ONLY with: 'Chamora aims to provide customized answers for application related questions'. "
        "Be practical, clear, and specific. "
        "Use clean markdown with short bullet points when useful."
    )


def build_application_user_prompt(context, question, retrieved_knowledge):
    containers = context["containers"]
    primary_container = containers[0]["name"] if containers else "unknown-container"
    primary_image = containers[0]["image"] if containers else "unknown-image"

    evidence = ", ".join(context["tech_stack"].get("evidence", [])) or "Unknown"
    safe_retrieved_knowledge = retrieved_knowledge[:1800]

    return f"""
Application Context
- Name: {context["app_name"]}
- ID: {context["app_id"]}
- Domain: {context["domain"]}
- Environment: {context["environment"]}
- User: {context["user_name"]} ({context["user_id"]})
- Repo URL: {context["repo_url"]}

Technology Stack
- Frontend: {context["tech_stack"]["frontend"]}
- Backend: {context["tech_stack"]["backend"]}
- Database: {context["tech_stack"]["database"]}
- Evidence: {evidence}

Runtime Metrics
- CPU Usage: {context["metrics"]["cpu_percent"]}%
- Memory Usage: {context["metrics"]["memory_percent"]}%
- Memory Used: {context["metrics"]["memory_used"]}
- Memory Total: {context["metrics"]["memory_total"]}
- Metrics Source: {context["metrics"]["source"]}

Container
- Primary Container: {primary_container}
- Image: {primary_image}

Current Mode
- {context["mode"]}

Retrieved Knowledge Base Content
{safe_retrieved_knowledge}

User Question
{question}

Instructions
- Answer specifically for this application.
- Use the retrieved knowledge when relevant.
- Do not answer like a general chatbot.
- If data is unknown, say it clearly.
- Use neat markdown.
- Keep the answer concise and focused.
""".strip()


def build_anomaly_system_prompt():
    return (
        "You are Chamora in diagnostic mode. "
        "Explain anomalies using the provided application context and anomaly records. "
        "Focus on what happened, likely cause, impact, and actionable next steps. "
        "Use neat markdown."
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

    return f"""
Application Context
- Name: {context["app_name"]}
- ID: {context["app_id"]}
- Domain: {context["domain"]}
- Environment: {context["environment"]}
- Current Mode: diagnostic

Anomaly Records
- Total anomalies recorded for this application (all time): {total} ({severity_summary})
- Showing the {len(trimmed_records)} most relevant record(s) below as examples.

{anomaly_text}

User Question
{question}

Instructions
- The "Total anomalies recorded" figure above is authoritative for any count/total question — never infer a count from how many records are listed in detail.
- Explain what happened clearly, using the detailed records as illustrative examples only.
- Mention the requested time window if relevant.
- Interpret severity, score, root cause, and evidence.
- Give actionable recommendations.
- Stay specific to this application.
- Keep the answer concise and focused.
""".strip()


def build_test_comparison_system_prompt():
    return (
        "You are Chamora, an AI assistant for application-specific test analysis. "
        "Use the supplied comparison data to explain the differences clearly and practically. "
        "Use neat markdown."
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

    return f"""
Application Context
- Name: {context["app_name"]}
- ID: {context["app_id"]}
- Domain: {context["domain"]}
- Environment: {context["environment"]}

Comparison Summary
- {comparison_data.get("summary", "No summary available")}
- Regression Detected: {comparison_data.get("regression_detected", False)}

Requested Metric Comparison
{selected_text}

User Question
{question}

Instructions
- Explain the comparison clearly.
- Mention regressions or improvements.
- Keep the answer focused on the selected application.
- Use neat markdown.
""".strip()


def handle_application_question(app_id, question, user_id=None):
    context = build_chatbot_context(app_id)

    retrieved_chunks = retrieve_relevant_chunks(app_id, question, top_k=2)
    retrieved_knowledge = format_retrieved_knowledge(retrieved_chunks)

    system_prompt = build_application_system_prompt()
    user_prompt = build_application_user_prompt(context, question, retrieved_knowledge)

    try:
        answer = generate_llm_response(system_prompt, user_prompt)
    except Exception:
        answer = (
            f"{context['app_name']} is a {context['domain']} application running in the "
            f"{context['environment']} environment. It currently appears to use "
            f"{context['tech_stack']['frontend']} on the frontend and "
            f"{context['tech_stack']['backend']} on the backend. "
            f"The current CPU usage is {context['metrics']['cpu_percent']}% and memory usage is "
            f"{context['metrics']['memory_percent']}%."
        )

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
    answer = generate_llm_response(system_prompt, user_prompt)

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
    except Exception:
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