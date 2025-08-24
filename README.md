# Georgian IFRS-Compliant Accounting Software

A comprehensive, modular accounting software implemented in Python, specifically tailored to comply with Georgian legislation and International Financial Reporting Standards (IFRS). This application aims to provide Georgian businesses with a reliable, compliant, and efficient solution for managing their financial operations.

## Features

*   **Modular Architecture:** Built with a clear separation of concerns using Flask Blueprints.
*   **User Authentication & Authorization (RBAC):** Secure user management with role-based access control.
*   **Comprehensive Audit Trail:** Automatic logging of all data changes in the system.
*   **General Ledger Module:**
    *   Chart of Accounts management.
    *   Journal entry creation with double-entry validation.
    *   Placeholder for Balance Sheet and Income Statement generation.
*   **Accounts Payable/Receivable Module:**
    *   Customer and Vendor management.
    *   Invoice creation with multiple items and PDF generation.
    *   Invoice editing functionality.
*   **Inventory Module:** Basic product management.
*   **Payroll Module:** Basic employee management.
*   **Tax Module:** Basic tax rate management.
*   **Reporting Module:** Simple dashboard with an audit log viewer.

## Technology Stack

*   **Backend:** Python, Flask, SQLAlchemy (ORM), SQLite (for development/testing), PostgreSQL (recommended for production).
*   **Frontend:** HTML, CSS (Bootstrap), JavaScript.
*   **PDF Generation:** ReportLab.

## Setup and Installation

Follow these steps to set up and run the application locally:

1.  **Clone the repository:**
    ```bash
    git clone [YOUR_REPOSITORY_URL]
    cd [YOUR_PROJECT_DIRECTORY]
    ```
    (Replace `[YOUR_REPOSITORY_URL]` and `[YOUR_PROJECT_DIRECTORY]` with your actual GitHub repository URL and local project directory name.)

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv accounting_env
    # On Windows:
    accounting_env\Scripts\activate
    # On macOS/Linux:
    source accounting_env/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install Flask Flask-SQLAlchemy Flask-Login Flask-Bcrypt python-dotenv reportlab
    ```

4.  **Run the application:**
    ```bash
    python -m georgian_accounting.app
    ```
    The application will start a development server. You might see some warnings, but it should run.

## Usage

1.  **Access the application:** Open your web browser and go to `http://172.0.0.1:5000/`.
2.  **Register a new user:** Since Role-Based Access Control (RBAC) is implemented, you'll need to register an account first. Go to `http://172.0.0.1:5000/auth/register`.
3.  **Log in:** After registration, log in using your new credentials at `http://172.0.0.1:5000/auth/login`.
4.  **Explore:** Once logged in, you can navigate through the different modules using the navigation bar.

## Contributing

(Optional: Add guidelines for contributions here)

## License

(Optional: Add license information here)
