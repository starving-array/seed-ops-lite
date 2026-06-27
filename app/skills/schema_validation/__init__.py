"""Schema validation skills package definition."""

from app.skills.schema_validation.best_practices import BestPracticesSkill
from app.skills.schema_validation.data_quality import DataQualitySkill
from app.skills.schema_validation.naming import NamingSkill
from app.skills.schema_validation.registry import register_validation_skills
from app.skills.schema_validation.relationships import RelationshipsSkill
from app.skills.schema_validation.structure import StructureSkill

# Auto-register on import
register_validation_skills()

__all__ = [
    "StructureSkill",
    "RelationshipsSkill",
    "NamingSkill",
    "DataQualitySkill",
    "BestPracticesSkill",
    "register_validation_skills",
]
