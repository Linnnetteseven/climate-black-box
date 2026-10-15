# APEX assets

APEX stores an application's definition in its own metadata tables, writable
only through the APEX PL/SQL APIs. The `CBB` schema has no grant on
`APEX_UTIL`, `APEX_APPLICATION_INSTALL` or `WWV_FLOW_API`, so the console
cannot be built or restyled from SQL here — it is built in App Builder.

What lives in this directory is the part that *can* be version-controlled: the
CSS, and the queries the regions run. Paste them in once; review them here.

| File | Where it goes in APEX |
|---|---|
| `cbb-theme.css` | Shared Components → Themes → Vita → Edit → CSS → Inline |
| `kpi_cards.sql` | Page 1 → Cards region → Source → SQL Query |

Both travel with `database/apex_exports/climate_black_box_ops.sql` once saved,
so re-export the app after changing them.
