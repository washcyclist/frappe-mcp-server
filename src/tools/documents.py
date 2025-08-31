"""
Document MCP tools for Frappe CRUD operations.

This module provides tools for creating, reading, updating, deleting,
and listing Frappe documents.
"""

from typing import Any, Dict, List, Optional, Union
import json

from ..frappe_api import get_client, FrappeApiError
from ..auth import validate_api_credentials


def _format_error_response(error: Exception, operation: str) -> str:
    """Format error response with detailed information."""
    credentials_check = validate_api_credentials()
    
    # Build diagnostic information
    diagnostics = [
        f"Error in {operation}",
        f"Error type: {type(error).__name__}",
        f"Is FrappeApiError: {isinstance(error, FrappeApiError)}",
        f"API Key available: {credentials_check['details']['api_key_available']}",
        f"API Secret available: {credentials_check['details']['api_secret_available']}"
    ]
    
    # Check for missing credentials first
    if not credentials_check["valid"]:
        error_msg = f"Authentication failed: {credentials_check['message']}. "
        error_msg += "API key/secret is the only supported authentication method."
        return error_msg
    
    # Handle FrappeApiError
    if isinstance(error, FrappeApiError):
        error_msg = f"Frappe API error: {error}"
        if error.status_code in (401, 403):
            error_msg += " Please check your API key and secret."
        return error_msg
    
    # Default error handling
    return f"Error in {operation}: {str(error)}"


