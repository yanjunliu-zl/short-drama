package handler

import (
	"net/http"
	"short-drama-platform/asset-service/internal/svc"

	"github.com/zeromicro/go-zero/rest"
)

func RegisterHandlers(server *rest.Server, serverCtx *svc.ServiceContext) {
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/assets/personal",
				Handler: ListPersonalAssetsHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/assets/personal",
				Handler: CreatePersonalAssetHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/assets/company",
				Handler: ListCompanyAssetsHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/assets/company",
				Handler: CreateCompanyAssetHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/assets/:id",
				Handler: GetAssetHandler(serverCtx),
			},
			{
				Method:  http.MethodPut,
				Path:    "/api/v1/assets/:id",
				Handler: UpdateAssetHandler(serverCtx),
			},
			{
				Method:  http.MethodDelete,
				Path:    "/api/v1/assets/:id",
				Handler: DeleteAssetHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/assets/:id/use",
				Handler: UseAssetHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/assets/:id/share",
				Handler: ShareAssetHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/health",
				Handler: HealthCheckHandler(serverCtx),
			},
		},
	)
}