from dataclasses import dataclass, field
from typing import TypedDict


class LocationDict(TypedDict):
    name: str
    area: str
    lat: float | None
    lng: float | None


class ActivityScoreDict(TypedDict):
    activity_id: str
    interest_match: float
    budget_match: float
    weather_match: float
    location_match: float
    overall_score: float
    explanation: str


class ActivityDict(TypedDict):
    id: str
    name: str
    category: str
    description: str
    location: LocationDict
    estimated_cost_per_person: float
    estimated_cost_total: float
    duration_minutes: int
    indoor_outdoor: str
    tags: list
    reasoning: str
    score: ActivityScoreDict | None
    source: str


class TimeSlotDict(TypedDict):
    id: str
    start_time: str
    end_time: str
    activity: ActivityDict
    notes: str | None


class WeatherSummaryDict(TypedDict):
    day_number: int
    condition: str
    description: str
    affects_outdoor_activities: bool


class TravelDayDict(TypedDict):
    day_number: int
    title: str
    date: str | None
    weather: WeatherSummaryDict | None
    time_slots: list


class BudgetCategoryDict(TypedDict):
    category: str
    amount: float
    percentage: float


class BudgetSummaryDict(TypedDict):
    budget_total: float
    planned_total: float
    remaining: float
    currency: str
    per_person_total: float
    categories: list
    status: str


class TripRequestDict(TypedDict):
    destination: str
    duration_days: int
    budget_total: float
    currency: str
    number_of_people: int
    travel_type: str
    interests: list


class TravelPlanDict(TypedDict):
    id: str
    request: TripRequestDict
    days: list
    budget_summary: BudgetSummaryDict
    status: str
    created_at: str
    updated_at: str


class ReplanningChangeDict(TypedDict):
    type: str
    day_number: int
    original_activity_id: str | None
    new_activity_id: str | None
    explanation: str
    cost_delta: float


class ReplanningProposalDict(TypedDict):
    id: str
    plan_id: str
    reason: str
    affected_day_numbers: list
    changes: list
    proposed_plan: TravelPlanDict
    budget_before: BudgetSummaryDict
    budget_after: BudgetSummaryDict
    status: str
    created_at: str


class AgentInsightDict(TypedDict):
    agent_name: str
    display_label: str
    status: str
    summary: str


class ChecklistItemDict(TypedDict):
    id: str
    label: str
    category: str
    completed: bool
    priority: str


class ChecklistDict(TypedDict):
    trip_id: str
    items: list


class TripDict(TypedDict):
    id: str
    request: TripRequestDict
    active_plan: TravelPlanDict | None
    proposals: list
    checklist: ChecklistDict | None
    agent_insights: list
    chat_messages: list
