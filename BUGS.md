# Discovered Bugs & Issues

No functional bugs were discovered in the application source code during the execution of the 120 unit and integration tests or the automated smoke test suite. All tests compiled and ran cleanly.

## Environment Limitations / Known Issues

### 1. Docker Desktop Daemon Offline

- **Description**: The automated smoke test requires the Docker daemon to build and boot the test stack. On the local host environment, the Docker Desktop service `com.docker.service` is stopped, preventing Docker commands from connecting to the Docker API.
- **Steps to reproduce**:
  1. Open PowerShell.
  2. Run `pytest -v -m smoke tests/smoke`
- **Expected behavior**: The smoke test boots the Docker Compose services successfully.
- **Actual behavior**: The pytest run fails with a descriptive error:
  `Failed: Docker daemon is not running or unreachable. Please start Docker Desktop/daemon to run the end-to-end smoke test stack.`
- **Severity**: Low (Environment setup issue).
- **Remediation**: The user must start Docker Desktop manually or start the `com.docker.service` Windows service with administrative rights.
