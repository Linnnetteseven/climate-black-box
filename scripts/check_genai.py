"""Check OCI Generative AI access and report which models are usable.

Run this once the OCI config is in place. It prints what the region actually
serves rather than assuming a model id, and finishes by suggesting the two
lines to add to .env.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv()

from services.genai.oci_client import (  # noqa: E402
    GenAIUnavailable, choose_model, list_chat_models,
)


def main() -> int:
    compartment = os.getenv("OCI_COMPARTMENT_ID")
    try:
        models = list_chat_models(compartment)
    except GenAIUnavailable as exc:
        print(f"  NOT AVAILABLE: {exc}")
        print("\n  The deterministic fallback remains in use; nothing is broken.")
        return 1

    if not models:
        print("  Config works, but no chat-capable models are listed in this compartment.")
        return 1

    print(f"  {len(models)} chat-capable model(s) available:\n")
    for name, model_id in models:
        print(f"    {name}")
        print(f"      {model_id}")

    name, model_id = choose_model(models)
    print(f"\n  Recommended: {name}")
    print("\n  Add to .env to switch the investigation beat onto the model:\n")
    print("    OCI_GENAI_ENABLED=true")
    print(f"    OCI_COMPARTMENT_ID={compartment or '<your compartment ocid>'}")
    print(f"    OCI_GENAI_MODEL_NAME={name}")
    print(f"    OCI_GENAI_MODEL_ID={model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
