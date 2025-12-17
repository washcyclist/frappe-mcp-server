"""
Bank Clearance MCP tools for updating clearance dates on financial documents.

This module provides tools for updating clearance dates on Payment Entries,
Journal Entries, Bank Transactions, Sales Invoices, and Purchase Invoices
via the wcl_finance Frappe app API.
"""

import json
from typing import Any, Dict, List, Optional

from ..frappe_api import get_client, FrappeApiError
from ..auth import validate_api_credentials


def _format_error_response(error: Exception, operation: str) -> str:
    """Format error response with detailed information."""
    credentials_check = validate_api_credentials()
    
    if not credentials_check["valid"]:
        error_msg = f"Authentication failed: {credentials_check['message']}. "
        error_msg += "API key/secret is the only supported authentication method."
        return error_msg
    
    if isinstance(error, FrappeApiError):
        error_msg = f"Frappe API error: {error}"
        if error.status_code in (401, 403):
            error_msg += " Please check your API key and secret."
        return error_msg
    
    return f"Error in {operation}: {str(error)}"


def register_tools(mcp: Any) -> None:
    """Register bank clearance tools with the MCP server."""
    
    @mcp.tool()
    async def update_clearance_date(
        doctype: str,
        docname: str,
        clearance_date: str
    ) -> str:
        """
        Update the clearance date for a financial document.
        
        This tool updates the clearance_date field on Payment Entry, Journal Entry,
        Bank Transaction, Sales Invoice, or Purchase Invoice documents. It calls
        the wcl_finance.api.update_clearance_date whitelisted method.
        
        Args:
            doctype: The document type. Must be one of: Payment Entry, Journal Entry,
                    Bank Transaction, Sales Invoice, Purchase Invoice
            docname: The document name (e.g., "PE-00001", "ACC-PAY-2024-00001")
            clearance_date: The clearance date in YYYY-MM-DD format (e.g., "2024-12-14")
        
        Returns:
            Success message with updated document info, or error message if the
            update fails due to validation, permissions, or document not found.
        
        Examples:
            - update_clearance_date("Payment Entry", "PE-00001", "2024-12-14")
            - update_clearance_date("Journal Entry", "JV-00001", "2024-12-15")
            - update_clearance_date("Bank Transaction", "BT-00001", "2024-12-16")
        """
        try:
            client = get_client()
            
            # Call the wcl_finance API endpoint
            response = await client.post(
                "api/method/wcl_finance.api.update_clearance_date",
                json_data={
                    "doctype": doctype,
                    "docname": docname,
                    "clearance_date": clearance_date
                }
            )
            
            if "message" in response:
                result = response["message"]
                if isinstance(result, dict) and result.get("success"):
                    return (
                        f"✅ Clearance date updated successfully:\n"
                        f"  Document: {result.get('doctype')} '{result.get('docname')}'\n"
                        f"  Clearance Date: {result.get('clearance_date')}"
                    )
                else:
                    return json.dumps(result, indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except FrappeApiError as api_error:
            if api_error.response_data:
                error_data = api_error.response_data
                
                # Extract server messages for user-friendly errors
                if "_server_messages" in error_data:
                    try:
                        messages = json.loads(error_data["_server_messages"])
                        if messages:
                            msg_data = json.loads(messages[0])
                            user_message = msg_data.get("message", str(api_error))
                            return f"❌ Update failed: {user_message}"
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
                
                if "exception" in error_data:
                    return f"❌ Update failed: {error_data['exception']}"
            
            return f"❌ Update failed: {api_error}"
            
        except Exception as error:
            return _format_error_response(error, "update_clearance_date")

    @mcp.tool()
    async def bulk_update_clearance_dates(
        entries: List[Dict[str, str]]
    ) -> str:
        """
        Update clearance dates for multiple financial documents in a single call.
        
        This tool updates clearance_date fields on multiple documents at once.
        It calls the wcl_finance.api.bulk_update_clearance_dates whitelisted method.
        
        Args:
            entries: List of dictionaries, each containing:
                - doctype: Document type (Payment Entry, Journal Entry, etc.)
                - docname: Document name
                - clearance_date: Clearance date in YYYY-MM-DD format
        
        Returns:
            Summary of successful and failed updates with details.
        
        Example:
            bulk_update_clearance_dates([
                {"doctype": "Payment Entry", "docname": "PE-00001", "clearance_date": "2024-12-14"},
                {"doctype": "Journal Entry", "docname": "JV-00001", "clearance_date": "2024-12-14"},
                {"doctype": "Bank Transaction", "docname": "BT-00001", "clearance_date": "2024-12-15"}
            ])
        """
        try:
            client = get_client()
            
            # Call the wcl_finance API endpoint
            response = await client.post(
                "api/method/wcl_finance.api.bulk_update_clearance_dates",
                json_data={
                    "entries": json.dumps(entries)
                }
            )
            
            if "message" in response:
                result = response["message"]
                if isinstance(result, dict):
                    output_lines = []
                    
                    # Summary
                    success = result.get("success", False)
                    status_icon = "✅" if success else "⚠️"
                    output_lines.append(
                        f"{status_icon} Bulk update {'completed' if success else 'completed with errors'}:"
                    )
                    output_lines.append(
                        f"  Total: {result.get('total', 0)}, "
                        f"Updated: {result.get('updated_count', 0)}, "
                        f"Failed: {result.get('failed_count', 0)}"
                    )
                    
                    # Updated entries
                    updated = result.get("updated", [])
                    if updated:
                        output_lines.append("\nSuccessfully updated:")
                        for entry in updated:
                            output_lines.append(
                                f"  ✓ {entry.get('doctype')} '{entry.get('docname')}' → {entry.get('clearance_date')}"
                            )
                    
                    # Failed entries
                    failed = result.get("failed", [])
                    if failed:
                        output_lines.append("\nFailed updates:")
                        for entry in failed:
                            output_lines.append(
                                f"  ✗ {entry.get('doctype', 'Unknown')} '{entry.get('docname', 'Unknown')}': {entry.get('error', 'Unknown error')}"
                            )
                    
                    return "\n".join(output_lines)
                else:
                    return json.dumps(result, indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except FrappeApiError as api_error:
            if api_error.response_data:
                error_data = api_error.response_data
                
                if "_server_messages" in error_data:
                    try:
                        messages = json.loads(error_data["_server_messages"])
                        if messages:
                            msg_data = json.loads(messages[0])
                            user_message = msg_data.get("message", str(api_error))
                            return f"❌ Bulk update failed: {user_message}"
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
                
                if "exception" in error_data:
                    return f"❌ Bulk update failed: {error_data['exception']}"
            
            return f"❌ Bulk update failed: {api_error}"
            
        except Exception as error:
            return _format_error_response(error, "bulk_update_clearance_dates")

