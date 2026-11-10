import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, SQLALCHEMY_DATABASE_URL
from app.models import (
    ChangeRequest,
    Defect,
    Module,
    Project,
    TestCase,
    TestExecution,
)

# =====================================================================
# DATA FIXTURES
# =====================================================================

BANKING_DATA = {
    "project": {
        "name": "DEMO - Banking Platform",
        "description": "Synthetic banking application used for regression testing demonstrations.",
    },
    "modules": [
        {"name": "Authentication", "description": "User login, MFA, and JWT session handling."},
        {"name": "Dashboard", "description": "Account summary, metrics, and quick navigation widgets."},
        {"name": "Money Transfer", "description": "Domestic, wire, and ACH fund transfer operations."},
        {"name": "Transaction History", "description": "Audited account statement and historical transaction ledger."},
    ],
    "test_cases": [
        {
            "title": "Verify valid user login",
            "priority": "High",
            "steps": "1. Navigate to /login\n2. Enter registered username and password\n3. Click Login",
            "expected_result": "JWT session token issued, redirected to user dashboard.",
            "modules": ["Authentication"],
        },
        {
            "title": "Reject login with incorrect credentials",
            "priority": "High",
            "steps": "1. Navigate to /login\n2. Enter valid username with invalid password\n3. Click Login",
            "expected_result": "HTTP 401 error displayed: 'Invalid username or password'.",
            "modules": ["Authentication"],
        },
        {
            "title": "Refresh authentication token after an idle session",
            "priority": "Medium",
            "steps": "1. Authenticate user\n2. Wait for 14 minutes of inactivity\n3. Trigger background token refresh",
            "expected_result": "New access token generated seamlessly without user re-prompt.",
            "modules": ["Authentication"],
        },
        {
            "title": "Redirect user after session expiration",
            "priority": "High",
            "steps": "1. Log in and open dashboard\n2. Expire token on server\n3. Click any dashboard link",
            "expected_result": "Session expiration dialog appears and user is redirected to /login.",
            "modules": ["Authentication", "Dashboard"],
        },
        {
            "title": "Block money transfer when session expires before confirmation",
            "priority": "Critical",
            "steps": "1. Fill out transfer form\n2. Wait for session token to expire\n3. Click Confirm Transfer",
            "expected_result": "Transfer rejected with HTTP 401; no funds deducted from account balance.",
            "modules": ["Authentication", "Money Transfer"],
        },
        {
            "title": "Complete domestic transfer with an active session",
            "priority": "High",
            "steps": "1. Authenticate with active session\n2. Enter recipient account, routing, and $250.00\n3. Confirm OTP and submit",
            "expected_result": "Transfer processed immediately, transaction reference returned.",
            "modules": ["Money Transfer"],
        },
        {
            "title": "Display transaction history after re-authentication",
            "priority": "Medium",
            "steps": "1. Invalidate session on statement page\n2. Re-authenticate via modal\n3. Refresh transaction ledger",
            "expected_result": "Transaction table reloads complete record list without full page refresh.",
            "modules": ["Authentication", "Transaction History"],
        },
        {
            "title": "Prevent duplicate money transfers on repeated submission",
            "priority": "Critical",
            "steps": "1. Fill out $500 transfer\n2. Rapidly double-click submit button\n3. Verify ledger debits",
            "expected_result": "Idempotency key prevents duplicate transaction; single debit occurs.",
            "modules": ["Money Transfer"],
        },
    ],
    "defects": [
        {
            "title": "Authentication token refresh race causes intermittent logout",
            "module": "Authentication",
            "severity": "High",
            "description": "Concurrent API calls during token refresh trigger invalid refresh token exchange, abruptly destroying active user session.",
            "resolution_notes": "Added mutex lock around refresh queue and coalesced concurrent refresh requests into a single promise.",
        },
        {
            "title": "Dashboard API returns unauthorized response after prolonged inactivity",
            "module": "Dashboard",
            "severity": "Medium",
            "description": "When dashboard widgets poll summary metrics after 30 minutes of idle time, widget handlers crash instead of triggering auth modal.",
            "resolution_notes": "Implemented global Axios interceptor on 401 responses to cleanly display re-auth modal.",
        },
        {
            "title": "Transfer request is accepted after authentication session expiry",
            "module": "Money Transfer",
            "severity": "Critical",
            "description": "Transfer endpoint cached session validity in local state and executed withdrawal even though the server-side JWT had expired.",
            "resolution_notes": "Enforced synchronous server-side JWT verification in transfer authorization middleware prior to ledger entry.",
        },
        {
            "title": "Duplicate money transfer occurs after repeated submission",
            "module": "Money Transfer",
            "severity": "Critical",
            "description": "Network latency on high-value transfer caused double click to generate two distinct transaction IDs without idempotency checking.",
            "resolution_notes": "Added mandatory Client-Request-ID idempotency key header stored in Redis with a 5-minute TTL.",
        },
        {
            "title": "Transaction history remains accessible after session expiration",
            "module": "Transaction History",
            "severity": "High",
            "description": "Browser back button navigated to cached statement records and displayed full account balances after logout.",
            "resolution_notes": "Configured Cache-Control: no-store, no-cache, must-revalidate on all transaction history responses.",
        },
    ],
    "test_executions": [
        {"tc_index": 0, "status": "passed", "build_version": "banking-v1.0", "executed_at": "2026-08-01T09:00:00Z"},
        {"tc_index": 0, "status": "passed", "build_version": "banking-v1.1", "executed_at": "2026-08-15T09:30:00Z"},
        {"tc_index": 1, "status": "passed", "build_version": "banking-v1.0", "executed_at": "2026-08-01T10:15:00Z"},
        {"tc_index": 1, "status": "passed", "build_version": "banking-v1.1", "executed_at": "2026-08-15T10:00:00Z"},
        {"tc_index": 2, "status": "failed", "build_version": "banking-v1.0", "executed_at": "2026-08-02T11:00:00Z"},
        {"tc_index": 2, "status": "passed", "build_version": "banking-v1.1", "executed_at": "2026-08-16T11:30:00Z"},
        {"tc_index": 3, "status": "passed", "build_version": "banking-v1.0", "executed_at": "2026-08-02T14:00:00Z"},
        {"tc_index": 3, "status": "blocked", "build_version": "banking-v1.2", "executed_at": "2026-09-01T14:30:00Z"},
        {"tc_index": 4, "status": "failed", "build_version": "banking-v1.0", "executed_at": "2026-08-03T13:00:00Z"},
        {"tc_index": 4, "status": "passed", "build_version": "banking-v1.1", "executed_at": "2026-08-17T13:30:00Z"},
        {"tc_index": 5, "status": "passed", "build_version": "banking-v1.0", "executed_at": "2026-08-03T15:00:00Z"},
        {"tc_index": 5, "status": "passed", "build_version": "banking-v1.2", "executed_at": "2026-09-02T15:30:00Z"},
        {"tc_index": 6, "status": "passed", "build_version": "banking-v1.1", "executed_at": "2026-08-18T16:00:00Z"},
        {"tc_index": 6, "status": "passed", "build_version": "banking-v1.2", "executed_at": "2026-09-03T16:30:00Z"},
        {"tc_index": 7, "status": "failed", "build_version": "banking-v1.0", "executed_at": "2026-08-04T17:00:00Z"},
        {"tc_index": 7, "status": "passed", "build_version": "banking-v1.1", "executed_at": "2026-08-19T17:30:00Z"},
    ],
    "change_requests": [
        {
            "title": "Enforce session expiration validation before transfer confirmation",
            "status": "completed",
            "description": "Require two-stage cryptographic validation of user session token immediately before executing any monetary debit.",
            "modules": ["Authentication", "Money Transfer"],
        },
        {
            "title": "Improve authentication token refresh behaviour",
            "status": "in_progress",
            "description": "Implement proactive silent token refreshing 60 seconds before expiration to prevent UI disruptions across dashboard widgets.",
            "modules": ["Authentication", "Dashboard"],
        },
        {
            "title": "Secure transaction history access after re-authentication",
            "status": "submitted",
            "description": "Enforce re-authentication challenge before viewing or exporting historical statements older than 90 days.",
            "modules": ["Authentication", "Transaction History"],
        },
    ],
}

