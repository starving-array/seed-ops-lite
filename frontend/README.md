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

### 3. Layout Helpers

* `Container` – Max-width `7xl` layout centering helper.
* `PageHeader` – Semantic page title header with custom sub-description spacing.
* `Section` – Standard spacing utility for document blocks.
* `Stack` – Flex-based layout. Supports `direction` (`col`, `row`) and `gap` (`sm`, `md`, `lg`).
* `Grid` – CSS Grid wrapper. Supports `cols` (`1`, `2`, `3`, `4`) with automatic tablet/mobile scaling.

### 4. System Feedback States

* `EmptyState` – Displayed when no data is loaded. Includes illustration emojis, descriptions, and action trigger buttons.
* `LoadingState` – Full-page spinning loader with animated text.
* `ErrorState` – Card displaying error logs and retry CTA buttons.

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
