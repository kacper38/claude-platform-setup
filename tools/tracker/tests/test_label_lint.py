"""label-lint reports and never edits labels."""


def mk(tracker, fb, labels, state="open", title="t"):
    issue = fb.create_issue(title, "", labels)
    fb.issues[issue.number].state = state
    return issue.number


def test_findings_cover_the_contract(tracker, label_lint):
    fb = tracker.FakeBackend()
    ok = mk(tracker, fb, ["type/todo", "status/ready"])
    two = mk(tracker, fb, ["type/todo", "status/ready", "status/blocked"])
    none = mk(tracker, fb, ["type/bug"])
    closed_review = mk(tracker, fb, ["status/review"], state="closed")
    open_done = mk(tracker, fb, ["status/done"])
    unknown = mk(tracker, fb, ["status/wip", "type/todo", "type/bug"])
    found = {i.number: p for i, p in label_lint.findings(fb)}
    assert ok not in found
    assert "2 status labels" in found[two][0]
    assert "0 status labels" in found[none][0]
    assert "closed but status/review" in found[closed_review][0]
    assert "open but status/done" in found[open_done][0]
    assert any("unknown status label status/wip" in p for p in found[unknown])
    assert any("2 type labels" in p for p in found[unknown])


def test_report_comments_once_and_keeps_one_tracking_issue(tracker, label_lint):
    fb = tracker.FakeBackend()
    bad = mk(tracker, fb, ["type/todo", "status/ready", "status/blocked"], title="bad one")
    labels_before = list(fb.get_issue(bad).labels)
    counts = label_lint.report(fb, label_lint.findings(fb), "2026-10-29T00:00:00Z")
    assert counts == {"issues": 1, "comments": 1, "tracking": "created"}
    tracking = [i for i in fb.list_issues() if i.title == label_lint.TRACKING_TITLE]
    assert len(tracking) == 1 and "#1 bad one" in tracking[0].body
    assert set(tracking[0].labels) == {"type/agent-note", "status/backlog"}
    counts = label_lint.report(fb, label_lint.findings(fb), "2026-10-29T01:00:00Z")
    assert counts == {"issues": 1, "comments": 0, "tracking": "updated"}, "same finding set: no second comment"
    assert len(fb.get_issue(bad).comments) == 1
    assert fb.get_issue(bad).labels == labels_before, "lint never edits labels"
    assert not [e for e in fb.log if e[0] in ("add", "remove", "close")]
    fb.remove_labels(bad, ["status/blocked"])
    counts = label_lint.report(fb, label_lint.findings(fb), "2026-10-29T02:00:00Z")
    assert counts == {"issues": 0, "comments": 0, "tracking": "updated"}
    assert "No offending issues" in fb.get_issue(tracking[0].number).body
    assert len(fb.list_issues()) == 2, "the tracking issue is not closed by the job"
