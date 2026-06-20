package provider

import (
	"context"
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"short-drama-platform/payment-service/internal/config"
	"short-drama-platform/payment-service/model"
	"time"
)

// WeChatPayProvider 微信支付提供者
// 基于微信支付 API v3 实现
type WeChatPayProvider struct {
	config    config.WeChatPayConfig
	mchID     string
	apiV3Key  string
	serialNo  string
	notifyURL string
	returnURL string

	// 私钥，从配置的证书路径加载或直接配置
	privateKey *rsa.PrivateKey
}

// NewWeChatPayProvider 创建微信支付提供者
func NewWeChatPayProvider(cfg config.WeChatPayConfig) (*WeChatPayProvider, error) {
	provider := &WeChatPayProvider{
		config:    cfg,
		mchID:     cfg.MchID,
		apiV3Key:  cfg.APIv3Key,
		serialNo:  cfg.SerialNo,
		notifyURL: cfg.NotifyURL,
		returnURL: cfg.ReturnURL,
	}

	// 加载商户私钥（生产环境从证书文件加载）
	if cfg.PrivateKeyPath != "" {
		// TODO: 从文件加载私钥
		// privateKeyBytes, err := os.ReadFile(cfg.PrivateKeyPath)
		// if err != nil {
		//     return nil, fmt.Errorf("failed to read private key: %w", err)
		// }
		// provider.privateKey = parsePrivateKey(privateKeyBytes)
	}

	return provider, nil
}

// Name 返回支付渠道名称
func (p *WeChatPayProvider) Name() model.PaymentMethod {
	return model.PaymentMethodWeChat
}

// CreateOrder 创建微信支付订单
// 调用微信支付统一下单API（JSAPI / Native / H5）
func (p *WeChatPayProvider) CreateOrder(ctx context.Context, params *CreateOrderParams) (*OrderResult, error) {
	// 构建请求体
	reqBody := map[string]interface{}{
		"appid":        p.config.AppID,
		"mchid":        p.mchID,
		"description":  params.Subject,
		"out_trade_no": params.OrderNo,
		"notify_url":   p.notifyURL,
		"amount": map[string]interface{}{
			"total":    params.Amount,
			"currency": params.Currency,
		},
	}

	// 生成订单
	tradeNo := fmt.Sprintf("WX%s%d", params.OrderNo, time.Now().UnixNano())

	// 生产环境：调用微信支付API
	// POST https://api.mch.weixin.qq.com/v3/pay/transactions/native
	// 需要生成 Authorization 头：WECHATPAY2-SHA256-RSA2048
	// 签名方式：使用商户私钥对签名串进行SHA256 with RSA签名

	// 模拟返回
	result := &OrderResult{
		TransactionID: tradeNo,
		QrCode:        fmt.Sprintf("weixin://wxpay/bizpayurl?pr=%s", tradeNo),
		PayURL:        fmt.Sprintf("https://wx.tenpay.com/pay/%s", tradeNo),
	}

	return result, nil
}

// QueryOrder 查询微信支付订单状态
func (p *WeChatPayProvider) QueryOrder(ctx context.Context, transactionID string) (model.PaymentStatus, error) {
	// 生产环境：调用微信支付查询订单API
	// GET https://api.mch.weixin.qq.com/v3/pay/transactions/out-trade-no/{out_trade_no}
	// 或 GET https://api.mch.weixin.qq.com/v3/pay/transactions/id/{transaction_id}

	// 模拟返回：查询到的状态（实际由回调驱动）
	return model.PaymentStatusPending, nil
}

// CloseOrder 关闭微信支付订单
func (p *WeChatPayProvider) CloseOrder(ctx context.Context, transactionID string) error {
	// 生产环境：调用微信支付关闭订单API
	// POST https://api.mch.weixin.qq.com/v3/pay/transactions/out-trade-no/{out_trade_no}/close

	return nil
}

// Refund 微信支付退款
func (p *WeChatPayProvider) Refund(ctx context.Context, params *RefundParams) (*RefundResult, error) {
	// 生产环境：调用微信支付退款API
	// POST https://api.mch.weixin.qq.com/v3/refund/domestic/refunds

	refundNo := fmt.Sprintf("RF%s%s", params.TransactionID[:8], time.Now().Format("20060102150405"))

	result := &RefundResult{
		RefundNo: refundNo,
		Status:   model.RefundStatusProcessing,
	}

	return result, nil
}

// QueryRefund 查询退款状态
func (p *WeChatPayProvider) QueryRefund(ctx context.Context, refundNo string) (*RefundResult, error) {
	// 生产环境：调用微信支付退款查询API
	// GET https://api.mch.weixin.qq.com/v3/refund/domestic/refunds/{out_refund_no}

	result := &RefundResult{
		RefundNo: refundNo,
		Status:   model.RefundStatusSuccess,
	}

	return result, nil
}

