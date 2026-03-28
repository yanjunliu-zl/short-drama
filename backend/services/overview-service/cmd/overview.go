package main

import (
	"flag"
	"fmt"
	"net/http"

	"short-drama-platform/overview-service/internal/config"
	"short-drama-platform/overview-service/internal/handler"
	"short-drama-platform/overview-service/internal/svc"

	"github.com/zeromicro/go-zero/core/conf"
	"github.com/zeromicro/go-zero/rest"
)

var configFile = flag.String("f", "etc/overview.yaml", "the config file")

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

	// 注册健康检查
	server.AddRoute(rest.Route{
		Method:  "GET",
		Path:    "/health",
		Handler: healthHandler,
	})

	// 启动服务
	fmt.Printf("Starting overview service at %s:%d...\n", c.Host, c.Port)
	server.Start()
}

func healthHandler(w rest.ResponseWriter, r *rest.Request) {
	w.WriteHeader(http.StatusOK)
	w.WriteJson(map[string]string{"status": "ok"})
}
