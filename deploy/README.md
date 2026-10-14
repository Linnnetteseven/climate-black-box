# Deploying to Oracle Cloud

One Always Free Ampere A1 instance in Frankfurt, running the web app, the API
and nginx under Docker Compose, talking to the same Autonomous Database the
local stack uses.

The instance is disposable. Nothing is stored on it except credentials — all
evidence lives in Autonomous Database and on CKB testnet — so if it is lost,
rebuild it and nothing is gone.

---

## 1. Create the instance (OCI console, ~5 minutes)

**Compute → Instances → Create Instance**

| Setting | Value |
|---|---|
| Name | `climate-black-box` |
| Image | Canonical Ubuntu 22.04 |
| Shape | **VM.Standard.A1.Flex**, 2 OCPU, 12 GB *(Always Free)* |
| Networking | See below — the defaults are not enough |
| SSH keys | Generate a key pair and **download the private key** |

### Networking, in detail

Two settings here decide whether the instance is reachable at all, and neither
announces itself if you get it wrong.

**Primary network.** On a fresh tenancy pick **Create new virtual cloud
network** — OCI builds the VCN, an internet gateway and the route rule in one
step. With an existing VCN, select it instead.

**Subnet.** It must be **public**. A private subnet has no route to the
internet: the instance builds fine and is then unreachable, with nothing in the
console flagging it.

**Assign a public IPv4 address: yes.** Easy to miss, and it cannot be added
afterwards without detaching the VNIC.

**SSH keys.** Choose *Generate a key pair for me* and save **both** keys before
leaving the page. Oracle generates the private key in your browser and never
stores it — skip the download and the only fix is rebuilding the instance.

```bash
mkdir -p ~/.ssh && mv ~/Downloads/ssh-key-*.key ~/.ssh/cbb-oracle.key
chmod 600 ~/.ssh/cbb-oracle.key
```

**Storage.** Defaults are fine; images and build cache come to roughly 6 GB of
the 47 GB boot volume.

Note the public IP when it finishes provisioning.

## 2. Open the ports

The default security list only allows SSH.

**Networking → Virtual Cloud Networks →** your VCN **→ Subnets →** your subnet
**→** its Security List **→ Add Ingress Rules**, twice (leave *Stateless*
unchecked):

| Source CIDR | Protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

Leave *Source Port Range* blank. *Stateless* must stay unchecked: a stateful
rule allows the return traffic automatically, while a stateless one needs a
matching egress rule or replies are dropped and the connection hangs.

Ubuntu also ships iptables rules that drop these. On the instance:

Look before you edit — the rule numbering is not guaranteed:

```bash
sudo iptables -L INPUT --line-numbers -n
```

