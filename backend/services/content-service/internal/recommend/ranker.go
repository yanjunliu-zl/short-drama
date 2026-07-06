package recommend

import (
	"context"
	"math"
	"sort"
	"strings"

	"short-drama-platform/content-service/model"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// ============== Filter Layer ==============

// Filter 过滤层 — 去重、已看、黑名单
type Filter struct {
	db sqlx.SqlConn
}

func NewFilter(db sqlx.SqlConn) *Filter {
	return &Filter{db: db}
}

func (f *Filter) Apply(ctx context.Context, userID string, candidates []*RecallResult) []*RecallResult {
	if len(candidates) == 0 {
		return candidates
	}

	// 获取用户已看案例
	viewed := f.getViewedCases(ctx, userID)

	var filtered []*RecallResult
	seen := make(map[string]bool)
	for _, c := range candidates {
		if viewed[c.Case.ID] {
			continue // 过滤已看
		}
		if seen[c.Case.ID] {
			continue // 去重
		}
		seen[c.Case.ID] = true
		filtered = append(filtered, c)
	}
	return filtered
}

func (f *Filter) getViewedCases(ctx context.Context, userID string) map[string]bool {
	if userID == "" {
		return map[string]bool{}
	}
	sql := `SELECT DISTINCT case_id FROM user_case_interactions WHERE user_id = ?`
	var ids []string
	f.db.QueryRowsCtx(ctx, &ids, sql, userID)

	viewed := make(map[string]bool, len(ids))
	for _, id := range ids {
		viewed[id] = true
	}
	return viewed
}

// ============== Feature Extraction (for PyTorch ranking) ==============

// RankingFeatures 排序特征 — 喂给 PyTorch Wide&Deep 模型
type RankingFeatures struct {
	// 用户侧特征
	UserViewCount  int     `json:"user_view_count"`
	UserLikeCount  int     `json:"user_like_count"`
	UserTagDiversity int   `json:"user_tag_diversity"`

	// 物品侧特征
	ItemViewCount  int64   `json:"item_view_count"`
	ItemLikeCount  int64   `json:"item_like_count"`
	ItemShareCount int64   `json:"item_share_count"`
	ItemAgeDays    float64 `json:"item_age_days"`

	// 交叉特征
	TagMatchCount       int     `json:"tag_match_count"`
	GenreMatch          float64 `json:"genre_match"`
	AuthorMatch         float64 `json:"author_match"`
	SameSourceRecall    float64 `json:"same_source_recall"`

	// 上下文特征
	RecallSource string  `json:"recall_source"`
	RecallScore  float64 `json:"recall_score"`
	HourOfDay    int     `json:"hour_of_day"`
}

// ExtractFeatures 提取所有特征 — 给 PyTorch 模型打分
func ExtractFeatures(userProfile *UserProfile, item *model.Case, rr *RecallResult) *RankingFeatures {
	return &RankingFeatures{
		UserViewCount:    userProfile.ViewCount,
		UserLikeCount:    userProfile.LikeCount,
		UserTagDiversity: userProfile.TagDiversity,
		ItemViewCount:    item.ViewCount,
		ItemLikeCount:    item.LikeCount,
		ItemShareCount:   item.ShareCount,
		ItemAgeDays:      userProfile.ItemAgeDaysFunc(item),
		TagMatchCount:    userProfile.TagMatchCountFunc(item),
		GenreMatch:       userProfile.GenreMatchFunc(item),
		AuthorMatch:      userProfile.AuthorMatchFunc(item),
		SameSourceRecall: userProfile.SameSourceRecallFunc(rr),
		RecallSource:     rr.Source,
		RecallScore:      rr.Score,
		HourOfDay:        userProfile.HourOfDayFunc(),
	}
}

// UserProfile 用户画像,用于特征提取
type UserProfile struct {
	ViewCount    int
	LikeCount    int
	TagDiversity int
	TopTags      []string
	TopGenres    []string
	TopAuthors   []string
}

func (u *UserProfile) ItemAgeDaysFunc(item *model.Case) float64 {
	return item.CreatedAt.Sub(item.CreatedAt).Hours() / 24
}

func (u *UserProfile) TagMatchCountFunc(item *model.Case) int {
	count := 0
	for _, tt := range u.TopTags {
		if containsTag(item.Tags, tt) {
			count++
		}
	}
	return count
}

func (u *UserProfile) GenreMatchFunc(item *model.Case) float64 {
	for _, g := range u.TopGenres {
		if item.Genre == g {
			return 1.0
		}
	}
	return 0.0
}

func (u *UserProfile) AuthorMatchFunc(item *model.Case) float64 {
	for _, a := range u.TopAuthors {
		if item.Author == a {
			return 1.0
		}
	}
	return 0.0
}

func (u *UserProfile) SameSourceRecallFunc(rr *RecallResult) float64 {
	return 1.0 // placeholder
}

func (u *UserProfile) HourOfDayFunc() int {
	return 0 // placeholder, real impl uses time.Now().Hour()
}

// ============== MMR Rerank Layer ==============

// MMR 最大边界相关性重排 — 兼顾相关性和多样性
func MMRRerank(candidates []*RankedItem, lambda float64, topN int) []*RankedItem {
	if len(candidates) <= topN {
		return candidates
	}
	if lambda == 0 {
		lambda = 0.7 // 默认 70% 相关性, 30% 多样性
	}

	selected := make([]*RankedItem, 0, topN)
	pool := make([]*RankedItem, len(candidates))
	copy(pool, candidates)

	for len(selected) < topN && len(pool) > 0 {
		bestIdx := 0
		bestScore := math.Inf(-1)

		for i, item := range pool {
			// 相关性分
			relevance := item.Score

			// 多样性惩罚: 与已选物品的最大相似度
			maxSim := 0.0
			for _, sel := range selected {
				sim := tagSimilarity(item.Case, sel.Case)
				if sim > maxSim {
					maxSim = sim
				}
			}

			// MMR = λ * relevance - (1-λ) * max_similarity
			mmrScore := lambda*relevance - (1-lambda)*maxSim
			if mmrScore > bestScore {
				bestScore = mmrScore
				bestIdx = i
			}
		}

		selected = append(selected, pool[bestIdx])
		pool = append(pool[:bestIdx], pool[bestIdx+1:]...)
	}

	return selected
}

// RankedItem 排序后的物品
type RankedItem struct {
	Case  *model.Case
	Score float64 // CTR预估分 (0~1)
}

// tagSimilarity Jaccard 标签相似度
func tagSimilarity(a, b *model.Case) float64 {
	tagsA := splitTags(a.Tags)
	tagsB := splitTags(b.Tags)
	if len(tagsA) == 0 && len(tagsB) == 0 {
		return 0
	}

	intersection := 0
	setB := make(map[string]bool, len(tagsB))
	for _, t := range tagsB {
		setB[t] = true
	}
	for _, t := range tagsA {
		if setB[t] {
			intersection++
		}
	}
	union := len(tagsA) + len(tagsB) - intersection
	if union == 0 {
		return 0
	}
	return float64(intersection) / float64(union)
}

func splitTags(tagsStr string) []string {
	var result []string
	for _, t := range strings.Split(tagsStr, ",") {
		t = strings.TrimSpace(t)
		if t != "" {
			result = append(result, t)
		}
	}
	return result
}

// ============== Pipeline Orchestrator ==============

// Pipeline 四层推荐流水线
type Pipeline struct {
	recaller       *Recaller
	filter         *Filter
	pytorchClient  *PyTorchRankingClient
}

func NewPipeline(db sqlx.SqlConn, pytorchURL string) *Pipeline {
	return &Pipeline{
		recaller:      NewRecaller(db),
		filter:        NewFilter(db),
		pytorchClient: NewPyTorchRankingClient(pytorchURL),
	}
}

// Run 执行完整推荐流水线
// 1. 多路召回 → 2. 过滤 → 3. 特征提取 → 4. (外部PyTorch排序) → 5. MMR重排
func (p *Pipeline) Run(ctx context.Context, userID string, searchQuery string, userProfile *UserProfile, limit int) ([]*RankedItem, error) {
	// Step 1: 召回
	candidates, err := p.recaller.MultiPathRecall(ctx, userID, searchQuery)
	if err != nil {
		return nil, err
	}

	// Step 2: 过滤
	candidates = p.filter.Apply(ctx, userID, candidates)

	// Step 3: 特征提取 (每个候选提取特征, 准备给 PyTorch)
	featuresList := make([]*RankingFeatures, len(candidates))
	for i, rr := range candidates {
		featuresList[i] = ExtractFeatures(userProfile, rr.Case, rr)
	}
	_ = featuresList // passed to PyTorch ranking API externally

	// Step 4: CTR 预估排序
	// 优先使用 PyTorch Wide&Deep; 不可用时降级为加权公式
	var ctrScores []float64
	if p.pytorchClient != nil && p.pytorchClient.IsAvailable(ctx) {
		scores, err := p.pytorchClient.Rank(ctx, featuresList)
		if err == nil && len(scores) == len(candidates) {
			ctrScores = scores
		}
	}

	ranked := make([]*RankedItem, len(candidates))
	for i, rr := range candidates {
		if i < len(ctrScores) && ctrScores[i] > 0 {
			ranked[i] = &RankedItem{Case: rr.Case, Score: ctrScores[i]}
		} else {
			// 降级: 加权 CTR 公式
			ctr := 0.0
			ctr += float64(rr.Case.LikeCount) * 0.3 / 10000
			ctr += float64(rr.Case.ViewCount) * 0.1 / 100000
			ctr += float64(featuresList[i].TagMatchCount) * 0.2 / 5
			ctr += featuresList[i].GenreMatch * 0.2
			ctr += rr.Score * 0.2
			ctr = math.Min(ctr, 1.0)
			ranked[i] = &RankedItem{Case: rr.Case, Score: ctr}
		}
	}

	sort.Slice(ranked, func(i, j int) bool {
		return ranked[i].Score > ranked[j].Score
	})

	// Step 5: MMR 多样性重排
	ranked = MMRRerank(ranked, 0.7, limit)

	return ranked, nil
}

var _ = sort.Ints // avoid unused import issues
var _ = strings.Split
var _ = context.Background
