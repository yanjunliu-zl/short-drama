package handler

import (
	"net/http"
	"short-drama-platform/video-service/internal/svc"

	"github.com/zeromicro/go-zero/rest"
)

func RegisterHandlers(server *rest.Server, serverCtx *svc.ServiceContext) {
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/videos",
				Handler: ListVideosHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/videos",
				Handler: CreateVideoHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/videos/:id",
				Handler: GetVideoHandler(serverCtx),
			},
			{
				Method:  http.MethodPut,
				Path:    "/api/v1/videos/:id",
				Handler: UpdateVideoHandler(serverCtx),
			},
			{
				Method:  http.MethodDelete,
				Path:    "/api/v1/videos/:id",
				Handler: DeleteVideoHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/videos/:id/process",
				Handler: ProcessVideoHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/videos/:id/progress",
				Handler: GetProcessingProgressHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/health",
				Handler: HealthCheckHandler(serverCtx),
			},
		},
	)
}