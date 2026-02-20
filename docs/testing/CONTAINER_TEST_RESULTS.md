# INtelliBOX - Container Testing

## Base Image

Production and test containers use **IronBank UBI 9** (`registry1.dso.mil/ironbank/redhat/ubi/ubi9`) — a hardened RHEL 9 image from the DoD Iron Bank registry.

### Registry Access

IronBank requires authentication. Get credentials at [https://registry1.dso.mil](https://registry1.dso.mil):

```bash
podman login registry1.dso.mil
# Or in CI:
echo "$IRONBANK_PASSWORD" | docker login registry1.dso.mil -u "$IRONBANK_USER" --password-stdin
```

---

## Container Test Suite

All container testing runs in CI automatically. The `container` job in `.github/workflows/ci.yml` performs:

1. **Build production image** — `docker build -t intellibox:prod .`
2. **Build test runner image** — `docker build -f Dockerfile.test -t intellibox:test-runner .`
3. **Run unit tests in container** — 13 pytest modules + BDD scenarios
4. **Start production container** — verify health check passes
5. **Run BDD integration tests** — behave tests against the live container
6. **Generate SBOM** — Syft produces SPDX and CycloneDX manifests
7. **Vulnerability scan** — Grype scans the SBOM for high-severity fixable CVEs

### Running Locally

```bash
# Prerequisites: podman login registry1.dso.mil

# Build production image
podman build -t intellibox:prod .

# Build test runner image
cp .dockerignore .dockerignore.bak && cp .dockerignore.test .dockerignore
podman build -f Dockerfile.test -t intellibox:test-runner .
cp .dockerignore.bak .dockerignore

# Run tests inside container
podman run --rm --env-file .env.test intellibox:test-runner

# Run production container
podman run -d --name intellibox --env-file .env \
    -v ./data:/app/data:Z -p 8000:8000 intellibox:prod

# Verify health
curl http://localhost:8000/health
```

---

## Verification Checklist

### Container Build
- [x] Production image builds from IronBank UBI 9
- [x] Test runner image builds with Chromium dependencies for Playwright
- [x] Python 3.12 installed via `dnf` (RHEL packages)
- [x] `curl-minimal` pre-installed (used by HEALTHCHECK)

### Container Tests (CI)
- [x] 13 pytest modules pass inside container
- [x] 165 BDD scenarios pass inside container
- [x] Production container starts and health check passes
- [x] BDD integration tests pass against live container
- [x] Syft SBOM generation succeeds (SPDX + CycloneDX artifacts uploaded)
- [x] Grype vulnerability scan passes (no high-severity fixable CVEs)

### Production Deployment
- [x] Container runs on EC2 via Podman with systemd auto-restart
- [x] nginx reverse proxy with TLS (Let's Encrypt)
- [x] HTTP basic auth via nginx `.htpasswd`
- [x] Data volume mounted at `/opt/intellibox/data`
- [x] CI/CD auto-deploys on push to `main`

---

## Troubleshooting

### IronBank Registry Auth Fails
```bash
# Verify credentials at https://registry1.dso.mil — use the CLI secret, not web password
podman login registry1.dso.mil
```

### Playwright Fails in Test Container
The test Dockerfile manually installs RHEL Chromium dependencies (nss, atk, cups-libs, etc.) because `playwright install --with-deps` uses `apt-get` internally which doesn't exist on RHEL:
```bash
# In Dockerfile.test, Chromium deps are installed via dnf, then:
RUN playwright install chromium  # without --with-deps
```

### Volume Permission Issues
Use the `:Z` flag for SELinux relabeling:
```bash
podman run -v ./data:/app/data:Z intellibox:prod
```
