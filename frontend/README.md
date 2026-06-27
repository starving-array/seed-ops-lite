# SafeSeed-Ops Frontend Workspace

This is the official frontend project workspace foundation for **SafeSeed-Ops**.

---

## Technology Stack

The frontend is bootstrapped with a modern, high-performance, standards-compliant web stack:
1. **React 19** - Component-based user interface library.
2. **TypeScript** - Strict syntactical type-safety.
3. **Vite** - Lightning-fast frontend build tooling and HMR server.
4. **Tailwind CSS v4** - Utility-first styling engine for rapid design systems.
5. **Vitest** - Fast, native unit test runner integrated with Vite.

---

## Layout Overview

The UI is structured around a responsive global application shell matching modern desktop design architectures:
* **Sidebar (`<aside>`)**: Primary navigation links equipped with status icons, active page highlights, and width toggle controls (expanded `64rem` vs collapsed `20rem`). Responsive breakpoints switch the sidebar to a full-screen drawer layout on tablet/mobile screens.
* **Header (`<header>`)**: Sticky global workspace banner providing viewport menu controls, layout headings, and interactive placeholders for theme toggling and settings management.
* **Content Canvas (`<main>`)**: Accessible core viewing viewport carrying landmarks and focus attributes.
* **Footer (`<footer>`)**: System status info including application version indicators, copyrights, and direct licensing reference links.

---

## Routing Guide

Routing is managed client-side using `react-router-dom`. The following routes have been registered:

| Path | View | Description |
| :--- | :--- | :--- |
| `/` | *Redirect* | Fallback redirect pointing to `/dashboard`. |
| `/dashboard` | **Dashboard** | Operations hub summarizing running instances and agent status. |
| `/projects` | **Projects** | Workspace database configuration schema workspace. |
| `/schema-generator` | **Schema Generator** | Visual relational database table modeler. |
| `/schema-validation` | **Schema Validation** | Semantic validation controller for multi-agent loops. |
| `/data-generation` | **Data Generation** | Configuration and runner controls for synthetic data generation runs. |
| `/export` | **Export** | Export compiler to target files (CSV, SQL, JSON). |
| `/observability` | **Observability** | Telemetry logs, traces, and metrics console. |
| `/settings` | **Settings** | Application configurations and API settings. |
| `/about` | **About** | Platform version specs and metadata resources. |
| `*` | **NotFound (404)** | Error screen triggered on invalid view routes. |

---

## Getting Started

### 1. Installation

To install all workspace dependencies, navigate to the frontend directory and run:
```bash
npm install
```

### 2. Development Mode

To start the local hot-reloading development server:
```bash
npm run dev
```

### 3. Running Lint and Quality Checks

To execute ESLint check diagnostics:
```bash
npm run lint
```

### 4. Running Unit Tests

To execute the Vitest suite:
```bash
npm run test
```

### 5. Production Compiling & Building

To generate optimized, production-ready static assets in the `dist/` directory:
```bash
npm run build
```
