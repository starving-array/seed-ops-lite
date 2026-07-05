# SafeSeedOps Lite — Component Inventory

This document details the inventory of reusable client components and backend manager services frozen for SafeSeedOps Lite v1.0.0-rc1.

## 1. UI Primitives (`frontend/src/components/ui.tsx`)
*   **Button:** Standard click triggers supporting outline, ghost, primary, secondary, and danger styles.
*   **Card:** Backdrop cards with hover borders.
*   **Input, Textarea, Select, Checkbox:** Uniform input fields with focus indicators and label-mapping support.
*   **Badge & Alert:** Status-colored chips and notice boxes featuring dismiss controls.
*   **Spinner & LoadingState:** Animated loading loops with descriptions.
*   **Divider:** Upper-cased bordered section breakers.

## 2. Layout Elements
*   **Container, Section, Stack, Grid:** Responsive wrapper elements.

## 3. Backend Services & Controllers
*   **DeveloperStartupManager (`app/services/developer_startup.py`):** Environment validation checks and startup diagnostics.
*   **DDLValidator (`app/validation/ddl_validator.py`):** Lexical parsing of SQL input schemas.
*   **GuardianPlanner (`app/agents/guardian/planner.py`):** Cost calculations and topological execution plan compiler.
*   **NotificationManager (`app/services/notification.py`):** Interactive event notifications.
