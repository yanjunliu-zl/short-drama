package logic

import (
	"context"
	"fmt"
	"short-drama-platform/payment-service/internal/provider"
	"short-drama-platform/payment-service/internal/repository"
	"short-drama-platform/payment-service/internal/types"
	"short-drama-platform/payment-service/model"
	"time"

	"github.com/zeromicro/go-zero/core/stores/redis"
)

// PaymentLogic 支付业务逻辑
type PaymentLogic struct {
	repo       repository.PaymentRepository
	redis      *redis.Redis
	wechatPay  provider.PaymentProvider
	alipay     provider.PaymentProvider
}

// NewPaymentLogic 创建支付业务逻辑实例
func NewPaymentLogic(
	repo repository.PaymentRepository,
	redisClient *redis.Redis,
	wechatPay provider.PaymentProvider,
	alipay provider.PaymentProvider,
) types.PaymentService {
	return &PaymentLogic{
		repo:      repo,
		redis:     redisClient,
		wechatPay: wechatPay,
		alipay:    alipay,
	}
}

// getProvider 根据支付方式获取对应的支付渠道
func (l *PaymentLogic) getProvider(method model.PaymentMethod) (provider.PaymentProvider, error) {
	switch method {
	case model.PaymentMethodWeChat:
		return l.wechatPay, nil
	case model.PaymentMethodAlipay:
		return l.alipay, nil
	default:
		return nil, fmt.Errorf("unsupported payment method: %s", method)
	}
}

// CreatePayment 创建支付订单
func (l *PaymentLogic) CreatePayment(ctx context.Context, req *types.CreatePaymentRequest) (*types.PaymentResponse, error) {
	// 1. 获取支付渠道
	payProvider, err := l.getProvider(req.Method)
	if err != nil {
		return nil, err
	}

	// 2. 幂等性检查：查询是否已存在相同业务单号的订单
	existingOrder, err := l.repo.FindByOrderNo(ctx, req.OrderNo)
	if err == nil && existingOrder != nil {
		// 订单已存在，直接返回
		if existingOrder.Status == model.PaymentStatusPending {
			return l.orderToResponse(existingOrder), nil
		}
		return nil, fmt.Errorf("order %s already processed with status: %s", req.OrderNo, existingOrder.Status)
	}

	// 3. 生成支付订单ID
	orderID := fmt.Sprintf("PAY%d", time.Now().UnixNano())

	// 4. 设置默认币种
	currency := req.Currency
	if currency == "" {
		currency = "CNY"
	}

	// 5. 调用支付渠道创建订单
	orderParams := &provider.CreateOrderParams{
		OrderNo:     req.OrderNo,
		Amount:      req.Amount,
		Currency:    currency,
		Subject:     req.Subject,
		Description: req.Description,
		ClientIP:    req.ClientIP,
		Method:      req.Method,
	}

	orderResult, err := payProvider.CreateOrder(ctx, orderParams)
	if err != nil {
		return nil, fmt.Errorf("failed to create payment order via %s: %w", req.Method, err)
	}

	// 6. 保存支付订单到数据库
	paymentOrder := &model.PaymentOrder{
		ID:            orderID,
		OrderNo:       req.OrderNo,
		TransactionID: orderResult.TransactionID,
		UserID:        req.UserID,
		Amount:        req.Amount,
		Currency:      currency,
		Method:        req.Method,
		Status:        model.PaymentStatusPending,
		Subject:       req.Subject,
		Description:   req.Description,
		ClientIP:      req.ClientIP,
		ExpireTime:    time.Now().Add(30 * time.Minute), // 30分钟过期
		CreatedAt:     time.Now(),
		UpdatedAt:     time.Now(),
	}

	if err := l.repo.CreatePaymentOrder(ctx, paymentOrder); err != nil {
		return nil, fmt.Errorf("failed to save payment order: %w", err)
	}

	// 7. 构建响应
	resp := l.orderToResponse(paymentOrder)
	resp.QrCode = orderResult.QrCode
	resp.PayURL = orderResult.PayURL

	return resp, nil
}

// GetPayment 查询支付订单
func (l *PaymentLogic) GetPayment(ctx context.Context, req *types.GetPaymentRequest) (*types.PaymentResponse, error) {
	order, err := l.repo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to get payment order: %w", err)
	}

	// 如果订单状态为待支付，主动查询一次支付渠道获取最新状态
	if order.Status == model.PaymentStatusPending && order.TransactionID != "" {
		payProvider, err := l.getProvider(order.Method)
		if err == nil {
			latestStatus, err := payProvider.QueryOrder(ctx, order.TransactionID)
			if err == nil && latestStatus != order.Status {
				// 更新订单状态
				_ = l.repo.UpdateStatus(ctx, order.ID, latestStatus, order.TransactionID)
				order.Status = latestStatus
			}
		}
	}

	return l.orderToResponse(order), nil
}

