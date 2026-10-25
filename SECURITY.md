# Security Policy

## Supported Versions

TraceNest maintains security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

The TraceNest maintainers treat security vulnerabilities with high urgency.

If you believe you have found a security vulnerability in TraceNest:

1. **Do not** disclose the vulnerability publicly via GitHub Issues, public pull requests, or discussion forums.
2. Please report the vulnerability privately via GitHub Security Advisories at:
   https://github.com/tracenest/tracenest/security/advisories/new
   or by emailing: `security@tracenest.dev`
3. Include relevant reproduction steps, affected command-line flags, and a minimal reproduction repository if possible.

## Responsible Disclosure & Response Timeline

- **Initial Response:** Within 48 hours of report receipt.
- **Triage & Assessment:** Within 5 business days.
- **Fix & Public Advisory:** Coordinated release with the reporter.

## Security Design Tenets

- **Privacy by Default:** TraceNest never transmits code, diffs, or credentials to external network services unless explicitly configured by the user via `--allow-remote`.
- **Safe Command Invocations:** All subprocess executions pass arguments as structured arrays without `shell=True`.
- **Safe Path Resolving:** Paths are strictly validated to prevent directory traversal and symlink escapes.
- **Secret Redaction:** High-entropy patterns matching sensitive credentials are systematically redacted before logging, terminal output, or report serialization.
