"""Prefect documentation MCP server backed by Raggy and TurboPuffer."""

from __future__ import annotations

from typing import Annotated, Any

import logfire
from fastmcp import FastMCP
from openai import AsyncOpenAI, OpenAIError
from pydantic import Field
from turbopuffer import (
    APIError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
)

from docs_mcp_server._settings import settings
from docs_mcp_server._tpuf import normalize_score, row_to_dict, run_query

logfire.configure(
    service_name="prefect-docs-mcp",
    token=settings.logfire.token.get_secret_value() if settings.logfire.token else None,
    console=settings.logfire.console,
    send_to_logfire=settings.logfire.send_to_logfire,
    environment=settings.logfire.environment,
)

# instrument ALL OpenAI clients to capture token usage automatically
logfire.instrument_openai(AsyncOpenAI)

docs_mcp = FastMCP("Prefect Docs MCP", version="0.1.0")


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


@docs_mcp.tool
def search_prefect(
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
    include_attributes = list(dict.fromkeys(settings.include_attributes))

    with logfire.span(
        "search_prefect",
        query=query,
        top_k=result_limit,
        namespace=settings.turbopuffer.namespace,
        query_length=len(query),
    ) as span:
        try:
            with logfire.span("vector_query", top_k=result_limit) as vq_span:
                response = run_query(
                    query=query,
                    top_k=result_limit,
                    include_attributes=include_attributes,
                )
                rows_returned = len(response.rows or [])
                vq_span.set_attribute("rows_returned", rows_returned)
                vq_span.set_attribute("partial_results", rows_returned < result_limit)
        except NotFoundError:
            rows: list[Any] = []
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

        return _build_response(query, results)
