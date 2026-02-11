# Security Policy

## Supported Versions

We actively support the latest major and minor versions with security updates.

| Version | Supported          |
| ------- | ------------------ |
| 8.4.x   | :white_check_mark: |
| 8.3.x   | :white_check_mark: |
| 8.2.x   | :x:                |
| < 8.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report security vulnerabilities to:

**Email**: tomotomlo@gmail.com

### What to Include

Please include the following information in your report:

- Type of vulnerability (e.g., code injection, privilege escalation, data leak)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue (what an attacker could achieve)
- Any potential mitigations you've identified

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Target**: Critical vulnerabilities within 30 days, others within 90 days

### Disclosure Policy

- We follow coordinated disclosure practices
- We will work with you to understand and validate the vulnerability
- Once fixed, we'll publish a security advisory (GitHub Security Advisories)
- We appreciate your patience during the fix and testing process

## Security Considerations

### MCP (Model Context Protocol) Servers

âš EE**Third-party MCP servers can introduce security risks, including:**

- Prompt injection attacks via MCP server responses
- Filesystem access beyond intended scope
- Network access to sensitive resources
- Execution of arbitrary commands

**Recommendations:**

- Only use MCP servers from trusted sources
- Review MCP server code before enabling
- Use allowlists and confirmation prompts for sensitive operations
- Limit filesystem and network access scope
- Treat all MCP server outputs as potentially malicious

Official MCP security guidance: https://docs.anthropic.com/en/docs/mcp

### Defensive Memory Injection

Helix AI Studio implements "defensive memory injection" (v8.3.1+) to mitigate prompt injection risks from stored memories:

- All memory context includes safety guard text
- Memory is treated as "reference material" rather than commands
- Memory Risk Gate filters harmful content before storage

### Local LLM Execution

When using local LLMs via Ollama:

- Models run with your user privileges
- Models can access files within Helix's working directory
- Be cautious with untrusted models or model sources
- Review Ollama security guidelines: https://docs.ollama.com/

### Claude Code CLI

Claude Code CLI operations:

- Can read/write files in the specified working directory (`--cwd`)
- Can execute shell commands (when explicitly instructed)
- Uses your Anthropic API key

**Best practices:**

- Use project-specific working directories
- Review file operations before execution
- Monitor API usage for unexpected activity

## Known Security Limitations

1. **PyInstaller Obfuscation**: The Windows executable is not cryptographically obfuscated. Reverse engineering is possible.
2. **Config Storage**: `config/app_settings.json` may contain sensitive data (API keys, paths). Use appropriate file permissions.
3. **Memory Database**: `data/helix_memory.db` stores conversation context. Protect this file if it contains sensitive information.

## Security Updates

Security updates are published in:
- [GitHub Security Advisories](https://github.com/tsunamayo7/helix-ai-studio/security/advisories)
- [CHANGELOG.md](./CHANGELOG.md) (with `[SECURITY]` prefix)

Subscribe to releases and security advisories to stay informed.

---

**Thank you for helping keep Helix AI Studio secure!**
