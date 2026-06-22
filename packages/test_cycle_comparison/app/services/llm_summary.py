"""
LLM-backed narrative summary for a Phase-4 comparison report.

Triages the report by `significance.rank` and sends only the top-N axes
to Groq (default 12), along with aggregate counts so the model can say
"no significant change in 35 other metrics". Falls back to a deterministic
templated summary when Groq is unreachable or no API key is configured.

`generate_summary()` never raises — it always returns a dict with a
`summary` string, so the compare endpoint can include it inline.
"""

import asyncio
import logging
from typing import Iterator, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TOP_N = 12

# Lazy singleton so missing API key doesn't break module import.
_client = None
_client_init_error: Optional[str] = None


def _get_client():
    global _client, _client_init_error
    if _client is not None or _client_init_error is not None:
        return _client
    if not settings.GROQ_API_KEY:
        _client_init_error = "GROQ_API_KEY not configured"
        return None
    try:
        from groq import AsyncGroq
        _client = AsyncGroq(
            api_key=settings.GROQ_API_KEY,
            timeout=settings.GROQ_TIMEOUT,
        )
    except Exception as e:
        _client_init_error = f"{type(e).__name__}: {e}"
        logger.warning(f"Could not initialise Groq client: {_client_init_error}")
    return _client


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

async def generate_summary(report: dict, top_n: int = DEFAULT_TOP_N) -> dict:
    """
    Returns:
      { summary: str, source: 'llm' | 'fallback', model: str | None, error: str | None }
    """
    client = _get_client()
    if client is None:
        text = _fallback_summary(report, top_n)
        return {
            "summary": text,
            "source": "fallback",
            "model": None,
            "error": _client_init_error,
        }

    system = _build_system_prompt(report.get("mode", "baseline"))
    user = _build_user_prompt(report, top_n)

    try:
        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
            max_tokens=settings.GROQ_MAX_TOKENS,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise RuntimeError("LLM returned empty content")
        return {
            "summary": text,
            "source": "llm",
            "model": settings.GROQ_MODEL,
            "error": None,
        }
    except Exception as e:
        logger.exception("LLM call failed — falling back to templated summary")
        return {
            "summary": _fallback_summary(report, top_n),
            "source": "fallback",
            "model": settings.GROQ_MODEL,
            "error": f"{type(e).__name__}: {e}",
        }


# --------------------------------------------------------------------------- #
# Prompt construction
# --------------------------------------------------------------------------- #

def _build_system_prompt(mode: str) -> str:
    if mode == "threshold":
        return (
            "You are Chamora, a performance analyst reviewing a single test cycle "
            "against user-defined SLO thresholds. Lead with threshold violations, "
            "cite each metric's measured value, the limit it crossed, and by how much. "
            "Mention metrics that passed only briefly. Use clean markdown — short "
            "bullet points, no preamble, no apology. End with one practical next step."
        )
    return (
        "You are Chamora, a performance analyst comparing test cycles of a single "
        "application. Be specific and quantitative. Lead with regressions, mention "
        "notable improvements briefly, and end with one practical next step. "
        "Use clean markdown — short bullet points, no preamble, no apology. "
        "Cite the metric name, the percent change, and the cycle pair for every "
        "regression you mention."
    )


def _build_user_prompt(report: dict, top_n: int) -> str:
    cycles = report.get("cycles", [])
    n_cycles = len(cycles)
    baseline_id = report.get("baseline_cycle_id")
    grouped = report.get("group_by_endpoint", False)
    threshold_pct = report.get("regression_threshold_pct", 10.0)
    mode = report.get("mode", "baseline")

    cycle_lines = []
    for c in cycles:
        marker = " (baseline)" if c["cycle_id"] == baseline_id else ""
        duration = c.get("duration_seconds") or 0
        cycle_lines.append(
            f"  - cycle_id={c['cycle_id']}  "
            f"start={c.get('start_time')}  end={c.get('end_time')}  "
            f"duration={duration:.0f}s{marker}"
        )
    cycles_block = "\n".join(cycle_lines) or "  (none)"

    all_axes = list(_iter_axes_with_meta(report))
    top_axes = _select_top_axes(all_axes, top_n)
    metrics_block = _render_metrics_block(top_axes) or "  (no metrics)"

    if mode == "threshold":
        counts_line = (
            f"Violated: {report.get('violation_count', 0)}, "
            f"OK: {report.get('ok_count', 0)}, "
            f"No threshold set: {report.get('no_threshold_count', 0)}"
        )
        instruction = (
            "Lead with violations (lowest rank number). For each violated metric, "
            "cite the value, the limit (min or max), and the % overshoot. "
            "Briefly note how many metrics passed. If no violations, say so plainly."
        )
        mode_block = f"Mode: threshold check (single cycle vs SLOs)"
    else:
        counts_line = (
            f"Regressions: {report.get('regression_count', 0)}, "
            f"Improvements: {report.get('improvement_count', 0)}, "
            f"Unchanged: {report.get('unchanged_count', 0)}"
        )
        instruction = (
            "Describe the profile of this single cycle (top metric values and any "
            "obvious anomalies)."
            if n_cycles == 1
            else "Lead with the worst regressions (lowest rank number). "
                 "Cite metric name, percent change, and which cycle pair. "
                 "If improvements are notable, mention them briefly after."
        )
        mode_block = (
            f"Mode: baseline comparison (regression threshold {threshold_pct}%)"
        )

    other_axes_note = ""
    skipped = len(all_axes) - len(top_axes)
    if skipped > 0:
        other_axes_note = (
            f"\n(There are {skipped} additional metric axes not shown; "
            f"they fall outside the top {top_n} by significance.)"
        )

    return f"""Test cycle comparison report

- Application id: {report.get('application_id')}
- Endpoints in scope: {report.get('endpoint_ids')}
- Per-endpoint breakdown: {'yes' if grouped else 'no (aggregated)'}
- {mode_block}

Cycles ({n_cycles}):
{cycles_block}

Outcome counts: {counts_line}

Top {len(top_axes)} metric axes by significance (rank 1 = most significant):
{metrics_block}
{other_axes_note}

Instructions:
- {instruction}
- End with one actionable suggestion.
- Stay concise — aim for 5-8 short bullets total.
""".strip()