ECOMMERCE_DATA = {
    "project": {
        "name": "DEMO - E-Commerce Platform",
        "description": "Synthetic e-commerce application used for regression testing demonstrations.",
    },
    "modules": [
        {"name": "Product Catalog", "description": "Product browsing, search, categorization, and inventory count."},
        {"name": "Shopping Cart", "description": "Cart items, quantity updates, promotional discounts, and pricing calculations."},
        {"name": "Checkout", "description": "Order placement, shipping details, tax computation, and order confirmation."},
        {"name": "Payment Gateway", "description": "Integration with card processors, idempotency, authorizations, and captures."},
    ],
    "test_cases": [
        {
            "title": "Search products by category",
            "priority": "High",
            "steps": "1. Select 'Electronics' from category dropdown\n2. Apply filter\n3. Verify returned SKU list",
            "expected_result": "All items listed belong to Electronics category with valid prices.",
            "modules": ["Product Catalog"],
        },
        {
            "title": "Update item quantity in shopping cart",
            "priority": "Medium",
            "steps": "1. Add item to cart\n2. Change quantity from 1 to 4\n3. Observe line total and subtotal",
            "expected_result": "Cart subtotals update accurately in real-time.",
            "modules": ["Shopping Cart"],
        },
        {
            "title": "Recalculate cart price after product price changes",
            "priority": "High",
            "steps": "1. Add item at $50.00 to cart\n2. Modify product catalog price to $40.00\n3. Navigate to checkout",
            "expected_result": "Cart alerts user of price change and recalculates total to $40.00.",
            "modules": ["Shopping Cart", "Product Catalog"],
        },
        {
            "title": "Complete checkout using a valid payment method",
            "priority": "Critical",
            "steps": "1. Proceed to checkout\n2. Enter shipping address and valid Visa card\n3. Click Place Order",
            "expected_result": "Order status set to Paid, confirmation email triggered, receipt displayed.",
            "modules": ["Checkout", "Payment Gateway"],
        },
        {
            "title": "Handle payment gateway timeout without duplicate charging",
            "priority": "Critical",
            "steps": "1. Simulate gateway timeout of 15 seconds\n2. Submit order payment\n3. Verify customer card and order status",
            "expected_result": "Gateway poll checks transaction status; no secondary charge is created.",
            "modules": ["Payment Gateway", "Checkout"],
        },
        {
            "title": "Retry a failed payment using an idempotency key",
            "priority": "High",
            "steps": "1. Gateway returns 503 Service Unavailable\n2. Automatic retry triggered after 3 seconds with same idempotency key",
            "expected_result": "Second call succeeds or returns existing charge record without double billing.",
            "modules": ["Payment Gateway", "Checkout"],
        },
        {
            "title": "Confirm order only after successful payment capture",
            "priority": "Critical",
            "steps": "1. Trigger authorization without capture\n2. Inspect order confirmation status",
            "expected_result": "Order remains in 'Payment Pending' state until capture webhook is received.",
            "modules": ["Checkout", "Payment Gateway"],
        },
        {
            "title": "Prevent checkout with insufficient inventory",
            "priority": "High",
            "steps": "1. Attempt to purchase 10 units when only 2 remain in stock\n2. Click Proceed to Checkout",
            "expected_result": "Checkout blocked with error: 'Only 2 items available in inventory'.",
            "modules": ["Shopping Cart", "Product Catalog"],
        },
    ],
    "defects": [
        {
            "title": "Payment gateway timeout leaves the order in pending state",
            "module": "Payment Gateway",
            "severity": "Critical",
            "description": "When third-party processor timed out, webhook listener dropped message and left order permanently in pending state.",
            "resolution_notes": "Implemented dead-letter queue and background reconciler to poll unconfirmed transactions every 5 minutes.",
        },
        {
            "title": "Retried payment request charges customer twice",
            "module": "Payment Gateway",
            "severity": "Critical",
            "description": "Client-side retry button generated a fresh UUID instead of reusing the initial checkout attempt key, resulting in dual authorizations.",
            "resolution_notes": "Tied idempotency key to order_id on backend so subsequent attempts reuse identical charge key.",
        },
        {
            "title": "Cart total uses stale product price after discount changes",
            "module": "Shopping Cart",
            "severity": "High",
            "description": "Promotional sale expiration did not invalidate cached cart session prices, allowing checkout at expired discounted prices.",
            "resolution_notes": "Added mandatory server-side price validation step during checkout order creation.",
        },
        {
            "title": "Checkout marks order successful before payment capture",
            "module": "Checkout",
            "severity": "Critical",
            "description": "Asynchronous authorization flow returned 200 before settlement succeeded, creating unfulfilled orders on declined cards.",
            "resolution_notes": "Separated order submission from order confirmation, requiring authorization success callback.",
        },
        {
            "title": "Inventory is oversold during simultaneous checkout requests",
            "module": "Product Catalog",
            "severity": "High",
            "description": "Two concurrent customers purchasing the last available unit both passed stock check due to non-atomic inventory queries.",
            "resolution_notes": "Implemented database row-level locking (SELECT ... FOR UPDATE) during inventory decrement.",
        },
    ],
    "test_executions": [
        {"tc_index": 0, "status": "passed", "build_version": "ecommerce-v1.0", "executed_at": "2026-08-05T09:00:00Z"},
        {"tc_index": 0, "status": "passed", "build_version": "ecommerce-v1.1", "executed_at": "2026-08-20T09:30:00Z"},
        {"tc_index": 1, "status": "passed", "build_version": "ecommerce-v1.0", "executed_at": "2026-08-05T10:15:00Z"},
        {"tc_index": 1, "status": "passed", "build_version": "ecommerce-v1.1", "executed_at": "2026-08-20T10:00:00Z"},
        {"tc_index": 2, "status": "failed", "build_version": "ecommerce-v1.0", "executed_at": "2026-08-06T11:00:00Z"},
        {"tc_index": 2, "status": "passed", "build_version": "ecommerce-v1.1", "executed_at": "2026-08-21T11:30:00Z"},
        {"tc_index": 3, "status": "passed", "build_version": "ecommerce-v1.0", "executed_at": "2026-08-06T14:00:00Z"},
        {"tc_index": 3, "status": "passed", "build_version": "ecommerce-v1.2", "executed_at": "2026-09-05T14:30:00Z"},
        {"tc_index": 4, "status": "failed", "build_version": "ecommerce-v1.0", "executed_at": "2026-08-07T13:00:00Z"},
        {"tc_index": 4, "status": "passed", "build_version": "ecommerce-v1.1", "executed_at": "2026-08-22T13:30:00Z"},
        {"tc_index": 5, "status": "blocked", "build_version": "ecommerce-v1.0", "executed_at": "2026-08-07T15:00:00Z"},
        {"tc_index": 5, "status": "passed", "build_version": "ecommerce-v1.1", "executed_at": "2026-08-22T15:30:00Z"},
        {"tc_index": 6, "status": "failed", "build_version": "ecommerce-v1.1", "executed_at": "2026-08-23T16:00:00Z"},
        {"tc_index": 6, "status": "passed", "build_version": "ecommerce-v1.2", "executed_at": "2026-09-06T16:30:00Z"},
        {"tc_index": 7, "status": "passed", "build_version": "ecommerce-v1.0", "executed_at": "2026-08-08T17:00:00Z"},
        {"tc_index": 7, "status": "passed", "build_version": "ecommerce-v1.2", "executed_at": "2026-09-07T17:30:00Z"},
    ],
    "change_requests": [
        {
            "title": "Add idempotent payment retry handling",
            "status": "completed",
            "description": "Standardize idempotency keys across all payment provider adapter calls to prevent duplicate charges during network drops.",
            "modules": ["Payment Gateway", "Checkout"],
        },
        {
            "title": "Recalculate cart totals when inventory or promotional prices change",
            "status": "in_progress",
            "description": "Subscribe shopping cart sessions to product catalog price update events for real-time customer price notifications.",
            "modules": ["Shopping Cart", "Product Catalog"],
        },
        {
            "title": "Make order confirmation dependent on payment capture",
            "status": "submitted",
            "description": "Refactor order fulfillment pipeline to defer inventory reservation confirmation until final payment settlement.",
            "modules": ["Checkout", "Payment Gateway"],
        },
    ],
}


