package main

import (
	"flag"
	"fmt"

	"short-drama-platform/payment-service/internal/config"
	"short-drama-platform/payment-service/internal/handler"
	"short-drama-platform/payment-service/internal/svc"

	"github.com/zeromicro/go-zero/core/conf"
	"github.com/zeromicro/go-zero/rest"
)

var configFile = flag.String("f", "etc/payment.yaml", "the config file")

func main() {
	flag.Parse()

	var c config.Config
	conf.MustLoad(*configFile, &c)

	// 创建服务上下文
	ctx := svc.NewServiceContext(c)

	// 创建HTTP服务
	server := rest.MustNewServer(c.RestConf)
	defer server.Stop()

	// 注册路由
	handler.RegisterHandlers(server, ctx)

	// 启动服务
	fmt.Printf("Starting payment service at %s:%d...\n", c.Host, c.Port)
	fmt.Println("Supported payment methods: wechat, alipay")
	server.Start()
}
