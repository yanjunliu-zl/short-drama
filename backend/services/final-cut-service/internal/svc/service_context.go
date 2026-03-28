package svc

import (
	"context"
	"short-drama-platform/final-cut-service/internal/client"
	"short-drama-platform/final-cut-service/internal/config"
	"short-drama-platform/final-cut-service/internal/repository"

	"github.com/go-redis/redis/v8"
	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
	"github.com/zeromicro/go-zero/core/stores/rediscluster"
)

type ServiceContext struct {
	Config            config.Config
	DB                sqlx.SqlConn
	Redis             *redis.Redis
	RedisCluster      *redisCluster.Client
	RabbitMQ          RabbitMQClient
	FinalCutRepository repository.FinalCutRepository
	ScriptService     *client.ScriptServiceClient
	VideoService      *client.VideoServiceClient
	StorageClient     *client.StorageClient
	ServiceDiscovery  *client.ServiceDiscovery
	DistributedLocker *client.DistributedLocker
}

func NewServiceContext(c config.Config) *ServiceContext {
	dsn := c.Database.User + ":" + c.Database.Password + "@tcp(" + c.Database.Host + ":" + c.Database.Port + ")/" + c.Database.DBName + "?parseTime=true&loc=Local"
	db := sqlx.NewMysql(dsn, c.Database.MaxOpenConns)

	// 单机Redis
	rds := redis.New(c.Redis.Host+":"+c.Redis.Port, c.Redis.Password)

	// Redis集群支持
	var redisCluster *redisCluster.Client
	if c.RedisCluster.Enabled {
		redisCluster = redisCluster.New(c.RedisCluster.Nodes, redisCluster.Options{
			Password:   c.RedisCluster.Password,
			PoolSize:   c.RedisCluster.PoolSize,
			MinIdleConns: c.RedisCluster.MinIdleConns,
		})
	}

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
			// 启动服务监控
			go serviceDiscovery.RefreshServices()
		}
	}

	// 分布式锁
	var distributedLocker *client.DistributedLocker
	if redisCluster != nil {
		distributedLocker = client.NewDistributedLocker(redisCluster)
	}

	rabbitMQ := NewRabbitMQClient(c.RabbitMQ)

	return &ServiceContext{
		Config:            c,
		DB:                db,
		Redis:             rds,
		RedisCluster:      redisCluster,
		RabbitMQ:          rabbitMQ,
		FinalCutRepository: repository.NewFinalCutRepository(db),
		ScriptService:     client.NewScriptServiceClient(c),
		VideoService:      client.NewVideoServiceClient(c),
		StorageClient:     storageClient,
		ServiceDiscovery:  serviceDiscovery,
		DistributedLocker: distributedLocker,
	}
}
