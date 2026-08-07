# H2 complexity, duplication, and dependency simplification

H2 starts from the published, annotated
`v0.8.0-h1-hardening-checkpoint` tag at merge commit
`d6cab118c44422375e69bd077cabc85a990a9a33`.

H2 is behavior-preserving release hardening, not a feature sprint. It resolves
the 50 retained suspicious-reference candidates before selectively addressing
well-covered complexity or exact-semantic duplication. Uncertain candidates
remain in place. H0 and H1 evidence is immutable.

Tracked evidence in this directory is compact. Raw analyzer, Blender, package,
dataset, lifecycle, and scanner output stays under the ignored
`manual-tests/hardening/reports/h2/` tree.

Publication, version/schema/profile/threshold changes, H3, and Sprint 8 remain
outside scope.

Current tracked H2 evidence includes the frozen H1 identity, complete
reference/complexity/duplication dispositions, preserved failure history,
bounded removal batches, and measured structural simplification report. The
final 17-gate result is produced only after Blender, package, dataset,
lifecycle, contract, security, and Git-scope validation.
