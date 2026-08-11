// Package middleware provides shared HTTP middleware for go-zero services.
package middleware

import (
	"net/http"
	"strings"

	"github.com/zeromicro/go-zero/core/logx"
)

const (
	// HeaderTraceParent is the W3C TraceContext header propagated by APISIX opentelemetry plugin.
	HeaderTraceParent = "traceparent"
	// HeaderXRequestID is APISIX's injected request-id header (fallback).
	HeaderXRequestID = "x-request-id"
)

// LogFieldKeyTraceID is the log context key for trace_id.
const LogFieldKeyTraceID = "trace_id"

// TraceMiddleware extracts trace context from incoming request headers and
// injects trace_id into the go-zero logx context so all downstream log calls
// (via logx.WithContext) automatically include the trace identifier.
func TraceMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		traceID := extractTraceID(r)
		ctx := logx.ContextWithFields(r.Context(), logx.Field(LogFieldKeyTraceID, traceID))
		next(w, r.WithContext(ctx))
	}
}

// extractTraceID extracts trace_id from headers with the following priority:
// 1. W3C traceparent (format: 00-{trace_id}-{span_id}-{flags})
// 2. x-request-id (APISIX injected)
// 3. Empty string (no trace context available)
func extractTraceID(r *http.Request) string {
	// 1. Try W3C traceparent header
	if tp := r.Header.Get(HeaderTraceParent); tp != "" {
		// Format: 00-0af7651916f3d2b26d7c90a06e0b1a2e-...-...
		parts := strings.Split(tp, "-")
		if len(parts) >= 2 && len(parts[1]) == 32 {
			return parts[1]
		}
	}

	// 2. Fallback: APISIX x-request-id
	if xrid := r.Header.Get(HeaderXRequestID); xrid != "" {
		return xrid
	}

	// 3. No trace context
	return ""
}
