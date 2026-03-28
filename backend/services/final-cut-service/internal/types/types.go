package types

import (
	"context"
	"time"
)

// FinalCutRequest 最终剪辑请求
type FinalCutRequest struct {
	ProjectID    string   `json:"project_id" validate:"required"`
	VideoIDs     []string `json:"video_ids" validate:"required"`
	AudioID      string   `json:"audio_id" validate:"required"`
	Transcript   string   `json:"transcript" validate:"required"`
	CutPoints    []CutPoint `json:"cut_points" validate:"required"`
	Effects      []Effect   `json:"effects" validate:"omitempty"`
	FontSize     int        `json:"font_size" validate:"omitempty"`
	FontColor    string     `json:"font_color" validate:"omitempty"`
	BackgroundColor string `json:"background_color" validate:"omitempty"`
}

// CutPoint 切点信息
type CutPoint struct {
	StartTime float64 `json:"start_time" validate:"required"`
	EndTime   float64 `json:"end_time" validate:"required"`
	SceneID   string  `json:"scene_id" validate:"required"`
}

// Effect 特效信息
type Effect struct {
	Name    string  `json:"name" validate:"required"`
	StartTime float64 `json:"start_time" validate:"required"`
	EndTime   float64 `json:"end_time" validate:"required"`
	Params  map[string]interface{} `json:"params" validate:"omitempty"`
}

// FinalCutResponse 最终剪辑响应
type FinalCutResponse struct {
	TaskID       string    `json:"task_id"`
	Status       string    `json:"status"`
	VideoURL     string    `json:"video_url,omitempty"`
	ThumbnailURL string    `json:"thumbnail_url,omitempty"`
	 Duration    float64   `json:"duration,omitempty"`
	CreatedAt    time.Time `json:"created_at"`
}

// GetFinalCutStatusRequest 获取剪辑状态请求
type GetFinalCutStatusRequest struct {
	TaskID string `path:"task_id" validate:"required"`
}

// GetFinalCutStatusResponse 获取剪辑状态响应
type GetFinalCutStatusResponse struct {
	TaskID       string    `json:"task_id"`
	Status       string    `json:"status"`
	Progress     int       `json:"progress"`
	VideoURL     string    `json:"video_url,omitempty"`
	ThumbnailURL string    `json:"thumbnail_url,omitempty"`
	ErrorMessage string    `json:"error_message,omitempty"`
	UpdatedAt    time.Time `json:"updated_at"`
}

// FinalCutListRequest 列表请求
type FinalCutListRequest struct {
	ProjectID string `form:"project_id" validate:"required"`
	Page      int    `form:"page,default=1" validate:"min=1"`
	PageSize  int    `form:"pageSize,default=10" validate:"min=1,max=100"`
}

// FinalCutListResponse 列表响应
type FinalCutListResponse struct {
	Tasks   []TaskInfo `json:"tasks"`
	Total   int64      `json:"total"`
	Page    int        `json:"page"`
	Pages   int        `json:"pages"`
}

type TaskInfo struct {
	TaskID       string    `json:"task_id"`
	ProjectID    string    `json:"project_id"`
	Status       string    `json:"status"`
	VideoURL     string    `json:"video_url,omitempty"`
	ThumbnailURL string    `json:"thumbnail_url,omitempty"`
	Duration     float64   `json:"duration,omitempty"`
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

// CancelFinalCutRequest 取消剪辑请求
type CancelFinalCutRequest struct {
	TaskID string `json:"task_id" validate:"required"`
}

// CancelFinalCutResponse 取消剪辑响应
type CancelFinalCutResponse struct {
	Success bool `json:"success"`
}

// FinalCutService 最终剪辑服务接口
type FinalCutService interface {
	CreateFinalCut(ctx context.Context, req *FinalCutRequest) (*FinalCutResponse, error)
	GetStatus(ctx context.Context, req *GetFinalCutStatusRequest) (*GetFinalCutStatusResponse, error)
	ListTasks(ctx context.Context, req *FinalCutListRequest) (*FinalCutListResponse, error)
	CancelTask(ctx context.Context, req *CancelFinalCutRequest) (*CancelFinalCutResponse, error)
}
