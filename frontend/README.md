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

## Folder Organization

The codebase maintains a clean separation of concerns:
```text
frontend/src/
├── api/             # Centralized HTTP request client and configuration loader
├── components/      # Reusable design system primitives, cards, and feedback components
├── context/         # Global application context stores and custom hooks
├── services/        # Service client hooks querying backend endpoints
├── types/           # Global model interfaces and API response envelopes
├── utils/           # Shared utility tools (e.g., custom logging wrapper)
├── pages.tsx        # View component definitions
├── App.tsx          # Main layout shell and navigation router
└── main.tsx         # Virtual DOM renderer entrypoint
```

---

## Layout Overview

The UI is structured around a responsive global application shell matching modern desktop design architectures:
* **Sidebar (`<aside>`)**: Primary navigation links equipped with status icons, active page highlights, and width toggle controls (expanded `64rem` / `w-64` vs collapsed `20rem` / `w-20`). Responsive breakpoints switch the sidebar to a full-screen drawer layout on tablet/mobile screens.
* **Header (`<header>`)**: Sticky global workspace banner providing viewport menu controls, layout headings, and interactive placeholders for theme toggling and settings management.
* **Content Canvas (`<main>`)**: Accessible core viewing viewport carrying landmarks and focus attributes.
* **Footer (`<footer>`)**: System status info including application version indicators, copyrights, and direct licensing reference links.

---

## Dashboard Overview

The **Dashboard** is the principal operations center summarizing metrics and providing navigation links:
* **Welcome Banner**: Dynamic card welcome layout listing software versions, env variables, and real-time backend API statuses.
* **Quick Actions Toolbar**: Direct navigation button triggers to launch project pages, schema generators, validation checks, mock generators, and exports.
* **Interactive Metrics**: Grid summaries compiling total database projects, verified schema counts, total generated synthetic rows, and templates.
* **Status Diagnostics**: Lists database connectivity parameters, SQLite integrations, git quality gates, and merge conflict status details.

---

## Project Workspace Overview

The **Project Workspace** manages custom database config files:
* **In-Memory Adding**: Interactive Prompt workflow to configure new custom projects on the fly.
* **Filters Toolbar**: Text query search boxes paired with toggle buttons to filter projects between `All`, `Verified`, and `Pending` flags.
* **Empty State Cards**: Renders custom illustrations and CTA actions when query searches yield no matching items.

---

## Design System & Reusable Components

All reusable UI primitives and styling tokens are established in [frontend/src/components/ui.tsx](file:///C:/Users/lovea/Documents/hackathon/safeseedops-lite/frontend/src/components/ui.tsx).

### 1. Theme Styling Tokens

Theme color tokens are configured inside the Tailwind v4 `@theme` directive in `src/index.css`:
* **Primary**: `#4f46e5` (Indigo brand color)
* **Secondary**: `#64748b` (Slate slate color)
* **Success**: `#10b981` (Emerald green)
* **Warning**: `#f59e0b` (Amber yellow)
* **Error**: `#ef4444` (Red error status)
* **Neutral**: `#0f172a` (Deep slate background)
* **Border Radius Scale**: `xl` (12px), `2xl` (16px), `3xl` (24px) for rounded components.

### 2. UI Components & Variants

| Component | Description | Available Variants / Properties |
| :--- | :--- | :--- |
| `Button` | Standard action button with keyboard focus targets. | `variant`: `primary`, `secondary`, `outline`, `ghost`, `danger`. `size`: `sm`, `md`, `lg`. |
| `Card` | Glassmorphic background container. | `hoverable`: boolean (shadow/border hover transition). |
| `Input` | Semantic text input with labels and error handlers. | `label`, `error`, default HTML input properties. |
| `Textarea` | Responsive multi-line text container. | `label`, `error`, `rows`, default HTML properties. |
| `Select` | Dropdown picker with styled arrows. | `label`, `error`, `options` array. |
| `Checkbox` | Styled checkbox with select-none labels. | `label`, `error`, checked attributes. |
| `Badge` | Colored text tag representing states. | `variant`: `info`, `success`, `warning`, `error`. |
| `Alert` | Viewport notification alert card. | `variant`: `info`, `success`, `warning`, `error`, `title`, `onClose`. |
| `Spinner` | Centered loading spinner animation. | `size`: `sm`, `md`, `lg`. |
| `Divider` | Horizontal dividing line with center labels. | `label` (optional text). |

---

## Global Application State

Application-wide state is managed using React Context and custom hooks.

### 1. Store Architecture

The state is split into two primary context providers located under `src/context/`:
* **`AppProvider`**: Responsible for global UI settings (sidebar width mode, mobile drawers toggling), theme preferences, global loading flags, settings parameters, active page headers, and modal indicators.
* **`NotificationProvider`**: Responsible for enqueuing and dequeuing toast banners with auto-dismiss timers.

---

## API Layer & Application Services

Communication with the backend uses a custom, lightweight HTTP client built on standard browser APIs.

### 1. API Environment Configuration

The client reads properties from system environment variables (with defaults):
* `VITE_API_BASE_URL` (Base backend URL, default: `http://localhost:8000`).
* `VITE_API_TIMEOUT` (Request cancellation threshold in milliseconds, default: `10000`).

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
| `/about` | **About** | Platform version specs, metadata resources, and Design System playground. |
| `/settings` | **Settings** | Application configurations and API settings. |
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
