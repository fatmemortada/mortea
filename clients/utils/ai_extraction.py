"""
AI document extraction service.

Sends a corporate document (PDF, image, or text) to Claude and returns
structured corporate data: entity details, directors, officers,
shareholders, and share classes. PDFs and images go to the model natively,
so scanned minute books work via vision — no OCR pipeline needed.
"""
import base64
import json
import os


# JSON schema for structured output — every field required so the model
# returns empty strings/arrays rather than omitting keys.
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "entity_name": {"type": "string", "description": "Legal name of the corporation"},
        "jurisdiction": {"type": "string", "description": "Jurisdiction of incorporation, e.g. Ontario, Federal, British Columbia"},
        "incorporation_date": {"type": "string", "description": "ISO date YYYY-MM-DD, or empty string if not found"},
        "business_number": {"type": "string", "description": "CRA business number if present"},
        "registered_address": {"type": "string", "description": "Registered office address"},
        "fiscal_year_end": {"type": "string", "description": "e.g. December 31, or empty string"},
        "directors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string"},
                    "address": {"type": "string"},
                    "appointment_date": {"type": "string", "description": "ISO date or empty string"},
                    "officer_title": {"type": "string", "description": "e.g. President, Secretary — empty if not an officer"},
                },
                "required": ["full_name", "address", "appointment_date", "officer_title"],
                "additionalProperties": False,
            },
        },
        "shareholders": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string"},
                    "share_class": {"type": "string", "description": "e.g. Common, Class A"},
                    "num_shares": {"type": "integer"},
                    "address": {"type": "string"},
                },
                "required": ["full_name", "share_class", "num_shares", "address"],
                "additionalProperties": False,
            },
        },
        "share_classes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "voting": {"type": "boolean"},
                    "rights_restrictions": {"type": "string"},
                },
                "required": ["name", "voting", "rights_restrictions"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string", "description": "Anything ambiguous or worth a human review"},
    },
    "required": ["entity_name", "jurisdiction", "incorporation_date", "business_number",
                 "registered_address", "fiscal_year_end", "directors", "shareholders",
                 "share_classes", "notes"],
    "additionalProperties": False,
}

PROMPT = (
    "Extract the corporate data from this document (articles of incorporation, "
    "minute book, register, resolution, or similar Canadian corporate record). "
    "Only include facts stated in the document — never invent names, dates or numbers. "
    "Use empty strings for missing values and ISO YYYY-MM-DD for dates. "
    "Flag anything ambiguous in the notes field."
)

MEDIA_TYPES = {
    '.pdf': 'application/pdf',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
}

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


def _build_content(file_bytes, filename):
    """Build the message content block for the file type."""
    ext = os.path.splitext(filename)[1].lower()
    media_type = MEDIA_TYPES.get(ext)
    if media_type == 'application/pdf':
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(file_bytes).decode("utf-8"),
            },
        }
    if media_type:  # image
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(file_bytes).decode("utf-8"),
            },
        }
    # Fall back to plain text (.doc/.docx aren't parsed — reject upstream)
    return {"type": "text", "text": file_bytes.decode("utf-8", errors="replace")[:200000]}


def extract_corporate_data(file_bytes, filename):
    """
    Run the extraction. Returns (data_dict, error_message) — exactly one is truthy.
    Requires ANTHROPIC_API_KEY in the environment.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, ("AI extraction is not configured: the ANTHROPIC_API_KEY "
                      "environment variable is missing.")
    if len(file_bytes) > MAX_FILE_BYTES:
        return None, "File is too large for AI extraction (max 10 MB)."

    import anthropic

    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=16000,
            thinking={"type": "adaptive"},
            output_config={"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
            messages=[{
                "role": "user",
                "content": [
                    _build_content(file_bytes, filename),
                    {"type": "text", "text": PROMPT},
                ],
            }],
        )
    except anthropic.AuthenticationError:
        return None, "AI extraction failed: the Anthropic API key is invalid."
    except anthropic.APIStatusError as e:
        return None, f"AI extraction failed: the AI service returned an error ({e.status_code}). Try again shortly."
    except anthropic.APIConnectionError:
        return None, "AI extraction failed: could not reach the AI service. Check the network and retry."

    if response.stop_reason == "refusal":
        return None, "AI extraction declined to process this document."

    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text:
        return None, "AI extraction returned no data for this document."
    try:
        return json.loads(text), None
    except ValueError:
        return None, "AI extraction returned malformed data. Try again."