def parse_datetime(dt_str: str) -> datetime:
    """Parses ISO-8601 UTC timestamp into a timezone-aware datetime."""
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def seed_project_data(
    session: Session, project_fixture: Dict[str, Any], dry_run: bool
) -> Dict[str, int]:
    """Seeds one project with its modules, test cases, defects, executions, and change requests.

    Identifies existing records by natural keys to ensure idempotency.
    """
    counts = {
        "projects_added": 0,
        "projects_skipped": 0,
        "modules_added": 0,
        "modules_skipped": 0,
        "test_cases_added": 0,
        "test_cases_skipped": 0,
        "defects_added": 0,
        "defects_skipped": 0,
        "executions_added": 0,
        "executions_skipped": 0,
        "change_requests_added": 0,
        "change_requests_skipped": 0,
    }

    # 1. Project
    proj_info = project_fixture["project"]
    project = (
        session.query(Project).filter(Project.name == proj_info["name"]).first()
    )
    if not project:
        project = Project(
            name=proj_info["name"], description=proj_info["description"]
        )
        session.add(project)
        session.flush()
        counts["projects_added"] += 1
    else:
        counts["projects_skipped"] += 1

    # 2. Modules
    modules_map: Dict[str, Module] = {}
    for mod_info in project_fixture["modules"]:
        module = (
            session.query(Module)
            .filter(
                Module.project_id == project.id,
                Module.name == mod_info["name"],
            )
            .first()
        )
        if not module:
            module = Module(
                project_id=project.id,
                name=mod_info["name"],
                description=mod_info["description"],
            )
            session.add(module)
            session.flush()
            counts["modules_added"] += 1
        else:
            counts["modules_skipped"] += 1
        modules_map[module.name] = module

    # 3. Test Cases
    created_test_cases: List[TestCase] = []
    for tc_info in project_fixture["test_cases"]:
        test_case = (
            session.query(TestCase)
            .filter(
                TestCase.project_id == project.id,
                TestCase.title == tc_info["title"],
            )
            .first()
        )

        target_modules = [
            modules_map[m_name]
            for m_name in tc_info["modules"]
            if m_name in modules_map
        ]

        if not test_case:
            test_case = TestCase(
                project_id=project.id,
                title=tc_info["title"],
                priority=tc_info["priority"],
                steps=tc_info["steps"],
                expected_result=tc_info["expected_result"],
                modules=target_modules,
            )
            session.add(test_case)
            session.flush()
            counts["test_cases_added"] += 1
        else:
            # Ensure missing module associations for our demo records are completed
            for tm in target_modules:
                if tm not in test_case.modules:
                    test_case.modules.append(tm)
            counts["test_cases_skipped"] += 1

        created_test_cases.append(test_case)

    # 4. Defects
    for defect_info in project_fixture["defects"]:
        defect = (
            session.query(Defect)
            .filter(
                Defect.project_id == project.id,
                Defect.title == defect_info["title"],
            )
            .first()
        )
        primary_module = modules_map.get(defect_info["module"])
        if not primary_module:
            raise ValueError(
                f"Referenced module '{defect_info['module']}' not found in project '{project.name}'"
            )

        if not defect:
            defect = Defect(
                project_id=project.id,
                module_id=primary_module.id,
                title=defect_info["title"],
                severity=defect_info["severity"],
                description=defect_info["description"],
                resolution_notes=defect_info["resolution_notes"],
            )
            session.add(defect)
            session.flush()
            counts["defects_added"] += 1
        else:
            counts["defects_skipped"] += 1

    # 5. Test Executions
    for exec_info in project_fixture["test_executions"]:
        target_tc = created_test_cases[exec_info["tc_index"]]
        dt = parse_datetime(exec_info["executed_at"])

        existing_exec = (
            session.query(TestExecution)
            .filter(
                TestExecution.test_case_id == target_tc.id,
                TestExecution.build_version == exec_info["build_version"],
                TestExecution.status == exec_info["status"],
                TestExecution.executed_at == dt,
            )
            .first()
        )

        if not existing_exec:
            new_exec = TestExecution(
                test_case_id=target_tc.id,
                status=exec_info["status"],
                build_version=exec_info["build_version"],
                executed_at=dt,
            )
            session.add(new_exec)
            session.flush()
            counts["executions_added"] += 1
        else:
            counts["executions_skipped"] += 1

    # 6. Change Requests
    for cr_info in project_fixture["change_requests"]:
        change_request = (
            session.query(ChangeRequest)
            .filter(
                ChangeRequest.project_id == project.id,
                ChangeRequest.title == cr_info["title"],
            )
            .first()
        )

        target_modules = [
            modules_map[m_name]
            for m_name in cr_info["modules"]
            if m_name in modules_map
        ]

        if not change_request:
            change_request = ChangeRequest(
                project_id=project.id,
                title=cr_info["title"],
                status=cr_info["status"],
                description=cr_info["description"],
                modules=target_modules,
            )
            session.add(change_request)
            session.flush()
            counts["change_requests_added"] += 1
        else:
            # Ensure missing module associations for our demo records are completed
            for tm in target_modules:
                if tm not in change_request.modules:
                    change_request.modules.append(tm)
            counts["change_requests_skipped"] += 1

    return counts


