# Security Fixes Log

Running log of every security finding and its resolution.

## Scanner Reference

| Scanner | Scope | Gate Criteria |
|---------|-------|---------------|
| **pip-audit** | Python dependency CVEs (PyPI advisory DB) | Any known vulnerability |
| **bandit** | Python static security analysis | High severity + high confidence |
| **Syft/Grype** | Container image CVEs (OS + libraries) | High severity, fixable only |

---

## 2026-02-20 — Initial Security Scan

### B324: Use of weak MD5 hash (bandit — High/High)

- **File**: `src/intellibox/knowledge/embeddings.py:303`
- **Finding**: `hashlib.md5(...)` flagged as insecure hash usage (CWE-327)
- **Root cause**: MD5 used to compute a cache key for TF-IDF corpus change detection — not for any security purpose
- **Fix**: Added `usedforsecurity=False` parameter: `hashlib.md5(..., usedforsecurity=False)`
- **Commit**: `e3fbcd5`

### B701: Jinja2 autoescape disabled (bandit — High/High)

- **File**: `src/intellibox/reporter/email_sender.py:27`
- **Finding**: `Environment(loader=...)` without `autoescape=True` creates XSS risk (CWE-94)
- **Root cause**: Jinja2 defaults `autoescape` to `False`; email report templates render user-supplied data (email subjects, action descriptions)
- **Fix**: Added `autoescape=True`: `Environment(loader=FileSystemLoader(...), autoescape=True)`
- **Commit**: `e3fbcd5`

### B110: try/except/pass (bandit — Low/High) — Accepted

- **Files**: `src/intellibox/ingestion/file_watcher.py:106`, `src/intellibox/utils/logging.py:62`
- **Finding**: Bare `except: pass` suppresses errors silently (CWE-703)
- **Resolution**: Accepted as intentional resilience code. File watcher catch prevents a failed settings sync from crashing the watcher loop. Logging catch prevents a read-only filesystem from crashing the application. Both are non-critical operations where failure is expected in some environments.
- **Gate**: Does not trigger CI gate (low severity)

### pip-audit — Clean

- **Finding**: No known CVEs in any Python dependency
- **Resolution**: No action needed

### Grype container scan — Clean

- **Finding**: No high-severity fixable CVEs in IronBank UBI 9 base image or installed packages
- **Resolution**: No action needed
