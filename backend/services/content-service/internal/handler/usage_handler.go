package handler

import (
	"encoding/json"
	"net/http"
	"short-drama-platform/content-service/internal/svc"
	"short-drama-platform/content-service/internal/types"
)

func RecordUsageHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var req types.RecordUsageRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid request body", http.StatusBadRequest)
			return
		}
		if err := svcCtx.ContentService.RecordUsage(r.Context(), &req); err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
	}
}

func GetUsageSummaryHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := r.URL.Query().Get("userId")
		period := r.URL.Query().Get("period")
		if period == "" {
			period = "month"
		}
		resp, err := svcCtx.ContentService.GetUsageSummary(r.Context(), &types.GetUsageSummaryRequest{
			UserID: userID,
			Period: period,
		})
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}
}

func GetUsageHistoryHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		userID := r.URL.Query().Get("userId")
		resp, err := svcCtx.ContentService.GetUsageHistory(r.Context(), &types.GetUsageHistoryRequest{
			UserID: userID,
			Limit:  20,
		})
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(resp)
	}
}
