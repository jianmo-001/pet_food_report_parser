"""检测报告 PDF 的归档文件夹路由（纯规则，无大模型）。

把一份报告（主要看 PDF 文件名，其次样品名）判定到共享文件夹里的某个产品子目录。
匹配逻辑全部来自 config/archive_rules.yaml，可读可改；新代号型文件夹可零配置自动派生。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SubFolderRule:
    name: str
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FolderRule:
    name: str
    codes: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    subfolders: list[SubFolderRule] = field(default_factory=list)


@dataclass(frozen=True)
class RouteResult:
    """一次路由结果。path_parts 不含根目录名，例如 ["零食", "补水汤包"]。"""

    path_parts: tuple[str, ...]
    matched: str          # 命中的代号或关键词，便于排查
    tier: str             # code / keyword / auto-code
    ambiguous: bool = False  # 多个文件夹同分冲突时为 True（按未匹配处理）

    @property
    def top_folder(self) -> str:
        return self.path_parts[0]


# 自动派生用：从“代号型”文件夹名里抽产品代号（如 "P50"、"Q01 & Q01Plus"）。
_CODE_TOKEN = re.compile(r"[A-Za-z]{1,6}\d{1,3}(?:PLUS)?", re.IGNORECASE)
_SPLIT = re.compile(r"[、，,&/\\\s]+")


def _norm(text: str) -> str:
    """统一大小写并去掉空格与商标符，供代号/关键词子串匹配。"""
    return re.sub(r"\s+", "", text).upper().replace("®", "").replace("™", "")


def load_archive_rules(path: Path) -> "ArchiveRouter":
    if not path.exists():
        raise RuntimeError(f"归档规则文件不存在：{path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    root_name = str(data.get("archive_root_name") or "").strip()
    rules: list[FolderRule] = []
    for entry in data.get("folders") or []:
        subs = [
            SubFolderRule(name=str(sub["name"]), keywords=list(sub.get("keywords") or []))
            for sub in (entry.get("subfolders") or [])
        ]
        rules.append(
            FolderRule(
                name=str(entry["name"]),
                codes=[str(c) for c in (entry.get("codes") or [])],
                keywords=[str(k) for k in (entry.get("keywords") or [])],
                subfolders=subs,
            )
        )
    return ArchiveRouter(root_name=root_name, rules=rules)


def _auto_codes(folder_name: str) -> list[str]:
    """给没在配置里的代号型文件夹自动抽取代号。中文类目文件夹返回空。"""
    codes: list[str] = []
    for token in _SPLIT.split(folder_name):
        for match in _CODE_TOKEN.findall(token):
            code = _norm(match)
            if code and code not in codes:
                codes.append(code)
    # 长代号优先（如 BK01PLUS 先于 BK01），保证最长匹配
    return sorted(codes, key=len, reverse=True)


class ArchiveRouter:
    """根据规则把文件名路由到目标文件夹路径。

    与飞书无关、不依赖网络，方便用本地镜像做全量验证。
    传入 ``known_folders`` 时，会对配置里没有、但云端真实存在的代号型文件夹自动派生规则。
    """

    def __init__(self, root_name: str, rules: list[FolderRule]) -> None:
        self.root_name = root_name
        self._rules: dict[str, FolderRule] = {rule.name: rule for rule in rules}

    @property
    def rules(self) -> list[FolderRule]:
        return list(self._rules.values())

    def with_live_folders(self, folder_names: list[str]) -> "ArchiveRouter":
        """合并云端真实文件夹：配置里有的用配置，没有的尝试自动派生代号规则。"""
        merged = dict(self._rules)
        for name in folder_names:
            if name in merged:
                continue
            codes = _auto_codes(name)
            if codes:
                merged[name] = FolderRule(name=name, codes=codes)
        return ArchiveRouter(self.root_name, list(merged.values()))

    def classify(self, file_name: str, sample_name: str | None = None) -> RouteResult | None:
        """返回路由结果；判不出来返回 None（应进未匹配清单）。"""
        haystack = _norm(file_name) + "" + _norm(sample_name or "")

        # 候选打分：(tier_rank, 命中长度)。代号 tier=2 永远压过关键词 tier=1。
        best_key: tuple[int, int] | None = None
        best_folder: FolderRule | None = None
        best_token = ""
        best_tier = ""
        tie = False

        for rule in self._rules.values():
            for code in rule.codes:
                if _norm(code) in haystack:
                    key = (2, len(_norm(code)))
                    best_key, best_folder, best_token, best_tier, tie = _take(
                        key, rule, code, "code", best_key, best_folder, best_token, best_tier, tie
                    )
            for kw in rule.keywords:
                if _norm(kw) in haystack:
                    key = (1, len(_norm(kw)))
                    best_key, best_folder, best_token, best_tier, tie = _take(
                        key, rule, kw, "keyword", best_key, best_folder, best_token, best_tier, tie
                    )

        if best_folder is None:
            return None
        if tie:
            return RouteResult((best_folder.name,), best_token, best_tier, ambiguous=True)

        parts: tuple[str, ...] = (best_folder.name,)
        if best_folder.subfolders:
            sub = self._classify_sub(haystack, best_folder)
            if sub:
                parts = (best_folder.name, sub)
        return RouteResult(parts, best_token, best_tier)

    def _classify_sub(self, haystack: str, folder: FolderRule) -> str | None:
        best_len = 0
        best_name: str | None = None
        for sub in folder.subfolders:
            for kw in sub.keywords:
                if _norm(kw) in haystack and len(_norm(kw)) > best_len:
                    best_len = len(_norm(kw))
                    best_name = sub.name
        return best_name

    def archive_path(self, result: RouteResult) -> str:
        """回写多维表的归档路径文字，例如 诚实一口大货报告/零食/补水汤包。"""
        parts = [self.root_name, *result.path_parts] if self.root_name else list(result.path_parts)
        return "/".join(parts)


def _take(key, rule, token, tier, best_key, best_folder, best_token, best_tier, tie):
    """挑选更优候选；与当前最优同分但属不同文件夹则标记为冲突。"""
    if best_key is None or key > best_key:
        return key, rule, token, tier, False
    if key == best_key and rule.name != (best_folder.name if best_folder else None):
        return best_key, best_folder, best_token, best_tier, True
    return best_key, best_folder, best_token, best_tier, tie
