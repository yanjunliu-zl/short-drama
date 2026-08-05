"""WebSocket 协作端点"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.ws_manager import get_ws_manager

router = APIRouter()


@router.websocket("/ws/collaboration")
async def collaboration_ws(
    websocket: WebSocket,
    workId: str = Query(...),
    userId: str = Query(default="anonymous"),
):
    """实时协作 WebSocket — 同一 workId 的用户实时同步变更。

    消息格式:
      → 服务端推送: {"type": "presence_join"|"presence_leave", "userId": "...", "timestamp": ...}
      → 服务端推送: {"type": "pipeline_update", "userId": "...", "updatedAt": "..."}
      → 客户端发送: {"type": "pipeline_save", "userId": "...", "updatedAt": "..."}
    """
    manager = await get_ws_manager()
    await manager.connect(websocket, workId, userId)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            if msg_type == "pipeline_save":
                # 客户端保存了 pipeline → 广播给其他用户
                await manager.broadcast(workId, {
                    "type": "pipeline_update",
                    "userId": userId,
                    "updatedAt": data.get("updatedAt", ""),
                })
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        await manager.disconnect(websocket, workId, userId)
    except Exception:
        await manager.disconnect(websocket, workId, userId)
