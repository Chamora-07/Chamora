from app.services.groq_service import generate_llm_response
from app.services.rag_service import retrieve_relevant_chunks, format_retrieved_knowledge
from app.services.application_context_service import get_application_context
from app.services.anomaly_query_service import get_latest_anomaly_for_app, get_anomalies_by_time_window
from app.services.test_comparison_service import (
    extract_cycle_numbers,
    extract_requested_metrics,
    get_test_cycle_comparison,
)
from app.services.chat_history_service import (
    create_chat_session,
    store_chat_message,
    store_recommendation_history,
)
from app.services.rag_logging_service import log_retrieval
from app.services.time_parser import parse_time_window
from app.services.anomaly_service import get_anomalies_between

def classify_question_llm(question):
    prompt = f"""
        Classify this question into one category:

        Categories:
        - application (questions about the app, metrics, anomalies, tests, performance)
        - anomaly (incident, spike, failure, root cause, downtime)
        - test_comparison (comparing test runs or cycles)
        - general_knowledge (definitions, explanations, facts not related to the application)

        Question: {question}

        Return ONLY one word from the categories above.
        """

    response = generate_llm_response(
        "You are a strict classification engine. Output only one label.",
        prompt
    )

    return response.strip().lower()

def build_chatbot_context(app_id):
    return get_application_context(app_id)


def build_application_system_prompt():
    return (
        "You are Chamora, an AI assistant that provides customized recommendations "
        "for the user's selected application. Answer only using the provided application "
        "context and retrieved knowledge when relevant. Be practical, clear, and specific. "
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
- Use ONLY the provided application context and retrieved knowledge
- If the answer is not found in retrieved knowledge, say:
  "No relevant information found in uploaded documents"
- Do NOT hallucinate
- Keep answer short and structured
- Format the answer using clean markdown.
- Use bullet points for lists.
- Do not put all bullet points in one paragraph.
- Use short sections when helpful.
""".strip()


def build_anomaly_system_prompt():
    return (
        "You are Chamora in diagnostic mode. Explain anomalies using only the provided "
        "application context and anomaly records. Focus on whether anomalies were found "
        "in the requested time window, what happened, likely cause, impact, and actionable next steps. "
        "Use neat markdown."
    )


def build_anomaly_user_prompt(context: dict, anomaly_records: list[dict], question: str) -> str:
    trimmed_records = anomaly_records[:3]

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
- Time UTC: {record.get("window_timestamp")}
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
- If the question asks about a specific time, answer only based on anomaly records in that requested time window.
- Do not use latest anomaly state as evidence for a different requested time.
- Interpret severity, score, root cause, and evidence.
- Give actionable recommendations only if anomaly records exist.
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
    log_retrieval(app_id, question, retrieved_chunks)

    sources = []
    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata", {})
        file_name = metadata.get("file_name", "unknown")
        if file_name not in sources:
            sources.append(file_name)

    system_prompt = build_application_system_prompt()
    user_prompt = build_application_user_prompt(context, question, retrieved_knowledge)

    try:
        answer = generate_llm_response(system_prompt, user_prompt)
    except Exception:
        answer = (
            f"{context['app_name']} is a {context['domain']} application running in the "
            f"{context['environment']} environment. Current CPU usage is "
            f"{context['metrics']['cpu_percent']}% and memory usage is "
            f"{context['metrics']['memory_percent']}%. Retrieved document knowledge was unavailable or insufficient."
        )

    store_chat_message(session_id, app_id, user_id, "assistant", answer, "application")
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
        "sources": sources
    }


def handle_anomaly_question(app_id, question, session_id, user_id):
    context = build_chatbot_context(app_id)
    latest_state = get_latest_anomaly_for_app(app_id)

    time_window = parse_time_window(question)

    if time_window:
        start_time, end_time = time_window

        anomaly_records = get_anomalies_between(
            app_id,
            start_time,
            end_time
        )
    else:
        anomaly_records = get_anomalies_by_time_window(
            app_id,
            question
        )

    if not anomaly_records:
        answer = "No anomaly records were found for the requested time window."
        store_chat_message(session_id, app_id, user_id, "assistant", answer, "anomaly")
        store_recommendation_history(
            app_id,
            user_id,
            session_id,
            question,
            answer,
            "diagnostic",
            [],
        )
        return {
            "answer": answer,
            "mode": "diagnostic",
        }

    system_prompt = build_anomaly_system_prompt()
    user_prompt = build_anomaly_user_prompt(context, anomaly_records, question)

    try:
        answer = generate_llm_response(system_prompt, user_prompt)
    except Exception:
        answer = (
            f"Found {len(anomaly_records)} anomaly record(s) for the requested time window. "
            f"Latest severity: {anomaly_records[-1].get('severity')}. "
            f"Root cause: {anomaly_records[-1].get('root_cause')}."
        )

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
            "Please specify which test runs or cycles you want to compare and which metrics "
            "you want to focus on.\n\n"
            "Example: Compare test run 1 and 2 for response time and throughput."
        )
        store_chat_message(session_id, app_id, user_id, "assistant", answer, "clarification")

        return {
            "answer": answer,
            "mode": "advisory",
        }

    comparison_data = get_test_cycle_comparison(app_id, cycle_a, cycle_b)

    if comparison_data is None:
        answer = f"No comparison data found for test run/cycle {cycle_a} and {cycle_b}."
        store_chat_message(session_id, app_id, user_id, "assistant", answer, "test_comparison")

        return {
            "answer": answer,
            "mode": "advisory",
        }

    system_prompt = build_test_comparison_system_prompt()
    user_prompt = build_test_comparison_user_prompt(
        context,
        comparison_data,
        metrics,
        question
    )

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

def normalize_question_type(qtype):
    qtype = qtype.lower().strip()

    allowed = ["application", "anomaly", "test_comparison", "general_knowledge"]

    if qtype not in allowed:
        return "application"   # safe fallback

    return qtype

def handle_chatbot_question(app_id, question, user_id=None):
    question_type = normalize_question_type(classify_question_llm(question))
    context = build_chatbot_context(app_id)

    session = create_chat_session(app_id, user_id, context["mode"])
    session_id = session["id"] if "id" in session else session["session_id"]

    store_chat_message(session_id, app_id, user_id, "user", question, question_type)

    if question_type == "general_knowledge":
        return blocked_common_response()
        store_chat_message(session_id, app_id, user_id, "assistant", answer["answer"], "common_blocked")
        return answer

    if question_type == "test_comparison":
        return handle_test_comparison_question(app_id, question, session_id, user_id)

    if question_type == "anomaly":
        return handle_anomaly_question(app_id, question, session_id, user_id)

    return handle_application_question(app_id, question, session_id, user_id)


def generate_demo_chat_response(app_id, question):
    return handle_chatbot_question(app_id, question, None)