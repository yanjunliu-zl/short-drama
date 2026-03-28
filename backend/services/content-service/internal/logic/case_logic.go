package logic

import (
	"context"
	"short-drama-platform/content-service/internal/repository"
	"short-drama-platform/content-service/internal/types"

	"github.com/zeromicro/go-zero/core/stores/redis"
)

type CaseService interface {
	// 定义案例服务接口
}

type caseLogic struct {
	caseRepo repository.CaseRepository
	redis    *redis.Redis
}

func NewCaseLogic(caseRepo repository.CaseRepository, redis *redis.Redis) CaseService {
	return &caseLogic{
		caseRepo: caseRepo,
		redis:    redis,
	}
}