"""`AGENTS.md` and `CLAUDE.md` must carry the same rules, and the
`writing-rules` skill must read the same under `.claude/` and `.agents/`.

`CLAUDE.md` is what Claude Code reads. `AGENTS.md` is the cross-agent
convention that other tools read. `.claude/skills/writing-rules/SKILL.md`
is where Claude Code loads the skill from; `.agents/skills/writing-rules/
SKILL.md` is a mirror for any other agent. A rule that lives in only one of
a pair binds only one agent, which is the same as not binding anyone.

`AGENTS.md` drifted once already: it accumulated three near-copies of the
whole ruleset, 741 lines against 320, and the copies disagreed. This test
is what stops that from happening again, for both pairs.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _body(name: str) -> str:
    """The file's text without its title line."""
    lines = (ROOT / name).read_text(encoding="utf-8").split("\n")
    return "\n".join(lines[1:])


class TestAgentsMirrorsClaude(unittest.TestCase):
    def test_both_files_exist(self):
        for name in ("CLAUDE.md", "AGENTS.md"):
            self.assertTrue((ROOT / name).is_file(), f"{name} is missing")

    def test_the_body_is_identical(self):
        self.assertEqual(
            _body("CLAUDE.md"), _body("AGENTS.md"),
            "AGENTS.md and CLAUDE.md have diverged. They must carry the same "
            "rules, so copy CLAUDE.md over AGENTS.md and change only the "
            "title line.")

    def test_each_title_names_its_file(self):
        self.assertEqual(
            (ROOT / "CLAUDE.md").read_text(encoding="utf-8").split("\n")[0],
            "# CLAUDE.md")
        self.assertEqual(
            (ROOT / "AGENTS.md").read_text(encoding="utf-8").split("\n")[0],
            "# AGENTS.md")

    def test_no_section_appears_twice(self):
        """The duplication that broke AGENTS.md must not come back."""
        for name in ("CLAUDE.md", "AGENTS.md"):
            titles = [l for l in (ROOT / name).read_text(encoding="utf-8").split("\n")
                      if l.startswith("## ")]
            repeated = sorted({t for t in titles if titles.count(t) > 1})
            self.assertEqual(repeated, [], f"{name} repeats sections: {repeated}")

    def test_both_point_to_the_writing_skill(self):
        for name in ("CLAUDE.md", "AGENTS.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("writing-rules", text,
                          f"{name} does not mention the writing-rules skill")


class TestSkillMirroredInAgents(unittest.TestCase):
    """The writing-rules skill must read the same under both conventions."""

    CLAUDE_SKILL = ".claude/skills/writing-rules/SKILL.md"
    AGENTS_SKILL = ".agents/skills/writing-rules/SKILL.md"

    def test_the_two_copies_exist(self):
        for path in (self.CLAUDE_SKILL, self.AGENTS_SKILL):
            self.assertTrue((ROOT / path).is_file(), f"{path} is missing")

    def test_the_two_copies_are_identical(self):
        a = (ROOT / self.CLAUDE_SKILL).read_text(encoding="utf-8")
        b = (ROOT / self.AGENTS_SKILL).read_text(encoding="utf-8")
        self.assertEqual(
            a, b,
            f"{self.CLAUDE_SKILL} and {self.AGENTS_SKILL} have diverged. "
            "Copy one over the other so both agents follow the same rules.")


if __name__ == "__main__":
    unittest.main()
