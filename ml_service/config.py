import os

ML_SERVICE_TOKEN = os.getenv("ML_SERVICE_TOKEN", "dev-token")
EXECUTION_ENVIRONMENT = os.getenv("EXECUTION_ENVIRONMENT", "local")
PORT = int(os.getenv("ML_SERVICE_PORT", "5002"))
