package repository

import (
	"context"
	"fmt"

	"short-drama-platform/content-service/model"
)

// GetOrCreateCredit 获取或创建用户信用额度（新用户默认 50000 分 = ¥500）
func (r *mysqlContentRepository) GetOrCreateCredit(ctx context.Context, userID string) (*model.UserCredit, error) {
	var c model.UserCredit
	err := r.conn.QueryRowCtx(ctx, &c,
		"SELECT id, user_id, balance, created_at, updated_at FROM user_credits WHERE user_id = ?",
		userID,
	)
	if err == nil {
		return &c, nil
	}
	// 新用户：初始 50000 分
	_, err = r.conn.ExecCtx(ctx,
		"INSERT INTO user_credits (user_id, balance) VALUES (?, 50000)",
		userID,
	)
	if err != nil {
		return nil, fmt.Errorf("create credit for user %s: %w", userID, err)
	}
	return &model.UserCredit{UserID: userID, Balance: 50000}, nil
}

// DeductCredit 扣减信用额度（幂等，不会扣到负数）
func (r *mysqlContentRepository) DeductCredit(ctx context.Context, userID string, amount int64) (int64, error) {
	_, err := r.conn.ExecCtx(ctx,
		"UPDATE user_credits SET balance = GREATEST(balance - ?, 0), updated_at = NOW() WHERE user_id = ?",
		amount, userID,
	)
	if err != nil {
		return 0, fmt.Errorf("deduct credit user=%s: %w", userID, err)
	}
	var balance int64
	r.conn.QueryRowCtx(ctx, &balance, "SELECT balance FROM user_credits WHERE user_id = ?", userID)
	return balance, nil
}

// AddCredit 增加信用额度（管理员充值）
func (r *mysqlContentRepository) AddCredit(ctx context.Context, userID string, amount int64) (int64, error) {
	_, err := r.conn.ExecCtx(ctx,
		"UPDATE user_credits SET balance = balance + ?, updated_at = NOW() WHERE user_id = ?",
		amount, userID,
	)
	if err != nil {
		return 0, fmt.Errorf("add credit user=%s: %w", userID, err)
	}
	var balance int64
	r.conn.QueryRowCtx(ctx, &balance, "SELECT balance FROM user_credits WHERE user_id = ?", userID)
	return balance, nil
}
