# Candidates and Plans

Candidate generation is read-only and bounded. Candidate IDs are deterministic and unique; fingerprints bind operation parameters to source, process, policy, objective, and implementation identities. Evidence is capped and ambiguous fingerprint remapping is rejected.

Plans sort candidates by a fixed operation order and retain parameters, expected objective deltas, prerequisites, rejection reasons, approval requirements, and limitations. Plan generation never mutates a workspace. Any source/workspace/profile/material/process/flag/policy/objective/implementation change makes the plan stale and requires regeneration.
