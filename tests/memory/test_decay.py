from datetime import datetime, timedelta, timezone
from mem0.utils.scoring import calculate_decay_multiplier, score_and_rank

def test_calculate_decay_multiplier():
    now = datetime.now(timezone.utc)
    
    # Just updated: multiplier ~ 1.5
    just_now_str = now.isoformat()
    multiplier = calculate_decay_multiplier(just_now_str)
    assert 1.4 < multiplier <= 1.5

    # Updated 30 days ago: multiplier ~ 0.3
    old_date = now - timedelta(days=30)
    old_date_str = old_date.isoformat()
    old_multiplier = calculate_decay_multiplier(old_date_str)
    assert 0.3 <= old_multiplier < 0.4
    
    assert multiplier > old_multiplier

def test_score_and_rank_decay():
    now = datetime.now(timezone.utc)
    recent_date = now.isoformat()
    old_date = (now - timedelta(days=30)).isoformat()
    
    semantic_results = [
        {"id": "old_mem", "score": 0.8, "payload": {"updated_at": old_date}},
        {"id": "recent_mem", "score": 0.8, "payload": {"updated_at": recent_date}},
    ]
    
    # Without decay, both should have the same combined score
    scored_no_decay = score_and_rank(
        semantic_results=semantic_results,
        bm25_scores={},
        entity_boosts={},
        threshold=0.1,
        top_k=5,
        decay=False
    )
    
    scores_no_decay = {item["id"]: item["score"] for item in scored_no_decay}
    assert scores_no_decay["old_mem"] == scores_no_decay["recent_mem"]
    
    # With decay, recent should be much higher than old
    scored_with_decay = score_and_rank(
        semantic_results=semantic_results,
        bm25_scores={},
        entity_boosts={},
        threshold=0.1,
        top_k=5,
        decay=True
    )
    
    assert len(scored_with_decay) == 2
    assert scored_with_decay[0]["id"] == "recent_mem"
    assert scored_with_decay[1]["id"] == "old_mem"
    assert scored_with_decay[0]["score"] > scored_with_decay[1]["score"]
