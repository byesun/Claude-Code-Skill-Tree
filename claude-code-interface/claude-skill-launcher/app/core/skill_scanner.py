"""SKILL.md 파일을 찾아 Skill 목록으로 변환한다.

UI 의존성이 없으므로 `python -m app.core.skill_scanner` 로 단독 검증 가능.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.config import (
    IGNORED_DIRS,
    MAX_PARENT_LOOKUP,
    MAX_SCAN_DEPTH,
    log,
    plugins_root,
    user_skills_root,
)
from app.models import Skill, SkillSource

SKILL_FILENAME = "SKILL.md"
_FRONTMATTER_FENCE = "---"


class SkillScanner:
    """(path, mtime, size) 캐시를 가진 스캐너."""

    def __init__(self) -> None:
        self._cache: dict[Path, tuple[tuple[float, int], Skill]] = {}

    # ------------------------------------------------------------------ public

    def scan(
        self, project_cwd: Path | None = None, extra_roots: list[Path] | None = None
    ) -> list[Skill]:
        """모든 소스를 스캔하고 중복을 해소한 목록을 우선순위 순으로 반환."""
        found: list[Skill] = []
        user_marketplaces = _user_installed_marketplaces()

        for marketplace, plugin_name, root in self._plugin_roots():
            user_added = marketplace is None or marketplace in user_marketplaces
            found += self._scan_root(root, SkillSource.PLUGIN, marketplace, user_added, plugin_name)

        found += self._scan_root(user_skills_root(), SkillSource.USER)

        project_root = self._resolve_project_skills_root(project_cwd)
        if project_root:
            found += self._scan_root(project_root, SkillSource.PROJECT)

        for root in extra_roots or []:
            found += self._scan_root(root, SkillSource.USER)

        return self._dedupe(found)

    def scan_roots(self, project_cwd: Path | None = None) -> list[Path]:
        """watchdog 감시 대상으로 넘길 실제 존재하는 루트 목록."""
        roots = [user_skills_root(), plugins_root()]
        project_root = self._resolve_project_skills_root(project_cwd)
        if project_root:
            roots.append(project_root)
        return [r for r in roots if r.is_dir()]

    # ----------------------------------------------------------------- private

    def _plugin_roots(self) -> list[tuple[str | None, str, Path]]:
        """마켓플레이스/플러그인마다 레이아웃이 제각각이라 관찰된 패턴을 모두 시도한다:
        - ~/.claude/plugins/<plugin>/skills                              (플랫)
        - ~/.claude/plugins/marketplaces/<market>/skills                 (마켓플레이스 = 단일 플러그인, 예: ponytail)
        - ~/.claude/plugins/marketplaces/<market>/.claude/skills         (마켓플레이스가 .claude 관례를 따름, 예: ui-ux-pro-max)
        - ~/.claude/plugins/marketplaces/<market>/plugins/<plugin>/skills (멀티 플러그인 마켓플레이스, 예: claude-plugins-official)
        패턴이 명시적이라 cli/assets 같은 패키징용 중복 사본은 자연히 걸러진다.
        반환값은 (마켓플레이스 이름 또는 None, 슬래시 커맨드용 plugin_name, skills 폴더 경로)
        튜플 목록. 마켓플레이스 이름은 "사용자가 직접 설치했는지" 판정에, plugin_name은
        `/plugin_name:skill` 슬래시 커맨드 생성에 쓰인다 — 이 둘은 다를 수 있다
        (예: 마켓플레이스 폴더명 "karpathy-skills"의 실제 plugin.json name은
        "andrej-karpathy-skills")."""
        base = plugins_root()
        if not base.is_dir():
            return []
        out: list[tuple[str | None, str, Path]] = []
        try:
            for entry in base.iterdir():
                if entry.name == "marketplaces":
                    continue
                skills = entry / "skills"
                if skills.is_dir():
                    out.append((None, _read_plugin_name(entry, entry.name), skills))
        except OSError as exc:
            log.warning("플러그인 루트 열거 실패: %s", exc)

        marketplaces = base / "marketplaces"
        if marketplaces.is_dir():
            try:
                for market in marketplaces.iterdir():
                    if not market.is_dir():
                        continue
                    market_plugin_name = _read_plugin_name(market, market.name)
                    for candidate in (market / "skills", market / ".claude" / "skills"):
                        if candidate.is_dir():
                            out.append((market.name, market_plugin_name, candidate))

                    plugins_dir = market / "plugins"
                    if plugins_dir.is_dir():
                        for plugin in plugins_dir.iterdir():
                            skills = plugin / "skills"
                            if skills.is_dir():
                                out.append(
                                    (market.name, _read_plugin_name(plugin, plugin.name), skills)
                                )
            except OSError as exc:
                log.warning("마켓플레이스 플러그인 열거 실패: %s", exc)

        return out

    def _resolve_project_skills_root(self, cwd: Path | None) -> Path | None:
        """cwd 에서 위로 올라가며 .claude/skills 를 찾는다."""
        if not cwd:
            return None
        current = cwd
        for _ in range(MAX_PARENT_LOOKUP + 1):
            candidate = current / ".claude" / "skills"
            if candidate.is_dir():
                return candidate
            if current.parent == current:
                break
            current = current.parent
        return None

    def _scan_root(
        self,
        root: Path,
        source: SkillSource,
        marketplace: str | None = None,
        user_added: bool = True,
        plugin_name: str | None = None,
    ) -> list[Skill]:
        if not root.is_dir():
            return []
        skills: list[Skill] = []
        for md in self._iter_skill_files(root, depth=0):
            skill = self._load(md, source, marketplace, user_added, plugin_name)
            if skill:
                skills.append(skill)
        return skills

    def _iter_skill_files(self, directory: Path, depth: int):
        """깊이 제한을 두고 SKILL.md 를 찾는다. 심볼릭 링크는 따라가지 않음."""
        if depth > MAX_SCAN_DEPTH:
            return
        try:
            entries = list(directory.iterdir())
        except OSError as exc:
            log.debug("디렉터리 접근 불가 %s: %s", directory, exc)
            return
        for entry in entries:
            try:
                if entry.is_symlink():
                    continue
                if entry.is_file() and entry.name.upper() == SKILL_FILENAME.upper():
                    yield entry
                elif entry.is_dir() and entry.name not in IGNORED_DIRS:
                    yield from self._iter_skill_files(entry, depth + 1)
            except OSError:
                continue

    def _load(
        self,
        md: Path,
        source: SkillSource,
        marketplace: str | None = None,
        user_added: bool = True,
        plugin_name: str | None = None,
    ) -> Skill | None:
        try:
            stat = md.stat()
        except OSError:
            return None
        stamp = (stat.st_mtime, stat.st_size)

        cached = self._cache.get(md)
        if cached and cached[0] == stamp:
            skill = cached[1]
            skill.source = source
            skill.shadowed_by = None
            skill.marketplace = marketplace
            skill.user_added = user_added
            skill.plugin_name = plugin_name
            return skill

        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            log.warning("SKILL.md 읽기 실패 %s: %s", md, exc)
            return None

        meta, body, warning = _parse_frontmatter(text)
        root = md.parent

        name = str(meta.get("name") or root.name).strip()
        description = str(meta.get("description") or _first_sentence(body)).strip()

        skill = Skill(
            name=name,
            description=description,
            path=md,
            root=root,
            source=source,
            allowed_tools=_as_list(meta.get("allowed-tools")),
            body_preview=body[:400].strip(),
            has_scripts=(root / "scripts").is_dir(),
            has_assets=(root / "assets").is_dir(),
            command_template=(
                str(meta["x-launcher-command"])
                if meta.get("x-launcher-command")
                else None
            ),
            parse_warning=warning,
            marketplace=marketplace,
            user_added=user_added,
            plugin_name=plugin_name,
        )
        self._cache[md] = (stamp, skill)
        return skill

    def _dedupe(self, skills: list[Skill]) -> list[Skill]:
        """같은 이름은 PROJECT > USER > PLUGIN 우선. 밀린 쪽은 목록에서 제외."""
        best: dict[str, Skill] = {}
        for skill in skills:
            existing = best.get(skill.key)
            if existing is None:
                best[skill.key] = skill
                continue
            if skill.source.priority > existing.source.priority:
                skill.shadowed_by = None
                best[skill.key] = skill
            else:
                skill.shadowed_by = existing.source
        return sorted(best.values(), key=lambda s: s.name.lower())


# ------------------------------------------------------------------- helpers


def _parse_frontmatter(text: str) -> tuple[dict, str, str | None]:
    """(meta, body, warning) 반환. 실패해도 예외를 던지지 않는다."""
    stripped = text.lstrip("\ufeff")
    if not stripped.startswith(_FRONTMATTER_FENCE):
        return {}, stripped, "frontmatter 없음"

    parts = stripped.split(_FRONTMATTER_FENCE, 2)
    if len(parts) < 3:
        return {}, stripped, "frontmatter 종료 구분자 없음"

    raw_meta, body = parts[1], parts[2]
    try:
        meta = yaml.safe_load(raw_meta) or {}
    except yaml.YAMLError as exc:
        return {}, body, f"YAML 파싱 실패: {exc.__class__.__name__}"

    if not isinstance(meta, dict):
        return {}, body, "frontmatter 가 매핑이 아님"
    return meta, body, None


def _as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _read_plugin_name(plugin_dir: Path, fallback: str) -> str:
    """plugin_dir/.claude-plugin/plugin.json 의 `name` 필드를 읽는다. 폴더 이름과
    실제 plugin.json name이 다른 경우가 있어(예: karpathy-skills 마켓플레이스의 실제
    이름은 andrej-karpathy-skills) 반드시 이 파일을 읽어야 슬래시 커맨드가 맞는다.
    없거나 파싱 실패 시 폴더 이름으로 폴백한다."""
    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(plugin_json.read_text(encoding="utf-8"))
        name = data.get("name")
        if name:
            return str(name)
    except (OSError, ValueError):
        pass
    return fallback


def _user_installed_marketplaces() -> set[str]:
    """~/.claude/plugins/installed_plugins.json 을 읽어 사용자가 플러그인 매니저로
    직접 설치한 마켓플레이스 이름 집합을 반환한다. 키 형식은 "plugin@marketplace".
    claude-plugins-official 처럼 기본 번들로 딸려오는 마켓플레이스는 이 파일에
    등장하지 않으므로, 여기 없는 마켓플레이스는 "기존에 있던" 것으로 간주한다.
    파일이 없거나 파싱에 실패해도 조용히 빈 집합을 반환한다(치명적이지 않음)."""
    path = plugins_root() / "installed_plugins.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return set()
    marketplaces: set[str] = set()
    for key in plugins:
        if "@" in key:
            marketplaces.add(key.rsplit("@", 1)[1])
    return marketplaces


def _first_sentence(body: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:160]
    return "설명 없음"


if __name__ == "__main__":  # 수동 검증용
    scanner = SkillScanner()
    for s in scanner.scan(project_cwd=Path.cwd()):
        flag = "!" if s.parse_warning else " "
        added = "내추가" if s.user_added else "기본  "
        print(f"{flag} [{added}] {s.invocation:<45} {s.description[:60]}")
