package svc

import (
	"fmt"
	"time"
	"short-drama-platform/overview-service/internal/config"
	"short-drama-platform/overview-service/internal/logic"
	"short-drama-platform/overview-service/internal/repository"

	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type ServiceContext struct {
	Config      config.Config
	OverviewRepo repository.OverviewRepository
	Redis       *redis.Redis
}

func NewServiceContext(c config.Config) *ServiceContext {
	// 初始化数据库连接
	dsn := buildDSN(c.Database)
	conn := sqlx.NewMysql(dsn)

	// 初始化Redis
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

	return &ServiceContext{
		Config:       c,
		OverviewRepo: overviewRepo,
		Redis:        redisClient,
	}
}

func buildDSN(db config.DatabaseConfig) string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
		db.User, db.Password, db.Host, db.Port, db.DBName)
}
