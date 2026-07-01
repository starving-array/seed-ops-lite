# UI Functional Specification — SafeSeedOps Lite

This document describes the functional specification of the user interface for **SafeSeedOps Lite**, covering the purpose, navigation, UI controls, validation rules, state transitions, and backend API interactions for each page/workspace.

---

## Global Layout & Navigation

### 1. Navigation Sidebar
*   **Purpose**: Central navigation across the workspace features.
*   **Links**:
    *   📊 **Dashboard**: System overview, operations metrics, and quick starts.
    *   📁 **Projects**: Schema templates and project workspace management.
    *   🛠️ **Schema Generator**: Visual builder for tables, columns, and relationships.
    *   🛡️ **Schema Validation**: Rule validation engine and Gemini-powered AI Assistant.
    *   ⚙️ **Data Generation**: Row count targets and output format configurations.
    *   ⏱️ **Job History**: Operational audit log for all active and historical jobs.
    *   📥 **Export**: Serializer and downloader workspace.
    *   📈 **Observability**: Live logging, telemetry, and system traces (Placeholder).
    *   ⚙️ **Settings**: Global configuration and connection pools (Placeholder).
    *   ℹ️ **About**: Primitives showcase and version information.
*   **Sidebar States**: Collapsible sidebar with desktop responsive overlay and mobile drawer toggle.
*   **System Connectivity Indicator**: A status badge in the sidebar header reflecting real-time FastAPI connection status (`Connected` [green], `Connecting` [blue], `Offline` [red], `Timeout` [orange]).

---

## Feature Workspace Details

### 1. Dashboard Page
*   **Purpose**: Displays high-level analytics, active operations, and short summaries.
*   **Metrics Cards**:
    *   **Schema Size**: Number of tables and relationships configured.
    *   **Active Jobs**: Running background generation and export tasks.
    *   **Success Rate**: Percentage of completed operations in history.
*   **Quick Starts**: Fast navigation buttons to "Open Schema Designer" and "Start Generating Data".
*   **Recent Activity**: A list of the 3 most recent background operations showing their type, duration, and status.

### 2. Projects Page
*   **Purpose**: Manages multiple design files and workspace configurations.
*   **Controls**:
    *   `New Project` button: Opens a modal with forms:
        *   **Name**: Input string (Required, unique).
        *   **Description**: Optional text.
        *   **Category**: Dropdown (e.g. Development, Staging, Demo).
    *   `Load Project` card action: Overwrites current visual canvas with template schema.
    *   `Delete Project` action: Removes the workspace from storage.

### 3. Schema Generator Page
*   **Purpose**: Visual design builder for database tables and relationships.
*   **Interactive Components**:
    *   **Visual Grid/Canvas**: Contains table panels.
    *   `Add Table` Button: Creates a new empty table block on the canvas.
    *   `Save Schema` Button: Serializes the design and sends a `POST /schema` request.
    *   `Reset Schema` Button: Discards changes and resets to the default two-table layout.
    *   **Table Card Controls**:
        *   **Table Name**: Editable header input string.
        *   `Delete Table` Button: Removes the table and all its foreign key associations.
        *   `Add Column` Button: Adds a new column entry row.
    *   **Column Entry Controls**:
        *   **Name**: Input string.
        *   **Type**: Dropdown list (INTEGER, VARCHAR, FLOAT, BOOLEAN, TEXT, TIMESTAMP, DATE, UUID, JSON).
        *   **Primary Key (PK)**: Checkbox/Toggle.
        *   **Nullable**: Checkbox/Toggle.
        *   **Default Value**: Optional input string.
        *   `Delete Column` Button.
    *   **Relationship Panel**:
        *   `Add Relationship` Button: Opens settings form:
            *   **Name**: Unique constraint identifier.
            *   **Source Table**: Dropdown selection.
            *   **Source Column**: Dropdown selection.
            *   **Target Table**: Dropdown selection.
            *   **Target Column**: Dropdown selection.
            *   **Cardinality**: Dropdown (`many-to-one`, `one-to-one`, `many-to-many`).
*   **Validations**:
    *   Table/Column names must start with a letter/underscore and contain only alphanumeric/underscore characters.
    *   Warns if SQL reserved keywords are utilized.

