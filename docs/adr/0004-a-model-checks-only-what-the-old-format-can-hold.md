# A Model checks only what the old file format can hold

The owner approved this in the architecture review of 2026-11-05 (candidate 3). `Model` checks itself on construction and raises `InvalidModelError`, a `ValueError`. It enforces only what the old file format can hold: list lengths match, vertex and texture triangle indices are in range, each face has exactly one of a colour or a texture, alpha, priority and skin labels are 0 to 255, each delta between consecutive vertices is -16384 to 16383, and a model has at most 16384 vertices, so every face index difference fits too (the largest real model has 4,991). `encode` checks again, since lists can be changed in place.

Game-level limits, such as priorities 0 to 11, are not checked, so a model the client would draw oddly still saves. A textured face without a texture triangle is valid: `encode` gives it a triangle made of its own corners, which the client treats the same (`ModelData.java` line 1032).
