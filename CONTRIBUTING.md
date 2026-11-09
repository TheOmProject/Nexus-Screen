# Contributing to Nexus Screen

Thank you for your interest in contributing. This project is in **public beta** (v0.1.0-beta.1).
Contributions of all kinds are welcome: bug reports, feature requests, documentation improvements,
and code.

---

## Reporting Bugs

1. Run the built-in bug report tool from your Pi:
   ```bash
   ~/nexus-screen/scripts/bug-report.sh "brief description of the problem"
   ```
   This collects service logs, printer state, and version information without capturing credentials.

2. [Open a bug report](https://github.com/TheOmProject/Nexus-Screen/issues/new?template=bug_report.yml)
   and attach the resulting `logs/bug-*.tar.gz` file.

3. Include:
   - Your hardware (Pi model, display, OS version)
   - Steps to reproduce
   - What you expected vs. what happened
   - Any relevant journal output (`journalctl -u nexus-screen -b`)

---

## Requesting Features

[Open a feature request](https://github.com/TheOmProject/Nexus-Screen/issues/new?template=feature_request.yml)
describing what you want and why. Include:

- The problem you are trying to solve
- Your proposed solution (if any)
- Hardware context (printer type, add-ons, display)

---

## Submitting Pull Requests

1. Fork the repository and create a branch from `main`.
2. Make your changes. Keep each PR focused on one thing.
3. Run the test suite before submitting:
   ```bash
   cd ~/nexus-screen
   QT_QPA_PLATFORM=offscreen ~/nexus-screen-env/bin/python scripts/run_tests.py
   ```
   All tests must pass.
4. If you add a new feature or screen, add corresponding tests in `tests/`.
5. Open a pull request against `main` with a clear description of what changed and why.

---

## Code Style

- Python 3.11+, no external dependencies beyond PyQt6 (available via `apt`).
- All user-facing strings in English (US).
- No hardcoded paths, usernames, or IP addresses — derive everything from runtime context.
- Every printer command must go through `nexus/moonraker/commands.py` and be gated by
  `allow_commands` and the current printer state.
- Keep the `--hardware-display` / `--live` / `--allow-commands` flag separation intact:
  the app must work in read-only mode by default.

---

## Testing

```bash
# Run all tests
QT_QPA_PLATFORM=offscreen ~/nexus-screen-env/bin/python scripts/run_tests.py

# Run a specific test file
QT_QPA_PLATFORM=offscreen ~/nexus-screen-env/bin/python tests/test_print_controls.py
```

Tests use the offscreen Qt platform — no display hardware is needed.
Do not run tests with `--hardware-display` unless you intend to test on a real framebuffer.

---

## Hardware Testing

If you have access to hardware not listed in the [supported hardware table](README.md#supported-hardware),
testing and reporting results (pass or fail) is extremely valuable.
Please open an issue with your hardware details and findings.
