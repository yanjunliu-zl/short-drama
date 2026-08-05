package logic

import (
	"context"
	"math"
	"sync"

	"github.com/redis/go-redis/v9"
)

// BanditService LinUCB 上下文 Bandit — 召回路径权重在线学习
type BanditService struct {
	redis  *redis.Client
	mu     sync.RWMutex
	cache  map[string]*linUCBModel // userID → model
}

// 五条召回路径
var recallSources = []string{"cf", "tag", "hot", "author", "new"}

// Reward mapping
var rewardMap = map[string]float64{
	"view":  1.0,
	"like":  3.0,
	"share": 5.0,
	"skip":  -0.5,
}

type linUCBModel struct {
	A     map[string][]float64 // source → covariance diag (8-dim)
	b     map[string][]float64 // source → reward vector
	alpha float64
}

func NewBanditService(redis *redis.Client) *BanditService {
	return &BanditService{
		redis: redis,
		cache: make(map[string]*linUCBModel),
	}
}

// SelectSource UCB 选择最佳召回路径
func (b *BanditService) SelectSource(userID string, context []float64) string {
	model := b.getModel(userID)
	if len(context) == 0 {
		context = make([]float64, 8) // default 8-dim
	}

	bestSource, bestScore := "hot", math.Inf(-1)
	for _, src := range recallSources {
		A, okA := model.A[src]
		bt, okB := model.b[src]
		if !okA || !okB { continue }

		// θ = A⁻¹b (simplified: diagonal A)
		theta := make([]float64, len(context))
		for i := range context {
			if A[i] > 0 { theta[i] = bt[i] / A[i] }
		}

		// UCB = θ·x + α * √(xᵀA⁻¹x)
		exploitation := dot(theta, context)
		exploration := model.alpha * math.Sqrt(dot(context, invDiag(A)))
		score := exploitation + exploration
		if score > bestScore { bestScore, bestSource = score, src }
	}
	return bestSource
}

// Update 更新 Bandit 模型
func (b *BanditService) Update(ctx context.Context, userID, source, action string, context []float64) {
	reward, ok := rewardMap[action]
	if !ok { return }
	if len(context) == 0 { context = make([]float64, 8) }

	model := b.getModel(userID)
	A := model.A[source]
	bt := model.b[source]
	if A == nil {
		A = make([]float64, len(context))
		for i := range A { A[i] = 1.0 } // identity init
		bt = make([]float64, len(context))
	}

	for i := range context {
		A[i] += context[i] * context[i]
		bt[i] += context[i] * reward
	}
	model.A[source], model.b[source] = A, bt
	b.cache[userID] = model
}

func (b *BanditService) getModel(userID string) *linUCBModel {
	b.mu.RLock()
	m, ok := b.cache[userID]
	b.mu.RUnlock()
	if ok { return m }

	b.mu.Lock()
	defer b.mu.Unlock()
	return &linUCBModel{
		A:     make(map[string][]float64),
		b:     make(map[string][]float64),
		alpha: 1.0,
	}
}

func dot(a, b []float64) float64 {
	s := 0.0
	for i := range a { s += a[i] * b[i] }
	return s
}

func invDiag(A []float64) []float64 {
	inv := make([]float64, len(A))
	for i, v := range A {
		if v != 0 { inv[i] = 1.0 / v }
	}
	return inv
}
