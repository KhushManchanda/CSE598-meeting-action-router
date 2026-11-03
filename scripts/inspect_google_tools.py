"""Inspect pinned Google tool schemas; execute no actions or LLM requests.

Run locally with permission to read this project's .env. Keys are not printed.
"""
import json
from pathlib import Path


VERSIONS = {"googlecalendar": "20261010_00", "gmail": "20261029_00"}
SLUGS = ("GOOGLECALENDAR_CREATE_EVENT", "GOOGLECALENDAR_EVENTS_GET",
         "GMAIL_CREATE_EMAIL_DRAFT", "GMAIL_GET_DRAFT")


def main():
    from dotenv import dotenv_values
    from composio import Composio

    config = dotenv_values(Path(__file__).resolve().parents[1] / ".env", interpolate=False)
    if not config.get("COMPOSIO_API_KEY"):
        raise SystemExit("COMPOSIO_API_KEY is missing locally")
    client = Composio(api_key=config["COMPOSIO_API_KEY"], toolkit_versions=VERSIONS)
    print("Pinned toolkit versions:", json.dumps(VERSIONS))
    for slug in SLUGS:
        print(f"\n--- {slug} ---")
        try:
            tool = client.tools.get_raw_composio_tool_by_slug(slug)
            schema = getattr(tool, "input_parameters", None) or {}
            parameters = {}
            for name, prop in schema.get("properties", {}).items():
                parameters[name] = {key: prop[key] for key in
                                    ("type", "format", "default", "items", "anyOf", "oneOf") if key in prop}
                if prop.get("description"):
                    parameters[name]["description"] = prop["description"][:260]
            print(json.dumps({"required": schema.get("required", []), "parameters": parameters}, indent=2))
        except Exception as exc:
            # Do not print provider exception messages, which can contain keys.
            print(json.dumps({"error_type": type(exc).__name__,
                              "http_status": getattr(exc, "status_code", None)}))


if __name__ == "__main__":
    main()
