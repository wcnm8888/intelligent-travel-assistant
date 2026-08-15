"""Base configuration for stable public contracts."""

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Reject unknown fields and prevent mutation after validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)
