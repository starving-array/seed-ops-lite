import asyncio
import json
from httpx import AsyncClient
from app.main import app

async def verify_endpoints():
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        # Check Dashboard (Schema stats)
        print("--- Dashboard (Schema stats) ---")
        resp = await client.get("/api/v1/schema/stats")
        print(json.dumps(resp.json(), indent=2))
        
        # Check Analytics
        print("\n--- Analytics ---")
        resp = await client.get("/api/v1/llm/analytics")
        print(json.dumps(resp.json(), indent=2))

        # Check Export Datasets
        print("\n--- Export Datasets ---")
        resp = await client.get("/api/v1/schema/export/datasets")
        print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(verify_endpoints())
