from __future__ import annotations

from app.models import (
    CodeSkillChangedFilePublic,
    CodeSkillChangedSymbolPublic,
    CodeSkillImpactedFilePublic,
    CodeSkillRecommendedTestPublic,
    CodeSkillReviewChecklistItemPublic,
    CodeSkillRiskSignalPublic,
)
from app.services.code_skill import deduplicate_strings


HIGH_RISK_PATH_KEYWORDS = {
    "auth",
    "authentication",
    "authorization",
    "permission",
    "permissions",
    "security",
    "password",
    "token",
    "payment",
    "transaction",
    "migration",
    "migrations",
}

MEDIUM_RISK_PATH_KEYWORDS = {
    "upload",
    "archive",
    "storage",
    "database",
    "model",
    "models",
    "schema",
    "router",
    "routes",
    "api",
    "config",
}


def normalize_risk_level(risk_level: str) -> str:
    normalized_level = risk_level.strip().lower()

    if normalized_level in {"low", "medium", "high"}:
        return normalized_level

    return "low"


def calculate_overall_risk_level(
    risk_signals: list[CodeSkillRiskSignalPublic],
) -> str:
    levels = {
        normalize_risk_level(signal.risk_level)
        for signal in risk_signals
    }

    if "high" in levels:
        return "high"

    if "medium" in levels:
        return "medium"

    return "low"


def path_contains_keyword(
    *,
    file_path: str,
    keywords: set[str],
) -> list[str]:
    normalized_path = (
        file_path
        .replace("\\", "/")
        .lower()
    )

    matched_keywords = [
        keyword
        for keyword in sorted(keywords)
        if keyword in normalized_path
    ]

    return matched_keywords


