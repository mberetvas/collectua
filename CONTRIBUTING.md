# Contributing to OPC UA Client

Thank you for your interest in contributing to the OPC UA Client project! We appreciate contributions of all kinds: code, documentation, bug reports, and feature requests.

## Code of Conduct

This project adheres to the Contributor Covenant Code of Conduct. By participating, you are expected to uphold this code. See [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) for details.

## Getting Started

### Prerequisites

- Python 3.12 or later
- Git
- Familiarity with OPC UA concepts (helpful but not required)

### Setup for Development

```bash
# Clone the repository
git clone https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}.git
cd opcua-client

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate.bat

# Install with development dependencies
uv sync

# Verify setup
opcua-client --version
```

## Development Workflow

### Finding an Issue to Work On

1. Browse [GitHub Issues](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/issues)
2. Look for issues labeled:
   - `good first issue` – Great for newcomers
   - `help wanted` – Need community assistance
   - `bug` – Confirmed bugs to fix
   - `enhancement` – Feature requests
3. Comment on an issue to express interest before starting work

### Creating a Feature Branch

```bash
# Update main branch
git checkout main
git pull origin main

# Create feature branch (use descriptive names)
git checkout -b feature/your-feature-name
git checkout -b fix/your-bug-fix-name
git checkout -b docs/improve-documentation
```

### Branch Naming Conventions

- `feature/short-description` – New features
- `fix/short-description` – Bug fixes
- `docs/short-description` – Documentation improvements
- `refactor/short-description` – Code refactoring
- `test/short-description` – Test additions or improvements

## Code Style & Standards

### Python Style Guide

- **Formatter:** `ruff format` (automatic)
- **Linter:** `ruff check` (enforced in CI/CD)
- **Type Hints:** Required on all functions
- **Docstrings:** Google-style format

Example:

```python
async def collect_alarms(
    client: Client,
    interval_ms: int,
    timeout_sec: int
) -> list[Alarm]:
    """Collect alarms from OPC UA server.
    
    Args:
        client: Connected OPC UA client instance
        interval_ms: Collection interval in milliseconds
        timeout_sec: Total timeout in seconds
        
    Returns:
        List of collected Alarm objects
        
    Raises:
        TimeoutError: If collection exceeds timeout_sec
        ConnectionError: If connection to server is lost
    """
    # Implementation
    pass
```

### Code Quality Tools

Run before every commit:

```bash
# Auto-format code
uv run ruff format .

# Check for linting issues
uv run ruff check .

# Run type checker (if configured)
uv run mypy opcua_client/
```

## Testing

### Writing Tests

- Place tests in the `tests/` directory
- Use `pytest` framework
- Filename pattern: `test_*.py`
- Test function pattern: `test_*`

Example test:

```python
import pytest
from opcua_client.cli import connect_command

@pytest.mark.asyncio
async def test_connect_success():
    """Test successful connection to OPC UA server."""
    result = await connect_command(
        server_url="opc.tcp://localhost:4840",
        timeout_sec=5
    )
    assert result.success is True
    assert result.message == "Connected successfully"

def test_connect_invalid_url():
    """Test connection with invalid URL."""
    with pytest.raises(ValueError, match="Invalid URL"):
        connect_command(server_url="not-a-url")
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_cli.py

# Run with verbose output
uv run pytest tests/ -vv

# Run with coverage
uv run pytest tests/ --cov=opcua_client --cov-report=html

# Run specific test
uv run pytest tests/test_cli.py::test_connect_success
```

### Coverage Requirements

- Minimum coverage: 70% for new code
- Target coverage: >80% for critical paths
- Integration tests are encouraged for user-facing features

## Commit Guidelines

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat` – New feature
- `fix` – Bug fix
- `docs` – Documentation changes
- `test` – Adding or updating tests
- `refactor` – Code refactoring without behavior change
- `perf` – Performance improvements
- `chore` – Build, dependencies, or other non-functional changes

### Examples

```bash
git commit -m "feat(cli): add verbose flag to browse command"
git commit -m "fix(collector): handle empty alarm list correctly"
git commit -m "docs(readme): update installation instructions for Windows"
git commit -m "test(integration): add OPC UA server connectivity test"
git commit -m "refactor(client): simplify connection logic"
```

## Documentation Requirements

All contributions affecting user-facing behavior **must** update documentation:

### Update CHANGELOG.md

Add entry under `[Unreleased]` section:

```markdown
## [Unreleased]

### Added
- New feature description

### Fixed
- Bug fix description

### Changed
- Behavior change description
```

### Update README.md

- Command signature changes → update CLI Reference
- New environment variables → update Configuration section
- New features → add to Quickstart examples
- Breaking changes → highlight in migration guide

### Add Docstrings

```python
def your_function(param: str) -> bool:
    """Brief description of what the function does.
    
    Longer description explaining the purpose, behavior,
    and any important details.
    
    Args:
        param: Description of the parameter
        
    Returns:
        Description of return value
        
    Raises:
        ExceptionType: When this exception might be raised
    """
```

## Pull Request Process

### Before Submitting

```bash
# Update with latest changes from main
git fetch origin
git rebase origin/main

# Run all checks locally
uv run ruff format .
uv run ruff check .
uv run pytest tests/ --cov=opcua_client

# Push to your fork
git push origin feature/your-feature-name
```

### PR Description Template

```markdown
## Description
Brief description of changes

## Related Issues
Closes #123, Relates to #456

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added
- [ ] Integration tests added
- [ ] Manual testing done
- [ ] Existing tests still pass

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
- [ ] Tests pass locally
- [ ] No new warnings introduced
```

### During Review

- Respond to review comments within 3 days
- Request re-review after making changes
- Push updates to the same branch (don't create new PR)
- Use "Resolve conversation" button when addressing feedback

### Merge

Once approved:
- Ensure CI/CD pipeline passes
- Repository maintainers will merge the PR
- Your branch will typically be deleted

## Issues & Discussions

### Reporting Bugs

Please include:

1. **Version:** `opcua-client --version`
2. **Python version:** `python --version`
3. **OS:** Linux/macOS/Windows with version
4. **Steps to reproduce:**
   ```
   1. ...
   2. ...
   3. ...
   ```
5. **Expected behavior:**
6. **Actual behavior:**
7. **Error message or log:**
8. **Additional context:** (screenshots, config, etc.)

### Requesting Features

Please include:

1. **Use case:** Why is this feature needed?
2. **Proposed solution:** How should it work?
3. **Alternatives:** Other approaches considered?
4. **Impact:** Breaking changes? Performance concerns?

## Best Practices

### Keep PRs Focused

- One feature or fix per PR
- Smaller PRs are reviewed faster
- If a PR grows large, consider splitting it

### Communicate Early

- Discuss big changes in an issue first
- Ask for guidance if unsure
- Don't hesitate to ask questions

### Learn from Feedback

- Code review is about improvement, not criticism
- Suggestions help maintain consistency
- Questions help us understand your approach

### Respect the Codebase

- Follow existing patterns
- Read related code before writing
- Don't introduce unnecessary dependencies
- Consider performance implications

## Questions?

- Comment on relevant GitHub issues
- Start a [GitHub Discussion](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/discussions)
- Email maintainers at [{{MAINTAINER_EMAIL}}](mailto:{{MAINTAINER_EMAIL}})

## Recognition

Contributors are recognized in:

- [GitHub Contributors](https://github.com/{{GITHUB_ORG}}/{{GITHUB_REPO}}/graphs/contributors) page
- [CHANGELOG.md](./CHANGELOG.md) for notable contributions
- Project release notes

---

Thank you for contributing to OPC UA Client! 🎉
