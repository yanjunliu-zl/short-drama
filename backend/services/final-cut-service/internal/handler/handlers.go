package handler

import (
	"net/http"

	"short-drama-platform/final-cut-service/internal/logic"
	"short-drama-platform/final-cut-service/internal/svc"
	"short-drama-platform/final-cut-service/internal/types"

	"github.com/zeromicro/go-zero/rest"
	"github.com/zeromicro/go-zero/rest/httpx"
)

func RegisterHandlers(server *rest.Server, serverCtx *svc.ServiceContext) {
	// 最终剪辑路由
	server.AddRoutes(
		[]rest.Route{
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/final-cut",
				Handler: CreateFinalCutHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/final-cut/:task_id",
				Handler: GetStatusHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/final-cut",
				Handler: ListTasksHandler(serverCtx),
			},
			{
				Method:  http.MethodDelete,
				Path:    "/api/v1/final-cut",
				Handler: CancelTaskHandler(serverCtx),
			},
		},
	)
}

func getLogic(svcCtx *svc.ServiceContext) *logic.FinalCutLogic {
	return logic.NewFinalCutLogic(svcCtx)
}

// CreateFinalCutHandler 创建最终剪辑任务
func CreateFinalCutHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.FinalCutRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		resp, err := getLogic(svcCtx).CreateFinalCut(r.Context(), &req)
		if err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
		} else {
			httpx.OkJsonCtx(r.Context(), w, resp)
		}
	}
}

// GetStatusHandler 获取任务状态
func GetStatusHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.GetFinalCutStatusRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		resp, err := getLogic(svcCtx).GetStatus(r.Context(), &req)
		if err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
		} else {
			httpx.OkJsonCtx(r.Context(), w, resp)
		}
	}
}

// ListTasksHandler 列出任务
func ListTasksHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.FinalCutListRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		resp, err := getLogic(svcCtx).ListTasks(r.Context(), &req)
		if err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
		} else {
			httpx.OkJsonCtx(r.Context(), w, resp)
		}
	}
}

// CancelTaskHandler 取消任务
func CancelTaskHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.CancelFinalCutRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		resp, err := getLogic(svcCtx).CancelTask(r.Context(), &req)
		if err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
		} else {
			httpx.OkJsonCtx(r.Context(), w, resp)
		}
	}
}
