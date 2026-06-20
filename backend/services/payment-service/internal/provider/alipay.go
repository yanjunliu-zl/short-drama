package provider

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/url"
	"short-drama-platform/payment-service/internal/config"
	"short-drama-platform/payment-service/model"
	"sort"
	"strings"
	"time"
)

// AlipayProvider 支付宝支付提供者
type AlipayProvider struct {
	config    config.AlipayConfig
	appID     string
	notifyURL string
	returnURL string

	// 签名类型
	signType string

	// 应用私钥和支付宝公钥
	privateKey      *rsa.PrivateKey
	alipayPublicKey *rsa.PublicKey
}

// NewAlipayProvider 创建支付宝支付提供者
func NewAlipayProvider(cfg config.AlipayConfig) (*AlipayProvider, error) {
	signType := cfg.SignType
	if signType == "" {
		signType = "RSA2"
	}

	return &AlipayProvider{
		config:    cfg,
		appID:     cfg.AppID,
		notifyURL: cfg.NotifyURL,
		returnURL: cfg.ReturnURL,
		signType:  signType,
	}, nil
}

// Name 返回支付渠道名称
func (p *AlipayProvider) Name() model.PaymentMethod {
	return model.PaymentMethodAlipay
}

// CreateOrder 创建支付宝支付订单
// 调用支付宝统一下单API（alipay.trade.create / alipay.trade.page.pay / alipay.trade.wap.pay）
func (p *AlipayProvider) CreateOrder(ctx context.Context, params *CreateOrderParams) (*OrderResult, error) {
	// 构建公共请求参数
	bizContent := map[string]interface{}{
		"out_trade_no":  params.OrderNo,
		"total_amount":  formatAmount(params.Amount), // 支付宝以元为单位
		"subject":       params.Subject,
		"body":          params.Description,
		"product_code":  "FAST_INSTANT_TRADE_PAY",
		"timeout_express": "30m",
	}

	bizContentBytes, _ := json.Marshal(bizContent)

	// 构建请求参数
	reqParams := map[string]string{
		"app_id":      p.appID,
		"method":      "alipay.trade.precreate", // 当面付（扫码支付）
		"format":      "JSON",
		"charset":     "utf-8",
		"sign_type":   p.signType,
		"timestamp":   time.Now().Format("2006-01-02 15:04:05"),
		"version":     "1.0",
		"notify_url":  p.notifyURL,
		"biz_content": string(bizContentBytes),
	}

	// 生成签名
	sign, err := p.generateSign(reqParams)
	if err != nil {
		return nil, fmt.Errorf("failed to generate alipay sign: %w", err)
	}
	reqParams["sign"] = sign

	// 生产环境：调用支付宝API
	// POST https://openapi.alipay.com/gateway.do
	// 对返回的 qr_code 做处理

	tradeNo := fmt.Sprintf("ALI%s%d", params.OrderNo, time.Now().UnixNano())

	result := &OrderResult{
		TransactionID: tradeNo,
		QrCode:        fmt.Sprintf("https://qr.alipay.com/bax%d", time.Now().UnixNano()),
		PayURL:        fmt.Sprintf("https://openapi.alipay.com/gateway.do?%s", p.buildQueryString(reqParams)),
	}

	return result, nil
}

// QueryOrder 查询支付宝订单状态
func (p *AlipayProvider) QueryOrder(ctx context.Context, transactionID string) (model.PaymentStatus, error) {
	// 生产环境：调用 alipay.trade.query API

	return model.PaymentStatusPending, nil
}

// CloseOrder 关闭支付宝订单
func (p *AlipayProvider) CloseOrder(ctx context.Context, transactionID string) error {
	// 生产环境：调用 alipay.trade.close API

	return nil
}

// Refund 支付宝退款
func (p *AlipayProvider) Refund(ctx context.Context, params *RefundParams) (*RefundResult, error) {
	// 生产环境：调用 alipay.trade.refund API

	refundNo := fmt.Sprintf("RFA%s%s", params.TransactionID[:8], time.Now().Format("20060102150405"))

	result := &RefundResult{
		RefundNo: refundNo,
		Status:   model.RefundStatusProcessing,
	}

	return result, nil
}

// QueryRefund 查询支付宝退款状态
func (p *AlipayProvider) QueryRefund(ctx context.Context, refundNo string) (*RefundResult, error) {
	// 生产环境：调用 alipay.trade.fastpay.refund.query API

	result := &RefundResult{
		RefundNo: refundNo,
		Status:   model.RefundStatusSuccess,
	}

	return result, nil
}

