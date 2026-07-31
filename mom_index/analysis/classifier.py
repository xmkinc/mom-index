"""Deterministic keyword classifier for Mom Index posts."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .signals import (
    BUY_KEYWORDS,
    NEWBIE_KEYWORDS,
    NEWBIE_SIGNALS,
    PLATFORM_COMPOUND_OVERRIDES,
    PLATFORM_KEYWORD_EXTENSIONS,
    PRO_KEYWORDS,
    PRO_SIGNALS,
    SELL_KEYWORDS,
)


# ============================================================
# 分析引擎
# ============================================================

@dataclass
class AnalysisResult:
    """单条帖子的完整分析结果"""
    post_id: str
    title: str
    platform: str
    sector: str
    source_url: str = ""
    
    # 分数
    newbie_score: float = 0.0       # 小白总分 (0-100)
    newbie_confidence: str = "low"   # 置信度: high/medium/low
    
    # 命中信号
    matched_newbie: List[Tuple[str, str, float]] = field(default_factory=list)  
    matched_pro: List[Tuple[str, str, float]] = field(default_factory=list)
    matched_extension_signals: List[Tuple[str, str, float]] = field(default_factory=list)

    # 内容深度
    has_content: bool = False
    
    # 判定
    level: str = "未判定"      # 纯小白/偏小白/中间派/偏专业/专业
    reasoning: str = ""        # 人类可读的推理过程
    sentiment_score: float = 0  # -1(恐慌) ~ +1(贪婪)
    intent: str = "neutral"     # buy/sell/neutral — 买入/卖出意图
    intent_strength: float = 0  # 0~1 意图强度
    
    # 用于前端展示
    key_signals: List[str] = field(default_factory=list)


# 垃圾/活动帖过滤模式（与 scoring.py 的 spam 判定保持同步）
_SPAM_PATTERNS = [
    "我是冲着金条来的",
    "金条来的，你呢",
    "领金条",
    "签到",
    "打卡",
    "广告",
]


def _is_spam(full_text: str) -> str | None:
    """Return the matched spam pattern if the post should be filtered."""
    for spam in _SPAM_PATTERNS:
        if spam in full_text:
            return spam
    return None


def _get_keywords_for_platform(platform: str):
    """Return effective keyword tables and the raw extension tables for a platform."""
    newbie_ext = dict(PLATFORM_KEYWORD_EXTENSIONS.get(platform, {}).get("newbie", {}))
    buy_ext = list(PLATFORM_KEYWORD_EXTENSIONS.get(platform, {}).get("buy", []))
    sell_ext = list(PLATFORM_KEYWORD_EXTENSIONS.get(platform, {}).get("sell", []))

    newbie = {
        name: list(kws) + newbie_ext.get(name, [])
        for name, kws in NEWBIE_KEYWORDS.items()
    }
    pro = {name: list(kws) for name, kws in PRO_KEYWORDS.items()}
    buy = list(BUY_KEYWORDS) + buy_ext
    sell = list(SELL_KEYWORDS) + sell_ext

    return newbie, pro, buy, sell, newbie_ext, buy_ext, sell_ext


def _detect_compound_overrides(
    text: str,
    compound_overrides: List[Tuple[str, str]],
) -> Tuple[List[str], str]:
    """Detect ordered longest-match compound overrides.

    Returns a list of matched compound strings and a masked copy of ``text``
    where matched compounds are replaced with spaces so inner keywords do not
    contribute to ordinary intent/sentiment matching.
    """
    matched: List[str] = []
    masked_chars = list(text)
    # Compounds are already ordered longest-first.
    for compound, _side in compound_overrides:
        start = 0
        while True:
            idx = text.find(compound, start)
            if idx == -1:
                break
            matched.append(compound)
            for i in range(idx, idx + len(compound)):
                masked_chars[i] = " "
            start = idx + len(compound)
    return matched, "".join(masked_chars)


def analyze_post(post: Dict, sector: str) -> AnalysisResult:
    """分析单条帖子，返回详细判定"""
    title = post.get("title", "")
    content = post.get("content", "")
    platform = post.get("platform", "unknown")
    full_text = f"{title} {content}" if content else title
    has_content = bool(content and content.strip())
    
    # 0. 垃圾过滤 — 提前返回，不进入任何信号/意图/情绪计算
    spam = _is_spam(full_text)
    if spam:
        return AnalysisResult(
            post_id=post.get("id", ""),
            title=title[:80],
            platform=platform,
            sector=sector,
            source_url=post.get("url", ""),
            has_content=has_content,
            newbie_score=0,
            newbie_confidence="high",
            level="垃圾帖",
            reasoning=f"检测到垃圾/活动帖（命中: 「{spam}」），已过滤，不计入指数。",
        )
    
    result = AnalysisResult(
        post_id=post.get("id", ""),
        title=title[:80],
        platform=platform,
        sector=sector,
        source_url=post.get("url", ""),
        has_content=has_content,
    )
    
    # Select platform-scoped keyword tables.
    (
        newbie_keywords,
        pro_keywords,
        buy_keywords,
        sell_keywords,
        newbie_ext,
        buy_ext,
        sell_ext,
    ) = _get_keywords_for_platform(platform)
    compound_overrides = PLATFORM_COMPOUND_OVERRIDES.get(platform, [])

    # 1. 逐信号匹配（含平台扩展）
    matched_newbie = []
    matched_pro = []
    matched_extensions = []
    
    for signal in NEWBIE_SIGNALS:
        keywords = newbie_keywords.get(signal.name, [])
        matched_kws = [kw for kw in keywords if kw.lower() in full_text.lower()]
        if matched_kws:
            matched_newbie.append((signal.name, signal.description, signal.weight, matched_kws))
        # Track platform-specific extension hits separately.
        ext_matched = [kw for kw in newbie_ext.get(signal.name, []) if kw.lower() in full_text.lower()]
        if ext_matched:
            matched_extensions.append((signal.name, signal.description, signal.weight))
    
    for signal in PRO_SIGNALS:
        keywords = pro_keywords.get(signal.name, [])
        matched_kws = [kw for kw in keywords if kw.lower() in full_text.lower()]
        if matched_kws:
            matched_pro.append((signal.name, signal.description, signal.weight, matched_kws))
    
    # 2. 额外特征
    # 标题长度很短 + 情绪化
    extra_score = 0
    extra_reasons = []
    
    if len(title) < 12 and any(kw in title for kw in ["涨", "跌", "买", "卖"]):
        extra_score += 3
        extra_reasons.append("标题极短+情绪化，典型小白特征")
    
    if title.endswith("吗") or title.endswith("呢") or title.endswith("？"):
        extra_score += 2
        extra_reasons.append("以问句结尾，在寻求答案")
    
    # 3. 计算总分
    total_newbie = sum(s[2] for s in matched_newbie) + extra_score
    total_pro = abs(sum(s[2] for s in matched_pro))
    
    raw_score = total_newbie - total_pro * 0.8  # 专业信号打8折
    result.newbie_score = max(0, min(100, raw_score * 4 + 10))
    
    # 4. 置信度
    total_signals = len(matched_newbie) + len(matched_pro)
    if total_signals >= 4:
        result.newbie_confidence = "high"
    elif total_signals >= 2:
        result.newbie_confidence = "medium"
    else:
        result.newbie_confidence = "low"
    
    # 5. 判定等级
    s = result.newbie_score
    if s >= 50:
        result.level = "纯小白"
    elif s >= 35:
        result.level = "偏小白"
    elif s >= 20:
        result.level = "中间派"
    elif s >= 10:
        result.level = "偏专业"
    else:
        result.level = "专业投资者"
    
    # 6. 生成推理文本
    result.reasoning = _generate_reasoning(
        title, matched_newbie, matched_pro, extra_reasons,
        total_newbie, total_pro, result
    )
    
    # 7. 复合覆盖：在普通意图/情绪匹配前评估有序最长匹配覆盖。
    compound_matches, masked_text = _detect_compound_overrides(
        full_text,
        compound_overrides,
    )
    # Count actual matched compounds per side.
    compound_buy = 0
    compound_sell = 0
    for compound, side in compound_overrides:
        count = compound_matches.count(compound)
        if side == "buy":
            compound_buy += count
        elif side == "sell":
            compound_sell += count

    # 8. 情绪分析（在已屏蔽复合覆盖的文本上进行）
    result.sentiment_score = _analyze_sentiment(masked_text)
    # Compound overrides contribute panic/fear sentiment directly.
    if compound_sell:
        result.sentiment_score = _blend_sentiment(result.sentiment_score, -0.5)

    # 9. 买入/卖出意图判定（在已屏蔽复合覆盖的文本上进行）
    # 同一关键词只计一次，避免子串/重叠关键词的重复计数
    buy_matches = {kw for kw in buy_keywords if kw in masked_text}
    sell_matches = {kw for kw in sell_keywords if kw in masked_text}

    # Track platform-specific buy/sell extension hits.
    for kw in buy_ext:
        if kw in masked_text:
            matched_extensions.append(("buy", kw, 0.0))
    for kw in sell_ext:
        if kw in masked_text:
            matched_extensions.append(("sell", kw, 0.0))

    # Add compound override contributions to intent counts.
    buy_count = len(buy_matches) + compound_buy
    sell_count = len(sell_matches) + compound_sell
    
    # 确定性 tie 处理：买卖信号数相等时为 neutral
    if buy_count > sell_count:
        result.intent = "buy"
        result.intent_strength = min(1.0, buy_count / 5)
    elif sell_count > buy_count:
        result.intent = "sell"
        result.intent_strength = min(1.0, sell_count / 5)
    else:
        result.intent = "neutral"
        result.intent_strength = 0
    
    # 10. 关键信号摘要（用于前端卡片）
    result.key_signals = []
    for name, desc, weight, kws in matched_newbie[:3]:
        result.key_signals.append(f"「{name}」{desc} (命中: {', '.join(kws[:2])})")
    for name, desc, weight, kws in matched_pro[:2]:
        result.key_signals.append(f"「{name}」{desc} (命中: {', '.join(kws[:2])})")
    
    result.matched_newbie = [(n, d, w) for n, d, w, _ in matched_newbie]
    result.matched_pro = [(n, d, w) for n, d, w, _ in matched_pro]
    result.matched_extension_signals = matched_extensions
    
    return result


def _generate_reasoning(
    title: str,
    matched_newbie: List[Tuple],
    matched_pro: List[Tuple],
    extra_reasons: List[str],
    total_newbie: float,
    total_pro: float,
    result: AnalysisResult,
) -> str:
    """生成人类可读的推理文本"""
    parts = []
    
    # 开头
    parts.append(f"帖子「{title[:40]}...」")
    
    if not matched_newbie and not matched_pro:
        parts.append("未命中明确的信号词，内容较短或信息不足。")
        parts.append("根据有限信息判定为中间派。")
        return " ".join(parts)
    
    # 小白信号
    if matched_newbie:
        signal_descs = [f"{name}({weight}分)" for name, desc, weight, kws in matched_newbie]
        parts.append(f"命中{len(matched_newbie)}个小信号: {', '.join(signal_descs)}。")
    
    # 专业信号
    if matched_pro:
        signal_descs = [f"{name}({weight}分)" for name, desc, weight, kws in matched_pro]
        parts.append(f"命中{len(matched_pro)}个专业信号: {', '.join(signal_descs)}。")
    
    # 额外
    if extra_reasons:
        parts.extend(extra_reasons)
    
    # 结论
    parts.append(f"综合得分{result.newbie_score}分，")
    parts.append(f"判定为「{result.level}」")
    parts.append(f"(置信度: {result.newbie_confidence})。")
    
    return " ".join(parts)


def _analyze_sentiment(text: str) -> float:
    """情绪分析: -1(恐慌) ~ +1(贪婪)"""
    greed_words = ["冲", "梭哈", "稳赚", "必涨", "躺赚", "满仓", "抄底", "起飞", "暴涨", "翻倍", "赚了", "盈利"]
    fear_words = ["割肉", "止损", "亏", "跌惨", "暴跌", "崩盘", "完了", "套牢", "深套", "亏了", "赔了", "大跌"]
    
    greed = sum(1 for w in greed_words if w in text)
    fear = sum(1 for w in fear_words if w in text)
    
    total = greed + fear
    if total == 0:
        return 0.0
    return round((greed - fear) / total, 2)


def _blend_sentiment(base: float, override: float) -> float:
    """Blend ordinary sentiment with a compound-override sentiment nudge."""
    # Weight the override at 0.4 so it is visible but does not dominate completely.
    blended = base * 0.6 + override * 0.4
    return round(max(-1.0, min(1.0, blended)), 2)


# ============================================================
# 批量分析
# ============================================================

def dedupe_posts(posts: List[Dict]) -> List[Dict]:
    """按稳定 id 去重，保留首次出现顺序。"""
    seen: set[str] = set()
    result: List[Dict] = []
    for post in posts:
        post_id = str(post.get("id", ""))
        if not post_id or post_id in seen:
            continue
        seen.add(post_id)
        result.append(post)
    return result


def analyze_sector(posts: List[Dict], sector: str) -> List[AnalysisResult]:
    """分析一个板块的所有帖子，按稳定身份去重。"""
    unique_posts = dedupe_posts(posts)
    results = [analyze_post(post, sector) for post in unique_posts]
    
    # 按小白分数降序，分数相同按 post_id 升序以保证确定性
    results.sort(key=lambda r: (-r.newbie_score, r.post_id))
    return results


def analyze_all(sector_data: Dict[str, List[Dict]]) -> Dict[str, List[AnalysisResult]]:
    """分析所有板块"""
    all_results = {}
    for sector, posts in sector_data.items():
        print(f"  分析 {sector}: {len(posts)} 条帖子...")
        all_results[sector] = analyze_sector(posts, sector)
    return all_results
