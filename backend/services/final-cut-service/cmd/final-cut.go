package main

import (
	"flag"
	"fmt"
	"net/http"

	"short-drama-platform/final-cut-service/internal/config"
	grpcsvr "short-drama-platform/final-cut-service/internal/grpc"
	"short-drama-platform/final-cut-service/internal/handler"
	"short-drama-platform/final-cut-service/internal/svc"

	"github.com/zeromicro/go-zero/core/conf"
	"github.com/zeromicro/go-zero/rest"
)

var configFile = flag.String("f", "etc/final-cut.yaml", "the config file")

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
		Method:  http.MethodGet,
		Path:    "/health",
		Handler: healthHandler,
	})

	// P2: Start gRPC server on dedicated port alongside REST server
	grpcPort := 19085 // Dedicated gRPC port (avoiding Prometheus on 9085)
	grpcServer := grpcsvr.NewServer(ctx, grpcPort)
	go func() {
		if err := grpcServer.Start(); err != nil {
			fmt.Printf("gRPC server error: %v\n", err)
		}
	}()
	defer grpcServer.Stop()

	// 启动 REST 服务
	fmt.Printf("Starting REST server at %s:%d, gRPC at :%d...\n", c.Host, c.Port, grpcPort)
	server.Start()
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status": "ok"}`))
}
