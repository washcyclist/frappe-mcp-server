"""
Frappe API client for HTTP requests.

This module provides an async HTTP client for interacting with Frappe APIs,
including authentication, error handling, and response processing.
"""

import os
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin
import json

import httpx
from pydantic import BaseModel, Field

from .auth import get_api_credentials


class FrappeApiError(Exception):
    """Custom exception for Frappe API errors."""
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class FrappeApiClient:
    """Async HTTP client for Frappe API interactions."""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("FRAPPE_BASE_URL", "")
        if not self.base_url:
            raise ValueError("FRAPPE_BASE_URL environment variable is required")
        
        # Ensure base_url ends with /
        if not self.base_url.endswith("/"):
            self.base_url += "/"
        
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client instance."""
        if self._client is None:
            credentials = get_api_credentials()
            auth = httpx.BasicAuth(
                username=credentials["api_key"],
                password=credentials["api_secret"]
            )
            
            self._client = httpx.AsyncClient(
                auth=auth,
                timeout=httpx.Timeout(30.0),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
        
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "FrappeApiClient":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        return urljoin(self.base_url, endpoint.lstrip("/"))
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request and handle response."""
        client = await self._get_client()
        url = self._build_url(endpoint)
        
        try:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_data
            )
            
            # Try to parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError:
                response_data = {"text": response.text}
            
            # Check for HTTP errors
            if response.status_code >= 400:
                error_message = f"HTTP {response.status_code}"
                if isinstance(response_data, dict) and "message" in response_data:
                    error_message += f": {response_data['message']}"
                
                raise FrappeApiError(
                    message=error_message,
                    status_code=response.status_code,
                    response_data=response_data
                )
            
            return response_data
            
        except httpx.HTTPError as e:
            raise FrappeApiError(f"HTTP request failed: {str(e)}")
    
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make GET request."""
        return await self._request("GET", endpoint, params=params)
    
    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make POST request."""
        return await self._request("POST", endpoint, data=data, json_data=json_data)
    
    async def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make PUT request."""
        return await self._request("PUT", endpoint, data=data, json_data=json_data)
    
    async def delete(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make DELETE request."""
        return await self._request("DELETE", endpoint, params=params)


# Global client instance
_client_instance: Optional[FrappeApiClient] = None


def get_client() -> FrappeApiClient:
    """Get singleton Frappe API client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = FrappeApiClient()
    return _client_instance