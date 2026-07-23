# From Novel to Video: The Agentic AI Harness Pipeline

> A deep dive into how the Short Drama Platform transforms a 200-chapter novel into a complete short drama video series using multi-agent orchestration, industrial RAG, and streaming generation.

---

## Executive Summary

This document traces the complete journey of a novel through the platform's AI pipeline — from raw text to finished video. The pipeline leverages an **Agentic AI Harness** (multi-agent collaboration with tool calling, plan-execute, and self-correction) rather than a traditional linear workflow. Each stage is detailed with exact code paths, data transformations, and architectural decisions.

**Pipeline Overview**: Novel → Chapters → RAG Index → Multi-Agent Script Generation → Scene Extraction → Shot-Level Storyboard → Image Generation → Video Generation → Final Cut

---

## 1. Novel Ingestion & Preparation

### 1.1 Entry Point

The user uploads a novel via the frontend Script page (`Script.tsx`):

```
POST /api/v1/scripts/generate/from-novel
Content-Type: application/json
{
  "title": "Rebirth of the Sword Emperor",
  "novel_content": "...200万字...",
  "theme": "奇幻",
  "length": "长篇",
  "style": "古装风格",
  "pipeline_version": "v2"
}
```

### 1.2 Chapter Detection

The `Novel2ScriptV2Service.split_chapters()` method (`novel2script_v2_service.py:196`) uses regex to detect chapter boundaries:

```python
# Chinese format: 第X回/章/节
pattern_cn = r'(?:^|\n)\s*(?:#{1,6}\s*)?第\s*([一二三四五六七八九十百千\d]+)\s*[回章节]'

# English fallback: Chapter N
pattern_en = r'(?:^|\n)\s*(?:#{1,6}\s*)?Chapter\s+(\d+)'

# De-duplication by chapter number, skip fragments < 50 chars
# Result: 50 chapters with {index, title, content}
```

For a 200-chapter novel, this produces 50 deduplicated chapter entries. Chapters shorter than 50 characters are discarded as noise.

### 1.3 Knowledge Base Construction

The V2 pipeline builds a **dual-index knowledge base** (`_build_knowledge_base`, line 234):

```
Stage 1: Semantic Chunking (_semantic_chunk)
  Input: 50 chapters
  Process:
    1. Split on major scene boundaries (第X章, 【场景】, Scene N)
    2. Within each scene, split on paragraph breaks (\n\n)
    3. Merge small paragraphs into 2048-4096 char chunks
    4. Tag each chunk with metadata:
       {chapter, chapter_title, characters[], timeline, chunk_type, is_scene_boundary}
  Output: ~2000-8000 chunks with metadata

Stage 2: Dual Index (_build_knowledge_base)
  Dense Index:  FAISS + bge-large-zh-v1.5 (semantic similarity)
  Sparse Index: BM25Okapi character-level (exact name/location matching)
  Disk Cache:   {OUTPUT_DIR}/faiss_cache/{md5}.faiss (reuse on re-upload)
```

**Why semantic chunking instead of fixed-size**: A 4096-char fixed window would split dialogue mid-sentence, break scene transitions, and mix characters from different scenes. Semantic chunking preserves narrative coherence by detecting natural breakpoints.

---

## 2. Agentic Harness: Multi-Agent Script Generation

### 2.1 Why Not Linear Workflow?

Traditional linear pipelines process chapters sequentially without feedback. The novel-to-script problem requires:

| Requirement | Linear Pipeline | Agentic Harness |
|-------------|----------------|-----------------|
| Character consistency across 50 chapters | Single-pass generation | ReviewAgent checks → PolishAgent fixes |
| Dialogue authenticity | Static style rules | ScriptAgent can fetch character profiles via tools |
| Plot coherence | Depends on prompt quality | RouterAgent retries on low scores |
| Scene-level quality variation | All chapters same quality | PlanNode decomposes, scores per chapter |

### 2.2 Agent Architecture

