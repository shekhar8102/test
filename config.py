import os
from dotenv import load_dotenv

load_dotenv()

# Delta Exchange API Credentials for Production (India)
DELTA_API_KEY_PROD = os.getenv("DELTA_API_KEY_PROD")
DELTA_API_SECRET_PROD = os.getenv("DELTA_API_SECRET_PROD")
DELTA_API_URL_PROD = "https://api.india.delta.exchange"

# Delta Exchange API Credentials for Testnet (India)
DELTA_API_KEY_TEST = os.getenv("DELTA_API_KEY_TEST")
DELTA_API_SECRET_TEST = os.getenv("DELTA_API_SECRET_TEST")
DELTA_API_URL_TEST = "https://cdn-ind.testnet.deltaex.org"