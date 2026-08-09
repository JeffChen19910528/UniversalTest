# Universal Project Assessment Framework — Development Skill

## 1. Purpose

Build a reusable, project-agnostic automated testing and initial software-quality assessment framework.

The tool is intended for two situations:

1. **Unknown / unfamiliar project**
   - User receives a project from another team, vendor, Git repository, legacy system, or open-source project.
   - The tool should inspect the project and produce an initial assessment without requiring the user to understand the entire codebase first.

2. **User's own project**
   - User wants a repeatable baseline for functional testing, performance testing, regression detection, and basic quality assessment.

The framework MUST NOT claim to prove that a project is secure, bug-free, production-ready, or fully correct.

Its purpose is **initial automated assessment**, evidence collection, test execution, and risk indication.

---

# 2. Core Design Principle

The framework must be:

> **Universal Core + Project Adapters + Explicit Evidence**

Do NOT implement a collection of hard-coded tests tied to one project.

The architecture must separate:

```text
                    Universal Test Core
                           |
        +------------------+------------------+
        |                  |                  |
   Discovery           Adapters           Test Engine
        |                  |                  |
        +------------------+------------------+
                           |
                    Result / Evidence
                           |
                    Assessment Engine
                           |
                     Report Generator
```

The Core must remain independent from:

- programming language
- web framework
- database vendor
- frontend framework
- deployment platform
- cloud provider
- CI/CD platform

Technology-specific behavior belongs in adapters/plugins.

---

# 3. Primary User Experience

The eventual CLI should support a workflow similar to:

```bash
universal-test scan ./project
universal-test assess ./project
universal-test test ./project
universal-test performance ./project
universal-test report ./project
universal-test run ./project --all
```

The most important first command is:

```bash
universal-test assess ./project
```

It should be possible to point the tool at an unfamiliar repository and obtain an initial report.

Example:

```text
Universal Test Framework
========================

Project: Example ERP
Path: ./example-erp

Discovery
---------
[OK] Git repository detected
[OK] .NET solution detected
[OK] ASP.NET Core detected
[OK] React frontend detected
[OK] SQL Server configuration detected
[OK] Docker configuration detected
[OK] OpenAPI/Swagger detected

Detected Components
-------------------
Backend       ASP.NET Core
Frontend      React
Database      SQL Server
API           REST
Deployment    Docker

Assessment
----------
Functional Test Coverage:   PARTIAL
API Testability:            HIGH
Performance Testability:    HIGH
Configuration Risk:        MEDIUM
Dependency Risk:            MEDIUM
Test Infrastructure:        LOW

Evidence
--------
148 endpoints discovered
37 executable API checks generated
12 configuration findings
8 performance scenarios available

Overall Initial Assessment
--------------------------
MEDIUM CONFIDENCE

This assessment is not a security audit and does not prove correctness.
```

---

# 4. Development Rules

## 4.1 Never overclaim

The system must distinguish:

- detected
- tested
- passed
- failed
- skipped
- unknown
- inferred
- not applicable

Do NOT convert:

```text
"No test found"
```

into:

```text
"Feature is broken"
```

Do NOT convert:

```text
"No vulnerability detected"
```

into:

```text
"Secure"
```

Use evidence-based language.

---

## 4.2 Safe by default

Assessment of an unfamiliar project MUST default to non-destructive behavior.

The framework must NOT automatically:

- delete files
- modify source code
- modify production databases
- reset production data
- send uncontrolled high-volume traffic
- deploy infrastructure
- execute destructive SQL
- rotate credentials
- change cloud resources
- perform intrusive security exploitation

For performance tests, require an explicit target and explicit authorization/configuration.

Example:

```bash
universal-test performance ./project --target http://localhost:8080
```

Do not automatically attack arbitrary remote hosts.

---

## 4.3 Evidence first

Every finding should be traceable to evidence.

A result should conceptually contain:

```json
{
  "id": "API-001",
  "category": "functional",
  "status": "failed",
  "severity": "medium",
  "confidence": 0.94,
  "evidence": [
    {
      "type": "http_response",
      "status_code": 500
    }
  ],
  "message": "Endpoint returned HTTP 500 for valid request",
  "recommendation": "Inspect server-side exception handling"
}
```

The exact schema can evolve, but the principle must remain.

---

# 5. Architecture

Use a modular architecture.

Recommended structure:

