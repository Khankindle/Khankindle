"""Smoke test: Gemini key is set, a model answers, and the reply parses as JSON.

Run before a demo or after changing the extraction prompt:

    python test_gemini.py
"""

import os
import sys

from dotenv import load_dotenv

from ledger_core import gemini_client, model_candidates, parse_json_payload


def main() -> int:
    load_dotenv()
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        print("GEMINI_API_KEY is missing. Add it to .env before the demo.")
        return 1
    model = model_candidates()[0]
    client = gemini_client(key)
    prompt = 'Return only this JSON object and nothing else: {"ok": true, "project": "PocketLedger"}'
    try:
        interaction = client.interactions.create(model=model, input=prompt, timeout=60)
        payload = parse_json_payload(interaction.output_text or "")
    except Exception as error:
        print(f"Gemini smoke test failed on {model}: {error}")
        return 1
    if payload.get("ok") is not True or payload.get("project") != "PocketLedger":
        print(f"Gemini answered on {model}, but the JSON shape was unexpected: {payload}")
        return 1
    print(f"Gemini smoke test passed on {model}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