The `AgenticOrchestrator` (`agentic_harness.py`) coordinates four specialized agents:

```
┌─────────────────────────────────────────────────────────┐
│                    AgenticOrchestrator                    │
│                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────┐  │
│  │  RouterAgent  │──▶│  PlanNode    │──▶│ ScriptAgent │  │
│  │ (decides next │   │ (decomposes  │   │ (generates  │  │
│  │  action)      │   │  complex     │   │  content)   │  │
│  └──────────────┘   │  tasks)      │   └──────┬──────┘  │
│                      └──────────────┘          │         │
│                                                ▼         │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────┐  │
│  │  RouterAgent  │◀──│ PolishAgent  │◀──│ ReviewAgent │  │
│  │ (retry/done)  │   │ (rewrites    │   │ (scores 5   │  │
│  │               │   │  weak parts) │   │  dimensions)│  │
│  └──────────────┘   └──────────────┘   └─────────────┘  │
│                                                          │
│  Shared Context: {task, content, scores, issues, history} │
│  Tool Registry:  fetch_character, fetch_chapter, search  │
└─────────────────────────────────────────────────────────┘
```

### 2.3 Plan-Execute: Decomposing Complex Tasks

For a 200-chapter novel, a single LLM call cannot process everything. The `PlanNode.decompose()` method breaks the task into sub-tasks:

```
Input: "Generate script for 200-chapter novel 'Rebirth of the Sword Emperor'"

PlanNode.decompose(task, llm, max_steps=8):
  LLM Prompt → JSON array:
  [
    {"step_id": 1, "action": "generate", "description": "Chapters 1-10",
     "depends_on": []},
    {"step_id": 2, "action": "generate", "description": "Chapters 11-20",
     "depends_on": []},     ← parallel with step 1
    {"step_id": 3, "action": "review", "description": "Review chapters 1-20",
     "depends_on": [1, 2]}, ← waits for both
    {"step_id": 4, "action": "polish", "description": "Fix issues in 1-20",
     "depends_on": [3]},
    ...
  ]

Steps with same depends_on run concurrently (asyncio.gather)
Steps with different depends_on run sequentially
```

### 2.4 Tool Calling: Agents Can Access External Data

Each agent has access to a `ToolRegistry`. When the LLM needs external data, it outputs a tool call JSON:

```
ScriptAgent generates a scene. It needs to know the protagonist's personality.
Instead of guessing, it calls:

{"tool": "fetch_character_profile", "args": {"name": "萧炎"}}

The ToolRegistry routes this to _tool_fetch_character():
  → Query character vector store (FAISS)
  → Return: "Character '萧炎': personality=坚韧不拔, role=主角,
              traits=重情义,冷静果断,修炼天赋异禀"

The agent incorporates this into the script.
```

Available tools:
- `fetch_character_profile(name)` — queries character vector store
- `fetch_chapter_context(chapter)` — retrieves specific chapter from RAG
- `search_similar_scripts(query)` — semantic search in script database

### 2.5 Self-Correction Loop

The most powerful feature: agents critique and refine each other:

```
Iteration 1:
  ScriptAgent → generates script for chapters 1-10
  ReviewAgent → scores: {coherence: 7, consistency: 5, dialogue: 6, ...}
              → issues: ["主角性格在第3章突然变暴躁", "第7章对话过于现代"]
              → verdict: "retry"

Iteration 2:
  PolishAgent → receives issues + original content
              → rewrites chapters 3 and 7 specifically
              → preserves all other content unchanged

  ReviewAgent → scores: {coherence: 8, consistency: 8, dialogue: 8, ...}
              → verdict: "pass"

RouterAgent → "done" → return final content
```

The `PromptOptimizer` (`agentic_harness.py:PromptOptimizer`) tracks which prompts produce good scores:

