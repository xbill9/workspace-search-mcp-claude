"""The server name, URL, scopes and APIs must agree across every file that names them."""
import json, os, re, sys, unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SKILL = os.path.join(ROOT, "plugin", "skills", "google-workspace-search-mcp")
sys.path.insert(0, os.path.join(SKILL, "scripts"))
import wsearch  # noqa: E402

NAME = "workspace-universal"
URL = "https://workspacemcp.googleapis.com/mcp/v1"
G = "https://www.googleapis.com/auth/"
SCOPES = [G + "gmail.readonly", G + "drive.readonly", G + "calendar.readonly", G + "chat.messages.readonly"]
APIS = ["gmail.googleapis.com", "drive.googleapis.com", "calendar-json.googleapis.com",
        "chat.googleapis.com", "workspacemcp.googleapis.com"]
OLD_SERVERS = ["gmailmcp", "drivemcp", "docsmcp", "sheetsmcp", "slidesmcp", "calendarmcp", "chatmcp"]


def read(*parts):
    return open(os.path.join(ROOT, *parts)).read()


class Consistency(unittest.TestCase):
    def test_wsearch_constants(self):
        self.assertEqual(wsearch.NAME, NAME)
        self.assertEqual(wsearch.URL, URL)
        for corpus, scope in zip(wsearch.CORPORA, SCOPES):
            self.assertIn(scope, wsearch.CORPUS_SCOPES[corpus])

    def test_claude_setup(self):
        s = read(SKILL, "scripts", "claude_setup.sh")
        self.assertIn(f"NAME={NAME}", s)
        self.assertIn(f"URL={URL}", s)
        for scope in SCOPES:
            self.assertIn(scope.replace(G, "$G/"), s)
        self.assertNotIn("offline_access", s)  # Google rejects it as invalid_scope

    def test_gemini_settings(self):
        cfg = json.loads(read(".gemini", "settings.json"))["mcpServers"]
        self.assertEqual(list(cfg), [NAME])
        self.assertEqual(cfg[NAME]["httpUrl"], URL)
        self.assertEqual(cfg[NAME]["oauth"]["scopes"], SCOPES)

    def test_apis(self):
        for f in ("init.sh", os.path.join(SKILL, "scripts", "bootstrap.sh")):
            s = read(f)
            for api in APIS:
                self.assertIn(api, s, f"{api} missing from {f}")
            for old in OLD_SERVERS:
                self.assertNotIn(old, s, f"{old} still enabled in {f}")

    def test_docs_name_url_and_scopes(self):
        for f in ("README.md", "CLAUDE.md", os.path.join(SKILL, "SKILL.md"),
                  os.path.join(SKILL, "references", "server.md")):
            s = read(f)
            self.assertIn(NAME, s, f)
            self.assertIn(URL, s, f)
        for f in ("README.md", os.path.join(SKILL, "references", "server.md")):
            s = read(f)
            for scope in SCOPES:
                self.assertIn(scope.replace(G, ""), s, f"{scope} missing from {f}")

    def test_no_per_product_servers_left_in_scripts(self):
        scripts = os.path.join(SKILL, "scripts")
        for f in os.listdir(scripts):
            if not os.path.isfile(os.path.join(scripts, f)):
                continue
            s = read(scripts, f)
            for old in OLD_SERVERS:
                self.assertNotIn(f"{old}.googleapis.com", s, f"{old} in scripts/{f}")

    def test_versions_match(self):
        plugin = json.loads(read("plugin", ".claude-plugin", "plugin.json"))
        market = json.loads(read(".claude-plugin", "marketplace.json"))
        self.assertEqual(plugin["version"], market["metadata"]["version"])
        self.assertEqual(plugin["name"], market["plugins"][0]["name"])
        self.assertEqual(plugin["name"], "google-workspace-search-mcp")

    def test_skill_frontmatter(self):
        s = read(SKILL, "SKILL.md")
        m = re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", s)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "google-workspace-search-mcp")
        self.assertLessEqual(len(m.group(2)), 1024)

    def test_skill_references_exist(self):
        s = read(SKILL, "SKILL.md")
        for ref in set(re.findall(r"references/[\w.-]+\.md", s)):
            self.assertTrue(os.path.exists(os.path.join(SKILL, ref)), ref)
        for script in set(re.findall(r"scripts/([\w.-]+\.(?:sh|py))", s)):
            self.assertTrue(os.access(os.path.join(SKILL, "scripts", script), os.X_OK), script)

    def test_root_wrappers(self):
        for f in os.listdir(os.path.join(SKILL, "scripts")):
            if f.endswith(".sh"):
                w = read(f)
                self.assertIn(f"google-workspace-search-mcp/scripts/{f}", w, f)


if __name__ == "__main__":
    unittest.main()
