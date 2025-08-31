"""
Authentication utilities for Frappe API.

This module handles API key/secret validation and provides authentication
helpers for Frappe API interactions.
"""

import os
from typing import Dict, Any


def validate_api_credentials() -> Dict[str, Any]:
    """
    Validate that required API credentials are available.
    
    Returns:
        Dict containing validation status and details
    """
    api_key = os.getenv("FRAPPE_API_KEY")
    api_secret = os.getenv("FRAPPE_API_SECRET")
    
    if not api_key and not api_secret:
        return {
            "valid": False,
            "message": "Both API key and API secret are missing",
            "details": {
                "api_key_available": False,
                "api_secret_available": False,
                "auth_method": "API key/secret (token)"
            }
        }
    elif not api_key:
        return {
            "valid": False,
            "message": "API key is missing", 
            "details": {
                "api_key_available": False,
                "api_secret_available": True,
                "auth_method": "API key/secret (token)"
            }
        }
    elif not api_secret:
        return {
            "valid": False,
            "message": "API secret is missing",
            "details": {
                "api_key_available": True,
                "api_secret_available": False, 
                "auth_method": "API key/secret (token)"
            }
        }
    
    return {
        "valid": True,
        "message": "API credentials are properly configured",
        "details": {
            "api_key_available": True,
            "api_secret_available": True,
            "auth_method": "API key/secret (token)"
        }
    }


def get_api_credentials() -> Dict[str, str]:
    """
    Get API credentials from environment variables.
    
    Returns:
        Dict containing api_key and api_secret
        
    Raises:
        ValueError: If credentials are missing
    """
    api_key = os.getenv("FRAPPE_API_KEY")
    api_secret = os.getenv("FRAPPE_API_SECRET")
    
    if not api_key or not api_secret:
        validation = validate_api_credentials()
        raise ValueError(f"Authentication failed: {validation['message']}")
    
    return {
        "api_key": api_key,
        "api_secret": api_secret
    }