```python
# When a prompt produces low-quality output:
optimizer.record_feedback("ScriptAgent", prompt, score=5.2, output=content)

# When score < 7.0, auto-generate improved prompt:
new_prompt = optimizer.optimize(
    "ScriptAgent", output, issues, target_score=7.5
)
# New prompt now includes: "Ensure character personality remains consistent
# across chapters. Avoid modern colloquialisms in period settings."

# Future iterations use the improved prompt
```

---

## 3. Hybrid RAG Retrieval

### 3.1 Query Rewriting

Before retrieval, the user's intent is expanded (`_rewrite_query`):

```
Input:  "chapter 15, the scene where the protagonist fights the villain"
Output: "检索章节第十五章 主角与反派战斗场景 角色:萧炎,魂天帝
         情感:愤怒 场景类型:action 需要对话原文和动作描写"
```

This structured query improves both BM25 (exact character names) and dense (semantic "fight scene") retrieval.

### 3.2 Dual Retrieval + RRF Fusion

```
Parallel Retrieval:
  Dense: FAISS.similarity_search_with_score(query, k=16)
         → 16 chunks with cosine similarity scores
  Sparse: BM25Okapi.get_scores(tokenized_query)
         → rank all chunks, normalize scores to [0, 1]

RRF Fusion (_rrf_fusion, k=60):
  for each chunk:
    dense_rank = position in dense results
    sparse_rank = position in sparse results
    fused_score = 1/(60+dense_rank+1) + 1/(60+sparse_rank+1)
  sort by fused_score descending

Metadata Filter:
  Only keep chunks where filter_characters appear in chunk text
  Only keep chunks from target chapter (if chapter filter set)

Temporal Sort:
  Sort by chapter index (ascending) so LLM sees plot in order
```

### 3.3 Character Profile Injection

Parallel to RAG retrieval, the character vector store is queried (`_search_characters`):

```
For each character in the current chapter:
  Query: character name
  FAISS similarity search in character profile index
  Result: "角色:萧炎。性格:坚韧不拔,重情义。角色定位:主角。对白风格:沉稳,少言,关键时刻语气坚定"

This profile is injected into the LLM prompt as 【角色档案库】,
ensuring consistent character voice across all 50 chapters.
```

---

## 4. Script Generation Per Chapter

### 4.1 Prompt Assembly

Each chapter's LLM prompt combines 7 context sources:

```
System Prompt: SYSTEM_GENERATE_CHAPTER_V2
  - Role: "顶级影视编剧+分镜师"
  - Format: 场景编号, 场景类型, 地点, 角色, 道具, 分镜表, 剧本正文
  - Requirements: 3-6 scenes, 5:3:2 dialogue:action:environment ratio
  - Mandatory: 【本集钩子】(cliffhanger) at end

Human Prompt: HUMAN_GENERATE_CHAPTER_V2.format(
  global_info       = character graph from all 50 chapters
  story_framework   = episode outline (for outlines) or "" (for novels)
  graphrag_context  = cross-chapter relationship context
  cumulative_context= previous 3 chapter summaries + next preview
  char_profiles     = character profile vector store results
  rag_context       = hybrid RAG retrieval results
  chapter_content   = smart-truncated (first 6000 + last 2000 chars)
  style_rule        = ancient/suspense/comedy dialogue rules
  scene_serial      = "SCENE-015"
  episode_hint      = "这是第15集,共50集"
)
```

### 4.2 Parallel Execution

50 chapters are processed with controlled concurrency:

```python
sem = asyncio.Semaphore(3)  # Max 3 concurrent LLM calls

async def generate_one(i, chapter):
    scene_serial = f"SCENE-{str(i+1).zfill(3)}"
    cumulative_context = build_cumulative_context(summaries, i)
    async with sem:
        return await _generate_chapter_script(
            chapter, global_info, vector_store, style,
            scene_serial, cumulative_context
        )

# Launch all 50, semaphore limits to 3 at a time
tasks = [generate_one(i, ch) for i, ch in enumerate(chapters)]
results = await asyncio.gather(*tasks)
results.sort(key=lambda x: x[0])  # Restore chapter order
```

