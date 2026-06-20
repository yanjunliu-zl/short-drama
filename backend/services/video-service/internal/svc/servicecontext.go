package svc

import (
	"context"
	"fmt"
	"time"
	"short-drama-platform/video-service/internal/client"
	"short-drama-platform/video-service/internal/config"
	"short-drama-platform/video-service/internal/logic"
	"short-drama-platform/video-service/internal/repository"
	"short-drama-platform/video-service/internal/types"

	"github.com/zeromicro/go-zero/core/logx"
	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type ServiceContext struct {
	Config        config.Config
	VideoRepo     repository.VideoRepository
	VideoService  types.VideoService
	Redis         *redis.Redis
	StorageClient *client.StorageClient
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

	// 初始化对象存储客户端 (Ceph RGW / MinIO / S3)
	storageClient, err := client.NewStorageClient(c)
	if err != nil {
		logx.Errorf("failed to create storage client: %v", err)
		panic(err)
	}

	// 确保 Bucket 存在 (在启动时检查)
	ctx := context.Background()
	if err := storageClient.EnsureBucket(ctx); err != nil {
		logx.Errorf("failed to ensure bucket exists: %v", err)
		panic(err)
	}

	// 初始化仓库
	videoRepo := repository.NewVideoRepository(conn)

	// 初始化视频服务（注入存储客户端）
	videoService := logic.NewVideoLogic(videoRepo, redisClient, storageClient)

	return &ServiceContext{
		Config:        c,
		VideoRepo:     videoRepo,
		VideoService:  videoService,
		Redis:         redisClient,
		StorageClient: storageClient,
	}
}

func buildDSN(db config.DatabaseConfig) string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
		db.User, db.Password, db.Host, db.Port, db.DBName)
}