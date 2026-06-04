from typing import Any


def format_agent_run_markdown(record: dict[str, Any]) -> str:
    """AgentRun record를 사람이 읽기 쉬운 Markdown 실행 기록으로 변환한다."""
    model = _as_dict(record.get("model"))
    source_window = _as_dict(record.get("source_window"))
    summary = _as_dict(record.get("summary"))
    events = record.get("events")
    event_rows = _format_event_rows(events if isinstance(events, list) else [])

    return "\n".join(
        [
            f"## Agent Run: {_text(record.get('agent_name'))} / {_text(record.get('owner'))}",
            "",
            f"- Run ID: `{_text(record.get('agent_run_id'))}`",
            f"- Request ID: `{_text(record.get('request_id'))}`",
            f"- Session ID: `{_text(record.get('session_id'))}`",
            f"- Turn: `{_text(record.get('turn_index'))}`",
            f"- Status: `{_text(record.get('status'))}`",
            f"- Started: `{_text(record.get('started_at'))}`",
            f"- Completed: `{_text(record.get('completed_at'))}`",
            f"- Model: `{_text(model.get('model_name'))}`",
            f"- Tokens: `{_text(model.get('total_tokens'))}`",
            f"- Estimated Cost USD: `{_text(model.get('estimated_cost_usd'))}`",
            "",
            "### Source",
            "",
            f"- Source Type: `{_text(source_window.get('source_type'))}`",
            f"- Chapter: `{_text(source_window.get('chapter_id'))}`",
            f"- Node: `{_text(source_window.get('node_id'))}`",
            f"- Input Summary: {_inline_text(summary.get('input'))}",
            "",
            "### Timeline",
            "",
            "| # | Event | Status | Tool | Data Loaded | Output |",
            "|---|---|---|---|---|---|",
            *event_rows,
            "",
            "### Output",
            "",
            f"- Output Summary: {_inline_text(summary.get('output'))}",
            f"- Fallback Used: `{_text(summary.get('fallback_used'))}`",
            f"- Audio URL: `{_text(summary.get('audio_url'))}`",
        ]
    )


def _format_event_rows(events: list[Any]) -> list[str]:
    rows: list[str] = []
    for index, event in enumerate(events, start=1):
        event_dict = _as_dict(event)
        rows.append(
            "| {index} | {event} | {status} | {tool} | {data_loaded} | {output} |".format(
                index=index,
                event=_cell(event_dict.get("event")),
                status=_cell(event_dict.get("status")),
                tool=_cell(event_dict.get("tool_name")),
                data_loaded=_cell(_compact(event_dict.get("data_loaded") or event_dict.get("input_summary"))),
                output=_cell(_compact(event_dict.get("output_summary") or event_dict.get("error"))),
            )
        )
    return rows or ["| 1 | no_events | - | - | - | - |"]


def _compact(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, dict):
        parts = [f"{key}={_text(item)}" for key, item in value.items()]
        return ", ".join(parts) if parts else "-"
    if isinstance(value, list):
        return ", ".join(_text(item) for item in value) if value else "-"
    return _text(value)


def _cell(value: Any) -> str:
    text = _compact(value).replace("\n", " ")
    return text.replace("|", "\\|")


def _inline_text(value: Any) -> str:
    return _text(value).replace("\n", " ")


def _text(value: Any) -> str:
    if value is None:
        return "-"
    return str(value)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