### 4.3 Output Structure

Each chapter's LLM output follows a strict format parsed by regex:

```
【场景编号】SCENE-015
【场景类型】外景 黄昏
【场景地点】迦南学院后山
【出场角色】萧炎, 药老
【核心道具】玄重尺, 丹药
【分镜明细表】
镜号：1 | 镜头类型：远景 | 运镜：推 | 时长：5s | 画面：后山全景，夕阳余晖
镜号：2 | 镜头类型：中景 | 运镜：固定 | 时长：4s | 画面：萧炎盘坐修炼
镜号：3 | 镜头类型：近景 | 运镜：推 | 时长：3s | 画面：药老出现，面容严肃
【标准化剧本正文】
△后山，夕阳将天边染成金红色。萧炎盘坐在巨石之上，双眼紧闭。
药老：（严肃）你确定要尝试突破斗皇？
萧炎：（睁眼，坚定）弟子已经准备好了。
...
【本集钩子】
△远处，一道黑影悄然接近，手中闪烁着诡异的光芒...
```

---

## 5. Scene Extraction

After all chapters are generated, the `SceneExtractor` service processes the script:

```
POST /api/v1/scenes/
{
  "script_content": "...full script...",
  "extract_type": "all",
  "style": "古装风格"
}

LLM structured extraction → Pydantic models:
  SceneResponse: {scene_id, location, time_of_day, description,
                  characters[], props[], action_summary}
  CharacterResponse: {character_id, name, description, age,
                      personality, clothing, role}
  PropResponse: {prop_id, name, description, category, usage}

Optional: Seedance generates scene preview images for each scene
```

---

## 6. Storyboard Generation

### 6.1 Shot-Level Decomposition

The storyboard service takes the generated script and produces detailed shots:

```
POST /api/v1/storyboard/shots/generate
{
  "title": "Rebirth of the Sword Emperor",
  "script": "...",
  "episodeCount": 50,
  "episodeContents": [...],  // pre-split by episode
  "style": "古装风格",
  "characterNames": ["萧炎", "药老", "魂天帝"],
  "sceneRefs": ["迦南学院", "后山", "魂殿"]
}
```

### 6.2 Five-Layer Cinematography Prompt Builder

Each shot is enriched with `PromptBuilder` (`prompt_builder.py`):

```
Shot: {type: "远景", angle: "仰视", duration: 5, ...}

Layer 1: Camera Design
  "extreme wide shot, low angle looking up, dolly on tracks,
   smooth lateral movement, deep focus"

Layer 1.5: Lighting Design
  "natural daylight, soft ambient illumination, backlight,
   warm temperature 3200K"

Layer 2: Subject & Location
  "location: 迦南学院后山, characters: 萧炎、药老,
   dialogue context: 你确定要尝试突破斗皇？"

Layer 3: Mood & Atmosphere
  "emotional progression: 紧张 → 坚定,
   narrative beat: 关键突破时刻, atmosphere: 雾 (轻微)"

Layer 5: Visual Style
  "visual style: 古装风格"

→ imagePromptZh: "远景, 仰视, 滑轨平滑横移, 深景深,
   自然光, 逆光, 暖色调3200K, 地点:迦南学院后山,
   角色:萧炎 药老, 情绪:紧张→坚定, 雾(轻微),
   风格:古装风格, still frame, sharp focus, high quality"

→ videoPromptZh: (same but with movement keywords:
   "smooth motion, dynamic movement, fluid animation")
```

### 6.3 Cinematography Profiles

17 preset profiles provide baseline visual styles:

```
Style "古装风格" → profile "ancient-palace":
  lighting_style: 逆光
  lighting_direction: 侧光
  color_temperature: 暖色调 3200K
  depth_of_field: 深景深
  atmospheric_effects: 轻微烟雾
  negative_prompt: "modern buildings, cars, phones, technology, neon"

Per-shot fields override profile defaults when LLM provides them
```

---

## 7. Image Generation

