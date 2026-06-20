package model

import (
	"time"
)

// PaymentMethod 支付方式
type PaymentMethod string

const (
	PaymentMethodWeChat PaymentMethod = "wechat"
	PaymentMethodAlipay PaymentMethod = "alipay"
)

// PaymentStatus 支付状态
type PaymentStatus string

const (
	PaymentStatusPending  PaymentStatus = "pending"  // 待支付
	PaymentStatusPaid     PaymentStatus = "paid"     // 已支付
	PaymentStatusFailed   PaymentStatus = "failed"   // 支付失败
	PaymentStatusCanceled PaymentStatus = "canceled" // 已取消
	PaymentStatusRefunded PaymentStatus = "refunded" // 已退款
)

// RefundStatus 退款状态
type RefundStatus string

const (
	RefundStatusProcessing RefundStatus = "processing" // 退款处理中
	RefundStatusSuccess    RefundStatus = "success"    // 退款成功
	RefundStatusFailed     RefundStatus = "failed"     // 退款失败
)

// PaymentOrder 支付订单
type PaymentOrder struct {
	ID            string        `db:"id" json:"id"`
	OrderNo       string        `db:"order_no" json:"order_no"`             // 业务订单号
	TransactionID string        `db:"transaction_id" json:"transaction_id"` // 第三方交易号
	UserID        string        `db:"user_id" json:"user_id"`
	Amount        int64         `db:"amount" json:"amount"`             // 金额，单位：分
	Currency      string        `db:"currency" json:"currency"`         // 币种，默认 CNY
	Method        PaymentMethod `db:"method" json:"method"`             // 支付方式
	Status        PaymentStatus `db:"status" json:"status"`             // 支付状态
	Subject       string        `db:"subject" json:"subject"`           // 商品标题
	Description   string        `db:"description" json:"description"`   // 商品描述
	NotifyURL     string        `db:"notify_url" json:"notify_url"`     // 异步通知地址
	ReturnURL     string        `db:"return_url" json:"return_url"`     // 同步跳转地址
	ClientIP      string        `db:"client_ip" json:"client_ip"`       // 客户端IP
	ExpireTime    time.Time     `db:"expire_time" json:"expire_time"`   // 过期时间
	PaidAt        *time.Time    `db:"paid_at" json:"paid_at,omitempty"` // 支付时间
	Extra         string        `db:"extra" json:"extra,omitempty"`     // 扩展参数，JSON格式
	CreatedAt     time.Time     `db:"created_at" json:"created_at"`
	UpdatedAt     time.Time     `db:"updated_at" json:"updated_at"`
}

// RefundOrder 退款订单
type RefundOrder struct {
	ID             int64        `db:"id" json:"id"`
	RefundNo       string       `db:"refund_no" json:"refund_no"`             // 退款单号
	PaymentOrderID string       `db:"payment_order_id" json:"payment_order_id"` // 原支付订单ID
	TransactionID  string       `db:"transaction_id" json:"transaction_id"`   // 第三方交易号
	RefundAmount   int64        `db:"refund_amount" json:"refund_amount"`     // 退款金额，单位：分
	TotalAmount    int64        `db:"total_amount" json:"total_amount"`       // 原订单总金额
	Reason         string       `db:"reason" json:"reason"`                   // 退款原因
	Status         RefundStatus `db:"status" json:"status"`                   // 退款状态
	RefundedAt     *time.Time   `db:"refunded_at" json:"refunded_at,omitempty"` // 退款时间
	CreatedAt      time.Time    `db:"created_at" json:"created_at"`
	UpdatedAt      time.Time    `db:"updated_at" json:"updated_at"`
}

// PaymentNotifyData 支付回调通用数据结构
type PaymentNotifyData struct {
	OrderNo       string        `json:"order_no"`
	TransactionID string        `json:"transaction_id"`
	Method        PaymentMethod `json:"method"`
	Status        PaymentStatus `json:"status"`
	Amount        int64         `json:"amount"`
	PaidAt        time.Time     `json:"paid_at"`
	RawData       string        `json:"raw_data"` // 原始回调数据
}