The list ends in a catch-all `REJECT ... icmp-host-prohibited`. The new rules
have to go *above* it or they are never reached. Substitute its line number
for the `6` below (it usually is 6 on Oracle's Ubuntu image):

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo iptables -L INPUT --line-numbers -n     # confirm both sit above REJECT
sudo netfilter-persistent save
```

If `netfilter-persistent` is missing, `sudo apt install -y iptables-persistent`
installs it and offers to save the current rules.

Forgetting this is the single most common reason a correctly configured OCI
instance appears unreachable.

To tell the failures apart, run `curl -I --max-time 10 http://<public-ip>` from
your laptop:

| Result | Meaning |
|---|---|
| `Connection timed out` | The security list rules did not take |
| `Connection refused` | Both firewalls are open; nothing is listening yet — **expected until step 5** |
| `HTTP/1.1 ...` | Something is already serving |

## 3. Install Docker

```bash
ssh -i /path/to/key ubuntu@<public-ip>
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker ubuntu && exit
```

Log back in so the group membership applies.

## 4. Get the code and the secrets onto it

```bash
ssh -i /path/to/key ubuntu@<public-ip> 'git clone https://github.com/Linnnetteseven/climate-black-box.git'
```

The three things git does not carry, because none of them belong in a
repository:

```bash
# from your workstation
scp -i /path/to/key -r ~/oracle/cbb-wallet  ubuntu@<ip>:~/wallet
scp -i /path/to/key -r ~/.oci              ubuntu@<ip>:~/oci
scp -i /path/to/key .env                   ubuntu@<ip>:~/climate-black-box/.env
```

**Strip the signing key first.** The API only ever *verifies* against CKB,
which is a read-only RPC call. Anchoring runs from your workstation, so the
instance has no use for the key — and a public box should not hold one:

```bash
sed -i '/^CKB_SIGNER_PRIVATE_KEY=/d' ~/climate-black-box/.env
```

Compose already overrides `TNS_ADMIN`, `OCI_CONFIG_FILE` and `ORACLE_MODE`
with the paths inside the container, so you do not have to edit `.env` for
those. One thing it cannot fix for you is the key path *inside* the OCI config,
because that file names it absolutely:

```bash
sed -i 's|^key_file=.*|key_file=/secrets/oci/oci_api_key.pem|' ~/oci/config
chmod 600 ~/climate-black-box/.env
```

Check the key filename matches what is actually in `~/oci/` first.

## 5. Bring it up

Compose reads `deploy/.env` for variable substitution, so write the paths there
once rather than exporting them. Exports die with the shell, and the next SSH
session fails with `required variable CBB_WALLET_DIR is missing a value` on
every compose command — including ones that have nothing to do with the API.

```bash
cd ~/climate-black-box/deploy
cat > .env <<'ENV'
CBB_WALLET_DIR=/home/ubuntu/wallet
CBB_OCI_DIR=/home/ubuntu/oci
CBB_DOMAIN=example.com
CBB_EMAIL=you@example.com
ENV
docker compose -f docker-compose.prod.yml up -d --build
```

`deploy/.env` is gitignored. The domain and email are only read by the certbot
service in step 6; leave the placeholders if you are not setting up TLS.

First build takes 5–10 minutes on 2 OCPUs. Then:

```bash
docker compose -f docker-compose.prod.yml ps
curl -s localhost/api/health
```

You want `{"status":"ok","backend":"Oracle Autonomous Database"}`.

Visit `http://<public-ip>/` — that is your shareable link.

## 6. HTTPS (optional, needs a domain)

Without a domain the plain IP over HTTP works fine for a demo — but say that
out loud rather than letting anyone assume the link is encrypted. Let's Encrypt
will not issue a certificate for a bare IP, so this step needs a hostname.

With a domain's A record pointed at the instance:

With `CBB_DOMAIN` and `CBB_EMAIL` already in `deploy/.env` from step 5:

```bash
cd ~/climate-black-box/deploy
docker compose -f docker-compose.prod.yml run --rm certbot
```

Let's Encrypt allows five certificates per domain per week, so if a run is
interrupted check before retrying:

```bash
docker compose -f docker-compose.prod.yml run --rm --entrypoint "certbot certificates" certbot
```

The `certbot` service sits behind a profile, so it never starts with the rest
of the stack — it runs once, writes into the volumes nginx already mounts, and
exits. Then switch nginx to the TLS config:

```bash
sed -i "s|CBB_DOMAIN|$CBB_DOMAIN|g" nginx-tls.conf
sed -i 's|./nginx.conf:|./nginx-tls.conf:|' docker-compose.prod.yml
docker compose -f docker-compose.prod.yml up -d --force-recreate nginx
docker compose -f docker-compose.prod.yml logs --tail 20 nginx
```

A bare `up -d nginx` can decide the service is unchanged and skip the restart,
since only a mounted file moved — hence `--force-recreate`.

Renew with the same `run --rm certbot` command plus `docker compose ... restart
nginx`; certificates last 90 days, which outlives any hackathon.

---

## Updating after a change

```bash
cd ~/climate-black-box && git pull
cd deploy && docker compose -f docker-compose.prod.yml up -d --build
```

## What is exposed

The instance holds the Autonomous Database credentials and an OCI API key. It
does **not** hold the CKB signing key, so nothing on it can write to the chain.

The API has no authentication. Anyone with the URL can read every endpoint and
record an intervention — which the database forces to `simulated`, so the worst
case is a spurious row in the demo timeline. Regenerating an AI investigation
is gated behind `API_SHARED_KEY`, sent as an `X-API-Key` header — a header
rather than a query parameter because nginx logs full request lines. That gate
is what stops a public URL from being a public spend button on your tenancy.

Set a fresh `API_SHARED_KEY` on the instance rather than reusing the local one:

```bash
sed -i "s|^API_SHARED_KEY=.*|API_SHARED_KEY=$(openssl rand -hex 24)|" ~/climate-black-box/.env
```

If the link goes anywhere beyond the judges, put basic auth in front of it:

```nginx
location / {
    auth_basic           "Climate Black Box";
    auth_basic_user_file /etc/nginx/.htpasswd;
    # ... existing proxy_pass ...
}
```

## If something fails

| Symptom | Cause |
|---|---|
| Site unreachable, instance running | iptables rules in step 2 |
| `api` unhealthy, `ORA-12506` | wallet not mounted, or `TNS_ADMIN` still points at a laptop path |
| `api` unhealthy, `ORA-01017` | wrong `ADB_PASSWORD` in `.env` |
| Investigation shows `fallback` | OCI config or key path wrong inside the container |
| Verify returns `chain_unavailable` | the instance cannot reach `testnet.ckb.dev`; check egress |

| Compose refuses every command with `CBB_WALLET_DIR is missing` | `deploy/.env` not written — see step 5 |
| SSH session freezes mid-command | the client connection, not the instance; press Enter then `~.`, and reconnect with `-o ServerAliveInterval=30` |

Logs: `docker compose -f docker-compose.prod.yml logs -f api`

A free hostname (DuckDNS, FreeDNS) is enough for a real certificate — Let's
Encrypt will not issue for a bare IP, and a demo about trustworthy records
should not be served over plain HTTP with a browser warning next to it.

---

## What was verified before writing this

The whole stack was built and run locally against the real Autonomous Database
and CKB testnet, not just assembled:

| Checked | Result |
|---|---|
| All 29 Python deps resolve to prebuilt **aarch64** wheels | no source builds on Ampere |
| API container → Autonomous Database | `{"status":"ok","backend":"Oracle Autonomous Database"}` |
| `verify` on a real anchored event, from inside the container | `verified: true`, hashes match |
| `tamper-check` | `state: modified`, recomputed hash diverges |
| Live Llama 3.3 70B through the mounted OCI config | `simulation_status: real`, 10.4s |
| Refresh gate with no key / wrong key / right key | model called only on the third |
| Server-rendered page through nginx | 123 KB, real project and alert data in the HTML |
| Imagery and audio caching | single `immutable` header |

Two bugs surfaced in that pass and are fixed here: the build context was 1.5 GB
and pnpm's symlinked `node_modules` collided with the install inside the image
(hence `.dockerignore`, now 25 MB), and nginx was emitting two `Cache-Control`
headers because `add_header` appends rather than replaces.
