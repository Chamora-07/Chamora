from .groq_service import generate_llm_response
from .rag_service import retrieve_relevant_chunks, format_retrieved_knowledge
from .application_context_service import get_application_context
from .anomaly_query_service import get_latest_anomaly_for_app, get_anomalies_by_time_window
from .test_comparison_service import (
    extract_cycle_numbers,
    extract_requested_metrics,
    get_test_cycle_comparison,
)
from .chat_history_service import (
    create_chat_session,
    store_chat_message,
    store_recommendation_history,
)


def detect_question_type(question):
    q = question.lower().strip()

    anomaly_keywords = [
        "anomaly",
        "diagnostic",
        "issue",
        "problem",
        "abnormal",
        "root cause",
        "what happened yesterday",
        "why there is an anomaly",
        "why is there an anomaly",
        "why did anomaly happen",
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

    application_keywords = [
        "my application",
        "my app",
        "tech stack",
        "application details",
        "application metadata",
        "my environment",
        "my documents",
        "uploaded documents",
        "explain my application",
        "explain about my application",
    ]

    common_keywords = [
        "what is machine learning",
        "tell me a joke",
        "capital of",
        "who is",
        "history of",
        "weather",
        "translate",
    ]

    if any(keyword in q for keyword in anomaly_keywords):
        return "anomaly"

    if any(keyword in q for keyword in test_keywords):
        return "test_comparison"

    if any(keyword in q for keyword in application_keywords):
        return "application"

    if any(keyword in q for keyword in common_keywords):
        return "common_blocked"

    return "application"


def build_chatbot_context(app_id):
    return get_application_context(app_id)


def build_application_system_prompt():
    return (
        "You are Chamora, an AI assistant that provides customized recommendations "
        "for the user's selected application. "
        "Answer only in the context of the provided application data. "
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


def build_anomaly_user_prompt(context: dict, anomaly_records: list[dict], question: str) -> str:
    trimmed_records = anomaly_records[:3]

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
{anomaly_text}

User Question
{question}

Instructions
- Explain what happened clearly.
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


def blocked_common_response():
    return {
        "answer": "Chamora aims to provide customized recommendations and assistance for your application, not general answers as other chatbots.",
        "mode": "advisory",
    }


def handle_application_question(app_id, question, session_id, user_id):
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

    store_chat_message(session_id, app_id, user_id, "assistant", answer, "application")
    store_recommendation_history(
        app_id,
        user_id,
        session_id,
        question,
        answer,
        context["mode"],
        [],
    )

    return {
        "answer": answer,
        "mode": context["mode"],
    }


def handle_anomaly_question(app_id, question, session_id, user_id):
    context = build_chatbot_context(app_id)
    latest_state = get_latest_anomaly_for_app(app_id)
    anomaly_records = get_anomalies_by_time_window(app_id, question)

    if not anomaly_records:
        answer = "No anomaly records were found for the requested time window."
        store_chat_message(session_id, app_id, user_id, "assistant", answer, "anomaly")
        return {
            "answer": answer,
            "mode": latest_state.get("mode", "advisory"),
        }

    system_prompt = build_anomaly_system_prompt()
    user_prompt = build_anomaly_user_prompt(context, anomaly_records, question)
    answer = generate_llm_response(system_prompt, user_prompt)

    store_chat_message(session_id, app_id, user_id, "assistant", answer, "anomaly")
    store_recommendation_history(
        app_id,
        user_id,
        session_id,
        question,
        answer,
        latest_state.get("mode", "diagnostic"),
        [],
    )

    return {
        "answer": answer,
        "mode": latest_state.get("mode", "diagnostic"),
    }


def handle_test_comparison_question(app_id, question, session_id, user_id):
    context = build_chatbot_context(app_id)
    cycle_a, cycle_b = extract_cycle_numbers(question)
    metrics = extract_requested_metrics(question)

    if cycle_a is None or cycle_b is None or not metrics:
        answer = (
            "Please specify which test cycles you want to compare and which metrics "
            "you want to focus on, such as response time, throughput, error rate, CPU, or memory.\n\n"
            "Example: Compare cycle 2 and cycle 5 for response time and throughput."
        )
        store_chat_message(session_id, app_id, user_id, "assistant", answer, "clarification")
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

    store_chat_message(session_id, app_id, user_id, "assistant", answer, "test_comparison")
    store_recommendation_history(
        app_id,
        user_id,
        session_id,
        question,
        answer,
        "advisory",
        [],
    )

    return {
        "answer": answer,
        "mode": "advisory",
    }


def handle_chatbot_question(app_id, question, user_id=None, session_id=None):
    question_type = detect_question_type(question)
    context = build_chatbot_context(app_id)

    if not session_id:
        session = create_chat_session(app_id, user_id, context["mode"])
        session_id = session["id"] if "id" in session else session["session_id"]

    store_chat_message(session_id, app_id, user_id, "user", question, question_type)

    if question_type == "common_blocked":
        answer = blocked_common_response()
        store_chat_message(session_id, app_id, user_id, "assistant", answer["answer"], "common_blocked")
        return {**answer, "session_id": session_id}

    if question_type == "anomaly":
        response = handle_anomaly_question(app_id, question, session_id, user_id)
        return {**response, "session_id": session_id}

    if question_type == "test_comparison":
        response = handle_test_comparison_question(app_id, question, session_id, user_id)
        return {**response, "session_id": session_id}

    response = handle_application_question(app_id, question, session_id, user_id)
    return {**response, "session_id": session_id}


def generate_demo_chat_response(app_id, question, session_id=None):
    return handle_chatbot_question(app_id, question, None, session_id)