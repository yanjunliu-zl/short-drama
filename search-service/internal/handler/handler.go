package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"

	"short-drama-platform/search-service/internal/logic"
	"short-drama-platform/search-service/model"
)

type Handler struct {
	engine      *logic.QueryEngine
	contentURL  string
	httpClient  *http.Client
}

func NewHandler(engine *logic.QueryEngine, contentURL string) *Handler {
	return &Handler{
		engine:     engine,
		contentURL: contentURL,
		httpClient: &http.Client{},
	}
}

// Search GET /api/v1/search
func (h *Handler) Search(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	if q == "" {
		writeJSON(w, 400, &model.SearchResponse{Code: 1, Message: "query required"})
		return
	}
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	if page <= 0 { page = 1 }
	if pageSize <= 0 { pageSize = 20 }

	// Query understanding
	corrected := h.engine.Correct(q)
	expanded := h.engine.Expand(corrected)

	// Fetch from content-service search
	results := h.fetchFromContentService(r.Context(), strings.Join(expanded, " "), page, pageSize)

	// Record
	go h.engine.RecordQuery(context.Background(), q)
	go h.engine.SetImpression(context.Background(), q, len(results))

	resp := &model.SearchResponse{
		Code:    0,
		Message: "ok",
		Data: &model.SearchData{
			Results:        results,
			Total:          len(results),
			CorrectedQuery: corrected,
			Synonyms:       expanded[1:], // expanded queries (excluding original)
		},
	}
	if q != corrected { resp.Data.CorrectedQuery = corrected }

	writeJSON(w, 200, resp)
}

func (h *Handler) fetchFromContentService(ctx context.Context, query string, page, pageSize int) []*model.SearchResult {
	u := fmt.Sprintf("%s/api/v1/cases/search?q=%s&page=%d&pageSize=%d",
		h.contentURL, url.QueryEscape(query), page, pageSize)

	req, err := http.NewRequestWithContext(ctx, "GET", u, nil)
	if err != nil { return nil }

	resp, err := h.httpClient.Do(req)
	if err != nil { return nil }
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var searchResp struct {
		Hits []struct {
			ID          string  `json:"id"`
			Title       string  `json:"title"`
			Description string  `json:"description"`
			CoverURL    string  `json:"cover_url"`
			Genre       string  `json:"genre"`
			Tags        string  `json:"tags"`
			Author      string  `json:"author"`
			Score       float64 `json:"_score"`
		} `json:"hits"`
	}
	json.Unmarshal(body, &searchResp)

	var results []*model.SearchResult
	for _, hit := range searchResp.Hits {
		results = append(results, &model.SearchResult{
			ID: hit.ID, Title: hit.Title, Description: hit.Description,
			CoverURL: hit.CoverURL, Genre: hit.Genre,
			Tags: strings.Split(hit.Tags, ","),
			Author: hit.Author, Score: hit.Score,
		})
	}
	return results
}

// Suggestions GET /api/v1/search/suggestions
func (h *Handler) Suggestions(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	typ := r.URL.Query().Get("type")

	var items []string
	if typ == "trending" {
		items = h.engine.Trending(r.Context(), 10)
	} else {
		items = h.engine.Autocomplete(r.Context(), q, 5)
	}
	writeJSON(w, 200, &model.SuggestionResponse{Suggestions: items})
}

// Click POST /api/v1/search/click
func (h *Handler) Click(w http.ResponseWriter, r *http.Request) {
	var req model.ClickRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, 400, map[string]string{"error": "invalid"})
		return
	}
	h.engine.RecordClick(r.Context(), req.Query, req.ItemID, req.Position, req.UserID)
	log.Printf("[Search] click: q='%s' item=%s pos=%d", req.Query, req.ItemID, req.Position)
	writeJSON(w, 200, map[string]string{"status": "ok"})
}

// Funnel GET /api/v1/search/funnel
func (h *Handler) Funnel(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("query")
	data := h.engine.GetFunnel(r.Context(), q)
	writeJSON(w, 200, data)
}

// Health GET /health
func (h *Handler) Health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, 200, map[string]string{"status": "healthy", "service": "search-service"})
}

func writeJSON(w http.ResponseWriter, code int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(v)
}
