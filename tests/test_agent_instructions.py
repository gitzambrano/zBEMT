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

RAIZ = Path(__file__).resolve().parents[1]


def _corpo(nome: str) -> str:
    """The file's text without its title line."""
    linhas = (RAIZ / nome).read_text(encoding="utf-8").split("\n")
    return "\n".join(linhas[1:])


class TestAgentsEspelhaClaude(unittest.TestCase):
    def test_os_dois_arquivos_existem(self):
        for nome in ("CLAUDE.md", "AGENTS.md"):
            self.assertTrue((RAIZ / nome).is_file(), f"{nome} is missing")

    def test_o_corpo_e_identico(self):
        self.assertEqual(
            _corpo("CLAUDE.md"), _corpo("AGENTS.md"),
            "AGENTS.md and CLAUDE.md have diverged. They must carry the same "
            "rules, so copy CLAUDE.md over AGENTS.md and change only the "
            "title line.")

    def test_cada_titulo_nomeia_o_seu_arquivo(self):
        self.assertEqual(
            (RAIZ / "CLAUDE.md").read_text(encoding="utf-8").split("\n")[0],
            "# CLAUDE.md")
        self.assertEqual(
            (RAIZ / "AGENTS.md").read_text(encoding="utf-8").split("\n")[0],
            "# AGENTS.md")

    def test_nenhuma_secao_aparece_duas_vezes(self):
        """The duplication that broke AGENTS.md must not come back."""
        for nome in ("CLAUDE.md", "AGENTS.md"):
            titulos = [l for l in (RAIZ / nome).read_text(encoding="utf-8").split("\n")
                       if l.startswith("## ")]
            repetidos = sorted({t for t in titulos if titulos.count(t) > 1})
            self.assertEqual(repetidos, [], f"{nome} repeats sections: {repetidos}")

    def test_os_dois_apontam_para_a_skill_de_escrita(self):
        for nome in ("CLAUDE.md", "AGENTS.md"):
            texto = (RAIZ / nome).read_text(encoding="utf-8")
            self.assertIn("writing-rules", texto,
                          f"{nome} does not mention the writing-rules skill")


class TestSkillEspelhadaEmAgents(unittest.TestCase):
    """The writing-rules skill must read the same under both conventions."""

    CLAUDE_SKILL = ".claude/skills/writing-rules/SKILL.md"
    AGENTS_SKILL = ".agents/skills/writing-rules/SKILL.md"

    def test_as_duas_copias_existem(self):
        for caminho in (self.CLAUDE_SKILL, self.AGENTS_SKILL):
            self.assertTrue((RAIZ / caminho).is_file(), f"{caminho} is missing")

    def test_as_duas_copias_sao_identicas(self):
        a = (RAIZ / self.CLAUDE_SKILL).read_text(encoding="utf-8")
        b = (RAIZ / self.AGENTS_SKILL).read_text(encoding="utf-8")
        self.assertEqual(
            a, b,
            f"{self.CLAUDE_SKILL} and {self.AGENTS_SKILL} have diverged. "
            "Copy one over the other so both agents follow the same rules.")


if __name__ == "__main__":
    unittest.main()
