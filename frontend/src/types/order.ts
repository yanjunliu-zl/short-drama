export interface Order {
  id: string
  order_number: string
  user_id: number
  type: OrderType
  status: OrderStatus
  amount: number
  currency: Currency
  description?: string
  metadata?: Record<string, any>
  payment_method?: PaymentMethod
  payment_status: PaymentStatus
  payment_id?: string
  completed_at?: string
  cancelled_at?: string
  created_at: string
  updated_at: string
}

export interface OrderItem {
  id: string
  order_id: string
  product_type: ProductType
  product_id: string
  product_name: string
  quantity: number
  unit_price: number
  total_price: number
  metadata?: Record<string, any>
}

export interface CreateOrderRequest {
  type: OrderType
  items: OrderItemRequest[]
  payment_method?: PaymentMethod
  metadata?: Record<string, any>
}

export interface OrderItemRequest {
  product_type: ProductType
  product_id: string
  quantity: number
  metadata?: Record<string, any>
}

export interface PaymentRequest {
  order_id: string
  payment_method: PaymentMethod
  payment_details?: Record<string, any>
}

export interface PaymentResponse {
  payment_id: string
  order_id: string
  status: PaymentStatus
  amount: number
  currency: Currency
  payment_method: PaymentMethod
  payment_url?: string
  qr_code_url?: string
  created_at: string
}

export interface OrderResponse {
  order: Order
  items: OrderItem[]
  payment?: PaymentResponse
}

export interface OrderListResponse {
  orders: Order[]
  total: number
  page: number
  page_size: number
}

// 枚举类型
export enum OrderType {
  ScriptGeneration = 'script_generation',
  VideoGeneration = 'video_generation',
  Subscription = 'subscription',
  CreditPurchase = 'credit_purchase',
  Custom = 'custom',
}

export enum OrderStatus {
  Pending = 'pending',
  Processing = 'processing',
  Completed = 'completed',
  Cancelled = 'cancelled',
  Refunded = 'refunded',
}

export enum PaymentStatus {
  Pending = 'pending',
  Processing = 'processing',
  Success = 'success',
  Failed = 'failed',
  Refunded = 'refunded',
  Cancelled = 'cancelled',
}

export enum PaymentMethod {
  Alipay = 'alipay',
  WechatPay = 'wechatpay',
  UnionPay = 'unionpay',
  CreditCard = 'credit_card',
  PayPal = 'paypal',
  BankTransfer = 'bank_transfer',
  Balance = 'balance',
}

export enum Currency {
  CNY = 'CNY',
  USD = 'USD',
  EUR = 'EUR',
  JPY = 'JPY',
}

export enum ProductType {
  Script = 'script',
  Video = 'video',
  Subscription = 'subscription',
  Credit = 'credit',
  Service = 'service',
}

// 订阅相关
export interface Subscription {
  id: string
  user_id: number
  plan_id: string
  plan_name: string
  status: SubscriptionStatus
  current_period_start: string
  current_period_end: string
  cancel_at_period_end: boolean
  cancelled_at?: string
  metadata?: Record<string, any>
  created_at: string
  updated_at: string
}

export enum SubscriptionStatus {
  Active = 'active',
  PastDue = 'past_due',
  Cancelled = 'cancelled',
  Expired = 'expired',
}

export interface SubscriptionPlan {
  id: string
  name: string
  description: string
  price_monthly: number
  price_yearly: number
  currency: Currency
  features: string[]
  max_scripts_per_month: number
  max_videos_per_month: number
  max_duration_minutes: number
  priority_support: boolean
  custom_branding: boolean
  is_popular: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}