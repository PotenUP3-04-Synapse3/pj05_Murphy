import base64

from scripts.smoke_elevenlabs_realtime_stt_relay import _build_audio_chunk_events


def test_smoke_script_commits_last_real_audio_chunk_without_silence_sentinel() -> None:
    events = list(
        _build_audio_chunk_events(
            chunks=[b"first", b"last"],
            request_id="req_smoke_test",
            session_id="session_smoke_test",
            turn_index=1,
        )
    )

    assert len(events) == 2
    assert events[0]["commit"] is False
    assert events[0]["audio_base64"] == base64.b64encode(b"first").decode("ascii")
    assert events[1]["commit"] is True
    assert events[1]["audio_base64"] == base64.b64encode(b"last").decode("ascii")
    assert events[1]["sequence"] == 2
