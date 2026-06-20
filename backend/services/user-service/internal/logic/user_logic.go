package logic

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"short-drama-platform/user-service/internal/repository"
	"short-drama-platform/user-service/internal/types"
	"short-drama-platform/user-service/model"
	"time"

	"github.com/zeromicro/go-zero/core/stores/redis"
)

// UserLogic 用户业务逻辑
type UserLogic struct {
	userRepo repository.UserRepository
	redis    *redis.Redis
}

// NewUserLogic 创建用户业务逻辑实例
func NewUserLogic(userRepo repository.UserRepository, redisClient *redis.Redis) types.UserService {
	return &UserLogic{
		userRepo: userRepo,
		redis:    redisClient,
	}
}

// Register 用户注册
func (l *UserLogic) Register(ctx context.Context, req *types.RegisterRequest) (*types.RegisterResponse, error) {
	// 检查用户名是否已存在
	existingByUser, err := l.userRepo.FindByUsername(ctx, req.Username)
	if err == nil && existingByUser != nil {
		return nil, fmt.Errorf("username %s already exists", req.Username)
	}

	// 检查邮箱是否已存在
	existingByEmail, err := l.userRepo.FindByEmail(ctx, req.Email)
	if err == nil && existingByEmail != nil {
		return nil, fmt.Errorf("email %s already exists", req.Email)
	}

	// 密码哈希
	passwordHash := hashPassword(req.Password)

	now := time.Now()
	user := &model.User{
		Username:     req.Username,
		Email:        req.Email,
		PasswordHash: passwordHash,
		Phone:        req.Phone,
		Status:       model.UserStatusActive,
		Role:         model.UserRoleUser,
		LastLoginAt:  now,
		CreatedAt:    now,
		UpdatedAt:    now,
	}

	id, err := l.userRepo.Create(ctx, user)
	if err != nil {
		return nil, fmt.Errorf("failed to create user: %w", err)
	}

	// 生成 token 和 session
	token := generateToken(id, req.Username)
	refreshToken := generateRefreshToken(id)
	expiresAt := now.Add(24 * time.Hour)

	session := &model.UserSession{
		ID:           fmt.Sprintf("sess_%d_%d", id, now.UnixNano()),
		UserID:       id,
		AccessToken:  token,
		RefreshToken: refreshToken,
		ExpiresAt:    expiresAt,
		CreatedAt:    now,
	}
	_ = l.userRepo.CreateSession(ctx, session)

	return &types.RegisterResponse{
		ID:           id,
		Username:     req.Username,
		Email:        req.Email,
		Token:        token,
		RefreshToken: refreshToken,
		ExpiresAt:    expiresAt,
	}, nil
}

// Login 用户登录
func (l *UserLogic) Login(ctx context.Context, req *types.LoginRequest) (*types.LoginResponse, error) {
	user, err := l.userRepo.FindByUsername(ctx, req.Username)
	if err != nil {
		return nil, fmt.Errorf("invalid username or password")
	}

	// 验证密码
	if user.PasswordHash != hashPassword(req.Password) {
		return nil, fmt.Errorf("invalid username or password")
	}

	// 检查用户状态
	if user.Status != model.UserStatusActive {
		return nil, fmt.Errorf("user account is not active")
	}

	// 更新最后登录时间
	now := time.Now()
	user.LastLoginAt = now
	user.UpdatedAt = now
	_ = l.userRepo.Update(ctx, user)

	// 生成 token 和 session
	token := generateToken(user.ID, user.Username)
	refreshToken := generateRefreshToken(user.ID)
	expiresAt := now.Add(24 * time.Hour)

	session := &model.UserSession{
		ID:           fmt.Sprintf("sess_%d_%d", user.ID, now.UnixNano()),
		UserID:       user.ID,
		AccessToken:  token,
		RefreshToken: refreshToken,
		ExpiresAt:    expiresAt,
		CreatedAt:    now,
	}
	_ = l.userRepo.CreateSession(ctx, session)

	return &types.LoginResponse{
		ID:           user.ID,
		Username:     user.Username,
		Email:        user.Email,
		Token:        token,
		RefreshToken: refreshToken,
		ExpiresAt:    expiresAt,
	}, nil
}

// GetUser 获取用户信息
func (l *UserLogic) GetUser(ctx context.Context, req *types.GetUserRequest) (*types.GetUserResponse, error) {
	user, err := l.userRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("user not found: %w", err)
	}

	return &types.GetUserResponse{
		ID:          user.ID,
		Username:    user.Username,
		Email:       user.Email,
		Phone:       user.Phone,
		Avatar:      user.Avatar,
		Status:      user.Status,
		Role:        user.Role,
		LastLoginAt: user.LastLoginAt,
		CreatedAt:   user.CreatedAt,
	}, nil
}

