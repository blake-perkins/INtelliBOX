# Building INtelliBOX with Claude Code: A Development Report

## Overview

INtelliBOX is an automated email action tracking system built for fast-paced software teams. It parses emails using AI (GPT-4) to extract actionable items, stores them in a database, and provides a web dashboard for action management, assignment tracking, and AI-generated reports.

The entire application — from empty repository to fully deployed, containerized production system — was built collaboratively with Claude Code (Anthropic's AI coding assistant) over the course of 8 days in February 2026. This report documents how that collaboration worked: what was needed to get started, how the project evolved, and what patterns made the process effective.

---

## Table of Contents

1. [Prerequisites & Setup](#prerequisites--setup)
2. [Getting Started — The First Prompts](#getting-started--the-first-prompts)
3. [Day 1: Zero to MVP (Feb 16)](#day-1-zero-to-mvp-feb-16)
4. [Day 2: Polish & Production Hardening (Feb 17)](#day-2-polish--production-hardening-feb-17)
5. [Day 3: CI/CD & Deployment (Feb 18)](#day-3-cicd--deployment-feb-18)
6. [Days 4–8: Enterprise Features (Feb 19–23)](#days-48-enterprise-features-feb-1923)
7. [The Tooling Troubleshooting Story](#the-tooling-troubleshooting-story)
8. [The MatlabToCpp Crossover](#the-matlabtocpp-crossover)
9. [Prompt Patterns That Worked](#prompt-patterns-that-worked)
10. [What Claude Couldn't Do](#what-claude-couldnt-do)
11. [By the Numbers](#by-the-numbers)

---

## Prerequisites & Setup

Before any code was written, the following tools and accounts were needed:

| Prerequisite | Purpose | Notes |
|-------------|---------|-------|
| **Python 3.12** | Runtime for the application | Claude helped install it during the first session |
| **VS Code** | IDE / development environment | Primary interface for all work |
| **Claude Code VS Code Extension** | AI coding assistant | The extension that runs Claude inside VS Code |
| **Git + GitHub account** | Version control & hosting | Repo was created manually on GitHub (`blake-perkins/EmailTools`) |
| **OpenAI API account** | GPT-4 for email action extraction | A mock/demo mode was built so the app works without one |
| **Node.js** | Required for the Claude Code CLI | Installed mid-project to manage permissions |
| **AWS account** | Production hosting (EC2) | Set up manually for deployment |

The Claude Code extension runs inside VS Code and provides an interactive chat panel where you describe what you want built. Claude reads your codebase, writes code, runs commands, and iterates based on your feedback — all within the editor.

---

## Getting Started — The First Prompts

### Prompt 1: Orientation

> **"Tell me about this repo"**

Claude examined the repository and described what it found: an essentially empty project with just a `test.md` placeholder file and a `CLAUDE.md` configuration file. Three commits total. A blank canvas.

### Prompt 2: The Ask

> **"I have an application for parsing emails that I would like you to write for me. What's the best way for us to start collaborating?"**

Claude responded by asking clarifying questions about the use case, email source, tech stack preferences, and desired output. This led to the foundational problem statement:

### Prompt 3: The Problem Description

> *"I work on a very fast paced, high visibility software team of about 100 people. Every day, we get new Requests For Information and data calls from our customer, internal team leads, external stakeholders (such as directors, executives, managers, etc.). All of these come in the form of dozens and dozens of emails. It's practically impossible to keep up with them and I need a solution.*
>
> *My thought is to have an email account called 'ProgramTracker@example.com' so that I can Cc any important emails on it. This account would kick off some type of script/pipeline to store the relevant critical data in a database. Nightly, a report would be created that we could view in our morning scrum to see if there are any actions that need to be taken. Once those actions are assigned, they should not show up in the report anymore"*

### Prompt 4: Technical Constraints & Requirements

> *"1. Email Access*
>
> *I don't currently have anything set up. Come up with a solution for me just so I can test.*
>
> *2. Technology Stack*
>
> *Let's use Python for the language. Use SQLite. Hosting for now will be on my local machine, but I want to be able to host it in AWS for deployment.*
>
> *3. Report Format*
>
> *Let's start with an email summary, but I'd like the option for a Web dashboard. The report should have a couple sections. First section should be actions and should give me a source including sender, subject, and the ability to view the original email contents. The second section should have a 'program news' that basically summarizes everything that's been going on over the past X amount of days.*
>
> *4. Assignment Workflow*
>
> *If we're using the WebUI, I'd like to be able to click checkboxes and submit it. If using email, I'd like to send a response back to the ProgramTracker@example.com*
>
> *5. Parsing Intelligence*
>
> *I would like the AI to auto-detect important items and possible actions."*

### Prompt 5: Approval

Claude proposed a 3-phase MVP plan:
- **Phase 1** (Week 1): Database schema + email ingestion pipeline
- **Phase 2** (Week 2): GPT-4 action extraction with priority/due date detection
- **Phase 3** (Week 3): Nightly report generation and email delivery

The user's response:

> **"yes"**

And development began.

---

## Day 1: Zero to MVP (Feb 16)

The first day produced **56 commits** in roughly 14 hours — from empty repo to a fully functional web application with AI integration. Here's the timeline:

| Time | Commits | What Was Built |
|------|---------|---------------|
| 09:46 | 1 | Repository created (empty `test.md`) |
| 12:38 | 1 | **Full MVP**: SQLAlchemy models, Alembic migrations, email parser (.eml/.msg), CLI commands, GPT-4 integration with mock mode |
| 12:45–12:50 | 2 | Fix GPT-4 JSON parsing; add containerization + AWS deployment support |
| 13:14–13:24 | 2 | Dockerfile fixes; Podman helper scripts |
| 13:38–14:03 | 5 | **Web dashboard** (FastAPI + Jinja2): action list, email list, detail views, validation fixes |
| 14:11–14:46 | 5 | Interactive action management: assign, edit status, due dates, quick-assign dropdowns |
| 14:51–15:02 | 2 | Fix overdue logic; exclude completed actions from dashboard |
| 15:10–15:45 | 5 | **Modern UX redesign** across all pages: metrics bar, cards, enhanced header, program news |
| 15:52 | 1 | Manual action editing and creation |
| 16:00–16:17 | 7 | **Rebrand to INtelliBOX**: new name, custom SVG/PNG logo, favicon, mail icon |
| 16:21 | 2 | Date range filtering; quick-assign functionality |
| 19:45–20:36 | 5 | Priority rules engine with settings UI; test suite with DB isolation; AI Insights page |
| 20:45–22:52 | 4 | Structured program news; program roster; configurable AI categories |
| 23:04–23:24 | 5 | Dashboard simplification; timezone settings; customizable program name; bug fixes |

### Key Design Decisions Made on Day 1

- **Mock AI client**: Built a demo mode that generates realistic fake actions without needing an OpenAI API key. This made development and testing possible without burning API credits.
- **Click CLI**: All functionality exposed as CLI commands (`intellibox init`, `intellibox process`, `intellibox web`), making it scriptable and testable.
- **Jinja2 templates**: Server-rendered HTML rather than a JavaScript SPA — simpler stack, faster iteration.
- **Alembic migrations**: Database schema versioned from the start, enabling smooth upgrades.

---

## Day 2: Polish & Production Hardening (Feb 17)

**19 commits** focused on making the application robust and production-worthy:

### Features
- Redesigned action detail page with unified edit form
- Global stats bar with real-time last-sync tracking
- Analytics page with trend charts
- High-volume email processing: deduplication, email chain stripping, `.msg` file support
- **Knowledge Base**: document upload, TF-IDF search, OpenAI embedding search
- **RAG integration**: knowledge base context automatically injected into AI action extraction prompts

### Infrastructure
- BDD test suite using Behave/Gherkin (eventually grew to 165 scenarios)
- Database maintenance: VACUUM, ANALYZE, cache cleanup, log retention
- UTC datetime utility to eliminate timezone bugs
- Rotating log files for production persistence
- N+1 query consolidation (aggregated stats queries)
- File watcher resilience with health monitoring and supervised restarts
- AI client retry logic with exponential backoff
- TF-IDF corpus caching and knowledge context TTL cache

---

## Day 3: CI/CD & Deployment (Feb 18)

**37 commits** — the busiest day of the project. The application went from "runs locally" to "deployed in production with automated CI/CD":

### CI/CD Pipeline (GitHub Actions)
- 4-level testing: lint → unit tests → container build → integration tests
- Container test infrastructure using IronBank UBI 9 base images
- Automated deployment triggered on push to `main`

### Production Deployment
- **AWS EC2** instance with DuckDNS dynamic DNS
- **nginx** reverse proxy with Let's Encrypt SSL certificates
- **Zero-touch deployment script** (`pilot.sh`) — one command to provision a fresh server
- SSH-based deploy from CI, with rootless Podman containers
- Multiple rounds of deployment bug fixes (port conflicts, systemd service ordering, Windows line endings in deploy scripts)

### Testing
- **Playwright E2E test suite** (eventually 46 browser-based tests)
- Smoke tests against the live pilot server
- Stress and timing tests

### The Rename Recovery Incident

The project was originally called "EmailTools" and was renamed to "INtelliBOX" on this day. The rename changed the project directory path, which caused Claude Code to lose track of all previous conversation history. The conversations were stored under `d--dev-EmailTools` but the project now mapped to `d--dev-INtelliBOX`. Claude diagnosed the issue and copied the session files to the new directory, restoring access to the full development history.

---

## Days 4–8: Enterprise Features (Feb 19–23)

Development continued at a more sustainable pace (~5–10 commits/day), adding enterprise-grade capabilities:

| Date | Key Features |
|------|-------------|
| **Feb 19** | Security scanning (pip-audit, Bandit SAST, Syft SBOM, Grype container CVEs); PostgreSQL dual-database support; app.py refactored into domain-based router modules |
| **Feb 20** | Multi-user authentication (local auth + OIDC support); responsive layout (tablet/mobile); CSV export; audit logging |
| **Feb 21** | Re-process email with AI feature (admin-only); CI fixes |
| **Feb 23** | PostgreSQL deployment with Podman pod; deployment hardening; API usage telemetry dashboard; Sentry error tracking; structured JSON logging |

---

## The Tooling Troubleshooting Story

Not everything was smooth. An entire conversation session was dedicated to getting the basic development environment working. The Claude Code VS Code extension on Windows had issues executing bash commands — every command silently failed with exit code 1.

The troubleshooting journey included:
1. Attempting to install the Claude Code CLI via npm (required installing Node.js first)
2. Fixing PowerShell's execution policy (`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`)
3. Discovering the CLI permissions were separate from the VS Code extension's permissions
4. Modifying `settings.local.json` to allow bash commands
5. Restarting VS Code multiple times for settings to take effect
6. Diagnosing that the issue was a sandbox/shell configuration problem, not a permissions problem
7. Configuring the VS Code terminal to use Git Bash instead of PowerShell

This is a real "warts and all" detail — the first interaction wasn't writing brilliant code, it was fighting with tooling configuration. But once resolved, it never came up again.

---

## The MatlabToCpp Crossover

On Feb 27, the same Claude Code setup was used to build an entirely separate project: **MatlabToCpp** — a Jenkins CI/CD pipeline for automating MATLAB-to-C++ code generation.

In a single session (9.6MB of conversation, running out of context 4+ times), Claude:
- Designed a full Jenkins pipeline with 10 stages
- Built 3 algorithm packages (Kalman filter, low-pass filter, PID controller)
- Created a mock MATLAB system (so no MATLAB license was needed)
- Set up Nexus artifact repository for package publishing
- Deployed Jenkins + Nexus to a new EC2 instance
- Built a consumer application that pulls released algorithms via Conan
- Created comprehensive documentation

Notably, Claude examined the existing INtelliBOX EC2 instance to assess whether it could also host Jenkins and Nexus — it determined the t3.micro (1GB RAM) was too small and recommended a separate instance.

This demonstrates that the workflow isn't project-specific. The same human-AI collaboration pattern — describe the problem, specify constraints, approve the plan, iterate on results — transferred directly to a completely different domain.

---

## Prompt Patterns That Worked

### 1. Front-load the problem description

The most important prompt in the entire project was the third one — the detailed natural-language description of the problem. It included:
- Team size and dynamics ("100 people, fast-paced, high visibility")
- The pain point ("things come in faster than we can manage them")
- The proposed workflow ("Cc important emails to ProgramTracker@example.com")
- The desired outcome ("nightly report for morning scrum")

This gave Claude enough context to make good architectural decisions throughout the entire project.

### 2. Specify constraints up front

Stating "Python, SQLite, OpenAI, Outlook" in the fourth prompt prevented wasted time exploring alternatives. Claude knew the boundaries and worked within them.

### 3. Keep prompts short after the initial setup

After the detailed problem description, most prompts were brief directives:
- **"yes"** — approve a proposed plan
- **"let's knock out sentry and structured logging"** — request a specific feature
- **"what's next on the roadmap"** — ask Claude to prioritize
- **"restarted. does it work now?"** — confirm a fix

### 4. Review the live application and give UX feedback

A significant portion of the conversation was the user reviewing the running web application and providing feedback on the UI — colors, spacing, card layouts, button placement, logo iterations. The user drove design decisions while Claude handled implementation.

### 5. Let Claude propose, then approve or redirect

Claude frequently proposed plans before implementing them. The user would approve ("yes"), redirect ("actually, let's do X instead"), or ask questions ("what is Sentry?"). This kept the human in control without requiring deep technical specification of every detail.

---

## What Claude Couldn't Do

Despite handling the vast majority of the coding work, there were things the user had to do manually:

| Task | Why |
|------|-----|
| **Create the GitHub repository** | Requires browser authentication and account access |
| **Set up the AWS account** | Account creation, billing, IAM configuration |
| **Provision EC2 instances** | Launching instances, configuring security groups, key pairs |
| **Configure DNS (DuckDNS)** | Account registration and domain setup |
| **Obtain API keys** (OpenAI, Sentry) | Account creation on external services |
| **Install Node.js** | Required downloading and running an installer |
| **Fix Windows shell issues** | PowerShell execution policy, VS Code terminal configuration |
| **Review UI/UX in the browser** | Claude can't see the rendered web application |
| **IronBank registry login** | DoD credentials for container base images |

Claude could write deployment scripts, CI/CD pipelines, and infrastructure-as-code — but couldn't click buttons in a browser or authenticate to external services.

---

## By the Numbers

| Metric | Value |
|--------|-------|
| **Total development time** | 8 days (Feb 16–23, 2026) |
| **Total commits** | 119 |
| **Busiest day** | Feb 18 — 37 commits |
| **Conversation sessions** | 16 (one primary session of 208MB / ~8,700 user messages) |
| **Python source files** | ~30+ modules across 7 packages |
| **Test coverage** | 14 pytest modules + 165 BDD scenarios + 46 Playwright E2E tests |
| **Web pages** | 8 (dashboard, actions, emails, insights, settings, knowledge base, roster, analytics) |
| **Database migrations** | 8 Alembic revisions |
| **Deployment targets** | Local dev, Docker/Podman container, AWS EC2 with CI/CD |
| **Databases supported** | SQLite (dev) + PostgreSQL (production) |
| **Security scans** | 4 tools (pip-audit, Bandit, Syft SBOM, Grype) |

---

*This report was generated by analyzing Claude Code conversation history files and git commit logs from the INtelliBOX repository.*
