"""OCI Generative AI client.

Kept deliberately thin. Everything that matters about trusting the output --
the bounded evidence packet, the citation check, the forbidden-claims guard --
lives in `investigate.py` and applies whatever model answers. This module only
has to get a well-formed JSON object back, or fail cleanly so the caller falls
back.

Authentication comes from the standard `~/.oci/config`, which supports both an
uploaded API key and a `oci session authenticate` security token. Both are
handled; nothing here reads a key directly.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from functools import lru_cache
from typing import Any

log = logging.getLogger("cbb.genai.oci")

DEFAULT_ENDPOINT = "https://inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com"
REQUEST_TIMEOUT_S = 45
MAX_TOKENS = 1200
#: Low but not zero: we want the model to commit to a reading of the evidence
#: rather than hedge across every possibility, while staying reproducible
#: enough that two runs on the same evidence broadly agree.
TEMPERATURE = 0.2


#: Preference order when no model is pinned. Llama 3.3 70B is a deliberate
#: default: it follows a strict-JSON instruction reliably, it is served in
#: Frankfurt, and it uses the GENERIC chat format. The list is a preference,
#: not a requirement -- whatever is pinned in .env wins.
PREFERRED_MODELS = (
    "meta.llama-3.3-70b-instruct",
    "openai.gpt-oss-120b",
    "google.gemini-2.5-pro",
    "meta.llama-3.1-70b-instruct",
)


class GenAIUnavailable(RuntimeError):
    """OCI Generative AI could not be reached or is not configured."""


def _api_format(model_name: str) -> str:
    """Which chat API shape this model family expects.

    OCI serves two request formats and they are not interchangeable: Cohere
    models reject a GenericChatRequest outright. Choosing by family is why
    pinning a Cohere model in .env works rather than failing at the first call.
    """
    return "COHERE" if model_name.lower().startswith("cohere.") else "GENERIC"


@lru_cache(maxsize=1)
def _config() -> dict:
    import oci

    path = os.path.expanduser(os.getenv("OCI_CONFIG_FILE", "~/.oci/config"))
    profile = os.getenv("OCI_CONFIG_PROFILE", "DEFAULT")
    if not os.path.exists(path):
        raise GenAIUnavailable(f"no OCI config at {path}")
    try:
        config = oci.config.from_file(path, profile)
    except Exception as exc:
        raise GenAIUnavailable(f"could not read OCI config: {exc}") from exc
    return config


def _signer(config: dict):
    """Return a signer for a session-token profile, or None for an API key.

    `oci session authenticate` writes a profile with `security_token_file` and
    no uploaded key; API-key profiles have neither. Supporting both means the
    console path and the browser-login path work identically from here.
    """
    import oci

    token_file = config.get("security_token_file")
    if not token_file:
        return None
    try:
        token = open(os.path.expanduser(token_file)).read().strip()
        private_key = oci.signer.load_private_key_from_file(config["key_file"])
        return oci.auth.signers.SecurityTokenSigner(token, private_key)
    except Exception as exc:
        raise GenAIUnavailable(f"session token unusable: {exc}") from exc


@lru_cache(maxsize=1)
def _inference_client():
    import oci

    config = _config()
    endpoint = os.getenv("OCI_GENAI_ENDPOINT", DEFAULT_ENDPOINT)
    signer = _signer(config)
    kwargs: dict[str, Any] = dict(service_endpoint=endpoint, timeout=REQUEST_TIMEOUT_S)
    if signer is not None:
        kwargs["signer"] = signer
    try:
        return oci.generative_ai_inference.GenerativeAiInferenceClient(config, **kwargs)
    except Exception as exc:
        raise GenAIUnavailable(f"could not build inference client: {exc}") from exc


def choose_model(models: list[tuple[str, str]]) -> tuple[str, str]:
    """Pick a sensible default from what the region actually serves."""
    by_name = {name: mid for name, mid in models}
    for preferred in PREFERRED_MODELS:
        if preferred in by_name:
            return preferred, by_name[preferred]
    # Nothing preferred is available: take the first non-Cohere model so the
    # default path does not depend on the format we are least sure about.
    generic = [(n, m) for n, m in models if _api_format(n) == "GENERIC"]
    return (generic or models)[0]


def list_chat_models(compartment_id: str | None = None) -> list[tuple[str, str]]:
    """Return (display_name, model_id) for chat-capable models in the region.

    Model availability changes, so we read it rather than hard-coding an id
    that will 404 in a month with no warning.
    """
    import oci

    config = _config()
    compartment = compartment_id or os.getenv("OCI_COMPARTMENT_ID") or config.get("tenancy")
    if not compartment:
        raise GenAIUnavailable("no compartment OCID: set OCI_COMPARTMENT_ID")

    signer = _signer(config)
    kwargs: dict[str, Any] = {}
    if signer is not None:
        kwargs["signer"] = signer
    client = oci.generative_ai.GenerativeAiClient(config, **kwargs)

    try:
        models = client.list_models(compartment_id=compartment).data.items
    except Exception as exc:
        raise GenAIUnavailable(f"could not list models: {exc}") from exc

    out = []
    for model in models:
        caps = set(model.capabilities or [])
        if "CHAT" not in caps:
            continue
        if getattr(model, "lifecycle_state", "ACTIVE") != "ACTIVE":
            continue
        # A model can be listed twice under one name: once as an on-demand
        # chat model, and once as a fine-tuning base. They have different
        # OCIDs, and calling the fine-tune base for inference is rejected with
        # "Not allowed to call finetune base model". Only the CHAT-only entry
        # is servable on demand, so drop anything advertising FINE_TUNE.
        if "FINE_TUNE" in caps:
            continue
        out.append((model.display_name, model.id))
    return sorted(set(out))


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of a model response.

    Models wrap JSON in prose or fences however they feel. Rather than
    insisting on clean output, take the first balanced object; the schema and
    citation checks downstream decide whether it is acceptable.
    """
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in model response")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unterminated JSON object in model response")