def run_seeder(db_url: str, allow_demo_data: bool, dry_run: bool) -> Dict[str, int]:
    """Validates safeguards, initializes connection, and executes seeding within a transaction."""
    # Safety Check 1: Mandatory command-line flag
    if not allow_demo_data:
        print(
            "ERROR: The '--allow-demo-data' flag is strictly required to run the seeder.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Safety Check 2: Production environment guard
    env = os.getenv("ENV", "").lower() or os.getenv("ENVIRONMENT", "").lower()
    if env == "production":
        print(
            "ERROR: Seeding synthetic demo data is forbidden in production environments.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Safety Check 3: Local SQLite database guard
    if not db_url.startswith("sqlite"):
        print(
            f"ERROR: Seeder only operates on local SQLite databases. Target URL '{db_url}' was rejected.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Setup database engine and session
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    total_stats = {
        "projects_added": 0,
        "projects_skipped": 0,
        "modules_added": 0,
        "modules_skipped": 0,
        "test_cases_added": 0,
        "test_cases_skipped": 0,
        "defects_added": 0,
        "defects_skipped": 0,
        "executions_added": 0,
        "executions_skipped": 0,
        "change_requests_added": 0,
        "change_requests_skipped": 0,
    }

    print("=" * 60)
    print("TestImpact AI - Synthetic Demo Data Seeder")
    print(f"Target Database : {db_url}")
    print(f"Execution Mode  : {'DRY RUN (No changes saved)' if dry_run else 'APPLY (Persistent)'}")
    print("=" * 60)

    try:
        # Seed Banking Project
        b_stats = seed_project_data(session, BANKING_DATA, dry_run)
        for k, v in b_stats.items():
            total_stats[k] += v

        # Seed E-Commerce Project
        e_stats = seed_project_data(session, ECOMMERCE_DATA, dry_run)
        for k, v in e_stats.items():
            total_stats[k] += v

        if dry_run:
            session.rollback()
            print("\n[DRY RUN] Rolling back all operations. No database modifications were written.")
        else:
            session.commit()
            print("\n[SUCCESS] Transaction committed successfully.")

    except Exception as exc:
        session.rollback()
        print(f"\n[ERROR] Seeding failed: {exc}", file=sys.stderr)
        raise exc
    finally:
        session.close()

    print("\n--- Seeding Summary ---")
    print(f"Projects        : +{total_stats['projects_added']} added, {total_stats['projects_skipped']} skipped")
    print(f"Modules         : +{total_stats['modules_added']} added, {total_stats['modules_skipped']} skipped")
    print(f"Test Cases      : +{total_stats['test_cases_added']} added, {total_stats['test_cases_skipped']} skipped")
    print(f"Defects         : +{total_stats['defects_added']} added, {total_stats['defects_skipped']} skipped")
    print(f"Test Executions : +{total_stats['executions_added']} added, {total_stats['executions_skipped']} skipped")
    print(f"Change Requests : +{total_stats['change_requests_added']} added, {total_stats['change_requests_skipped']} skipped")
    print("=" * 60)

    return total_stats


def main():
    parser = argparse.ArgumentParser(
        description="Seed synthetic demo data for TestImpact AI."
    )
    parser.add_argument(
        "--allow-demo-data",
        action="store_true",
        help="Explicit confirmation required to allow seeding demo data.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the seeding process without committing database changes.",
    )
    parser.add_argument(
        "--db-url",
        default=SQLALCHEMY_DATABASE_URL,
        help="Database connection URL (defaults to local SQLite database).",
    )

    args = parser.parse_args()
    run_seeder(
        db_url=args.db_url,
        allow_demo_data=args.allow_demo_data,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()

