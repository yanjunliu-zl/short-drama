package model

import (
	"time"
)

// MediaType 媒体类型
type MediaType string

const (
	MediaTypeImage MediaType = "image"
	MediaTypeVideo MediaType = "video"
)

// SourceService 来源服务
const (
	SourceLLMHUA         = "llmhua-service"
	SourceSceneExtractor = "scene-extractor"
	SourceStoryboard     = "storyboard-service"
	SourceVideoService   = "video-service"
	SourceFinalCut       = "final-cut-service"
)

// MediaAsset 媒体资产 — 记录存储在 Ceph 中的 AI 生成媒体文件
type MediaAsset struct {
	ID                int64     `db:"id" json:"id"`
	ObjectKey         string    `db:"object_key" json:"object_key"`                   // Ceph 对象 Key
	Bucket            string    `db:"bucket" json:"bucket"`                           // Ceph Bucket
	MediaType         string    `db:"media_type" json:"media_type"`                   // "image" / "video"
	ContentType       string    `db:"content_type" json:"content_type,omitempty"`     // MIME 类型
	FileSize          int64     `db:"file_size" json:"file_size"`                     // 文件大小
	OriginalURL       string    `db:"original_url" json:"original_url,omitempty"`     // 原始来源 URL
	CephURL           string    `db:"ceph_url" json:"ceph_url,omitempty"`             // Ceph 预签名 URL
	SourceService     string    `db:"source_service" json:"source_service"`           // 来源服务
	RelatedEntityType string    `db:"related_entity_type" json:"related_entity_type,omitempty"` // 关联实体类型
	RelatedEntityID   string    `db:"related_entity_id" json:"related_entity_id,omitempty"`     // 关联实体 ID
	UserID            string    `db:"user_id" json:"user_id,omitempty"`               // 用户 ID
	Metadata          string    `db:"metadata_json" json:"metadata,omitempty"`        // 额外元数据 JSON
	CreatedAt         time.Time `db:"created_at" json:"created_at"`
}
