package repository

import (
	"context"
	"fmt"
	"short-drama-platform/payment-service/model"
	"time"

	"github.com/zeromicro/go-zero/core/stores/sqlx"
)

// PaymentRepository 支付数据仓库接口
type PaymentRepository interface {
	// 支付订单操作
	CreatePaymentOrder(ctx context.Context, order *model.PaymentOrder) error
	FindByID(ctx context.Context, id string) (*model.PaymentOrder, error)
	FindByOrderNo(ctx context.Context, orderNo string) (*model.PaymentOrder, error)
	FindByUserID(ctx context.Context, userID string, page, pageSize int, status string) ([]*model.PaymentOrder, error)
	CountByUserID(ctx context.Context, userID string, status string) (int64, error)
	UpdateStatus(ctx context.Context, id string, status model.PaymentStatus, transactionID string) error
	UpdateStatusWithPaidTime(ctx context.Context, id string, status model.PaymentStatus, transactionID string, paidAt time.Time) error

	// 退款订单操作
	CreateRefundOrder(ctx context.Context, order *model.RefundOrder) error
	FindRefundByPaymentOrderID(ctx context.Context, paymentOrderID string) (*model.RefundOrder, error)
	UpdateRefundStatus(ctx context.Context, id int64, status model.RefundStatus) error
}

// mysqlPaymentRepository MySQL 实现
type mysqlPaymentRepository struct {
	conn sqlx.SqlConn
}

// NewPaymentRepository 创建 MySQL 支付仓库实例
func NewPaymentRepository(conn sqlx.SqlConn) PaymentRepository {
	return &mysqlPaymentRepository{conn: conn}
}

// ==============================
// 支付订单
// ==============================

var createPaymentOrderSQL = `INSERT INTO payment_orders
	(id, order_no, transaction_id, user_id, amount, currency, method, status, subject, description, notify_url, return_url, client_ip, expire_time, extra, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW())`

func (r *mysqlPaymentRepository) CreatePaymentOrder(ctx context.Context, order *model.PaymentOrder) error {
	_, err := r.conn.ExecCtx(ctx, createPaymentOrderSQL,
		order.ID, order.OrderNo, order.TransactionID, order.UserID,
		order.Amount, order.Currency, order.Method, order.Status,
		order.Subject, order.Description, order.NotifyURL, order.ReturnURL,
		order.ClientIP, order.ExpireTime, order.Extra,
	)
	if err != nil {
		return fmt.Errorf("create payment order: %w", err)
	}
	return nil
}

var findPaymentByIDSQL = `SELECT id, order_no, transaction_id, user_id, amount, currency, method, status,
	subject, description, notify_url, return_url, client_ip, expire_time, paid_at, extra, created_at, updated_at
	FROM payment_orders WHERE id = ?`

func (r *mysqlPaymentRepository) FindByID(ctx context.Context, id string) (*model.PaymentOrder, error) {
	var order model.PaymentOrder
	err := r.conn.QueryRowCtx(ctx, &order, findPaymentByIDSQL, id)
	if err != nil {
		return nil, fmt.Errorf("find payment order by id %s: %w", id, err)
	}
	return &order, nil
}

var findPaymentByOrderNoSQL = `SELECT id, order_no, transaction_id, user_id, amount, currency, method, status,
	subject, description, notify_url, return_url, client_ip, expire_time, paid_at, extra, created_at, updated_at
	FROM payment_orders WHERE order_no = ?`

func (r *mysqlPaymentRepository) FindByOrderNo(ctx context.Context, orderNo string) (*model.PaymentOrder, error) {
	var order model.PaymentOrder
	err := r.conn.QueryRowCtx(ctx, &order, findPaymentByOrderNoSQL, orderNo)
	if err != nil {
		return nil, fmt.Errorf("find payment order by order_no %s: %w", orderNo, err)
	}
	return &order, nil
}

var updatePaymentStatusSQL = `UPDATE payment_orders SET status = ?, transaction_id = ?, updated_at = NOW() WHERE id = ?`

func (r *mysqlPaymentRepository) UpdateStatus(ctx context.Context, id string, status model.PaymentStatus, transactionID string) error {
	_, err := r.conn.ExecCtx(ctx, updatePaymentStatusSQL, status, transactionID, id)
	if err != nil {
		return fmt.Errorf("update payment status %s: %w", id, err)
	}
	return nil
}

