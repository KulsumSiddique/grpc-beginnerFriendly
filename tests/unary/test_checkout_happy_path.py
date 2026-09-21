"""
Happy-path unary tests for CheckoutService.PlaceOrder and PaymentService.Charge.

These establish the baseline "does the basic contract work" coverage before
layering on error-code, chain, and performance testing. Every assertion here
should pass against an unmodified, healthy local Online Boutique deployment.
"""

import pytest


class TestCheckoutHappyPath:
    def test_place_order_returns_order_with_id(
        self, checkout_channel, sample_order_request
    ):
        from generated import demo_pb2_grpc

        stub = demo_pb2_grpc.CheckoutServiceStub(checkout_channel)
        response = stub.PlaceOrder(sample_order_request, timeout=10.0)

        assert response.order.order_id != ""

    def test_place_order_returns_shipping_tracking_id(
        self, checkout_channel, sample_order_request
    ):
        from generated import demo_pb2_grpc

        stub = demo_pb2_grpc.CheckoutServiceStub(checkout_channel)
        response = stub.PlaceOrder(sample_order_request, timeout=10.0)

        assert response.order.shipping_tracking_id != "", (
            "Expected a shipping tracking ID to confirm ShippingService "
            "was actually invoked as part of the chain, not skipped."
        )

    def test_place_order_returns_expected_currency(
        self, checkout_channel, sample_order_request
    ):
        from generated import demo_pb2_grpc

        stub = demo_pb2_grpc.CheckoutServiceStub(checkout_channel)
        response = stub.PlaceOrder(sample_order_request, timeout=10.0)

        # Confirms CurrencyService.Convert was applied correctly rather
        # than the order silently passing through in the wrong currency.
        assert response.order.shipping_cost.currency_code == \
            sample_order_request.user_currency


class TestPaymentHappyPath:
    def test_charge_valid_card_returns_transaction_id(self, payment_channel):
        from generated import demo_pb2, demo_pb2_grpc

        stub = demo_pb2_grpc.PaymentServiceStub(payment_channel)
        request = demo_pb2.ChargeRequest(
            amount=demo_pb2.Money(currency_code="USD", units=100, nanos=0),
            credit_card=demo_pb2.CreditCardInfo(
                credit_card_number="4432801561520454",
                credit_card_cvv=672,
                credit_card_expiration_year=2030,
                credit_card_expiration_month=1,
            ),
        )
        response = stub.Charge(request)

        assert response.transaction_id != ""

    def test_charge_zero_amount_still_returns_transaction_id(
        self, payment_channel
    ):
        """
        Edge case worth checking explicitly: does the mock PaymentService
        treat a $0.00 charge as valid (e.g. a fully-discounted order), or
        reject it? Document whichever behavior is observed — either is
        potentially correct depending on business rules, but it should be
        a deliberate decision, not an untested edge case.
        """
        from generated import demo_pb2, demo_pb2_grpc

        stub = demo_pb2_grpc.PaymentServiceStub(payment_channel)
        request = demo_pb2.ChargeRequest(
            amount=demo_pb2.Money(currency_code="USD", units=0, nanos=0),
            credit_card=demo_pb2.CreditCardInfo(
                credit_card_number="4432801561520454",
                credit_card_cvv=672,
                credit_card_expiration_year=2030,
                credit_card_expiration_month=1,
            ),
        )
        response = stub.Charge(request)

        assert response.transaction_id != ""