package model

import "time"

// Case 短剧案例
type Case struct {
	ID           string    `db:"id" json:"id"`
	Title        string    `db:"title" json:"title"`
	Description  string    `db:"description" json:"description"`
	Author       string    `db:"author" json:"author"`
	CoverURL     string    `db:"cover_url" json:"cover_url"`
	DemoVideoURL string    `db:"demo_video_url" json:"demo_video_url"`
	Genre        string    `db:"genre" json:"genre"`
	Tags         string    `db:"tags" json:"tags"`
	Status       string    `db:"status" json:"status"`
	ViewCount    int64     `db:"view_count" json:"view_count"`
	LikeCount    int64     `db:"like_count" json:"like_count"`
	ShareCount   int64     `db:"share_count" json:"share_count"`
	UserID       string    `db:"user_id" json:"user_id"`
	CreatedAt    time.Time `db:"created_at" json:"created_at"`
	UpdatedAt    time.Time `db:"updated_at" json:"updated_at"`
}

// RecommendRequest 推荐请求
type RecommendRequest struct {
	UserID    string `form:"user_id"`
	Scene     string `form:"scene"`
	Limit     int    `form:"limit"`
	PageSize  int    `form:"page_size"`
}

// RecommendResponse 推荐响应
type RecommendResponse struct {
	Code    int              `json:"code"`
	Message string           `json:"message"`
	Data    *RecommendData   `json:"data,omitempty"`
}

// RecommendData 推荐数据
type RecommendData struct {
	Items      []*RecommendItem `json:"items"`
	Total      int              `json:"total"`
	RecallFrom []string         `json:"recall_from"`
}

// RecommendItem 推荐条目
type RecommendItem struct {
	Case  *Case   `json:"case"`
	Score float64 `json:"score"`
	Source string `json:"source"`
}

// FeedbackRequest 反馈请求
type FeedbackRequest struct {
	UserID   string `json:"user_id"`
	ItemID   string `json:"item_id"`
	Action   string `json:"action"`   // view, like, share, skip
	Position int    `json:"position"`
	Source   string `json:"source"`
}

// RecallResult 召回结果
type RecallResult struct {
	Case   *Case
	Score  float64
	Source string
}

// RankedItem 排序后条目
type RankedItem struct {
	Case  *Case
	Score float64
}

// UserProfile 用户画像
type UserProfile struct {
	UserID        string
	TopTags       []string
	TopGenres     []string
	TopAuthors    []string
	ViewCount     int
	LikeCount     int
	TotalInteract  int
}
