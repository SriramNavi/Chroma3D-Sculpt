# Security Baseline

Status: `PASS` at checkpoint `v0.8.0-pre-hardening-backup`.

| Classification | Count |
| --- | --- |
| EXPECTED_RESTRICTED_PROVIDER_PATH | 2 |

| Path | Line | Category | Classification | Evidence |
| --- | --- | --- | --- | --- |
| blender_addon/chroma3d_sculpt/services/provider_transport.py | 6 | network_boundary | EXPECTED_RESTRICTED_PROVIDER_PATH | import http.client |
| blender_addon/chroma3d_sculpt/services/provider_transport.py | 8 | network_boundary | EXPECTED_RESTRICTED_PROVIDER_PATH | import ssl |

The explicit provider adapter is classified separately from unbounded network behavior. This is a local static baseline, not live-provider security qualification.
