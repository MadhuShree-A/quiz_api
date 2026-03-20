from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Wraps DRF's default handler to return a consistent error envelope:
    {
        "error": {
            "code": "...",
            "message": "...",
            "details": { ... }   # optional field-level errors
        }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_payload = {
            'error': {
                'code': _status_to_code(response.status_code),
                'message': _extract_message(response.data),
                'details': response.data if isinstance(response.data, dict) else {},
            }
        }
        response.data = error_payload
        return response

    # Unhandled exception — log it, return 500
    logger.exception('Unhandled exception in view: %s', exc)
    return Response(
        {'error': {'code': 'internal_server_error', 'message': 'An unexpected error occurred.'}},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def _status_to_code(status_code: int) -> str:
    mapping = {
        400: 'bad_request',
        401: 'unauthorized',
        403: 'forbidden',
        404: 'not_found',
        405: 'method_not_allowed',
        409: 'conflict',
        429: 'too_many_requests',
        500: 'internal_server_error',
    }
    return mapping.get(status_code, f'http_{status_code}')


def _extract_message(data) -> str:
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        # Return first field error
        for key, val in data.items():
            if isinstance(val, list) and val:
                return f"{key}: {val[0]}"
        return 'Validation failed.'
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data)


def handler_404(request, exception=None):
    return JsonResponse(
        {'error': {'code': 'not_found', 'message': 'The requested resource was not found.'}},
        status=404,
    )


def handler_500(request):
    return JsonResponse(
        {'error': {'code': 'internal_server_error', 'message': 'An unexpected error occurred.'}},
        status=500,
    )