### 7.1 Prompt Enhancement

Before sending to Seedance, the `PromptEnhancer` (`prompt_enhancer.py`) uses an LLM to translate Chinese scene descriptions into professional English image prompts:

```
Input:  "古装风格，远景仰视拍摄迦南学院后山，萧炎盘坐修炼"
Output: "Ancient Chinese fantasy palace academy rear mountain at golden hour,
        extreme wide shot, low angle hero perspective, a young cultivator
        with black hair sitting cross-legged in meditation on a massive rock,
        warm golden sunlight streaming through mist, traditional Chinese
        architecture in background, cinematic lighting, shallow depth of field,
        8k resolution, highly detailed, sharp focus, professional photography"
```

### 7.2 Generation Pipeline

```
SeedanceService.generate_image_from_scene():
  1. PromptEnhancer.enhance(description, style)
  2. POST https://ark.cn-beijing.volces.com/api/v3/images/generations
     Body: {"model": "doubao-seedream-4-5-251128",
            "prompt": "...enhanced prompt...",
            "size": "1920x1080", "n": 1}
  3. Retry on 429 (exponential backoff: 2s, 4s, 8s)
  4. Parse response: data[0].url → download → upload to MinIO
  5. Return presigned URL (7-day expiry)
```

### 7.3 Character Consistency

For batch processing, character reference images ensure visual consistency:

```
ShotsToVideoRequest.referenceImages:
  characters: {"萧炎": "http://minio/char_xiaoyan.png",
               "药老": "http://minio/char_yaolao.png"}

For each shot:
  if shot.characters ∩ referenceImages:
    image_prompt += f"。角色视觉参考: 萧炎参考图:{url}, 药老参考图:{url}"

Shared seed per scene:
  scene_seeds[sceneRef] = hash(sceneRef + shot_number) % 2^31
  Same scene → same seed → consistent lighting, color, character position
```

---

## 8. Video Generation

### 8.1 Image-to-Video Pipeline

```
SeedanceService.generate_video():
  1. Download reference image from MinIO URL
  2. Base64-encode as data URI: "data:image/png;base64,..."
  3. POST /contents/generations/tasks
     Body: {
       "model": "doubao-seedance-2-0-260128",
       "content": [
         {"type": "text", "text": "camera slowly pushes in..."},
         {"type": "image_url", "image_url": {"url": "data:..."},
          "role": "first_frame"}
       ],
       "resolution": "720p", "ratio": "16:9",
       "duration": 5, "watermark": false
     }
  4. Poll status: GET /tasks/{task_id} every 2s (max 120 iterations = 4 min)
  5. Success statuses: {succeeded, completed, successful}
  6. Failure → status="image_only" (explicitly marked, not masked as success)

Adaptive Duration:
  dialogue_len = len(shot.dialogue or "")
  duration = max(3, min(15, shot.duration, int(dialogue_len/3) + 3))
  Short dialogue → 3-5s, long dialogue → 8-15s
```

### 8.2 Batch Processing

50 episodes × 6-12 shots = 300-600 shots. Parallel processing within each episode:

```
for episode in episodes:
    sem = asyncio.Semaphore(3)   # Max 3 concurrent per episode
    tasks = [process_one(shot) for shot in episode.shots]
    results = await asyncio.gather(*tasks)

    for result in results:
        yield SSE progress event → frontend real-time progress bar
```

---

## 9. Quality Gates

### 9.1 Content Safety

Before any output reaches the user:

```python
safety = ContentSafetyChecker()
report = safety.check_script(script_content)

Categories checked:
  political: sensitive political terms
  violence: excessive gore description
  adult: inappropriate sexual content
  illegal: crime-inducing content

Score < 80 → rejection warning logged
```

### 9.2 LLM-as-Judge Scoring

Every generated script is evaluated by `QualityJudge`:

