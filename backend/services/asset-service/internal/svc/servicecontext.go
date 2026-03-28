package svc

import (
	"fmt"
	"time"
	"short-drama-platform/asset-service/internal/config"
	"short-drama-platform/asset-service/internal/logic"
	"short-drama-platform/asset-service/internal/repository"
	"short-drama-platform/asset-service/internal/types"

	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type ServiceContext struct {
	Config       config.Config
	AssetRepo    repository.AssetRepository
	AssetService types.AssetService
	Redis        *redis.Redis
	// 可以添加其他依赖，如RabbitMQ客户端、Consul客户端等
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
	assetRepo := repository.NewAssetRepository(conn)

	// 初始化资产服务
	assetService := logic.NewAssetLogic(assetRepo, redisClient)

	return &ServiceContext{
		Config:       c,
		AssetRepo:    assetRepo,
		AssetService: assetService,
		Redis:        redisClient,
	}
}

func buildDSN(db config.DatabaseConfig) string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
		db.User, db.Password, db.Host, db.Port, db.DBName)
}