```text
universal-test/
|
+-- src/
|   +-- core/
|   |   +-- models/
|   |   +-- engine/
|   |   +-- assertions/
|   |   +-- orchestration/
|   |   +-- configuration/
|   |
|   +-- discovery/
|   |   +-- filesystem/
|   |   +-- language/
|   |   +-- framework/
|   |   +-- service/
|   |   +-- api/
|   |   +-- database/
|   |
|   +-- adapters/
|   |   +-- rest/
|   |   +-- graphql/
|   |   +-- browser/
|   |   +-- database/
|   |   +-- docker/
|   |   +-- dotnet/
|   |   +-- node/
|   |   +-- python/
|   |   +-- blockchain/
|   |
|   +-- testing/
|   |   +-- functional/
|   |   +-- performance/
|   |   +-- regression/
|   |   +-- reliability/
|   |
|   +-- assessment/
|   |   +-- scoring/
|   |   +-- findings/
|   |   +-- recommendations/
|   |
|   +-- reporting/
|   |   +-- json/
|   |   +-- html/
|   |   +-- markdown/
|   |
|   +-- cli/
|
+-- tests/
+-- docs/
+-- examples/
+-- plugins/
+-- schemas/
+-- reports/
```

The actual language/framework can be selected by the implementation agent, but the architecture must preserve these boundaries.

---

# 6. Phase 1 — Discovery Engine

The first major capability is project discovery.

The tool should inspect the project without modifying it.

Detect, where possible:

## Repository

- Git
- branch
- commit
- repository root
- dirty working tree
- ignored files

## Languages

Examples:

- C#
- Java
- JavaScript
- TypeScript
- Python
- Go
- Rust
- PHP
- Kotlin
- Swift
- Solidity
- SQL

## Frameworks

Examples:

- ASP.NET Core
- WinForms
- WPF
- React
- Angular
- Vue
- Node.js
- Express
- FastAPI
- Django
- Spring Boot
- Laravel
- Hardhat
- Foundry

## Infrastructure

Detect:

- Dockerfile
- docker-compose
- Kubernetes
- Terraform
- GitHub Actions
- GitLab CI
- Jenkins
- Azure Pipelines

## Databases

Detect configuration/evidence for:

- SQL Server
- PostgreSQL
- MySQL
- SQLite
- MongoDB
- Redis

Never expose secrets in reports.

If configuration contains:

```text
password=...
api_key=...
token=...
connection string credentials
```

the report should redact the value.

---

# 7. API Discovery

If REST/OpenAPI is detected, discover:

- base URLs
- OpenAPI documents
- Swagger documents
- HTTP methods
- endpoints
- parameters
- request schemas
- response schemas
- authentication requirements

Generate a normalized internal representation.

Example:

```yaml
endpoint:
  method: POST
  path: /api/orders

request:
  content_type: application/json
  schema:
    customerId: string
    items: array

expected:
  status_codes:
    - 201
```

The Core test engine must consume the normalized representation, not framework-specific objects.

---

# 8. Functional Testing

Functional tests should be generated conservatively.

For each discovered endpoint, consider:

### Positive tests

- valid request
- minimum valid input
- normal input
- expected authentication

### Boundary tests

- minimum values
- maximum values
- empty collections
- optional fields
- null where allowed

### Negative tests

- missing required field
- invalid type
- malformed request
- unsupported method
- invalid identifier

### Authentication tests

Only when explicitly configured/authorized:

- unauthenticated request
- authenticated request
- invalid credential/token
- insufficient role

The framework should not assume what the correct business result is unless the specification provides it.

---

# 9. Assertion Engine

Create reusable assertions.

Examples:

```text
status_code
status_code_in
response_time_less_than
json_path_exists
json_path_equals
json_schema_valid
header_exists
header_equals
body_contains
body_not_contains
row_count
value_equals
value_not_null
```

Assertions must produce structured evidence.

---

# 10. Performance Testing

Performance testing must be separated from functional testing.

Support at minimum:

- baseline test
- load test
- stress test
- concurrency test

Measure:

```text
requests/sec
latency
P50
P90
P95
P99
error rate
timeouts
```

Where possible, collect:

```text
CPU
memory
network
database latency
```

Do not make host-level metrics mandatory because remote targets may not expose them.

The performance engine must support explicit limits:

