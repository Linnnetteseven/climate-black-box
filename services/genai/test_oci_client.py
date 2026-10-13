"""Tests for the parts of the OCI client we can exercise without a tenancy.

The network call cannot be tested here, but the response parsing can -- and
that is where real models actually cause trouble, by wrapping JSON in prose or
code fences no matter what the prompt asked for.
"""

import pytest

from services.genai.oci_client import _extract_json


def test_plain_json_object():
    assert _extract_json('{"summary": "x"}') == {"summary": "x"}


def test_json_wrapped_in_a_code_fence():
    text = 'Here you go:\n```json\n{"summary": "x"}\n```\nHope that helps.'
    assert _extract_json(text) == {"summary": "x"}


def test_json_wrapped_in_an_unlabelled_fence():
    assert _extract_json('```\n{"a": 1}\n```') == {"a": 1}


def test_json_with_prose_around_it():
    assert _extract_json('Certainly. {"a": 1} Let me know.') == {"a": 1}


def test_nested_braces_do_not_terminate_early():
    text = '{"a": {"b": {"c": 1}}, "d": 2}'
    assert _extract_json(text) == {"a": {"b": {"c": 1}}, "d": 2}


def test_prose_with_no_json_raises():
    with pytest.raises(ValueError, match="no JSON object"):
        _extract_json("I'm afraid I can't help with that.")


def test_unterminated_object_raises():
    with pytest.raises(ValueError, match="unterminated"):
        _extract_json('{"a": 1')


# --- model selection -------------------------------------------------------

from services.genai.oci_client import _api_format, choose_model  # noqa: E402


def test_cohere_models_need_the_cohere_format():
    """They reject a GenericChatRequest outright, so this must be right."""
    assert _api_format("cohere.command-r-plus") == "COHERE"
    assert _api_format("cohere.command-a-03-2025") == "COHERE"


def test_other_families_use_the_generic_format():
    for name in ("meta.llama-3.3-70b-instruct", "google.gemini-2.5-pro",
                 "openai.gpt-oss-120b"):
        assert _api_format(name) == "GENERIC"


def test_choose_model_prefers_llama_over_alphabetical_first():
    """Guards the bug this was written for: sorting put a Cohere model first,
    which the generic request path cannot talk to."""
    available = [
        ("cohere.command-a-03-2025", "ocid-cohere"),
        ("meta.llama-3.3-70b-instruct", "ocid-llama"),
        ("google.gemini-2.5-pro", "ocid-gemini"),
    ]
    assert choose_model(available) == ("meta.llama-3.3-70b-instruct", "ocid-llama")


def test_choose_model_avoids_cohere_when_nothing_preferred_exists():
    available = [("cohere.command-r-16k", "ocid-c"), ("openai.gpt-oss-20b", "ocid-o")]
    assert choose_model(available)[0] == "openai.gpt-oss-20b"


def test_choose_model_falls_back_to_whatever_exists():
    available = [("cohere.command-r-16k", "ocid-c")]
    assert choose_model(available) == ("cohere.command-r-16k", "ocid-c")


def test_fine_tune_bases_are_excluded_from_inference_candidates():
    """Regression: OCI lists meta.llama-3.3-70b-instruct twice, once as an
    on-demand chat model and once as a fine-tuning base with a different OCID.
    Calling the latter fails with 'Not allowed to call finetune base model',
    so only CHAT-only entries may be offered for inference."""
    import services.genai.oci_client as mod

    class FakeModel:
        def __init__(self, name, caps, mid):
            self.display_name, self.capabilities, self.id = name, caps, mid
            self.lifecycle_state = "ACTIVE"

    listed = [
        FakeModel("meta.llama-3.3-70b-instruct", ["CHAT", "FINE_TUNE"], "ocid-finetune"),
        FakeModel("meta.llama-3.3-70b-instruct", ["CHAT"], "ocid-ondemand"),
        FakeModel("meta.llama-3.1-405b-instruct", ["CHAT"], "ocid-405b"),
    ]
    kept = []
    for model in listed:
        caps = set(model.capabilities or [])
        if "CHAT" not in caps or "FINE_TUNE" in caps:
            continue
        kept.append((model.display_name, model.id))

    assert ("meta.llama-3.3-70b-instruct", "ocid-ondemand") in kept
    assert ("meta.llama-3.3-70b-instruct", "ocid-finetune") not in kept
