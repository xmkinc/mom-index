"""Deterministic Mom Index scoring."""

from typing import Dict, List


def compute_sector_index(analysis_results: List) -> Dict:
    """
    计算单个板块的宝妈指数 (0-100)
    
    四个维度:
    1. 小白占比 (40%) — 该板块中小白帖的比例
    2. 小白强度 (25%) — 小白帖的平均得分
    3. 情绪极端度 (20%) — 贪婪/恐慌的情绪极端程度
    4. 热度纯度 (15%) — 纯小白帖在小白帖中的占比
    
    注意: ``activity``（有效帖数相对热度）作为 details 的独立观察指标输出，
    schema v2 要求 details 必须包含该字段。当前加权公式仅使用上述四个维度，
    与 config.METHODOLOGY 中的权重声明保持一致。
    """
    if not analysis_results:
        return {
            "index": 0, 
            "interpretation": "无数据",
            "details": {}
        }
    
    total = len(analysis_results)
    
    # 过滤掉垃圾帖 — 垃圾记录不参与任何指标、分母或意图统计
    valid_posts = [r for r in analysis_results if r.level != "垃圾帖"]
    spam_count = total - len(valid_posts)
    valid_count = len(valid_posts)
    
    # 小白帖（分数 >= 20）与纯小白（分数 >= 50）均基于有效帖
    newbie_posts = [r for r in valid_posts if r.newbie_score >= 20]
    pure_newbie = [r for r in valid_posts if r.newbie_score >= 50]
    newbie_count = len(newbie_posts)
    
    # 维度1: 小白占比 (0-100) — 基于有效帖子
    newbie_ratio = (newbie_count / valid_count) * 100 if valid_count else 0
    
    # 维度2: 小白强度 (0-100)
    avg_newbie_score = sum(r.newbie_score for r in newbie_posts) / max(newbie_count, 1)
    
    # 维度3: 情绪极端度 (0-100)
    sentiments = [abs(r.sentiment_score) for r in newbie_posts]
    avg_sentiment = sum(sentiments) / max(len(sentiments), 1) * 100
    
    # 维度4: 热度纯度 (0-100) — 纯小白在小白中的占比
    purity_signal = (len(pure_newbie) / max(newbie_count, 1)) * 100 if newbie_count > 0 else 0
    
    # 独立观察指标：讨论活跃度（schema v2 details 必填，不参与加权指数）
    activity_signal = min(100, valid_count / 80 * 100)  # 80条有效帖为满热度
    
    # 综合指数
    index = (
        newbie_ratio * 0.40 +
        avg_newbie_score * 0.25 +
        avg_sentiment * 0.20 +
        purity_signal * 0.15
    )
    
    index = round(min(100, index), 1)
    
    # ---- 买入/卖出子指数 ----
    newbie_buy = [r for r in newbie_posts if r.intent == "buy"]
    newbie_sell = [r for r in newbie_posts if r.intent == "sell"]
    
    buy_count = len(newbie_buy)
    sell_count = len(newbie_sell)
    
    buy_ratio = buy_count / max(newbie_count, 1)
    sell_ratio = sell_count / max(newbie_count, 1)
    buy_intensity = sum(r.intent_strength for r in newbie_buy) / max(buy_count, 1)
    sell_intensity = sum(r.intent_strength for r in newbie_sell) / max(sell_count, 1)
    
    # 买入指数: 小白买入占比(50%) + 小白热度(30%) + 买入强度(20%)
    mom_buy_index = round(min(100, (
        buy_ratio * 100 * 0.50 +
        (avg_newbie_score / 100) * buy_ratio * 30 * 0.30 +
        buy_intensity * 100 * 0.20
    )), 1)
    
    # 卖出指数: 小白卖出占比(50%) + 小白热度(30%) + 卖出强度(20%)
    mom_sell_index = round(min(100, (
        sell_ratio * 100 * 0.50 +
        (avg_newbie_score / 100) * sell_ratio * 30 * 0.30 +
        sell_intensity * 100 * 0.20
    )), 1)
    
    # 买卖比: 有买无卖时为 null（避免除以零的误导数值）；买卖均为 0 时定义为 0.0
    if buy_count == 0 and sell_count == 0:
        buy_sell_ratio = 0.0
    elif sell_count == 0:
        buy_sell_ratio = None
    else:
        buy_sell_ratio = round(buy_count / sell_count, 1)
    
    return {
        "index": index,
        "interpretation": interpret_index(index),
        "details": {
            "total_posts": total,
            "valid_posts": valid_count,
            "spam_posts": spam_count,
            "newbie_posts": newbie_count,
            "pure_newbie": len(pure_newbie),
            "newbie_ratio": round(newbie_ratio, 1),
            "avg_newbie_score": round(avg_newbie_score, 1),
            "avg_sentiment": round(avg_sentiment, 1),
            "purity_signal": round(purity_signal, 1),
            "activity": round(activity_signal, 1),
            # 买入/卖出子指数
            "mom_buy_index": mom_buy_index,
            "mom_sell_index": mom_sell_index,
            "buy_sell_ratio": buy_sell_ratio,
            "buy_count": buy_count,
            "sell_count": sell_count,
        },
        "top_newbie_posts": [
            {
                "title": r.title[:60],
                "score": r.newbie_score,
                "level": r.level,
                "reasoning": r.reasoning[:150],
                "intent": r.intent,
                "key_signals": r.key_signals[:2],
                "source_url": r.source_url,
            }
            for r in sorted(newbie_posts, key=lambda x: (-x.newbie_score, x.post_id))
            if r.source_url
        ][:5],
    }


def interpret_index(index: float) -> str:
    """Canonical interpretation of a Mom Index value."""
    if index >= 75:
        return "🔴 极度狂热 — 擦鞋童时刻！小白情绪爆表，历史级别的危险信号"
    elif index >= 60:
        return "🟠 高度警惕 — 小白大量涌入，市场情绪过热，建议大幅减仓"
    elif index >= 40:
        return "🟡 开始升温 — 小白活跃度明显上升，需保持关注"
    elif index >= 20:
        return "🟢 正常区间 — 小白参与度适中，无需特别操作"
    else:
        return "🔵 极度冷清 — 小白沉默不语，可能是市场底部信号"
