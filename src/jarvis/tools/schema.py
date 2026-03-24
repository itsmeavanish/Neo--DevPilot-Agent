"""
JSON Schema validation utilities for tools.
"""

from typing import Any

# Using a simple validator to avoid heavy dependencies
# Can be replaced with jsonschema if needed


def validate_params(params: dict, schema: dict) -> list[str]:
    """
    Validate parameters against a JSON Schema.

    Args:
        params: Parameters to validate
        schema: JSON Schema to validate against

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in params:
            errors.append(f"Missing required field: {field}")

    # Validate properties
    properties = schema.get("properties", {})
    for key, value in params.items():
        if key in properties:
            prop_schema = properties[key]
            field_errors = _validate_field(key, value, prop_schema)
            errors.extend(field_errors)

    return errors


def _validate_field(name: str, value: Any, schema: dict) -> list[str]:
    """Validate a single field against its schema."""
    errors = []
    expected_type = schema.get("type")

    if expected_type:
        if not _check_type(value, expected_type):
            errors.append(f"Field '{name}': expected {expected_type}, got {type(value).__name__}")
            return errors  # Skip further validation if type is wrong

    # Enum validation
    if "enum" in schema:
        if value not in schema["enum"]:
            errors.append(f"Field '{name}': must be one of {schema['enum']}")

    # String constraints
    if expected_type == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"Field '{name}': minimum length is {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"Field '{name}': maximum length is {schema['maxLength']}")
        if "pattern" in schema:
            import re
            if not re.match(schema["pattern"], value):
                errors.append(f"Field '{name}': does not match pattern {schema['pattern']}")

    # Number constraints
    if expected_type in ("integer", "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"Field '{name}': minimum value is {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"Field '{name}': maximum value is {schema['maximum']}")

    # Array constraints
    if expected_type == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"Field '{name}': minimum items is {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"Field '{name}': maximum items is {schema['maxItems']}")
        # Validate array items
        if "items" in schema:
            for i, item in enumerate(value):
                item_errors = _validate_field(f"{name}[{i}]", item, schema["items"])
                errors.extend(item_errors)

    return errors


def _check_type(value: Any, expected: str) -> bool:
    """Check if value matches expected JSON Schema type."""
    type_mapping = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    if expected not in type_mapping:
        return True  # Unknown type, skip validation

    expected_types = type_mapping[expected]
    if isinstance(expected_types, tuple):
        return isinstance(value, expected_types)
    return isinstance(value, expected_types)


def extract_function_call(response: dict) -> tuple[str, dict] | None:
    """
    Extract function call from LLM response.

    Handles both OpenAI and Anthropic formats.

    Args:
        response: LLM response dictionary

    Returns:
        Tuple of (function_name, arguments) or None if no function call
    """
    # OpenAI format
    if "function_call" in response:
        fc = response["function_call"]
        return fc["name"], fc.get("arguments", {})

    # OpenAI tool_calls format
    if "tool_calls" in response:
        for tc in response["tool_calls"]:
            if tc["type"] == "function":
                func = tc["function"]
                return func["name"], func.get("arguments", {})

    # Anthropic format
    if "content" in response:
        for block in response.get("content", []):
            if block.get("type") == "tool_use":
                return block["name"], block.get("input", {})

    return None


__all__ = ["validate_params", "extract_function_call"]
