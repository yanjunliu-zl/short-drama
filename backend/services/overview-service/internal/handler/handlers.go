package handler

import (
	"net/http"
	"short-drama-platform/overview-service/internal/svc"

	"github.com/zeromicro/go-zero/rest"
)

func RegisterHandlers(server *rest.Server, serverCtx *svc.ServiceContext) {
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/overview/:userId",
				Handler: GetOverviewHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/overview/config",
				Handler: SetOverviewConfigHandler(serverCtx),
			},
		},
	)
}
