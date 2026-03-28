package handler

import (
	"net/http"
	"short-drama-platform/final-cut-service/internal/logic"
	"short-drama-platform/final-cut-service/internal/svc"
	"short-drama-platform/final-cut-service/internal/types"

	"github.com/zeromicro/go-zero/core/jsonx"
	"github.com/zeromicro/go-zero/rest"
)

func RegisterHandlers(server *rest.Server, serverCtx *svc.ServiceContext) {
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

// CreateFinalCutHandler 创建最终剪辑任务
func CreateFinalCutHandler(serverCtx *svc.ServiceContext) rest.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.FinalCutRequest
		if err := rest.GetJson(r, &req); err != nil {
			rest.RenderJson(w, rest.ErrJSONParse(err))
			return
		}

		l := logic.NewFinalCutLogic(serverCtx)
		resp, err := l.CreateFinalCut(r.Context(), &req)
		if err != nil {
			rest.RenderJson(w, rest.ErrServer(err))
			return
		}

		rest.RenderJson(w, resp)
	}
}

// GetStatusHandler 获取剪辑任务状态
func GetStatusHandler(serverCtx *svc.ServiceContext) rest.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		taskID := r.URL.Query().Get("task_id")
		if taskID == "" {
			pathVars := rest.PathVariables(r)
			taskID = pathVars["task_id"]
		}

		req := &types.GetFinalCutStatusRequest{
			TaskID: taskID,
		}

		l := logic.NewFinalCutLogic(serverCtx)
		resp, err := l.GetStatus(r.Context(), req)
		if err != nil {
			rest.RenderJson(w, rest.ErrServer(err))
			return
		}

		rest.RenderJson(w, resp)
	}
}

// ListTasksHandler 列出剪辑任务
func ListTasksHandler(serverCtx *svc.ServiceContext) rest.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.FinalCutListRequest
		if err := rest.GetForm(r, &req); err != nil {
			rest.RenderJson(w, rest.ErrJSONParse(err))
			return
		}

		l := logic.NewFinalCutLogic(serverCtx)
		resp, err := l.ListTasks(r.Context(), &req)
		if err != nil {
			rest.RenderJson(w, rest.ErrServer(err))
			return
		}

		rest.RenderJson(w, resp)
	}
}

// CancelTaskHandler 取消剪辑任务
func CancelTaskHandler(serverCtx *svc.ServiceContext) rest.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			rest.RenderJson(w, rest.ErrMethodNotAllowed)
			return
		}

		var req types.CancelFinalCutRequest
		if err := jsonx.Unmarshal(r.Body, &req); err != nil {
			rest.RenderJson(w, rest.ErrJSONParse(err))
			return
		}

		l := logic.NewFinalCutLogic(serverCtx)
		resp, err := l.CancelTask(r.Context(), &req)
		if err != nil {
			rest.RenderJson(w, rest.ErrServer(err))
			return
		}

		rest.RenderJson(w, resp)
	}
}