```
4 dimensions (0-100 each):
  1. Plot coherence — logical consistency, scene transitions
  2. Character consistency — voice consistency across episodes
  3. Dialogue naturalness — conversational, fits short video
  4. Short-video fitness — fast pacing, visualizable, cliffhangers

Verdict:
  total ≥ 60 → pass
  40 ≤ total < 60 → retry (auto-optimize with feedback)
  total < 40 → reject (flag for manual review)

Retry flow:
  1. Extract weaknesses + suggestions from judge output
  2. Build optimization prompt: "请根据以下评审意见优化..."
  3. PolishAgent rewrites weak chapters
  4. Re-evaluate (max 1 retry)
```

---

## 10. Streaming & Real-Time Feedback

### 10.1 SSE Event Types

```
event: stage
data: {"stage": "构建知识库", "progress": 10}

event: stage
data: {"stage": "提取角色关系图谱", "progress": 30}

event: stage
data: {"stage": "剧本生成 5/50", "progress": 55}

event: progress
data: {"stage": "shot_done", "shot_number": 3,
       "completed": 3, "total": 10, "progress": 35}

event: done
data: {"status": "completed", "result": {...}}

event: error
data: {"error": "...", "code": "TIMEOUT"}
```

### 10.2 Architecture

```
Browser                     Server
  │ POST /generate/from-outline-sync  │
  │ {"stream":true, ...}              │
  │                                    │
  │◄── event: stage ──────────────────┤ FAISS built
  │◄── event: stage ──────────────────┤ Chapters detected
  │◄── event: stage ──────────────────┤ Characters extracted
  │◄── event: stage ──────────────────┤ Generating (5/50)
  │◄── event: stage ──────────────────┤ Entity extraction
  │◄── event: stage ──────────────────┤ Quality review
  │◄── event: done ───────────────────┤ Full result
  │                                    │
  │  Connection closes                 │
```

Implementation uses `StreamingResponse` with `text/event-stream` content type. Each stage callback pushes events via an `asyncio.Queue` bridge.

---

## 11. End-to-End Latency Profile

| Stage | 50-Chapter Novel | 200-Chapter Novel |
|-------|-----------------|-------------------|
| Chapter Detection | 0.1s | 0.3s |
| FAISS Index Build | 30s | 120s |
| Global Character Extraction | 10s | 15s |
| Chapter Summaries | 30s | 120s |
| Script Generation (3 concurrent) | 120s | 480s |
| Entity Extraction | 10s | 15s |
| Quality Gates | 5s | 5s |
| **Total** | **~3.5 min** | **~12.5 min** |

Image/video generation adds 15-30s per shot (5-8s per image, 15-30s per video including polling).

---

## 12. Consistency: How We Keep Everything Coherent

Long-form content production (50+ episodes, 300+ shots) faces one fundamental challenge: **consistency across time and media**. A character must look, sound, and act the same in episode 3 and episode 47. A prop introduced in chapter 7 must reappear correctly in chapter 30. A cliffhanger in episode 15 must pay off in episode 16.

Our platform enforces consistency across **four dimensions** through a layered defense strategy.

### 12.1 Plot Consistency (Narrative Level)

**Problem**: When 50 chapters are generated in parallel (Semaphore=3), chapter 15 might have the protagonist in Beijing, while chapter 16 (generated simultaneously) has them in Shanghai with no explanation.

**Solution**: Cumulative Context Injection (`_build_cumulative_context`)

```
Before parallel generation:
  Stage 3c: Serial chapter summarization (30s per chapter, lightweight LLM)
  Chapter 1: "萧炎在迦南学院突破斗皇 → 魂殿来袭"
  Chapter 2: "萧炎击退魂殿使者 → 得知药老被囚"
  ...

During chapter 5 generation:
  Prompt includes:
    【前情提要】
    第2章: 萧炎击退魂殿使者 → 得知药老被囚
    第3章: 萧炎前往中州 → 结识风尊者
    第4章: 抵达丹塔 → 参加炼药师大会
    【下集预告】第6章: 决赛对阵魂殿天才

  This ensures chapter 5's content connects coherently from chapter 4
  and sets up chapter 6 — even though all three were generated in parallel.
```

