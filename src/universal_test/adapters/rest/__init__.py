"""REST/OpenAPI functional-testing adapter (Phase 3).

Technology-specific: parses OpenAPI documents, generates conservative
`core.models.TestCase`s, and executes them over HTTP via `httpx`. Core never
imports this package directly.
"""
