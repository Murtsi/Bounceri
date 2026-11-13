# Security

Bounceri is a hackathon prototype. It has no stable release or production support commitment yet.

## Report a vulnerability

Use the repository's **Security → Advisories → Report a vulnerability** option if private reporting is enabled. Otherwise, contact a repository maintainer privately using their GitHub profile contact details. Do not put credentials, visitor data, or an exploitable vulnerability in a public issue.

Include the affected commit, steps to reproduce, and a minimal example with synthetic data. We have no guaranteed response time.

## Data and credentials

Keep API keys and deployment credentials outside Git. If a credential was committed, revoke or rotate it; removing the current file does not remove Git history.

Do not upload raw production access logs, browser HAR files, database exports, authentication headers, or identifying visitor data. Use synthetic fixtures with documentation addresses for reproducible reports.

The Compose services and example passwords are for local development. Database and Adminer host ports bind to loopback. Review deployment authentication and network access before hosting these services publicly.
