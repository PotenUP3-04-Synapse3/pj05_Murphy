from __future__ import annotations

import argparse
import asyncio
import base64
import json
import wave
from pathlib import Path
from typing import Any

import websockets


async def main() -> None:
    args = _parse_args()
    uri = f"{args.backend_url.rstrip('/')}/api/game/ai/stt/stream"

    async with websockets.connect(uri) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "contract_version": "dev_c_realtime_stt.v1",
                    "event_type": "session_start",
                    "request_id": args.request_id,
                    "session_id": args.session_id,
                    "turn_index": args.turn_index,
                    "sequence": 0,
                    "provider": "elevenlabs_relay",
                    "language_hint": args.language_hint,
                }
            )
        )
        print(await websocket.recv())

        sequence = 1
        for chunk in _read_pcm16_chunks(args.wav, args.chunk_ms):
            await websocket.send(
                json.dumps(
                    {
                        "contract_version": "dev_c_realtime_stt.v1",
                        "event_type": "audio_chunk",
                        "request_id": args.request_id,
                        "session_id": args.session_id,
                        "turn_index": args.turn_index,
                        "sequence": sequence,
                        "provider": "elevenlabs_relay",
                        "audio_base64": base64.b64encode(chunk).decode("ascii"),
                        "commit": False,
                        "sample_rate_hz": 16000,
                    }
                )
            )
            await _drain_available_events(websocket, args.receive_timeout_s)
            sequence += 1

        await websocket.send(
            json.dumps(
                {
                    "contract_version": "dev_c_realtime_stt.v1",
                    "event_type": "audio_chunk",
                    "request_id": args.request_id,
                    "session_id": args.session_id,
                    "turn_index": args.turn_index,
                    "sequence": sequence,
                    "provider": "elevenlabs_relay",
                    "audio_base64": base64.b64encode(b"\x00" * 640).decode("ascii"),
                    "commit": True,
                    "sample_rate_hz": 16000,
                }
            )
        )
        await _drain_available_events(websocket, args.final_wait_s)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test C backend ElevenLabs realtime STT relay.")
    parser.add_argument("--backend-url", default="ws://127.0.0.1:8000")
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--request-id", default="req_elevenlabs_smoke_0001")
    parser.add_argument("--session-id", default="session_elevenlabs_smoke_001")
    parser.add_argument("--turn-index", type=int, default=1)
    parser.add_argument("--language-hint", default="en")
    parser.add_argument("--chunk-ms", type=int, default=250)
    parser.add_argument("--receive-timeout-s", type=float, default=0.15)
    parser.add_argument("--final-wait-s", type=float, default=2.0)
    return parser.parse_args()


def _read_pcm16_chunks(path: Path, chunk_ms: int) -> list[bytes]:
    with wave.open(str(path), "rb") as wav_file:
        if wav_file.getframerate() != 16000 or wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
            raise ValueError("Expected 16 kHz mono 16-bit PCM wav. Convert the file before running this smoke test.")

        frames_per_chunk = max(1, int(16000 * chunk_ms / 1000))
        chunks: list[bytes] = []
        while True:
            chunk = wav_file.readframes(frames_per_chunk)
            if not chunk:
                break
            chunks.append(chunk)

        return chunks


async def _drain_available_events(websocket: Any, timeout_s: float) -> None:
    while True:
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=timeout_s)
        except TimeoutError:
            return

        print(message)


if __name__ == "__main__":
    asyncio.run(main())
