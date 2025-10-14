"""Prefect documentation MCP server backed by OpenAI and TurboPuffer."""

from __future__ import annotations

import json
from typing import Annotated, Any

import logfire
from fastmcp import FastMCP
from openai import AsyncOpenAI, OpenAIError
from pydantic import Field
from turbopuffer import (
    APIError,
    AsyncTurbopuffer,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
)
from turbopuffer.types.row import Row

from docs_mcp_server._settings import settings

logfire.configure(
    service_name="prefect-docs-mcp",
    token=settings.logfire.token.get_secret_value() if settings.logfire.token else None,
    console=settings.logfire.console,
    send_to_logfire=settings.logfire.send_to_logfire,
    environment=settings.logfire.environment,
)

# instrument ALL OpenAI clients to capture token usage automatically
logfire.instrument_openai(AsyncOpenAI)


app = FastMCP("Prefect Docs MCP", version="0.1.0")


def _build_response(
    query: str, results: list[dict[str, Any]], error: str | None = None
) -> dict[str, Any]:
    """build a response payload for the search tool."""
    payload: dict[str, Any] = {
        "query": query,
        "namespace": settings.turbopuffer.namespace,
        "results": results,
    }
    if error:
        payload["error"] = error
    return payload


@app.tool
async def search_prefect(
    query: Annotated[
        str,
        Field(
            description=(
                "a search query to find relevant document excerpts from Prefect's knowledgebase"
            )
        ),
    ],
    top_k: Annotated[
        int | None,
        Field(
            ge=1,
            le=20,
            description="How many document excerpts to return.",
        ),
    ] = None,
) -> dict[str, Any]:
    """Search the Prefect knowledgebase for documentation on concepts, usage, and best practices."""

    if not query.strip():
        raise ValueError("Query must not be empty.")

    result_limit = top_k or settings.top_k
    include_attributes = list(dict.fromkeys(settings.include_attributes)) or ["text"]

    with logfire.span(
        "search_prefect",
        query=query,
        top_k=result_limit,
        namespace=settings.turbopuffer.namespace,
        query_length=len(query),
    ) as span:
        try:
            with logfire.span("vector_query", top_k=result_limit) as vq_span:
                async with AsyncTurbopuffer(
                    region=settings.turbopuffer.region,
                    api_key=settings.turbopuffer.api_key.get_secret_value(),
                ) as client:
                    namespace = client.namespace(settings.turbopuffer.namespace)
                    async with AsyncOpenAI() as openai_client:
                        embedding = await openai_client.embeddings.create(
                            input=query, model="text-embedding-3-small", timeout=60
                        )
                    response = await namespace.query(
                        rank_by=("vector", "ANN", embedding.data[0].embedding),
                        top_k=result_limit,
                        include_attributes=include_attributes,
                    )
                rows_returned = len(response.rows or [])
                vq_span.set_attribute("rows_returned", rows_returned)
                vq_span.set_attribute("partial_results", rows_returned < result_limit)
        except NotFoundError:
            rows: list[Row] = []
            span.set_attribute("error_type", "not_found")
        except (AuthenticationError, PermissionDeniedError) as exc:
            span.set_attribute("error_type", "authentication")
            span.record_exception(exc)
            return _build_response(
                query, [], f"TurboPuffer authentication error: {exc}"
            )
        except APIError as exc:
            span.set_attribute("error_type", "api_error")
            span.record_exception(exc)
            return _build_response(query, [], f"TurboPuffer API error: {exc}")
        except OpenAIError as exc:
            span.set_attribute("error_type", "openai_error")
            span.record_exception(exc)
            return _build_response(query, [], f"OpenAI error: {exc}")
        except ValueError as exc:
            span.set_attribute("error_type", "config_error")
            span.record_exception(exc)
            return _build_response(
                query,
                [],
                "TurboPuffer configuration error. Ensure API key and namespace are set.",
            )
        else:
            rows = list(response.rows or [])

        results: list[dict[str, Any]] = []
        scores: list[float] = []

        with logfire.span("format_response", result_count=len(rows)):
            for row in rows:
                data = row_to_dict(row)
                snippet = data.get("text") or data.get("content")
                # no slicing - content is already chunked at ingestion time
                snippet_text = str(snippet) if snippet else ""

                score = normalize_score(
                    data.get("$dist")  # turbopuffer returns distance as $dist
                    or data.get("score")
                    or data.get("distance")
                    or data.get("similarity")
                )
                if score is not None:
                    scores.append(score)

                result_payload: dict[str, Any] = {
                    "snippet": snippet_text,
                    "id": data.get("id"),
                    "score": score,
                }

                metadata: dict[str, Any] | None = (
                    data.get("metadata")
                    if isinstance(data.get("metadata"), dict)
                    else None
                )
                title = data.get("title") or (metadata or {}).get("title")
                link = data.get("link") or (metadata or {}).get("link")
                if title:
                    result_payload["title"] = title
                if link:
                    result_payload["link"] = link
                if metadata:
                    result_payload["metadata"] = metadata

                results.append(result_payload)

        span.set_attribute("result_count", len(results))
        span.set_attribute("success", True)

        # add score statistics for dashboard analysis
        if scores:
            span.set_attribute("score_min", min(scores))
            span.set_attribute("score_max", max(scores))
            span.set_attribute("score_avg", sum(scores) / len(scores))

        response = _build_response(query, results)

    logfire.force_flush()
    return response


def row_to_dict(row: Row) -> dict[str, Any]:
    """normalize turbopuffer row objects to plain dictionaries."""

    data = row.model_dump(mode="python")
    if row.model_extra:
        data.update(row.model_extra)

    metadata = data.get("metadata")
    if isinstance(metadata, str):
        try:
            data["metadata"] = json.loads(metadata)
        except json.JSONDecodeError:
            pass

    return data


def normalize_score(value: Any) -> float | None:
    """coerce turbopuffer scores into floats when present."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
