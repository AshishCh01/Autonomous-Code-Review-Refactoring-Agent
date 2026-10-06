# Quorum

**A multi-agent code review and repair system that only reports bugs it can reproduce and only suggests fixes it can verify.**

![status](https://img.shields.io/badge/status-in%20development-orange)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)

> Most AI review tools paste a diff into an LLM and post whatever comes back. Quorum treats every LLM claim as a hypothesis: a finding is posted only after a sandboxed test reproduces it, and a patch is suggested only after the full test suite passes with it applied.

---

## Table of Contents

- [Why Quorum](#why-quorum)
- [Features](#features)
- [How It Works](#how-it-works)
- [The Agents](#the-agents)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [Sandbox and Security Model](#sandbox-and-security-model)
- [Evaluation](#evaluation)
- [Design Decisions](#design-decisions)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Why Quorum

LLM-based review tools have three recurring problems:

1. **Hallucinated issues.** The model flags bugs that do not exist, and developers learn to ignore the tool.
2. **Unverified fixes.** Suggested patches often do not compile, break other tests, or "pass" only because the test was weakened.
3. **Noise.** A flood of low-value comments buries the few that matter.

Quorum addresses these with an evidence-first pipeline. Independent reviewer agents propose findings, a reproducer tries to turn each one into a failing test, a repair agent writes a patch, and a deterministic verifier decides whether the patch is accepted. Agents propose; the sandbox decides.

## Features

- **GitHub App integration**: triggers automatically on pull requests and posts inline review comments and `suggestion` blocks.
- **Specialized reviewer agents**: logic, security, performance, and test-coverage reviewers, each with its own prompt and tools.
- **Reproduce-then-report**: findings that cannot be reproduced are downgraded or dropped.
- **Verified patches**: every suggested fix is applied in a fresh sandbox and checked against the new failing test, the existing suite, linters, and type checks.
- **Test-tampering detection**: patches that modify or delete tests are rejected automatically.
- **Code-aware context building**: tree-sitter symbol index and call graph pull in callers, callees, and related tests instead of dumping the whole repo.
- **Noise control**: confidence thresholds, deduplication, and a configurable comment cap per PR.
- **Budgeting**: per-PR token, time, and retry limits enforced by the orchestrator.
- **Run traces**: every agent step, tool call, and sandbox result is stored and viewable in a dashboard.
- **Evaluation harness**: reproducible benchmarks for both repair quality and review precision/recall, including ablations.

## How It Works

```
PR opened / updated (GitHub webhook)
        |
        v
+------------------+
| Context Builder  |  diff + symbol index + call graph + related tests
+------------------+
        |
        v
+------------------+
| Reviewer Agents  |  logic | security | performance | coverage  (parallel)
+------------------+
        |  structured findings (file, line, claim, severity, confidence)
        v
+------------------+
| Triage           |  dedupe, merge, drop below confidence threshold
+------------------+
        |
        v
+------------------+
| Reproducer Agent |  writes a failing test or script in the sandbox
+------------------+
        |  reproduced?  -- no --> downgrade or drop finding
        | yes
        v
+------------------+
| Repair Agent     |  proposes a minimal unified diff
+------------------+
        |
        v
+------------------+
| Verifier         |  deterministic: apply patch, run tests, lint, types
+------------------+
        |  pass? -- no --> retry (up to N attempts) or report without a fix
        | yes
        v
+------------------+
| Reporter         |  inline comments + suggested changes + summary
+------------------+
```

A finding therefore ends in one of three states:

| State | Meaning |
|---|---|
| **Verified fix** | Bug reproduced, patch passes all checks. Posted with a suggestion block. |
| **Reproduced, no fix** | Bug reproduced but no verified patch within the retry budget. Posted with the failing test. |
| **Unreproduced** | Could not be reproduced. Dropped, or posted as a low-confidence note if enabled in config. |

## The Agents

| Component | Type | Responsibility |
|---|---|---|
| **Context Builder** | Deterministic | Parses the repo with tree-sitter, builds a symbol index and call graph, selects the functions touched by the diff plus their callers, callees, and tests. |
| **Reviewer agents** | LLM | Analyze the diff with focused prompts and emit structured findings with a confidence score. |
| **Triage** | Deterministic + light LLM | Deduplicates overlapping findings, ranks by severity and confidence, applies the comment cap. |
| **Reproducer** | LLM + sandbox tools | Writes a minimal failing test or script that demonstrates the finding, and runs it. |
| **Repair agent** | LLM + sandbox tools | Produces a minimal patch from the failing test and relevant code. May iterate on verifier feedback. |
| **Verifier** | Deterministic | Applies the patch in a fresh sandbox, runs the reproducing test, the existing suite, linters, and type checks. Rejects test tampering. |
| **Orchestrator** | State machine | Routes between stages, enforces retry limits and budgets, records traces. |

The verifier is intentionally **not** an LLM. Keeping the final decision deterministic is what prevents the system from talking itself into a wrong answer.

## Architecture

```
                +--------------------+
   GitHub  ---> |  Webhook API       |  FastAPI, signature verification
                +---------+----------+
                          |
                          v
                +--------------------+        +-------------------+
                |  Job Queue         | -----> |  Orchestrator     |
                |  (Redis)           |        |  (state machine)  |
                +--------------------+        +----+---------+----+
                                                   |         |
                          +------------------------+         +-----------------+
                          v                                                    v
                +--------------------+                               +--------------------+
                |  Agent Runtime     |  LLM API with tool calling    |  Sandbox Manager   |
                |  (prompts, tools)  | <---------------------------> |  Docker / gVisor   |
                +--------------------+                               +--------------------+
                          |                                                    |
                          v                                                    v
                +--------------------+                               +--------------------+
                |  Postgres          |  runs, findings, traces       |  Ephemeral         |
                |                    |                               |  containers        |
                +--------------------+                               +--------------------+
                          |
                          v
                +--------------------+
                |  Dashboard         |  trace viewer, metrics
                +--------------------+
```

**Key design points**

- Webhook handling is asynchronous: the API acknowledges quickly and enqueues a job.
- Each sandbox is a fresh, short-lived container; no state leaks between runs.
- Repo indexes are cached by commit SHA so repeated PR updates stay cheap.
- Reviewers run in parallel; reproduction and repair run per finding with bounded concurrency.

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.14+ |
| API | FastAPI |
| GitHub | GitHub App (Webhooks, Checks API, Pull Requests API) |
| Parsing | tree-sitter |
| Sandbox | Docker SDK (gVisor or Firecracker as a hardening option) |
| Queue | Redis |
| Storage | PostgreSQL |
| LLM access | Any provider with tool calling, behind a thin adapter |
| Dashboard | Minimal web UI for run traces |
| Testing | pytest |

## Project Structure

> This is the planned layout. Adjust it as the implementation evolves.

```
quorum/
├── app/
│   ├── api/              # webhook endpoints, signature verification
│   ├── orchestrator/     # state machine, retries, budgets
│   ├── agents/
│   │   ├── reviewers/    # logic, security, performance, coverage
│   │   ├── reproducer.py
│   │   ├── repair.py
│   │   └── prompts/      # versioned prompt templates
│   ├── context/          # tree-sitter indexing, call graph, retrieval
│   ├── sandbox/          # container lifecycle, resource limits, runners
│   ├── verifier/         # patch application, test/lint/type checks, tamper detection
│   ├── reporter/         # GitHub comment and suggestion formatting
│   ├── llm/              # provider adapter, token accounting
│   └── models/           # DB models and schemas
├── dashboard/            # trace viewer UI
├── eval/
│   ├── repair/           # SWE-bench subset runner
│   ├── review/           # injected-bug dataset and scoring
│   └── ablations/        # configuration sweeps
├── tests/
├── docker/               # sandbox images
├── quorum.yml.example
├── docker-compose.yml
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.14+
- Docker (running locally)
- Redis and PostgreSQL (provided via `docker-compose`)
- A GitHub account where you can create a GitHub App
- An API key for your chosen LLM provider
- A tunnel such as `ngrok` for receiving webhooks during local development

### 1. Clone and install

```powershell
git clone https://github.com/<your-username>/quorum.git
cd quorum/quorum-server
py -V:3.14 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

### 2. Create a GitHub App

1. Go to **Settings → Developer settings → GitHub Apps → New GitHub App**.
2. Set the webhook URL to your tunnel URL plus `/webhooks/github`.
3. Set a webhook secret.
4. Grant these permissions:
   - Pull requests: **Read & write**
   - Contents: **Read**
   - Checks: **Read & write**
   - Metadata: **Read**
5. Subscribe to the **Pull request** event.
6. Generate and download a private key.
7. Install the app on a repository you control.

### 3. Configure environment

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `GITHUB_APP_ID` | Numeric ID of your GitHub App |
| `GITHUB_PRIVATE_KEY_PATH` | Path to the downloaded private key |
| `GITHUB_WEBHOOK_SECRET` | Secret used to verify webhook signatures |
| `LLM_API_KEY` | API key for your LLM provider |
| `LLM_MODEL_TRIAGE` | Cheaper model used for triage |
| `LLM_MODEL_REPAIR` | Stronger model used for reproduction and repair |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |

### 4. Build sandbox images and start services

```powershell
# Build sandbox image (from project root)
cd ..
docker build -t quorum-sandbox-python docker/python

# Start Redis and PostgreSQL
docker compose up -d

# Start the API server
cd quorum-server
uvicorn app.api.main:app --reload
```

### 5. Try it

Open a pull request on the installed repository that introduces a deliberate logic bug. Within a few minutes Quorum should post a review with the reproducing test and, if verification passes, a suggested fix.

## Configuration

Per-repository behavior is controlled by a `quorum.yml` file at the repo root.

```yaml
language: python
test_command: "pytest -x -q"
lint_command: "ruff check ."
type_check_command: "mypy ."

reviewers:
  - logic
  - security
  - performance
  - coverage

thresholds:
  min_confidence: 0.6
  max_comments_per_pr: 8
  post_unreproduced: false      # post low-confidence notes for unreproduced findings

budgets:
  max_repair_attempts: 3
  max_tokens_per_pr: 400000
  max_seconds_per_pr: 600

sandbox:
  network: false
  cpu_limit: 2
  memory_limit_mb: 2048
  timeout_seconds: 120

ignore_paths:
  - "docs/**"
  - "migrations/**"
```

## Usage

**Automatic mode.** Once installed, Quorum runs on every opened or updated pull request.

**Re-run on demand** (planned): comment `/quorum review` on a PR to trigger a fresh run.

**CLI for local evaluation:**

```bash
# Run the repair pipeline on a SWE-bench subset
python -m eval.repair --subset lite --limit 25 --config configs/default.yml

# Score review quality on the injected-bug dataset
python -m eval.review --dataset data/injected_bugs --config configs/default.yml

# Compare configurations
python -m eval.ablations --matrix configs/ablations.yml
```

## Sandbox and Security Model

Pull requests contain untrusted code, so the sandbox is a core part of the design, not an add-on.

- **No network access** inside sandboxes by default.
- **Resource limits**: CPU, memory, process count, and wall-clock timeout on every run.
- **Read-only mounts** for the repository, with a writable scratch directory only.
- **Fresh container per verification**, destroyed afterwards.
- **Non-root user** inside containers.
- **Secrets never enter the sandbox.** API keys and the GitHub private key live only in the orchestrator process.
- **Optional hardening** with gVisor or Firecracker for stronger isolation.
- **Webhook signature verification** on every incoming request.
- **Fork PRs** are handled conservatively; review of forked PRs should run without any secrets and with the strictest sandbox profile.

Do not run Quorum against untrusted repositories on a machine that holds sensitive data without enabling the hardened sandbox profile.

## Evaluation

The project is only credible if the claims are measured. Evaluation covers two halves of the system.

### Repair quality

- **Benchmark:** a subset of SWE-bench Lite or Verified.
- **Metric:** resolve rate (the fraction of tasks where the generated patch makes the target tests pass without breaking others).
- **Note:** full benchmark runs are expensive, so start with a small, fixed subset and report the subset size and seed.

### Review quality

- **Dataset:** a set of PRs with known, injected bugs across several categories.
- **Metrics:** precision (share of posted comments that are real issues), recall (share of injected bugs found), and false-positive rate per PR.
- **Developer-facing metric:** comment acceptance rate, once used on real repositories.

### Ablations

| Configuration | Question it answers |
|---|---|
| Single agent vs. multi-agent | Does the multi-agent split help at all? |
| With vs. without reproducer | How many hallucinated findings does reproduction remove? |
| With vs. without context retrieval | How much does code-aware context improve results? |
| Different repair retry limits | Where do returns diminish? |
| Cheap vs. strong model per stage | What is the best cost/quality trade-off? |

### Results

> Results will be added as experiments are completed. Report the model used, the subset size, the number of runs, and cost per PR alongside every number.

| Configuration | Resolve rate | Precision | Recall | Avg. cost / PR | Avg. latency |
|---|---|---|---|---|---|
| Single-agent baseline | TBD | TBD | TBD | TBD | TBD |
| Quorum (full) | TBD | TBD | TBD | TBD | TBD |
| Quorum without reproducer | TBD | TBD | TBD | TBD | TBD |

If the multi-agent design does not outperform a well-prompted single agent, that result will be reported as is.

## Design Decisions

- **Deterministic verifier.** The final accept/reject decision comes from running code, not from a model's opinion.
- **Reproduce before repair.** A failing test gives the repair agent a concrete target and gives the reviewer a way to be wrong.
- **Tests are read-only to the repair agent.** Any patch touching existing tests is rejected, which closes the most common route to fake fixes.
- **Hand-rolled orchestration over a heavy framework.** A small explicit state machine is easier to debug, trace, and reason about. A framework such as LangGraph could be swapped in later.
- **Structured outputs everywhere.** Agents exchange typed objects (findings, patches, results), not free text.
- **Cheap model for triage, strong model for repair.** Spend tokens where quality matters.

## Known Limitations

- Initial support is limited to **Python projects with a pytest test suite**.
- Bugs that cannot be demonstrated by a test (design issues, naming, style, some concurrency problems) are out of scope for verified findings.
- Dependency installation and test-command detection can fail on unusual project setups; `quorum.yml` lets you specify them explicitly.
- Reproduction depends on the quality of the existing test infrastructure.
- Large PRs may exceed budgets and be reviewed partially.
- LLM output is non-deterministic, so results can vary between runs.

## Roadmap

- [ ] **Phase 1: Core loop.** Webhook, single reviewer, sandbox, reproducer, verifier, comment posting on one repository.
- [ ] **Phase 2: Repair.** Repair agent with retry loop and test-tampering detection.
- [ ] **Phase 3: Multi-agent.** Logic, security, performance, and coverage reviewers plus triage and noise control.
- [ ] **Phase 4: Context.** tree-sitter indexing, call graph, and cached repo indexes.
- [ ] **Phase 5: Evaluation.** SWE-bench subset runner, injected-bug dataset, ablation matrix, published results.
- [ ] **Phase 6: Dashboard.** Trace viewer and metrics.
- [ ] **Later:** additional languages (JavaScript/TypeScript), `/quorum` PR commands, learning from accepted and dismissed suggestions, hardened sandbox profile.

## Contributing

Contributions are welcome once the core loop is stable.

1. Fork the repository and create a feature branch.
2. Install development dependencies: `pip install -e ".[dev]"`.
3. Run the checks before opening a PR:
   ```bash
   ruff check .
   mypy .
   pytest
   ```
4. Open a pull request describing the change and, where relevant, evaluation impact.

Please open an issue first for large changes.

## License

Released under the MIT License. See [`LICENSE`](LICENSE) for details.

## Acknowledgments

- [SWE-bench](https://www.swebench.com/) for the repair benchmark.
- [tree-sitter](https://tree-sitter.github.io/) for code parsing.
- The open-source sandboxing community (Docker, gVisor, Firecracker).