# --------------------------------------------------------------------------- #
# Triage helpers (kept independent so they can be unit-tested)
# --------------------------------------------------------------------------- #

def _iter_axes_with_meta(report: dict) -> Iterator[Tuple[str, Optional[str], dict, dict]]:
    """
    Yield (metric_key, endpoint_id_or_None, axis_block, parent_meta) for every
    comparison axis in the report. Parent meta gives us unit/higher_is_worse
    even when reading a nested per-endpoint block.
    """
    for key, block in report.get("metrics", {}).items():
        parent_meta = {
            "unit": block.get("unit"),
            "higher_is_worse": block.get("higher_is_worse"),
            "category": block.get("category"),
            "aggregation": block.get("aggregation"),
        }
        if "by_endpoint" in block and block["by_endpoint"]:
            for eid, sub in block["by_endpoint"].items():
                yield (key, eid, sub, parent_meta)
        else:
            yield (key, None, block, parent_meta)


def _select_top_axes(
    axes: List[Tuple[str, Optional[str], dict, dict]],
    top_n: int,
) -> List[Tuple[str, Optional[str], dict, dict]]:
    def rank_key(item):
        r = item[2].get("significance", {}).get("rank")
        return r if r is not None else 10**9
    return sorted(axes, key=rank_key)[:top_n]


def _render_metrics_block(
    axes: List[Tuple[str, Optional[str], dict, dict]]
) -> str:
    lines = []
    for key, eid, block, meta in axes:
        rank = block.get("significance", {}).get("rank", "?")
        score = block.get("significance", {}).get("score", 0.0) or 0.0
        unit = meta.get("unit") or ""
        hiw = meta.get("higher_is_worse")
        ep_suffix = f" [endpoint={eid}]" if eid is not None else ""
        direction = "higher=worse" if hiw else ("lower=worse" if hiw is False else "direction unknown")

        lines.append(
            f"  #{rank}  {key}{ep_suffix}  ({unit}, {direction}, significance={score:.2f})"
        )
        for v in block.get("values", []):
            lines.append(f"        cycle {v['cycle_id']}: {_fmt_value(v.get('value'))}")
        for c in block.get("comparisons", []):
            pct = c.get("pct_change")
            cls = c.get("classification") or "n/a"
            if pct is None:
                lines.append(f"        vs baseline (cycle {c['cycle_id']}): no data [{cls}]")
            else:
                lines.append(
                    f"        vs baseline (cycle {c['cycle_id']}): {pct:+.1f}% [{cls}]"
                )
        tc = block.get("threshold_check")
        if tc is not None:
            spec = tc.get("threshold") or {}
            spec_bits = []
            if spec.get("min") is not None:
                spec_bits.append(f"min={_fmt_value(spec['min'])}")
            if spec.get("max") is not None:
                spec_bits.append(f"max={_fmt_value(spec['max'])}")
            if spec.get("target") is not None:
                spec_bits.append(f"target={_fmt_value(spec['target'])}")
            spec_str = ", ".join(spec_bits) or "no bounds"
            cls = tc.get("classification") or "n/a"
            v = tc.get("violation")
            if v:
                pct = v.get("exceeded_by_pct")
                pct_str = f"{pct:+.1f}%" if pct is not None else "n/a%"
                lines.append(
                    f"        threshold [{spec_str}] -> {cls.upper()}: "
                    f"{v.get('kind')} limit={_fmt_value(v.get('limit'))}, "
                    f"over by {_fmt_value(v.get('exceeded_by'))} ({pct_str})"
                )
            else:
                lines.append(f"        threshold [{spec_str}] -> {cls}")
        cross = block.get("cross_cycle_stats")
        if cross:
            slope = cross.get("trend_slope_per_cycle", 0)
            cv = cross.get("cv")
            cv_text = f"cv={cv:.2f}" if cv is not None else "cv=n/a"
            lines.append(
                f"        trend slope/cycle: {slope:+.4f}  {cv_text}"
            )
    return "\n".join(lines)