```yaml
performance:
  concurrency:
    - 1
    - 10
    - 50
    - 100

  duration_seconds: 60

  thresholds:
    p95_ms: 500
    error_rate_percent: 1
```

The framework should clearly distinguish:

```text
observed value
configured threshold
pass/fail decision
```

---

# 11. Regression Engine

Support comparison against previous runs.

Example:

```text
Baseline
P95: 120ms
RPS: 900

Current
P95: 180ms
RPS: 870

Regression
P95: +50%
RPS: -3.3%
```

Allow configurable thresholds.

Do not mark every performance difference as a regression.

---

# 12. Assessment Engine

The assessment engine should aggregate evidence into categories.

Suggested categories:

```text
Project Discoverability
Build Health
Testability
Functional Health
API Health
Performance
Reliability
Dependency Health
Configuration Hygiene
Documentation
CI/CD Readiness
```

The first version should avoid pretending to calculate a scientifically validated universal quality score.

Instead produce:

```text
PASS
WARNING
FAIL
UNKNOWN
NOT_ASSESSED
```

A later version may introduce a scoring model after empirical validation.

---

# 13. AI Integration

AI is optional, not required for the framework to function.

The deterministic engine must work without an LLM.

AI may be used for:

- test case generation
- test prioritization
- failure explanation
- root-cause hypothesis
- project documentation summarization
- discovering likely business invariants
- recommending additional tests

AI output MUST be marked as:

```text
AI-generated hypothesis
```

rather than deterministic fact.

Recommended architecture:

```text
Deterministic Discovery
        |
        v
Structured Project Model
        |
        +------> Deterministic Tests
        |
        +------> Optional AI Test Generation
                         |
                         v
                  Candidate Tests
                         |
                         v
                 Validation Layer
                         |
                         v
                   Test Engine
```

AI must never bypass the validation/execution layer.

---

# 14. Plugin / Adapter System

The framework must support future adapters without modifying the Core.

Each adapter should expose capabilities conceptually similar to:

```text
detect()
describe()
discover()
generate_tests()
execute()
collect_metrics()
```

An adapter must declare:

```yaml
name: rest
version: 1
capabilities:
  - discovery
  - functional_testing
  - performance_testing
```

The Core should dynamically discover available adapters.

---

# 15. Initial Adapter Priorities

Implement in this order.

## Adapter 1 — REST/OpenAPI

Highest priority.

Support:

- HTTP/HTTPS
- JSON
- OpenAPI 3.x
- Swagger
- authentication configuration
- functional testing
- performance testing

## Adapter 2 — SQL

Support read-only assessment first.

Prioritize:

- SQL Server
- PostgreSQL
- MySQL

Never execute destructive SQL automatically.

## Adapter 3 — Browser

Support:

- Chromium-based browsers
- page discovery where possible
- basic navigation
- form interaction
- screenshot on failure

Prefer Playwright if technically appropriate.

## Adapter 4 — Docker

Detect:

- containers
- ports
- health checks
- service dependencies

Allow controlled startup only when explicitly requested.

## Adapter 5 — .NET

Detect:

- solution
- projects
- target framework
- tests
- build status
- package dependencies
- ASP.NET endpoints

## Adapter 6 — Node/Python

Add project discovery and test execution integration.

Blockchain support can be added later as a specialized adapter.

---

# 16. Test Specification

Tests should have a framework-independent representation.

Example:

```yaml
id: API-USER-001
name: Create user
type: functional

target:
  adapter: rest
  method: POST
  path: /api/users

request:
  json:
    name: Test User
    email: test@example.com

assertions:
  - type: status_code
    equals: 201

  - type: json_path_exists
    path: $.id
```

This allows the same test model to work with different execution engines.

---

# 17. CLI Requirements

At minimum:

```bash
universal-test scan <path>
universal-test assess <path>
universal-test test <path>
universal-test performance <path>
universal-test report <path>
```

Useful options:

```bash
--config
--output
--format
--verbose
--adapter
--target
--dry-run
--safe-mode
```

Default behavior should be safe.

---

# 18. Configuration

Support a project-local configuration file:

```text
universal-test.yaml
```

Example:

```yaml
project:
  name: example-project

assessment:
  enabled: true

functional:
  enabled: true

performance:
  enabled: true
  target: http://localhost:8080
  concurrency:
    - 1
    - 10
    - 50

database:
  enabled: false

security:
  enabled: false

ai:
  enabled: false
```

