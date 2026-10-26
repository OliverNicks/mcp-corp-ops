from data.fixtures.seed_sqlite import seed_sqlite
from src.core import telemetry
from src.server.tools.sql_tool import execute_safe_query

seed_sqlite()


class FakeSpan:
    def __init__(self, log):
        self.log = log

    def end(self, **kw):
        self.log.append(("span_end", kw))


class FakeTrace:
    def __init__(self, log):
        self.log = log

    def span(self, **kw):
        self.log.append(("span_start", kw))
        return FakeSpan(self.log)

    def update(self, **kw):
        self.log.append(("trace_update", kw))


class FakeLangfuse:
    def __init__(self):
        self.log = []

    def trace(self, **kw):
        self.log.append(("trace", kw))
        return FakeTrace(self.log)


def test_successful_query_is_traced(monkeypatch):
    fake = FakeLangfuse()
    monkeypatch.setattr(telemetry, "get_langfuse", lambda: fake)
    execute_safe_query(query="SELECT product_id FROM oc_product", query_purpose="t")
    names = [e[0] for e in fake.log]
    assert names == ["trace", "span_start", "span_end", "trace_update"]
    end = dict(fake.log)["span_end"]
    assert end["level"] == "DEFAULT"
    assert end["output"]["rows"].startswith("<list of")   # rows are not stored


def test_rejected_query_is_flagged_warning(monkeypatch):
    fake = FakeLangfuse()
    monkeypatch.setattr(telemetry, "get_langfuse", lambda: fake)
    execute_safe_query(query="DROP TABLE oc_product;", query_purpose="attack")
    end = dict(fake.log)["span_end"]
    assert end["level"] == "WARNING"
    assert end["status_message"] == "rejected"


def test_tracing_failure_does_not_break_tool(monkeypatch):
    class Broken:
        def trace(self, **kw):
            raise RuntimeError("langfuse down")

    monkeypatch.setattr(telemetry, "get_langfuse", lambda: Broken())
    result = execute_safe_query(query="SELECT product_id FROM oc_product", query_purpose="t")
    assert result["status"] == "success"