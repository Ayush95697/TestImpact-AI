# TestImpact AI — Synthetic Demo Dataset Guide

## 1. Overview and Purpose

The synthetic demo dataset provides realistic, production-like test engineering data for **TestImpact AI**. It is designed for:
- Testing relational CRUD operations across all entities.
- Validating many-to-many relationship associations (`TestCase` <-> `Module`, `ChangeRequest` <-> `Module`).
- Serving as the future knowledge base for the RAG pipeline once the company embedding API is integrated.
- Demonstrating cross-project isolation in vector search and analytical queries.

> **CRITICAL NOTE ON RAG INDEXING:**
> Vector indexing of this dataset must **wait** until the company's approved embedding API is configured. Attempting to call `/rag/index` or `/rag/search` before setting the required environment variables will return `HTTP 503 Service Unavailable` with a diagnostic message.

---

## 2. Safe Seeding Execution Guide

The seed script is located at `scripts/seed_demo_data.py`. To prevent accidental execution in production or wiping local environments, the script includes strict safety guards.

### Safety Guards
1. **Explicit Confirmation Flag (`--allow-demo-data`)**: The script will refuse to execute unless `--allow-demo-data` is supplied.
2. **Production URL Guard**: The script inspects the target database URL and aborts immediately if it detects production hosts (e.g. `rds.amazonaws.com`, `postgres://prod*`).
3. **Natural Key Idempotency**: Running the script multiple times against the same database is safe. Existing records matching natural keys are detected and skipped without duplicating entities or crashing with constraint violations.
4. **Single Transaction**: All operations execute within an atomic transaction. If any error occurs, all changes roll back.

### Usage Commands

From the `testimpact-ai` directory:

```bash
# 1. Preview changes without writing to database (Dry-run mode)
python scripts/seed_demo_data.py --allow-demo-data --dry-run

# 2. Apply seed data to the default local SQLite database
python scripts/seed_demo_data.py --allow-demo-data

# 3. Apply seed data to an isolated custom database URL
python scripts/seed_demo_data.py --allow-demo-data --db-url sqlite:///./temp_test_seed.db
```

---

## 3. Dataset Summary and Exact Record Counts

The synthetic dataset consists of two completely independent enterprise domains:

| Entity Type | DEMO - Banking Platform | DEMO - E-Commerce Platform | Total Across Database |
| :--- | :---: | :---: | :---: |
| **Projects** | 1 | 1 | **2** |
| **Modules** | 4 | 4 | **8** |
| **Test Cases** | 8 | 8 | **16** |
| **Defects** | 5 | 5 | **10** |
| **Test Executions** | 16 | 16 | **32** |
| **Change Requests** | 3 | 3 | **6** |

---

## 4. Domain Breakdown

### Domain A: DEMO - Banking Platform

Synthetic banking application simulating financial transfers, authentication, session tokens, balance calculations, and transaction histories.

#### Modules
1. **Authentication**: User login, Multi-Factor Authentication (MFA), and JWT session handling.
2. **Dashboard**: Account summary, balances, real-time metrics, and quick navigation widgets.
3. **Money Transfer**: Domestic ACH, wire, and inter-account fund transfer operations.
4. **Transaction History**: Audited account statements, filtering, and historical transaction ledgers.

#### Test Cases (8 total)
1. `Verify valid user login` (High) — Module: Authentication
2. `Reject login with incorrect credentials` (High) — Module: Authentication
3. `Refresh authentication token after an idle session` (Medium) — Module: Authentication
4. `Render account balances accurately on dashboard` (High) — Module: Dashboard
5. `Execute intra-bank transfer with sufficient balance` (High) — Module: Money Transfer
6. `Reject wire transfer exceeding available balance` (High) — Module: Money Transfer
7. `Enforce daily transfer limit policy` (Medium) — Module: Money Transfer
8. `Filter transaction history by custom date range` (Low) — Module: Transaction History

#### Defect History (5 total)
- `Session token expires prematurely under high load` (Critical) — Authentication
- `Dashboard displays cached balance instead of real-time` (Medium) — Dashboard
- `Transfer timeout leaves transaction in pending state indefinitely` (High) — Money Transfer
- `Special characters in beneficiary name crash transfer endpoint` (Medium) — Money Transfer
- `Transaction export CSV contains unmasked account numbers` (High) — Transaction History

#### Execution History (16 total, 2 per test case)
- 12 Passed, 3 Failed, 1 Blocked across builds `v1.2.0-rc1` and `v1.2.0-final`.
- Highlights: Transfer limits and token refresh failed in early release candidate `v1.2.0-rc1` and were subsequently resolved.

#### Change Requests (3 total)
- `CR-BANK-001: Implement Biometric WebAuthn MFA Step-Up` — Impacted: Authentication
- `CR-BANK-002: Add Real-Time Fraud Detection Score on Wire Transfers` — Impacted: Money Transfer
- `CR-BANK-003: Dark Mode Support for Executive Dashboard` — Impacted: Dashboard

---

### Domain B: DEMO - E-Commerce Platform

Synthetic retail and marketplace application managing catalog browsing, cart operations, multi-currency checkout, and payment gateways.

