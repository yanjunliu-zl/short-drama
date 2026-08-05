package svc

import (
	"fmt"
	"short-drama-platform/final-cut-service/internal/client"
	"short-drama-platform/final-cut-service/internal/config"
	"short-drama-platform/final-cut-service/internal/repository"
	dbshared "short-drama-platform/shared/db"

	goredis "github.com/go-redis/redis/v8"
	"github.com/zeromicro/go-zero/core/logx"
	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

type ServiceContext struct {
	Config             config.Config
	DB                 sqlx.SqlConn
	DBResolver         *dbshared.DBResolver // Read/write splitting resolver (P1)
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

	// P1: Read/write splitting via DBResolver
	// Reader DSNs from config; falls back to writer if no readers configured
	var dbResolver *dbshared.DBResolver
	if len(c.Database.ReadHosts) > 0 {
		var readerDSNs []string
		for _, rh := range c.Database.ReadHosts {
			readerDSN := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?parseTime=true&loc=Local",
				c.Database.User, c.Database.Password, rh, c.Database.Port, c.Database.DBName)
			readerDSNs = append(readerDSNs, readerDSN)
		}
		dbResolver = dbshared.NewDBResolver(dsn, readerDSNs...)
		logx.Infof("DBResolver enabled with %d read replica(s)", len(readerDSNs))
	} else {
		dbResolver = dbshared.NewDBResolver(dsn) // Falls back to writer-only
	}

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
		DBResolver:         dbResolver,
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
