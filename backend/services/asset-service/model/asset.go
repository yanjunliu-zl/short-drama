package model

import (
	"time"
)

type Asset struct {
	ID          string    `db:"id" json:"id"`
	Name        string    `db:"name" json:"name"`
	Type        string    `db:"type" json:"type"` // AssetType枚举值
	Count       int       `db:"count" json:"count"`
	AccessLevel string    `db:"access_level" json:"access_level,omitempty"` // AccessLevel枚举值，公司资产使用
	OwnerID     string    `db:"owner_id" json:"owner_id,omitempty"`         // 个人资产所有者
	IsPersonal  bool      `db:"is_personal" json:"is_personal"`
	Description string    `db:"description" json:"description,omitempty"`
	LastUpdate  time.Time `db:"last_update" json:"last_update"`
	CreatedAt   time.Time `db:"created_at" json:"created_at"`
	UpdatedAt   time.Time `db:"updated_at" json:"updated_at"`
}

// AssetUsage 资产使用记录
type AssetUsage struct {
	ID        int64     `db:"id" json:"id"`
	AssetID   string    `db:"asset_id" json:"asset_id"`
	UserID    string    `db:"user_id" json:"user_id"`
	UsageType string    `db:"usage_type" json:"usage_type"` // "use", "share", "download"
	Count     int       `db:"count" json:"count"`
	CreatedAt time.Time `db:"created_at" json:"created_at"`
}

// AssetShare 资产分享记录
type AssetShare struct {
	ID           int64     `db:"id" json:"id"`
	AssetID      string    `db:"asset_id" json:"asset_id"`
	OwnerID      string    `db:"owner_id" json:"owner_id"`
	TargetUserID string    `db:"target_user_id" json:"target_user_id"`
	Status       string    `db:"status" json:"status"` // "active", "revoked"
	CreatedAt    time.Time `db:"created_at" json:"created_at"`
	ExpiresAt    time.Time `db:"expires_at" json:"expires_at,omitempty"`
}