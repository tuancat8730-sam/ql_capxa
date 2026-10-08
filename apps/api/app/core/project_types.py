"""What each kind of project shows. The frontend builds its menu from `modules`."""

PROCUREMENT_MODULES = (
    "dashboard",
    "packages",
    "daily_log",
    "alerts",
    "progress",
    "contracts",
    "payments",
    "documents",
    "risks",
    "issues",
    "meetings",
    "change_requests",
    "outgoing_docs",
    "audit",
)

SOFTWARE_DELIVERY_MODULES = (
    "dashboard",
    "schedule",
    "weekly_reports",
    "risks",
    "decisions",
    "alerts",
    "audit",
)

MODULES_BY_TYPE: dict[str, tuple[str, ...]] = {
    "procurement": PROCUREMENT_MODULES,
    "software_delivery": SOFTWARE_DELIVERY_MODULES,
}


def modules_for(project_type: str) -> list[str]:
    return list(MODULES_BY_TYPE.get(project_type, ()))
