# Contributing to Helix AI Studio

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to Helix AI Studio.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [BIBLE Documentation System](#bible-documentation-system)
- [Commit Message Guidelines](#commit-message-guidelines)

## Code of Conduct

By participating in this project, you agree to maintain a respectful, inclusive, and collaborative environment.

## How Can I Contribute?

### Reporting Bugs

Before submitting a bug report:
1. Check the [existing issues](https://github.com/tsunamayo7/helix-ai-studio/issues)
2. Verify you're using the latest version
3. Include detailed reproduction steps

Use the bug report template when creating an issue.

### Suggesting Enhancements

Feature requests are welcome! Please:
1. Search for existing feature requests first
2. Explain the use case and expected behavior
3. Consider how it fits with the project's goals

### Code Contributions

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature-name`)
3. Make your changes
4. Test thoroughly (see Testing section)
5. Update documentation (including BIBLE if architectural changes)
6. Submit a pull request

## Development Setup

### Prerequisites

- Windows 10/11
- Python 3.12+
- NVIDIA GPU (recommended for local LLM testing)
- Ollama installed and running
- Claude Code CLI installed (`npm install -g @anthropic-ai/claude-code`)

### Installation

```bash
# Clone your fork
git clone https://github.com/tsunamayo7/helix-ai-studio.git
cd helix-ai-studio

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest black mypy

# Run the app
python HelixAIStudio.py
```

### Project Structure

```
src/
  backends/       # Orchestration logic (mix_orchestrator, sequential_executor)
  tabs/           # UI tabs (mixAI, soloAI, settings)
  widgets/        # Custom widgets (neural visualizer, VRAM simulator)
  bible/          # BIBLE Manager system
  memory/         # 4-layer memory + Memory Risk Gate
  mcp/            # MCP integration
  utils/          # Constants, diagnostics, markdown renderer
config/           # Settings (gitignored, use examples)
data/             # Runtime data (sessions, memory DB)
```

## Pull Request Process

### Before Submitting

1. **Test your changes**:
   - Run the app and verify functionality
   - Test both mixAI and soloAI tabs if applicable
   - Verify no regressions in existing features

2. **Update documentation**:
   - Add/update docstrings for new functions/classes
   - Update BIBLE if architectural changes (see below)
   - Update CHANGELOG.md under `[Unreleased]` section

3. **Code quality**:
   - Run `black` for formatting: `black src/ HelixAIStudio.py`
   - Check for obvious issues
   - No commented-out code or debug prints

### PR Template

Use the provided pull request template. Key sections:

- **What**: Brief description of changes
- **Why**: Motivation and context
- **How**: Technical approach
- **Testing**: What you tested and how
- **BIBLE**: Whether BIBLE needs updating
- **Screenshots**: For UI changes

### Review Process

1. Maintainers will review within 7 days
2. Address feedback in new commits (don't force-push during review)
3. Once approved, maintainers will merge

## Coding Standards

### Python Style

- Follow PEP 8 (enforced by `black`)
- Use type hints where practical
- Docstrings for public functions/classes (Google style)

```python
def example_function(param1: str, param2: int) -> bool:
    """Short description.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value
    """
    pass
```

### PyQt6 Conventions

- Use snake_case for methods: `_on_button_clicked()`
- Private methods start with `_`
- Signal connections in `__init__()`
- Use constants from `styles.py` and `constants.py`

### Error Handling

- Use `logging` module (not print statements)
- Provide context in log messages
- Handle exceptions at appropriate levels

```python
import logging

logger = logging.getLogger(__name__)

try:
    risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
```

## BIBLE Documentation System

The project uses a "BIBLE-first" approach where the BIBLE document is the source of truth for architecture.

### When to Update BIBLE

Update the BIBLE (create a new version) when:

- Adding major features (e.g., new phase, memory layer)
- Changing architecture (e.g., module reorganization)
- Modifying data schemas (e.g., SQLite tables)
- Updating version number

### How to Update BIBLE

1. Copy `BIBLE/BIBLE_Helix AI Studio_[CURRENT].md` to `BIBLE/BIBLE_Helix AI Studio_[NEW].md`
2. Update version number, date, and changelog section
3. Modify relevant sections (architecture, file list, etc.)
4. Update `constants.py` `APP_VERSION`
5. Update `config/app_settings.json` version field
6. Mention BIBLE update in your PR

### BIBLE Sections to Update

Common sections that need updating:

| Section | When to Update |
|---------|---------------|
| Version History | Every version bump |
| Changelog | Every significant change |
| Architecture | New modules, data flows |
| File List | New/removed files |
| Directory Structure | New directories |
| Tech Stack | New dependencies |

## Commit Message Guidelines

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Formatting, no code change
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding tests
- `chore`: Maintenance tasks

### Examples

```
feat(memory): add GraphRAG community summaries

Implement graphrag_community_summary() to generate 3-sentence
abstracts of entity-centered subgraphs using ministral-3:8b.

Closes #123
```

```
fix(bible): correct section detection for numbered headings

BibleParser now handles headings like "## 3. Architecture" by
adding _NUM_ pattern to SECTION_HEADING_MAP.

Fixes #456
```

## Testing

### Manual Testing Checklist

Before submitting PR, test:

- [ ] App starts without errors
- [ ] mixAI: Full 3-phase pipeline completes
- [ ] soloAI: Claude CLI execution works
- [ ] Settings: Changes persist after restart
- [ ] BIBLE: Detection and display work
- [ ] Memory: No database errors
- [ ] UI: No visual regressions

### Future: Automated Testing

We plan to add:
- Unit tests for core logic (`pytest`)
- Integration tests for Phase 1-3 pipeline
- UI smoke tests

## Questions?

- Open a [discussion](https://github.com/tsunamayo7/helix-ai-studio/discussions)
- Comment on relevant issues
- Reach out to maintainers

---

**Thank you for contributing to Helix AI Studio!**
