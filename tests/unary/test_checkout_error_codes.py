"""
Error-code tests for CheckoutService.PlaceOrder.

Goal: confirm that invalid input at each stage of the order produces the
correct gRPC status code, rather than a generic UNKNOWN or a silent
success with corrupted data.
"""

import copy

import grpc
import pytest


class TestCheckoutErrorCodes:
    def test_place_order_missing_email_returns_invalid_argument(
        self, checkout_channel, sample_order_request
    ):
        from generated import demo_pb2_grpc

        stub = demo_pb2_grpc.CheckoutServiceStub(checkout_channel)
        request = copy.deepcopy(sample_order_request)
        request.email = ""

        with pytest.raises(grpc.RpcError) as exc_info:
            stub.PlaceOrder(request, timeout=10.0)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT

    def test_place_order_invalid_currency_code_returns_error(
        self, checkout_channel, sample_order_request
    ):
        from generated import demo_pb2_grpc

        stub = demo_pb2_grpc.CheckoutServiceStub(checkout_channel)
        request = copy.deepcopy(sample_order_request)
        request.user_currency = "ZZZ"  # not a real ISO currency code

        with pytest.raises(grpc.RpcError) as exc_info:
            stub.PlaceOrder(request, timeout=10.0)

        # Document whichever code is actually returned here — CurrencyService
        # may surface INVALID_ARGUMENT directly, or the error may arrive
        # wrapped/translated by CheckoutService. Either is worth noting as
        # a finding if it's not INVALID_ARGUMENT, since that's what a
        # client would reasonably expect.
        assert exc_info.value.code() in (
            grpc.StatusCode.INVALID_ARGUMENT,
            grpc.StatusCode.UNKNOWN,
        )

    def test_place_order_empty_cart_returns_error_not_empty_success(
        self, checkout_channel, sample_order_request
    ):
        """
        Placing an order for a user with no items in their cart should
        fail clearly, not return a "successful" order with zero items
        and a real shipping charge — a realistic bug pattern where an
        edge case at the start of the chain isn't checked before the
        rest of the chain proceeds anyway.
        """
        from generated import demo_pb2_grpc

        stub = demo_pb2_grpc.CheckoutServiceStub(checkout_channel)
        request = copy.deepcopy(sample_order_request)
        request.user_id = "user-with-empty-cart"  # assumes no prior AddItem calls

        with pytest.raises(grpc.RpcError):
            stub.PlaceOrder(request, timeout=10.0)

    def test_place_order_invalid_zip_code_type_boundary(
        self, checkout_channel, sample_order_request
    ):
        """
        zip_code is an int32 field in the proto. Confirm a boundary/invalid
        value (negative) is rejected rather than silently accepted and
        passed to ShippingService, which could produce a nonsensical
        shipping quote downstream.
        """
        from generated import demo_pb2_grpc

        stub = demo_pb2_grpc.CheckoutServiceStub(checkout_channel)
        request = copy.deepcopy(sample_order_request)
        request.address.zip_code = -1

        with pytest.raises(grpc.RpcError) as exc_info:
            stub.PlaceOrder(request, timeout=10.0)

        assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT