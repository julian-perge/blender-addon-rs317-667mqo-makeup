# Old School caches come first, and 317 and 667 support stays until it is removed

Superseded by [ADR 0017](0017-read-caches-directly-without-317-and-667-code.md) on 2026-11-11.

On 2026-11-06 the owner moved dumper and add-on work to Old School RuneScape caches, starting with OpenRS2 archive 430 (build 149, July 2017), and decided to keep the 317 and 667 support, with its local files archived. Work on 667's new format was already parked until the old format is done (issue 23 (`git show 2a78edd:.scratch/osrs-focus/issues/23-667-new-format-models.md`)).

The owner wants the code that serves only the 317 and 667 revisions removed once Old School work no longer needs it, to reduce tech debt (issue 24 (`git show 2a78edd:.scratch/osrs-focus/issues/24-remove-317-and-667-only-code.md`)). Until then it stays, including the old-format decoder's footer boundary check and its `InvalidModelError` wrapping. Old School support does not extend the approved revision 1 animation contract on its own.
