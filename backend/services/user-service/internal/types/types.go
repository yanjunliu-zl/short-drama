package types

import (
	"context"
	"time"
)

// 注册请求
type RegisterRequest struct {
	Username string `json:"username" validate:"required,min=3,max=50"`
	Email    string `json:"email" validate:"required,email"`
	Password string `json:"password" validate:"required,min=6,max=50"`
	Phone    string `json:"phone" validate:"omitempty,phone"`
}

// 注册响应
type RegisterResponse struct {
	ID       int64  `json:"id"`
	Username string `json:"username"`
	Email    string `json:"email"`
	Token    string `json:"token"`
}

// 登录请求
type LoginRequest struct {
	Username string `json:"username" validate:"required"`
	Password string `json:"password" validate:"required"`
}

// 登录响应
type LoginResponse struct {
	ID           int64     `json:"id"`
	Username     string    `json:"username"`
	Email        string    `json:"email"`
	Token        string    `json:"token"`
	RefreshToken string    `json:"refresh_token"`
	ExpiresAt    time.Time `json:"expires_at"`
}

// 获取用户请求
type GetUserRequest struct {
	ID int64 `path:"id"`
}

// 获取用户响应
type GetUserResponse struct {
	ID          int64     `json:"id"`
	Username    string    `json:"username"`
	Email       string    `json:"email"`
	Phone       string    `json:"phone,omitempty"`
	Avatar      string    `json:"avatar,omitempty"`
	Status      int       `json:"status"`
	Role        int       `json:"role"`
	LastLoginAt time.Time `json:"last_login_at,omitempty"`
	CreatedAt   time.Time `json:"created_at"`
}

// 更新用户请求
type UpdateUserRequest struct {
	ID       int64  `path:"id"`
	Username string `json:"username" validate:"omitempty,min=3,max=50"`
	Email    string `json:"email" validate:"omitempty,email"`
	Phone    string `json:"phone" validate:"omitempty,phone"`
	Avatar   string `json:"avatar" validate:"omitempty,url"`
}

// 更新用户响应
type UpdateUserResponse struct {
	ID       int64  `json:"id"`
	Username string `json:"username"`
	Email    string `json:"email"`
	Phone    string `json:"phone,omitempty"`
	Avatar   string `json:"avatar,omitempty"`
}

// 删除用户请求
type DeleteUserRequest struct {
	ID int64 `path:"id"`
}

// 删除用户响应
type DeleteUserResponse struct {
	Success bool `json:"success"`
}

// 用户列表请求
type ListUsersRequest struct {
	Page     int `form:"page,default=1" validate:"min=1"`
	PageSize int `form:"pageSize,default=10" validate:"min=1,max=100"`
}

// 用户列表响应
type ListUsersResponse struct {
	Users []UserInfo `json:"users"`
	Total int64      `json:"total"`
	Page  int        `json:"page"`
	Pages int        `json:"pages"`
}

type UserInfo struct {
	ID        int64     `json:"id"`
	Username  string    `json:"username"`
	Email     string    `json:"email"`
	Avatar    string    `json:"avatar,omitempty"`
	Status    int       `json:"status"`
	Role      int       `json:"role"`
	CreatedAt time.Time `json:"created_at"`
}

// 用户Profile请求
type GetUserProfileRequest struct {
	ID int64 `path:"id"`
}

// 用户Profile响应
type GetUserProfileResponse struct {
	UserID      int64     `json:"user_id"`
	FullName    string    `json:"full_name,omitempty"`
	Gender      int       `json:"gender"`
	Birthday    time.Time `json:"birthday,omitempty"`
	Bio         string    `json:"bio,omitempty"`
	Website     string    `json:"website,omitempty"`
	SocialLinks string    `json:"social_links,omitempty"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// 更新用户Profile请求
type UpdateUserProfileRequest struct {
	ID         int64     `path:"id"`
	FullName   string    `json:"full_name" validate:"omitempty,max=100"`
	Gender     int       `json:"gender" validate:"omitempty,oneof=0 1 2"`
	Birthday   time.Time `json:"birthday" validate:"omitempty"`
	Bio        string    `json:"bio" validate:"omitempty,max=500"`
	Website    string    `json:"website" validate:"omitempty,url"`
	SocialLinks string   `json:"social_links" validate:"omitempty"`
}

// 更新用户Profile响应
type UpdateUserProfileResponse struct {
	UserID      int64     `json:"user_id"`
	FullName    string    `json:"full_name,omitempty"`
	Gender      int       `json:"gender"`
	Birthday    time.Time `json:"birthday,omitempty"`
	Bio         string    `json:"bio,omitempty"`
	Website     string    `json:"website,omitempty"`
	SocialLinks string    `json:"social_links,omitempty"`
	UpdatedAt   time.Time `json:"updated_at"`
}

// UserService 用户服务接口
type UserService interface {
	Register(ctx context.Context, req *RegisterRequest) (*RegisterResponse, error)
	Login(ctx context.Context, req *LoginRequest) (*LoginResponse, error)
	GetUser(ctx context.Context, req *GetUserRequest) (*GetUserResponse, error)
	UpdateUser(ctx context.Context, req *UpdateUserRequest) (*UpdateUserResponse, error)
	DeleteUser(ctx context.Context, req *DeleteUserRequest) (*DeleteUserResponse, error)
	ListUsers(ctx context.Context, req *ListUsersRequest) (*ListUsersResponse, error)
	GetUserProfile(ctx context.Context, req *GetUserProfileRequest) (*GetUserProfileResponse, error)
	UpdateUserProfile(ctx context.Context, req *UpdateUserProfileRequest) (*UpdateUserProfileResponse, error)
}