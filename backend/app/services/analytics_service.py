from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Call,
    Agent
)


def get_call_analytics(
    db: Session,
    workspace_id,
    days: int = 7
):

    if days <= 0:
        days = 7

    start_date = datetime.now(
        timezone.utc
    ) - timedelta(days=days)

    base_query = db.query(Call).filter(
        Call.workspace_id == workspace_id,
        Call.start_time >= start_date
    )

    total_calls = base_query.count()

    completed_calls = base_query.filter(
        Call.status == "completed"
    ).count()

    failed_calls = base_query.filter(
        Call.status == "failed"
    ).count()

    resolved_calls = (
        completed_calls + failed_calls
    )

    success_rate = 0.0

    if resolved_calls > 0:

        success_rate = round(
            (completed_calls / resolved_calls) * 100,
            2
        )

    avg_duration = db.query(
        func.avg(Call.duration)
    ).filter(
        Call.workspace_id == workspace_id,
        Call.start_time >= start_date,
        Call.duration.isnot(None)
    ).scalar()

    avg_duration = int(avg_duration or 0)

    calls_per_day_query = db.query(
        func.date(Call.start_time),
        func.count(Call.id)
    ).filter(
        Call.workspace_id == workspace_id,
        Call.start_time >= start_date
    ).group_by(
        func.date(Call.start_time)
    ).order_by(
        func.date(Call.start_time)
    ).all()

    calls_per_day = [
        {
            "date": str(date),
            "count": count
        }
        for date, count in calls_per_day_query
    ]

    sentiment_query = db.query(
        Call.sentiment,
        func.count(Call.id)
    ).filter(
        Call.workspace_id == workspace_id,
        Call.start_time >= start_date,
        Call.sentiment.isnot(None)
    ).group_by(
        Call.sentiment
    ).all()

    sentiment_breakdown = {
        "positive": 0,
        "neutral": 0,
        "negative": 0
    }

    for sentiment, count in sentiment_query:

        normalized_sentiment = (
            sentiment.lower().strip()
        )

        if normalized_sentiment in sentiment_breakdown:
            sentiment_breakdown[
                normalized_sentiment
            ] = count

    top_agents_query = db.query(
        Agent.id,
        Agent.name,
        func.count(Call.id)
    ).join(
        Call,
        Call.agent_id == Agent.id
    ).filter(
        Call.workspace_id == workspace_id,
        Call.start_time >= start_date
    ).group_by(
        Agent.id,
        Agent.name
    ).order_by(
        func.count(Call.id).desc()
    ).limit(5).all()

    top_agents = [
        {
            "agent_id": str(agent_id),
            "agent_name": agent_name,
            "call_count": call_count
        }
        for agent_id, agent_name, call_count
        in top_agents_query
    ]

    return {
        "total_calls": total_calls,
        "completed_calls": completed_calls,
        "failed_calls": failed_calls,
        "success_rate": success_rate,
        "avg_duration": avg_duration,
        "calls_per_day": calls_per_day,
        "sentiment_breakdown": sentiment_breakdown,
        "top_agents": top_agents
    }