def register_tools(mcp: Any) -> None:
    """Register document tools with the MCP server."""
    
    @mcp.tool()
    async def create_document(
        doctype: str,
        values: Dict[str, Any]
    ) -> str:
        """
        Create a new document in Frappe.
        
        Args:
            doctype: DocType name
            values: Document field values. Required fields must be included.
                   For Link fields, provide the exact document name.
                   For Table fields, provide an array of row objects.
        """
        try:
            client = get_client()
            
            # Create the document data
            doc_data = {
                "doctype": doctype,
                **values
            }
            
            # Make API request to create document
            response = await client.post(
                f"api/resource/{doctype}",
                json_data=doc_data
            )
            
            if "data" in response:
                doc = response["data"]
                return f"Document created successfully: {doctype} '{doc.get('name', 'Unknown')}'"
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "create_document")
    
    @mcp.tool()
    async def get_document(
        doctype: str,
        name: str
    ) -> str:
        """
        Retrieve a document from Frappe.
        
        Args:
            doctype: DocType name
            name: Document name (case-sensitive)
        """
        try:
            client = get_client()
            
            # Make API request to get document
            response = await client.get(f"api/resource/{doctype}/{name}")
            
            if "data" in response:
                return json.dumps(response["data"], indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "get_document")
    
    @mcp.tool()
    async def update_document(
        doctype: str,
        name: str,
        values: Dict[str, Any]
    ) -> str:
        """
        Update an existing document in Frappe.
        
        Args:
            doctype: DocType name
            name: Document name (case-sensitive)
            values: Field values to update
        """
        try:
            client = get_client()
            
            # Make API request to update document
            response = await client.put(
                f"api/resource/{doctype}/{name}",
                json_data=values
            )
            
            if "data" in response:
                doc = response["data"]
                return f"Document updated successfully: {doctype} '{doc.get('name', name)}'"
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "update_document")
    
    @mcp.tool()
    async def delete_document(
        doctype: str,
        name: str
    ) -> str:
        """
        Delete a document from Frappe.
        
        Args:
            doctype: DocType name
            name: Document name (case-sensitive)
        """
        try:
            client = get_client()
            
            # Make API request to delete document
            response = await client.delete(f"api/resource/{doctype}/{name}")
            
            if response.get("message") == "ok":
                return f"Document deleted successfully: {doctype} '{name}'"
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "delete_document")
    
    @mcp.tool()
    async def list_documents(
        doctype: str,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None
    ) -> str:
        """
        List documents from Frappe with filters.
        
        Args:
            doctype: DocType name
            filters: Filters to apply (optional). Simple format: {"field": "value"} 
                    or with operators: {"field": [">", "value"]}. 
                    Available operators: =, !=, <, >, <=, >=, like, not like, in, not in, is, is not, between.
            fields: List of fields to return (optional)
            limit: Maximum number of records to return (optional)
            order_by: Field to order by (optional, can include 'desc' like 'creation desc')
        """
        try:
            client = get_client()
            
            # Build query parameters
            params = {}
            if filters:
                params["filters"] = json.dumps(filters)
            if fields:
                params["fields"] = json.dumps(fields)
            if limit:
                params["limit"] = str(limit)
            if order_by:
                params["order_by"] = order_by
            
            # Make API request to list documents
            response = await client.get(f"api/resource/{doctype}", params=params)
            
            if "data" in response:
                documents = response["data"]
                count = len(documents)
                return f"Found {count} {doctype} documents:\n\n" + json.dumps(documents, indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "list_documents")
    
    @mcp.tool()
    async def call_method(
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Execute a whitelisted Frappe method.
        
        Args:
            method: Method name to call (whitelisted)
            params: Parameters to pass to the method (optional)
        """
        try:
            client = get_client()
            
            # Prepare request data
            request_data = {"cmd": method}
            if params:
                request_data.update(params)
            
            # Make API request to call method
            response = await client.post("api/method", json_data=request_data)
            
            if "message" in response:
                return json.dumps(response["message"], indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "call_method")
    
    @mcp.tool()
    async def count_documents(
        doctype: str,
        filters: Optional[str] = None
    ) -> str:
        """
        Count documents in Frappe with optional filters.
        
        This tool addresses the filtering limitation that existed in previous implementations
        by using Frappe's native count functionality via the REST API with a custom filter language.
        
        Args:
            doctype: DocType name
            filters: Filter string (optional). Uses custom syntax to bypass MCP validation issues.
        
        Filter Syntax:
            - Simple equality: "field:value" -> {"field": "value"}
            - Operators: "field:operator:value" -> {"field": ["operator", value]}
            - Multiple filters: "field1:value1,field2:operator:value2"
            
        Supported Operators:
            - Equality: = (default), !=
            - Comparison: <, >, <=, >=  
            - Pattern: like, not_like (use % for wildcards)
            - Lists: in, not_in (separate values with |)
            - Null checks: is:null, is:not_null, is_not:null
            - Ranges: between (separate values with |)
        
        Examples:
            - count_documents("User") -> Count all users
            - count_documents("Bank Transaction", "status:Unreconciled") -> Count unreconciled transactions
            - count_documents("Bank Transaction", "unallocated_amount:>:0") -> Count with unallocated amount
            - count_documents("Task", "status:in:Open|Working|Pending") -> Count tasks with multiple statuses
            - count_documents("User", "name:like:%admin%") -> Count users with 'admin' in name  
            - count_documents("Payment Entry", "posting_date:between:2025-01-01|2025-12-31") -> Count in date range
            - count_documents("Contact", "phone:is:not_null") -> Count contacts with phone numbers
        """
        def _parse_filter_string(filter_str: str) -> Dict[str, Any]:
            """
            Parse filter string into Frappe filter format.
            
            Supported operators: =, !=, <, >, <=, >=, like, not_like, in, not_in, is, is_not, between
            
            Examples:
            - "status:Unreconciled" -> {"status": "Unreconciled"}
            - "amount:>:100" -> {"amount": [">", 100]}
            - "name:like:%test%" -> {"name": ["like", "%test%"]}
            - "status:in:Open|Closed" -> {"status": ["in", ["Open", "Closed"]]}
            - "date:between:2025-01-01|2025-12-31" -> {"date": ["between", ["2025-01-01", "2025-12-31"]]}
            - "field:is:null" -> {"field": ["is", "set"]} or {"field": ["is", "not set"]}
            """
            filters_dict = {}
            
            # Handle multiple filters separated by commas
            filter_parts = filter_str.split(',')
            
            for part in filter_parts:
                part = part.strip()
                if ':' in part:
                    # Split on first two colons to handle operators with underscores
                    components = part.split(':', 2)
                    
                    if len(components) >= 3:
                        # Format: field:operator:value(s)
                        field, operator, value_str = components[0].strip(), components[1].strip(), components[2]
                        
                        # Handle special operators
                        if operator.lower() in ['in', 'not_in']:
                            # Handle list values separated by |
                            values = [v.strip() for v in value_str.split('|')]
                            # Convert numbers in list
                            converted_values = []
                            for v in values:
                                converted_values.append(_convert_value(v))
                            filters_dict[field] = [operator.replace('_', ' '), converted_values]
                            
                        elif operator.lower() == 'between':
                            # Handle range values separated by |
                            range_values = [v.strip() for v in value_str.split('|')]
                            if len(range_values) == 2:
                                converted_range = [_convert_value(v) for v in range_values]
                                filters_dict[field] = [operator, converted_range]
                            else:
                                raise ValueError(f"Between operator requires exactly 2 values separated by |, got: {value_str}")
                                
                        elif operator.lower() in ['is', 'is_not']:
                            # Handle null checks: is:null, is:not_null, is_not:null, etc.
                            if value_str.lower() in ['null', 'none', 'empty']:
                                filters_dict[field] = [operator.replace('_', ' '), "not set"]
                            elif value_str.lower() in ['not_null', 'not_none', 'not_empty']:
                                filters_dict[field] = [operator.replace('_', ' '), "set"]
                            else:
                                filters_dict[field] = [operator.replace('_', ' '), _convert_value(value_str)]
                                
                        elif operator.lower() == 'not_like':
                            # Handle not like operator  
                            filters_dict[field] = ["not like", value_str]
                            
                        else:
                            # Standard operators: =, !=, <, >, <=, >=, like
                            filters_dict[field] = [operator, _convert_value(value_str)]
                            
                    elif len(components) == 2:
                        # Simple field:value format (implies equality)
                        field, value_str = components[0].strip(), components[1]
                        filters_dict[field] = _convert_value(value_str)
                        
            return filters_dict
        
        def _convert_value(value_str: str):
            """Convert string value to appropriate Python type."""
            value_str = value_str.strip()
            
            # Try to convert to number
            try:
                if '.' in value_str:
                    return float(value_str)
                else:
                    return int(value_str)
            except ValueError:
                pass
                
            # Handle boolean values
            if value_str.lower() in ['true', 'yes', '1']:
                return True
            elif value_str.lower() in ['false', 'no', '0']:
                return False
                
            # Return as string
            return value_str
        
        try:
            client = get_client()
            
            # Build query parameters for counting
            params = {
                "fields": json.dumps(["count(name) as count"])
            }
            
            # Parse and add filters if provided
            parsed_filters = None
            if filters:
                parsed_filters = _parse_filter_string(filters)
                params["filters"] = json.dumps(parsed_filters)
            
            # Make API request to count documents
            response = await client.get(f"api/resource/{doctype}", params=params)
            
            if "data" in response and response["data"]:
                count_result = response["data"][0]
                count = count_result.get("count", 0)
                
                # Format response based on whether filters were applied
                if parsed_filters:
                    return f"Found {count} {doctype} documents matching filters: {filters}"
                else:
                    return f"Found {count} {doctype} documents total"
            else:
                return f"No data returned for {doctype} count"
                
        except Exception as error:
            return _format_error_response(error, "count_documents")
    
    @mcp.tool()
    async def test_hardcoded_filter(doctype: str) -> str:
        """
        Test hardcoded filter to verify Frappe API filtering works.
        This bypasses all parameter validation issues.
        """
        try:
            client = get_client()
            
            # Hard-code filters for testing
            if doctype == "Bank Transaction":
                # Test unreconciled filter
                test_filters = {"status": "Unreconciled"}
                params = {
                    "fields": json.dumps(["count(name) as count"]),
                    "filters": json.dumps(test_filters)
                }
                
                response = await client.get(f"api/resource/{doctype}", params=params)
                
                if "data" in response and response["data"]:
                    count = response["data"][0].get("count", 0)
                    return f"HARDCODED TEST: Found {count} {doctype} with status='Unreconciled'"
                else:
                    return f"HARDCODED TEST: No data returned for {doctype}"
            else:
                return f"HARDCODED TEST: Only supports 'Bank Transaction' doctype for now"
                
        except Exception as error:
            return f"HARDCODED TEST ERROR: {error}"