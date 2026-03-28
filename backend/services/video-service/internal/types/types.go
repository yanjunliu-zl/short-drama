package types

import (
	"context"
	"time"
)

// 创建视频请求
type CreateVideoRequest struct {
	Title       string `json:"title" validate:"required"`
	Description string `json:"description,omitempty"`
	FileName    string `json:"file_name" validate:"required"`
	FileSize    int64  `json:"file_size" validate:"required,min=1"`
	FileFormat  string `json:"file_format" validate:"required"`
}

// 创建视频响应
type CreateVideoResponse struct {
	ID        string    `json:"id"`
	Title     string    `json:"title"`
	Status    string    `json:"status"`
	CreatedAt time.Time `json:"created_at"`
	UploadURL string    `json:"upload_url,omitempty"` // 用于上传文件的预签名URL
}

// 获取视频列表请求
type ListVideosRequest struct {
	UserID string `form:"user_id,omitempty"`
	Status string `form:"status,omitempty"`
	Page   int    `form:"page,default=1" validate:"min=1"`
	PageSize int  `form:"page_size,default=10" validate:"min=1,max=100"`
}

// 获取视频列表响应
type ListVideosResponse struct {
	Videos  []VideoResponse `json:"videos"`
	Total   int64           `json:"total"`
	Page    int             `json:"page"`
	PageSize int            `json:"page_size"`
}

// 获取视频详情请求
type GetVideoRequest struct {
	ID string `path:"id" validate:"required"`
}

// 更新视频请求
type UpdateVideoRequest struct {
	ID          string  `path:"id" validate:"required"`
	Title       *string `json:"title,omitempty"`
	Description *string `json:"description,omitempty"`
}

// 删除视频请求
type DeleteVideoRequest struct {
	ID string `path:"id" validate:"required"`
}

// 删除视频响应
type DeleteVideoResponse struct {
	Success bool `json:"success"`
}

// 处理视频请求
type ProcessVideoRequest struct {
	ID     string                 `path:"id" validate:"required"`
	Action string                 `json:"action" validate:"required"` // "transcode", "extract_audio", "add_subtitle"
	Params map[string]interface{} `json:"params,omitempty"`
}

// 处理视频响应
type ProcessVideoResponse struct {
	JobID   string `json:"job_id"`
	VideoID string `json:"video_id"`
	Action  string `json:"action"`
	Status  string `json:"status"`
}

// 获取处理进度请求
type GetProcessingProgressRequest struct {
	ID string `path:"id" validate:"required"`
}

// 获取处理进度响应
type GetProcessingProgressResponse struct {
	VideoID  string `json:"video_id"`
	Status   string `json:"status"`
	Progress int    `json:"progress"`
	Message  string `json:"message,omitempty"`
}

// 视频响应
type VideoResponse struct {
	ID          string    `json:"id"`
	Title       string    `json:"title"`
	Description string    `json:"description,omitempty"`
	UserID      string    `json:"user_id"`
	FileName    string    `json:"file_name"`
	FileSize    int64     `json:"file_size"`
	FileFormat  string    `json:"file_format"`
	Status      string    `json:"status"`
	Progress    int       `json:"progress"`
	ErrorMsg    string    `json:"error_msg,omitempty"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
	ProcessedAt time.Time `json:"processed_at,omitempty"`
}

// 视频服务接口
type VideoService interface {
	CreateVideo(ctx context.Context, req *CreateVideoRequest) (*CreateVideoResponse, error)
	ListVideos(ctx context.Context, req *ListVideosRequest) (*ListVideosResponse, error)
	GetVideo(ctx context.Context, req *GetVideoRequest) (*VideoResponse, error)
	UpdateVideo(ctx context.Context, req *UpdateVideoRequest) (*VideoResponse, error)
	DeleteVideo(ctx context.Context, req *DeleteVideoRequest) (*DeleteVideoResponse, error)
	ProcessVideo(ctx context.Context, req *ProcessVideoRequest) (*ProcessVideoResponse, error)
	GetProcessingProgress(ctx context.Context, req *GetProcessingProgressRequest) (*GetProcessingProgressResponse, error)
}