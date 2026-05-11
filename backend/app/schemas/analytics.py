from pydantic import BaseModel
from uuid import UUID

class CallsPerDayResponse(BaseModel):

    date: str
    count: int


class SentimentBreakdownResponse(BaseModel):

    positive: int
    neutral: int
    negative: int


class TopAgentResponse(BaseModel):

    agent_id: UUID
    agent_name: str
    call_count: int


class CallAnalyticsResponse(BaseModel):

    total_calls: int
    completed_calls: int
    failed_calls: int
    success_rate: float
    avg_duration: int
    calls_per_day: list[CallsPerDayResponse]
    sentiment_breakdown: SentimentBreakdownResponse
    top_agents: list[TopAgentResponse]