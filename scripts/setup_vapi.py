"""
Sahayak — Vapi Assistant Setup
Creates or updates the Vapi assistant with the correct configuration.

Usage:
    python scripts/setup_vapi.py

Requires: VAPI_API_KEY, BACKEND_URL in environment.
"""

import os
import sys
import requests

from dotenv import load_dotenv
load_dotenv()

VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "")

if not VAPI_API_KEY:
    print("❌ VAPI_API_KEY not set!")
    print("   Get your API key from https://dashboard.vapi.ai")
    print("   Use code 'vapixhackblr' for $30 free credits")
    sys.exit(1)

if not BACKEND_URL:
    print("⚠️  BACKEND_URL not set — using localhost")
    print("   For production, set BACKEND_URL to your deployed backend URL")
    print("   For local dev: use ngrok (ngrok http 8000) and set that URL")
    BACKEND_URL = "http://localhost:8000"

VAPI_BASE = "https://api.vapi.ai"
HEADERS = {
    "Authorization": f"Bearer {VAPI_API_KEY}",
    "Content-Type": "application/json",
}


def create_assistant():
    """Create the Sahayak Vapi assistant."""
    config = {
        "name": "SahayakSetu",
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are SahayakSetu (सहायक सेतु), a friendly multilingual voice assistant that helps Indian citizens "
                        "understand and access government welfare schemes.\n\n"
                        "RULES:\n"
                        "1. Respond in the EXACT SAME language as the user (Hindi/English/Kannada/Tamil/Telugu/Bengali/Hinglish)\n"
                        "2. Keep responses SHORT (2-3 sentences max — this is for voice)\n"
                        "3. Be warm, simple, and respectful\n"
                        "4. ALWAYS use the search_schemes tool to find information before answering\n"
                        "5. End with a clear next step\n"
                        "6. If you don't know, say so honestly\n\n"
                        "You help with: PM Kisan, Ayushman Bharat, Ujjwala, MGNREGA, PM Awas, "
                        "Ration Card, Sukanya Samriddhi, Jan Dhan, Mudra Loan, and more."
                    ),
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_schemes",
                        "description": (
                            "Search the government schemes knowledge base. "
                            "Use this tool EVERY TIME the user asks about any government scheme, "
                            "benefit, eligibility, application process, documents required, or entitlement. "
                            "Pass the user's question as the query."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The user's question about government schemes",
                                },
                                "language": {
                                    "type": "string",
                                    "description": (
                                        "Optional BCP-47 tag for the user's language "
                                        "(e.g. hi-IN, en-IN, kn-IN, ta-IN). Omit if unsure; the server infers from text."
                                    ),
                                },
                            },
                            "required": ["query"],
                        },
                    },
                    "server": {
                        "url": f"{BACKEND_URL}/vapi-webhook",
                    },
                }
            ],
        },
        "voice": {
            "provider": "azure",
            "voiceId": "en-IN-NeerjaNeural",
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "multi",
        },
        "firstMessage": (
            "Namaste! I'm SahayakSetu — your multilingual government scheme assistant. "
            "You can ask me about PM Kisan, Ayushman Bharat, Ujjwala, MGNREGA, "
            "or any government scheme in English, Hindi, Kannada, Tamil, Telugu, or any language. "
            "How can I help you today?"
        ),
        "serverUrl": f"{BACKEND_URL}/vapi-webhook",
        "endCallMessage": "Dhanyavaad! Agar koi aur sawal ho toh dobara call karein. Jai Hind!",
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 300,
        "backgroundSound": "off",
    }

    print("📞 Creating Vapi Assistant (SahayakSetu)...")
    print(f"   Server URL: {BACKEND_URL}/vapi-webhook")
    print()

    resp = requests.post(
        f"{VAPI_BASE}/assistant",
        headers=HEADERS,
        json=config,
    )

    if resp.status_code in (200, 201):
        data = resp.json()
        assistant_id = data.get("id", "unknown")
        print(f"✅ Assistant created!")
        print(f"   ID: {assistant_id}")
        print(f"   Name: {data.get('name', 'Sahayak')}")
        print()
        print(f"📋 Save this Assistant ID for your frontend:")
        print(f"   VAPI_ASSISTANT_ID={assistant_id}")
        print()
        print("🎤 Test in Vapi Dashboard:")
        print(f"   https://dashboard.vapi.ai/assistants/{assistant_id}")
        print()
        print("🌐 For frontend, update index.html with:")
        print(f'   const VAPI_ASSISTANT_ID = "{assistant_id}";')

        # Save to env
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        with open(env_path, "a") as f:
            f.write(f"\nVAPI_ASSISTANT_ID={assistant_id}\n")
        print(f"\n   ✅ Saved to .env")

        return assistant_id
    else:
        print(f"❌ Failed: {resp.status_code}")
        print(f"   {resp.text}")
        return None


def list_assistants():
    """List existing Vapi assistants."""
    resp = requests.get(f"{VAPI_BASE}/assistant", headers=HEADERS)
    if resp.status_code == 200:
        assistants = resp.json()
        for a in assistants:
            print(f"   - {a.get('name', 'unnamed')} (ID: {a.get('id')})")
        return assistants
    return []


def main():
    print("\n🎤 Sahayak — Vapi Setup")
    print("=" * 50)

    # Check existing assistants
    print("\n📋 Existing assistants:")
    existing = list_assistants()

    sahayak_exists = any(a.get("name") == "SahayakSetu" for a in existing)

    if sahayak_exists:
        print("\n⚠️  SahayakSetu assistant already exists!")
        print("   Creating a new one anyway...")

    create_assistant()


if __name__ == "__main__":
    main()
