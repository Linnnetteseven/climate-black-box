# Oracle setup — what to do in the console

**Home region: eu-frankfurt-1 (Frankfurt).** Good news: Frankfurt is one of
the regions where OCI Generative AI is available, so the AI beat does not
need a second region or a workaround.

Everything below is done in the OCI console by Linnette. Nothing here needs
the repo. Work top to bottom; each step says what to send back.

> **Never paste a password, private key, wallet file or auth token into chat
> or into the repo.** The things I need back are names, OCIDs and
> hostnames — identifiers, not credentials. Secrets go in your local `.env`,
> which is gitignored.

---

## 1. Autonomous Database (20 minutes, mostly waiting)

1. Console → **Oracle Database → Autonomous Database** → *Create Autonomous
   Database*.
2. Settings:
   - **Display name:** `climate-black-box`
   - **Database name:** `CBB` (no hyphens allowed here)
   - **Workload type:** **Transaction Processing.**

     The console may list these as *Data Lakehouse* (the renamed Data
     Warehouse), *Transaction Processing*, *JSON* and *APEX*.

     **Do not pick APEX.** That workload type has **no SQL*Net connectivity** —
     every interaction must go over HTTPS. Our FastAPI service connects with
     `oracledb` over SQL*Net, so the APEX type would break the repository
     layer, the migration runner and the loader. It is cheaper because it is
     restricted to APEX/ORDS access only.

     Transaction Processing suits our shape: many small reads and writes
     (observations, interventions, audit events, chain anchors) rather than
     large analytical scans. Data Lakehouse would also work but is tuned for a
     problem we do not have — the whole dataset is tens of rows. APEX, ORDS and
     Spatial are all included either way.
   - **Deployment:** Serverless
   - **Always Free:** toggle **ON** if offered. It is enough for this, and it
     protects the $300 from a runaway. If the shape you want is not Always
     Free, 1 ECPU / 20 GB is fine and costs cents.
   - **Database version:** 23ai
   - **Admin password:** set one, save it in your password manager. You will
     need it twice below.
   - **Access type:** *Secure access from everywhere* (mTLS). Simplest for a
     hackathon; the wallet is the credential.
3. Create, and wait until the state is **Available** (3–8 minutes).

**Send me back:** the database name, the region, and whether you ended up on
Always Free. No password.

---

## 2. Wallet (this is how the API connects)

1. On the database page → **Database connection** → *Download wallet*.
2. Set a wallet password (any strong value; save it).
3. Unzip it to a directory **outside the repo**, e.g. `~/oracle/cbb-wallet/`.

```bash
mkdir -p ~/oracle/cbb-wallet
unzip ~/Downloads/Wallet_CBB.zip -d ~/oracle/cbb-wallet
ls ~/oracle/cbb-wallet   # expect: tnsnames.ora sqlnet.ora cwallet.sso ewallet.p12 ...
grep -o '^[a-z_]*' ~/oracle/cbb-wallet/tnsnames.ora | sort -u
```

That last command prints the connection aliases — you want the one ending
`_high` (e.g. `cbb_high`).

**Send me back:** the alias ending in `_high`, and the absolute path you
unzipped to. `.gitignore` already blocks `wallet/` and `Wallet_*.zip`, but
keep it outside the repo anyway.

---

## 3. Database user for the app

Do **not** let the app connect as ADMIN. On the database page → **Database
actions** → *SQL*, signed in as ADMIN, run:

```sql
CREATE USER cbb IDENTIFIED BY "<pick-a-strong-password>";
GRANT CONNECT, RESOURCE TO cbb;
ALTER USER cbb QUOTA UNLIMITED ON DATA;
-- lets us REST-enable the schema for APEX/ORDS later
GRANT CONNECT THROUGH ORDS_PUBLIC_USER TO cbb;
```

Then the GeoRaster check from the plan (30-second version — this decides
whether the stretch goal is even on the table):

```sql
SELECT COUNT(*) AS georaster_objects
FROM all_objects
WHERE object_name LIKE 'SDO_GEOR%';

SELECT COUNT(*) AS spatial_objects
FROM all_objects
WHERE object_name = 'SDO_GEOMETRY';
```

**Send me back:** both counts. `SDO_GEOMETRY` must be > 0 — we store the
project polygon in it. `SDO_GEOR*` decides GeoRaster.

---

## 4. APEX workspace (this is our Oracle proof on stage)

1. Database page → **Tools** tab → **APEX** → *Open APEX*.
2. First time it asks you to create a workspace. Sign in as `ADMIN` with the
   database admin password from step 1.
3. Create workspace:
   - **Workspace name:** `CBB`
   - **Schema:** choose the existing `CBB` schema you just created (do *not*
     let it create a new one — APEX and the API must share one schema, which
     is the entire point of the Oracle proof).
   - **Admin username/password:** your choice.

**Send me back:** the APEX workspace URL (it looks like
`https://<something>.adb.eu-frankfurt-1.oraclecloudapps.com/ords/r/cbb/...`)
and confirmation that the workspace is attached to the `CBB` schema.

---

## 5. OCI Generative AI access

Frankfurt has it. Two things are needed: a compartment and a policy.

1. **Compartment:** Identity → Compartments. Use the root, or create
   `climate-black-box`. Copy its **OCID** (starts `ocid1.compartment...`).
2. **Policy:** Identity → Policies → Create, in the root compartment:

```
Allow group <your-group-name> to manage generative-ai-family in tenancy
```

If you are the tenancy administrator you already have this and can skip the
policy.

3. **API key for the backend:** Profile (top right) → *My profile* → **API
   keys** → *Add API key* → *Generate API key pair* → download the private
   key → **Add**. The console then shows a config snippet. Save it to
   `~/.oci/config` and the key to `~/.oci/oci_api_key.pem`:

```bash
mkdir -p ~/.oci && chmod 700 ~/.oci
# paste the console's config snippet into ~/.oci/config
mv ~/Downloads/*.pem ~/.oci/oci_api_key.pem
chmod 600 ~/.oci/config ~/.oci/oci_api_key.pem
```

Make sure the `key_file=` line in `~/.oci/config` points at that `.pem`.

4. **Check which models the region actually serves** — model IDs change, so
   we read them rather than guess:

```bash
pip install oci
python3 -c "
import oci
cfg = oci.config.from_file()
client = oci.generative_ai.GenerativeAiClient(cfg)
import os
models = client.list_models(compartment_id=os.environ['OCI_COMPARTMENT_ID']).data
for m in models.items:
    if 'CHAT' in (m.capabilities or []):
        print(m.display_name, '|', m.id)
"
```

**Send me back:** the compartment OCID, and the output of that last command
(the chat-capable model names and IDs). Not the private key, not the
fingerprint.

---

## 6. What I do once you send those back

- Point the API at ADB instead of local Oracle — it is one connection string
  plus `TNS_ADMIN`, already wired in `.env.example`.
- Run the migrations against `CBB` so APEX and the API see the same rows.
- Wire the GenAI client to the model ID you found, with the deterministic
  fallback still in place behind it.

---

## 7. If something is blocked

Nothing here is on the critical path for the next few hours. Local Oracle
23ai Free is already the dev target, the schema is identical, and the swap is
a connection string. So: do these steps when you can, tell me what failed,
and keep building. The only item with a real deadline is the GeoRaster count
in step 3, because it decides whether we mention GeoRaster at all.
