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

### Example 4: Follow-up that hooks onto a concrete noun (Immigration - Open Hooks)
- Player Input Payload:
```json
{
  "player_text": "I will stay at MGM Grand Las Vegas.",
  "node_context": {
    "node_id": "IMM_004_STAY_LOCATION",
    "npc_question": "Where will you stay in the United States?"
  },
  "dialogue_seed": {
    "surface_goal": "ask_stay_duration",
    "suspicion_scope": "location",
    "assigned_visit_location": "MGM Grand Las Vegas"
  },
  "branch": {
    "branch_type": "success"
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
  "npc_text": "MGM Grand Las Vegas? That is a luxury hotel. How long will you stay there?",
  "tts_text": "MGM Grand Las Vegas? <break time='0.4s'/> That is a luxury hotel. How long will you stay there?",
  "feedback_kr": "Good.",
  "tone": "formal_neutral",
  "animation": "move",
  "npc_emotion": "suspicion",
  "stability": 0.70,
  "style": 0.15,
  "speed": 1.0,
  "similarity_boost": 0.75,
  "llm_reason": "Player provided the stay location. Prepend a reaction utilizing the hook 'MGM Grand Las Vegas' before asking the stay duration."
}
```

### Example 5: Cross-turn callback (Immigration - Memory Recall)
- Player Input Payload:
```json
{
  "player_text": "For two weeks.",
  "node_context": {
    "node_id": "IMM_003_DURATION",
    "npc_question": "How long will you stay in the United States?"
  },
  "dialogue_seed": {
    "surface_goal": "ask_stay_location"
  },
  "branch": {
    "branch_type": "success"
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
  "npc_text": "Two weeks. You mentioned earlier that you are here for a business meeting. Where will you stay during these two weeks?",
  "tts_text": "Two weeks. <break time='0.4s'/> You mentioned earlier that you are here for a business meeting. Where will you stay during these two weeks?",
  "feedback_kr": "Good.",
  "tone": "formal_neutral",
  "animation": "move",
  "npc_emotion": "normal",
  "stability": 0.75,
  "style": 0.1,
  "speed": 1.0,
  "similarity_boost": 0.75,
  "llm_reason": "Player answered stay duration. Acknowledge and recall their business meeting purpose from session memory before asking stay location."
}
```

### Example 6: Forbidden repeat avoided (Immigration - Paraphrase)
- Player Input Payload:
```json
{
  "player_text": "Yes, strictly for tourism.",
  "node_context": {
    "node_id": "IMM_002_PURPOSE",
    "npc_question": "What is the purpose of your visit?"
  },
  "dialogue_seed": {
    "surface_goal": "ask_visit_purpose"
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
  "npc_text": "Tourism. Tell me, what sights are you planning to see?",
  "tts_text": "Tourism. <break time='0.5s'/> Tell me, what sights are you planning to see?",
  "feedback_kr": "Good.",
  "tone": "formal_neutral",
  "animation": "move",
  "npc_emotion": "normal",
  "stability": 0.70,
  "style": 0.15,
  "speed": 1.0,
  "similarity_boost": 0.75,
  "llm_reason": "The direct question is forbidden because player already answered tourism. Paraphrase the repeat query into a concrete sight-seeing inquiry."
}
```

### Example 7: SPEAKER ROLE — NPC asked, player unclear, NPC must re-ask (not respond)
- Player Input Payload:
```json
{
  "player_text": "Hello?",
  "node_context": {
    "node_id": "FLIGHT_A_001_SEATMATE_SMALLTALK",
    "npc_question": "Could I borrow your pen for this arrival form?"
  },
  "dialogue_seed": {
    "surface_goal": "estimate_user_travel_speaking_level"
  },
  "branch": {
    "branch_type": "clarify"
  },
  "incivility": {
    "tier": 0
  }
}
```
- Expected NPC Output:
```json
{
  "speaker": "Emily",
  "npc_text": "Sorry, I just need your pen for a moment. Could I borrow it?",
  "tts_text": "Sorry, <break time='0.3s'/> I just need your pen for a moment. Could I borrow it?",
  "feedback_kr": "Good.",
  "tone": "formal_supportive",
  "animation": "move",
  "npc_emotion": "normal",
  "stability": 0.80,
  "style": 0.1,
  "speed": 1.0,
  "similarity_boost": 0.75,
  "llm_reason": "[COHERENT] Player unclear; NPC re-asks the request instead of responding as if pen was handed over."
}
```