def _fmt_value(v) -> str:
    if v is None:
        return "null"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if v == 0:
        return "0"
    if abs(v) >= 1e6 or abs(v) < 1e-3:
        return f"{v:.3e}"
    return f"{v:.4g}"


# --------------------------------------------------------------------------- #
# Fallback templated summary
# --------------------------------------------------------------------------- #

def _fallback_summary(report: dict, top_n: int) -> str:
    mode = report.get("mode", "baseline")
    cycles = report.get("cycles", [])
    n_cycles = len(cycles)
    baseline_id = report.get("baseline_cycle_id")

    all_axes = list(_iter_axes_with_meta(report))
    top_axes = _select_top_axes(all_axes, top_n)

    if mode == "threshold":
        return _fallback_threshold_summary(report, cycles, all_axes, top_axes)

    regs = report.get("regression_count", 0)
    imps = report.get("improvement_count", 0)
    unch = report.get("unchanged_count", 0)

    if n_cycles == 1:
        c = cycles[0]
        out = [f"## Cycle {c['cycle_id']} profile"]
        out.append(f"- Duration: {(c.get('duration_seconds') or 0):.0f}s")
        out.append("")
        out.append("### Top metric values")
        for key, eid, block, meta in top_axes[:5]:
            values = block.get("values", [])
            if not values:
                continue
            ep = f" [endpoint={eid}]" if eid is not None else ""
            unit = meta.get("unit") or ""
            out.append(f"- **{key}**{ep}: {_fmt_value(values[0].get('value'))} {unit}".rstrip())
        return "\n".join(out)

    out = [
        f"## Cycle comparison (baseline = cycle {baseline_id})",
        f"- {regs} regression(s), {imps} improvement(s), {unch} unchanged across {len(all_axes)} metric axes",
        "",
    ]

    regression_lines: List[str] = []
    for key, eid, block, meta in top_axes:
        for c in block.get("comparisons", []):
            if c.get("classification") != "regressed":
                continue
            ep = f" [endpoint={eid}]" if eid is not None else ""
            pct = c.get("pct_change", 0) or 0
            unit = meta.get("unit") or ""
            regression_lines.append(
                f"- **{key}**{ep} vs cycle {c['cycle_id']}: {pct:+.1f}% ({unit})".rstrip()
            )
            if len(regression_lines) >= 5:
                break
        if len(regression_lines) >= 5:
            break

    if regression_lines:
        out.append("### Top regressions")
        out.extend(regression_lines)
    else:
        out.append("_No metrics regressed beyond threshold._")

    out.append("")
    out.append("_LLM unavailable — this is a deterministic summary._")
    return "\n".join(out)


def _fallback_threshold_summary(report, cycles, all_axes, top_axes) -> str:
    cycle_id = cycles[0]["cycle_id"] if cycles else "?"
    viol = report.get("violation_count", 0)
    ok = report.get("ok_count", 0)
    none_set = report.get("no_threshold_count", 0)

    out = [
        f"## Cycle {cycle_id} vs thresholds",
        f"- {viol} violation(s), {ok} within bounds, {none_set} without a threshold ({len(all_axes)} axes total)",
        "",
    ]

    violation_lines: List[str] = []
    for key, eid, block, meta in top_axes:
        tc = block.get("threshold_check")
        if not tc or tc.get("classification") != "violated":
            continue
        ep = f" [endpoint={eid}]" if eid is not None else ""
        v = tc.get("violation") or {}
        kind = v.get("kind", "?")
        limit = _fmt_value(v.get("limit"))
        val = _fmt_value(tc.get("value"))
        pct = v.get("exceeded_by_pct")
        pct_str = f" ({pct:+.1f}%)" if pct is not None else ""
        unit = meta.get("unit") or ""
        violation_lines.append(
            f"- **{key}**{ep}: {val} {unit} — {kind.replace('_', ' ')} of {limit}{pct_str}".rstrip()
        )
        if len(violation_lines) >= 6:
            break

    if violation_lines:
        out.append("### Violations")
        out.extend(violation_lines)
    else:
        out.append("_All metrics passed their configured thresholds._")

    out.append("")
    out.append("_LLM unavailable — this is a deterministic summary._")
    return "\n".join(out)
