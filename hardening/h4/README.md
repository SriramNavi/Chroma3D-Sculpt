# H4 Release Stabilization and Qualification

H4 qualifies the frozen H3 product as the basis for a future Version 1.0
release-candidate decision. It adds no Sprint 8 capability and keeps the product
version at `0.8.0-alpha.1`.

The gate order is fail-closed: frozen identity, registration, persistence,
lifecycle, failure injection, operator safety, filesystem/privacy, public
contract, performance, focused/combined regression, package/native/install,
dataset identity, security, documentation, and final scope safety.

Tracked files are compact decisions and evidence summaries. Raw Blender output,
temporary `.blend` files, isolated profiles, package logs, and generated JSON are
ignored under `manual-tests/hardening/h4/reports/` and `logs/`.

No H4 tool commits, pushes, merges, tags, publishes, performs a live provider
request, uses a real Blender profile, mutates a protected dataset source, or
claims physical-print qualification.
