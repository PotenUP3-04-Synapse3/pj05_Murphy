from backend.app.schemas.game_turn import ErrorCapture, RecordedErrorSummary


class LoggingService:
    def record_error_capture(
        self,
        session_id: str,
        error_capture: ErrorCapture,
    ) -> RecordedErrorSummary:
        if not error_capture.should_record:
            return RecordedErrorSummary(
                recorded=False,
                storage_format="markdown",
                error_log_markdown_path=None,
                recorded_error_count=0,
            )

        return RecordedErrorSummary(
            recorded=True,
            storage_format="markdown",
            error_log_markdown_path=f"logs/{session_id}/error_log.md",
            recorded_error_count=len(error_capture.error_items),
        )
