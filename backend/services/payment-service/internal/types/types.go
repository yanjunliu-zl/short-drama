package types

import (
	"context"
	"short-drama-platform/payment-service/model"
)

// ==============================
// 请求类型
// ==============================

// CreatePaymentRequest 创建支付订单请求
type CreatePaymentRequest struct {
	OrderNo     string              `json:"order_no" validate:"required"`     // 业务订单号
	UserID      string              `json:"user_id" validate:"required"`      // 用户ID
	Amount      int64               `json:"amount" validate:"required,min=1"` // 金额（分）
	Currency    string              `json:"currency,default=CNY"`             // 币种
	Method      model.PaymentMethod `json:"method" validate:"required"`       // 支付方式
	Subject     string              `json:"subject" validate:"required"`      // 商品标题
	Description string              `json:"description,omitempty"`            // 商品描述
	ClientIP    string              `json:"client_ip,omitempty"`              // 客户端IP
}

// GetPaymentRequest 查询支付订单请求
type GetPaymentRequest struct {
	ID string `path:"id" validate:"required"`
}

// CancelPaymentRequest 取消支付订单请求
type CancelPaymentRequest struct {
	ID string `path:"id" validate:"required"`
}

// CreateRefundRequest 申请退款请求
type CreateRefundRequest struct {
	ID           string `path:"id" validate:"required"`
	RefundAmount int64  `json:"refund_amount" validate:"required,min=1"` // 退款金额（分）
	Reason       string `json:"reason" validate:"required"`              // 退款原因
}

// GetRefundRequest 查询退款请求
type GetRefundRequest struct {
	ID string `path:"id" validate:"required"`
}

// WeChatNotifyRequest 微信支付回调请求
type WeChatNotifyRequest struct {
	// 回调数据由微信支付SDK解析
}

// AlipayNotifyRequest 支付宝回调请求
type AlipayNotifyRequest struct {
	// 回调数据由支付宝SDK解析
}

// ==============================
// 响应类型
// ==============================

// PaymentResponse 支付订单响应
type PaymentResponse struct {
	ID            string              `json:"id"`
	OrderNo       string              `json:"order_no"`
	TransactionID string              `json:"transaction_id,omitempty"`
	UserID        string              `json:"user_id"`
	Amount        int64               `json:"amount"`
	Currency      string              `json:"currency"`
	Method        model.PaymentMethod `json:"method"`
	Status        model.PaymentStatus `json:"status"`
	Subject       string              `json:"subject"`
	Description   string              `json:"description,omitempty"`
	QrCode        string              `json:"qr_code,omitempty"`    // 扫码支付二维码链接
	PayURL        string              `json:"pay_url,omitempty"`    // H5支付跳转链接
	ExpireTime    string              `json:"expire_time"`          // 过期时间
	PaidAt        string              `json:"paid_at,omitempty"`    // 支付时间
	CreatedAt     string              `json:"created_at"`
}

// CancelPaymentResponse 取消支付响应
type CancelPaymentResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

// RefundResponse 退款响应
type RefundResponse struct {
	ID             int64               `json:"id"`
	RefundNo       string              `json:"refund_no"`
	PaymentOrderID string              `json:"payment_order_id"`
	RefundAmount   int64               `json:"refund_amount"`
	TotalAmount    int64               `json:"total_amount"`
	Reason         string              `json:"reason"`
	Status         model.RefundStatus  `json:"status"`
	CreatedAt      string              `json:"created_at"`
	RefundedAt     string              `json:"refunded_at,omitempty"`
}

// NotifyResponse 回调处理响应
type NotifyResponse struct {
	Success bool   `json:"success"`
	Message string `json:"message"`
}

// ListPaymentsRequest 用户支付列表请求
type ListPaymentsRequest struct {
	UserID   string `form:"user_id" validate:"required"`
	Page     int    `form:"page,default=1" validate:"min=1"`
	PageSize int    `form:"pageSize,default=10" validate:"min=1,max=100"`
	Status   string `form:"status,optional"`
}

// ListPaymentsResponse 用户支付列表响应
type ListPaymentsResponse struct {
	Payments []PaymentResponse `json:"payments"`
	Total    int64             `json:"total"`
	Page     int               `json:"page"`
	Pages    int               `json:"pages"`
}

// ==============================
// 服务接口
// ==============================

// PaymentService 支付服务接口
type PaymentService interface {
	// CreatePayment 创建支付订单
	CreatePayment(ctx context.Context, req *CreatePaymentRequest) (*PaymentResponse, error)

	// GetPayment 查询支付订单
	GetPayment(ctx context.Context, req *GetPaymentRequest) (*PaymentResponse, error)

	// ListPayments 查询用户支付列表
	ListPayments(ctx context.Context, req *ListPaymentsRequest) (*ListPaymentsResponse, error)

	// CancelPayment 取消支付订单
	CancelPayment(ctx context.Context, req *CancelPaymentRequest) (*CancelPaymentResponse, error)

	// CreateRefund 申请退款
	CreateRefund(ctx context.Context, req *CreateRefundRequest) (*RefundResponse, error)

	// GetRefund 查询退款状态
	GetRefund(ctx context.Context, req *GetRefundRequest) (*RefundResponse, error)

	// HandleWeChatNotify 处理微信支付回调
	HandleWeChatNotify(ctx context.Context, body []byte) (*NotifyResponse, error)

	// HandleAlipayNotify 处理支付宝回调
	HandleAlipayNotify(ctx context.Context, body []byte) (*NotifyResponse, error)
}