// CancelPayment 取消支付订单
func (l *PaymentLogic) CancelPayment(ctx context.Context, req *types.CancelPaymentRequest) (*types.CancelPaymentResponse, error) {
	order, err := l.repo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find payment order: %w", err)
	}

	// 只能取消待支付的订单
	if order.Status != model.PaymentStatusPending {
		return &types.CancelPaymentResponse{
			Success: false,
			Message: fmt.Sprintf("order status %s cannot be canceled", order.Status),
		}, nil
	}

	// 调用支付渠道关闭订单
	payProvider, err := l.getProvider(order.Method)
	if err != nil {
		return nil, err
	}

	if err := payProvider.CloseOrder(ctx, order.TransactionID); err != nil {
		return nil, fmt.Errorf("failed to close order via %s: %w", order.Method, err)
	}

	// 更新订单状态
	if err := l.repo.UpdateStatus(ctx, order.ID, model.PaymentStatusCanceled, order.TransactionID); err != nil {
		return nil, fmt.Errorf("failed to update order status: %w", err)
	}

	return &types.CancelPaymentResponse{
		Success: true,
		Message: "payment order canceled",
	}, nil
}

// CreateRefund 申请退款
func (l *PaymentLogic) CreateRefund(ctx context.Context, req *types.CreateRefundRequest) (*types.RefundResponse, error) {
	// 1. 查询原支付订单
	order, err := l.repo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find payment order: %w", err)
	}

	// 2. 只能对已支付的订单退款
	if order.Status != model.PaymentStatusPaid {
		return nil, fmt.Errorf("order status %s cannot be refunded", order.Status)
	}

	// 3. 检查是否已有退款记录
	existingRefund, err := l.repo.FindRefundByPaymentOrderID(ctx, order.ID)
	if err == nil && existingRefund != nil {
		return l.refundToResponse(existingRefund), nil
	}

	// 4. 校验退款金额
	if req.RefundAmount > order.Amount {
		return nil, fmt.Errorf("refund amount %d exceeds total amount %d", req.RefundAmount, order.Amount)
	}

	// 5. 调用支付渠道退款
	payProvider, err := l.getProvider(order.Method)
	if err != nil {
		return nil, err
	}

	refundParams := &provider.RefundParams{
		TransactionID: order.TransactionID,
		RefundNo:      fmt.Sprintf("RF_%s_%d", order.OrderNo, time.Now().Unix()),
		TotalAmount:   order.Amount,
		RefundAmount:  req.RefundAmount,
		Reason:        req.Reason,
	}

	refundResult, err := payProvider.Refund(ctx, refundParams)
	if err != nil {
		return nil, fmt.Errorf("failed to refund via %s: %w", order.Method, err)
	}

	// 6. 保存退款记录
	refundOrder := &model.RefundOrder{
		RefundNo:       refundResult.RefundNo,
		PaymentOrderID: order.ID,
		TransactionID:  order.TransactionID,
		RefundAmount:   req.RefundAmount,
		TotalAmount:    order.Amount,
		Reason:         req.Reason,
		Status:         refundResult.Status,
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}

	if err := l.repo.CreateRefundOrder(ctx, refundOrder); err != nil {
		return nil, fmt.Errorf("failed to save refund order: %w", err)
	}

	return l.refundToResponse(refundOrder), nil
}

// GetRefund 查询退款状态
func (l *PaymentLogic) GetRefund(ctx context.Context, req *types.GetRefundRequest) (*types.RefundResponse, error) {
	// 先查支付订单
	order, err := l.repo.FindByID(ctx, req.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find payment order: %w", err)
	}

	// 查退款记录
	refundOrder, err := l.repo.FindRefundByPaymentOrderID(ctx, order.ID)
	if err != nil {
		return nil, fmt.Errorf("refund not found for order: %s", req.ID)
	}

	return l.refundToResponse(refundOrder), nil
}

// ListPayments 查询用户支付列表
func (l *PaymentLogic) ListPayments(ctx context.Context, req *types.ListPaymentsRequest) (*types.ListPaymentsResponse, error) {
	orders, err := l.repo.FindByUserID(ctx, req.UserID, req.Page, req.PageSize, req.Status)
	if err != nil {
		return nil, fmt.Errorf("failed to list payments: %w", err)
	}

	total, err := l.repo.CountByUserID(ctx, req.UserID, req.Status)
	if err != nil {
		return nil, fmt.Errorf("failed to count payments: %w", err)
	}

	payments := make([]types.PaymentResponse, 0, len(orders))
	for _, order := range orders {
		payments = append(payments, *l.orderToResponse(order))
	}

	pages := (int(total) + req.PageSize - 1) / req.PageSize
	return &types.ListPaymentsResponse{
		Payments: payments,
		Total:    total,
		Page:     req.Page,
		Pages:    pages,
	}, nil
}

