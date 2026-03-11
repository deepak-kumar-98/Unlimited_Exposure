from django.core.exceptions import ObjectDoesNotExist
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import traceback

def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    # If response is None, it means the exception wasn't handled by DRF natively
    # This prevents the server from returning an HTML 500 error page, and instead returns clean JSON
    if response is None:
        if isinstance(exc, ObjectDoesNotExist):
            return Response(
                {
                    'error': 'The requested resource was not found.',
                    'details': str(exc)
                }, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Log the actual error to the console for debugging
        print(f"UNHANDLED EXCEPTION in {context['view']}:")
        print(traceback.format_exc())

        return Response(
            {
                'error': 'An unexpected server error occurred. Please try again later.',
                'details': str(exc)
            }, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return response
