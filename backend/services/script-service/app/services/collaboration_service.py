"""
团队协作服务 — 剧本共享、评论批注、团队资产库访问。

对标 LibTV 的多人实时协作 + 统一资产库。
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════

class SharePermission(str):
    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"
    OWNER = "owner"


@dataclass
class ShareLink:
    """剧本分享链接"""
    script_id: int
    shared_by: str                      # 分享者 user_id
    shared_with: str = ""               # 被分享者 user_id（空=公开链接）
    permission: str = SharePermission.VIEW
    token: str = ""                     # 分享 token（公开链接用）
    expires_at: str = ""                # 过期时间
    created_at: str = ""

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now(timezone.utc)

    @property
    def is_public(self) -> bool:
        return not self.shared_with

    def to_dict(self) -> Dict[str, Any]:
        return {
            "script_id": self.script_id,
            "shared_by": self.shared_by,
            "shared_with": self.shared_with,
            "permission": self.permission,
            "token": self.token,
            "expires_at": self.expires_at,
            "is_expired": self.is_expired,
            "is_public": self.is_public,
        }


@dataclass
class Annotation:
    """剧本批注 — 对标 Final Draft 的注释功能"""
    annotation_id: str
    script_id: int
    user_id: str
    episode_number: int = 0           # 批注在哪一集
    position: Dict[str, Any] = field(default_factory=dict)  # {"line": 42, "char_offset": 10}
    content: str = ""                 # 批注内容
    annotation_type: str = "note"     # "note" | "suggestion" | "issue" | "praise"
    resolved: bool = False
    resolved_by: str = ""
    created_at: str = ""
    replies: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "script_id": self.script_id,
            "user_id": self.user_id,
            "episode_number": self.episode_number,
            "position": self.position,
            "content": self.content,
            "annotation_type": self.annotation_type,
            "resolved": self.resolved,
            "resolved_by": self.resolved_by,
            "created_at": self.created_at,
            "replies": self.replies,
        }


# ═══════════════════════════════════════════════════════════════
# CollaborationService
# ═══════════════════════════════════════════════════════════════

class CollaborationService:
    """团队协作服务 — 内存实现，生产环境迁移到 MySQL。"""

    def __init__(self):
        self._shares: Dict[str, ShareLink] = {}       # token → ShareLink
        self._annotations: Dict[str, Annotation] = {}  # annotation_id → Annotation
        self._script_shares: Dict[int, List[str]] = {}  # script_id → [token, ...]

    # ═══════════════ 剧本共享 ═══════════════

    def share_script(
        self,
        script_id: int,
        shared_by: str,
        shared_with: str = "",
        permission: str = SharePermission.VIEW,
        ttl_hours: int = 72,
    ) -> ShareLink:
        """分享剧本给特定用户或生成公开链接。

        Args:
            script_id: 剧本 ID
            shared_by: 分享者
            shared_with: 被分享者（空=生成公开链接）
            permission: view / comment / edit
            ttl_hours: 公开链接有效期（小时）

        Returns:
            ShareLink
        """
        import hashlib
        token = hashlib.md5(
            f"{script_id}-{shared_by}-{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        expires = ""
        if not shared_with:
            expires = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()

        link = ShareLink(
            script_id=script_id,
            shared_by=shared_by,
            shared_with=shared_with,
            permission=permission,
            token=token,
            expires_at=expires,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        self._shares[token] = link
        if script_id not in self._script_shares:
            self._script_shares[script_id] = []
        self._script_shares[script_id].append(token)

        logger.info(
            f"Script shared: script={script_id} by={shared_by} "
            f"with={shared_with or 'public'} permission={permission}"
        )
        return link

    def get_share(self, token: str) -> Optional[ShareLink]:
        """通过 token 获取分享链接。"""
        link = self._shares.get(token)
        if link and link.is_expired:
            return None
        return link

    def list_shares(self, script_id: int) -> List[ShareLink]:
        """列出剧本的所有分享链接。"""
        tokens = self._script_shares.get(script_id, [])
        return [
            self._shares[t] for t in tokens
            if t in self._shares and not self._shares[t].is_expired
        ]

    def revoke_share(self, token: str) -> bool:
        """撤销分享链接。"""
        link = self._shares.pop(token, None)
        if link and link.script_id in self._script_shares:
            self._script_shares[link.script_id].remove(token)
            return True
        return False

    def check_access(self, script_id: int, user_id: str) -> str:
        """检查用户对剧本的访问权限。返回最高权限级别。"""
        tokens = self._script_shares.get(script_id, [])
        best = ""
        for t in tokens:
            link = self._shares.get(t)
            if link and not link.is_expired:
                if link.shared_with == user_id or link.is_public:
                    if link.permission == SharePermission.EDIT:
                        return SharePermission.EDIT
                    if link.permission == SharePermission.COMMENT and best != SharePermission.EDIT:
                        best = SharePermission.COMMENT
                    if link.permission == SharePermission.VIEW and not best:
                        best = SharePermission.VIEW
        return best

    # ═══════════════ 批注 ═══════════════

    def add_annotation(
        self,
        script_id: int,
        user_id: str,
        content: str,
        episode_number: int = 0,
        position: Optional[Dict] = None,
        annotation_type: str = "note",
    ) -> Annotation:
        """添加剧本批注。"""
        import uuid
        aid = f"ann_{uuid.uuid4().hex[:8]}"
        ann = Annotation(
            annotation_id=aid,
            script_id=script_id,
            user_id=user_id,
            episode_number=episode_number,
            position=position or {},
            content=content,
            annotation_type=annotation_type,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._annotations[aid] = ann
        logger.info(f"Annotation added: {aid} on script={script_id} by={user_id}")
        return ann

    def list_annotations(
        self, script_id: int, episode_number: Optional[int] = None, resolved: Optional[bool] = None
    ) -> List[Annotation]:
        """列出剧本的批注。"""
        result = []
        for ann in self._annotations.values():
            if ann.script_id != script_id:
                continue
            if episode_number is not None and ann.episode_number != episode_number:
                continue
            if resolved is not None and ann.resolved != resolved:
                continue
            result.append(ann)
        result.sort(key=lambda a: a.created_at)
        return result

    def reply_annotation(self, annotation_id: str, user_id: str, content: str) -> bool:
        """回复批注。"""
        ann = self._annotations.get(annotation_id)
        if not ann:
            return False
        ann.replies.append({
            "user_id": user_id,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return True

    def resolve_annotation(self, annotation_id: str, resolved_by: str) -> bool:
        """标记批注为已解决。"""
        ann = self._annotations.get(annotation_id)
        if not ann:
            return False
        ann.resolved = True
        ann.resolved_by = resolved_by
        return True

    # ═══════════════ 统计 ═══════════════

    def get_script_collaborators(self, script_id: int) -> List[str]:
        """获取剧本的协作者列表。"""
        tokens = self._script_shares.get(script_id, [])
        users = set()
        for t in tokens:
            link = self._shares.get(t)
            if link and not link.is_expired and not link.is_public:
                users.add(link.shared_with)
                users.add(link.shared_by)
        return list(users)

    def get_annotations_summary(self, script_id: int) -> Dict[str, int]:
        """获取批注摘要统计。"""
        annotations = self.list_annotations(script_id)
        open_count = sum(1 for a in annotations if not a.resolved)
        by_type = {}
        for a in annotations:
            by_type[a.annotation_type] = by_type.get(a.annotation_type, 0) + 1
        return {
            "total": len(annotations),
            "open": open_count,
            "resolved": len(annotations) - open_count,
            "by_type": by_type,
        }


# ═══════════════════════════════════════════════════════════════
# Global
# ═══════════════════════════════════════════════════════════════

_collaboration_service: Optional[CollaborationService] = None


def get_collaboration_service() -> CollaborationService:
    global _collaboration_service
    if _collaboration_service is None:
        _collaboration_service = CollaborationService()
    return _collaboration_service