The user should be able to start with almost no configuration and progressively add configuration for better accuracy.

---

# 19. Reports

Generate at least:

```text
report.json
report.md
report.html
```

The report should contain:

1. Executive summary
2. Project discovery
3. Detected technologies
4. Test summary
5. Failed tests
6. Performance results
7. Findings
8. Evidence
9. Recommendations
10. Unknown / untested areas
11. Environment information
12. Run timestamp
13. Tool version

The HTML report should be useful for someone who has never seen the project before.

---

# 20. Important Concept — Unknown Is a Result

The framework must explicitly report uncertainty.

Example:

```text
Authentication
---------------
Status: UNKNOWN

Reason:
Authentication mechanism was detected but no authorized test
credentials were supplied.

This is not interpreted as PASS or FAIL.
```

Likewise:

```text
Database Integrity
------------------
Status: NOT_ASSESSED

Reason:
Database adapter was detected but read-only database access
was not configured.
```

This is a core design principle.

---

# 21. Testing the Testing Framework

The framework itself must have strong automated tests.

Required:

- unit tests
- integration tests
- adapter tests
- CLI tests
- fixture projects
- regression tests

Create fixture projects such as:

```text
examples/
  rest-demo/
  dotnet-demo/
  node-demo/
  python-demo/
  database-demo/
```

The framework must be able to run against its own fixtures.

---

# 22. Golden Test Projects

Create deliberately controlled projects:

```text
fixtures/
  healthy-api/
  broken-api/
  slow-api/
  invalid-api/
  auth-api/
```

Expected results should be version-controlled.

This allows the framework to detect regressions in its own detection and assessment logic.

---

# 23. Development Workflow for Claude Code

Claude Code must work incrementally.

Do NOT attempt the entire platform in one pass.

Use the following sequence:

## Phase 0 — Repository initialization

Create:

```text
README.md
ARCHITECTURE.md
SPECIFICATION.md
ROADMAP.md
PROGRESS.md
CHANGELOG.md
```

Define the architecture before major implementation.

## Phase 1 — Core

Implement:

- domain models
- configuration
- test result model
- assertion engine
- orchestrator
- CLI skeleton
- logging
- error handling

## Phase 2 — Discovery

Implement:

- filesystem discovery
- language detection
- project type detection
- configuration detection
- API/OpenAPI discovery

## Phase 3 — REST Adapter

Implement:

- OpenAPI parser
- endpoint model
- test generation
- execution
- assertions
- report output

## Phase 4 — Performance

Implement:

- concurrency engine
- latency measurement
- percentile calculation
- threshold evaluation
- baseline comparison

## Phase 5 — Reports

Implement:

- JSON
- Markdown
- HTML

## Phase 6 — SQL Adapter

Read-only first.

## Phase 7 — Browser Adapter

Playwright or equivalent.

## Phase 8 — .NET / Node / Python project adapters

## Phase 9 — AI integration

Only after deterministic functionality is stable.

---

# 24. Definition of Done

A feature is NOT complete because code compiles.

A feature is complete only when:

```text
[ ] implementation exists
[ ] unit tests exist
[ ] integration tests exist where applicable
[ ] error handling exists
[ ] CLI behavior is documented
[ ] configuration is documented
[ ] report output is implemented
[ ] fixture project exists
[ ] regression test exists
[ ] README documentation is updated
[ ] PROGRESS.md is updated
```

---

# 25. Engineering Constraints

Prefer:

- maintainability
- deterministic behavior
- modularity
- clear interfaces
- strong typing
- structured logging
- reproducible results
- offline operation where practical
- minimal external dependencies

Avoid:

- giant monolithic classes
- hard-coded project assumptions
- framework-specific logic in Core
- hidden network activity
- destructive default behavior
- mandatory cloud services
- mandatory LLM dependency
- unexplained magic scoring

---

# 26. Security and Privacy

The tool may encounter:

- API keys
- passwords
- access tokens
- connection strings
- private keys
- environment variables

Never print secrets into:

- console logs
- reports
- screenshots
- exception messages
- generated test cases

Implement redaction.

Patterns should include at least:

```text
password
passwd
secret
token
api_key
apikey
authorization
connection string credentials
private key
```

The exact redaction system should be extensible.

---

# 27. Performance of the Framework

The testing framework itself should not become a bottleneck.

Discovery should be:

- incremental where possible
- cacheable
- cancellable

