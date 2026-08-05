package model

import (
	"time"
)

// FinalCutTask 最终剪辑任务模型
type FinalCutTask struct {
	ID              int64     `db:"id"`
	TaskID          string    `db:"task_id"`
	ProjectID       string    `db:"project_id"`
	Status          string    `db:"status"` // pending, processing, completed, failed, cancelled
	VideoURLs       string    `db:"video_ids"` // JSON array of video URLs
	AudioID         string    `db:"audio_id"`
	Transcript      string    `db:"transcript"`
	CutPoints       string    `db:"cut_points"` // JSON array
	Effects         string    `db:"effects"` // JSON array
	FontSize        int       `db:"font_size"`
	FontColor       string    `db:"font_color"`
	BackgroundColor string    `db:"background_color"`
	VideoURL        string    `db:"video_url"`
	ThumbnailURL    string    `db:"thumbnail_url"`
	Duration        float64   `db:"duration"`
	Progress        int       `db:"progress"` // 0-100
	ErrorMessage    string    `db:"error_message"`
	CreatedAt       time.Time `db:"created_at"`
	UpdatedAt       time.Time `db:"updated_at"`
}

// NewFinalCutTask 创建新的任务模型
func NewFinalCutTask(task *FinalCutTask) *FinalCutTask {
	return task
}
