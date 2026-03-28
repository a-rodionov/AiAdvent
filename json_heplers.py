import json
from typing import Any, Dict, List, Optional, Type, Union
from pydantic import BaseModel, create_model, Field, field_validator
from pydantic.fields import FieldInfo

def _get_python_type(schema_type: str, schema_format: Optional[str] = None) -> Any:
    """Преобразует тип JSON Schema в Python-тип."""
    type_mapping = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,  # для вложенных объектов будет отдельная обработка
    }

    return type_mapping.get(schema_type, Any)

def create_model_from_schema(
    schema: Dict[str, Any],
    model_name: str = "DynamicModel"
) -> Type[BaseModel]:
    """
    Рекурсивно создаёт Pydantic-модель на основе JSON Schema.
    """
    # Базовая валидация: ожидаем объект верхнего уровня
    if schema.get("type") != "object":
        raise ValueError("Корневая схема должна быть типа 'object'")
    
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    fields = {}
    
    for field_name, field_schema in properties.items():
        field_type = field_schema.get("type")
        field_format = field_schema.get("format")
        default = field_schema.get("default")
        is_required = field_name in required
        
        if field_type == "object":
            # Вложенный объект: рекурсивно создаём модель
            sub_model = create_model_from_schema(field_schema, f"{model_name}_{field_name}")
            field_type_annotation = sub_model
        elif field_type == "array":
            items_schema = field_schema.get("items", {})
            if items_schema.get("type") == "object":
                item_model = create_model_from_schema(items_schema, f"{model_name}_{field_name}_item")
                field_type_annotation = List[item_model]
            else:
                # Примитивный тип внутри массива
                item_type = _get_python_type(items_schema.get("type"), items_schema.get("format"))
                field_type_annotation = List[item_type]
        else:
            field_type_annotation = _get_python_type(field_type, field_format)
        
        # Настройка поля: обязательное или с дефолтом
        if is_required:
            fields[field_name] = (field_type_annotation, Field(...))
        else:
            # Если дефолт не указан, ставим None
            if default is not None:
                fields[field_name] = (Optional[field_type_annotation], Field(default=default))
            else:
                fields[field_name] = (Optional[field_type_annotation], Field(None))
    
    # Создаём модель с помощью create_model
    return create_model(model_name, **fields)
