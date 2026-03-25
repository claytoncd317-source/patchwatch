# PatchWatch

A containerized vulnerability intelligence agent that lets you ask plain-English questions about your vulnerability and asset data. Built as a portfolio piece for the Nucleus Security Cloud Engineering Intern challenge.

---

## Running locally

You'll need Docker and an Anthropic API key.

```bash
git clone https://github.com/claytoncd317-source/patchwatch.git
cd patchwatch
cp .env.example .env
# add your ANTHROPIC_API_KEY to .env
docker compose up --build
```

Open `https://localhost` in your browser and accept the self-signed cert warning.

The database seeds automatically on first startup with 12 realistic assets, 20 real CVEs from 2023–2024, and 30 findings linking them together.

---

## Design choices

**Hypercorn over uvicorn**
uvicorn's built-in SSL path calls `ctx.load_cert_chain()` in a way that raises `PermissionError: [Errno 13]` in WSL2 environments regardless of file permissions or user context. Hypercorn builds its own SSLContext differently and doesn't hit this bug. This was the single biggest technical decision in the project and the one that took the most time to diagnose.

**Self-signed cert generated at container startup**
`serve.py` calls the `openssl` CLI binary when the container starts and writes the cert and key to `/tmp`. This means every deployment gets a fresh cert, the private key never touches the repository, and `/tmp` is always writable inside a Docker container so there are no permission issues.

**SSL at the server layer, not the app layer**
The FastAPI application code knows nothing about TLS. Hypercorn handles all encryption before a request reaches the app. This is the correct separation of concerns — the web framework handles routing and business logic, the ASGI server handles transport security.

**SQLite with raw sqlite3**
The point of this project is the agentic layer on top of the database, not the database itself. SQLite keeps the stack simple and portable with zero external dependencies. Using the stdlib `sqlite3` module directly (no ORM) keeps the SQL surface transparent, which matters because Claude is the one writing the queries.

**Claude tool use for SQL generation**
Rather than prompting Claude to return SQL in a code block and parsing it with regex, the agent uses the Anthropic tool use API. Claude calls `run_sql(query=...)` as a structured function call, we execute it, feed the results back, and Claude writes a plain-English answer grounded in real data. This is more reliable and more interesting to demonstrate than string parsing.

---

## What I would improve with more time

- **Replace the self-signed cert with a proper local CA** using something like `mkcert` so the browser trust warning goes away entirely
- **Add persistent storage** — right now the SQLite database lives in `/tmp` inside the container and is wiped on restart. A Docker volume would fix this
- **Streaming responses** — the query endpoint currently waits for Claude to finish before returning anything. Server-sent events would make it feel much more responsive
- **Rate limiting and error handling** — the `/query` endpoint has no protection against abuse or runaway API costs
- **Better logging** — right now logs go to stdout. A structured logging setup with request IDs would make debugging much easier in a real environment
- **Authentication** — anyone who can reach the service can query it. Even basic API key auth would be a meaningful improvement

---

## Deploying to AWS

The straightforward path would be ECS (Elastic Container Service) with Fargate:

1. Push the Docker image to ECR (Elastic Container Registry)
2. Define an ECS task that pulls from ECR and injects `ANTHROPIC_API_KEY` via AWS Secrets Manager as an environment variable — never hardcoded
3. Put an Application Load Balancer in front of the ECS service and attach an ACM (AWS Certificate Manager) certificate for real HTTPS — this replaces the self-signed cert entirely
4. The ALB terminates TLS and forwards plain HTTP to the container internally, so the Hypercorn SSL setup would be removed in favor of ALB-managed certs
5. Use RDS or EFS if you need the SQLite database to persist across container restarts

For a simpler single-container deployment, App Runner or Elastic Beanstalk would get it running faster with less configuration.

---

## Why storing a private SSL key in a repository is bad practice

A private key is the secret half of a TLS certificate — whoever has it can impersonate your server and decrypt traffic that was meant for it. Committing it to a repository is dangerous for several reasons:

- **Git history is permanent.** Even if you delete the file in a later commit, the key still exists in the repository history and can be recovered with `git log` or by cloning an older state
- **Public repos are truly public.** If the repo is on GitHub, the key is accessible to anyone on the internet the moment it's pushed
- **Secrets scanners will flag it.** Tools like GitHub's secret scanning, truffleHog, and GitGuardian actively scan for private keys and will alert on it
- **It invalidates the security model.** TLS only works if the private key is secret. Once it's in a repo, you have to assume it's compromised and revoke and reissue the cert

The correct approach — which this project uses — is to generate the cert and key at runtime, store them only in memory or a tmpfs location like `/tmp`, and never let them touch version control. For production, secrets belong in a secrets manager like AWS Secrets Manager or HashiCorp Vault.

---

## How long it took

About an hour to build the actual application. The SSL issue — diagnosing why uvicorn was throwing `PermissionError: [Errno 13]` on `ctx.load_cert_chain()` in WSL2 and finding that Hypercorn solved it cleanly — took additional time on top of that before a single line of app code was written.

---

## AI tools used

I used Claude as a coding assistant throughout this project. I designed the architecture, debugged the SSL issues, and worked through the agentic loop logic — Claude helped write and refine the implementation.

The frontend (`app/static/index.html`) was almost entirely AI-generated. I gave it a direction and Claude produced the HTML/CSS/JS. The design decisions were mine; the implementation was Claude's.

---

## Data sources

All vulnerability data is sourced from publicly available, open source records:

- **CVE IDs, CVSS scores, and metadata** — from the [National Vulnerability Database (NVD)](https://nvd.nist.gov), maintained by NIST. Fully public information
- **Asset data** — entirely fictional. Hostnames, IPs, and team names do not represent any real organization
- **Findings data** — synthetically generated for demonstration purposes

Nothing in this repository contains proprietary data or information from any real organization's environment.

---

## Project structure

```
patchwatch/
├── serve.py           # Hypercorn entrypoint, generates SSL cert at startup
├── Dockerfile
├── docker-compose.yml
├── app/
│   ├── main.py        # FastAPI routes
│   ├── agent.py       # Claude tool-use loop
│   ├── database.py    # SQLite init + seed data
│   ├── models.py      # Pydantic schemas
│   └── static/
│       └── index.html # Frontend (AI-generated)
```

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.11 |
| Web framework | FastAPI |
| ASGI server | Hypercorn |
| AI | Claude via Anthropic tool use API |
| Database | SQLite |
| Container | Docker + Compose |

---

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/query` | Natural language → SQL → answer |
| GET | `/schema` | Raw database schema |
| GET | `/health` | Health check |
| GET | `/docs` | Auto-generated OpenAPI docs |
