-- Independent SQL arithmetic over saved records; no Python reconstruction inputs.
WITH t AS (
 SELECT date, client, method, COUNT(*) AS asset_count,
   SUM(pretrade_dollars) AS pre_nav, SUM(posttrade_dollars) AS post_nav,
   SUM(trade_dollars) AS signed_trades, SUM(cost_dollars) AS fees,
   MAX(ABS(posttrade_dollars-pretrade_dollars-trade_dollars)) AS position_error,
   MAX(ABS(cost_dollars-ABS(trade_dollars)*?)) AS fee_error
 FROM trades GROUP BY date, client, method
)
SELECT COUNT(*) AS row_count,
 COALESCE(MAX(ABS(t.pre_nav-t.post_nav-t.fees)),0) AS funding_error,
 COALESCE(MAX(ABS(t.signed_trades+t.fees)),0) AS signed_trade_error,
 COALESCE(MAX(t.position_error),0) AS position_error,
 COALESCE(MAX(t.fee_error),0) AS fee_error,
 COALESCE(MAX(ABS(t.post_nav-d.nav)),0) AS daily_nav_error,
 COALESCE(MAX(ABS(t.fees-d.cost_dollars)),0) AS daily_fee_error,
 COALESCE(SUM(CASE WHEN d.date IS NULL OR q.execution_date IS NULL THEN 1 ELSE 0 END),0) AS missing_join_count
FROM t
LEFT JOIN daily d ON t.date=d.date AND t.client=d.client AND t.method=d.method
LEFT JOIN decisions q ON t.date=q.execution_date AND t.client=q.client AND t.method=q.method;