// UpdateUser 更新用户信息
func (l *UserLogic) UpdateUser(ctx context.Context, req *types.UpdateUserRequest) (*types.UpdateUserResponse, error) {
	user, err := l.userRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("user not found: %w", err)
	}

	if req.Username != "" {
		user.Username = req.Username
	}
	if req.Email != "" {
		user.Email = req.Email
	}
	if req.Phone != "" {
		user.Phone = req.Phone
	}
	if req.Avatar != "" {
		user.Avatar = req.Avatar
	}
	user.UpdatedAt = time.Now()

	if err := l.userRepo.Update(ctx, user); err != nil {
		return nil, fmt.Errorf("failed to update user: %w", err)
	}

	return &types.UpdateUserResponse{
		ID:       user.ID,
		Username: user.Username,
		Email:    user.Email,
		Phone:    user.Phone,
		Avatar:   user.Avatar,
	}, nil
}

// DeleteUser 删除用户
func (l *UserLogic) DeleteUser(ctx context.Context, req *types.DeleteUserRequest) (*types.DeleteUserResponse, error) {
	// 检查用户是否存在
	_, err := l.userRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("user not found: %w", err)
	}

	if err := l.userRepo.Delete(ctx, req.ID); err != nil {
		return nil, fmt.Errorf("failed to delete user: %w", err)
	}

	return &types.DeleteUserResponse{Success: true}, nil
}

// ListUsers 获取用户列表
func (l *UserLogic) ListUsers(ctx context.Context, req *types.ListUsersRequest) (*types.ListUsersResponse, error) {
	users, err := l.userRepo.List(ctx, req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("failed to list users: %w", err)
	}

	total, err := l.userRepo.Count(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to count users: %w", err)
	}

	userInfos := make([]types.UserInfo, 0, len(users))
	for _, u := range users {
		userInfos = append(userInfos, types.UserInfo{
			ID:        u.ID,
			Username:  u.Username,
			Email:     u.Email,
			Avatar:    u.Avatar,
			Status:    u.Status,
			Role:      u.Role,
			CreatedAt: u.CreatedAt,
		})
	}

	pages := (int(total) + req.PageSize - 1) / req.PageSize
	return &types.ListUsersResponse{
		Users: userInfos,
		Total: total,
		Page:  req.Page,
		Pages: pages,
	}, nil
}

// GetUserProfile 获取用户 Profile
func (l *UserLogic) GetUserProfile(ctx context.Context, req *types.GetUserProfileRequest) (*types.GetUserProfileResponse, error) {
	profile, err := l.userRepo.FindProfileByUserID(ctx, req.ID)
	if err != nil {
		// Profile 可能尚未创建，返回空
		return &types.GetUserProfileResponse{
			UserID: req.ID,
		}, nil
	}

	return &types.GetUserProfileResponse{
		UserID:      profile.UserID,
		FullName:    profile.FullName,
		Gender:      profile.Gender,
		Birthday:    profile.Birthday,
		Bio:         profile.Bio,
		Website:     profile.Website,
		SocialLinks: profile.SocialLinks,
		CreatedAt:   profile.CreatedAt,
		UpdatedAt:   profile.UpdatedAt,
	}, nil
}

// UpdateUserProfile 更新用户 Profile
func (l *UserLogic) UpdateUserProfile(ctx context.Context, req *types.UpdateUserProfileRequest) (*types.UpdateUserProfileResponse, error) {
	// 确保用户存在
	_, err := l.userRepo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("user not found: %w", err)
	}

	profile := &model.UserProfile{
		UserID:      req.ID,
		FullName:    req.FullName,
		Gender:      req.Gender,
		Birthday:    req.Birthday,
		Bio:         req.Bio,
		Website:     req.Website,
		SocialLinks: req.SocialLinks,
	}

	if err := l.userRepo.UpsertProfile(ctx, profile); err != nil {
		return nil, fmt.Errorf("failed to update profile: %w", err)
	}

	return &types.UpdateUserProfileResponse{
		UserID:      profile.UserID,
		FullName:    profile.FullName,
		Gender:      profile.Gender,
		Birthday:    profile.Birthday,
		Bio:         profile.Bio,
		Website:     profile.Website,
		SocialLinks: profile.SocialLinks,
		UpdatedAt:   time.Now(),
	}, nil
}

// ==============================
// 辅助函数
// ==============================

// hashPassword 密码哈希
func hashPassword(password string) string {
	h := sha256.New()
	h.Write([]byte(password))
	return hex.EncodeToString(h.Sum(nil))
}

// generateToken 生成访问令牌（简化版，生产环境应使用 JWT）
func generateToken(userID int64, username string) string {
	payload := fmt.Sprintf("%d:%s:%d", userID, username, time.Now().UnixNano())
	h := sha256.New()
	h.Write([]byte(payload))
	return hex.EncodeToString(h.Sum(nil))
}

// generateRefreshToken 生成刷新令牌
func generateRefreshToken(userID int64) string {
	payload := fmt.Sprintf("refresh:%d:%d", userID, time.Now().UnixNano())
	h := sha256.New()
	h.Write([]byte(payload))
	return hex.EncodeToString(h.Sum(nil))
}