def build_review_risk_signals(
    *,
    changed_files: list[CodeSkillChangedFilePublic],
    changed_symbols: list[CodeSkillChangedSymbolPublic],
    unresolved_files: list[str],
    impacted_files: list[CodeSkillImpactedFilePublic],
    recommended_tests: list[CodeSkillRecommendedTestPublic],
    uncovered_changed_files: list[str],
    uncovered_symbols: list[str],
) -> list[CodeSkillRiskSignalPublic]:
    risk_signals: list[CodeSkillRiskSignalPublic] = []

    total_changed_lines = sum(
        changed_file.added_lines + changed_file.deleted_lines
        for changed_file in changed_files
    )

    if total_changed_lines >= 500:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="large_change",
                risk_level="high",
                title="本次代码改动规模较大",
                message=(
                    f"本次变更共涉及 {total_changed_lines} 行新增或删除，"
                    "建议拆分 Review，并重点检查跨模块影响。"
                ),
                evidence=[
                    f"changed_lines={total_changed_lines}",
                ],
                related_files=[
                    changed_file.file_path
                    for changed_file in changed_files
                ],
            )
        )
    elif total_changed_lines >= 200:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="large_change",
                risk_level="medium",
                title="本次代码改动规模偏大",
                message=(
                    f"本次变更共涉及 {total_changed_lines} 行新增或删除，"
                    "人工 Review 时需要关注逻辑遗漏。"
                ),
                evidence=[
                    f"changed_lines={total_changed_lines}",
                ],
                related_files=[
                    changed_file.file_path
                    for changed_file in changed_files
                ],
            )
        )

    if len(changed_files) >= 20:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="wide_change_scope",
                risk_level="high",
                title="变更文件范围较广",
                message=(
                    f"本次变更涉及 {len(changed_files)} 个文件，"
                    "可能包含跨模块行为变化。"
                ),
                evidence=[
                    f"changed_files={len(changed_files)}",
                ],
                related_files=[
                    changed_file.file_path
                    for changed_file in changed_files
                ],
            )
        )
    elif len(changed_files) >= 8:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="wide_change_scope",
                risk_level="medium",
                title="变更涉及多个文件",
                message=(
                    f"本次变更涉及 {len(changed_files)} 个文件，"
                    "建议检查模块之间的依赖关系。"
                ),
                evidence=[
                    f"changed_files={len(changed_files)}",
                ],
                related_files=[
                    changed_file.file_path
                    for changed_file in changed_files
                ],
            )
        )

    if unresolved_files:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="unresolved_changed_files",
                risk_level="medium",
                title="部分变更文件无法定位代码符号",
                message=(
                    f"有 {len(unresolved_files)} 个变更文件未能映射到"
                    "知识库中的代码文件或符号。"
                ),
                evidence=[
                    f"unresolved_files={len(unresolved_files)}",
                ],
                related_files=unresolved_files,
            )
        )

    fallback_symbols = [
        symbol
        for symbol in changed_symbols
        if symbol.symbol_type == "file"
        or symbol.confidence <= 0.3
    ]

    if fallback_symbols:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="symbol_location_fallback",
                risk_level="medium",
                title="部分变更只能定位到文件级",
                message=(
                    f"有 {len(fallback_symbols)} 条变更未定位到明确的"
                    "函数、类或方法，影响分析精度可能下降。"
                ),
                evidence=[
                    (
                        f"{symbol.file_path}:"
                        f"{symbol.changed_hunk_new_start}-"
                        f"{symbol.changed_hunk_new_end}"
                    )
                    for symbol in fallback_symbols
                ],
                related_files=deduplicate_strings(
                    [
                        symbol.file_path
                        for symbol in fallback_symbols
                    ]
                ),
                related_symbols=deduplicate_strings(
                    [
                        symbol.symbol_name
                        for symbol in fallback_symbols
                    ]
                ),
            )
        )

    if len(impacted_files) >= 10:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="high_impact_fanout",
                risk_level="high",
                title="变更影响范围较大",
                message=(
                    f"静态分析发现 {len(impacted_files)} 个可能受影响文件，"
                    "建议重点检查公共函数和跨模块调用。"
                ),
                evidence=[
                    f"impacted_files={len(impacted_files)}",
                ],
                related_files=[
                    item.file_path
                    for item in impacted_files
                ],
            )
        )
    elif len(impacted_files) >= 5:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="high_impact_fanout",
                risk_level="medium",
                title="变更存在一定调用扩散",
                message=(
                    f"静态分析发现 {len(impacted_files)} 个可能受影响文件。"
                ),
                evidence=[
                    f"impacted_files={len(impacted_files)}",
                ],
                related_files=[
                    item.file_path
                    for item in impacted_files
                ],
            )
        )

    high_risk_files: list[str] = []
    high_risk_keywords: list[str] = []

    medium_risk_files: list[str] = []
    medium_risk_keywords: list[str] = []

    for changed_file in changed_files:
        current_high_keywords = path_contains_keyword(
            file_path=changed_file.file_path,
            keywords=HIGH_RISK_PATH_KEYWORDS,
        )

        if current_high_keywords:
            high_risk_files.append(changed_file.file_path)
            high_risk_keywords.extend(current_high_keywords)

        current_medium_keywords = path_contains_keyword(
            file_path=changed_file.file_path,
            keywords=MEDIUM_RISK_PATH_KEYWORDS,
        )

        if current_medium_keywords:
            medium_risk_files.append(changed_file.file_path)
            medium_risk_keywords.extend(current_medium_keywords)

    if high_risk_files:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="sensitive_module_change",
                risk_level="high",
                title="变更涉及高敏感模块",
                message=(
                    "变更路径包含鉴权、安全、事务、支付或数据库迁移"
                    "相关模块，需要进行更严格的人工审查。"
                ),
                evidence=deduplicate_strings(high_risk_keywords),
                related_files=deduplicate_strings(high_risk_files),
            )
        )

    if medium_risk_files:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="important_module_change",
                risk_level="medium",
                title="变更涉及重要基础模块",
                message=(
                    "变更涉及 API、文件上传、压缩包、存储、配置或"
                    "数据库模型等基础能力。"
                ),
                evidence=deduplicate_strings(medium_risk_keywords),
                related_files=deduplicate_strings(medium_risk_files),
            )
        )

    if not recommended_tests and changed_files:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="missing_test_evidence",
                risk_level="high",
                title="未找到明确相关的测试文件",
                message=(
                    "当前知识库中没有找到与本次变更明显相关的测试文件，"
                    "建议人工确认测试范围并补充测试。"
                ),
                evidence=[
                    "recommended_tests=0",
                ],
                related_files=[
                    changed_file.file_path
                    for changed_file in changed_files
                ],
            )
        )
    elif uncovered_changed_files:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="partial_test_gap",
                risk_level="medium",
                title="部分变更文件缺少测试关联证据",
                message=(
                    f"有 {len(uncovered_changed_files)} 个变更文件"
                    "没有匹配到明确的测试文件。"
                ),
                evidence=[
                    f"uncovered_changed_files={len(uncovered_changed_files)}",
                ],
                related_files=uncovered_changed_files,
            )
        )

    if uncovered_symbols:
        risk_signals.append(
            CodeSkillRiskSignalPublic(
                risk_type="uncovered_changed_symbols",
                risk_level="medium",
                title="部分变更符号未在测试中直接出现",
                message=(
                    f"有 {len(uncovered_symbols)} 个相关符号"
                    "没有在推荐测试代码中直接匹配到。"
                ),
                evidence=[
                    f"uncovered_symbols={len(uncovered_symbols)}",
                ],
                related_symbols=uncovered_symbols,
            )
        )

    return risk_signals


