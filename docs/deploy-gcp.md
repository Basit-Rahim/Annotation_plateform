# Deploying to Google Cloud (Compute Engine)

A runbook for the person (or browser agent) doing the deployment. It uses only the Google Cloud Console and its
**SSH-in-browser** window, so no local tools are needed.

**What gets deployed:** one Compute Engine VM running `docker-compose.prod.yml`. Caddy serves the app over HTTPS
and gets its certificate from Let's Encrypt automatically. Postgres, the API and a nightly backup job run beside it
on the same VM and are not reachable from the internet.

Why a VM and not Cloud Run or GKE: the app stores audio on local disk, reads a drop folder, and runs a scheduled
lease-expiry job inside the API. All of that assumes one long-lived server.

---

## 0. Values to decide before starting

Fill these in first. The deployment needs every one of them.

| Placeholder | Meaning | Example |
| --- | --- | --- |
| `<PROJECT_ID>` | GCP project to deploy into (billing enabled) | `dare-rc-annotation` |
| `<REGION>` / `<ZONE>` | Where the VM and its data live. **This is a data-protection decision:** the disk holds children's voice recordings. Confirm with the research team / IRB. | `me-central1` / `me-central1-a` (Doha), or `asia-south1` / `asia-south1-a` (Mumbai) |
| `<DOMAIN>` | Hostname for the app. You must be able to add a DNS A record for it. | `annotate.dare-rc.lums.edu.pk` |
| `<ADMIN_EMAIL>` | Admin login for the app | `admin@dare-rc.lums.edu.pk` |

No domain yet? For a pilot you can use `<IP-with-dashes>.sslip.io` (for example `34-18-1-25.sslip.io`).
It resolves to the VM's IP with no DNS setup, and Let's Encrypt will issue a certificate for it.
Switch to a real domain before the study starts.

---

## 1. Create the VM

Console → **Compute Engine → VM instances → Create instance**. The Compute Engine API must be enabled; the Console offers to enable it.

| Setting | Value |
| --- | --- |
| Name | `annotation-prod` |
| Region / Zone | `<REGION>` / `<ZONE>` |
| Machine type | `e2-medium` (2 vCPU, 4 GB) |
| Boot disk | **Ubuntu 24.04 LTS** (x86/64), **Balanced persistent disk, 50 GB**. About 1 MB per 60-second recording, plus 14 days of backups. |
| Firewall | Tick **Allow HTTP traffic** and **Allow HTTPS traffic** |

Leave everything else at the defaults. Click **Create**.

## 2. Give the VM a static IP

Console → **VPC network → IP addresses**. Find the VM's external IP and click **Promote to static IP address**.
Name it `annotation-prod-ip`. Note the IP as `<VM_IP>`.

## 3. Point the domain at it

At the DNS provider for `<DOMAIN>`, create an **A record** for `<DOMAIN>` pointing at `<VM_IP>`.
(Skip this if you use `sslip.io`.)

Wait until it resolves before step 6. You can check from the VM later with `getent hosts <DOMAIN>`, which must print `<VM_IP>`.

## 4. Install Docker

Console → VM instances → `annotation-prod` → **SSH**. This opens the browser terminal; run every command below there.

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo docker version && sudo docker compose version
```

Both commands must print version information.

## 5. Get the code and create `.env`

```bash
sudo git clone https://github.com/Basit-Rahim/Annotation_plateform.git /opt/annotation
cd /opt/annotation
sudo cp .env.example .env
```

Generate the secrets **on the VM** and write them into `.env`. Replace `<DOMAIN>` and `<ADMIN_EMAIL>` before running.

```bash
DB_PW=$(openssl rand -hex 24)
SK=$(openssl rand -hex 32)
ADMIN_PW=$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)
sudo sed -i \
  -e "s/CHANGE_ME_strong_db_password/$DB_PW/g" \
  -e "s/CHANGE_ME_openssl_rand_hex_32/$SK/" \
  -e "s/CHANGE_ME_strong_admin_password/$ADMIN_PW/" \
  -e "s/^ENVIRONMENT=.*/ENVIRONMENT=production/" \
  -e "s/^DOMAIN=.*/DOMAIN=<DOMAIN>/" \
  -e "s/^ADMIN_EMAIL=.*/ADMIN_EMAIL=<ADMIN_EMAIL>/" \
  .env