**Defense Layers**:

| Layer | Mechanism | When |
|-------|-----------|------|
| Prompt-level | 前情提要 (last 3 chapters) + 下集预告 (next chapter) | Every chapter generation |
| Knowledge Graph | GraphRAG cross-chapter entity relationships | Injected as context when available |
| Agentic Review | ReviewAgent checks plot coherence across scenes | After each batch generation |
| Auto-retry | PolishAgent rewrites inconsistent chapters | On ReviewAgent score < 7.0 |

### 12.2 Character Consistency (Personality Level)

**Problem**: In chapter 3 the protagonist speaks 3 sentences calmly. In chapter 8, the same character suddenly becomes verbose and emotional with no character development arc to justify it.

**Solution**: Independent Character Vector Store (`_build_character_store`)

```
Global character extraction (Stage 3):
  LLM reads entire novel → structured output:
    {name: "萧炎", personality: "坚韧不拔,重情义,冷静果断",
     role: "主角", speech_style: "沉稳,少言,关键时语气坚定"}

  Each character profile is embedded and stored in a separate FAISS index.

Per-chapter injection (Stage 4):
  For chapter 15, characters present: ["萧炎", "风尊者", "慕骨老人"]
  → _search_characters(["萧炎", "风尊者", "慕骨老人"])
  → Returns combined profiles:
    "角色:萧炎。性格:坚韧不拔,重情义。角色定位:主角。对白风格:沉稳,少言..."
    "角色:风尊者。性格:老练圆滑,亦正亦邪。角色定位:配角。对白风格:话多带刺..."
  → Injected into prompt as 【角色档案库】

  The LLM now has character-specific voice instructions for every line of dialogue.
```

**Defense Layers**:

| Layer | Mechanism | When |
|-------|-----------|------|
| Global extraction | LLM extracts personality + speech style per character | Once, after chapter detection |
| Vector store | FAISS index of all character profiles | Once, before generation |
| Per-chapter lookup | _search_characters() retrieves profiles for current scene | Every chapter |
| Agentic Review | ReviewAgent scores "Character Consistency" dimension | After each batch |
| PromptOptimizer | Auto-adjusts system prompt to emphasize voice consistency | When score drops below 7.0 |

### 12.3 Visual Consistency (Image/Video Level)

**Problem**: Shot 3 and shot 7 are the same scene (迦南学院后山 at sunset), but the AI generates them with different lighting, color temperature, and background details — breaking visual continuity.

**Solution**: Shared Seed per Scene + Cinematography Profiles

```
Per-Scene Seed Sharing:
  scene_seeds = {}
  For each shot:
    sceneRef = shot.sceneRef  # "迦南学院后山"
    if sceneRef not in scene_seeds:
      scene_seeds[sceneRef] = hash(sceneRef + shot_number) % 2^31
    seed = scene_seeds[sceneRef]
    # All shots in the same scene use the same seed
    # → Same lighting, color grading, background composition

Cinematography Profile Baseline:
  Style "古装风格" → Profile "ancient-palace":
    lighting_style: 逆光
    color_temperature: 暖色调 3200K
    depth_of_field: 深景深
    atmospheric_effects: 轻微烟雾

  Per-shot LLM-generated fields override profile when needed:
    Shot 1 (对话): lighting_style=三点布光 (overrides profile for indoor dialogue)
    Shot 2 (远景): uses profile default (逆光 for outdoor establishing shot)

Style-Specific Negative Prompts:
  ancient-palace → "modern buildings, cars, phones, technology, neon"
  Prevents anachronistic elements from appearing in historical scenes
```

**Defense Layers**:

