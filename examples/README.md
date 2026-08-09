# examples/

Fixture projects the framework runs against for its own integration tests and
golden-test regression suite (`skill.md` §21-22): `rest-demo/`, `dotnet-demo/`,
`node-demo/`, `python-demo/`, `database-demo/`, etc. Populated starting
Phase 2, once there is a discovery engine to exercise against them.

## `ci/`

CI provider templates for the Quality Gate (Phase 8) — `github-actions/`,
`gitlab/`, `jenkins/`. Each is a documented template, not a working
pipeline: it always shells out to the plain `universal-test` CLI, never
requires a provider-specific SDK, and leaves how *your* project starts
(build/deploy/run) as an explicit placeholder step you fill in. See
`README.md`'s "CI/CD Integration" section for the exit-code contract and
recommended baseline/pull-request workflow these templates follow.
