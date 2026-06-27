import pytest

from app.prompts import (
    PromptAssetLoader,
    PromptBuilder,
    PromptNotFoundError,
    PromptRenderer,
    PromptTemplate,
    PromptTemplateError,
    PromptValidationError,
    registry,
)


@pytest.fixture(autouse=True)
def clean_registry() -> None:
    """Fixture to ensure the global registry is cleared before each test."""
    registry.clear()


def test_prompt_builder() -> None:
    """Test building a PromptTemplate using PromptBuilder sections."""
    builder = PromptBuilder()
    builder.set_system_instructions("You are a database designer assistant.")
    builder.add_developer_instructions("Use standard SQL syntax.")
    builder.add_developer_instructions("Always lowercase keywords.")
    builder.add_task_instructions("Create table {{ table_name }}.")
    builder.add_context("Available keys: {{ keys }}.")
    builder.add_constraints("No drop tables allowed.")
    builder.set_expected_output("Return CREATE TABLE only.")

    template = builder.build(name="sql_gen", version="1.0.0")

    assert template.name == "sql_gen"
    assert template.version == "1.0.0"
    assert template.system_template == "You are a database designer assistant."

    expected_body = (
        "### Developer Instructions\n"
        "Use standard SQL syntax.\n"
        "Always lowercase keywords.\n"
        "\n"
        "### Task Instructions\n"
        "Create table {{ table_name }}.\n"
        "\n"
        "### Context\n"
        "Available keys: {{ keys }}.\n"
        "\n"
        "### Constraints\n"
        "No drop tables allowed.\n"
        "\n"
        "### Expected Output\n"
        "Return CREATE TABLE only."
    )
    assert template.prompt_template == expected_body


def test_prompt_registry() -> None:
    """Test template registration and retrieval (latest vs explicit version)."""
    t1 = PromptTemplate(name="test_tmpl", version="1.0.0", prompt_template="Prompt v1")
    t2 = PromptTemplate(name="test_tmpl", version="1.1.0", prompt_template="Prompt v2")
    t3 = PromptTemplate(
        name="another_tmpl", version="1.0.0", prompt_template="Other prompt"
    )

    registry.register(t1)
    registry.register(t2)
    registry.register(t3)

    # Retrieval of explicit versions
    assert registry.get("test_tmpl", "1.0.0").prompt_template == "Prompt v1"
    assert registry.get("test_tmpl", "1.1.0").prompt_template == "Prompt v2"

    # Retrieval of latest version (1.1.0 is lexicographically greater than 1.0.0)
    assert registry.get("test_tmpl").version == "1.1.0"
    assert registry.get("test_tmpl").prompt_template == "Prompt v2"

    # Raises when not found
    with pytest.raises(PromptNotFoundError):
        registry.get("non_existent")

    with pytest.raises(PromptNotFoundError):
        registry.get("test_tmpl", "2.0.0")


def test_prompt_renderer_success() -> None:
    """Test successful prompt template rendering and deterministic hashing."""
    template = PromptTemplate(
        name="query_tmpl",
        version="1.0.0",
        system_template="Role: {{ role }}",
        prompt_template="Select from {{ table }} where id = {{ id }}.",
    )

    variables = {"role": "analyzer", "table": "users", "id": 42}
    rendered = PromptRenderer.render(template, variables)

    assert rendered.system_instruction == "Role: analyzer"
    assert rendered.prompt_text == "Select from users where id = 42."
    assert rendered.template_name == "query_tmpl"
    assert rendered.template_version == "1.0.0"

    # Hash should be stable, deterministic SHA-256 string (length 64)
    assert len(rendered.prompt_hash) == 64

    # Identical rendering generates identical hash
    rendered_dup = PromptRenderer.render(template, variables)
    assert rendered.prompt_hash == rendered_dup.prompt_hash

    # Different variables yield different hash
    variables_diff = {"role": "analyzer", "table": "users", "id": 99}
    rendered_diff = PromptRenderer.render(template, variables_diff)
    assert rendered.prompt_hash != rendered_diff.prompt_hash


def test_prompt_renderer_error() -> None:
    """Test that rendering failure raises PromptTemplateError."""
    # Place a malformed Jinja variable tag
    template = PromptTemplate(
        name="bad_tmpl",
        version="1.0.0",
        prompt_template="Select from {{ table ",  # unmatched bracket
    )

    with pytest.raises(PromptTemplateError):
        PromptRenderer.render(template, {"table": "users"})


def test_asset_loader_success() -> None:
    """Test loading and compiling the schema_validation prompt template from files."""
    loader = PromptAssetLoader()
    template = loader.load_prompt("schema_validation")

    assert template.name == "schema_validation"
    assert template.version == "1.0.0"
    assert template.metadata is not None
    assert template.metadata.provider == "Google"
    assert template.metadata.model == "gemini-1.5-pro"
    assert template.metadata.temperature == 0.1

    # Test rendering the loaded prompt template
    variables = {"schema_ddl": "CREATE TABLE customers (id INT PRIMARY KEY);"}
    rendered = PromptRenderer.render(template, variables)

    assert "SeedOps" in rendered.system_instruction
    assert "### Task Instructions" in rendered.prompt_text
    assert "CREATE TABLE customers" in rendered.prompt_text
    assert rendered.provider == "Google"
    assert rendered.model == "gemini-1.5-pro"
    assert rendered.temperature == 0.1
    assert rendered.expected_response is not None
    assert rendered.estimated_tokens > 0
    assert len(rendered.prompt_hash) == 64


