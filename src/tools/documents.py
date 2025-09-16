"""
Document MCP tools for Frappe CRUD operations.

This module provides tools for creating, reading, updating, deleting,
and listing Frappe documents.
"""

from typing import Any, Dict, List, Optional, Union
import json

from ..frappe_api import get_client, FrappeApiError
from ..auth import validate_api_credentials
from .filter_parser import format_filters_for_api, FILTER_SYNTAX_DOCS


def _extract_linked_docs_from_error(error_message: str) -> List[Dict[str, str]]:
    """
    Extract linked document information from Frappe error messages.
    
    Frappe's LinkExistsError and similar messages often contain specific information
    about which documents are linked, which we can parse directly.
    """
    import re
    linked_docs = []
    
    # Common patterns in Frappe error messages for linked documents
    patterns = [
        # "is linked with DocType <a href="...">Name</a>"
        r'is linked with (\w+(?:\s+\w+)*)\s+<a[^>]*>([^<]+)</a>',
        # "Cannot delete ... because ... is linked with DocType Name"
        r'is linked with (\w+(?:\s+\w+)*)\s+([A-Z0-9-]+)',
        # "referenced by DocType: Name"
        r'referenced by (\w+(?:\s+\w+)*):?\s+([A-Z0-9-]+)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, error_message, re.IGNORECASE)
        for match in matches:
            doctype, name = match
            # Clean up doctype (remove extra spaces, standardize)
            doctype = ' '.join(doctype.split())
            linked_docs.append({
                "doctype": doctype,
                "name": name,
                "source": "error_message"
            })
    
    return linked_docs


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
        
        This tool handles document deletion with comprehensive error handling,
        providing detailed feedback about why deletions fail and actionable
        guidance for resolving common deletion blockers.
        
        Args:
            doctype: DocType name
            name: Document name (case-sensitive)
            
        Returns:
            Success message if deleted, or detailed error information with
            corrective actions for linked documents, permissions, or constraints.
        """
        try:
            client = get_client()
            
            # First, get the current document to check its status and understand constraints
            try:
                doc_response = await client.get(f"api/resource/{doctype}/{name}")
                doc_data = doc_response.get("data", {})
                current_docstatus = doc_data.get("docstatus", None)
                
                if current_docstatus is None:
                    return f"Error: Could not retrieve document {doctype} '{name}'. Document may not exist."
                
                # Provide guidance based on document status
                if current_docstatus == 1:
                    return (
                        f"⚠️ Document {doctype} '{name}' is submitted (docstatus=1). "
                        f"Submitted documents cannot be deleted. You must cancel it first using cancel_document, "
                        f"then delete the cancelled document."
                    )
                elif current_docstatus == 2:
                    # Cancelled documents can usually be deleted, but may have constraints
                    pass  # Continue with deletion attempt
                elif current_docstatus == 0:
                    # Draft documents should be deletable, but may have linked documents
                    pass  # Continue with deletion attempt
                    
            except Exception as get_error:
                # Document might not exist, which is fine for deletion
                pass
            
            # Attempt to delete the document
            response = await client.delete(f"api/resource/{doctype}/{name}")
            
            if response.get("message") == "ok":
                return f"✅ Document {doctype} '{name}' successfully deleted."
            else:
                return f"⚠️ Deletion may have succeeded but response format unexpected: {json.dumps(response, indent=2)}"
                
        except FrappeApiError as api_error:
            # Handle specific Frappe API errors with detailed information
            if api_error.response_data:
                error_data = api_error.response_data
                
                # Check for validation errors in the response
                if "exception" in error_data:
                    exception_msg = error_data["exception"]
                    
                    # Extract user-friendly error messages
                    if "ValidationError" in str(exception_msg):
                        # Common deletion validation errors
                        if "linked" in str(exception_msg).lower() or "referenced" in str(exception_msg).lower():
                            # Extract linked document information directly from the error message
                            linked_docs = _extract_linked_docs_from_error(str(exception_msg))
                            if linked_docs:
                                linked_info = "\n".join([f"  - {doc['doctype']} '{doc['name']}'" for doc in linked_docs])
                                return (
                                    f"❌ Deletion failed: Document {doctype} '{name}' cannot be deleted because it is linked to other documents.\n"
                                    f"Blocking document(s):\n{linked_info}\n"
                                    f"To resolve: Delete, cancel, or unlink these documents first, then retry deletion."
                                )
                            else:
                                return (
                                    f"❌ Deletion failed: Document {doctype} '{name}' cannot be deleted because it is linked to other documents. "
                                    f"Error details: {exception_msg}. "
                                    f"To resolve: Find and delete/cancel the documents that reference this one, or remove the links first."
                                )
                        elif "Cannot delete" in str(exception_msg):
                            return (
                                f"❌ Deletion failed: {exception_msg}. "
                                f"This may be due to business rules, data integrity constraints, or linked transactions. "
                                f"Check for related documents that need to be handled first."
                            )
                        elif "submitted" in str(exception_msg).lower():
                            return (
                                f"❌ Deletion failed: Cannot delete submitted documents. "
                                f"Use cancel_document first to cancel {doctype} '{name}', then try deleting the cancelled document."
                            )
                        else:
                            # Generic validation error
                            return f"❌ Validation error: {exception_msg}. Please resolve the validation issues before deleting."
                    
                    elif "PermissionError" in str(exception_msg):
                        return (
                            f"❌ Permission denied: You don't have sufficient permissions to delete {doctype} documents. "
                            f"Contact your system administrator to request Delete permission for {doctype}."
                        )
                    
                    elif "IntegrityError" in str(exception_msg) or "foreign key" in str(exception_msg).lower():
                        return (
                            f"❌ Database constraint violation: Document {doctype} '{name}' cannot be deleted due to foreign key constraints. "
                            f"Error: {exception_msg}. "
                            f"This usually means other records reference this document. Find and handle those references first."
                        )
                    
                    else:
                        # Other exceptions with helpful context
                        return f"❌ Deletion failed: {exception_msg}"
                
                # Check for server messages with more details
                if "_server_messages" in error_data:
                    try:
                        messages = json.loads(error_data["_server_messages"])
                        if messages:
                            msg_data = json.loads(messages[0])
                            user_message = msg_data.get("message", "Unknown error")
                            
                            # Parse common server messages for actionable guidance
                            if "linked" in user_message.lower():
                                return (
                                    f"❌ Deletion failed: {user_message}. "
                                    f"To resolve: Identify and handle the linked documents first, then retry deletion."
                                )
                            else:
                                return f"❌ Deletion failed: {user_message}"
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
            
            # Handle HTTP status codes for additional context
            if api_error.status_code == 403:
                return (
                    f"❌ Access forbidden: You don't have permission to delete {doctype} '{name}'. "
                    f"Contact your administrator for Delete permissions on {doctype}."
                )
            elif api_error.status_code == 404:
                return f"✅ Document {doctype} '{name}' not found - it may already be deleted or never existed."
            elif api_error.status_code == 417:
                # HTTP 417 errors may contain linked document information in the response
                error_text = str(api_error)
                if api_error.response_data:
                    error_text += " " + str(api_error.response_data)
                
                linked_docs = _extract_linked_docs_from_error(error_text)
                if linked_docs:
                    linked_info = "\n".join([f"  - {doc['doctype']} '{doc['name']}'" for doc in linked_docs])
                    return (
                        f"❌ Deletion failed with HTTP 417 error. Found blocking document(s):\n{linked_info}\n"
                        f"These documents may be preventing deletion. Try deleting, cancelling, or unlinking them first."
                    )
                else:
                    return (
                        f"❌ Deletion failed with HTTP 417 error. This may be due to server configuration issues "
                        f"or complex validation constraints. Error: {api_error}. "
                        f"Check for business rule violations, permissions, or linked documents."
                    )
            else:
                return f"❌ Deletion failed: {api_error}"
            
        except Exception as error:
            return _format_error_response(error, "delete_document")
    
    @mcp.tool()
    async def list_documents(
        doctype: str,
        filters: Optional[str] = None,
        fields: Optional[str] = None,
        limit: Optional[str] = None,
        order_by: Optional[str] = None
    ) -> str:
        """
        List documents from Frappe with filters.
        
        Args:
            doctype: DocType name
            filters: Filter string (optional). Uses custom syntax to bypass MCP validation issues.
            fields: Comma-separated field names (optional). E.g. "name,customer,total"
            limit: Maximum number of records to return (optional). E.g. "20"
            order_by: Field to order by (optional, can include 'desc' like 'creation desc')
        
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
            - list_documents("Bank Transaction", "status:Unreconciled") -> List unreconciled transactions
            - list_documents("Task", "status:in:Open|Working", "name,subject", "10") -> List open tasks with specific fields
            - list_documents("User", "name:like:%admin%") -> List users with 'admin' in name
        """
        try:
            client = get_client()
            
            # Build query parameters
            params = {}
            parsed_filters = format_filters_for_api(filters)
            if parsed_filters:
                params["filters"] = json.dumps(parsed_filters)
            if fields:
                # Convert comma-separated string to list
                field_list = [f.strip() for f in fields.split(',')]
                params["fields"] = json.dumps(field_list)
            if limit:
                # Convert string to integer for API
                params["limit"] = limit
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
            - "status:Unreconciled" -> Status equals Unreconciled
            - "amount:>:100" -> Amount greater than 100
            - "name:like:%admin%" -> Name contains 'admin'
            - "status:in:Open|Working|Pending" -> Status in list
            - "date:between:2025-01-01|2025-12-31" -> Date in range
            - "phone:is:not_null" -> Phone is not null
        
        Tool Examples:
            - count_documents("User") -> Count all users
            - count_documents("Bank Transaction", "status:Unreconciled") -> Count unreconciled transactions
            - count_documents("Bank Transaction", "unallocated_amount:>:0") -> Count with unallocated amount
            - count_documents("Task", "status:in:Open|Working|Pending") -> Count tasks with multiple statuses
            - count_documents("User", "name:like:%admin%") -> Count users with 'admin' in name  
            - count_documents("Payment Entry", "posting_date:between:2025-01-01|2025-12-31") -> Count in date range
            - count_documents("Contact", "phone:is:not_null") -> Count contacts with phone numbers
        """
        try:
            client = get_client()
            
            # Build query parameters for counting
            params = {
                "fields": json.dumps(["count(name) as count"])
            }
            
            # Parse and add filters if provided
            parsed_filters = format_filters_for_api(filters)
            if parsed_filters:
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
    async def submit_document(
        doctype: str,
        name: str
    ) -> str:
        """
        Submit a document in Frappe (change docstatus from 0 to 1).
        
        This tool handles document submission using Frappe's submission workflow,
        including proper validation and error handling to provide clear feedback
        for corrective action.
        
        Args:
            doctype: DocType name
            name: Document name (case-sensitive)
            
        Returns:
            Success message if submitted, or detailed error information if submission
            fails due to validation errors or missing required fields.
        """
        try:
            client = get_client()
            
            # First, get the current document to check its status and get full data
            try:
                doc_response = await client.get(f"api/resource/{doctype}/{name}")
                doc_data = doc_response.get("data", {})
                current_docstatus = doc_data.get("docstatus", None)
                
                if current_docstatus is None:
                    return f"Error: Could not retrieve document {doctype} '{name}'. Document may not exist."
                    
                if current_docstatus == 1:
                    return f"Document {doctype} '{name}' is already submitted."
                    
                if current_docstatus == 2:
                    return f"Document {doctype} '{name}' is cancelled and cannot be submitted."
                    
                if current_docstatus != 0:
                    return f"Document {doctype} '{name}' has unexpected status (docstatus={current_docstatus}). Only draft documents (docstatus=0) can be submitted."
                    
            except Exception as get_error:
                return f"Error retrieving document for submission: {get_error}"
            
            # Prepare document for submission by setting docstatus to 1
            submit_doc = doc_data.copy()
            submit_doc['docstatus'] = 1
            
            # Use Frappe's savedocs method which handles the submission workflow
            response = await client.post(
                "api/method/frappe.desk.form.save.savedocs",
                json_data={
                    "doc": json.dumps(submit_doc),
                    "action": "Submit"
                }
            )
            
            # Check if submission was successful
            if "docs" in response:
                submitted_doc = response["docs"][0] if response["docs"] else {}
                final_docstatus = submitted_doc.get("docstatus", 0)
                
                if final_docstatus == 1:
                    return f"✅ Document {doctype} '{name}' successfully submitted."
                else:
                    return f"⚠️ Submission completed but document status is {final_docstatus} (expected 1)."
            
            # If we get here, check for success without docs
            if response.get("message") == "ok" or "exc" not in response:
                return f"✅ Document {doctype} '{name}' successfully submitted."
            
            # If no explicit success indicator, assume it worked
            return f"✅ Document {doctype} '{name}' submission completed."
            
        except FrappeApiError as api_error:
            # Handle specific Frappe API errors with detailed information
            if api_error.response_data:
                error_data = api_error.response_data
                
                # Check for validation errors in the response
                if "exception" in error_data:
                    exception_msg = error_data["exception"]
                    
                    # Extract user-friendly error messages
                    if "ValidationError" in str(exception_msg):
                        # Try to extract the specific validation error
                        if "Reference No & Reference Date is required" in str(exception_msg):
                            return (
                                f"❌ Submission failed: Document {doctype} '{name}' requires 'reference_no' and 'reference_date' fields for Bank Entry vouchers. "
                                f"Please update the document with these required fields before submitting."
                            )
                        else:
                            # Generic validation error
                            return f"❌ Validation error: {exception_msg}. Please fix the validation issues and try again."
                    
                    elif "PermissionError" in str(exception_msg):
                        return f"❌ Permission denied: You don't have sufficient permissions to submit {doctype} documents."
                    
                    else:
                        # Other exceptions
                        return f"❌ Submission failed: {exception_msg}"
                
                # Check for server messages with more details
                if "_server_messages" in error_data:
                    try:
                        messages = json.loads(error_data["_server_messages"])
                        if messages:
                            msg_data = json.loads(messages[0])
                            user_message = msg_data.get("message", "Unknown error")
                            return f"❌ Submission failed: {user_message}"
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
            
            return f"❌ Submission failed: {api_error}"
            
        except Exception as error:
            return _format_error_response(error, "submit_document")

    @mcp.tool()
    async def cancel_document(
        doctype: str,
        name: str
    ) -> str:
        """
        Cancel a document in Frappe (change docstatus from 1 to 2).
        
        This tool handles document cancellation using Frappe's cancellation workflow,
        including proper validation and error handling to provide clear feedback
        for corrective action.
        
        Args:
            doctype: DocType name
            name: Document name (case-sensitive)
            
        Returns:
            Success message if cancelled, or detailed error information if cancellation
            fails due to validation errors, linked documents, or permission issues.
        """
        try:
            client = get_client()
            
            # First, get the current document to check its status and get full data
            try:
                doc_response = await client.get(f"api/resource/{doctype}/{name}")
                doc_data = doc_response.get("data", {})
                current_docstatus = doc_data.get("docstatus", None)
                
                if current_docstatus is None:
                    return f"Error: Could not retrieve document {doctype} '{name}'. Document may not exist."
                    
                if current_docstatus == 0:
                    return f"Document {doctype} '{name}' is in Draft status. Only submitted documents (docstatus=1) can be cancelled."
                    
                if current_docstatus == 2:
                    return f"Document {doctype} '{name}' is already cancelled."
                    
                if current_docstatus != 1:
                    return f"Document {doctype} '{name}' has unexpected status (docstatus={current_docstatus}). Only submitted documents (docstatus=1) can be cancelled."
                    
            except Exception as get_error:
                return f"Error retrieving document for cancellation: {get_error}"
            
            # Prepare document for cancellation by setting docstatus to 2
            cancel_doc = doc_data.copy()
            cancel_doc['docstatus'] = 2
            
            # Use Frappe's savedocs method which handles the cancellation workflow
            response = await client.post(
                "api/method/frappe.desk.form.save.savedocs",
                json_data={
                    "doc": json.dumps(cancel_doc),
                    "action": "Cancel"
                }
            )
            
            # Check if cancellation was successful
            if "docs" in response:
                cancelled_doc = response["docs"][0] if response["docs"] else {}
                final_docstatus = cancelled_doc.get("docstatus", 0)
                
                if final_docstatus == 2:
                    return f"✅ Document {doctype} '{name}' successfully cancelled."
                else:
                    return f"⚠️ Cancellation completed but document status is {final_docstatus} (expected 2)."
            
            # If we get here, check for success without docs
            if response.get("message") == "ok" or "exc" not in response:
                return f"✅ Document {doctype} '{name}' successfully cancelled."
            
            # If no explicit success indicator, assume it worked
            return f"✅ Document {doctype} '{name}' cancellation completed."
            
        except FrappeApiError as api_error:
            # Handle specific Frappe API errors with detailed information
            if api_error.response_data:
                error_data = api_error.response_data
                
                # Check for validation errors in the response
                if "exception" in error_data:
                    exception_msg = error_data["exception"]
                    
                    # Extract user-friendly error messages
                    if "ValidationError" in str(exception_msg):
                        # Common cancellation validation errors
                        if "Cannot cancel" in str(exception_msg) and "linked" in str(exception_msg).lower():
                            return (
                                f"❌ Cancellation failed: Document {doctype} '{name}' cannot be cancelled because it has linked documents. "
                                f"You may need to cancel or unlink related documents first before cancelling this document."
                            )
                        elif "Cannot cancel" in str(exception_msg):
                            return f"❌ Cancellation failed: {exception_msg}. Check document constraints and linked records."
                        else:
                            # Generic validation error
                            return f"❌ Validation error: {exception_msg}. Please fix the validation issues and try again."
                    
                    elif "PermissionError" in str(exception_msg):
                        return f"❌ Permission denied: You don't have sufficient permissions to cancel {doctype} documents."
                    
                    else:
                        # Other exceptions
                        return f"❌ Cancellation failed: {exception_msg}"
                
                # Check for server messages with more details
                if "_server_messages" in error_data:
                    try:
                        messages = json.loads(error_data["_server_messages"])
                        if messages:
                            msg_data = json.loads(messages[0])
                            user_message = msg_data.get("message", "Unknown error")
                            return f"❌ Cancellation failed: {user_message}"
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
            
            return f"❌ Cancellation failed: {api_error}"
            
        except Exception as error:
            return _format_error_response(error, "cancel_document")

    @mcp.tool()
    async def amend_document(
        doctype: str,
        name: str
    ) -> str:
        """
        Amend a document in Frappe (create a new amended version of a cancelled document).
        
        This tool handles document amendment by creating a new document with an amended name
        (e.g., DOC-001-1, DOC-001-2) and copying all relevant field values from the original
        cancelled document, establishing proper linkage via the 'amended_from' field.
        
        Args:
            doctype: DocType name
            name: Document name (case-sensitive) - must be a cancelled document
            
        Returns:
            Success message with new amended document name if successful, or detailed 
            error information if amendment fails due to validation errors or constraints.
        """
        try:
            client = get_client()
            
            # First, get the current document to check its status and get full data
            try:
                doc_response = await client.get(f"api/resource/{doctype}/{name}")
                doc_data = doc_response.get("data", {})
                current_docstatus = doc_data.get("docstatus", None)
                
                if current_docstatus is None:
                    return f"Error: Could not retrieve document {doctype} '{name}'. Document may not exist."
                    
                if current_docstatus == 0:
                    return f"Document {doctype} '{name}' is in Draft status. Only cancelled documents (docstatus=2) can be amended."
                    
                if current_docstatus == 1:
                    return f"Document {doctype} '{name}' is submitted. You must cancel it first before amending."
                    
                if current_docstatus != 2:
                    return f"Document {doctype} '{name}' has unexpected status (docstatus={current_docstatus}). Only cancelled documents (docstatus=2) can be amended."
                    
            except Exception as get_error:
                return f"Error retrieving document for amendment: {get_error}"
            
            # Generate amended document name
            base_name = name
            amended_counter = 1
            
            # Check if this document is already an amendment (contains dash and number)
            if '-' in name:
                parts = name.rsplit('-', 1)
                if len(parts) == 2 and parts[1].isdigit():
                    base_name = parts[0]
                    amended_counter = int(parts[1]) + 1
            
            # Find the next available amended name
            amended_name = f"{base_name}-{amended_counter}"
            while True:
                try:
                    # Check if amended name already exists
                    check_response = await client.get(f"api/resource/{doctype}/{amended_name}")
                    if "data" in check_response:
                        # Name exists, try next number
                        amended_counter += 1
                        amended_name = f"{base_name}-{amended_counter}"
                    else:
                        # Name doesn't exist, we can use it
                        break
                except FrappeApiError as e:
                    # If we get 404, the name doesn't exist and we can use it
                    if e.status_code == 404:
                        break
                    else:
                        # Some other error, we should handle it
                        raise e
            
            # Prepare amended document data
            amended_doc = doc_data.copy()
            
            # Clear system fields that should not be copied
            system_fields = [
                'name', 'creation', 'modified', 'modified_by', 'owner', 
                'docstatus', 'idx', '_user_tags', '_comments', '_assign', '_liked_by'
            ]
            for field in system_fields:
                amended_doc.pop(field, None)
            
            # Set amendment fields
            amended_doc['name'] = amended_name
            amended_doc['amended_from'] = name
            amended_doc['docstatus'] = 0  # New document starts as draft
            
            # Clear any child table names to let Frappe generate new ones
            for key, value in amended_doc.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            item.pop('name', None)  # Clear child table row names
                            item['parent'] = amended_name  # Update parent reference
            
            # Create the amended document
            response = await client.post(
                f"api/resource/{doctype}",
                json_data=amended_doc
            )
            
            if "data" in response:
                created_doc = response["data"]
                created_name = created_doc.get('name', amended_name)
                return f"✅ Document successfully amended: {doctype} '{created_name}' created from cancelled document '{name}'. The amended document is in Draft status and ready for editing."
            else:
                return f"⚠️ Amendment may have succeeded but response format unexpected: {json.dumps(response, indent=2)}"
                
        except FrappeApiError as api_error:
            # Handle specific Frappe API errors with detailed information
            if api_error.response_data:
                error_data = api_error.response_data
                
                # Check for validation errors in the response
                if "exception" in error_data:
                    exception_msg = error_data["exception"]
                    
                    # Extract user-friendly error messages
                    if "ValidationError" in str(exception_msg):
                        # Common amendment validation errors
                        if "amended_from" in str(exception_msg).lower():
                            return (
                                f"❌ Amendment failed: {doctype} does not have an 'amended_from' field configured. "
                                f"This DocType may not support amendments. Contact your system administrator to enable amendment functionality."
                            )
                        elif "DuplicateEntryError" in str(exception_msg) or "duplicate" in str(exception_msg).lower():
                            return f"❌ Amendment failed: Document name conflict. The amended name may already exist. Please try again."
                        else:
                            # Generic validation error
                            return f"❌ Validation error: {exception_msg}. Please fix the validation issues before amending."
                    
                    elif "PermissionError" in str(exception_msg):
                        return f"❌ Permission denied: You don't have sufficient permissions to amend {doctype} documents."
                    
                    else:
                        # Other exceptions
                        return f"❌ Amendment failed: {exception_msg}"
                
                # Check for server messages with more details
                if "_server_messages" in error_data:
                    try:
                        messages = json.loads(error_data["_server_messages"])
                        if messages:
                            msg_data = json.loads(messages[0])
                            user_message = msg_data.get("message", "Unknown error")
                            return f"❌ Amendment failed: {user_message}"
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass
            
            return f"❌ Amendment failed: {api_error}"
            
        except Exception as error:
            return _format_error_response(error, "amend_document")

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