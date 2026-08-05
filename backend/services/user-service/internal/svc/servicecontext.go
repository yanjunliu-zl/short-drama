package svc

import (
	"fmt"
	"time"
	"short-drama-platform/user-service/internal/config"
	"short-drama-platform/user-service/internal/logic"
	"short-drama-platform/user-service/internal/repository"
	"short-drama-platform/user-service/internal/types"
	dbshared "short-drama-platform/shared/db"

	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type ServiceContext struct {
	Config      config.Config
	UserRepo    repository.UserRepository
	UserService types.UserService
	Redis       *redis.Redis
	DBResolver  *dbshared.DBResolver // P1: Read/write splitting
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
	userRepo := repository.NewUserRepository(conn)

	// 初始化用户服务
	userService := logic.NewUserLogic(userRepo, redisClient)

	return &ServiceContext{
		Config:      c,
		UserRepo:    userRepo,
		UserService: userService,
		Redis:       redisClient,
	}
}

func buildDSN(db config.DatabaseConfig) string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
		db.User, db.Password, db.Host, db.Port, db.DBName)
}