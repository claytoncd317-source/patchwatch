# PatchWatch

A containerized vulnerability intelligence agent that lets you ask plain-English questions about your vulnerability and asset data. Built as a portfolio piece targeting the vulnerability management space.

---

## What it does

Instead of clicking through dashboards, you just ask questions. Things like:

- *"Which production assets have critical open findings?"*
- *"Show me everything past its SLA deadline"*
- *"What CVEs don't have a patch yet?"*

Under the hood, Claude generates a SQL query from your question, runs it against a SQLite database, and writes back a plain-English answer alongside the raw results and the generated query. The whole thing runs over HTTPS in a Docker container.

---

## How long it took

Total build time was around 4-5 hours spread across a couple of sessions.

The bulk of that wasn't writing code — it was environment issues. WSL2 + Docker + SSL is a genuinely painful combination. uvicorn's built-in SSL support throws a `PermissionError: [Errno 13]` on `ctx.load_cert_chain()` in WSL2 regardless of file permissions, user context, or approach. I went through several attempts before landing on Hypercorn as the ASGI server, generating certs via the openssl CLI at container startup and storing them in `/tmp` to sidestep the permission issues entirely. That one problem probably ate 1.5-2 hours on its own.

The actual application logic — the two-turn tool use loop in `agent.py`, the FastAPI routes, the SQLite schema and seed data — came together relatively quickly once the infrastructure was sorted. Getting Docker Compose working on the specific Ubuntu/WSL2 setup (the compose plugin wasn't in the default apt repos and had to be installed manually) added another chunk of time.

The frontend was AI-generated from a direction I gave it. The backend architecture, data model, and debugging were mine.

---

## A note on AI assistance

I used Claude as a coding assistant throughout this project. I designed the architecture, worked through the SSL debugging, and built the agentic loop logic — but Claude helped write and refine a lot of the implementation, particularly boilerplate and seed data.

The frontend (`app/static/index.html`) was almost entirely AI-generated. I gave it a direction — dark terminal aesthetic, security tool vibe, show the generated SQL alongside results and the plain-English answer — and Claude produced the HTML/CSS/JS. That's worth being transparent about. The design decisions were mine; the implementation was Claude's.

This is an honest reflection of how a lot of development works right now. The understanding of what the code does and why still has to be yours.

---

## Data sources

All vulnerability data used in this project is sourced from publicly available, open source records:

- **CVE IDs and metadata** — sourced from the [National Vulnerability Database (NVD)](https://nvd.nist.gov), maintained by NIST. CVE identifiers, CVSS scores, severity ratings, and publish dates are all publicly disclosed information available to anyone.
- **Vulnerability descriptions** — written in plain English based on public security advisories, vendor bulletins, and NVD entries. No proprietary threat intelligence or paid feed data was used.
- **Asset data** — entirely fictional. Hostnames, IP addresses, OS names, and team names are generic and made up. They do not represent any real organization's infrastructure.
- **Findings data** — synthetically generated relationships between the fictional assets and the public CVEs. SLA deadlines and remediation statuses are fabricated for demonstration purposes.

Nothing in this repository contains proprietary data, private vulnerability intelligence, or information from any real organization's environment.

---

## How the SSL works

SSL is handled entirely in `serve.py` at the server level — the application code knows nothing about it. On container startup, `serve.py` calls the `openssl` CLI binary to generate a self-signed cert and stores it in `/tmp`. Hypercorn is then pointed at those cert files and binds on port 443. All TLS termination happens at the ASGI server layer before a request ever reaches FastAPI.

This approach was chosen specifically because uvicorn's built-in SSL path calls `ctx.load_cert_chain()` in a way that raises `PermissionError: [Errno 13]` in WSL2 environments. Hypercorn builds its own SSLContext differently and doesn't hit this bug.

---

## Infrastructure setup (WSL2 + Docker)

This is the full sequence of commands used to set up the environment and get the project running from scratch on WSL2 Ubuntu.

### Project structure
```bash
mkdir -p ~/patchwatch/app/static
cd ~/patchwatch
touch serve.py Dockerfile docker-compose.yml requirements.txt README.md .env.example .gitignore
touch app/__init__.py app/main.py app/agent.py app/database.py app/models.py
touch app/static/index.html
```

### Docker Compose plugin
Docker Compose wasn't available as an apt package on this Ubuntu setup, so it was installed manually as a CLI plugin:
```bash
DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
mkdir -p $DOCKER_CONFIG/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 \
  -o $DOCKER_CONFIG/cli-plugins/docker-compose
chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose

# Verify
docker compose version
```

### Environment file
```bash
cp .env.example .env
# Then open .env and add your ANTHROPIC_API_KEY
nano .env
```

### Build and run
```bash
docker compose up --build
```

### Verify the container is running
```bash
docker compose ps
```

### Stop the container
```bash
docker compose down
```

### Rebuild after code changes
```bash
docker compose up --build
```

### Git setup
```bash
cd ~/patchwatch
git init
git add .
git commit -m "initial commit: vulnerability intelligence agent with Claude tool use"
git remote add origin https://github.com/claytoncd317-source/patchwatch.git
git branch -M main
git push -u origin main
```

### Pushing updates
```bash
git add .
git commit -m "your message here"
git push
```

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.11 |
| Web framework | FastAPI |
| ASGI server | Hypercorn (SSL-safe in WSL2) |
| AI | Claude via Anthropic tool use API |
| Database | SQLite (stdlib, no ORM) |
| Container | Docker + Compose |

---

## Running it locally

You'll need Docker and an Anthropic API key.

```bash
git clone https://github.com/claytoncd317-source/patchwatch.git
cd patchwatch
cp .env.example .env
# add your ANTHROPIC_API_KEY to .env
docker compose up --build
```

Open `https://localhost` and accept the self-signed cert warning.

The database seeds automatically on first startup with 12 realistic assets, 20 real CVEs from 2023–2024 (RegreSSHion, XZ backdoor, HTTP/2 Rapid Reset, etc.), and 30 findings linking them together.

---

## Project structure

```
patchwatch/
├── serve.py           # Hypercorn entrypoint, generates SSL cert at startup
├── Dockerfile
├── docker-compose.yml
├── app/
│   ├── main.py        # FastAPI routes
│   ├── agent.py       # Claude tool-use loop (the interesting part)
│   ├── database.py    # SQLite init + seed data
│   ├── models.py      # Pydantic schemas
│   └── static/
│       └── index.html # Frontend (AI-generated)
```

---

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/query` | Natural language → SQL → answer |
| GET | `/schema` | Raw database schema |
| GET | `/health` | Health check |
| GET | `/docs` | Auto-generated OpenAPI docs |
