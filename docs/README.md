# TubeTrim developer docs

Technical documentation for people working on the TubeTrim codebase. For end-user documentation (installing, using the app, FAQ), see the [GitHub Wiki](https://github.com/CaddyDz/tubetrim/wiki).

## Onboarding path

Read these in order; together they take about 30 minutes.

1. **[Getting started](getting-started.md)**: run the app and the tests locally.
2. **[Architecture](architecture.md)**: components, request flow, job lifecycle, and the design decisions behind them.
3. **[API reference](api.md)**: HTTP endpoints, payloads, and status codes.
4. **[Development guide](development.md)**: conventions, testing patterns, CI, and how to make common changes.
5. **[Troubleshooting](troubleshooting.md)**: YouTube breakage, 403s, and other operational issues.

## Source of truth

The code is authoritative. [`SPEC.md`](../SPEC.md) is the original v1 design spec. It is still useful for intent and non-goals, but it has drifted in small ways (for example, trim validation is stricter in code than in the spec). These docs describe the code as it is.