def test_asset_loader_missing_metadata(tmp_path) -> None:
    """Test that loading from a directory with missing metadata.yaml fails."""
    # Create empty agent directory
    agent_dir = tmp_path / "missing_meta"
    agent_dir.mkdir()

    loader = PromptAssetLoader(templates_dir=tmp_path)
    with pytest.raises(PromptNotFoundError):
        loader.load_prompt("missing_meta")


def test_asset_loader_invalid_metadata(tmp_path) -> None:
    """Test that invalid YAML metadata structure fails validation checks."""
    agent_dir = tmp_path / "bad_meta"
    agent_dir.mkdir()

    # Create invalid YAML (missing name and version)
    meta_file = agent_dir / "metadata.yaml"
    meta_file.write_text("description: missing required fields", encoding="utf-8")

    loader = PromptAssetLoader(templates_dir=tmp_path)
    with pytest.raises(PromptValidationError):
        loader.load_prompt("bad_meta")


def test_asset_loader_inheritance_and_overrides(tmp_path) -> None:
    """Test that agent specific files properly override common templates."""
    common_dir = tmp_path / "common"
    common_dir.mkdir()
    (common_dir / "system.md").write_text("Common System", encoding="utf-8")
    (common_dir / "constraints.md").write_text("Common Constraints", encoding="utf-8")

    agent_dir = tmp_path / "custom_agent"
    agent_dir.mkdir()
    (agent_dir / "system.md").write_text("Overridden System", encoding="utf-8")
    (agent_dir / "task.md").write_text("Agent Task", encoding="utf-8")

    # Metadata
    (agent_dir / "metadata.yaml").write_text(
        "name: custom_agent\nversion: 2.0.0", encoding="utf-8"
    )

    loader = PromptAssetLoader(templates_dir=tmp_path)
    template = loader.load_prompt("custom_agent")

    assert template.name == "custom_agent"
    assert template.version == "2.0.0"
    # System should be overridden
    assert template.system_template == "Overridden System"
    # Constraints should be inherited from common
    assert "Common Constraints" in template.prompt_template
    # Task should be agent specific
    assert "Agent Task" in template.prompt_template


def test_prompt_builder_with_safety() -> None:
    """Test building a PromptTemplate containing a Safety Guidelines section."""
    builder = PromptBuilder()
    builder.set_system_instructions("System instructions")
    builder.add_constraints("Constraint 1")
    builder.add_safety_instructions("Safety 1")
    builder.add_safety_instructions("Safety 2")
    builder.set_expected_output("Expected Output 1")

    template = builder.build(name="safety_test", version="1.0.0")

    expected_body = (
        "### Constraints\n"
        "Constraint 1\n"
        "\n"
        "### Safety Guidelines\n"
        "Safety 1\n"
        "Safety 2\n"
        "\n"
        "### Expected Output\n"
        "Expected Output 1"
    )
    assert template.prompt_template == expected_body


def test_asset_loader_safety_inheritance(tmp_path) -> None:
    """Test that safety guidelines are inherited or overridden correctly."""
    common_dir = tmp_path / "common"
    common_dir.mkdir()
    (common_dir / "system.md").write_text("Common System", encoding="utf-8")
    (common_dir / "safety.md").write_text("Common Safety Guidelines", encoding="utf-8")

    agent_dir = tmp_path / "safety_agent"
    agent_dir.mkdir()
    (agent_dir / "metadata.yaml").write_text(
        "name: safety_agent\nversion: 1.0.0", encoding="utf-8"
    )

    loader = PromptAssetLoader(templates_dir=tmp_path)
    template = loader.load_prompt("safety_agent")

    # Verify safety is inherited from common
    assert "Common Safety Guidelines" in template.prompt_template

    # Now override in agent dir
    (agent_dir / "safety.md").write_text(
        "Overridden Safety Guidelines", encoding="utf-8"
    )
    template_override = loader.load_prompt("safety_agent")
    assert "Overridden Safety Guidelines" in template_override.prompt_template
    assert "Common Safety" not in template_override.prompt_template


def test_prompt_renderer_propagates_metadata() -> None:
    """Test that all metadata fields are correctly set on the RenderedPrompt."""
    from app.prompts.metadata import PromptMetadata

    metadata = PromptMetadata(
        name="test_meta",
        version="1.0.0",
        description="A test prompt",
        owner="test-owner",
        provider="Google",
        model="gemini-1.5-pro",
        temperature=0.7,
        max_output_tokens=1000,
        timeout_seconds=60.0,
        retry_count=4,
        expected_response="JSON format",
        cacheable=False,
        telemetry_enabled=False,
        cost_tracking=False,
        tags=["t1", "t2"],
    )

    template = PromptTemplate(
        name="test_meta",
        version="1.0.0",
        prompt_template="Select * from users;",
        metadata=metadata,
    )

    rendered = PromptRenderer.render(template, {})

    assert rendered.template_name == "test_meta"
    assert rendered.template_version == "1.0.0"
    assert rendered.provider == "Google"
    assert rendered.model == "gemini-1.5-pro"
    assert rendered.temperature == 0.7
    assert rendered.max_output_tokens == 1000
    assert rendered.timeout_seconds == 60.0
    assert rendered.retry_count == 4
    assert rendered.expected_response == "JSON format"
    assert rendered.cacheable is False
    assert rendered.telemetry_enabled is False
    assert rendered.cost_tracking is False
    assert rendered.tags == ["t1", "t2"]
    assert rendered.estimated_tokens > 0
