"""Registration utility auto-loading and registering validation skills into global registry."""

from app.skills.registry import registry
from app.skills.schema_validation.best_practices import BestPracticesSkill
from app.skills.schema_validation.data_quality import DataQualitySkill
from app.skills.schema_validation.naming import NamingSkill
from app.skills.schema_validation.relationships import RelationshipsSkill
from app.skills.schema_validation.structure import StructureSkill


def register_validation_skills() -> None:
    """Instantiate and register all validation skills with the global registry."""
    registry.register(StructureSkill())
    registry.register(RelationshipsSkill())
    registry.register(NamingSkill())
    registry.register(DataQualitySkill())
    registry.register(BestPracticesSkill())