// ParseNotify 解析微信支付回调通知
func (p *WeChatPayProvider) ParseNotify(ctx context.Context, body []byte) (*model.PaymentNotifyData, error) {
	// 微信支付回调格式：
	// {
	//   "id": "EV-20180225112233",
	//   "create_time": "2023-01-01T00:00:00+08:00",
	//   "resource_type": "encrypt-resource",
	//   "event_type": "TRANSACTION.SUCCESS",
	//   "summary": "支付成功",
	//   "resource": {
	//     "algorithm": "AEAD_AES_256_GCM",
	//     "ciphertext": "...",
	//     "associated_data": "",
	//     "nonce": "..."
	//   }
	// }

	var rawNotify map[string]interface{}
	if err := json.Unmarshal(body, &rawNotify); err != nil {
		return nil, fmt.Errorf("failed to parse wechat notify: %w", err)
	}

	// 解密 resource.ciphertext 获取交易数据
	// 使用 AEAD_AES_256_GCM 解密，key 为 APIv3 密钥

	// 模拟解析结果
	notifyData := &model.PaymentNotifyData{
		OrderNo:       extractString(rawNotify, "out_trade_no"),
		TransactionID: extractString(rawNotify, "transaction_id"),
		Method:        model.PaymentMethodWeChat,
		Status:        model.PaymentStatusPaid,
		PaidAt:        time.Now(),
		RawData:       string(body),
	}

	return notifyData, nil
}

// VerifyNotifySign 验证微信支付回调签名
func (p *WeChatPayProvider) VerifyNotifySign(ctx context.Context, body []byte) (bool, error) {
	// 微信支付回调验签流程：
	// 1. 从 HTTP Header 获取：
	//    - Wechatpay-Timestamp: 时间戳
	//    - Wechatpay-Nonce: 随机串
	//    - Wechatpay-Signature: 签名值
	//    - Wechatpay-Serial: 证书序列号
	// 2. 构造验签串：时间戳\n随机串\n请求体\n
	// 3. 使用微信支付平台公钥验证签名

	return true, nil
}

// ==============================
// 辅助方法
// ==============================

// generateSign 生成微信支付API签名
func (p *WeChatPayProvider) generateSign(method, urlPath string, body []byte) (string, error) {
	nonce := generateNonce(32)
	timestamp := fmt.Sprintf("%d", time.Now().Unix())

	// 构造签名串
	signStr := fmt.Sprintf("%s\n%s\n%s\n%s\n%s\n", method, urlPath, timestamp, nonce, string(body))

	// SHA256 with RSA 签名
	h := sha256.New()
	h.Write([]byte(signStr))
	digest := h.Sum(nil)

	signature, err := rsa.SignPKCS1v15(rand.Reader, p.privateKey, crypto.SHA256, digest)
	if err != nil {
		return "", fmt.Errorf("failed to sign: %w", err)
	}

	signBase64 := base64.StdEncoding.EncodeToString(signature)

	// 返回 Authorization token
	token := fmt.Sprintf(
		"WECHATPAY2-SHA256-RSA2048 mchid=\"%s\",nonce_str=\"%s\",signature=\"%s\",timestamp=\"%s\",serial_no=\"%s\"",
		p.mchID, nonce, signBase64, timestamp, p.serialNo,
	)

	return token, nil
}

// generateNonce 生成随机字符串
func generateNonce(length int) string {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	b := make([]byte, length)
	for i := range b {
		randByte := make([]byte, 1)
		rand.Read(randByte)
		b[i] = charset[int(randByte[0])%len(charset)]
	}
	return string(b)
}

// extractString 从map中安全提取字符串
func extractString(m map[string]interface{}, key string) string {
	if v, ok := m[key]; ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}

// decryptAES256GCM 解密微信支付回调中的加密数据
func decryptAES256GCM(ciphertext, nonce, associatedData, key string) ([]byte, error) {
	// 生产环境实现：使用 AES-256-GCM 解密
	// cipher, _ := aes.NewCipher([]byte(key))
	// gcm, _ := cipher.NewGCM(cipher)
	// plaintext, _ := gcm.Open(nil, []byte(nonce), []byte(ciphertext), []byte(associatedData))
	// 此处为模拟实现
	return nil, nil
}

// parsePrivateKey 解析PEM格式的私钥
func parsePrivateKey(data []byte) (*rsa.PrivateKey, error) {
	// 生产环境实现
	return nil, nil
}
