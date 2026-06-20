package logic

import (
	"context"
	"fmt"
	"short-drama-platform/content-service/internal/types"
)

func (l *ContentLogic) ListPayments(ctx context.Context, req *types.ListPaymentsRequest) (*types.ListPaymentsResponse, error) {
	orders, err := l.repo.FindPayments(ctx, req.UserID, req.Page, req.PageSize)
	if err != nil {
		return nil, fmt.Errorf("list payments: %w", err)
	}
	total, _ := l.repo.CountPayments(ctx, req.UserID)

	result := make([]types.PaymentOrderItem, 0, len(orders))
	for _, o := range orders {
		result = append(result, types.PaymentOrderItem{
			ID:            o.ID,
			OrderNo:       o.OrderNo,
			TransactionID: o.TransactionID,
			UserID:        o.UserID,
			Amount:        o.Amount,
			Currency:      o.Currency,
			Method:        o.Method,
			Status:        o.Status,
			Subject:       o.Subject,
			Description:   o.Description,
			QrCode:        o.QrCode,
			PayUrl:        o.PayUrl,
			ExpireTime:    o.ExpireTime,
			PaidAt:        o.PaidAt,
			CreatedAt:     o.CreatedAt,
		})
	}

	pages := (int(total) + req.PageSize - 1) / req.PageSize
	return &types.ListPaymentsResponse{
		Payments: result,
		Total:    total,
		Page:     req.Page,
		Pages:    pages,
	}, nil
}
