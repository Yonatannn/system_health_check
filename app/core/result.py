from app.core.models import CheckResult, CheckStatus, CheckCategory, PrecheckReport, OverallStatus


def make_pass(id: str, category: str, title: str, expected: str = None, actual: str = None, details: str = "") -> CheckResult:
    return CheckResult(id=id, category=category, title=title, status=CheckStatus.PASS,
                       expected=expected, actual=actual, details=details)


def make_fail(id: str, category: str, title: str, expected: str = None, actual: str = None,
              details: str = "", blocking: bool = True) -> CheckResult:
    return CheckResult(id=id, category=category, title=title, status=CheckStatus.FAIL,
                       expected=expected, actual=actual, details=details, blocking=blocking)


def make_warning(id: str, category: str, title: str, expected: str = None, actual: str = None, details: str = "") -> CheckResult:
    return CheckResult(id=id, category=category, title=title, status=CheckStatus.WARNING,
                       expected=expected, actual=actual, details=details, blocking=False)


def make_skipped(id: str, category: str, title: str, details: str = "") -> CheckResult:
    return CheckResult(id=id, category=category, title=title, status=CheckStatus.SKIPPED,
                       details=details, blocking=False)


def calculate_overall_status(results: list[CheckResult]) -> OverallStatus:
    if any(r.status == CheckStatus.FAIL and r.blocking for r in results):
        return OverallStatus.NOT_READY
    if any(r.status == CheckStatus.WARNING for r in results):
        return OverallStatus.READY_WITH_WARNINGS
    return OverallStatus.READY


def group_by_category(results: list[CheckResult]) -> list[CheckCategory]:
    seen: dict[str, CheckCategory] = {}
    for r in results:
        if r.category not in seen:
            seen[r.category] = CheckCategory(name=r.category)
        seen[r.category].results.append(r)
    return list(seen.values())
