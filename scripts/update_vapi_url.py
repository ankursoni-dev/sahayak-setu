import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
BACKEND_URL = os.getenv("BACKEND_URL", "https://sahayaksetu-backend-3kxl.onrender.com")

if not VAPI_API_KEY:
    print("❌ VAPI_API_KEY is not set in .env")
    sys.exit(1)

if not ASSISTANT_ID:
    print("❌ VAPI_ASSISTANT_ID is not set in .env")
    print("   Add the assistant ID from your Vapi dashboard or scripts/setup_vapi.py output.")
    sys.exit(1)

webhook_url = f"{BACKEND_URL.rstrip('/')}/vapi-webhook"

headers = {
    "Authorization": f"Bearer {VAPI_API_KEY}",
    "Content-Type": "application/json",
}

data = {"serverUrl": webhook_url}

print(f"🎙️ Updating Vapi Assistant {ASSISTANT_ID}...")
print(f"🌐 Setting Server URL to: {webhook_url}")

response = requests.patch(
    f"https://api.vapi.ai/assistant/{ASSISTANT_ID}",
    headers=headers,
    json=data,
)

if response.status_code == 200:
    print("✅ Vapi Assistant updated successfully!")
else:
    print(f"❌ Failed to update assistant: {response.text}")
