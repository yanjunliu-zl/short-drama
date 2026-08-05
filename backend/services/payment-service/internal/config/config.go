package config

import (
	"github.com/zeromicro/go-zero/rest"
)

type Config struct {
	rest.RestConf
	Database      DatabaseConfig
	Redis         RedisConfig
	WeChatPay     WeChatPayConfig
	Alipay        AlipayConfig
	JWT           JWTConfig
}

type DatabaseConfig struct {
	Host            string
	Port            int
	User            string
	Password        string
	DBName          string
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime int
	ReadHosts       []string `json:",optional"` // P1: MySQL read replica hosts
}

type RedisConfig struct {
	Host         string
	Port         int
	Password     string
	DB           int
	PoolSize     int
	MinIdleConns int
}

// WeChatPayConfig 微信支付配置
type WeChatPayConfig struct {
	AppID          string // 应用ID
	MchID          string // 商户号
	APIv3Key       string // API v3密钥
	PrivateKeyPath string // 商户私钥证书路径
	SerialNo       string // 商户证书序列号
	NotifyURL      string // 回调通知地址
	ReturnURL      string // 支付完成跳转地址
}

// AlipayConfig 支付宝配置
type AlipayConfig struct {
	AppID            string // 应用ID
	PrivateKey       string // 应用私钥
	AlipayPublicKey  string // 支付宝公钥
	NotifyURL        string // 回调通知地址
	ReturnURL        string // 支付完成跳转地址
	SignType         string // 签名方式，默认 RSA2
}

type JWTConfig struct {
	Secret string
	Expire int64
}
