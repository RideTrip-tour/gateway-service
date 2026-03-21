import logging
import httpx


def build_openapi_urls(service_map: dict[str, str]) -> dict[str, str]:
    return {
        service_name: f"{base_url.rstrip('/')}/api/{service_name}/openapi.json"
        for service_name, base_url in service_map.items()
    }


async def fetch_openapi_schema(
    client: httpx.AsyncClient,
    service_name: str,
    url: str,
) -> dict:
    try:
        logging.info(f"[OPENAPI] start {service_name}: {url}")
        response = await client.get(url, timeout=5.0)
        response.raise_for_status()
        logging.info(f"[OPENAPI] success {service_name}: {url}")
        return response.json()
    except Exception as e:
        logging.exception(f"[OPENAPI] failed {service_name}: {url} | {e}")
        return {}


def merge_openapi_schemas(schemas: list[dict]) -> dict:
    merged = {
        "openapi": "3.1.0",
        "info": {
            "title": "Unified API",
            "version": "1.0.0",
        },
        "paths": {},
        "components": {
            "schemas": {},
            "responses": {},
            "parameters": {},
            "securitySchemes": {},
            "requestBodies": {},
            "headers": {},
            "examples": {},
            "links": {},
            "callbacks": {},
        },
        "tags": [],
    }

    seen_tags = set()

    for schema in schemas:
        if not schema:
            continue

        for path, methods in schema.get("paths", {}).items():
            if path in merged["paths"]:
                if merged["paths"][path] == methods:
                    continue
                raise ValueError(f"Конфликт path: {path}")
            merged["paths"][path] = methods

        for tag in schema.get("tags", []):
            tag_name = tag.get("name")
            if tag_name and tag_name not in seen_tags:
                merged["tags"].append(tag)
                seen_tags.add(tag_name)

        src_components = schema.get("components", {})
        dst_components = merged["components"]

        for section_name in dst_components:
            src_section = src_components.get(section_name, {})
            dst_section = dst_components[section_name]

            for key, value in src_section.items():
                if key in dst_section:
                    if dst_section[key] == value:
                        continue
                    raise ValueError(f"Конфликт components/{section_name}/{key}")
                dst_section[key] = value

    return merged