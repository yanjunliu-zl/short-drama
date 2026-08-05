package handler

import (
	"net/http"
	"short-drama-platform/payment-service/internal/svc"
	"time"

	"github.com/zeromicro/go-zero/rest"
	"github.com/zeromicro/go-zero/rest/httpx"
)

// RegisterHandlers 注册支付服务路由
func RegisterHandlers(server *rest.Server, serverCtx *svc.ServiceContext) {
	server.AddRoutes(
		[]rest.Route{
			// 支付订单
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/payments",
				Handler: CreatePaymentHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/payments",
				Handler: ListPaymentsHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/payments/:id",
				Handler: GetPaymentHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/payments/:id/cancel",
				Handler: CancelPaymentHandler(serverCtx),
			},

			// 退款
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/payments/:id/refund",
				Handler: CreateRefundHandler(serverCtx),
			},
			{
				Method:  http.MethodGet,
				Path:    "/api/v1/payments/:id/refund",
				Handler: GetRefundHandler(serverCtx),
			},

			// 支付回调通知
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/payments/wechat/notify",
				Handler: WeChatNotifyHandler(serverCtx),
			},
			{
				Method:  http.MethodPost,
				Path:    "/api/v1/payments/alipay/notify",
				Handler: AlipayNotifyHandler(serverCtx),
			},

			// 健康检查
			{
				Method:  http.MethodGet,
				Path:    "/health",
				Handler: HealthCheckHandler(serverCtx),
			},
		},
	)
}

// HealthCheckHandler 健康检查
func HealthCheckHandler(svcCtx *svc.ServiceContext) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		httpx.OkJsonCtx(r.Context(), w, map[string]interface{}{
			"status":    "healthy",
			"service":   "payment-service",
			"timestamp": time.Now().Unix(),
		})
	}
}
