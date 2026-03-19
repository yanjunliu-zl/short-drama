package handler

import (
	"net/http"
	"short-drama-platform/user-service/internal/svc"

	"github.com/zeromicro/go-zero/rest"
)

func RegisterHandlers(server *rest.Server, serverCtx *svc.ServiceContext) {
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/users/register",
				Handler: RegisterHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/users/login",
				Handler: LoginHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/users/:id",
				Handler: GetUserHandler(serverCtx),
			},
			{
				Method:  http.MethodPut,
				Path:    "/api/v1/users/:id",
				Handler: UpdateUserHandler(serverCtx),
			},
			{
				Method:  http.MethodDelete,
				Path:    "/api/v1/users/:id",
				Handler: DeleteUserHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/users",
				Handler: ListUsersHandler(serverCtx),
			},
		},
	)

	// 用户profile相关路由
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/users/:id/profile",
				Handler: GetUserProfileHandler(serverCtx),
			},
			{
				Method:  http.MethodPut,
				Path:    "/api/v1/users/:id/profile",
				Handler: UpdateUserProfileHandler(serverCtx),
			},
		},
	)
}