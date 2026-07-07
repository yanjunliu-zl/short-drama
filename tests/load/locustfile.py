"""
全链路压测 — Short Drama Platform AI 服务

用法:
    pip install locust
    locust -f tests/load/locustfile.py --host=http://localhost:80

场景:
    1. 浏览首页案例    — 5000 RPS (轻量)
    2. 搜索            — 2000 RPS
    3. 剧本生成        — 50 RPS (AI 重负载)
    4. 分镜生成        — 30 RPS
    5. 图像生成        — 20 RPS
    6. 推荐            — 1000 RPS
    7. 全链路串联      — 10 RPS (剧本→分镜→图像→视频)
"""
import random
import time
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


# 测试数据池
OUTLINES = [
    "一个复仇故事，主角回到故乡发现一切已变",
    "都市白领意外穿越到古代成为王妃",
    "AI 觉醒后帮助人类解决全球危机",
    "悬疑推理：连环案件背后的惊天阴谋",
    "武林高手在现代都市的搞笑日常",
]

THEMES = ["爱情", "悬疑", "科幻", "奇幻", "复仇", "成长"]
STYLES = ["写实风格", "浪漫喜剧", "悬疑风格", "古装风格", "科幻风格"]
LENGTHS = ["短篇", "中篇", "长篇"]


class ShortDramaUser(HttpUser):
    """模拟真实用户行为: 浏览→搜索→生成→查看"""

    wait_time = between(1, 5)

    def on_start(self):
        self.user_id = f"loadtest-user-{random.randint(1, 100000)}"

    # ═══════════════════════════════════════════
    # 轻量级: 浏览 + 搜索 (占比 70%)
    # ═══════════════════════════════════════════

    @task(30)
    def browse_cases(self):
        """浏览案例广场"""
        page = random.randint(1, 10)
        with self.client.get(
            f"/api/v1/cases?page={page}&pageSize=20&sortBy=views",
            name="GET /cases",
            catch_response=True,
        ) as r:
            if r.status_code != 200:
                r.failure(f"Status {r.status_code}")

    @task(15)
    def search_cases(self):
        """搜索案例"""
        query = random.choice(["总裁", "穿越", "悬疑", "甜宠", "复仇"])
        with self.client.get(
            f"/api/v1/cases/search?q={query}",
            name="GET /cases/search",
            catch_response=True,
        ) as r:
            if r.status_code != 200:
                r.failure(f"Status {r.status_code}")

    @task(15)
    def get_recommendations(self):
        """获取个性化推荐"""
        with self.client.get(
            f"/api/v1/recommendations/recommend?user_id={self.user_id}&limit=10",
            name="GET /recommendations",
            catch_response=True,
        ) as r:
            if r.status_code != 200:
                r.failure(f"Status {r.status_code}")

    # ═══════════════════════════════════════════
    # 中量级: 分镜 + 场景提取 (占比 20%)
    # ═══════════════════════════════════════════

    @task(8)
    def extract_scenes(self):
        """场景提取"""
        script = f"第一集\n\n**1-1 日 内 咖啡馆**\n人物：主角A、配角B\n△阳光明媚的午后\n主角A：（微笑）好久不见\n"
        with self.client.post(
            "/api/v1/scenes/",
            json={"script_content": script, "extract_type": "all"},
            name="POST /scenes",
            catch_response=True,
        ) as r:
            if r.status_code not in (200, 202):
                r.failure(f"Status {r.status_code}")

    @task(5)
    def generate_storyboard(self):
        """分镜生成"""
        script = "第一集\n\n**1-1 日 内 办公室**\n人物：主角\n△主角走进办公室\n主角：开始吧\n"
        with self.client.post(
            "/api/v1/storyboard/generate",
            json={"title": "测试分镜", "script": script, "theme": "悬疑", "style": "写实风格"},
            name="POST /storyboard/generate",
            catch_response=True,
        ) as r:
            if r.status_code not in (200, 202):
                r.failure(f"Status {r.status_code}")

    # ═══════════════════════════════════════════
    # 重量级: AI 剧本生成 (占比 10%)
    # ═══════════════════════════════════════════

    @task(4)
    def generate_script_sync(self):
        """同步剧本生成 (V2 pipeline)"""
        outline = random.choice(OUTLINES)
        theme = random.choice(THEMES)
        style = random.choice(STYLES)
        length = random.choice(LENGTHS)

        with self.client.post(
            "/api/v1/scripts/generate/from-outline-sync",
            json={
                "title": f"压测剧本-{int(time.time())}",
                "outline": outline,
                "theme": theme,
                "style": style,
                "length": length,
                "user_id": self.user_id,
            },
            name="POST /scripts/generate/from-outline-sync",
            timeout=120,  # 2 min timeout for AI generation
            catch_response=True,
        ) as r:
            if r.status_code != 200:
                r.failure(f"Status {r.status_code}: {r.text[:200]}")

    @task(2)
    def generate_script_stream(self):
        """流式剧本生成"""
        with self.client.post(
            "/api/v1/scripts/generate/from-outline-sync",
            json={
                "title": f"流式压测-{int(time.time())}",
                "outline": random.choice(OUTLINES),
                "theme": random.choice(THEMES),
                "stream": True,
                "length": "短篇",
                "user_id": self.user_id,
            },
            name="POST /scripts/generate/from-outline-sync (stream)",
            timeout=120,
            catch_response=True,
        ) as r:
            if r.status_code != 200:
                r.failure(f"Status {r.status_code}")

    @task(1)
    def generate_image(self):
        """AI 图像生成"""
        with self.client.post(
            "/api/v1/llmhua/images/generate",
            json={
                "scene_description": "古代宫殿，金碧辉煌，阳光透过窗棂",
                "storyboard_id": "loadtest-sb-1",
                "scene_number": 1,
                "style": "古装风格",
            },
            name="POST /llmhua/images/generate",
            timeout=120,
            catch_response=True,
        ) as r:
            if r.status_code not in (200, 202):
                r.failure(f"Status {r.status_code}")


