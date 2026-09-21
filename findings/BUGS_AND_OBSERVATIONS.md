# Bugs & Observations

Findings from the local Kubernetes-based checkout and payment test run.

## Payment validation — fixed

Payment validation previously returned generic `UNKNOWN` errors for invalid
cards, expired cards, and unsupported brands. It also accepted invalid CVVs
and negative amounts. The service now rejects these inputs with gRPC
`INVALID_ARGUMENT` before processing the transaction.

Covered by `tests/unary/test_payment_validation.py`.

## Checkout edge-case validation — fixed

Checkout now returns `INVALID_ARGUMENT` for missing email, unsupported
currency, negative ZIP codes, and empty carts.

Covered by `tests/unary/test_checkout_error_codes.py`.

## Local test setup

The test client runs outside the cluster and reaches internal services through
port-forwards on ports 5050, 50051, and 7070. These forwards must be running
before executing the Python suite.

Generated protobuf Python files are local artifacts and are intentionally
ignored by Git. Recreate them with the `grpc_tools.protoc` command in the
README.

## Deadline test sensitivity

The partial-chain deadline test uses a 5 ms timeout so it remains deterministic
on the local Docker Desktop cluster. Deadline behavior can vary with machine
load, so this threshold should be recalibrated for slower or remote clusters.
