-- Page 1, "Sites under monitoring" Cards region.
--
-- One row per project with the three numbers an operator actually opens the
-- page for. latest_ndvi takes the newest period that has a value, so a month
-- excluded for cloud cover does not blank the card.
--
-- Wrapped in an outer SELECT only so alert_class can test open_alerts: it is a
-- scalar subquery, and Oracle will not let an alias be referenced from the
-- same SELECT list that defines it.
SELECT project_id,
       project_name,
       region,
       periods,
       latest_ndvi,
       open_alerts,
       -- The page exists to surface the one site that is diverging. A green
       -- rail on all three tiles says "all well" at a glance, which is the
       -- opposite of what this card means when the count is 1.
       CASE WHEN open_alerts > 0 THEN 'cbb-kpi is-alert' ELSE 'cbb-kpi' END
         AS alert_class
  FROM (SELECT p.id    AS project_id,
               p.name  AS project_name,
               p.region AS region,
               COUNT(DISTINCT CASE WHEN o.metric = 'ndvi_mean'
                                   THEN o.period_key END)       AS periods,
               -- FM0.0000 keeps the leading zero. Oracle's default drops it,
               -- and ".4668" beside "45" reads as a broken number.
               TO_CHAR(ROUND(MAX(CASE WHEN o.metric = 'ndvi_mean'
                               AND o.period_key = (SELECT MAX(period_key)
                                                     FROM observations
                                                    WHERE project_id = p.id
                                                      AND metric     = 'ndvi_mean'
                                                      AND value IS NOT NULL)
                              THEN o.value END), 4), 'FM0.0000') AS latest_ndvi,
               (SELECT COUNT(*) FROM alerts a
                 WHERE a.project_id = p.id
                   AND a.status     = 'open')                   AS open_alerts
          FROM projects p
          LEFT JOIN observations o ON o.project_id = p.id
         GROUP BY p.id, p.name, p.region)
 ORDER BY open_alerts DESC, project_id
