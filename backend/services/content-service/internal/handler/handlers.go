package handler

import (
	"net/http"
	"short-drama-platform/content-service/internal/svc"

	"github.com/zeromicro/go-zero/rest"
)

func RegisterHandlers(server *rest.Server, serverCtx *svc.ServiceContext) {
	// 场景管理路由
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/scenes",
				Handler: CreateSceneHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/scenes",
				Handler: ListScenesHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/scenes/:id",
				Handler: GetSceneHandler(serverCtx),
			},
			{
				Method:  http.MethodPut,
				Path:    "/api/v1/scenes/:id",
				Handler: UpdateSceneHandler(serverCtx),
			},
			{
				Method:  http.MethodDelete,
				Path:    "/api/v1/scenes/:id",
				Handler: DeleteSceneHandler(serverCtx),
			},
		},
	)

	// 角色管理路由
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/characters",
				Handler: CreateCharacterHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/characters",
				Handler: ListCharactersHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/characters/:id",
				Handler: GetCharacterHandler(serverCtx),
			},
			{
				Method:  http.MethodPut,
				Path:    "/api/v1/characters/:id",
				Handler: UpdateCharacterHandler(serverCtx),
			},
			{
				Method:  http.MethodDelete,
				Path:    "/api/v1/characters/:id",
				Handler: DeleteCharacterHandler(serverCtx),
			},
		},
	)

	// 剧本大纲路由
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/script-outline",
				Handler: GetScriptOutlineHandler(serverCtx),
			},
			{
				Method:  http.MethodPut,
				Path:    "/api/v1/script-outline",
				Handler: UpdateScriptOutlineHandler(serverCtx),
			},
		},
	)

	// 案例广场路由 (根据API_IMPLEMENTATION.md)
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/cases",
				Handler: ListCasesHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/cases/:id",
				Handler: GetCaseHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/cases",
				Handler: CreateCaseHandler(serverCtx),
			},
			{
				Method:  http.MethodPut,
				Path:    "/api/v1/cases/:id",
				Handler: UpdateCaseHandler(serverCtx),
			},
			{
				Method:  http.MethodDelete,
				Path:    "/api/v1/cases/:id",
				Handler: DeleteCaseHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/cases/:id/view",
				Handler: RecordCaseViewHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/cases/:id/like",
				Handler: RecordCaseLikeHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/cases/:id/share",
				Handler: RecordCaseShareHandler(serverCtx),
			},
		},
	)

	// 我的作品路由
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/works",
				Handler: ListWorksHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/works/:id",
				Handler: GetWorkHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/works",
				Handler: CreateWorkHandler(serverCtx),
			},
			{
				Method:  http.MethodPut,
				Path:    "/api/v1/works/:id",
				Handler: UpdateWorkHandler(serverCtx),
			},
			{
				Method:  http.MethodPut,
				Path:    "/api/v1/works/:id/progress",
				Handler: UpdateWorkProgressHandler(serverCtx),
			},
			{
				Method:  http.MethodDelete,
				Path:    "/api/v1/works/:id",
				Handler: DeleteWorkHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/works/:id/export",
				Handler: ExportWorkHandler(serverCtx),
				},
				{
					Method:  http.MethodPut,
					Path:    "/api/v1/works/:id/pipeline-state",
					Handler: SavePipelineStateHandler(serverCtx),
				},
				{
					Method:  http.MethodGet,
					Path:    "/api/v1/works/:id/pipeline-state",
					Handler: GetPipelineStateHandler(serverCtx),
			},
		},
	)

	// 支付路由
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/payments",
				Handler: ListPaymentsHandler(serverCtx),
			},
		},
	)

	// 资产库路由
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/assets/personal",
				Handler: ListPersonalAssetsHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/assets/company",
				Handler: ListCompanyAssetsHandler(serverCtx),
			},
		},
	)
}