def complete_json(system_prompt: str, user_content: str) -> tuple[dict, str]:
    """Ask the configured model for JSON. Returns (parsed, model_id)."""
    import oci
    from oci.generative_ai_inference.models import (
        ChatDetails,
        GenericChatRequest,
        Message,
        OnDemandServingMode,
        TextContent,
    )

    config = _config()
    compartment = os.getenv("OCI_COMPARTMENT_ID") or config.get("tenancy")

    model_id = os.getenv("OCI_GENAI_MODEL_ID")
    model_name = os.getenv("OCI_GENAI_MODEL_NAME", "")
    if not model_id:
        candidates = list_chat_models(compartment)
        if not candidates:
            raise GenAIUnavailable("no chat-capable model available in this compartment")
        model_name, model_id = choose_model(candidates)
        log.info("no OCI_GENAI_MODEL_ID set; using %s", model_name)

    if _api_format(model_name) == "COHERE":
        from oci.generative_ai_inference.models import CohereChatRequest

        chat_request = CohereChatRequest(
            api_format="COHERE",
            preamble_override=system_prompt,
            message=user_content,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            top_p=0.9,
        )
    else:
        chat_request = GenericChatRequest(
            api_format="GENERIC",
            messages=[
                Message(role="SYSTEM", content=[TextContent(text=system_prompt)]),
                Message(role="USER", content=[TextContent(text=user_content)]),
            ],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            top_p=0.9,
        )

    request = ChatDetails(
        compartment_id=compartment,
        serving_mode=OnDemandServingMode(model_id=model_id),
        chat_request=chat_request,
    )

    started = time.monotonic()
    try:
        response = _inference_client().chat(request)
    except Exception as exc:
        raise GenAIUnavailable(f"chat request failed: {exc}") from exc
    log.info("genai responded in %.1fs using %s", time.monotonic() - started, model_id)

    # The two formats return different shapes.
    try:
        chat_response = response.data.chat_response
        if hasattr(chat_response, "choices"):
            parts = chat_response.choices[0].message.content
            text = "".join(getattr(p, "text", "") for p in parts)
        else:
            text = chat_response.text
    except Exception as exc:
        raise GenAIUnavailable(f"unexpected response shape: {exc}") from exc

    return _extract_json(text), model_id
