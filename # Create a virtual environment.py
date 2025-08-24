# Create a virtual environment
python -m venv accounting_env

# Activate the virtual environment
# On Windows:
accounting_env\Scripts\activate
# On macOS/Linux:
source accounting_env/bin/activate

# Install required packages
pip install flask sqlalchemy psycopg2-binary pandas numpy reportlab openpyxl pyjwt bcrypt python-dotenv Flask-Migrate alembic
