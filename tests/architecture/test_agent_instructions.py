"""Guard the repository instruction sources.

`AGENTS.md` and `CLAUDE.md` contain the same operational instructions.
The writing-rule skill has identical Claude and cross-agent copies.
Product and architecture requirements remain in
`docs/software_requirements.md` instead of being copied into agent files.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _body(name: str) -> str:
    """Return file text without its title line."""
    lines = (ROOT / name).read_text(encoding="utf-8").split("\n")
    return "\n".join(lines[1:])


class TestAgentsMirrorsClaude(unittest.TestCase):
    def test_both_files_exist(self):
        for name in ("CLAUDE.md", "AGENTS.md"):
            self.assertTrue((ROOT / name).is_file(), f"{name} is missing")

    def test_the_body_is_identical(self):
        self.assertEqual(
            _body("CLAUDE.md"), _body("AGENTS.md"),
            "AGENTS.md and CLAUDE.md must carry identical operational rules."
        )

    def test_each_title_names_its_file(self):
        self.assertEqual(
            (ROOT / "CLAUDE.md").read_text(encoding="utf-8").split("\n")[0],
            "# CLAUDE.md")
        self.assertEqual(
            (ROOT / "AGENTS.md").read_text(encoding="utf-8").split("\n")[0],
            "# AGENTS.md")

    def test_no_section_appears_twice(self):
        for name in ("CLAUDE.md", "AGENTS.md"):
            lines = (ROOT / name).read_text(encoding="utf-8").split("\n")
            titles = [line for line in lines if line.startswith("## ")]
            repeated = sorted({title for title in titles
                               if titles.count(title) > 1})
            self.assertEqual(repeated, [],
                             f"{name} repeats sections: {repeated}")

    def test_both_point_to_the_writing_skill(self):
        for name in ("CLAUDE.md", "AGENTS.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("writing-rules", text,
                          f"{name} does not mention the writing-rules skill")

    def test_agent_files_do_not_define_requirement_bullets(self):
        pattern = re.compile(r"^- \*\*[A-Z]{2}-\d+[a-z]?\*\*", re.MULTILINE)
        for name in ("CLAUDE.md", "AGENTS.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIsNone(
                pattern.search(text),
                f"{name} defines a software requirement. Put it in "
                "docs/software_requirements.md and reference its code.")

    def test_requirements_file_is_named_as_binding_source(self):
        for name in ("CLAUDE.md", "AGENTS.md"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("docs/software_requirements.md", text)
            self.assertIn("binding specification", text)
            self.assertIn("Do not copy requirements into this file", text)


class TestSkillMirroredInAgents(unittest.TestCase):
    """The writing-rules skill must be identical for both agent conventions."""

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
            f"{self.CLAUDE_SKILL} and {self.AGENTS_SKILL} must stay identical."
        )

    def test_all_discussed_rule_ids_remain_present(self):
        text = (ROOT / self.CLAUDE_SKILL).read_text(encoding="utf-8")
        expected = (
            {f"G{i}" for i in range(1, 33)}
            | {f"P{i}" for i in range(1, 6)}
            | {f"D{i}" for i in range(1, 4)}
        )
        rows = set(re.findall(r"^\| (G\d+|P\d+|D\d+) \|", text,
                              flags=re.MULTILINE))
        self.assertEqual(rows, expected,
                         "The writing-rule Do/Don't tables changed their "
                         "rule set. Add or remove a rule only deliberately.")


if __name__ == "__main__":
    unittest.main()
