package provider

import (
	"context"
	"short-drama-platform/payment-service/model"
)

// CreateOrderParams 创建支付订单参数
type CreateOrderParams struct {
	OrderNo     string              // 业务订单号
	Amount      int64               // 金额（分）
	Currency    string              // 币种
	Subject     string              // 商品标题
	Description string              // 商品描述
	NotifyURL   string              // 异步通知地址
	ReturnURL   string              // 同步跳转地址
	ClientIP    string              // 客户端IP
	Method      model.PaymentMethod // 支付方式
}

// OrderResult 创建订单返回结果
type OrderResult struct {
	TransactionID string // 第三方交易号
	QrCode        string // 扫码支付二维码
	PayURL        string // H5支付跳转链接
}

// RefundParams 退款参数
type RefundParams struct {
	TransactionID string // 第三方交易号
	RefundNo      string // 退款单号
	TotalAmount   int64  // 原订单总金额（分）
	RefundAmount  int64  // 退款金额（分）
	Reason        string // 退款原因
}

// RefundResult 退款结果
type RefundResult struct {
	RefundNo    string              // 退款单号
	Status      model.RefundStatus  // 退款状态
	RefundedAt  string              // 退款时间
}

// PaymentProvider 支付渠道抽象接口
// 新增支付渠道只需实现此接口
type PaymentProvider interface {
	// Name 返回支付渠道名称
	Name() model.PaymentMethod

	// CreateOrder 创建支付订单（统一下单）
	CreateOrder(ctx context.Context, params *CreateOrderParams) (*OrderResult, error)

	// QueryOrder 查询订单状态
	QueryOrder(ctx context.Context, transactionID string) (model.PaymentStatus, error)

	// CloseOrder 关闭/取消订单
	CloseOrder(ctx context.Context, transactionID string) error

	// Refund 申请退款
	Refund(ctx context.Context, params *RefundParams) (*RefundResult, error)

	// QueryRefund 查询退款状态
	QueryRefund(ctx context.Context, refundNo string) (*RefundResult, error)

	// ParseNotify 解析回调通知，返回统一的回调数据
	ParseNotify(ctx context.Context, body []byte) (*model.PaymentNotifyData, error)

	// VerifyNotifySign 验证回调签名
	VerifyNotifySign(ctx context.Context, body []byte) (bool, error)
}
