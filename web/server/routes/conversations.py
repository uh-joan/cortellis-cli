from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from web.server import db, chat

router = APIRouter()


class NewConversation(BaseModel):
    title: str = "New conversation"
    workspace_path: str


class RenameConversation(BaseModel):
    title: str


class NewMessage(BaseModel):
    content: str


@router.get("/conversations")
def list_conversations(workspace_path: str):
    return db.list_conversations(workspace_path)


@router.post("/conversations")
def create_conversation(body: NewConversation):
    return db.create_conversation(body.workspace_path, body.title)


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str):
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.patch("/conversations/{conv_id}")
def rename_conversation(conv_id: str, body: RenameConversation):
    if not db.get_conversation(conv_id):
        raise HTTPException(404, "Conversation not found")
    db.rename_conversation(conv_id, body.title)
    return {"ok": True}


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    if not db.get_conversation(conv_id):
        raise HTTPException(404, "Conversation not found")
    db.delete_conversation(conv_id)
    return {"ok": True}


@router.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: str):
    if not db.get_conversation(conv_id):
        raise HTTPException(404, "Conversation not found")
    return db.list_messages(conv_id)


@router.post("/conversations/{conv_id}/message")
def send_message(conv_id: str, body: NewMessage):
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")

    db.add_message(conv_id, "user", body.content)

    return StreamingResponse(
        chat.stream_chat_turn(conv_id, body.content, conv["workspace_path"]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
