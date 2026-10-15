-- Page 1, "Sites under monitoring" Cards region.
--
-- One row per project with the three numbers an operator actually opens the
-- page for. latest_ndvi takes the newest period that has a value, so a month
-- excluded for cloud cover does not blank the card.
SELECT p.id                                   AS project_id,
       p.name                                 AS project_name,
       p.region                               AS region,
       COUNT(DISTINCT CASE WHEN o.metric = 'ndvi_mean'
                           THEN o.period_key END)                AS periods,
       ROUND(MAX(CASE WHEN o.metric = 'ndvi_mean'
                       AND o.period_key = (SELECT MAX(period_key)
                                             FROM observations
                                            WHERE project_id = p.id
                                              AND metric     = 'ndvi_mean'
                                              AND value IS NOT NULL)
                      THEN o.value END), 4)                      AS latest_ndvi,
       (SELECT COUNT(*) FROM alerts a
         WHERE a.project_id = p.id
           AND a.status     = 'open')                            AS open_alerts
  FROM projects p
  LEFT JOIN observations o ON o.project_id = p.id
 GROUP BY p.id, p.name, p.region
 ORDER BY open_alerts DESC, p.id