# ═══════════════════════════════════════════
# 压测事件回调
# ═══════════════════════════════════════════

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("=" * 60)
    print("Short Drama Platform — 全链路压测")
    print(f"目标: {environment.host}")
    print(f"用户数: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats
    print("\n" + "=" * 60)
    print("压测完成 — 汇总")
    print(f"总请求: {stats.total.num_requests}")
    print(f"失败: {stats.total.num_failures}")
    print(f"平均响应: {stats.total.avg_response_time:.0f}ms")
    print(f"P50: {stats.total.get_response_time_percentile(0.5):.0f}ms")
    print(f"P95: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"P99: {stats.total.get_response_time_percentile(0.99):.0f}ms")
    print(f"RPS: {stats.total.total_rps:.1f}")
    print("=" * 60)

    # Per-endpoint breakdown
    print("\n端点详情:")
    for name, stat in stats.entries.items():
        if stat.num_requests > 0:
            print(f"  {name}: {stat.num_requests} reqs, "
                  f"avg={stat.avg_response_time:.0f}ms, "
                  f"fail={stat.num_failures}/{stat.num_requests}")


# ═══════════════════════════════════════════
# 混沌工程 — 故障注入
# ═══════════════════════════════════════════

class ChaosMonkey:
    """故障注入器 — 模拟生产环境异常"""

    @staticmethod
    def inject_latency(base_delay: float = 0, jitter: float = 0.5) -> float:
        """注入随机网络延迟"""
        import random
        return base_delay + random.uniform(0, jitter)

    @staticmethod
    def inject_error(error_rate: float = 0.01) -> bool:
        """按概率注入错误"""
        import random
        return random.random() < error_rate

    @staticmethod
    def simulate_cold_start():
        """模拟冷启动延迟"""
        time.sleep(random.uniform(0.1, 2.0))
