package handler

import (
	"net/http"

	"short-drama-platform/content-service/internal/svc"
	"short-drama-platform/content-service/internal/types"

	"github.com/zeromicro/go-zero/rest/httpx"
)

// SavePipelineStateHandler 保存管道状态
func SavePipelineStateHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.SavePipelineStateRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		resp, err := svcCtx.ContentService.SavePipelineState(r.Context(), &req)
		if err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
		} else {
			httpx.OkJsonCtx(r.Context(), w, resp)
		}
	}
}

// GetPipelineStateHandler 获取管道状态
func GetPipelineStateHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.GetPipelineStateRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		resp, err := svcCtx.ContentService.GetPipelineState(r.Context(), &req)
		if err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
		} else {
			httpx.OkJsonCtx(r.Context(), w, resp)
		}
	}
}

// SavePipelineStepHandler 保存单个 pipeline step（原子写入 Redis hash）
func SavePipelineStepHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.SavePipelineStepRequest
		if err := types.ParseSavePipelineStepBody(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		resp, err := svcCtx.ContentService.SavePipelineStep(r.Context(), &req)
		if err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
		} else {
			httpx.OkJsonCtx(r.Context(), w, resp)
		}
	}
}

// GetPipelineStepHandler 获取单个 pipeline step（Redis hash 优先，MySQL fallback）
func GetPipelineStepHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.GetPipelineStepRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}
		resp, err := svcCtx.ContentService.GetPipelineStep(r.Context(), &req)
		if err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
		} else {
			httpx.OkJsonCtx(r.Context(), w, resp)
		}
	}
}
