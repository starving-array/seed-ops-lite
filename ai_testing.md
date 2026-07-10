# QA Test Report: Data Generation Pipeline

**Date:** 2026-07-10
**Provider:** Ollama (model: llama3)
**Schema:** 3-table e-commerce (customers → orders → order_items)

---

## 1. DDL Import → Schema Parsing

### Input DDL (3 tables, FK chain)

```sql
CREATE TABLE customers (
    customer_id   UUID PRIMARY KEY,
    customer_code VARCHAR(20) NOT NULL UNIQUE,
    customer_name VARCHAR(100) NOT NULL,
    phone         VARCHAR(20),
    email         VARCHAR(100),
    city          VARCHAR(100),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders (
    order_id     UUID PRIMARY KEY,
    customer_id  UUID NOT NULL REFERENCES customers(customer_id),
    order_no     VARCHAR(50) NOT NULL UNIQUE,
    order_date   DATE NOT NULL,
    shipped_date DATE,
    status       VARCHAR(30),
    subtotal     DECIMAL(12,2),
    tax          DECIMAL(12,2),
    shipping_fee DECIMAL(12,2),
    grand_total  DECIMAL(12,2)
);

CREATE TABLE order_items (
    order_item_id UUID PRIMARY KEY,
    order_id      UUID NOT NULL REFERENCES orders(order_id),
    product_name  VARCHAR(200) NOT NULL,
    quantity      INTEGER NOT NULL,
    unit_price    DECIMAL(12,2) NOT NULL,
    line_total    DECIMAL(12,2)
);
```

### Result: Schema created successfully with 3 tables, 2 FK relationships.

---

## 2. Data Generation

- **Workflow:** `625e3aa8-bd40-4008-8319-bebbb0dfc753`
- **Status:** Generation completed (preview available, rows visible)
- **Row count:** 10 per table (30 total)

---

## 3. Bug Inventory

### Bug #1: Status endpoint returns 404

- **File:** `app/api/endpoints/schema/generation.py`
- **Issue:** `GET /schema/generate/{workflow_id}/status` returns HTTP 404 — the route does not exist.
- **Only available:** `GET /schema/generate/{workflow_id}` returns the full status object.

### Bug #2: `isNullable` always `true` on DDL import

- **File:** `app/api/endpoints/schema/designer.py` (line 168), `app/validation/ddl_validator.py`
- **Root cause:** `DDLValidator.ColumnDef` (line 36-50) has no `is_nullable` field. The parser ignores `NOT NULL`/`NULL` constraints. `designer.py` hardcodes `isNullable=True` for all columns.
- **Affected columns:** All 22 columns across 3 tables show `isNullable: true` regardless of DDL `NOT NULL` declarations.
- **Impact:** The system cannot enforce NOT NULL constraints; null data could be generated for required fields.

### Bug #3: `grand_total` ignores `shipping_fee` column

- **File:** `app/seeder/math_computer.py` (line 85)
- **Code:** `shipping_raw = record.get("shipping")` — looks for key `"shipping"`.
- **DDL column:** `shipping_fee` — the column exists as `shipping_fee`, not `shipping`.
- **Result:** `shipping_raw` is always `None`, defaults to `0.0`.
- **Formula:** `grand_total = subtotal - discount + tax + shipping` → shipping is always 0.
- **Data:** **10/10 orders** have wrong grand_total values.
  - Example: subtotal=74.84, tax=1.72, shipping_fee=53.34 → grand_total=76.56 (should be 129.90)

### Bug #4: `line_total` not computed for order_items

- **File:** `app/seeder/math_computer.py` (line 32-52)
- **Code:** Only computes `subtotal = quantity × unit_price` for columns named `"subtotal"`.
- **DDL column:** `line_total` — the order_items table uses `line_total`, not `subtotal`.
- **Result:** MathComputer never touches `line_total`. The AI generates arbitrary values.
- **Data:** **10/10 order_items** have wrong line_total values.
  - Example: quantity=701, unit_price=29.79 → line_total=43.24 (AI-generated, not 701×29.79=20,882.79)

### Bug #5: Export format parameter ignored

- **File:** `app/api/endpoints/schema/export.py` (lines 440-441)
- **Issue:** The download handler's disk fallback (`stream_multi_table_zip`) always returns a fixed ZIP containing CSV files, regardless of the requested format (JSON, CSV, or SQL).
- **All three formats return identical 3535-byte ZIP** with the same contents (CSV files).
- **Primary path:** The `ExportEngine` with correct format conversion runs in a background task, but if the RuntimeProvider cache hasn't been populated by the time download is requested, the disk fallback silently serves incorrect format.

### Bug #6: Export always ZIP even with `compression: false`

- **File:** `app/api/endpoints/schema/export.py` (line 161)
- **Code:** `if zip_placeholder or len(serialized_data) > 1:`
- **Issue:** For multi-table datasets (3 tables → 3 files), `len(serialized_data) > 1` is True, so ZIP is always used regardless of `compression` setting.

### Bug #7: Unrealistic quantity values

- **File:** AI generation prompt (no explicit range constraints)
- **Data:** Quantities in order_items: 701, 397, 237, 887, 959, 722, 146, 123, 993, 893
- **Expected:** 1-5 for e-commerce order items
- **Impact:** unrealistic training/test data for any ML or demo purpose

---

## 4. What Worked Correctly

| Check | Result |
|---|---|
| FK referential integrity (customers→orders) | 10/10 OK |
| FK referential integrity (orders→order_items) | 10/10 OK |
| `customer_code` generated (CUS001-CUS010) | ✓ |
| `order_no` generated (ORD123456789, etc.) | ✓ |
| `shipped_date` after `order_date` | All chronologically correct |
| UUID v5 primary keys | All unique, valid UUIDs |
| 10 rows per table | ✓ |
| Timestamp/dates within 2026 range | ✓ |

---

## 5. Token & Performance Statistics

| Metric | Value |
|---|---|
| Total tokens | 22,024 |
| Input tokens | 6,092 |
| Output tokens | 9,873 |
| Tokens per job | ~501 |
| Model | llama3 (Ollama) |
| Estimated cost | $0.0021 |

---

## 6. Recommendations (Priority Order)

1. **Add route** `GET /schema/generate/{workflow_id}/status` or fix the client to use the existing `GET /schema/generate/{workflow_id}` endpoint.
2. **Fix MathComputer** — add column name aliases:
   - `"shipping"` should also match `"shipping_fee"`
   - `"line_total"` should be treated like `"subtotal"` (quantity × unit_price)
   - Consider adding a column-name mapping table for known business field aliases.
3. **Fix DDL parser** — add `is_nullable` to `ColumnDef` in `DDLValidator`, parse `NOT NULL`/`NULL` constraints, and pass through to `ColumnModel`.
4. **Fix export** — ensure the download endpoint waits for background processing or verify format is respected before serving.
5. **Add field-level constraints** — limit ranges for numeric fields (e.g., quantity max=10) and validate values against realistic business ranges.

---

## 7. Summary

The pipeline successfully:
- Parsed a 3-table DDL with FK chain
- Generated 30 rows with valid UUIDs, dates, and FK references
- Preserved code-pattern fields (customer_code, order_no)

**But 6 bugs were found** that affect data quality (wrong computed fields, missing nullable info) and API reliability (missing endpoint, format parameter ignored). The two MathComputer bugs (grand_total, line_total) mean **20/30 rows have incorrect monetary values**, making the export unfit for use without fixes.
