import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_projects(client: AsyncClient) -> None:
    """Test creating a project and listing projects."""
    # List projects initially
    resp = await client.get("/projects")
    assert resp.status_code == 200
    initial_projects = resp.json()
    assert isinstance(initial_projects, list)

    # Create a new project
    proj_payload = {
        "id": "test-proj-persistence",
        "name": "Persistence Test Project",
        "description": "Verify project lifecycle integration.",
        "status": "pending",
    }
    resp = await client.post("/projects", json=proj_payload)
    assert resp.status_code == 201
    created_proj = resp.json()
    assert created_proj["id"] == "test-proj-persistence"
    assert created_proj["name"] == "Persistence Test Project"
    assert created_proj["description"] == "Verify project lifecycle integration."
    assert created_proj["status"] == "pending"

    # List again to confirm persistence
    resp = await client.get("/projects")
    assert resp.status_code == 200
    updated_projects = resp.json()
    assert len(updated_projects) == len(initial_projects) + 1
    ids = [p["id"] for p in updated_projects]
    assert "test-proj-persistence" in ids


@pytest.mark.asyncio
async def test_project_header_resolution(client: AsyncClient) -> None:
    """Test setting schema with X-Project-Id headers."""
    # Create two different projects
    await client.post(
        "/projects",
        json={
            "id": "proj-a",
            "name": "Project A",
            "description": "First test project",
            "status": "pending",
        },
    )
    await client.post(
        "/projects",
        json={
            "id": "proj-b",
            "name": "Project B",
            "description": "Second test project",
            "status": "pending",
        },
    )

    # Save schema for Project A
    schema_a = {
        "tables": [
            {
                "id": "t1",
                "name": "users_a",
                "columns": [
                    {
                        "id": "c1",
                        "name": "id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                        "defaultValue": "",
                    }
                ],
            }
        ],
        "relationships": [],
    }
    resp = await client.post(
        "/schema", json=schema_a, headers={"X-Project-Id": "proj-a"}
    )
    assert resp.status_code == 200

    # Save schema for Project B
    schema_b = {
        "tables": [
            {
                "id": "t2",
                "name": "profiles_b",
                "columns": [
                    {
                        "id": "c2",
                        "name": "id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                        "defaultValue": "",
                    }
                ],
            }
        ],
        "relationships": [],
    }
    resp = await client.post(
        "/schema", json=schema_b, headers={"X-Project-Id": "proj-b"}
    )
    assert resp.status_code == 200

    # Retrieve schema for Project A and check it has users_a table
    resp = await client.get("/schema", headers={"X-Project-Id": "proj-a"})
    assert resp.status_code == 200
    res_a = resp.json()
    assert res_a["tables"][0]["name"] == "users_a"

    # Retrieve schema for Project B and check it has profiles_b table
    resp = await client.get("/schema", headers={"X-Project-Id": "proj-b"})
    assert resp.status_code == 200
    res_b = resp.json()
    assert res_b["tables"][0]["name"] == "profiles_b"
