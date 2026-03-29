from typing import Any

from pydantic import BaseModel, Field, create_model


def _get_python_type(schema_type: str, schema_format: str | None = None) -> Any:
    """Convert a JSON Schema type string to a Python type."""
    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_mapping.get(schema_type, Any)


def create_model_from_schema(
    schema: dict[str, Any],
    model_name: str = "DynamicModel",
) -> type[BaseModel]:
    """Recursively build a Pydantic model from a JSON Schema dict."""
    if schema.get("type") != "object":
        raise ValueError("Root schema must be of type 'object'")

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields: dict[str, Any] = {}

    for field_name, field_schema in properties.items():
        field_type = field_schema.get("type")
        field_format = field_schema.get("format")
        default = field_schema.get("default")
        is_required = field_name in required

        if field_type == "object":
            sub_model = create_model_from_schema(field_schema, f"{model_name}_{field_name}")
            field_type_annotation: Any = sub_model
        elif field_type == "array":
            items_schema = field_schema.get("items", {})
            if items_schema.get("type") == "object":
                item_model = create_model_from_schema(items_schema, f"{model_name}_{field_name}_item")
                field_type_annotation = list[item_model]  # type: ignore[valid-type]
            else:
                item_type = _get_python_type(items_schema.get("type"), items_schema.get("format"))
                field_type_annotation = list[item_type]  # type: ignore[valid-type]
        else:
            field_type_annotation = _get_python_type(field_type, field_format)

        if is_required:
            fields[field_name] = (field_type_annotation, Field(...))
        else:
            if default is not None:
                fields[field_name] = (field_type_annotation | None, Field(default=default))
            else:
                fields[field_name] = (field_type_annotation | None, Field(None))

    return create_model(model_name, **fields)
