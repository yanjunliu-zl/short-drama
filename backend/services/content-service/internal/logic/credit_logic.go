package logic

import (
	"context"
	"fmt"

	"short-drama-platform/content-service/model"
	"short-drama-platform/content-service/internal/repository"

	"github.com/zeromicro/go-zero/core/logx"
)

type CreditLogic struct {
	logx.Logger
	repo repository.ContentRepository
}

func NewCreditLogic(repo repository.ContentRepository) *CreditLogic {
	return &CreditLogic{Logger: logx.WithContext(context.Background()), repo: repo}
}

func (l *CreditLogic) GetBalance(ctx context.Context, userID string) (*model.UserCredit, error) {
	return l.repo.GetOrCreateCredit(ctx, userID)
}

func (l *CreditLogic) Deduct(ctx context.Context, userID string, amount int64) (int64, error) {
	return l.repo.DeductCredit(ctx, userID, amount)
}

func (l *CreditLogic) Add(ctx context.Context, userID string, amount int64) (int64, error) {
	return l.repo.AddCredit(ctx, userID, amount)
}

// CheckAndDeduct 检查余额并扣减，不足则返回错误
func (l *CreditLogic) CheckAndDeduct(ctx context.Context, userID string, costCents int64) error {
	credit, err := l.repo.GetOrCreateCredit(ctx, userID)
	if err != nil {
		return err
	}
	if credit.Balance < costCents {
		return fmt.Errorf("余额不足：当前 ¥%.2f，需要 ¥%.2f", float64(credit.Balance)/100, float64(costCents)/100)
	}
	_, err = l.repo.DeductCredit(ctx, userID, costCents)
	return err
}
