"""
Filter parsing utilities for MCP tools.

This module provides utilities to parse string-based filters into Frappe filter format,
bypassing MCP JSON validation limitations.
"""

from typing import Any, Dict, Optional


def parse_filter_string(filter_str: str) -> Dict[str, Any]:
    """
    Parse filter string into Frappe filter format.
    
    Supported operators: =, !=, <, >, <=, >=, like, not_like, in, not_in, is, is_not, between
    
    Examples:
    - "status:Unreconciled" -> {"status": "Unreconciled"}
    - "amount:>:100" -> {"amount": [">", 100]}
    - "name:like:%test%" -> {"name": ["like", "%test%"]}
    - "status:in:Open|Closed" -> {"status": ["in", ["Open", "Closed"]]}
    - "date:between:2025-01-01|2025-12-31" -> {"date": ["between", ["2025-01-01", "2025-12-31"]]}
    - "field:is:null" -> {"field": ["is", "not set"]}
    - "date:>=:2024-01-01,date:<=:2024-01-31" -> {"date": [[">=", "2024-01-01"], ["<=", "2024-01-31"]]}
    """
    filters_dict: Dict[str, Any] = {}
    
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
                
                # Create the filter condition
                filter_condition = None
                
                # Handle special operators
                if operator.lower() in ['in', 'not_in']:
                    # Handle list values separated by |
                    values = [v.strip() for v in value_str.split('|')]
                    # Convert numbers in list
                    converted_values = []
                    for v in values:
                        converted_values.append(_convert_value(v))
                    filter_condition = [operator.replace('_', ' '), converted_values]
                    
                elif operator.lower() == 'between':
                    # Handle range values separated by |
                    range_values = [v.strip() for v in value_str.split('|')]
                    if len(range_values) == 2:
                        converted_range = [_convert_value(v) for v in range_values]
                        filter_condition = [operator, converted_range]
                    else:
                        raise ValueError(f"Between operator requires exactly 2 values separated by |, got: {value_str}")
                        
                elif operator.lower() in ['is', 'is_not']:
                    # Handle null checks: is:null, is:not_null, is_not:null, etc.
                    if value_str.lower() in ['null', 'none', 'empty']:
                        filter_condition = [operator.replace('_', ' '), "not set"]
                    elif value_str.lower() in ['not_null', 'not_none', 'not_empty']:
                        filter_condition = [operator.replace('_', ' '), "set"]
                    else:
                        filter_condition = [operator.replace('_', ' '), _convert_value(value_str)]
                        
                elif operator.lower() == 'not_like':
                    # Handle not like operator  
                    filter_condition = ["not like", value_str]
                    
                else:
                    # Standard operators: =, !=, <, >, <=, >=, like
                    filter_condition = [operator, _convert_value(value_str)]
                
                # Handle multiple filters for the same field
                if field in filters_dict:
                    # Convert existing single filter to list format
                    if not isinstance(filters_dict[field], list) or len(filters_dict[field]) != 2 or not isinstance(filters_dict[field][0], list):
                        filters_dict[field] = [filters_dict[field]]
                    # Add new filter condition
                    filters_dict[field].append(filter_condition)
                else:
                    filters_dict[field] = filter_condition
                    
            elif len(components) == 2:
                # Simple field:value format (implies equality)
                field, value_str = components[0].strip(), components[1]
                filter_condition = _convert_value(value_str)
                
                # Handle multiple filters for the same field
                if field in filters_dict:
                    # Convert existing single filter to list format
                    if not isinstance(filters_dict[field], list) or len(filters_dict[field]) != 2 or not isinstance(filters_dict[field][0], list):
                        filters_dict[field] = [filters_dict[field]]
                    # Add new filter condition
                    filters_dict[field].append(filter_condition)
                else:
                    filters_dict[field] = filter_condition
                
    # Post-process: Convert >= and <= on same field to between operator
    filters_dict = _optimize_range_filters(filters_dict)
    
    return filters_dict


def _optimize_range_filters(filters_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optimize range filters by converting >= and <= conditions on the same field to between operator.
    
    This fixes the issue where Frappe API can't handle nested arrays like:
    {"date": [[">=", "2024-01-01"], ["<=", "2024-01-31"]]}
    
    Instead converts to:
    {"date": ["between", ["2024-01-01", "2024-01-31"]]}
    """
    optimized = {}
    
    for field, conditions in filters_dict.items():
        # Check if we have multiple conditions on the same field
        if isinstance(conditions, list) and len(conditions) >= 2:
            # Look for >= and <= patterns that can be converted to between
            gte_value = None
            lte_value = None
            other_conditions = []
            
            for condition in conditions:
                if isinstance(condition, list) and len(condition) == 2:
                    operator, value = condition
                    if operator == ">=":
                        gte_value = value
                    elif operator == "<=":
                        lte_value = value
                    else:
                        other_conditions.append(condition)
                else:
                    other_conditions.append(condition)
            
            # If we found both >= and <= conditions, convert to between
            if gte_value is not None and lte_value is not None:
                between_condition = ["between", [gte_value, lte_value]]
                
                if other_conditions:
                    # If there are other conditions, keep them along with between
                    optimized[field] = [between_condition] + other_conditions
                else:
                    # Just the between condition
                    optimized[field] = between_condition
            else:
                # Keep original conditions if we can't optimize
                optimized[field] = conditions
        else:
            # Single condition, keep as-is
            optimized[field] = conditions
    
    return optimized


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


def format_filters_for_api(filters: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Convert string filters to Frappe API format.
    
    Args:
        filters: Filter string or None
        
    Returns:
        Parsed filters dict or None
    """
    if not filters:
        return None
    return parse_filter_string(filters)


# Filter syntax documentation for use in tool docstrings
FILTER_SYNTAX_DOCS = """
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
"""