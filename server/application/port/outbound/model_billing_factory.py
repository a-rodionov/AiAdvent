"""IModelBillingFactory port — factory for creating ModelBilling instances.

Spec: ``openspec/specs/model-billing-factory/spec.md``
"""
from typing import Protocol

from server.application.domain.model.model_billing import ModelBilling


class IModelBillingFactory(Protocol):
    """Factory port for creating ModelBilling instances by provider and model."""

    def create(self, provider: str, model: str) -> ModelBilling | None: ...
