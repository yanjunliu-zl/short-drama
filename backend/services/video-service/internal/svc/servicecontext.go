package svc

import (
	"fmt"
	"time"
	"short-drama-platform/video-service/internal/config"
	"short-drama-platform/video-service/internal/logic"
	"short-drama-platform/video-service/internal/repository"
	"short-drama-platform/video-service/internal/types"

	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type ServiceContext struct {
	Config       config.Config
	VideoRepo    repository.VideoRepository
	VideoService types.VideoService
	Redis        *redis.Redis
	// 可以添加其他依赖，如RabbitMQ客户端、消息队列生产者等
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
	videoRepo := repository.NewVideoRepository(conn)

	// 初始化视频服务
	videoService := logic.NewVideoLogic(videoRepo, redisClient)

	return &ServiceContext{
		Config:       c,
		VideoRepo:    videoRepo,
		VideoService: videoService,
		Redis:        redisClient,
	}
}

func buildDSN(db config.DatabaseConfig) string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
		db.User, db.Password, db.Host, db.Port, db.DBName)
}