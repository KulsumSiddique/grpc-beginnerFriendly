"""
Deadline propagation tests for CheckoutService.PlaceOrder.

WHY THIS MATTERS
-----------------
PlaceOrder is not a single gRPC call — it's an orchestrator that fans out to
CartService, ProductCatalogService, CurrencyService, ShippingService,
PaymentService, and EmailService in sequence. gRPC deadlines are meant to
propagate through this whole chain: if the *client* sets a 1-second deadline
on PlaceOrder, every downstream call the server makes on the client's behalf
should inherit a shrinking remaining-time budget, not get its own fresh
timeout.

This is a genuinely common real-world bug class: a service respects deadlines
on its own inbound calls but forgets to forward the remaining deadline to the
services *it* calls — meaning a client that gave up waiting can still cause a
payment to be charged seconds later, with no one listening for the result.

WHAT THESE TESTS CHECK
-----------------------
1. An impossibly short deadline fails fast and cleanly (DEADLINE_EXCEEDED),
   rather than hanging or silently succeeding.
2. A short-but-technically-sufficient deadline for the first hop but
   insufficient for the full chain still fails with DEADLINE_EXCEEDED,
   not with a different/misleading error further down the chain.
3. [Documented, not automatable via the public API alone] whether a charge
   was actually issued despite the client giving up — this requires checking
   PaymentService's own logs/state after the client-side failure, and is
   flagged as a manual/observability-based check in findings/.
"""

import time

import grpc
import pytest


class TestDeadlinePropagation:
    def test_impossible_deadline_fails_fast_with_deadline_exceeded(
        self, checkout_channel, sample_order_request
    ):
        """
        A 1-millisecond deadline cannot possibly be met by an orchestrator
        making 5+ downstream calls. Confirm the client sees a clean
        DEADLINE_EXCEEDED, not a hang, not a generic UNKNOWN, and not a
        false-positive success.
        """
        from generated import demo_pb2_grpc

        stub = demo_pb2_grpc.CheckoutServiceStub(checkout_channel)

        start = time.monotonic()
        with pytest.raises(grpc.RpcError) as exc_info:
            stub.PlaceOrder(sample_order_request, timeout=0.001)
        elapsed = time.monotonic() - start

        assert exc_info.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED
        # The client should give up close to the requested deadline, not
        # after the full chain would have taken to complete unassisted.
        assert elapsed < 1.0, (
            f"Expected fast client-side failure near the 1ms deadline, "
            f"took {elapsed:.3f}s instead — deadline may not be enforced "
            f"client-side as expected."
        )

    def test_partial_chain_deadline_fails_with_deadline_exceeded_not_downstream_error(
        self, checkout_channel, sample_order_request
    ):
        """
        A deadline long enough for the first hop or two (e.g. CartService,
        ProductCatalogService) but too short for the full chain including
        PaymentService should still surface as DEADLINE_EXCEEDED to the
        client — not as some other error code that leaks an internal
        implementation detail of which downstream call happened to be
        running when time ran out.

        Tune this value against your own environment: run the happy-path
        test first, note its typical latency, and set this to roughly
        30-50% of that.
        """
        from generated import demo_pb2_grpc

        stub = demo_pb2_grpc.CheckoutServiceStub(checkout_channel)

        with pytest.raises(grpc.RpcError) as exc_info:
            # Keep this below the normal local end-to-end latency so the
            # test remains deterministic on a fast Docker Desktop cluster.
            stub.PlaceOrder(sample_order_request, timeout=0.005)  # 5ms

        assert exc_info.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED, (
            f"Expected DEADLINE_EXCEEDED for a partial-chain timeout, got "
            f"{exc_info.value.code()} instead. This may indicate the "
            f"deadline is not propagating cleanly through the whole call "
            f"chain — worth investigating which hop surfaced this error."
        )

    def test_sufficient_deadline_succeeds(
        self, checkout_channel, sample_order_request
    ):
        """
        Control/baseline case: a generous deadline should let the full
        chain complete normally. This exists so that a failure in the two
        tests above can be interpreted as a real deadline-propagation
        issue, not just "the service is broken" — if this test also fails,
        the problem is unrelated to deadline handling.
        """
        from generated import demo_pb2_grpc

        stub = demo_pb2_grpc.CheckoutServiceStub(checkout_channel)

        response = stub.PlaceOrder(sample_order_request, timeout=10.0)
        assert response.order.order_id != ""


# ---------------------------------------------------------------------------
# MANUAL / OBSERVABILITY-BASED CHECK (documented here, not automated)
# ---------------------------------------------------------------------------
#
# The public PlaceOrder API alone cannot confirm whether a downstream charge
# was actually issued after the client already received DEADLINE_EXCEEDED.
# To verify this properly:
#
#   1. Run test_impossible_deadline_fails_fast_with_deadline_exceeded above.
#   2. Immediately check PaymentService's logs (docker-compose logs paymentservice)
#      for a transaction matching sample_order_request's card/amount.
#   3. If a charge was logged despite the client-side failure, this is a real
#      finding: the client has no way to know money moved, and any retry
#      logic built on "DEADLINE_EXCEEDED means nothing happened" would be
#      unsafe here (a classic gRPC at-most-once vs at-least-once semantics
#      gap worth flagging explicitly to engineering).
#
# This gap — and whatever the actual observed behavior turns out to be —
# should be written up in findings/BUGS_AND_OBSERVATIONS.md with the log
# excerpt as evidence, since it's the single most senior-level finding this
# test suite can produce.
