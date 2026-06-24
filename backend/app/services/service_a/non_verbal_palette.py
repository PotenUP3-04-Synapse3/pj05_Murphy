"""NPC 캐릭터별 비-텍스트(비구어) 표현 팔레트를 정의하는 모듈입니다."""

from typing import Final

# NPC ID 별 사용 가능한 비-텍스트(의성어, 한숨, break 태그 등) 요소 목록
NPC_NON_VERBAL_PALETTES: Final[dict[str, list[str]]] = {
    "arabella": ["Haha!", "Aww.", "Hmm...", "<break time='0.5s'/>"],
    "novak": ["Hmm.", "Well...", "<break time='0.4s'/>"],
    "hale": ["Hmph.", "Tsk.", "<break time='0.4s'/>"],
    "harris": ["Mm-hmm.", "Indeed.", "<break time='0.3s'/>"],
    "dan": ["Halt.", "Now...", "<break time='0.5s'/>"],
    "brielle": ["Oh!", "Mm-hmm.", "Let's see...", "<break time='0.4s'/>"],
}

def get_non_verbal_palette(npc_id: str) -> list[str]:
    """지정된 NPC의 비-텍스트 팔레트 목록을 안전하게 조회합니다.
    존재하지 않는 ID인 경우 빈 리스트를 반환합니다.
    """
    return NPC_NON_VERBAL_PALETTES.get(npc_id, [])
