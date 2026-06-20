package svc

import (
	"fmt"
	"short-drama-platform/payment-service/internal/config"
	"short-drama-platform/payment-service/internal/logic"
	"short-drama-platform/payment-service/internal/provider"
	"short-drama-platform/payment-service/internal/repository"
	"short-drama-platform/payment-service/internal/types"
	"time"

	"github.com/zeromicro/go-zero/core/stores/redis"
	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// ServiceContext 服务上下文，依赖注入容器
type ServiceContext struct {
	Config         config.Config
	PaymentRepo    repository.PaymentRepository
	PaymentService types.PaymentService
	Redis          *redis.Redis

	// 支付渠道提供者
	WeChatPayProvider provider.PaymentProvider
	AlipayProvider    provider.PaymentProvider
}

// NewServiceContext 创建服务上下文
func NewServiceContext(c config.Config) *ServiceContext {
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

	// 初始化数据库连接
	dsn := fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?charset=utf8mb4&parseTime=True&loc=Local",
		c.Database.User, c.Database.Password, c.Database.Host, c.Database.Port, c.Database.DBName)
	conn := sqlx.NewMysql(dsn)

	// 初始化仓库
	paymentRepo := repository.NewPaymentRepository(conn)

	// 初始化支付渠道提供者
	wechatPayProvider, err := provider.NewWeChatPayProvider(c.WeChatPay)
	if err != nil {
		panic(fmt.Sprintf("failed to init WeChat Pay provider: %v", err))
	}

	alipayProvider, err := provider.NewAlipayProvider(c.Alipay)
	if err != nil {
		panic(fmt.Sprintf("failed to init Alipay provider: %v", err))
	}

	// 初始化支付服务
	paymentService := logic.NewPaymentLogic(paymentRepo, redisClient, wechatPayProvider, alipayProvider)

	return &ServiceContext{
		Config:            c,
		PaymentRepo:       paymentRepo,
		PaymentService:    paymentService,
		Redis:             redisClient,
		WeChatPayProvider: wechatPayProvider,
		AlipayProvider:    alipayProvider,
	}
}
