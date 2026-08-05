package handler

import (
	"encoding/json"
	"log"
	"net/http"
	"strconv"

	"short-drama-platform/recommendation-service/internal/logic"
	"short-drama-platform/recommendation-service/model"
)

type Handler struct {
	pipeline *logic.Pipeline
	bandit   *logic.BanditService
}

func NewHandler(pipeline *logic.Pipeline, bandit *logic.BanditService) *Handler {
	return &Handler{pipeline: pipeline, bandit: bandit}
}

// Recommend GET /api/v1/recommendations/recommend
func (h *Handler) Recommend(w http.ResponseWriter, r *http.Request) {
	userID := r.URL.Query().Get("user_id")
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 { limit = 20 }

	data := h.pipeline.Run(r.Context(), userID, limit)

	writeJSON(w, 200, &model.RecommendResponse{
		Code:    0,
		Message: "ok",
		Data:    data,
	})
}

// Feedback POST /api/v1/recommendations/feedback
func (h *Handler) Feedback(w http.ResponseWriter, r *http.Request) {
	var req model.FeedbackRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid request"})
		return
	}

	h.bandit.Update(r.Context(), req.UserID, req.Source, req.Action, nil)
	log.Printf("[Feedback] user=%s item=%s action=%s source=%s", req.UserID, req.ItemID, req.Action, req.Source)

	writeJSON(w, 200, map[string]string{"status": "ok"})
}

// Health GET /health
func (h *Handler) Health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, 200, map[string]string{"status": "healthy", "service": "recommendation-service"})
}

func writeJSON(w http.ResponseWriter, code int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}
