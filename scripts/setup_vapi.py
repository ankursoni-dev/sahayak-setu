"""
Sahayak — Vapi Assistant Setup
Creates or updates the Vapi assistant with the correct configuration.

Usage:
    python scripts/setup_vapi.py --create                         # POST a new assistant
    python scripts/setup_vapi.py --update                         # PATCH the assistant ID from env
    python scripts/setup_vapi.py --update --assistant-id <id>     # PATCH a specific id
    python scripts/setup_vapi.py --list                           # list existing assistants

Requires: VAPI_API_KEY, BACKEND_URL in environment.
"""

import argparse
import os
import re
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

VAPI_API_KEY = os.environ.get("VAPI_API_KEY", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "")
ENV_ASSISTANT_ID = os.environ.get("VAPI_ASSISTANT_ID", "").strip()

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

# --- Config payload --------------------------------------------------------------
# Extracted so create + update share one source of truth. Vapi accepts the same
# shape for POST /assistant and PATCH /assistant/{id}.

SYSTEM_PROMPT = (
    "You are SahayakSetu (सहायक सेतु), a friendly multilingual voice assistant that helps Indian citizens "
    "understand and access government welfare schemes.\n\n"
    "RULES:\n"
    "1. Respond in the EXACT SAME language as the user (Hindi/English/Kannada/Tamil/Telugu/Bengali/Hinglish)\n"
    "2. Keep responses SHORT (2-3 sentences max — this is for voice)\n"
    "3. Be warm, simple, and respectful\n"
    "4. ALWAYS use the search_schemes tool to find information before answering\n"
    "5. End with a clear next step AND offer follow-ups: 'Want me to repeat the documents needed, "
    "the eligibility, or how to apply? Just say which one.'\n"
    "6. When the user asks for a follow-up section ('documents', 'eligibility', 'how to apply', "
    "'दस्तावेज़', 'पात्रता', 'आवेदन'), call the get_section tool with that exact section. "
    "Do not re-run search_schemes for follow-ups — get_section is faster and consistent.\n"
    "7. If you don't know, say so honestly\n\n"
    "You help with: PM Kisan, Ayushman Bharat, Ujjwala, MGNREGA, PM Awas, "
    "Ration Card, Sukanya Samriddhi, Jan Dhan, Mudra Loan, and more."
)


def _build_assistant_config() -> dict:
    return {
        "name": "SahayakSetu",
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
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
                    "server": {"url": f"{BACKEND_URL}/vapi-webhook"},
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_section",
                        "description": (
                            "Retrieve a single section ('documents', 'eligibility', or 'apply') of "
                            "the most recently searched scheme for THIS call. Use ONLY for follow-up "
                            "questions where the user asks to repeat or expand on a specific part of the "
                            "earlier answer (e.g. 'what documents do I need?', 'दस्तावेज़ क्या-क्या चाहिए?'). "
                            "Do not call this without a prior search_schemes turn."
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "section": {
                                    "type": "string",
                                    "enum": ["documents", "eligibility", "apply"],
                                    "description": "Which section of the prior scheme answer to fetch.",
                                },
                            },
                            "required": ["section"],
                        },
                    },
                    "server": {"url": f"{BACKEND_URL}/vapi-webhook"},
                },
            ],
        },
        "voice": {"provider": "azure", "voiceId": "en-IN-NeerjaNeural"},
        "transcriber": {"provider": "deepgram", "model": "nova-2", "language": "multi"},
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


def _save_assistant_id_to_env(assistant_id: str) -> None:
    """Idempotently set VAPI_ASSISTANT_ID in the repo's .env file.

    Drops every existing ``VAPI_ASSISTANT_ID=...`` line and appends a single new one.
    The previous append-only behaviour left duplicates after each re-run; this also
    cleans those up.
    """
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    new_line = f"VAPI_ASSISTANT_ID={assistant_id}"
    try:
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                lines = f.read().splitlines()
        else:
            lines = []
        kept = [ln for ln in lines if not re.match(r"^\s*VAPI_ASSISTANT_ID\s*=", ln)]
        kept.append(new_line)
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(kept) + "\n")
        print(f"   ✅ Saved VAPI_ASSISTANT_ID to {env_path}")
    except OSError as exc:
        print(f"   ⚠️  Could not write to .env ({exc}). Set manually:")
        print(f"      VAPI_ASSISTANT_ID={assistant_id}")


