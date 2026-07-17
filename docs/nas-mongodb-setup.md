# MongoDB on Synology DS925+ (pa-voice-mvp)

Local-first setup: **MongoDB Community Edition** in Docker (Container Manager) on the NAS.
The FastAPI app runs on your Windows dev machine and connects over the LAN.

**Out of scope for Phase 1:** Atlas, replica sets, native `$vectorSearch` (embeddings stay in documents; ranking is in Python).

## Architecture

```
Windows Dev  (C:\Users\...\pa-voice-mvp)
  uvicorn + Motor
       |
       |  MONGODB_URI = mongodb://USER:PASS@NAS_IP:27017/?authSource=admin
       v
Synology DS925+
  Container Manager  ->  pa-mongo (mongo:8.0)
       |
       v
  /volume1/docker/pa-mongo/data  ->  /data/db
```

## Prerequisites

- DSM with **Container Manager** installed
- Shared folder for Docker data (usually `docker` on `volume1`)
- NAS LAN IP known (static IP or DHCP reservation recommended)
- Dev PC on the same LAN

## 1. Folders on the NAS

In **File Station**, create:

| Path | Purpose |
|------|---------|
| `/volume1/docker/pa-mongo/` | Compose project root |
| `/volume1/docker/pa-mongo/data` | MongoDB data (bind mount) |

If the container fails with permission errors on `/data/db`, ensure the folder is writable by Docker (Mongo often runs as UID 999). Prefer fixing ownership/ACLs over world-writable `777`.

## 2. Compose file

1. Copy the template from the repo:
   - Source: [`deploy/nas/docker-compose.mongodb.yml`](../deploy/nas/docker-compose.mongodb.yml)
   - Destination on NAS: `/volume1/docker/pa-mongo/docker-compose.yml`
2. Set a **strong** password for `MONGO_INITDB_ROOT_PASSWORD` (only on the NAS copy).
3. Confirm the bind path matches your volume (`/volume1/...`).

**Important:** `MONGO_INITDB_ROOT_USERNAME` / `MONGO_INITDB_ROOT_PASSWORD` are applied only when `/data/db` is **empty** (first start). Changing them later does nothing until you wipe data or create users manually.

### Image pinning

- Template uses `mongo:8.0` (not `latest`).
- After a known-good pull, you may pin a full patch tag (e.g. `mongo:8.0.12`) for reproducibility.
- DS925+ (AMD) supports AVX required by MongoDB 5+.

## 3. Start with Container Manager

1. Open **Container Manager** → **Project** → **Create**.
2. Path: `/volume1/docker/pa-mongo` (folder that contains `docker-compose.yml`).
3. Project name e.g. `pa-mongo`.
4. Create / start and wait until the container is **Running**.
5. Check **Logs**: no crash loop; Mongo should accept connections.

Optional: set restart policy to **unless-stopped** (already in the compose file).

## 4. Firewall / network

- Allow **TCP 27017** only from the **LAN** (DSM Firewall).
- Do **not** forward 27017 to the internet or via QuickConnect.
- Note the NAS IP, e.g. `192.168.1.50`.

## 5. Verify from Windows

PowerShell:

```powershell
Test-NetConnection -ComputerName <NAS_IP> -Port 27017
```

Optional (Compass or `mongosh`):

```
mongodb://pa_admin:<PASSWORD>@<NAS_IP>:27017/?authSource=admin
```

Smoke test in `mongosh`:

```javascript
use jarvis_db
db.working_memory.insertOne({
  user_id: "setup-test",
  text: "hello from nas",
  created_at: new Date()
})
db.working_memory.find()
```

Connection **without** credentials must fail (auth enabled).

### Password special characters

If the password contains `@ : / # ? %` etc., **URL-encode** them in the URI (e.g. `@` → `%40`).

## 6. App `.env` (Windows)

In the project root `.env` (never commit):

```env
MONGODB_URI=mongodb://pa_admin:<PASSWORD>@<NAS_IP>:27017/?authSource=admin
MONGODB_DB_NAME=jarvis_db
OPENAI_API_KEY=...
```

Start the API:

```powershell
cd C:\Users\nyiry\DEV\pa-voice-mvp
# activate venv, then:
uvicorn src.main:app --reload
```

Checks:

1. `GET http://127.0.0.1:8000/health` → ok
2. Write a fact via memory API (`working_memory` / `semantic_memory`)
3. Restart the app → data still present
4. Recreate the container **with the same volume** → data still present

App wiring (already in code):

- `src/core/config.py` — `mongodb_uri`, `mongodb_db_name`
- `src/db/mongodb.py` — Motor client
- `src/main.py` — connect on lifespan startup

## 7. Optional hardening

### Dedicated app user (instead of root in the URI)

```javascript
use admin
db.auth("pa_admin", "<ROOT_PASSWORD>")
use jarvis_db
db.createUser({
  user: "jarvis_app",
  pwd: "<APP_PASSWORD>",
  roles: [ { role: "readWrite", db: "jarvis_db" } ]
})
```

URI:

```env
MONGODB_URI=mongodb://jarvis_app:<APP_PASSWORD>@<NAS_IP>:27017/jarvis_db?authSource=jarvis_db
```

### Indexes (after first real traffic)

```javascript
use jarvis_db
db.working_memory.createIndex({ user_id: 1 })
db.semantic_memory.createIndex({ user_id: 1 })
```

Vector search remains in-app (cosine) for Phase 1; Community Edition does not require Atlas for that path.

### Backup

- Hyper Backup / snapshots of `/volume1/docker/pa-mongo/data`, or
- `mongodump` from inside the container on a schedule

## Success criteria

- [ ] Container `pa-mongo` runs continuously
- [ ] Data lives under the NAS bind path / volume
- [ ] Auth required; no open Mongo on the LAN without password
- [ ] Windows PC connects with the URI
- [ ] FastAPI persists `working_memory` / `semantic_memory`
- [ ] Data survives app restart and container recreate (same volume)
- [ ] No secrets in Git; image not floating on `latest`

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| Auth fails / old password | Data dir was not empty when env password changed |
| Permission denied `/data/db` | Host folder permissions |
| Timeout from PC | Firewall, wrong IP, port not published, different VLAN |
| `Authentication failed` | Wrong user/pass, missing `authSource=admin`, unencoded special chars |
| Empty DB after recreate | Volume/bind mount missing — always map `/data/db` |

## Related files

- Template: `deploy/nas/docker-compose.mongodb.yml`
- Local full stack (PC): `docker-compose.yml`
- Env sample: `.env.example`
- Memory design: `docs/memory-design.md`
