## ADDED Requirements

### Requirement: Static index page
The system SHALL serve a static `index.html` page at the root path (`/`) of the container's HTTP server.

#### Scenario: Requesting the root path
- **WHEN** a client sends an HTTP GET request to `/`
- **THEN** the server responds with HTTP 200 and the contents of `index.html`

### Requirement: Same-domain API endpoint
The system SHALL expose a backend API at the `/api/` path on the same host and port as the static page, so no cross-origin requests are required from the frontend.

#### Scenario: Requesting the API path
- **WHEN** a client sends an HTTP GET request to `/api/`
- **THEN** the server responds with HTTP 200 and a JSON body

### Requirement: CDK bootstrap version lookup via SSM
The `/api/` endpoint SHALL use boto3 to call AWS Systems Manager `GetParameter` for the parameter named `/cdk-bootstrap/hnb659fds/version` and SHALL return its value in the JSON response when the lookup succeeds.

#### Scenario: Parameter exists
- **WHEN** the `/api/` endpoint is called and the SSM parameter `/cdk-bootstrap/hnb659fds/version` exists and is readable
- **THEN** the JSON response includes the parameter's current value

### Requirement: Graceful fallback when parameter is unavailable
The `/api/` endpoint SHALL return the literal string `unavailable` in place of the parameter value when the parameter does not exist, and SHALL NOT return an HTTP error status for this case.

#### Scenario: Parameter does not exist
- **WHEN** the `/api/` endpoint is called and the SSM parameter `/cdk-bootstrap/hnb659fds/version` does not exist (SSM raises ParameterNotFound)
- **THEN** the JSON response includes the value `unavailable`
- **AND** the HTTP response status is 200

### Requirement: Containerized delivery
The system SHALL be packaged as a Docker image, defined by a single Dockerfile, that builds and runs the static page and the API together as one deployable unit.

#### Scenario: Building and running the image
- **WHEN** the Dockerfile is built with `docker build` and the resulting image is run with `docker run`
- **THEN** the container starts a single HTTP server process that serves both `/` and `/api/` on the container's exposed port
