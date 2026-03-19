package model

import (
	"time"
)

type User struct {
	ID           int64     `db:"id" json:"id"`
	Username     string    `db:"username" json:"username"`
	Email        string    `db:"email" json:"email"`
	PasswordHash string    `db:"password_hash" json:"-"`
	Phone        string    `db:"phone" json:"phone,omitempty"`
	Avatar       string    `db:"avatar" json:"avatar,omitempty"`
	Status       int       `db:"status" json:"status"` // 0: inactive, 1: active, 2: suspended
	Role         int       `db:"role" json:"role"`     // 0: user, 1: admin, 2: superadmin
	LastLoginAt  time.Time `db:"last_login_at" json:"last_login_at,omitempty"`
	CreatedAt    time.Time `db:"created_at" json:"created_at"`
	UpdatedAt    time.Time `db:"updated_at" json:"updated_at"`
}

type UserProfile struct {
	UserID      int64     `db:"user_id" json:"user_id"`
	FullName    string    `db:"full_name" json:"full_name"`
	Gender      int       `db:"gender" json:"gender"` // 0: unknown, 1: male, 2: female
	Birthday    time.Time `db:"birthday" json:"birthday,omitempty"`
	Bio         string    `db:"bio" json:"bio,omitempty"`
	Website     string    `db:"website" json:"website,omitempty"`
	SocialLinks string    `db:"social_links" json:"social_links,omitempty"` // JSON格式
	CreatedAt   time.Time `db:"created_at" json:"created_at"`
	UpdatedAt   time.Time `db:"updated_at" json:"updated_at"`
}

type UserSession struct {
	ID           string    `db:"id" json:"id"`
	UserID       int64     `db:"user_id" json:"user_id"`
	AccessToken  string    `db:"access_token" json:"access_token"`
	RefreshToken string    `db:"refresh_token" json:"refresh_token"`
	ExpiresAt    time.Time `db:"expires_at" json:"expires_at"`
	CreatedAt    time.Time `db:"created_at" json:"created_at"`
}

// 用户状态常量
const (
	UserStatusInactive = iota
	UserStatusActive
	UserStatusSuspended
)

// 用户角色常量
const (
	UserRoleUser = iota
	UserRoleAdmin
	UserRoleSuperAdmin
)

// 性别常量
const (
	GenderUnknown = iota
	GenderMale
	GenderFemale
)