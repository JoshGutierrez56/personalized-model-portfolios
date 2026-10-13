"""Presentation metadata for validation residuals; never alters pass/fail logic.

Units are explicit, not inferred from a tolerance's magnitude. An unknown check
fails report generation so a new residual cannot silently inherit the wrong unit.
"""

USD = {
    "sql_funding_error", "sql_signed_trade_error", "sql_position_error",
    "sql_fee_error", "sql_daily_nav_error", "sql_daily_fee_error",
    "benchmark_nav_reconstruction", "trade_preholdings_reconstruction",
    "trade_postholdings_reconstruction", "trade_cost_formula",
    "trade_self_financing", "daily_fee_reconstruction", "daily_nav_reconstruction",
}
RETURNS = {
    "sql_nav_return_error", "sql_cost_return_error", "sql_gross_active_error",
    "sql_net_active_error", "sql_benchmark_error", "benchmark_return_reconstruction",
    "daily_asset_gross_identity", "daily_net_contribution_identity",
    "daily_active_contribution_identity", "daily_gross_reconciliation",
    "daily_net_reconciliation", "daily_benchmark_reconciliation",
    "daily_gross_active_reconciliation", "daily_net_active_reconciliation",
    "multiperiod_portfolio_linking", "multiperiod_benchmark_linking",
    "multiperiod_active_linking",
}
WEIGHTS = {
    "decision_full_investment", "decision_constraint_bounds",
    "posttrade_decision_weights", "posttrade_constraints", "daily_drift_reconciliation",
}
ANNUAL_TE = {
    "risk_te_reconciliation", "risk_te_budget", "risk_minimum_reference",
    "risk_budget_definition",
}
FRACTIONS = {"risk_shrinkage_reconciliation", "daily_cost_fraction", "daily_traded_fraction"}
ROWS = {"sql_missing_join_count", "sql_missing_benchmark_count"}
FLAGS = {
    "override_keys", "contract_valid", "private_output_boundary",
    "required_run_provenance", "executed_configuration_drift",
    "required_source_provenance", "source_manifest_schema", "calendar_boundary",
    "source_ticker_roster", "source_calendar_complete", "source_return_domain",
    "source_identity_stable", "nonempty_evaluation", "positive_saved_nav",
    "nonnegative_saved_fees", "rebalance_flag_domain", "risk_history_sufficient",
    "risk_covariance_psd", "decision_chronology", "decision_risk_window",
    "trade_chronology", "rebalance_schedule", "reconstructed_positive_nav",
    "validator_execution",
}
FLAG_PREFIXES = (
    "production_contract_drift_", "cached_source_hash_", "schema_", "nonnull_keys_",
    "unique_keys_", "valid_dates_", "real_numeric_", "finite_", "source_flag_",
    "complete_roster_",
)
GOVERNANCE = {
    "override_keys", "contract_valid", "private_output_boundary",
    "required_run_provenance", "executed_configuration_drift",
    "required_source_provenance", "source_manifest_schema", "validator_execution",
}
CATEGORY_LABELS = {
    "accounting": "Reconciliation and accounting",
    "risk": "Risk and constraints",
    "data": "Data and chronology",
    "governance": "Configuration and provenance",
}


def describe_control(control_id: str) -> dict[str, str]:
    """Return one complete category and the residual/tolerance unit."""
    if control_id in USD:
        unit = "USD"
    elif control_id in RETURNS:
        unit = "return fraction"
    elif control_id in WEIGHTS:
        unit = "weight fraction"
    elif control_id in ANNUAL_TE:
        unit = "annual TE fraction"
    elif control_id in FRACTIONS:
        unit = "fraction"
    elif control_id in ROWS:
        unit = "rows"
    elif control_id in FLAGS or control_id.startswith(FLAG_PREFIXES):
        unit = "flag (0/1)"
    else:
        raise ValueError(f"No reviewed residual unit for control: {control_id}")

    if control_id in GOVERNANCE or control_id.startswith(("production_contract_drift_", "cached_source_hash_")):
        category = "governance"
    elif control_id.startswith("risk_") or control_id in WEIGHTS:
        category = "risk"
    elif control_id in USD | RETURNS | FRACTIONS | ROWS or control_id in {
        "positive_saved_nav", "nonnegative_saved_fees", "reconstructed_positive_nav",
    }:
        category = "accounting"
    else:
        category = "data"
    return {"unit": unit, "category": category, "category_label": CATEGORY_LABELS[category]}
