# End-to-End Test Plan & Checklist — SafeSeedOps Lite

This test plan lists all manual verification procedures to validate the SafeSeedOps Lite application workflow from workspace configuration to final export delivery.

---

## Workspace Setup & Bootstrap

| Step | Action | Expected Result | Actual Result | Status | Notes |
|---|---|---|---|---|---|
| **1** | Run `redis-server` locally. | Redis starts listening on port `6379`. | | | |
| **2** | Copy `.env.example` to `.env` and configure port bindings. | `.env` file successfully created. | | | |
| **3** | Run `uv run uvicorn app.main:app --reload` in backend. | FastAPI server runs on `http://127.0.0.1:8000` with zero exceptions. | | | |
| **4** | Run `npm run dev` inside `frontend/` directory. | Vite starts local dev server at `http://localhost:5173`. | | | |
| **5** | Navigate browser to `http://localhost:5173`. | Web UI renders successfully, and a "Backend Connected" toast notification is shown in the top right. | | | |

---

## Schema Designer Workflows

| Step | Action | Expected Result | Actual Result | Status | Notes |
|---|---|---|---|---|---|
| **6** | Navigate to the **Projects** page. | Displays the templates list containing default schemas. | | | |
| **7** | Click "Load Default Template". | Loads the default template containing `users` and `orders` tables. | | | |
| **8** | Navigate to **Schema Generator**. | Table cards for `users` and `orders` render on the design canvas. | | | |
| **9** | Click "Add Table" on the canvas. | Creates a new table card with a placeholder name. | | | |
| **10** | Edit table name to `products`. | Title header input successfully changes to `products`. | | | |
| **11** | Click "Add Column" in the `products` table. | Appends an empty column row definition. | | | |
| **12** | Input name `id`, type `INTEGER`, and check the "PK" checkbox. | Column `id` is set as the primary key. | | | |
| **13** | Add another column: `price`, type `FLOAT`. | Column `price` is added successfully. | | | |
| **14** | Add column `product_id` to the `orders` table. | Column `product_id` appears inside the `orders` table card. | | | |
| **15** | Click "Add Relationship" and set: Source `orders.product_id` -> Target `products.id`. | Relational connection line appears on the canvas or relationship list. | | | |
| **16** | Click "Save Schema" in the action toolbar. | Displays a "Schema saved successfully" notification. | | | |

---

## Validation & AI Review Workflows

| Step | Action | Expected Result | Actual Result | Status | Notes |
|---|---|---|---|---|---|
| **17** | Navigate to the **Schema Validation** page. | Displays the validation auditor and AI assistant panels. | | | |
| **18** | Click the "Validate Design" button. | Validation rule engine runs, returning green "Passed" checkmarks for all schema standards. | | | |
| **19** | Click "Ask AI Assistant" (requires `GEMINI_API_KEY`). | Loader spinner displays, and Gemini suggestions (Naming, best practices) render inside the panel. | | | |

---

## Data Generation Workflows

| Step | Action | Expected Result | Actual Result | Status | Notes |
|---|---|---|---|---|---|
| **20** | Navigate to the **Data Generation** page. | Shows target row inputs for `users`, `orders`, and `products`. | | | |
| **21** | Set targets: `users` = 50, `products` = 20, `orders` = 100. | Values are successfully inputted. | | | |
| **22** | Click the "Start Generation" button. | Generation job queues. Progress bars appear for each table. | | | |
| **23** | Observe the topological generation order. | `products` and `users` generate first (since they are target references), then `orders` generates. | | | |
| **24** | Verify generation transitions to `Completed`. | Banner shows success: "Successfully generated 170 rows" in elapsed seconds. | | | |

---

## Job History & Auditing Workflows

| Step | Action | Expected Result | Actual Result | Status | Notes |
|---|---|---|---|---|---|
| **25** | Navigate to the **Job History** page. | Shows the generation job in the historical table list. | | | |
| **26** | Verify the job is recorded as `Completed` with `100%` progress. | Match values and verify the started timestamp is accurate. | | | |

---

## Export & Download Workflows

| Step | Action | Expected Result | Actual Result | Status | Notes |
|---|---|---|---|---|---|
| **27** | Navigate to the **Export** page. | Shows export settings panel. | | | |
| **28** | Select the completed generation run from the dropdown. | Loads dataset session parameters. | | | |
| **29** | Select format `CSV` and check "ZIP Archive". | Configures zip packaging. | | | |
| **30** | Click "Start Export" button. | Starts export background task. | | | |
| **31** | Click the "Download File" button after completion. | Downloads a `.zip` archive containing separate CSV files for each table. | | | |
