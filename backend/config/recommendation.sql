-- 用户案例交互记录表 — 推荐系统数据源
CREATE TABLE IF NOT EXISTS user_case_interactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    case_id VARCHAR(64) NOT NULL,
    action_type VARCHAR(20) NOT NULL DEFAULT 'view' COMMENT 'view, like, share',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_action (user_id, action_type),
    INDEX idx_case (case_id),
    INDEX idx_user_time (user_id, created_at),
    UNIQUE KEY uk_user_case_action (user_id, case_id, action_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
