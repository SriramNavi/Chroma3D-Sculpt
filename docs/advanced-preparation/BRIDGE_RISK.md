# Bridge-Risk Analysis

Bridge analysis searches the evaluated mesh for bounded candidate regions that
are elevated relative to the proposed build direction, face downward, and have
supporting evidence on two sides. It estimates span, projected unsupported
distance, width, area, angle, material modifier, severity, confidence, and a
bounded list of evidence faces.

A broad overhang is not automatically called a bridge. One-sided cantilevers,
unsupported islands, ambiguous topology, and candidates beyond configured
limits remain distinct or explicitly limited. All sampling, evidence, region,
and triangle limits come from `performance_registry.py`.

Bridge severity is advisory. It depends on the sampled mesh, proposed build
direction, generic material modifier, process context, and declared evidence
limits. It is not a promise that a span will print successfully, and the
analysis never adds support geometry or changes orientation.
