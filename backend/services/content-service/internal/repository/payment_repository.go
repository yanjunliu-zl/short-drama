package repository

import (
	"context"
	"fmt"
)

type PaymentRecord struct {
	ID            string `db:"id"`
	OrderNo       string `db:"order_no"`
	TransactionID string `db:"transaction_id"`
	UserID        string `db:"user_id"`
	Amount        int64  `db:"amount"`
	Currency      string `db:"currency"`
	Method        string `db:"method"`
	Status        string `db:"status"`
	Subject       string `db:"subject"`
	Description   string `db:"description"`
	QrCode        string `db:"qr_code"`
	PayUrl        string `db:"pay_url"`
	ExpireTime    string `db:"expire_time"`
	PaidAt        string `db:"paid_at"`
	CreatedAt     string `db:"created_at"`
}

func (r *mysqlContentRepository) FindPayments(ctx context.Context, userID string, page, pageSize int) ([]*PaymentRecord, error) {
	offset := (page - 1) * pageSize
	query := `SELECT id, order_no, COALESCE(transaction_id,'') as transaction_id, user_id, amount, currency, method, status,
		subject, COALESCE(description,'') as description, COALESCE(qr_code,'') as qr_code, COALESCE(pay_url,'') as pay_url,
		DATE_FORMAT(expire_time, '%Y-%m-%d %H:%i:%s') as expire_time,
		COALESCE(DATE_FORMAT(paid_at, '%Y-%m-%d %H:%i:%s'),'') as paid_at,
		DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as created_at
		FROM payment_orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?`
	var orders []*PaymentRecord
	if err := r.conn.QueryRowsCtx(ctx, &orders, query, userID, pageSize, offset); err != nil {
		return nil, fmt.Errorf("find payments: %w", err)
	}
	return orders, nil
}

func (r *mysqlContentRepository) CountPayments(ctx context.Context, userID string) (int64, error) {
	query := `SELECT COUNT(*) FROM payment_orders WHERE user_id = ?`
	var total int64
	if err := r.conn.QueryRowCtx(ctx, &total, query, userID); err != nil {
		return 0, fmt.Errorf("count payments: %w", err)
	}
	return total, nil
}
