def calculate_significance(message: str, intent: str, confidence: float) -> float:
    base = confidence * 0.6
    msg_lower = message.lower()
    urgency_keywords = ["urgent", "asap", "emergency", "deadline", "important"]
    urgency_bonus = 0.2 if any(kw in msg_lower for kw in urgency_keywords) else 0.0

    intent_weights = {
        "compliance": 0.2,
        "scheduling": 0.1,
        "leave": 0.1,
        "clarification": 0.0
    }
    intent_bonus = intent_weights.get(intent, 0.0)

    significance = min(base + urgency_bonus + intent_bonus, 1.0)
    return round(significance, 3)