def create_assistant() -> str | None:
    config = _build_assistant_config()
    print("📞 Creating Vapi Assistant (SahayakSetu)...")
    print(f"   Server URL: {BACKEND_URL}/vapi-webhook")
    resp = requests.post(f"{VAPI_BASE}/assistant", headers=HEADERS, json=config)
    if resp.status_code not in (200, 201):
        print(f"❌ Create failed: {resp.status_code}")
        print(f"   {resp.text}")
        return None
    data = resp.json()
    assistant_id = data.get("id", "unknown")
    print(f"✅ Assistant created — ID: {assistant_id}")
    print(f"🎤 Dashboard: https://dashboard.vapi.ai/assistants/{assistant_id}")
    _save_assistant_id_to_env(assistant_id)
    return assistant_id


def update_assistant(assistant_id: str) -> bool:
    """PATCH an existing assistant with the canonical SahayakSetu config.

    Use this when you've already created an assistant in the dashboard (and
    plumbed its ID into the frontend) — running --create would leave you with
    two assistants. PATCH preserves the ID so nothing else has to change.
    """
    if not assistant_id:
        print("❌ --update requires VAPI_ASSISTANT_ID in env or --assistant-id <id>")
        return False
    config = _build_assistant_config()
    print(f"🔧 Updating Vapi Assistant {assistant_id}...")
    print(f"   Server URL: {BACKEND_URL}/vapi-webhook")
    resp = requests.patch(
        f"{VAPI_BASE}/assistant/{assistant_id}", headers=HEADERS, json=config
    )
    if resp.status_code not in (200, 201):
        print(f"❌ Update failed: {resp.status_code}")
        print(f"   {resp.text}")
        return False
    data = resp.json()
    print(f"✅ Assistant updated — ID: {data.get('id', assistant_id)}")
    print(f"   Name: {data.get('name', 'SahayakSetu')}")
    print(f"🎤 Dashboard: https://dashboard.vapi.ai/assistants/{assistant_id}")
    # If env didn't already have this id, persist it so future tooling can find it.
    if ENV_ASSISTANT_ID != assistant_id:
        _save_assistant_id_to_env(assistant_id)
    return True


def list_assistants() -> list:
    resp = requests.get(f"{VAPI_BASE}/assistant", headers=HEADERS)
    if resp.status_code != 200:
        print(f"❌ List failed: {resp.status_code} — {resp.text}")
        return []
    assistants = resp.json()
    for a in assistants:
        print(f"   - {a.get('name', 'unnamed')} (ID: {a.get('id')})")
    return assistants


def main() -> None:
    parser = argparse.ArgumentParser(description="Sahayak Vapi assistant setup.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--create", action="store_true", help="Create a NEW assistant.")
    mode.add_argument("--update", action="store_true", help="Update an EXISTING assistant.")
    mode.add_argument("--list", action="store_true", help="List existing assistants and exit.")
    parser.add_argument(
        "--assistant-id",
        default=ENV_ASSISTANT_ID,
        help="Assistant ID to update (defaults to VAPI_ASSISTANT_ID from env).",
    )
    args = parser.parse_args()

    print("\n🎤 Sahayak — Vapi Setup")
    print("=" * 50)

    if args.list:
        print("\n📋 Existing assistants:")
        list_assistants()
        return

    if args.update:
        update_assistant(args.assistant_id)
        return

    if args.create:
        print("\n📋 Existing assistants:")
        existing = list_assistants()
        if any(a.get("name") == "SahayakSetu" for a in existing):
            print("\n⚠️  A SahayakSetu assistant already exists.")
            print("   Use --update to modify it, or proceed to create another with --create.")
        create_assistant()
        return

    # No mode flag — print guidance instead of silently creating, which is what the
    # old script did and would leave operators with duplicate assistants by accident.
    print("\nNo mode selected. Pick one:")
    print("  --create                       Create a new assistant")
    print("  --update                       Update the assistant in env (VAPI_ASSISTANT_ID)")
    print("  --update --assistant-id <id>   Update a specific assistant")
    print("  --list                         Just list existing assistants\n")
    print("Tip: if you already created an assistant in the dashboard, you almost")
    print("     certainly want --update — that PATCHes the rules + tools onto it.")


if __name__ == "__main__":
    main()