// HandleWeChatNotify 处理微信支付回调
func (l *PaymentLogic) HandleWeChatNotify(ctx context.Context, body []byte) (*types.NotifyResponse, error) {
	// 1. 验证签名
	verified, err := l.wechatPay.VerifyNotifySign(ctx, body)
	if err != nil || !verified {
		return &types.NotifyResponse{Success: false, Message: "signature verification failed"}, nil
	}

	// 2. 解析回调数据
	notifyData, err := l.wechatPay.ParseNotify(ctx, body)
	if err != nil {
		return nil, fmt.Errorf("failed to parse wechat notify: %w", err)
	}

	// 3. 根据订单号查找支付订单
	order, err := l.repo.FindByOrderNo(ctx, notifyData.OrderNo)
	if err != nil {
		return nil, fmt.Errorf("order not found for notify: %s", notifyData.OrderNo)
	}

	// 4. 更新订单状态（幂等处理）
	if order.Status == model.PaymentStatusPending {
		if err := l.repo.UpdateStatusWithPaidTime(
			ctx, order.ID, notifyData.Status, notifyData.TransactionID, notifyData.PaidAt,
		); err != nil {
			return nil, fmt.Errorf("failed to update order status: %w", err)
		}
	}

	return &types.NotifyResponse{Success: true, Message: "ok"}, nil
}

// HandleAlipayNotify 处理支付宝回调
func (l *PaymentLogic) HandleAlipayNotify(ctx context.Context, body []byte) (*types.NotifyResponse, error) {
	// 1. 验证签名
	verified, err := l.alipay.VerifyNotifySign(ctx, body)
	if err != nil || !verified {
		return &types.NotifyResponse{Success: false, Message: "signature verification failed"}, nil
	}

	// 2. 解析回调数据
	notifyData, err := l.alipay.ParseNotify(ctx, body)
	if err != nil {
		return nil, fmt.Errorf("failed to parse alipay notify: %w", err)
	}

	// 3. 根据订单号查找支付订单
	order, err := l.repo.FindByOrderNo(ctx, notifyData.OrderNo)
	if err != nil {
		return nil, fmt.Errorf("order not found for notify: %s", notifyData.OrderNo)
	}

	// 4. 更新订单状态
	if order.Status == model.PaymentStatusPending {
		if err := l.repo.UpdateStatusWithPaidTime(
			ctx, order.ID, notifyData.Status, notifyData.TransactionID, notifyData.PaidAt,
		); err != nil {
			return nil, fmt.Errorf("failed to update order status: %w", err)
		}
	}

	return &types.NotifyResponse{Success: true, Message: "success"}, nil
}

// ==============================
// 辅助方法
// ==============================

// orderToResponse 将支付订单模型转换为响应
func (l *PaymentLogic) orderToResponse(order *model.PaymentOrder) *types.PaymentResponse {
	resp := &types.PaymentResponse{
		ID:            order.ID,
		OrderNo:       order.OrderNo,
		TransactionID: order.TransactionID,
		UserID:        order.UserID,
		Amount:        order.Amount,
		Currency:      order.Currency,
		Method:        order.Method,
		Status:        order.Status,
		Subject:       order.Subject,
		Description:   order.Description,
		ExpireTime:    order.ExpireTime.Format("2006-01-02 15:04:05"),
		CreatedAt:     order.CreatedAt.Format("2006-01-02 15:04:05"),
	}

	if order.PaidAt != nil {
		resp.PaidAt = order.PaidAt.Format("2006-01-02 15:04:05")
	}

	return resp
}

// refundToResponse 将退款订单模型转换为响应
func (l *PaymentLogic) refundToResponse(refund *model.RefundOrder) *types.RefundResponse {
	resp := &types.RefundResponse{
		ID:             refund.ID,
		RefundNo:       refund.RefundNo,
		PaymentOrderID: refund.PaymentOrderID,
		RefundAmount:   refund.RefundAmount,
		TotalAmount:    refund.TotalAmount,
		Reason:         refund.Reason,
		Status:         refund.Status,
		CreatedAt:      refund.CreatedAt.Format("2006-01-02 15:04:05"),
	}

	if refund.RefundedAt != nil {
		resp.RefundedAt = refund.RefundedAt.Format("2006-01-02 15:04:05")
	}

	return resp
}
