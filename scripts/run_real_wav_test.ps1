## powershell -ExecutionPolicy Bypass -File .\scripts\run_real_wav_test.ps1 -AudioPath "samples\uncle.wav"
## uv run uvicorn backend.app.main:app --reload --port 8000
param(
    [string]$ServerUrl = "http://localhost:8000/api/game/ai/respond",
    [string]$AudioPath = "C:\potenup3\pj05_Murphy\samples\uncle.wav"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Net.Http

if (-not (Test-Path -LiteralPath $AudioPath)) {
    throw "Test wav file not found: $AudioPath"
}

# In production, Unreal creates this turn JSON from the current game state.
# This script builds a local mock request for end-to-end testing.
$turnObject = @{
    contract_version          = "dev_c_unreal_turn.v1"
    request_id                = "req_real_wav_001"
    session                   = @{
        session_id      = "session_real_wav_001"
        player_id       = "player_001"
        chapter_id      = "CH0_IMMIGRATION"
        scene_id        = "JFK_IMMIGRATION_HALL"
        current_node_id = "IMM_002_PURPOSE"
        turn_index      = 1
    }
    npc                       = @{
        npc_id           = "officer_miller"
        npc_role         = "immigration_officer"
        last_npc_message = "What is the purpose of your visit?"
    }
    audio                     = @{
        mime_type      = "audio/wav"
        sample_rate_hz = 16000
        channels       = 1
        duration_ms    = 3000
        language_hint  = "en-US"
    }
    player_profile            = @{
        nickname              = "player"
        english_confidence    = "beginner"
        tier                  = "Bronze"
        travel_speaking_level = "TSL_1_SURVIVAL"
    }
    scenario_state            = @{
        patience            = 5
        suspicion           = 0
        retry_count         = 0
        hint_count          = 0
        previous_fail_count = 0
        completed_intents   = @()
    }
    game_state                = @{
        inventory         = @("passport")
        flags             = @()
        completed_intents = @()
        current_objective = "Answer the immigration officer."
    }
    previous_node_results     = @()
    client_allowed_next_nodes = @("IMM_003_DURATION", "IMM_002_PURPOSE")
    client_context            = @{
        platform      = "windows"
        input_device  = "microphone"
        locale        = "ko-KR"
        build_version = "local-test"
    }
}

$turnJson = $turnObject | ConvertTo-Json -Depth 20
$audioBytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $AudioPath))
$audioFileName = [System.IO.Path]::GetFileName($AudioPath)

$client = [System.Net.Http.HttpClient]::new()
$form = [System.Net.Http.MultipartFormDataContent]::new()

try {
    $turnContent = [System.Net.Http.StringContent]::new($turnJson, [System.Text.Encoding]::UTF8, "application/json")
    $audioContent = [System.Net.Http.ByteArrayContent]::new($audioBytes)
    $audioContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("audio/wav")

    $form.Add($turnContent, "turn")
    $form.Add($audioContent, "audio", $audioFileName)

    Write-Host "Sending request: $ServerUrl"
    Write-Host "Audio file: $AudioPath"

    $response = $client.PostAsync($ServerUrl, $form).GetAwaiter().GetResult()
    $responseBody = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()

    if (-not $response.IsSuccessStatusCode) {
        Write-Host "Request failed. Status code: $([int]$response.StatusCode)"
        Write-Host $responseBody
        exit 1
    }

    $responseObject = $responseBody | ConvertFrom-Json

    Write-Host ""
    Write-Host "=== STT Result ==="
    Write-Host $responseObject.stt.player_text

    Write-Host ""
    Write-Host "=== NPC Text ==="
    Write-Host $responseObject.npc.text

    Write-Host ""
    Write-Host "=== NPC Audio URL ==="
    Write-Host $responseObject.npc.audio_url

    Write-Host ""
    Write-Host "=== Full Response JSON ==="
    $responseObject | ConvertTo-Json -Depth 30
}
finally {
    $form.Dispose()
    $client.Dispose()
}