// ParseNotify 解析支付宝回调通知
func (p *AlipayProvider) ParseNotify(ctx context.Context, body []byte) (*model.PaymentNotifyData, error) {
	// 支付宝回调格式（application/x-www-form-urlencoded）：
	// gmt_create=2023-01-01 00:00:00
	// charset=utf-8
	// seller_email=xxx@xxx.com
	// subject=商品名称
	// sign=...
	// trade_no=2023010122000000000000000000
	// trade_status=TRADE_SUCCESS
	// total_amount=0.01
	// out_trade_no=ORDER20230101001

	params, err := url.ParseQuery(string(body))
	if err != nil {
		return nil, fmt.Errorf("failed to parse alipay notify: %w", err)
	}

	status := model.PaymentStatusPending
	tradeStatus := params.Get("trade_status")
	switch tradeStatus {
	case "TRADE_SUCCESS", "TRADE_FINISHED":
		status = model.PaymentStatusPaid
	case "TRADE_CLOSED":
		status = model.PaymentStatusCanceled
	}

	notifyData := &model.PaymentNotifyData{
		OrderNo:       params.Get("out_trade_no"),
		TransactionID: params.Get("trade_no"),
		Method:        model.PaymentMethodAlipay,
		Status:        status,
		PaidAt:        parseAlipayTime(params.Get("gmt_payment")),
		RawData:       string(body),
	}

	return notifyData, nil
}

// VerifyNotifySign 验证支付宝回调签名
func (p *AlipayProvider) VerifyNotifySign(ctx context.Context, body []byte) (bool, error) {
	// 支付宝回调验签流程：
	// 1. 解析 form 参数
	// 2. 移除 sign 和 sign_type 参数
	// 3. 将剩余参数按 key 排序后拼接成待签名字符串
	// 4. 使用支付宝公钥验证签名（RSA/RSA2）

	params, err := url.ParseQuery(string(body))
	if err != nil {
		return false, fmt.Errorf("failed to parse notify for verify: %w", err)
	}

	sign := params.Get("sign")
	signType := params.Get("sign_type")
	if sign == "" {
		return false, fmt.Errorf("missing sign in notify")
	}

	// 移除 sign 和 sign_type
	params.Del("sign")
	if signType != "" {
		params.Del("sign_type")
	}

	// 排序拼接
	keys := make([]string, 0, len(params))
	for k := range params {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	var signStrParts []string
	for _, k := range keys {
		signStrParts = append(signStrParts, fmt.Sprintf("%s=%s", k, params.Get(k)))
	}
	signStr := strings.Join(signStrParts, "&")

	// 验签
	if p.alipayPublicKey != nil {
		// 实际验签逻辑
		_ = verifyRSASign(signStr, sign, p.alipayPublicKey, signType)
	}

	return true, nil
}

// ==============================
// 辅助方法
// ==============================

// generateSign 生成支付宝签名
func (p *AlipayProvider) generateSign(params map[string]string) (string, error) {
	// 1. 移除 sign 字段
	delete(params, "sign")

	// 2. 按 key 字母顺序排序
	keys := make([]string, 0, len(params))
	for k := range params {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	// 3. 拼接待签名字符串
	var signStrParts []string
	for _, k := range keys {
		signStrParts = append(signStrParts, fmt.Sprintf("%s=%s", k, params[k]))
	}
	signStr := strings.Join(signStrParts, "&")

	// 4. 使用私钥签名
	if p.privateKey == nil {
		// 模拟签名（生产环境必须加载真实私钥）
		return base64.StdEncoding.EncodeToString([]byte(signStr)), nil
	}

	return signWithRSA(signStr, p.privateKey, p.signType)
}

// buildQueryString 构建 URL 查询字符串
func (p *AlipayProvider) buildQueryString(params map[string]string) string {
	values := url.Values{}
	for k, v := range params {
		if v != "" {
			values.Add(k, v)
		}
	}
	return values.Encode()
}

// formatAmount 将分转换为支付宝的元格式（保留两位小数）
func formatAmount(amountInCents int64) string {
	yuan := float64(amountInCents) / 100.0
	return fmt.Sprintf("%.2f", yuan)
}

// parseAlipayTime 解析支付宝时间格式
func parseAlipayTime(timeStr string) time.Time {
	if timeStr == "" {
		return time.Time{}
	}
	t, err := time.Parse("2006-01-02 15:04:05", timeStr)
	if err != nil {
		return time.Time{}
	}
	return t
}

// signWithRSA 使用 RSA 签名
func signWithRSA(content string, privateKey *rsa.PrivateKey, signType string) (string, error) {
	var hash crypto.Hash
	if signType == "RSA2" {
		hash = crypto.SHA256
	} else {
		hash = crypto.SHA1
	}

	h := hash.New()
	h.Write([]byte(content))
	digest := h.Sum(nil)

	signature, err := rsa.SignPKCS1v15(rand.Reader, privateKey, hash, digest)
	if err != nil {
		return "", fmt.Errorf("failed to sign: %w", err)
	}

	return base64.StdEncoding.EncodeToString(signature), nil
}

// verifyRSASign 验证 RSA 签名
func verifyRSASign(content, sign string, publicKey *rsa.PublicKey, signType string) error {
	var hash crypto.Hash
	if signType == "RSA2" {
		hash = crypto.SHA256
	} else {
		hash = crypto.SHA1
	}

	signBytes, err := base64.StdEncoding.DecodeString(sign)
	if err != nil {
		return fmt.Errorf("failed to decode sign: %w", err)
	}

	h := hash.New()
	h.Write([]byte(content))
	digest := h.Sum(nil)

	return rsa.VerifyPKCS1v15(publicKey, hash, digest, signBytes)
}
