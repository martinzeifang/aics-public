"""OpenAPI Documentation."""

from flask import Blueprint, jsonify

docs_bp = Blueprint('docs', __name__, url_prefix='/api/docs')


@docs_bp.get('/swagger.json')
def get_swagger():
    """OpenAPI 3.0 Specification."""
    return {
        'openapi': '3.0.0',
        'info': {
            'title': 'AI Compliance Suite Web API',
            'version': '1.0.0',
        },
        'servers': [
            {'url': 'http://localhost:5000'},
            {'url': 'https://api.example.com'},
        ],
        'paths': {
            '/api/auth/login': {
                'post': {
                    'summary': 'User Login',
                    'requestBody': {
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'email': {'type': 'string'},
                                        'password': {'type': 'string'},
                                    }
                                }
                            }
                        }
                    },
                    'responses': {
                        '200': {'description': 'Login successful'}
                    }
                }
            },
            '/api/cra/dashboard': {
                'get': {
                    'summary': 'CRA Dashboard Statistics',
                    'responses': {
                        '200': {'description': 'Dashboard data'}
                    }
                }
            },
        }
    }, 200
