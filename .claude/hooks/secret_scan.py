#!/usr/bin/env python3
"""PreToolUse hook: bloqueia Write/Edit que contenham segredos aparentes.

Exit code 2 = bloqueia a ação e devolve a mensagem (stderr) ao Claude.
Sem dependências externas.
"""
import json
import re
import sys

PATTERNS = {
    "AWS access key": r"AKIA[0-9A-Z]{16}",
    "Chave privada": r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----",
    "GitHub token": r"gh[pousr]_[A-Za-z0-9]{36,}",
    "Token de bot do Telegram": r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b",
    "Token Bearer": r"Bearer\s+[A-Za-z0-9\-._~+/]{30,}=*",
    "Atribuição de segredo": (
        r"(?i)(api[_-]?key|secret|client[_-]?secret|access[_-]?token|password|passwd)"
        r"\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"
    ),
}

# Arquivos onde placeholders são esperados
ALLOWED_SUFFIXES = (".env.example", ".md")


def staged() -> int:
    """Modo pre-commit (`--staged`): vale para qualquer ferramenta, não só o Claude."""
    import subprocess

    def git(*args):
        return subprocess.run(["git", *args], capture_output=True, check=True).stdout

    names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split(b"\0")
    bad = []
    for name in filter(None, (n.decode() for n in names)):
        if name.endswith(ALLOWED_SUFFIXES):
            continue
        text = git("show", f":{name}").decode("utf-8", "ignore")
        hits = [k for k, rx in PATTERNS.items() if re.search(rx, text)]
        if hits:
            bad.append(f"  {name}: {', '.join(hits)}")
    if bad:
        print("Commit bloqueado: possível segredo\n" + "\n".join(bad), file=sys.stderr)
        return 1
    return 0


def main() -> int:
    if "--staged" in sys.argv:
        return staged()
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    path = tool_input.get("file_path", "") or ""
    if path.endswith(ALLOWED_SUFFIXES):
        return 0

    chunks = [tool_input.get("content", ""), tool_input.get("new_string", "")]
    for edit in tool_input.get("edits", []) or []:
        chunks.append(edit.get("new_string", ""))
    text = "\n".join(c for c in chunks if c)

    hits = [name for name, rx in PATTERNS.items() if re.search(rx, text)]
    if hits:
        print(
            f"Bloqueado: possível segredo em {path or 'arquivo'} ({', '.join(hits)}). "
            "Use variável de ambiente (os.environ / GitHub Secrets) em vez de valor literal.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
