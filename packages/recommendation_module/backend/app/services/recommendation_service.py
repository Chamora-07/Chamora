"""
recommendation_service.py

Generates the "Actionable Recommendations" section of the Chamora report.

Pipeline position:
    Anomaly Detection -> (report summary / findings) -> *this service*
        -> RAG retrieval (ChromaDB) -> Groq (Llama 3.1) -> structured recommendations

Design:
  - The frontend computes a compact `findings` payload from the detected anomalies
    and POSTs it here. We do NOT re-run detection — we turn those findings into a
    grounded, specific set of recommendations.
  - The evidence block is built deterministically from the findings so the LLM is
    reasoning over exact numbers, not vibes.
  - RAG retrieval pulls relevant chunks from the app's knowledge base to ground the
    advice in the team's own runbooks/docs.
  - If Groq is unavailable / rate-limited / returns junk, a deterministic
    rule-based fallback produces recommendations from the same evidence, so a live
    demo never dies on a 429.

Expected `findings` shape (from the frontend ReportPage):
    {
      "app_id": 1,
      "totals":  {"detections": 4249, "critical": 923, "warning": 3326},
      "signals": {
          "peak_memory_pressure": 0.164,      # 0..1
          "baseline_memory_pressure": 0.04,   # 0..1 (optional)
          "max_error_rate": 1.0,              # 0..1
          "timeouts": 14,                     # count of timeout windows
          "restarts": 20,                     # count of restart windows
          "restarts_new_vs_baseline": true,   # optional
          "latency_p95_regression_pct": 73    # optional, +% vs baseline
      },
      "top_incidents": [                       # optional, a few worst windows
          {"when": "2026-06-04 03:05", "severity": "CRITICAL",
           "error_rate": 1.0, "latency_p95": 99.99,
           "memory_pressure": 0.16, "restart": true}
      ]
    }
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

# Adjust these imports to your tree.
from .groq_service import generate_llm_response
from .rag_service import retrieve_relevant_chunks  # (app_id, question, top_k)


# ---------------------------------------------------------------------------
# 1. Turn findings -> human-readable, number-anchored evidence statements
# ---------------------------------------------------------------------------

def _pct(x: Optional[float]) -> str:
    return f"{round(x * 100)}%" if isinstance(x, (int, float)) else "n/a"


def build_evidence_block(findings: dict) -> list[str]:
    """Deterministic, factual statements the LLM must reason over.

    Each line states a symptom AND the measured number that proves it.
    """
    s = findings.get("signals", {}) or {}
    t = findings.get("totals", {}) or {}
    lines: list[str] = []

    if t:
        lines.append(
            f"Detection volume: {t.get('detections', 'n/a')} anomaly windows "
            f"({t.get('critical', 0)} critical, {t.get('warning', 0)} warning)."
        )
    if s.get("timeouts"):
        lines.append(
            f"Request timeouts: {s['timeouts']} window(s) returned no response "
            f"(latency p95 hit the timeout sentinel). The service was unreachable "
            f"during these windows."
        )
    if s.get("max_error_rate", 0) and s["max_error_rate"] >= 0.99:
        lines.append(
            "Error rate: reached 100% in the most severe windows — every request "
            "failed, not a partial degradation."
        )
    elif s.get("max_error_rate"):
        lines.append(f"Error rate: peaked at {_pct(s['max_error_rate'])}.")
    if s.get("restarts"):
        new = " This restart signal is NEW versus the earlier baseline cycle." \
            if s.get("restarts_new_vs_baseline") else ""
        lines.append(
            f"Container restarts: {s['restarts']} restart(s) observed.{new} "
            f"Restarts during load usually indicate the orchestrator killed the "
            f"container (OOMKilled or failed liveness probe)."
        )
    if s.get("peak_memory_pressure"):
        base = s.get("baseline_memory_pressure")
        cmp = f" vs ~{_pct(base)} baseline" if base else ""
        lines.append(
            f"Memory pressure: peaked at {_pct(s['peak_memory_pressure'])}{cmp} — "
            f"the dominant stress signal across the run."
        )
    if s.get("latency_p95_regression_pct"):
        lines.append(
            f"Latency regression: p95 latency rose +{s['latency_p95_regression_pct']}% "
            f"in the recent cycle compared to baseline."
        )

    incidents = findings.get("top_incidents") or []
    if incidents:
        lines.append("Worst individual windows:")
        for i in incidents[:4]:
            lat = "timeout" if (i.get("latency_p95", 0) or 0) >= 99 else \
                f"{round((i.get('latency_p95') or 0) * 1000)}ms"
            lines.append(
                f"  - {i.get('when', '?')} [{i.get('severity', '?')}]: "
                f"errors {_pct(i.get('error_rate'))}, latency {lat}, "
                f"mem pressure {_pct(i.get('memory_pressure'))}, "
                f"restart={'yes' if i.get('restart') else 'no'}."
            )
    return lines


def _rag_queries(findings: dict) -> list[str]:
    """Derive targeted retrieval queries from the dominant signals."""
    s = findings.get("signals", {}) or {}
    queries: list[str] = []
    if s.get("restarts"):
        queries.append("container restart OOMKilled out of memory crash during load")
    if s.get("peak_memory_pressure", 0) and s["peak_memory_pressure"] >= 0.10:
        queries.append("high memory pressure tuning memory limit leak")
    if s.get("timeouts") or (s.get("max_error_rate", 0) >= 0.99):
        queries.append("request timeout 100% error rate service unavailable")
    if s.get("latency_p95_regression_pct"):
        queries.append("p95 latency regression slow response performance")
    if not queries:  # always retrieve something
        queries.append("performance anomaly remediation")
    return queries


def gather_knowledge(app_id: int | str, findings: dict, top_k: int = 4) -> str:
    """Retrieve and de-duplicate knowledge-base chunks for the issues found."""
    seen: set[str] = set()
    blocks: list[str] = []
    for q in _rag_queries(findings):
        try:
            chunks = retrieve_relevant_chunks(app_id, q, top_k=top_k) or []
        except Exception:
            chunks = []
        for c in chunks:
            text = (c.get("text") or "").strip()
            key = text[:120]
            if text and key not in seen:
                seen.add(key)
                blocks.append(text)
    if not blocks:
        return "(No specific knowledge-base entries were retrieved for these issues.)"
    # Cap total context so we don't blow the prompt budget.
    return "\n\n---\n\n".join(blocks[:8])


# ---------------------------------------------------------------------------
# 2. The prompt
# ---------------------------------------------------------------------------

RECO_SYSTEM_PROMPT = (
    "You are a senior Site Reliability Engineer writing the recommendations section "
    "of a performance report for the engineering team that owns this application. "
    "You are given (1) the concrete anomalies detected in their system, each with "
    "measured evidence, and (2) relevant excerpts from their internal knowledge "
    "base and runbooks.\n\n"
    "Produce SPECIFIC, ACTIONABLE recommendations that address the ACTUAL issues in "
    "the evidence — never generic best practices. Every recommendation MUST:\n"
    "- Name the specific symptom and cite the exact metric/number that proves it.\n"
    "- State the most likely cause in one or two sentences, grounded in the evidence.\n"
    "- Give concrete, ordered actions: specific config changes, commands, code areas "
    "to inspect, or limits to set — not vague advice like 'investigate further'.\n"
    "- Use the knowledge-base excerpts where they apply; do not invent runbook steps "
    "that contradict them.\n"
    "- Be honest about uncertainty: if evidence is insufficient to pinpoint a cause, "
    "say exactly what to measure next.\n\n"
    "Do NOT recommend things the evidence does not support. Do NOT pad with filler. "
    "Prioritise by impact: issues causing outages (timeouts, 100% errors, container "
    "restarts) come before efficiency tuning.\n\n"
    "Return ONLY a JSON array — no prose, no markdown code fences. Each element:\n"
    "{\n"
    '  "title": "<short imperative title>",\n'
    '  "priority": "critical" | "high" | "medium" | "low",\n'
    '  "observation": "<the symptom + the exact evidence/number>",\n'
    '  "likely_cause": "<concise reasoning grounded in the evidence>",\n'
    '  "actions": ["<ordered step 1>", "<ordered step 2>", "..."],\n'
    '  "addresses": "<which metric/signal this targets>"\n'
    "}\n"
    "Return between 3 and 6 recommendations, ordered most severe first."
)


def build_user_prompt(app_id: int | str, evidence: list[str], knowledge: str) -> str:
    evidence_text = "\n".join(evidence) if evidence else "(No anomalies supplied.)"
    return (
        f"APPLICATION: #{app_id}\n\n"
        f"DETECTED ISSUES (anomaly detection + cycle comparison):\n"
        f"{evidence_text}\n\n"
        f"KNOWLEDGE BASE EXCERPTS (retrieved for these issues):\n"
        f"{knowledge}\n\n"
        f"Write the recommendations now, as the JSON array specified. Ground every "
        f"recommendation in the evidence above and reference the specific numbers."
    )


# ---------------------------------------------------------------------------
# 3. Parsing + deterministic fallback
# ---------------------------------------------------------------------------

_VALID_PRIORITIES = {"critical", "high", "medium", "low"}


def _parse_llm_json(text: str) -> Optional[list[dict]]:
    """Extract a JSON array from the model output, tolerating stray fences/prose."""
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    # Grab the outermost [ ... ] if the model added a sentence around it.
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start:end + 1]
    try:
        data = json.loads(cleaned)
    except Exception:
        return None
    if not isinstance(data, list):
        return None

    out: list[dict] = []
    for item in data:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        prio = str(item.get("priority", "medium")).lower()
        actions = item.get("actions") or []
        if isinstance(actions, str):
            actions = [actions]
        out.append({
            "title": str(item["title"]).strip(),
            "priority": prio if prio in _VALID_PRIORITIES else "medium",
            "observation": str(item.get("observation", "")).strip(),
            "likely_cause": str(item.get("likely_cause", "")).strip(),
            "actions": [str(a).strip() for a in actions if str(a).strip()],
            "addresses": str(item.get("addresses", "")).strip(),
        })
    return out or None


def _fallback_recommendations(findings: dict) -> list[dict]:
    """Rule-based recommendations derived from the same evidence.

    Used when Groq is unavailable or returns unparseable output. Specific enough
    to be useful, generic enough to always render.
    """
    s = findings.get("signals", {}) or {}
    recs: list[dict] = []

    if s.get("restarts"):
        recs.append({
            "title": "Stop the container restarts under load",
            "priority": "critical",
            "observation": f"{s['restarts']} container restart(s) were observed during "
                           "the run, coinciding with peak memory pressure.",
            "likely_cause": "The container is most likely being OOMKilled — memory "
                            "usage crosses its cgroup limit and the orchestrator "
                            "terminates it.",
            "actions": [
                "Check `kubectl describe pod` / container exit codes for OOMKilled (137).",
                "Raise the container memory limit, or fix the allocation that grows under load.",
                "Add/relax the liveness probe so a slow-but-alive pod isn't killed mid-request.",
                "Re-run the load test and confirm restarts drop to zero.",
            ],
            "addresses": "restarts / memory_pressure",
        })

    if s.get("peak_memory_pressure", 0) and s["peak_memory_pressure"] >= 0.10:
        recs.append({
            "title": "Reduce peak memory pressure",
            "priority": "high",
            "observation": f"Memory pressure peaked at {_pct(s['peak_memory_pressure'])}, "
                           f"well above the ~{_pct(s.get('baseline_memory_pressure', 0.04))} baseline.",
            "likely_cause": "Either a per-request allocation that doesn't get released, "
                            "or an under-provisioned memory limit for the offered load.",
            "actions": [
                "Profile heap usage during the load window to find the growth source.",
                "Cap in-memory buffers/caches and stream large responses instead of buffering.",
                "Set memory requests/limits from the observed peak with headroom.",
            ],
            "addresses": "memory_pressure",
        })

    if s.get("timeouts") or s.get("max_error_rate", 0) >= 0.99:
        recs.append({
            "title": "Eliminate request timeouts and 100% error windows",
            "priority": "critical",
            "observation": f"{s.get('timeouts', 0)} window(s) returned no response and "
                           "error rate reached 100% at the worst points.",
            "likely_cause": "The service became unreachable — consistent with the "
                            "restarts above (requests during a restart get no response).",
            "actions": [
                "Correlate timeout timestamps with restart events to confirm the link.",
                "Add a readiness probe so traffic isn't routed to a pod that isn't ready.",
                "Introduce graceful shutdown + connection draining to avoid dropped requests.",
            ],
            "addresses": "error_rate / timeouts",
        })

    if s.get("latency_p95_regression_pct"):
        recs.append({
            "title": "Investigate the p95 latency regression",
            "priority": "medium",
            "observation": f"p95 latency rose +{s['latency_p95_regression_pct']}% in the "
                           "recent cycle versus baseline.",
            "likely_cause": "Could be the same memory pressure (GC pauses) or a newly "
                            "introduced slow path; evidence isn't conclusive on its own.",
            "actions": [
                "Compare slow endpoints between the two cycles to localise the regression.",
                "Check GC pause times during the high-memory windows.",
                "Bisect recent deploys between the baseline and current cycle.",
            ],
            "addresses": "latency_p95",
        })

    if not recs:
        recs.append({
            "title": "Maintain current monitoring",
            "priority": "low",
            "observation": "No outage-level signals were present in the supplied findings.",
            "likely_cause": "System appears within normal operating bounds.",
            "actions": ["Keep anomaly thresholds as-is and re-evaluate after the next run."],
            "addresses": "general",
        })
    return recs


# ---------------------------------------------------------------------------
# 4. Public entry point
# ---------------------------------------------------------------------------

def generate_recommendations(app_id: int | str, findings: dict) -> dict:
    """Return {recommendations: [...], source: 'llm'|'fallback'}.

    Always returns something renderable, even if Groq/RAG are down.
    """
    evidence = build_evidence_block(findings)
    knowledge = gather_knowledge(app_id, findings)

    system_prompt = RECO_SYSTEM_PROMPT
    user_prompt = build_user_prompt(app_id, evidence, knowledge)

    try:
        raw = generate_llm_response(system_prompt, user_prompt)
        parsed = _parse_llm_json(raw)
        if parsed:
            return {"recommendations": parsed, "source": "llm"}
    except Exception:
        pass  # fall through to deterministic recommendations

    return {"recommendations": _fallback_recommendations(findings), "source": "fallback"}