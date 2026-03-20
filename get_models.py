import sys
import os
from dotenv import load_dotenv
from anthropic import Anthropic, APIError, AuthenticationError

load_dotenv()

api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("[ERROR] ANTHROPIC_API_KEY environment variable is not set.")
    sys.exit(1)

client = Anthropic(api_key=api_key)

try:
    models = client.models.list()
except AuthenticationError:
    print("[ERROR] Authentication failed. Check your ANTHROPIC_API_KEY.")
    sys.exit(1)
except APIError as e:
    print(f"[ERROR] API error: {e.message}")
    sys.exit(1)

for model in models:
    print(model.id)
