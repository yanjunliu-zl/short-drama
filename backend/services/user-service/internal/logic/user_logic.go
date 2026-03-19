package logic

import (
	"context"
	"errors"
	"short-drama-platform/user-service/internal/repository"
	"short-drama-platform/user-service/internal/types"

	"github.com/zeromicro/go-zero/core/stores/redis"
)

type UserLogic struct {
	userRepo repository.UserRepository
	redis    *redis.Redis
}

func NewUserLogic(userRepo repository.UserRepository, redis *redis.Redis) types.UserService {
	return &UserLogic{
		userRepo: userRepo,
		redis:    redis,
	}
}

func (l *UserLogic) Register(ctx context.Context, req *types.RegisterRequest) (*types.RegisterResponse, error) {
	// TODO: implement register logic
	return nil, errors.New("not implemented")
}

func (l *UserLogic) Login(ctx context.Context, req *types.LoginRequest) (*types.LoginResponse, error) {
	// TODO: implement login logic
	return nil, errors.New("not implemented")
}

func (l *UserLogic) GetUser(ctx context.Context, req *types.GetUserRequest) (*types.GetUserResponse, error) {
	// TODO: implement get user logic
	return nil, errors.New("not implemented")
}

func (l *UserLogic) UpdateUser(ctx context.Context, req *types.UpdateUserRequest) (*types.UpdateUserResponse, error) {
	// TODO: implement update user logic
	return nil, errors.New("not implemented")
}

func (l *UserLogic) DeleteUser(ctx context.Context, req *types.DeleteUserRequest) (*types.DeleteUserResponse, error) {
	// TODO: implement delete user logic
	return nil, errors.New("not implemented")
}

func (l *UserLogic) ListUsers(ctx context.Context, req *types.ListUsersRequest) (*types.ListUsersResponse, error) {
	// TODO: implement list users logic
	return nil, errors.New("not implemented")
}

func (l *UserLogic) GetUserProfile(ctx context.Context, req *types.GetUserProfileRequest) (*types.GetUserProfileResponse, error) {
	// TODO: implement get user profile logic
	return nil, errors.New("not implemented")
}

func (l *UserLogic) UpdateUserProfile(ctx context.Context, req *types.UpdateUserProfileRequest) (*types.UpdateUserProfileResponse, error) {
	// TODO: implement update user profile logic
	return nil, errors.New("not implemented")
}