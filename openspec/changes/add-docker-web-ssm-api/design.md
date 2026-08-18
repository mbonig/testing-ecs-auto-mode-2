## Context

This change produces a single Docker image that serves both a static HTML page and a backend JSON API on the same origin, distinguished by path (`/` vs `/api/`). The API's only job is to look up the CDK bootstrap qualifier version stored in SSM Parameter Store at `/cdk-bootstrap/hnb659fds/version` and return it, falling back to `unavailable` if the parameter is missing. There is no existing codebase to integrate with — this is a net-new, self-contained artifact intended to run as a container (e.g., on ECS, App Runner, or locally via `docker run`).

## Goals / Non-Goals

**Goals:**
- Single Dockerfile, single exposed port, single process model that's simple to run locally (`docker build` + `docker run`) and deploy to any container host.
- `/` serves `index.html` as static content.
- `/api/` returns a JSON response containing the SSM parameter value (or `unavailable`).
- Use Python + boto3 for the backend, per requirement.
- Fail gracefully: a missing parameter (`ParameterNotFound`) must not raise a 500 — it must be handled and return `unavailable`.

**Non-Goals:**
- No authentication/authorization on the API.
- No IaC (CDK/Terraform/CloudFormation) for deploying the container, provisioning IAM roles, or creating the SSM parameter itself — consumer of this image is responsible for granting `ssm:GetParameter` to the runtime role.
- No multi-page frontend, build tooling, or frontend framework — `index.html` is static and self-contained (inline CSS/JS is fine).
- No horizontal scaling, health checks, or observability beyond basic HTTP responses.
- No HTTPS termination inside the container (assumed to sit behind a load balancer/proxy if TLS is needed).

## Decisions

**1. Single process serving both static file and API, using Flask.**
Rationale: A single lightweight Python web framework can serve both the static `index.html` and the `/api/` route from one process on one port, which keeps the Dockerfile and runtime simple (one `CMD`, one port, no reverse proxy needed). Flask is chosen over raw `http.server`/`wsgiref` because it makes routing (`/` vs `/api/`) and JSON responses trivial with minimal code, and it's a well-known, minimal dependency. Alternative considered: nginx + separate Python API process (e.g., behind a reverse proxy) — rejected as unnecessary complexity for a "basic" demo app explicitly scoped to be simple.

**2. `boto3` SSM client calls `get_parameter` and catches `ParameterNotFound`.**
Rationale: `boto3`'s SSM client raises `ssm.exceptions.ParameterNotFound` when the parameter doesn't exist. Catching this specific exception (rather than a broad `except Exception`) and returning `unavailable` satisfies the requirement precisely while still surfacing unexpected errors (e.g., permission errors) distinctly if needed for debugging. For this basic version, any other boto3/ClientError is also treated as `unavailable` to keep the response contract simple (avoid leaking AWS error internals to the client), but is logged server-side.

**3. SSM client is created once at module load (process start), not per-request.**
Rationale: Creating a boto3 client is relatively expensive and clients are thread-safe; creating it once avoids repeated overhead per request. Region/credentials are picked up from the container's environment/instance role via the default boto3 credential chain — no hardcoded credentials.

**4. Base image: `python:3.12-slim`.**
Rationale: Small, official, well-maintained image with pip available; avoids the bulk of the full `python` image while avoiding the extra complexity of Alpine's musl/libc compatibility issues with some pip packages.

**5. Response shape: `{"cdk_bootstrap_version": "<value-or-unavailable>"}`.**
Rationale: A single, explicitly-named JSON field is unambiguous for the frontend to consume and for future extension (additional fields can be added without breaking the contract).

## Risks / Trade-offs

- [Risk] Container's IAM role/credentials lack `ssm:GetParameter` permission → API silently returns `unavailable` for a permissions issue, not just a genuinely missing parameter. **Mitigation**: Server-side logging distinguishes `ParameterNotFound` from other `ClientError`s (e.g., `AccessDeniedException`) in logs, even though the HTTP response is the same `unavailable` value for both, per the "basic response" scope of this change.
- [Risk] Running Flask's built-in dev server in production/containers is not recommended for robustness under load. **Mitigation**: Acceptable for this "basic"/demo-scoped change; noted as an open question below for anyone hardening this later.
- [Risk] No health-check endpoint means container orchestrators may have limited insight into liveness. **Mitigation**: Out of scope per Non-Goals; `/` and `/api/` both double as reachable endpoints for manual checks.

## Migration Plan

Not applicable — net-new, self-contained artifact with no existing deployment to migrate. Initial rollout is simply: build the image, run/deploy the container with an IAM role/credentials permitting `ssm:GetParameter` on `/cdk-bootstrap/hnb659fds/version`, and access port 80 (or whichever is exposed).

## Open Questions

- Should the API use a production WSGI server (e.g., gunicorn) instead of Flask's dev server? Left as basic/dev-server for this scope; can be revisited if this becomes a long-lived service rather than a demo.
- Should the SSM parameter name be configurable via environment variable rather than hardcoded? Out of scope for this change since the parameter name is explicitly specified as fixed.
