from uuid import UUID
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from adex_kernel.core import owner_match
from adex_agent.dependencies import core, runtime
from adex_agent.models.provider import ProviderFailure
from adex_agent.notes.composition import compose_note

router = APIRouter()


class NoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    owner_id: UUID
    conversation_id: UUID
    message_id: UUID
    content: str = Field(min_length=1, max_length=64000)


@router.post("/internal/agent/note-compose")
async def note_compose(request: Request, body: NoteRequest):
    claims = core.require(request, "app", "note:compose", body.conversation_id)
    owner_match(claims, body.owner_id)
    try:
        return await compose_note(runtime, body.owner_id, body.message_id, body.content)
    except ProviderFailure as exc:
        raise HTTPException(502, detail=exc.code) from None
    except (ValueError, TypeError):
        raise HTTPException(502, detail="NOTE_COMPOSITION_FAILED") from None
