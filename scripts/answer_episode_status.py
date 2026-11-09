"""Pure terminal episode accounting, not semantic grading or API execution."""


def classify(event):
    if type(event) is not dict or set(event)!={"admission","dispatch_attempted","outcome","schema_valid"}:
        raise ValueError("exact event fields required")
    admission=event["admission"];attempted=event["dispatch_attempted"]
    outcome=event["outcome"];schema=event["schema_valid"]
    if (admission not in ("pending","admitted","rejected") or type(attempted) is not bool or
            outcome not in ("none","transport_error","provider_error","truncated","completed") or
            schema is not None and type(schema) is not bool):
        raise ValueError("invalid event types or categories")
    if not attempted:
        if outcome!="none" or schema is not None:raise ValueError("response without dispatch")
        return dict(status="input_not_admitted" if admission=="rejected" else "not_attempted",
                    consumed_attempts=0,semantic_evaluation="unmeasured")
    if admission!="admitted" or outcome=="none":raise ValueError("invalid dispatched terminal state")
    if outcome in ("transport_error","provider_error"):
        if schema is not None:raise ValueError("schema attached to transport/provider failure")
        status="transport_failure" if outcome=="transport_error" else "provider_failure"
    elif outcome=="truncated":
        status="truncated"
    else:
        if type(schema) is not bool:raise ValueError("completed response requires schema result")
        status="completed" if schema else "schema_error"
    return dict(status=status,consumed_attempts=1,semantic_evaluation="unmeasured")
