"""Export the FastAPI OpenAPI schema as JSON for documentation review."""

from __future__ import annotations

import json

from app.main import app


def main() -> None:
    """Print the OpenAPI document to stdout."""
    print(json.dumps(app.openapi(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
