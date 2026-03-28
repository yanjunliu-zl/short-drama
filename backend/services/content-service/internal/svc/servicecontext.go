package svc

import (
	"fmt"
	"time"
	"short-drama-platform/content-service/internal/config"
	"short-drama-platform/content-service/internal/logic"
	"short-drama-platform/content-service/internal/repository"

	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type ServiceContext struct {
	Config         config.Config
	CaseRepo       repository.CaseRepository
	WorkRepo       repository.WorkRepository
	CaseService    logic.CaseService
	WorkService    logic.WorkService
	Redis          *redis.Redis
	// 可以添加其他依赖，如RabbitMQ客户端、Consul客户端等
}

func NewServiceContext(c config.Config) *ServiceContext {
	// 由于当前使用模拟数据，跳过数据库和Redis初始化
	// 实际生产环境中需要取消注释以下代码

	// // 初始化数据库连接
	// dsn := buildDSN(c.Database)
	// conn := sqlx.NewMysql(dsn)

	// // 初始化Redis
	// redisConf := redis.RedisConf{
	// 	Host:        fmt.Sprintf("%s:%d", c.Redis.Host, c.Redis.Port),
	// 	Type:        "node",
	// 	Pass:        c.Redis.Password,
	// 	Tls:         false,
	// 	NonBlock:    true,
	// 	PingTimeout: time.Second,
	// }
	// redisClient := redis.MustNewRedis(redisConf)

	// // 初始化仓库
	// caseRepo := repository.NewCaseRepository(conn)
	// workRepo := repository.NewWorkRepository(conn)

	// // 初始化服务
	// caseService := logic.NewCaseLogic(caseRepo, redisClient)
	// workService := logic.NewWorkLogic(workRepo, redisClient)

	// return &ServiceContext{
	// 	Config:      c,
	// 	CaseRepo:    caseRepo,
	// 	WorkRepo:    workRepo,
	// 	CaseService: caseService,
	// 	WorkService: workService,
	// 	Redis:       redisClient,
	// }

	// 临时返回空ServiceContext
	return &ServiceContext{
		Config: c,
		// 其他字段留空，处理程序使用模拟数据
	}
}

func buildDSN(db config.DatabaseConfig) string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
		db.User, db.Password, db.Host, db.Port, db.DBName)
}