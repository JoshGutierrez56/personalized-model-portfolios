-- Independent window-function reconstruction from the saved daily ledger.
WITH d AS (
 SELECT *, COALESCE(LAG(nav) OVER (PARTITION BY client,method ORDER BY date), ?) AS prior_nav
 FROM daily
)
SELECT COUNT(*) AS row_count,
 MAX(ABS(d.net_return-(d.nav/d.prior_nav-1))) AS nav_return_error,
 MAX(ABS(d.gross_return-d.net_return-d.cost_dollars/d.prior_nav)) AS cost_return_error,
 MAX(ABS(d.gross_active_return-(d.gross_return-b.benchmark_return))) AS gross_active_error,
 MAX(ABS(d.net_active_return-(d.net_return-b.benchmark_return))) AS net_active_error,
 MAX(ABS(d.benchmark_return-b.benchmark_return)) AS benchmark_error,
 SUM(CASE WHEN b.date IS NULL THEN 1 ELSE 0 END) AS missing_benchmark_count
FROM d LEFT JOIN benchmark b ON d.date=b.date;
