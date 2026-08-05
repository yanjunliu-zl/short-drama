package model

import (
	"time"
)

// VideoStatus 视频状态
type VideoStatus string

const (
	VideoStatusUploaded   VideoStatus = "uploaded"   // 已上传
	VideoStatusProcessing VideoStatus = "processing" // 处理中
	VideoStatusProcessed  VideoStatus = "processed"  // 处理完成
	VideoStatusFailed     VideoStatus = "failed"     // 处理失败
	VideoStatusCancelled  VideoStatus = "cancelled"  // 已取消
)

type Video struct {
	ID          string      `db:"id" json:"id"`
	Title       string      `db:"title" json:"title"`
	Description string      `db:"description" json:"description,omitempty"`
	UserID      string      `db:"user_id" json:"user_id"`
	FileName    string      `db:"file_name" json:"file_name"`
	FileSize    int64       `db:"file_size" json:"file_size"`
	FileFormat  string      `db:"file_format" json:"file_format"`
	FilePath    string      `db:"file_path" json:"file_path,omitempty"`
	OutputPath  string      `db:"output_path" json:"output_path,omitempty"`
	Status      VideoStatus `db:"status" json:"status"`
	Progress    int         `db:"progress" json:"progress"` // 0-100
	ErrorMsg    string      `db:"error_msg" json:"error_msg,omitempty"`
	Metadata    string      `db:"metadata" json:"metadata,omitempty"` // JSON格式的元数据
	CreatedAt   time.Time   `db:"created_at" json:"created_at"`
	UpdatedAt   time.Time   `db:"updated_at" json:"updated_at"`
	ProcessedAt time.Time   `db:"processed_at" json:"processed_at,omitempty"`
}

type VideoProcessingJob struct {
	ID        string      `db:"id" json:"id"`
	VideoID   string      `db:"video_id" json:"video_id"`
	JobType   string      `db:"job_type" json:"job_type"` // "transcode", "extract_audio", "add_subtitle", etc.
	Status    string      `db:"status" json:"status"`     // "pending", "processing", "completed", "failed"
	Progress  int         `db:"progress" json:"progress"`
	Priority  int         `db:"priority" json:"priority"` // 优先级 1-5, 1最高
	Params    string      `db:"params" json:"params"`     // JSON格式参数
	Result    string      `db:"result" json:"result,omitempty"` // JSON格式结果
	Error     string      `db:"error" json:"error,omitempty"`
	CreatedAt time.Time   `db:"created_at" json:"created_at"`
	UpdatedAt time.Time   `db:"updated_at" json:"updated_at"`
	StartedAt time.Time   `db:"started_at" json:"started_at,omitempty"`
	CompletedAt time.Time `db:"completed_at" json:"completed_at,omitempty"`
}

type VideoUsage struct {
	ID        int64     `db:"id" json:"id"`
	VideoID   string    `db:"video_id" json:"video_id"`
	UserID    string    `db:"user_id" json:"user_id"`
	Action    string    `db:"action" json:"action"` // "view", "download", "share"
	CreatedAt time.Time `db:"created_at" json:"created_at"`
}