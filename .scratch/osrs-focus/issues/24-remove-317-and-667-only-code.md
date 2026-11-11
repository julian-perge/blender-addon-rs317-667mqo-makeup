# Remove the code that serves only 317 and 667

Status: resolved

Parked by the owner, recorded 2026-11-06: the removal that [ADR 0003](../../../docs/adr/0003-old-school-caches-come-first.md) plans, once Old School work no longer needs that code.

## Comments

- 2026-11-10, triage with the user: needs-info. Parked. It unparks once Old School work no longer needs the 317 and 667 code (ADR 0003).
- 2026-11-11, agent: done on the branch `refactor/remove-dumper-and-legacy-revisions`, following [the spec](../../../spec/remove-dumper-and-legacy-revisions.md). The 667 importer, the `rs667` fixtures and the 317 and 667 cache files are gone, and the old format stays. [ADR 0017](../../../docs/adr/0017-read-caches-directly-without-317-and-667-code.md) records the decisions and supersedes ADR 0003.
