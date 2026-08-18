## Why

We need a minimal, containerized web application that demonstrates a static frontend and a backend API served from the same domain, where the API reads AWS account/environment metadata (the CDK bootstrap version SSM parameter) via boto3. This serves as a reference/starter container for validating that a service can reach SSM and surface that data through a simple HTTP API alongside a static page.

## What Changes

- Add a `Dockerfile` that builds a single container image hosting:
  - A static `index.html` page served at `/`.
  - A Python-based backend API served at `/api/` on the same domain/port.
- Add backend API code (Python + boto3) implementing a `/api/` route that:
  - Calls SSM `GetParameter` for `/cdk-bootstrap/hnb659fds/version`.
  - Returns the parameter value in a basic JSON response.
  - Returns `unavailable` (instead of erroring) when the parameter does not exist.
- Add `index.html` with minimal markup/JS that calls `/api/` and displays the response.
- Add Python dependency manifest (`requirements.txt`) including `boto3`.

## Capabilities

### New Capabilities
- `web-ssm-status-api`: A containerized web app serving a static page and a same-domain `/api/` endpoint that returns the CDK bootstrap SSM parameter version (or `unavailable`), using Python and boto3.

### Modified Capabilities
- None.

## Impact

- **New files**: `Dockerfile`, `index.html`, backend API source (e.g. `app.py`), `requirements.txt`.
- **Dependencies**: Python 3.x runtime, `boto3` (and a lightweight web framework such as Flask, unless implemented with the standard library).
- **AWS access**: The running container's execution role/credentials must have `ssm:GetParameter` permission on `/cdk-bootstrap/hnb659fds/version` for the feature to return a real value; otherwise it falls back to `unavailable`. No infrastructure-as-code for IAM/deployment is included in this change — it is out of scope.
- **No existing systems affected** — this is a net-new, self-contained artifact.
