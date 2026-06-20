package handler

import (
	"net/http"
	"short-drama-platform/content-service/internal/svc"
	"short-drama-platform/content-service/internal/types"

	"github.com/zeromicro/go-zero/rest/httpx"
)

func ListPaymentsHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.ListPaymentsRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
			return
		}

		resp, err := svcCtx.ContentService.ListPayments(r.Context(), &req)
		if err != nil {
			httpx.ErrorCtx(r.Context(), w, err)
		} else {
			httpx.OkJsonCtx(r.Context(), w, resp)
		}
	}
}