Long-running tests should support:

```text
timeout
cancellation
progress reporting
structured logging
```

---

# 28. Future Extensions

Do not implement these prematurely, but keep architecture open for:

- GraphQL
- gRPC
- message queues
- Kafka
- RabbitMQ
- mobile applications
- Kubernetes
- cloud resources
- blockchain / EVM
- smart contracts
- distributed load testing
- mutation testing
- code coverage analysis
- SBOM analysis
- dependency vulnerability scanning
- chaos testing
- AI-driven test generation
- self-healing test maintenance

---

# 29. What This Project Is NOT

Do not position the first version as:

- a complete security scanner
- a replacement for QA engineers
- a replacement for penetration testing
- a formal verification system
- a complete business-logic validator
- a guarantee of production readiness
- a universal vulnerability detector

The correct positioning is:

> A general-purpose automated framework for initial software project discovery, functional validation, performance measurement, regression detection, and evidence-based quality assessment.

---

# 30. First Implementation Goal

The first usable milestone should be:

```text
Given an unfamiliar REST/OpenAPI project:

1. Scan repository
2. Detect project/API
3. Discover endpoints
4. Start or connect to an explicitly configured target
5. Generate conservative functional tests
6. Execute tests
7. Collect latency/error information
8. Identify failures
9. Produce JSON + Markdown + HTML report
10. Clearly list unknown/unassessed areas
```

A user should be able to take a new project and obtain useful information within minutes.

---

# 31. Claude Code Operating Instructions

When working on this repository:

1. Read `SPECIFICATION.md`, `ARCHITECTURE.md`, and `PROGRESS.md` before changing architecture.
2. Do not rewrite the architecture merely because a local implementation is inconvenient.
3. Inspect existing code before creating new abstractions.
4. Prefer extending an existing interface over duplicating functionality.
5. Keep Core technology-independent.
6. Put technology-specific behavior in adapters.
7. Add tests with every non-trivial implementation.
8. Run the smallest relevant test suite first, then the full suite.
9. Never silently disable failing tests.
10. Never delete existing functionality without documenting the reason.
11. Never introduce an LLM dependency into deterministic Core functionality.
12. Never execute destructive actions against a discovered project automatically.
13. Redact secrets in logs and reports.
14. Update `PROGRESS.md` after completing a meaningful phase.
15. Update `CHANGELOG.md` for user-visible changes.
16. Keep documentation synchronized with implementation.
17. If a requirement is ambiguous, choose the safest implementation and document the assumption.
18. Before adding a new dependency, evaluate whether the functionality can be implemented using an existing dependency.
19. Keep the project runnable at every phase.
20. At the end of each implementation phase, report:
    - files changed
    - functionality added
    - tests executed
    - test results
    - known limitations
    - next recommended phase

---

# 32. Recommended First Prompt to Claude Code

After placing this skill file in the repository, ask Claude Code:

> Read `skill.md` completely and treat it as the development constitution for this project.
>
> Do not start by implementing the entire framework.
>
> First inspect the repository and determine whether an existing project structure already exists.
>
> Then create or update:
>
> - `SPECIFICATION.md`
> - `ARCHITECTURE.md`
> - `ROADMAP.md`
> - `PROGRESS.md`
> - `CHANGELOG.md`
> - `README.md`
>
> Convert the requirements in `skill.md` into a concrete implementation plan.
>
> Do not implement Phase 2+ yet.
>
> First finalize the architecture and Phase 1 Core specification, identify technology choices, define the core domain models/interfaces, and create the initial test strategy.
>
> Do not add unnecessary AI functionality at this stage.
>
> Do not implement project-specific business logic.
>
> After producing the planning documents, stop and report the proposed architecture and any assumptions that require approval.

---

# 33. Long-Term Goal

The final user experience should approach:

```bash
universal-test assess ./unknown-project
```

and produce:

```text
Project discovered
        ↓
Technology detected
        ↓
Services detected
        ↓
Testability evaluated
        ↓
Tests generated
        ↓
Tests executed safely
        ↓
Performance measured
        ↓
Failures analyzed
        ↓
Evidence collected
        ↓
Initial quality assessment
        ↓
HTML / Markdown / JSON report
```

The framework should make it possible for a developer or engineer to answer:

> "I just received this project. What can I learn about its health, testability, functionality, and performance without spending days manually understanding it?"

That is the central purpose of this project.
