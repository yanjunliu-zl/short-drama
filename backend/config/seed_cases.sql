-- Seed data for cases (案例广场)
-- Run this after the cases table is created to populate initial data

-- For existing databases, add the author column if not exists:
-- ALTER TABLE cases ADD COLUMN IF NOT EXISTS author VARCHAR(128) DEFAULT '' COMMENT 'author name' AFTER description;

INSERT INTO cases (id, title, description, author, cover_url, genre, tags, status, view_count, like_count, share_count, user_id, created_at, updated_at)
VALUES
('cs_1', '未来都市冒险', '一部关于未来科技与人性冲突的科幻短剧', 'AI创作助手', '0066cc', '科幻', '科幻,冒险,未来', 'published', 1560, 245, 0, 'system', NOW(), NOW()),
('cs_2', '古风爱情传奇', '古代宫廷中的爱恨情仇，精美的服化道设计', '传统编剧师', '34c759', '古风', '古风,爱情,历史', 'published', 980, 189, 0, 'system', NOW(), NOW()),
('cs_3', '悬疑推理剧场', '密室谋杀案的层层解谜，反转不断的剧情', '推理大师', 'ff9500', '悬疑', '悬疑,推理,犯罪', 'published', 2100, 312, 0, 'system', NOW(), NOW()),
('cs_4', '奇幻魔法世界', '魔法学院的新生成长故事，奇幻生物与魔法对决', '奇幻作家', '007aff', '奇幻', '奇幻,魔法,成长', 'published', 1250, 178, 0, 'system', NOW(), NOW()),
('cs_5', '职场奋斗日记', '互联网公司的职场生存法则与团队协作', '职场观察员', '0066cc', '职场', '职场,励志,都市', 'published', 890, 156, 0, 'system', NOW(), NOW()),
('cs_6', '家庭温情小品', '普通家庭中的温馨日常与亲情故事', '生活记录者', 'ff3b30', '家庭', '家庭,温情,生活', 'published', 1100, 198, 0, 'system', NOW(), NOW())
ON DUPLICATE KEY UPDATE
  title = VALUES(title),
  description = VALUES(description),
  author = VALUES(author),
  cover_url = VALUES(cover_url),
  genre = VALUES(genre),
  tags = VALUES(tags),
  status = VALUES(status),
  view_count = VALUES(view_count),
  like_count = VALUES(like_count),
  updated_at = NOW();
