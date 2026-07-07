from api.server.services.compose.translate import translate_update


def test_agent_message_chunk_becomes_narration():
    params = {"sessionId": "s", "update": {
        "sessionUpdate": "agent_message_chunk",
        "content": {"type": "text", "text": "Domain composed."}}}
    assert translate_update(params) == [
        {"type": "narration", "text": "Domain composed.", "partial": True}]


def test_agent_thought_chunk_becomes_thought():
    params = {"update": {"sessionUpdate": "agent_thought_chunk",
                         "content": {"type": "text", "text": "Reading the registry."}}}
    assert translate_update(params) == [
        {"type": "thought", "text": "Reading the registry.", "partial": True}]


def test_tool_call_read_maps_kind_and_path():
    params = {"update": {
        "sessionUpdate": "tool_call", "toolCallId": "t1",
        "title": "Reading api/shared/domains.py", "kind": "read", "status": "pending",
        "locations": [{"path": "api/shared/domains.py"}]}}
    assert translate_update(params) == [{
        "type": "tool", "id": "t1", "title": "Reading api/shared/domains.py",
        "kind": "read", "status": "pending", "path": "api/shared/domains.py"}]


def test_tool_call_edit_extracts_diff():
    params = {"update": {
        "sessionUpdate": "tool_call", "toolCallId": "t2",
        "title": "Creating fleet_capex.py", "kind": "edit", "status": "pending",
        "content": [{"type": "diff", "path": "api/functions/workflows/fleet_capex.py",
                     "oldText": "", "newText": "# orchestrator\n"}]}}
    out = translate_update(params)[0]
    assert out["type"] == "tool" and out["kind"] == "edit"
    assert out["diff"] == {"old": "", "new": "# orchestrator\n"}
    assert out["path"] == "api/functions/workflows/fleet_capex.py"


def test_tool_call_update_carries_status_and_output():
    params = {"update": {
        "sessionUpdate": "tool_call_update", "toolCallId": "t1", "status": "completed",
        "rawOutput": {"content": "Created file with 6 characters"}}}
    assert translate_update(params) == [{
        "type": "tool", "id": "t1", "status": "completed",
        "output": "Created file with 6 characters"}]


def test_plan_update_maps_entries():
    params = {"update": {"sessionUpdate": "plan", "entries": [
        {"title": "Author brief", "status": "in_progress"},
        {"title": "Graduate", "status": "pending"}]}}
    assert translate_update(params) == [{"type": "plan", "entries": [
        {"title": "Author brief", "status": "in_progress"},
        {"title": "Graduate", "status": "pending"}]}]


def test_ignored_updates_yield_nothing():
    for kind in ("available_commands_update", "config_option_update", "user_message_chunk"):
        assert translate_update({"update": {"sessionUpdate": kind}}) == []
