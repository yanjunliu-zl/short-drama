package model

import (
	"time"
)

// OverviewConfig 用户概览配置
type OverviewConfig struct {
	UserID         int64     `db:"user_id" json:"user_id"`
	VideoRatio     int       `db:"video_ratio" json:"video_ratio"`
	CreationMode   int       `db:"creation_mode" json:"creation_mode"`
	StyleReference int       `db:"style_reference" json:"style_reference"`
	CreatedAt      time.Time `db:"created_at" json:"created_at"`
	UpdatedAt      time.Time `db:"updated_at" json:"updated_at"`
}
