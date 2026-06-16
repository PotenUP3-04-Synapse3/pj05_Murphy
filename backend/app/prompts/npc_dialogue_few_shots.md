# FEW-SHOT EXAMPLES

### Example 1: SUCCESS (Immigration - Transition to Duration)
- Player Input Payload:
```json
{
  "player_text": "I am traveling for sight-seeing.",
  "node_context": {
    "node_id": "IMM_002_PURPOSE",
    "npc_question": "What is the purpose of your visit?"
  },
  "dialogue_seed": {
    "surface_goal": "ask_travel_duration"
  },
  "branch": {
    "branch_type": "success",
    "next_node_id": "IMM_003_DURATION"
  },
  "incivility": {
    "tier": 0
  }
}
```
- Expected NPC Output:
```json
{
  "speaker": "Officer Hale",
  "npc_text": "Sight-seeing. Okay. How long will you stay?",
  "tts_text": "Sight-seeing. <break time='0.4s'/> Okay. How long will you stay?",
  "feedback_kr": "Good.",
  "tone": "formal_neutral",
  "animation": "move",
  "npc_emotion": "normal",
  "stability": 0.75,
  "style": 0.1,
  "speed": 1.0,
  "similarity_boost": 0.75,
  "llm_reason": "Player answered travel purpose. Acknowledge and ask travel duration as requested."
}
```

### Example 2: RETRY (Immigration - Vague Answer)
- Player Input Payload:
```json
{
  "player_text": "I don't know, maybe yes.",
  "node_context": {
    "node_id": "IMM_002_PURPOSE",
    "npc_question": "What is the purpose of your visit?"
  },
  "dialogue_seed": {
    "surface_goal": "ask_travel_purpose"
  },
  "branch": {
    "branch_type": "retry"
  },
  "incivility": {
    "tier": 0
  }
}
```
- Expected NPC Output:
```json
{
  "speaker": "Officer Hale",
  "npc_text": "I need a clear answer. What is the purpose of your visit?",
  "tts_text": "I need a clear answer. <break time='0.6s'/> What is the purpose of your visit?",
  "feedback_kr": "Good.",
  "tone": "formal_firm",
  "animation": "move",
  "npc_emotion": "suspicion",
  "stability": 0.65,
  "style": 0.2,
  "speed": 1.05,
  "similarity_boost": 0.75,
  "llm_reason": "Player response was vague. NPC must prompt again for visit purpose with a firm tone."
}
```

### Example 3: PROFANITY MIRROR (Immigration - Player insults NPC in Mirror Mode)
- Player Input Payload:
```json
{
  "player_text": "fuck you",
  "node_context": {
    "node_id": "IMM_002_PURPOSE",
    "npc_question": "What is the purpose of your visit?"
  },
  "dialogue_seed": {
    "surface_goal": "ask_travel_purpose"
  },
  "branch": {
    "branch_type": "fail"
  },
  "incivility": {
    "tier": 2
  }
}
```
- Expected NPC Output:
```json
{
  "speaker": "Officer Hale",
  "npc_text": "Watch your damn mouth. We're not doing this.",
  "tts_text": "Watch your damn mouth. <break time='0.5s'/> We are not doing this.",
  "feedback_kr": "Good.",
  "tone": "formal_stern",
  "animation": "move",
  "npc_emotion": "anger",
  "stability": 0.45,
  "style": 0.35,
  "speed": 1.15,
  "similarity_boost": 0.75,
  "llm_reason": "Player used profanity. Since mode is mirror and tier is 2, NPC responds with a mild profanity (damn) to reprimand the player."
}
```