def build_review_checklist(
    *,
    changed_files: list[CodeSkillChangedFilePublic],
    changed_symbols: list[CodeSkillChangedSymbolPublic],
    impacted_files: list[CodeSkillImpactedFilePublic],
    recommended_tests: list[CodeSkillRecommendedTestPublic],
    risk_signals: list[CodeSkillRiskSignalPublic],
) -> list[CodeSkillReviewChecklistItemPublic]:
    checklist: list[CodeSkillReviewChecklistItemPublic] = []

    changed_file_paths = deduplicate_strings(
        [
            changed_file.file_path
            for changed_file in changed_files
        ]
    )

    changed_symbol_names = deduplicate_strings(
        [
            symbol.symbol_name
            for symbol in changed_symbols
            if symbol.symbol_type != "file"
        ]
    )

    checklist.append(
        CodeSkillReviewChecklistItemPublic(
            item_id="review-changed-symbols",
            category="change_scope",
            priority="high",
            description="逐项检查变更函数、类和方法的行为变化",
            reason=(
                f"本次共定位到 {len(changed_symbols)} 条变更符号记录。"
            ),
            related_files=changed_file_paths,
            related_symbols=changed_symbol_names,
        )
    )

    if impacted_files:
        checklist.append(
            CodeSkillReviewChecklistItemPublic(
                item_id="review-impacted-callers",
                category="impact_analysis",
                priority="high",
                description="检查直接调用方和受影响文件是否仍满足原有接口约定",
                reason=(
                    f"静态分析发现 {len(impacted_files)} 个可能受影响文件。"
                ),
                related_files=[
                    item.file_path
                    for item in impacted_files
                ],
                related_symbols=deduplicate_strings(
                    [
                        symbol_name
                        for item in impacted_files
                        for symbol_name in item.impacted_symbol_names
                    ]
                ),
            )
        )

    if recommended_tests:
        checklist.append(
            CodeSkillReviewChecklistItemPublic(
                item_id="run-recommended-tests",
                category="testing",
                priority="high",
                description="运行系统推荐的相关测试文件",
                reason=(
                    f"系统根据路径和符号匹配推荐了 "
                    f"{len(recommended_tests)} 个测试文件。"
                ),
                related_files=[
                    test.test_file_path
                    for test in recommended_tests
                ],
                related_symbols=deduplicate_strings(
                    [
                        symbol_name
                        for test in recommended_tests
                        for symbol_name in test.related_symbols
                    ]
                ),
            )
        )
    else:
        checklist.append(
            CodeSkillReviewChecklistItemPublic(
                item_id="add-missing-tests",
                category="testing",
                priority="high",
                description="人工确认测试范围并补充缺失的单元测试或集成测试",
                reason="当前没有找到明确相关的测试文件。",
                related_files=changed_file_paths,
                related_symbols=changed_symbol_names,
            )
        )

    archive_related_files = [
        file_path
        for file_path in changed_file_paths
        if path_contains_keyword(
            file_path=file_path,
            keywords={
                "upload",
                "archive",
                "zip",
                "rar",
                "storage",
            },
        )
    ]

    if archive_related_files:
        checklist.extend(
            [
                CodeSkillReviewChecklistItemPublic(
                    item_id="check-upload-size-limit",
                    category="file_upload",
                    priority="high",
                    description="检查上传文件大小限制是否对 ZIP 和 RAR 一致生效",
                    reason="本次变更涉及上传或压缩包处理逻辑。",
                    related_files=archive_related_files,
                ),
                CodeSkillReviewChecklistItemPublic(
                    item_id="check-malformed-archives",
                    category="file_upload",
                    priority="high",
                    description="测试空文件、损坏压缩包、加密压缩包和超大压缩包",
                    reason="压缩包输入属于不可信外部数据。",
                    related_files=archive_related_files,
                ),
                CodeSkillReviewChecklistItemPublic(
                    item_id="check-temporary-file-cleanup",
                    category="resource_management",
                    priority="medium",
                    description="检查异常路径下临时文件和文件句柄是否正确清理",
                    reason="大文件上传和解压可能占用磁盘与文件描述符。",
                    related_files=archive_related_files,
                ),
                CodeSkillReviewChecklistItemPublic(
                    item_id="check-archive-path-traversal",
                    category="security",
                    priority="high",
                    description="检查压缩包成员路径是否防止目录穿越和符号链接逃逸",
                    reason="ZIP/RAR 解压可能受到路径穿越攻击。",
                    related_files=archive_related_files,
                ),
            ]
        )

    api_related_files = [
        file_path
        for file_path in changed_file_paths
        if path_contains_keyword(
            file_path=file_path,
            keywords={
                "api",
                "router",
                "routes",
                "endpoint",
            },
        )
    ]

    if api_related_files:
        checklist.append(
            CodeSkillReviewChecklistItemPublic(
                item_id="check-api-compatibility",
                category="api",
                priority="high",
                description="检查接口参数、响应结构和错误码是否保持兼容",
                reason="本次改动涉及 API 或路由文件。",
                related_files=api_related_files,
            )
        )

    risk_types = {
        signal.risk_type
        for signal in risk_signals
    }

    if "sensitive_module_change" in risk_types:
        checklist.append(
            CodeSkillReviewChecklistItemPublic(
                item_id="security-manual-review",
                category="security",
                priority="high",
                description="安排人工安全审查，检查鉴权、权限、事务和敏感数据处理",
                reason="风险分析识别到高敏感模块变更。",
                related_files=deduplicate_strings(
                    [
                        file_path
                        for signal in risk_signals
                        if signal.risk_type == "sensitive_module_change"
                        for file_path in signal.related_files
                    ]
                ),
            )
        )

    return checklist


def build_review_limitations() -> list[str]:
    return [
        (
            "变更符号定位依赖代码 chunk 中的 file_path、"
            "symbol_name、symbol_type 和 line_range 元数据。"
        ),
        (
            "当前影响分析主要基于符号文本匹配，不等同于完整 AST、"
            "LSP 或编译器级调用图。"
        ),
        (
            "动态调用、反射、依赖注入、字符串路由和运行时生成代码"
            "可能无法被静态匹配发现。"
        ),
        (
            "测试推荐基于文件路径、文件名和符号出现情况，"
            "不等同于真实代码覆盖率证明。"
        ),
        (
            "风险信号用于辅助人工 Review，不能替代安全审计、"
            "单元测试、集成测试和生产验证。"
        ),
    ]