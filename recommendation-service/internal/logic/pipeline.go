package logic

import (
	"context"
	"database/sql"
	"log"

	"short-drama-platform/recommendation-service/model"

	"github.com/redis/go-redis/v9"
)

// Pipeline 推荐流水线：召回 → 过滤 → 排序 → Bandit → MMR 重排
type Pipeline struct {
	recaller *Recaller
	ranker   *Ranker
	bandit   *BanditService
	db       *sql.DB
}

func NewPipeline(db *sql.DB, redis *redis.Client) *Pipeline {
	return &Pipeline{
		recaller: NewRecaller(db),
		ranker:   NewRanker(),
		bandit:   NewBanditService(redis),
		db:       db,
	}
}

// Run 执行完整推荐流水线
func (p *Pipeline) Run(ctx context.Context, userID string, limit int) *model.RecommendData {
	if limit <= 0 { limit = 20 }

	// 1. 召回
	candidates := p.recaller.MultiPathRecall(ctx, userID)
	log.Printf("[Pipeline] recall: %d candidates", len(candidates))

	// 2. 过滤
	candidates = p.filter(ctx, userID, candidates)
	log.Printf("[Pipeline] filter: %d after dedup", len(candidates))

	// 3. 用户画像
	profile := p.ranker.BuildProfile(ctx, userID)

	// 4. 排序
	ranked := p.ranker.Rank(candidates, profile)

	// 5. MMR 重排
	ranked = p.ranker.MMRRerank(ranked, 0.7, limit)

	// 6. 组装结果
	items := make([]*model.RecommendItem, len(ranked))
	sources := make(map[string]bool)
	for i, r := range ranked {
		items[i] = &model.RecommendItem{
			Case:   r.Case,
			Score:  r.Score,
			Source: findRecallSource(r.Case.ID, candidates),
		}
	}

	var sourceList []string
	for s := range sources { sourceList = append(sourceList, s) }

	return &model.RecommendData{
		Items:      items,
		Total:      len(items),
		RecallFrom: sourceList,
	}
}

// filter 去重 + 过滤已看
func (p *Pipeline) filter(ctx context.Context, userID string, candidates []*model.RecallResult) []*model.RecallResult {
	if userID == "" || len(candidates) == 0 { return candidates }

	// 获取已看
	rows, err := p.db.QueryContext(ctx,
		`SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = ?`, userID)
	if err != nil { return candidates }
	defer rows.Close()

	viewed := make(map[string]bool)
	var id string
	for rows.Next() { rows.Scan(&id); viewed[id] = true }

	seen := make(map[string]bool)
	var filtered []*model.RecallResult
	for _, c := range candidates {
		if viewed[c.Case.ID] || seen[c.Case.ID] { continue }
		seen[c.Case.ID] = true
		filtered = append(filtered, c)
	}
	return filtered
}

func findRecallSource(caseID string, candidates []*model.RecallResult) string {
	for _, r := range candidates {
		if r.Case.ID == caseID { return r.Source }
	}
	return "unknown"
}
