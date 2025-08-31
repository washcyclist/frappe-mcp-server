"""
Schema MCP tools for Frappe DocType introspection.

This module provides tools for examining DocType schemas,
field definitions, and database structure.
"""

from typing import Any, Dict, List, Optional, Union
import json

from ..frappe_api import get_client, FrappeApiError
from ..auth import validate_api_credentials


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
    """Register schema tools with the MCP server."""
    
    @mcp.tool()
    async def get_doctype_schema(doctype: str) -> str:
        """
        Get the complete schema for a DocType including field definitions, validations, and linked DocTypes.
        
        Use this to understand the structure of a DocType before creating or updating documents.
        
        Args:
            doctype: DocType name
        """
        try:
            client = get_client()
            
            # Get DocType schema
            response = await client.get(f"api/resource/DocType/{doctype}")
            
            if "data" in response:
                schema_data = response["data"]
                
                # Format the response to highlight key information
                fields = schema_data.get("fields", [])
                field_summary = []
                
                for field in fields:
                    field_info = {
                        "label": field.get("label"),
                        "fieldname": field.get("fieldname"),
                        "fieldtype": field.get("fieldtype"),
                        "reqd": field.get("reqd", 0) == 1,
                        "options": field.get("options"),
                        "default": field.get("default")
                    }
                    if field.get("description"):
                        field_info["description"] = field.get("description")
                    field_summary.append(field_info)
                
                formatted_response = {
                    "doctype": doctype,
                    "module": schema_data.get("module"),
                    "naming_rule": schema_data.get("autoname"),
                    "is_submittable": schema_data.get("is_submittable", 0) == 1,
                    "is_tree": schema_data.get("is_tree", 0) == 1,
                    "track_changes": schema_data.get("track_changes", 0) == 1,
                    "allow_rename": schema_data.get("allow_rename", 0) == 1,
                    "fields": field_summary,
                    "permissions": schema_data.get("permissions", [])
                }
                
                return json.dumps(formatted_response, indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "get_doctype_schema")
    
    @mcp.tool()
    async def get_field_options(
        doctype: str,
        fieldname: str,
        limit: Optional[int] = 20
    ) -> str:
        """
        Get available options for a Link or Select field.
        
        For Link fields, returns documents from the linked DocType.
        For Select fields, returns the predefined options.
        
        Args:
            doctype: DocType name
            fieldname: Field name
            limit: Maximum number of options to return (default: 20)
        """
        try:
            client = get_client()
            
            # First get the field definition to understand its type
            schema_response = await client.get(f"api/resource/DocType/{doctype}")
            
            if "data" not in schema_response:
                return f"Could not get schema for DocType: {doctype}"
            
            fields = schema_response["data"].get("fields", [])
            target_field = None
            
            for field in fields:
                if field.get("fieldname") == fieldname:
                    target_field = field
                    break
            
            if not target_field:
                return f"Field '{fieldname}' not found in DocType '{doctype}'"
            
            fieldtype = target_field.get("fieldtype")
            options = target_field.get("options", "")
            
            if fieldtype == "Link":
                # Get documents from linked DocType
                if not options:
                    return f"Link field '{fieldname}' has no linked DocType defined"
                
                params = {
                    "fields": json.dumps(["name", "title"]),
                    "limit": str(limit)
                }
                
                response = await client.get(f"api/resource/{options}", params=params)
                
                if "data" in response:
                    documents = response["data"]
                    return f"Available {options} documents for field '{fieldname}':\n\n" + json.dumps(documents, indent=2)
                else:
                    return json.dumps(response, indent=2)
            
            elif fieldtype == "Select":
                # Parse select options
                if not options:
                    return f"Select field '{fieldname}' has no options defined"
                
                select_options = [opt.strip() for opt in options.split("\n") if opt.strip()]
                return f"Select options for field '{fieldname}':\n\n" + json.dumps(select_options, indent=2)
            
            else:
                return f"Field '{fieldname}' is of type '{fieldtype}' which doesn't have predefined options"
                
        except Exception as error:
            return _format_error_response(error, "get_field_options")
    
    @mcp.tool()
    async def get_doctype_list(
        module: Optional[str] = None,
        limit: Optional[int] = 50
    ) -> str:
        """
        Get a list of available DocTypes, optionally filtered by module.
        
        Args:
            module: Module name to filter by (optional)
            limit: Maximum number of DocTypes to return (default: 50)
        """
        try:
            client = get_client()
            
            # Build parameters
            params = {
                "fields": json.dumps(["name", "module", "is_submittable", "is_tree", "description"]),
                "limit": str(limit),
                "order_by": "name"
            }
            
            if module:
                params["filters"] = json.dumps({"module": module})
            
            # Get DocType list
            response = await client.get("api/resource/DocType", params=params)
            
            if "data" in response:
                doctypes = response["data"]
                count = len(doctypes)
                filter_text = f" in module '{module}'" if module else ""
                return f"Found {count} DocTypes{filter_text}:\n\n" + json.dumps(doctypes, indent=2)
            else:
                return json.dumps(response, indent=2)
                
        except Exception as error:
            return _format_error_response(error, "get_doctype_list")
    
    @mcp.tool()
    async def get_frappe_usage_info(
        doctype: Optional[str] = None,
        workflow: Optional[str] = None
    ) -> str:
        """
        Get combined information about a DocType or workflow, including schema metadata and usage guidance.
        
        Args:
            doctype: DocType name (optional if workflow is provided)
            workflow: Workflow name (optional if doctype is provided)
        """
        try:
            if not doctype and not workflow:
                return "Please provide either a doctype or workflow parameter"
            
            client = get_client()
            info_parts = []
            
            if doctype:
                # Get DocType schema information
                schema_response = await client.get(f"api/resource/DocType/{doctype}")
                
                if "data" in schema_response:
                    schema_data = schema_response["data"]
                    
                    # Extract key information
                    info = {
                        "doctype": doctype,
                        "module": schema_data.get("module"),
                        "description": schema_data.get("description"),
                        "is_submittable": schema_data.get("is_submittable", 0) == 1,
                        "is_tree": schema_data.get("is_tree", 0) == 1,
                        "naming_rule": schema_data.get("autoname"),
                        "required_fields": []
                    }
                    
                    # Get required fields
                    for field in schema_data.get("fields", []):
                        if field.get("reqd", 0) == 1:
                            info["required_fields"].append({
                                "fieldname": field.get("fieldname"),
                                "label": field.get("label"),
                                "fieldtype": field.get("fieldtype"),
                                "options": field.get("options")
                            })
                    
                    info_parts.append(f"DocType Information:\n{json.dumps(info, indent=2)}")
            
            if workflow:
                # Get workflow information
                try:
                    workflow_response = await client.get(f"api/resource/Workflow/{workflow}")
                    if "data" in workflow_response:
                        workflow_data = workflow_response["data"]
                        workflow_info = {
                            "workflow": workflow,
                            "document_type": workflow_data.get("document_type"),
                            "is_active": workflow_data.get("is_active", 0) == 1,
                            "workflow_states": workflow_data.get("states", []),
                            "transitions": workflow_data.get("transitions", [])
                        }
                        info_parts.append(f"Workflow Information:\n{json.dumps(workflow_info, indent=2)}")
                except:
                    info_parts.append(f"Could not retrieve workflow information for: {workflow}")
            
            return "\n\n".join(info_parts) if info_parts else "No information found"
                
        except Exception as error:
            return _format_error_response(error, "get_frappe_usage_info")