### 4. Schema Validation Page
*   **Purpose**: Automated constraint auditing and AI-assisted review.
*   **Workspaces**:
    *   **Rules Auditor**: Triggers `POST /schema/validate`. Displays a card list of rules:
        *   `Passed` (Green): Name checks, primary keys check, datatype checks.
        *   `Warning` (Yellow): Case naming conventions, reserved keywords, self-references.
        *   `Error` (Red): Duplicate table names, duplicate columns, missing columns, duplicate relationships.
    *   **AI Schema Assistant**: Triggers `POST /schema/ai-assist`.
        *   `Ask AI Assistant` Button: Submits DDL schema to Google Gemini.
        *   **Loading State**: Spinner showing "AI Agent is analyzing database constraints...".
        *   **Result**: Renders markdown suggestions showing category, severity (`low`/`medium`/`high`), title, description, and suggested action.

### 5. Data Generation Page
*   **Purpose**: Focus exclusively on dataset creation using simplified options, offloading export concerns to the dedicated Export workspace.
*   **Generation Modes**:
    *   **Quick Generate (Default)**: Optimized for first-time users. Exposes only a **Dataset Size** selector with presets: `100`, `1,000`, `10,000`, `100,000` records. All table row allocations and batch parameters are determined automatically.
    *   **Advanced Settings**: Available for detailed configurations. Includes:
        *   Custom target row inputs per table.
        *   Toggles to enable/disable specific tables.
*   **Generation Summary Step**:
    *   Triggers when clicking "Start/Apply Seeding" from either mode.
    *   Displays a confirmation box summarizing:
        *   **Active Tables count**
        *   **Total Estimated Records**
        *   **Active Relationships count**
        *   **Estimated Generation Time**
        *   **Estimated Heap Memory Usage** (`Low` / `Medium` / `High`)
        *   **Generation Strategy** (`Automatic`)
    *   Provides two controls: `Start Generating` (starts the workflow) and `Cancel` (returns to config).
*   **Running Progress Experience**:
    *   Displays overall status (Queued/Running).
    *   Simplifies stats to show: **Current Stage**, **Current Table**, **Rows Generated**, **Overall Progress Bar**, and **Estimated Time Remaining**.
    *   Suppresses developer-centric details (e.g. Batch Size, Random Seed, internal execution metrics).
    *   Provides a **Cancel Data Generation** button to gracefully abort the running seeding task.
*   **Completion Experience**:
    *   Displays validation success checkmark and statistics: Rows Generated, Duration, and Tables Seeded.
    *   Offers four user options:
        *   **Preview Dataset**: Opens an inline modal containing tabbed sheets for reviewing up to 10 sample records from any generated table.
        *   **Export Dataset**: Navigates the user to the Export workspace (`/export?workflowId=<workflowId>`) with the generated dataset automatically selected.
        *   **Generate Again**: Resets screen back to default configurations.
        *   **Return to Dashboard**: Navigates back to the main system dashboard (`/`).
*   **Failed state**: Displays the error cause and permits resetting the form to reconfigure parameters.

### 6. Job History Page
*   **Purpose**: Log and audit trail of operational background jobs.
*   **Table Columns**:
    *   **Job ID**: Workflow UUID link.
    *   **Type**: `Generation` or `Export`.
    *   **Status Badge**: `Queued` (gray), `Running` (blue), `Completed` (green), `Cancelled` (orange), `Failed` (red).
    *   **Progress**: Percentage complete bar.
    *   **Started At**: UTC timestamp.
    *   **Duration**: Elapsed seconds.
    *   **Action**: `Cancel` button for active running jobs.

### 7. Export Page
*   **Purpose**: Package and serialize generated datasets for delivery.
*   **Inputs**:
    *   **Source Dataset**: Dropdown listing completed generation sessions (`GET /schema/export/datasets`).
    *   **Format**: Dropdown selector (`JSON`, `CSV`, `SQL`).
    *   **Tables Selection**: Checkboxes to export only a subset of tables.
    *   **Compression**: Checkbox to package results into a ZIP archive.
    *   **Metadata**: Checkbox to append `metadata.json` (timestamp, format, row counts) into the package.
    *   **Filename Convention**: Select list (`Default (dataset_uuid)`, `Timestamp`).
*   **Actions**:
    *   `Start Export` Button: Triggers `POST /schema/export`.
    *   `Download File` Button: Triggers GET request to download the generated file stream.
