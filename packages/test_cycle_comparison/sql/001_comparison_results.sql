-- ---------------------------------------------------------------------------
-- comparison_results — persisted output of the Test Cycle Comparison module.
--
-- There is no Alembic in this project (see AGENTS.md "Database"), so apply
-- this by hand against Supabase:
--     Supabase Dashboard → SQL Editor → paste → Run
--
-- One row per executed comparison. The row holds everything
-- ComparisonResultsPage.tsx renders, so a saved comparison can be replayed
-- verbatim, and the recommendation module can read comparison history
-- without re-querying VictoriaMetrics.
-- ---------------------------------------------------------------------------

create table if not exists public.comparison_results (
    id                        bigserial primary key,

    -- Ownership. user_id is denormalised from applications.user_id so history
    -- can be scoped per user without a join.
    application_id            bigint  not null
                                  references public.applications(id) on delete cascade,
    user_id                   bigint
                                  references public.users(id) on delete set null,

    -- Request shape / how the comparison was run
    mode                      text    not null
                                  check (mode in ('baseline', 'threshold')),
    cycle_ids                 jsonb   not null default '[]'::jsonb,
    baseline_cycle_id         bigint,
    endpoint_ids              jsonb   not null default '[]'::jsonb,
    metric_keys               jsonb   not null default '[]'::jsonb,
    group_by_endpoint         boolean not null default false,
    regression_threshold_pct  double precision,
    thresholds_applied        boolean not null default false,

    -- Headline counters — the chips in the page header
    regression_count          integer not null default 0,
    improvement_count         integer not null default 0,
    unchanged_count           integer not null default 0,
    violation_count           integer not null default 0,
    ok_count                  integer not null default 0,
    no_threshold_count        integer not null default 0,
    metric_count              integer not null default 0,
    missing_metric_keys       jsonb   not null default '[]'::jsonb,

    -- The "AI Analysis" card
    summary_text              text,
    summary_source            text,       -- 'llm' | 'fallback'
    summary_model             text,
    summary_error             text,

    -- Most significant metric of the run — lets the recommendation module
    -- trend "what regressed most" over time without opening the jsonb.
    top_metric_key            text,
    top_metric_significance   double precision,

    -- Full payloads.
    --   report  = the exact POST /compare response body
    --   display = cycle labels/status, metric metadata and the flattened
    --             metric-breakdown rows exactly as the page renders them
    report                    jsonb   not null,
    display                   jsonb   not null,

    created_at                timestamptz not null default now()
);

-- History listing: newest comparisons for one application.
create index if not exists idx_comparison_results_app_created
    on public.comparison_results (application_id, created_at desc);

-- History listing scoped to a user (dashboard / chatbot).
create index if not exists idx_comparison_results_user_created
    on public.comparison_results (user_id, created_at desc);

-- "Which comparisons involved cycle 68?"  →  cycle_ids @> '68'::jsonb
create index if not exists idx_comparison_results_cycle_ids
    on public.comparison_results using gin (cycle_ids jsonb_path_ops);

-- "Which comparisons covered probe_duration_seconds?"
create index if not exists idx_comparison_results_metric_keys
    on public.comparison_results using gin (metric_keys jsonb_path_ops);

comment on table public.comparison_results is
    'Persisted Test Cycle Comparison reports. report = raw /compare response; display = page-render payload.';

-- ---------------------------------------------------------------------------
-- RLS is intentionally left OFF to match the other service-written tables
-- (anomalies, ml_model_metrics). The comparison service authenticates to
-- Supabase with the project key and enforces ownership in application code.
-- If you later turn RLS on project-wide, add a policy keyed on user_id.
-- ---------------------------------------------------------------------------
