# Dataset and Benchmark Baseline

Status: `PASS`. Checkpoint: `v0.8.0-pre-hardening-backup` / `d06e1a05890fe23e77e66f95fc40e0200638a765`.

| Identity | Version | Count | Manifest SHA-256 | Archive SHA-256 |
| --- | --- | --- | --- | --- |
| Dataset | 1.0.0 | 27 | 3e763782e6271eff153c8c4097a8b841423b31962d1222e2baf208178559df9a | ea260e588c1f7cbeed8798a11e2928491566882ee4ff867b4937e955ff399a13 |
| Golden benchmark | 1.0.0 | 27 | 5bafdbfdedf72afd1098a12d895dbbb538c997e9f6f87ae7f8d33316aff7f8bc | 23a67ec383f65c2b706237f151e45718f937e8832c9b55fe404ebae22bbba3df |

| Sprint 7 retained evidence | Value |
| --- | --- |
| Representative dataset | 10/10 PASS |
| Full dataset | 27/27 PASS |
| Release-input files | 206 |
| Release-input SHA-256 | 3c91d5a44ae8f7a35f2e1a28aa935ae35d9d8fef7326a420b32c59e851e71759 |
| Source immutability | PASS in fresh H0 10/10 and 27/27 evidence |
| Retained fingerprint compatible | False |
| Fingerprint mismatches | 54 |
| Newline-only mismatches | 45 |
| Content-identity mismatches | 9 |
| Evidence source | FRESH_H0_VALIDATION |
| Current semantic runtime fingerprint | 5394cc237ce1c66d265e75cc785dd03486e6c931cad20a19fd699e9bc3e8d832 |
| Frozen Sprint 7 evidence tree unchanged | True |

The retained raw fingerprint mismatch was not bypassed. H0 reconciled 45 newline-only paths, classified nine content differences, and ran fresh 10/10 plus 27/27 dataset validation under the current fingerprint. Frozen Sprint 7 evidence was not rewritten.
