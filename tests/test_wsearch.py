"""Unit tests for scripts/wsearch.py: no network, no credentials."""
import io, json, os, sys, unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "plugin", "skills", "google-workspace-search-mcp", "scripts"))
import wsearch  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
G = "https://www.googleapis.com/auth/"


def fixture(name):
    return open(os.path.join(FIX, name)).read()


class Scopes(unittest.TestCase):
    def test_all_four_readonly(self):
        s = f"{G}gmail.readonly {G}drive.readonly {G}calendar.readonly {G}chat.messages.readonly"
        self.assertEqual(wsearch.corpora_for_scopes(s), ["gmail", "drive", "calendar", "chat"])

    def test_partial_grant_drops_gmail(self):
        # The guide's example: omit gmail.readonly and Gmail is not searched.
        s = f"{G}drive.readonly {G}calendar.readonly {G}chat.messages.readonly"
        self.assertEqual(wsearch.corpora_for_scopes(s), ["drive", "calendar", "chat"])

    def test_broad_scopes_count(self):
        s = ["https://mail.google.com/", G + "drive"]
        self.assertEqual(wsearch.corpora_for_scopes(s), ["gmail", "drive"])

    def test_unrelated_scopes(self):
        s = f"{G}gmail.compose {G}drive.file {G}calendar.events.readonly {G}chat.spaces.readonly openid"
        self.assertEqual(wsearch.corpora_for_scopes(s), [])


class ParseListed(unittest.TestCase):
    def test_list_output(self):
        text = fixture("claude-mcp-list.txt")
        listed = wsearch.parse_listed(text)
        self.assertEqual(listed["workspace-universal"], "✔ Connected")
        self.assertIn("workspace-developer", listed)
        self.assertIn("plugin:nb2lite:nb2lite", listed)
        self.assertNotIn("Checking MCP server health…", listed)


class PickToken(unittest.TestCase):
    NOW = 1_800_000_000

    def test_newest_entry_for_server(self):
        store = {
            "workspace-universal|a": {"serverName": "workspace-universal", "accessToken": "old",
                                      "expiresAt": (self.NOW - 600) * 1000},
            "workspace-universal|b": {"serverName": "workspace-universal", "accessToken": "new",
                                      "expiresAt": (self.NOW + 1800) * 1000},
            "gmail|c": {"serverName": "gmail", "accessToken": "gm", "expiresAt": (self.NOW + 3000) * 1000},
        }
        left, refresh, token = wsearch.pick_token(store, now=self.NOW)
        self.assertEqual(token, "new")
        self.assertAlmostEqual(left, 30.0)
        self.assertFalse(refresh)

    def test_seconds_expiry_and_refresh(self):
        store = {"workspace-universal|x": {"accessToken": "t", "refreshToken": "r",
                                           "expiresAt": self.NOW + 60}}
        left, refresh, _ = wsearch.pick_token(store, now=self.NOW)
        self.assertAlmostEqual(left, 1.0)
        self.assertTrue(refresh)

    def test_none(self):
        self.assertIsNone(wsearch.pick_token({"gmail|c": {"accessToken": "x"}}, now=self.NOW))
        self.assertIsNone(wsearch.pick_token({"workspace-universal|c": {"accessToken": ""}}))


class RpcBody(unittest.TestCase):
    def test_json(self):
        self.assertEqual(wsearch.parse_rpc_body(b'{"id":1,"result":{}}')["id"], 1)

    def test_sse_takes_last_message(self):
        raw = 'event: message\ndata: {"id":1,"result":{"a":1}}\n\ndata: {"id":1,"result":{"a":2}}\n'
        self.assertEqual(wsearch.parse_rpc_body(raw)["result"]["a"], 2)

    def test_garbage(self):
        with self.assertRaises(ValueError):
            wsearch.parse_rpc_body("<html>")


class Counting(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(fixture("search_corpus-result.json"))

    def test_exact_counts(self):
        s = wsearch.count_by_corpus(self.payload)
        self.assertEqual(s["counts"], {"gmail": 2, "drive": 3, "calendar": 1, "chat": 1})
        self.assertEqual(s["total"], 7)
        self.assertEqual(s["messages"], {"gmail": 3, "chat": 2})
        self.assertFalse(s["next_page_token"])

    def test_empty(self):
        s = wsearch.count_by_corpus({})
        self.assertEqual(s["total"], 0)
        self.assertEqual(wsearch.count_by_corpus(None)["total"], 0)

    def test_unknown_item_kind_counts_in_total(self):
        s = wsearch.count_by_corpus({"items": [{"photosResult": {}}, {"driveResult": {}}]})
        self.assertEqual(s["counts"]["drive"], 1)
        self.assertEqual(s["other"], 1)
        self.assertEqual(s["total"], 2)

    def test_describe(self):
        kinds = [wsearch.describe_item(i)[0] for i in self.payload["items"]]
        self.assertEqual(sorted(kinds), ["calendar", "chat", "drive", "drive", "drive", "gmail", "gmail"])


class ToolPayload(unittest.TestCase):
    def test_structured_content_wins(self):
        p, err, _ = wsearch.tool_payload({"structuredContent": {"items": []},
                                          "content": [{"type": "text", "text": "x"}]})
        self.assertEqual(p, {"items": []})
        self.assertFalse(err)

    def test_text_json(self):
        p, err, _ = wsearch.tool_payload({"content": [{"type": "text", "text": '{"items":[{"driveResult":{}}]}'}]})
        self.assertEqual(len(p["items"]), 1)
        self.assertFalse(err)

    def test_error(self):
        p, err, text = wsearch.tool_payload({"isError": True, "content": [{"type": "text", "text": "401"}]})
        self.assertIsNone(p)
        self.assertTrue(err)
        self.assertEqual(text, "401")


class Grade(unittest.TestCase):
    def grade(self, name):
        return wsearch.grade_events(fixture(name).splitlines())

    def test_pass_counts_from_tool_result(self):
        g = self.grade("stream-pass.jsonl")
        self.assertEqual(g["status"], "PASS")
        self.assertEqual((g["calls"], g["ok"], g["err"]), (1, 1, 0))
        self.assertEqual(g["totals"], {"gmail": 2, "drive": 3, "calendar": 1, "chat": 1})
        self.assertEqual(g["queries"], ["meeting"])

    def test_fail(self):
        g = self.grade("stream-fail.jsonl")
        self.assertEqual(g["status"], "FAIL")
        self.assertEqual(g["err"], 1)

    def test_not_called_when_tools_missing(self):
        # A revoked token: the server shows connected, its tools never load.
        self.assertEqual(self.grade("stream-not-called.jsonl")["status"], "NOT CALLED")

    def test_not_registered(self):
        self.assertEqual(wsearch.grade_events(['{"type":"system","subtype":"init","mcp_servers":[]}'])["status"],
                         "NOT REGISTERED")

    def test_cmd_grade_exit_code(self):
        with redirect_stdout(io.StringIO()) as out:
            rc = wsearch.cmd_grade(os.path.join(FIX, "stream-pass.jsonl"))
        self.assertEqual(rc, 0)
        self.assertIn("gmail 2, drive 3, calendar 1, chat 1", out.getvalue())


if __name__ == "__main__":
    unittest.main()
