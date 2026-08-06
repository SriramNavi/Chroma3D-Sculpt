# Sprint 7 Independent-Final First Failure

- First status: `FAIL` (`12/13` S7F-A through S7F-M gates passed).
- Failed gate: `S7F-H` cancellation.
- Classification: `HARNESS`.
- Cause: S7F-H constructed a bare cancellation session without first clearing S7F-G's still-active owned session.
- Fix: call the existing owned-runtime cleanup before constructing the independent cancellation fixture.
- Product cancellation logic changed: no.
- Gate weakened: no.
- Live provider calls: `0`.