var updatePaymentStatusPaidSQL = `UPDATE payment_orders SET status = ?, transaction_id = ?, paid_at = ?, updated_at = NOW() WHERE id = ?`

func (r *mysqlPaymentRepository) UpdateStatusWithPaidTime(ctx context.Context, id string, status model.PaymentStatus, transactionID string, paidAt time.Time) error {
	_, err := r.conn.ExecCtx(ctx, updatePaymentStatusPaidSQL, status, transactionID, paidAt, id)
	if err != nil {
		return fmt.Errorf("update payment status with paid time %s: %w", id, err)
	}
	return nil
}

// ==============================
// 用户支付列表查询
// ==============================

var findPaymentsByUserIDSQL = `SELECT id, order_no, transaction_id, user_id, amount, currency, method, status,
	subject, description, notify_url, return_url, client_ip, expire_time, paid_at, extra, created_at, updated_at
	FROM payment_orders WHERE user_id = ?`

func (r *mysqlPaymentRepository) FindByUserID(ctx context.Context, userID string, page, pageSize int, status string) ([]*model.PaymentOrder, error) {
	query := findPaymentsByUserIDSQL
	args := []interface{}{userID}

	if status != "" {
		query += " AND status = ?"
		args = append(args, status)
	}

	query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
	offset := (page - 1) * pageSize
	args = append(args, pageSize, offset)

	var orders []*model.PaymentOrder
	err := r.conn.QueryRowsCtx(ctx, &orders, query, args...)
	if err != nil {
		return nil, fmt.Errorf("find payments by user_id %s: %w", userID, err)
	}
	return orders, nil
}

var countPaymentsByUserIDSQL = `SELECT COUNT(*) FROM payment_orders WHERE user_id = ?`

func (r *mysqlPaymentRepository) CountByUserID(ctx context.Context, userID string, status string) (int64, error) {
	query := countPaymentsByUserIDSQL
	args := []interface{}{userID}

	if status != "" {
		query += " AND status = ?"
		args = append(args, status)
	}

	var count int64
	err := r.conn.QueryRowCtx(ctx, &count, query, args...)
	if err != nil {
		return 0, fmt.Errorf("count payments by user_id %s: %w", userID, err)
	}
	return count, nil
}

// ==============================
// 退款订单
// ==============================

var createRefundOrderSQL = `INSERT INTO refund_orders
	(refund_no, payment_order_id, transaction_id, refund_amount, total_amount, reason, status, created_at, updated_at)
	VALUES (?, ?, ?, ?, ?, ?, ?, NOW(), NOW())`

func (r *mysqlPaymentRepository) CreateRefundOrder(ctx context.Context, order *model.RefundOrder) error {
	result, err := r.conn.ExecCtx(ctx, createRefundOrderSQL,
		order.RefundNo, order.PaymentOrderID, order.TransactionID,
		order.RefundAmount, order.TotalAmount, order.Reason, order.Status,
	)
	if err != nil {
		return fmt.Errorf("create refund order: %w", err)
	}
	id, _ := result.LastInsertId()
	order.ID = id
	return nil
}

var findRefundByPaymentSQL = `SELECT id, refund_no, payment_order_id, transaction_id, refund_amount, total_amount,
	reason, status, refunded_at, created_at, updated_at
	FROM refund_orders WHERE payment_order_id = ?`

func (r *mysqlPaymentRepository) FindRefundByPaymentOrderID(ctx context.Context, paymentOrderID string) (*model.RefundOrder, error) {
	var order model.RefundOrder
	err := r.conn.QueryRowCtx(ctx, &order, findRefundByPaymentSQL, paymentOrderID)
	if err != nil {
		return nil, fmt.Errorf("find refund by payment_order_id %s: %w", paymentOrderID, err)
	}
	return &order, nil
}

var updateRefundStatusSQL = `UPDATE refund_orders SET status = ?, refunded_at = ?, updated_at = NOW() WHERE id = ?`

func (r *mysqlPaymentRepository) UpdateRefundStatus(ctx context.Context, id int64, status model.RefundStatus) error {
	var refundedAt interface{}
	if status == model.RefundStatusSuccess {
		refundedAt = time.Now()
	}
	_, err := r.conn.ExecCtx(ctx, updateRefundStatusSQL, status, refundedAt, id)
	if err != nil {
		return fmt.Errorf("update refund status %d: %w", id, err)
	}
	return nil
}
