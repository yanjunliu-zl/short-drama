package logic

import (
	"context"
	"short-drama-platform/content-service/internal/repository"
	"short-drama-platform/content-service/internal/types"

	"github.com/zeromicro/go-zero/core/stores/redis"
)

type WorkService interface {
	// 定义作品服务接口
}

type workLogic struct {
	workRepo repository.WorkRepository
	redis    *redis.Redis
}

func NewWorkLogic(workRepo repository.WorkRepository, redis *redis.Redis) WorkService {
	return &workLogic{
		workRepo: workRepo,
		redis:    redis,
	}
}