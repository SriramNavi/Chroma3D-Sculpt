# Strategy Generation

Strategies are ordered Sprint 5 candidate sequences. The generator includes scale-only, orientation-only, translation-only, repair-first, orientation-first, scale-first, contact-first, fidelity-first, minimum-support, minimum-bridge, fit-to-printer, stable-base, lightweight, balanced, high-fidelity, repair combinations, base stabilization, bounded decimation combinations, and custom objective-driven families.

Generation is deterministic and bounded. Semantic sequence/parameter duplicates, disallowed operations, experimental operations without enablement, unsupported combinations, hard violations, stale evidence, and budget limits create explicit pruning records. No geometry is changed during generation.
