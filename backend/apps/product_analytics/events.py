from apps.product_analytics.models import ProductEvent


def track_event(*, company_id: int, event_name: str, actor_id: int | None = None, payload: dict | None = None):
    ProductEvent.objects.create(
        company_id=company_id,
        actor_id=actor_id,
        event_name=event_name,
        payload=payload or {},
    )
