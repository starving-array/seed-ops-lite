"""Batch decision engine for synthetic data generation in SafeSeedOps Lite."""

from app.schemas.schema_design import SchemaModel


def calculate_batch_size(schema: SchemaModel, row_targets: dict[str, int]) -> int:
    """Select the optimal batch size for synthetic dataset generation.

    Philosophy:
    - Small datasets -> Small batches (minimizes overhead, fits memory limits).
    - Large datasets -> Larger batches (optimizes throughput, fewer roundtrips).
    - Complex schemas -> More conservative batches (relationships and columns require more validation/processing per row).
    - Simple schemas -> Larger batches (faster generation is safe when relationships are few).

    Args:
        schema: The schema model configuration containing tables and relationships.
        row_targets: A dictionary mapping table names to the target number of rows to generate.

    Returns:
        int: The selected batch size.
    """
    if not row_targets or not schema.tables:
        return 10

    from app.core.settings.config import settings

    total_rows = sum(row_targets.values())
    num_tables = len(schema.tables)
    num_relationships = len(schema.relationships)

    # Calculate column statistics
    total_columns = sum(len(t.columns) for t in schema.tables)
    avg_columns = total_columns / num_tables if num_tables > 0 else 0

    # Determine base batch size based on workload size (total rows requested)
    if total_rows <= settings.BATCH_THRESHOLD_SMALL:
        base_batch = settings.BATCH_SIZE_SMALL
    elif total_rows <= settings.BATCH_THRESHOLD_MEDIUM:
        base_batch = settings.BATCH_SIZE_MEDIUM
    elif total_rows <= settings.BATCH_THRESHOLD_LARGE:
        base_batch = settings.BATCH_SIZE_LARGE
    else:
        base_batch = settings.BATCH_SIZE_XLARGE

    # Adjust for schema complexity
    # Complexity factors:
    # 1. Relationship density (relationships per table)
    rel_density = num_relationships / num_tables if num_tables > 0 else 0

    # 2. Schema size (number of tables & total columns)
    is_complex = (
        num_tables > 8
        or num_relationships > 10
        or avg_columns > 12
        or rel_density > 1.2
    )
    is_very_complex = (
        num_tables > 15
        or num_relationships > 20
        or avg_columns > 20
        or rel_density > 1.8
    )
    is_simple = num_tables <= 2 and num_relationships <= 1 and avg_columns <= 5

    # Apply adjustment multiplier based on complexity
    multiplier = 1.0
    if is_very_complex:
        multiplier = 0.5  # 50% reduction for extremely complex schemas
    elif is_complex:
        multiplier = 0.7  # 30% reduction for complex schemas
    elif is_simple:
        multiplier = 1.5  # 50% increase for simple schemas

    # Scale base batch size and convert to integer
    calculated = int(base_batch * multiplier)

    # Enforce safe boundaries [5, 1000]
    final_batch = max(5, min(calculated, 1000))

    # For very tiny workloads, do not let the batch size exceed total requested rows
    if final_batch > total_rows:
        final_batch = max(5, total_rows)

    return final_batch
