package model

import (
	"time"
)

// Scene 场景
type Scene struct {
	ID          int64     `db:"id" json:"id"`
	CaseID      string    `db:"case_id" json:"caseId"`
	Title       string    `db:"title" json:"title"`
	Description string    `db:"description" json:"description"`
	Location    string    `db:"location" json:"location"`
	TimeOfDay   string    `db:"time_of_day" json:"timeOfDay"`
	SortOrder   int       `db:"sort_order" json:"order"`
	CreatedAt   time.Time `db:"created_at" json:"createdAt"`
	UpdatedAt   time.Time `db:"updated_at" json:"updatedAt"`
}

// Character 角色
type Character struct {
	ID          int64     `db:"id" json:"id"`
	CaseID      string    `db:"case_id" json:"caseId"`
	Name        string    `db:"name" json:"name"`
	Role        string    `db:"role" json:"role"`
	Description string    `db:"description" json:"description"`
	AvatarURL   string    `db:"avatar_url" json:"avatarUrl"`
	CreatedAt   time.Time `db:"created_at" json:"createdAt"`
	UpdatedAt   time.Time `db:"updated_at" json:"updatedAt"`
}

// Case 案例
type Case struct {
	ID          string    `db:"id" json:"id"`
	Title       string    `db:"title" json:"title"`
	Description string    `db:"description" json:"description"`
	Author      string    `db:"author" json:"author"`
	CoverURL      string    `db:"cover_url" json:"coverUrl"`
	DemoVideoURL  string    `db:"demo_video_url" json:"demoVideoUrl"`
	Genre         string    `db:"genre" json:"genre"`
	Tags        string    `db:"tags" json:"tags"` // comma-separated
	Status      string    `db:"status" json:"status"`
	ViewCount   int64     `db:"view_count" json:"views"`
	LikeCount   int64     `db:"like_count" json:"likes"`
	ShareCount  int64     `db:"share_count" json:"shareCount"`
	UserID      string    `db:"user_id" json:"userId"`
	CreatedAt   time.Time `db:"created_at" json:"createdAt"`
	UpdatedAt   time.Time `db:"updated_at" json:"updatedAt"`
}

// Work 作品
type Work struct {
	ID           string    `db:"id" json:"id"`
	CaseID       string    `db:"case_id" json:"caseId"`
	UserID       string    `db:"user_id" json:"userId"`
	Title        string    `db:"title" json:"title"`
	Description  string    `db:"description" json:"description"`
	Status       string    `db:"status" json:"status"` // draft, editing, completed, exported
	Progress     int       `db:"progress" json:"progress"`
	PipelineData string    `db:"pipeline_data" json:"pipelineData"`
	CreatedAt    time.Time `db:"created_at" json:"createdAt"`
	UpdatedAt    time.Time `db:"updated_at" json:"updatedAt"`
}

// ScriptOutline 剧本大纲
type ScriptOutline struct {
	ID        string    `db:"id" json:"id"`
	CaseID    string    `db:"case_id" json:"caseId"`
	Content   string    `db:"content" json:"content"`
	CreatedAt time.Time `db:"created_at" json:"createdAt"`
	UpdatedAt time.Time `db:"updated_at" json:"updatedAt"`
}