| Layer | Mechanism | When |
|-------|-----------|------|
| Scene seed | hash(sceneRef + shot) → shared seed | Per-shot image generation |
| Cinematography profiles | 17 presets as baselines | All shots in same style |
| Per-shot differentiation | LLM-generated lighting/camera fields | LLM output during storyboard |
| Style negatives | Profile-specific exclusion list | Per-shot image prompt |
| Reference images | Character portrait URL injection | When available, per-shot |

### 12.4 Cross-Media Consistency (Script→Image→Video)

**Problem**: A scene described as "rainy night" in the script gets generated as a sunny day image because the image prompt lost the weather context during translation.

**Solution**: PromptBuilder 5-Layer Enrichment

```
Script text: "△暴雨夜的废弃工厂, 萧炎全身湿透潜入"

PromptBuilder processes this into structured layers:
  Layer 1 (Camera): "medium shot, eye-level, handheld"
  Layer 1.5 (Lighting): "lightning flashes, harsh shadows, cool temperature 5600K"
  Layer 2 (Subject): "location: 废弃工厂, character: 萧炎, action: 潜入"
  Layer 3 (Mood): "emotional progression: 紧张 → 警惕, atmosphere: 暴雨 (强烈)"
  Layer 5 (Style): "visual style: 古装风格"

→ imagePromptZh: "中景, 平视, 手持, 闪电照明, 冷色调5600K,
   地点:废弃工厂, 角色:萧炎, 情绪:紧张→警惕,
   暴雨(强烈), 风格:古装风格, still frame, sharp focus"

The weather, location, mood, and action from the script are all preserved
in mandatory structured layers — the image model cannot "forget" them.
```

**Defense Layers**:

| Layer | Mechanism | What It Preserves |
|-------|-----------|-------------------|
| PromptBuilder | 5-layer structured prompt | Weather, location, mood, action, characters |
| PromptEnhancer | LLM translates CN→EN with detail preservation | Composition, lighting, quality keywords |
| Metadata tagging | chunk_type, characters, timeline | Enables retrieval with contextual awareness |
| RAG retrieval | Hybrid search with character filter | Ensures image prompt has full scene context |
| Quality gates | LLM-as-Judge evaluates consistency | Catches discrepancies before delivery |

### 12.5 Consistency Architecture Summary

```
┌──────────────────────────────────────────────────────────────┐
│                   CONSISTENCY LAYERS                          │
├──────────────┬──────────────┬──────────────┬────────────────┤
│   PLOT       │  CHARACTER   │   VISUAL     │  CROSS-MEDIA   │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ Cumulative   │ Character    │ Scene Seed   │ 5-Layer        │
│ Context      │ Vector Store │ Sharing      │ PromptBuilder  │
│ (前情提要)    │ (档案库)      │ (shared seed)│ (structured)   │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ GraphRAG     │ Per-chapter  │ 17 Profiles  │ PromptEnhancer │
│ Knowledge    │ FAISS lookup │ + Overrides  │ (CN→EN)        │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ ReviewAgent  │ ReviewAgent  │ Style        │ RAG Context    │
│ Coherence    │ Consistency  │ Negatives    │ Injection      │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ PolishAgent  │ PromptOpt    │ Reference    │ Quality Gates  │
│ Auto-retry   │ Auto-tune    │ Images       │ Judge Check    │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

---

## 13. Key Architectural Decisions

| Decision | Choice | Impact |
|----------|--------|--------|
| Agentic over Linear | Multi-agent with RouterAgent | Self-correcting, quality-gated output |
| Semantic over Fixed Chunking | Scene-boundary detection | Preserves narrative coherence |
| Dual Retrieval | Dense + Sparse + RRF | Both semantic meaning and exact name matching |
| Character Vector Store | Separate FAISS index | Consistent character voice across 50+ chapters |
| SSE over Polling | Single-endpoint dual-mode | Backward compatible, real-time UX |
| Shared Seed per Scene | hash(sceneRef + shot) | Cross-shot visual consistency |
| Adaptive Video Duration | dialogue_len / 3 + 3 | Content-appropriate timing |

---

*Document version: 1.0 | Last updated: 2026-07-23*