#### Modules
1. **Catalog**: Product listing, full-text search, categories, and faceted filtering.
2. **Shopping Cart**: Cart persistence, item quantity updates, coupons, and discounts.
3. **Checkout**: Order summary, shipping address validation, tax, and inventory reserve.
4. **Payment Gateway**: Stripe and PayPal integration, credit card tokenization, and webhooks.

#### Test Cases (8 total)
1. `Search product catalog using keyword matching` (Medium) — Module: Catalog
2. `Filter catalog items by category and price tier` (Medium) — Module: Catalog
3. `Add item to shopping cart and verify total` (High) — Module: Shopping Cart
4. `Apply percentage discount coupon code` (Medium) — Module: Shopping Cart
5. `Prevent checkout with out-of-stock inventory` (High) — Modules: Shopping Cart, Checkout
6. `Process full checkout workflow with standard shipping` (High) — Module: Checkout
7. `Authorize payment via credit card tokenization` (High) — Module: Payment Gateway
8. `Handle payment gateway timeout and retry gracefully` (High) — Module: Payment Gateway

#### Defect History (5 total)
- `Catalog faceted search produces incorrect product counts` (Low) — Catalog
- `Cart subtotal rounding error when applying multiple coupons` (High) — Shopping Cart
- `Guest checkout fails address postal code validation` (Medium) — Checkout
- `Payment webhook double-processes orders on retry` (Critical) — Payment Gateway
- `3DSecure authentication iframe fails to open on Safari` (High) — Payment Gateway

#### Execution History (16 total, 2 per test case)
- 13 Passed, 2 Failed, 1 Blocked across builds `v2.4.0-beta` and `v2.4.0-stable`.
- Highlights: Payment retry timeout and cart coupon rounding failed during beta before patch stabilization.

#### Change Requests (3 total)
- `CR-ECOM-001: Support Apple Pay and Google Pay Direct Checkout` — Impacted: Payment Gateway, Checkout
- `CR-ECOM-002: Dynamic Tiered Bulk Discounts in Shopping Cart` — Impacted: Shopping Cart
- `CR-ECOM-003: Elasticsearch Integration for Catalog Typo-Tolerance` — Impacted: Catalog

---

## 5. Sample Future RAG Queries and Expected Retrievals

Once the company embedding API is integrated and indexing is executed, these sample queries demonstrate regression impact retrieval:

### Banking Queries
- **Query**: `"Changes to user session timeout and JWT expiration"`
  - **Expected Matching Entities**:
    - Test Case: `Refresh authentication token after an idle session`
    - Defect: `Session token expires prematurely under high load`
    - Change Request: `CR-BANK-001: Implement Biometric WebAuthn MFA Step-Up`
- **Query**: `"Modifications to daily wire limits and fund balance deductions"`
  - **Expected Matching Entities**:
    - Test Case: `Enforce daily transfer limit policy`
    - Test Case: `Reject wire transfer exceeding available balance`
    - Defect: `Transfer timeout leaves transaction in pending state indefinitely`
    - Change Request: `CR-BANK-002: Add Real-Time Fraud Detection Score on Wire Transfers`

### E-Commerce Queries
- **Query**: `"Integration of third-party payment wallets and tokenization"`
  - **Expected Matching Entities**:
    - Test Case: `Authorize payment via credit card tokenization`
    - Defect: `Payment webhook double-processes orders on retry`
    - Change Request: `CR-ECOM-001: Support Apple Pay and Google Pay Direct Checkout`
- **Query**: `"Voucher and coupon code calculations on shopping cart items"`
  - **Expected Matching Entities**:
    - Test Case: `Apply percentage discount coupon code`
    - Defect: `Cart subtotal rounding error when applying multiple coupons`
    - Change Request: `CR-ECOM-002: Dynamic Tiered Bulk Discounts in Shopping Cart`

---

## 6. Cross-Project Isolation Testing

A core requirement of TestImpact AI is strict project isolation: vector search results and regression recommendations must never leak data between unrelated projects.

| Search Query | Query Intended For | Target Project Filter | Permitted Matches | Strictly Forbidden Matches |
| :--- | :--- | :--- | :--- | :--- |
| `"ACH wire transfer and insufficient funds"` | Banking | `DEMO - Banking Platform` | Banking Test Cases 5, 6, 7 | Any Cart, Checkout, or Payment entities |
| `"Shopping cart discounts and coupon codes"` | E-Commerce | `DEMO - E-Commerce Platform` | E-Commerce Test Cases 3, 4 | Any Banking Balance, Transfer, or Ledger entities |
| `"Payment gateway webhook retries"` | E-Commerce | `DEMO - E-Commerce Platform` | Payment Gateway Test Case 8, Defect 4 | Any Banking Authentication or Transfer entities |
| `"Biometric MFA authentication"` | Banking | `DEMO - Banking Platform` | Authentication Test Cases 1, 2, 3 | Any E-Commerce Catalog or Checkout entities |

### How Project Isolation is Enforced
1. **Database Relational Boundary**: Every `Module`, `TestCase`, `Defect`, and `ChangeRequest` references a foreign key `project_id`.
2. **Vector Metadata Filtering**: When documents are indexed into ChromaDB, the `metadata` dictionary contains `project_id`. RAG retrieval requests include an explicit Chroma metadata filter `{"project_id": target_project_id}` ensuring absolute segregation.

