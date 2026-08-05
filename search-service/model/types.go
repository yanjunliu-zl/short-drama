package model

// SearchRequest 搜索请求
type SearchRequest struct {
	Query    string `form:"q"`
	UserID   string `form:"user_id"`
	Page     int    `form:"page"`
	PageSize int    `form:"page_size"`
}

// SearchResponse 搜索响应
type SearchResponse struct {
	Code    int          `json:"code"`
	Message string       `json:"message"`
	Data    *SearchData  `json:"data,omitempty"`
}

// SearchData 搜索数据
type SearchData struct {
	Results      []*SearchResult `json:"results"`
	Total        int             `json:"total"`
	CorrectedQuery string        `json:"corrected_query,omitempty"`
	Synonyms     []string        `json:"synonyms_used,omitempty"`
}

// SearchResult 搜索结果
type SearchResult struct {
	ID          string   `json:"id"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
	CoverURL    string   `json:"cover_url"`
	Genre       string   `json:"genre"`
	Tags        []string `json:"tags"`
	Author      string   `json:"author"`
	Score       float64  `json:"score"`
}

// SuggestionResponse 搜索建议
type SuggestionResponse struct {
	Suggestions []string `json:"suggestions"`
}

// ClickRequest 点击记录
type ClickRequest struct {
	Query    string `json:"query"`
	ItemID   string `json:"item_id"`
	Position int    `json:"position"`
	UserID   string `json:"user_id"`
}

// FunnelData 漏斗数据
type FunnelData struct {
	Query      string  `json:"query"`
	Impressions int   `json:"impressions"`
	Clicks     int    `json:"clicks"`
	CTR        float64 `json:"ctr"`
}
