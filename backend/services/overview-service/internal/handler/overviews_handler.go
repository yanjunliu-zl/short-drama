package handler

import (
	"encoding/json"
	"net/http"
	"short-drama-platform/overview-service/internal/logic"
	"short-drama-platform/overview-service/internal/types"

	"github.com/zeromicro/go-zero/rest/httpx"
)

func GetOverviewHandler(ctx *logic.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.OverviewRequest
		if err := httpx.Parse(r, &req); err != nil {
			httpx.WriteJson(w, http.StatusBadRequest, types.OverviewResponse{
				UserID:         0,
				VideoRatios:    nil,
				CreationModes:  nil,
				StyleReferences: nil,
				TotalVideos:    0,
				TotalDuration:  0,
				LastUpdated:    "",
			})
			return
		}

		l := logic.NewOverviewLogic(r.Context(), ctx)
		resp, err := l.GetOverview(&req)
		if err != nil {
			httpx.WriteJson(w, http.StatusInternalServerError, map[string]string{
				"error": err.Error(),
			})
			return
		}

		httpx.WriteJson(w, http.StatusOK, resp)
	}
}

func SetOverviewConfigHandler(ctx *logic.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.SetOverviewConfigRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			httpx.WriteJson(w, http.StatusBadRequest, map[string]string{
				"error": "invalid request body",
			})
			return
		}

		l := logic.NewOverviewLogic(r.Context(), ctx)
		resp, err := l.SetOverviewConfig(&req)
		if err != nil {
			httpx.WriteJson(w, http.StatusInternalServerError, map[string]string{
				"error": err.Error(),
			})
			return
		}

		httpx.WriteJson(w, http.StatusOK, resp)
	}
}
