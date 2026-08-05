package svc

import (
	"fmt"
	"short-drama-platform/overview-service/internal/config"
	"short-drama-platform/overview-service/internal/logic"
	"short-drama-platform/overview-service/internal/repository"
	"short-drama-platform/overview-service/internal/types"
	"time"

	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// ServiceContext 服务上下文，依赖注入容器
type ServiceContext struct {
	Config           config.Config
	OverviewRepo     repository.OverviewRepository
	OverviewService  types.OverviewService
	Redis            *redis.Redis
}

// NewServiceContext 创建服务上下文
func NewServiceContext(c config.Config) *ServiceContext {
	// 初始化数据库连接
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
		c.Database.User, c.Database.Password, c.Database.Host, c.Database.Port, c.Database.DBName)
	conn := sqlx.NewMysql(dsn)

	// 初始化 Redis
	redisConf := redis.RedisConf{
		Host:        fmt.Sprintf("%s:%d", c.Redis.Host, c.Redis.Port),
		Type:        "node",
		Pass:        c.Redis.Password,
		Tls:         false,
		NonBlock:    true,
		PingTimeout: time.Second,
	}
	redisClient := redis.MustNewRedis(redisConf)

	// 初始化仓库
	overviewRepo := repository.NewOverviewRepository(conn)

	// 初始化服务
	overviewService := logic.NewOverviewLogic(overviewRepo, redisClient)

	return &ServiceContext{
		Config:          c,
		OverviewRepo:    overviewRepo,
		OverviewService: overviewService,
		Redis:           redisClient,
	}
}
