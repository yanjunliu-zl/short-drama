package svc

import (
	"fmt"
	"short-drama-platform/final-cut-service/internal/client"
	"short-drama-platform/final-cut-service/internal/config"
	"short-drama-platform/final-cut-service/internal/repository"

	goredis "github.com/go-redis/redis/v8"
	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type ServiceContext struct {
	Config             config.Config
	DB                 sqlx.SqlConn
	Redis              *redis.Redis
	RedisCluster       interface{}
	RabbitMQ           RabbitMQClient
	FinalCutRepository repository.FinalCutRepository
	ScriptService      *client.ScriptServiceClient
	VideoService       *client.VideoServiceClient
	StorageClient      *client.StorageClient
	ServiceDiscovery   *client.ServiceDiscovery
	DistributedLocker  *client.DistributedLocker
}

func NewServiceContext(c config.Config) *ServiceContext {
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?parseTime=true&loc=Local",
		c.Database.User, c.Database.Password, c.Database.Host, c.Database.Port, c.Database.DBName)
	db := sqlx.NewMysql(dsn)

	// 单机Redis
	addr := fmt.Sprintf("%s:%d", c.Redis.Host, c.Redis.Port)
	rds := redis.New(addr, redis.WithPass(c.Redis.Password))

	// Redis集群支持 (当前未启用，保留接口)
	var redisCluster interface{}

	// 存储客户端
	storageClient, err := client.NewStorageClient(c)
	if err != nil {
		panic(err)
	}

	// Consul服务发现
	var serviceDiscovery *client.ServiceDiscovery
	if c.Consul.Enabled {
		sd, err := client.NewServiceDiscovery(c.Consul)
		if err == nil {
			serviceDiscovery = sd
			go serviceDiscovery.RefreshServices()
		}
	}

	// 分布式锁
	var distributedLocker *client.DistributedLocker
	if rc, ok := redisCluster.(*goredis.Client); ok && rc != nil {
		distributedLocker = client.NewDistributedLocker(rc)
	}

	rabbitMQ := NewRabbitMQClient(c.RabbitMQ)

	return &ServiceContext{
		Config:             c,
		DB:                 db,
		Redis:              rds,
		RedisCluster:       redisCluster,
		RabbitMQ:           rabbitMQ,
		FinalCutRepository: repository.NewFinalCutRepository(db),
		ScriptService:      client.NewScriptServiceClient(c),
		VideoService:       client.NewVideoServiceClient(c),
		StorageClient:      storageClient,
		ServiceDiscovery:   serviceDiscovery,
		DistributedLocker:  distributedLocker,
	}
}
