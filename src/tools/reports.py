"""
Report MCP tools for Frappe report operations.

This module provides tools for generating and exporting
Frappe reports in various formats.
"""

from typing import Any, Dict, List, Optional, Union
import json

from ..frappe_api import get_client, FrappeApiError
from ..auth import validate_api_credentials
from .filter_parser import format_filters_for_api, FILTER_SYNTAX_DOCS


def _format_error_response(error: Exception, operation: str) -> str:
    """Format error response with detailed information."""
    credentials_check = validate_api_credentials()
    
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
    """Register report tools with the MCP server."""
    
    @mcp.tool()
    async def run_query_report(
        report_name: str,
        filters: Optional[str] = None
    ) -> str:
        """
        Execute a Frappe query report with filters.
        
        Args:
            report_name: Name of the report to run
            filters: Filter string (optional). Uses custom syntax to bypass MCP validation issues.
        
        Filter Syntax: Use the same string-based syntax as count_documents and list_documents.
        Examples: "status:Open", "date:>=:2025-01-01", "status:in:Open|Working"
        """
        try:
            client = get_client()
            
            # Prepare request data
            parsed_filters = format_filters_for_api(filters) or {}
            request_data = {
                "cmd": "frappe.desk.query_report.run",
                "report_name": report_name,
                "filters": json.dumps(parsed_filters),
                "ignore_prepared_report": 1
            }
            
            # Run the report
            response = await client.post("api/method/frappe.desk.query_report.run", json_data=request_data)
            
            if "message" in response:
                result = response["message"]
                
                # Format the response
                columns = result.get("columns", [])
                data = result.get("result", [])
                
                formatted_result = {
                    "report_name": report_name,
                    "columns": columns,
                    "data": data,
                    "row_count": len(data)
                }
                
                return json.dumps(formatted_result, indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "run_query_report")
    
    @mcp.tool()
    async def get_report_meta(report_name: str) -> str:
        """
        Get metadata for a specific report including columns and filters.
        
        Args:
            report_name: Name of the report to get metadata for
        """
        try:
            client = get_client()
            
            # Get report document
            response = await client.get(f"api/resource/Report/{report_name}")
            
            if "data" in response:
                report_data = response["data"]
                
                # Format metadata
                metadata = {
                    "report_name": report_name,
                    "report_type": report_data.get("report_type"),
                    "module": report_data.get("module"),
                    "is_standard": report_data.get("is_standard"),
                    "ref_doctype": report_data.get("ref_doctype"),
                    "query": report_data.get("query"),
                    "columns": report_data.get("columns", []),
                    "filters": report_data.get("filters", [])
                }
                
                return json.dumps(metadata, indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "get_report_meta")
    
    @mcp.tool()
    async def list_reports(
        module: Optional[str] = None,
        limit: Optional[int] = 50
    ) -> str:
        """
        Get a list of all available reports in the system.
        
        Args:
            module: Filter reports by module (optional)
            limit: Maximum number of reports to return (default: 50)
        """
        try:
            client = get_client()
            
            # Build parameters
            params = {
                "fields": json.dumps(["name", "report_type", "module", "is_standard", "ref_doctype"]),
                "limit": str(limit),
                "order_by": "name"
            }
            
            if module:
                params["filters"] = json.dumps({"module": module})
            
            # Get reports list
            response = await client.get("api/resource/Report", params=params)
            
            if "data" in response:
                reports = response["data"]
                count = len(reports)
                filter_text = f" in module '{module}'" if module else ""
                return f"Found {count} reports{filter_text}:\n\n" + json.dumps(reports, indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "list_reports")
    
    @mcp.tool()
    async def run_doctype_report(
        doctype: str,
        fields: Optional[List[str]] = None,
        filters: Optional[str] = None,
        limit: Optional[int] = 100,
        order_by: Optional[str] = None
    ) -> str:
        """
        Run a standard doctype report with filters and sorting.
        
        Args:
            doctype: DocType to generate report for
            fields: Fields to include in report (optional)
            filters: Filter string (optional). Uses custom syntax to bypass MCP validation issues.
            limit: Maximum number of records (default: 100)
            order_by: Field to order by (optional)
        
        Filter Syntax: Use the same string-based syntax as count_documents and list_documents.
        Examples: "status:Open", "date:>=:2025-01-01", "status:in:Open|Working"
        """
        try:
            client = get_client()
            
            # Build parameters
            params = {}
            if fields:
                params["fields"] = json.dumps(fields)
            parsed_filters = format_filters_for_api(filters)
            if parsed_filters:
                params["filters"] = json.dumps(parsed_filters)
            if limit:
                params["limit"] = str(limit)
            if order_by:
                params["order_by"] = order_by
            
            # Get doctype data
            response = await client.get(f"api/resource/{doctype}", params=params)
            
            if "data" in response:
                data = response["data"]
                count = len(data)
                
                formatted_result = {
                    "doctype": doctype,
                    "row_count": count,
                    "data": data
                }
                
                return json.dumps(formatted_result, indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "run_doctype_report")
    
    @mcp.tool()
    async def get_financial_statements(
        report_type: str,
        company: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        periodicity: Optional[str] = "Yearly"
    ) -> str:
        """
        Get standard financial reports (P&L, Balance Sheet, Cash Flow).
        
        Args:
            report_type: Type of financial statement 
                       ('Profit and Loss Statement', 'Balance Sheet', 'Cash Flow')
            company: Company name
            from_date: Start date (YYYY-MM-DD format, optional)
            to_date: End date (YYYY-MM-DD format, optional) 
            periodicity: Periodicity (Monthly, Quarterly, Half-Yearly, Yearly)
        """
        try:
            client = get_client()
            
            # Build filters for financial report
            filters = {
                "company": company,
                "periodicity": periodicity
            }
            
            if from_date:
                filters["from_date"] = from_date
            if to_date:
                filters["to_date"] = to_date
            
            # Prepare request data
            request_data = {
                "cmd": "frappe.desk.query_report.run",
                "report_name": report_type,
                "filters": json.dumps(filters),
                "ignore_prepared_report": 1
            }
            
            # Run the financial report
            response = await client.post("api/method/frappe.desk.query_report.run", json_data=request_data)
            
            if "message" in response:
                result = response["message"]
                
                formatted_result = {
                    "report_type": report_type,
                    "company": company,
                    "filters": filters,
                    "columns": result.get("columns", []),
                    "data": result.get("result", [])
                }
                
                return json.dumps(formatted_result, indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "get_financial_statements")
    
    @mcp.tool()
    async def get_report_columns(
        report_name: str,
        filters: Optional[str] = None
    ) -> str:
        """
        Get the column structure for a specific report.
        
        Args:
            report_name: Name of the report
            filters: Filter string (optional). Uses custom syntax to bypass MCP validation issues.
        
        Filter Syntax: Use the same string-based syntax as count_documents and list_documents.
        Examples: "status:Open", "date:>=:2025-01-01", "status:in:Open|Working"
        """
        try:
            client = get_client()
            
            # Get report columns using the report.get_columns method
            parsed_filters = format_filters_for_api(filters) or {}
            request_data = {
                "cmd": "frappe.desk.query_report.get_columns",
                "report_name": report_name,
                "filters": json.dumps(parsed_filters)
            }
            
            response = await client.post("api/method/frappe.desk.query_report.get_columns", json_data=request_data)
            
            if "message" in response:
                columns = response["message"]
                
                formatted_result = {
                    "report_name": report_name,
                    "columns": columns
                }
                
                return json.dumps(formatted_result, indent=2)
            else:
                # Fallback: get columns from report metadata
                meta_response = await client.get(f"api/resource/Report/{report_name}")
                if "data" in meta_response:
                    columns = meta_response["data"].get("columns", [])
                    return json.dumps({"report_name": report_name, "columns": columns}, indent=2)
                else:
                    return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "get_report_columns")