sudo chmod 600 .env
grep -v '^#' .env | grep -c CHANGE_ME     # must print 0
grep -E '^(DOMAIN|ADMIN_EMAIL|ENVIRONMENT)=' .env
echo "ADMIN PASSWORD (give to the project owner, then clear the screen): $ADMIN_PW"
```

The `/g` on the first substitution matters: the database password appears twice, in `POSTGRES_PASSWORD` and inside `DATABASE_URL`.

The API refuses to start in production while any secret is still a placeholder or too short.
If that happens, `docker compose ... logs api` shows a line starting `Production .env is not configured` naming the variable to fix.

## 6. Start the stack

```bash
cd /opt/annotation
sudo docker compose -f docker-compose.prod.yml up -d --build
sudo docker compose -f docker-compose.prod.yml ps
```

The first build takes a few minutes. Wait until `ps` shows `postgres` and `api` **healthy**, and `web` and `backup` **running**.

Always pass `-f docker-compose.prod.yml`. The plain `docker-compose.yml` is the development stack: it publishes Postgres and the API to the internet and runs dev servers.

## 7. Verify

```bash
curl -s https://<DOMAIN>/api/health                         # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" http://<DOMAIN>/  # 308 (redirect to HTTPS)
sudo docker compose -f docker-compose.prod.yml logs --tail 50 api web
sudo docker compose -f docker-compose.prod.yml logs backup   # "db-... written", "audio-... written"
```

Then in a browser:

1. `https://<DOMAIN>` shows the login page with a valid padlock (no certificate warning).
2. Log in with `<ADMIN_EMAIL>` and the generated admin password. The Dashboard loads.
3. Confirm the Urdu line on the login page renders in Nastaliq script.

If the certificate fails, it is almost always DNS or the firewall. Check that `getent hosts <DOMAIN>` matches `<VM_IP>`,
that the HTTP/HTTPS boxes were ticked, then look at `logs web`. Caddy retries on its own, so restarting is not needed.

## 8. Off-server backups (disk snapshots)

The backup service keeps 14 days of database dumps and audio archives in `/opt/annotation/backups`, but those are on the same disk.
Add daily snapshots so a lost VM or disk is recoverable.

Console → **Compute Engine → Snapshots → Snapshot schedules → Create**:

- Name `annotation-daily`, region `<REGION>`
- Daily, start time 02:00
- Delete snapshots older than 14 days
- Snapshot storage location: **regional, `<REGION>`** (same data-residency reason as step 0)

Then go to **Compute Engine → Disks → `annotation-prod`** → **Edit**, set Snapshot schedule `annotation-daily`, and **Save**.

## 9. Hand-over notes for the admin

- **Adding audio:** in the VM's SSH window, use the gear menu, then **Upload file** (files land in the home folder). Then run:
  ```bash
  sudo mv ~/*.wav ~/*.mp3 /opt/annotation/data/incoming/ 2>/dev/null; ls /opt/annotation/data/incoming
  ```
  Then use **Ingest audio → Scan folder** in the app.
- **Updating to a new version:**
  ```bash
  cd /opt/annotation && sudo git pull && sudo docker compose -f docker-compose.prod.yml up -d --build
  ```
  Migrations run automatically on start.
- **Logs:** `sudo docker compose -f docker-compose.prod.yml logs -f api`
- **Restoring the database from a dump:** see "Backups" in the README.
- **Changing the admin password:** the admin account is created only once, from `.env`. Editing `ADMIN_PASSWORD` later has no effect on an existing account.

## Do not

- Do not run `docker compose ... down -v`. It deletes the database volume.
- Do not open ports 5432 or 8000 in the firewall, and do not start `docker-compose.yml` (the dev stack) on the server.
- Do not commit `.env` or paste its contents into GitHub, chat, tickets or documents. The admin password goes only to the project owner.
- Do not delete `/opt/annotation/data` or `/opt/annotation/backups`. That is where the recordings are kept.
