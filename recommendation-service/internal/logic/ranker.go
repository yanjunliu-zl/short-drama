package logic

import (
	"context"
	"math"
	"sort"
	"strings"
	"time"

	"short-drama-platform/recommendation-service/model"
)

// Ranker 排序 + MMR 重排
type Ranker struct{}

func NewRanker() *Ranker { return &Ranker{} }

// Rank 多目标排序：CTR 预估 + 完成率
func (rk *Ranker) Rank(candidates []*model.RecallResult, profile *model.UserProfile) []*model.RankedItem {
	ranked := make([]*model.RankedItem, len(candidates))
	for i, rr := range candidates {
		c := rr.Case
		ctr := 0.0
		ctr += float64(c.LikeCount) * 0.25 / 10000
		ctr += float64(c.ViewCount) * 0.10 / 100000
		ctr += float64(c.ShareCount) * 0.10 / 1000
		ctr += tagMatchScore(c.Tags, profile.TopTags) * 0.20
		ctr += genreMatch(c.Genre, profile.TopGenres) * 0.15
		ctr += authorMatch(c.Author, profile.TopAuthors) * 0.10
		ctr += itemAgeDecay(c.CreatedAt) * 0.05
		ctr += rr.Score * 0.05
		ranked[i] = &model.RankedItem{Case: c, Score: math.Min(ctr, 1.0)}
	}
	sort.Slice(ranked, func(i, j int) bool { return ranked[i].Score > ranked[j].Score })
	return ranked
}

// MMRRerank 最大边界相关性重排 — λ=0.7
func (rk *Ranker) MMRRerank(candidates []*model.RankedItem, lambda float64, topN int) []*model.RankedItem {
	if len(candidates) <= topN { return candidates }
	if lambda == 0 { lambda = 0.7 }

	selected := make([]*model.RankedItem, 0, topN)
	pool := make([]*model.RankedItem, len(candidates))
	copy(pool, candidates)

	for len(selected) < topN && len(pool) > 0 {
		bestIdx, bestScore := 0, math.Inf(-1)
		for i, item := range pool {
			maxSim := 0.0
			for _, sel := range selected {
				sim := jaccardTags(item.Case.Tags, sel.Case.Tags)
				if sim > maxSim { maxSim = sim }
			}
			mmr := lambda*item.Score - (1-lambda)*maxSim
			if mmr > bestScore { bestScore, bestIdx = mmr, i }
		}
		selected = append(selected, pool[bestIdx])
		pool = append(pool[:bestIdx], pool[bestIdx+1:]...)
	}
	return selected
}

func (rk *Ranker) BuildProfile(ctx context.Context, userID string) *model.UserProfile {
	return &model.UserProfile{UserID: userID}
}

// helpers
func tagMatchScore(tags string, topTags []string) float64 {
	if len(topTags) == 0 { return 0 }
	match := 0
	for _, tt := range topTags {
		if strings.Contains(tags, tt) { match++ }
	}
	return math.Min(float64(match)/float64(len(topTags)), 1.0)
}

func genreMatch(genre string, topGenres []string) float64 {
	for _, g := range topGenres {
		if genre == g { return 1.0 }
	}
	return 0
}

func authorMatch(author string, topAuthors []string) float64 {
	for _, a := range topAuthors {
		if author == a { return 1.0 }
	}
	return 0
}

func itemAgeDecay(createdAt time.Time) float64 {
	days := time.Since(createdAt).Hours() / 24
	return math.Max(0.1, 1.0-days*0.003)
}

func jaccardTags(a, b string) float64 {
	ta := splitTagsStr(a); tb := splitTagsStr(b)
	if len(ta)+len(tb) == 0 { return 0 }
	inter := 0
	setB := make(map[string]bool)
	for _, t := range tb { setB[t] = true }
	for _, t := range ta { if setB[t] { inter++ } }
	return float64(inter) / float64(len(ta)+len(tb)-inter)
}

func splitTagsStr(s string) []string {
	var r []string
	for _, t := range strings.Split(s, ",") {
		if t = strings.TrimSpace(t); t != "" { r = append(r, t) }
	}
	return r
}

