from __future__ import annotations

import uuid
from time import perf_counter
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select, col

from app.models import (
    CodeSkillBuildReviewEvidenceRequest,
    CodeSkillChangedFilePublic,
    CodeSkillChangedSymbolInput,
    CodeSkillChangeSummaryPublic,
    CodeSkillDiffHunkPublic,
    CodeSkillEvidenceTraceStepPublic,
    CodeSkillFindImpactsRequest,
    CodeSkillFindImpactsResponse,
    CodeSkillImpactedFileInput,
    CodeSkillLocateChangedSymbolsRequest,
    CodeSkillLocateChangedSymbolsResponse,
    CodeSkillRecommendTestsRequest,
    CodeSkillRecommendTestsResponse,
    CodeSkillReviewEvidenceResponse,
)
from app.services.code_skill import (
    DiffChangedFile,
    deduplicate_strings,
    parse_git_diff,
)
from app.services.code_skill_review import (
    build_review_checklist,
    build_review_limitations,
    build_review_risk_signals,
    calculate_overall_risk_level,
)


from app.models import (
    Document,
    CodeSkillChangedSymbolPublic,
    DocumentChunk,
    CodeSkillSymbolImpactPublic,
    CodeSkillImpactReferencePublic,
    CodeSkillRecommendedTestPublic,
    CodeSkillImpactedFilePublic,
)
from app.services.code_skill import (
    repo_paths_match,
    extract_code_chunk_metadata,
    parse_line_range,
    get_hunk_new_line_range,
    calculate_range_overlap,
    build_changed_symbol_reason,
    calculate_symbol_confidence,
    build_file_level_fallback_symbol,
    build_impact_reference_reason,
    build_reference_preview,
    calculate_reference_confidence,
    count_symbol_occurrences,
    is_definition_chunk_for_symbol,
    build_test_gap_notes,
    build_test_candidate_preview,
    calculate_test_recommendation_confidence,
    find_symbol_occurrences_in_content,
    calculate_test_path_match,
    is_test_file_path,
    resolve_code_file_path,
)


def elapsed_milliseconds(
    start_time: float,
) -> int:
    return max(
        0,
        int((perf_counter() - start_time) * 1000),
    )


def build_changed_file_public(
    changed_file: DiffChangedFile,
) -> CodeSkillChangedFilePublic:
    return CodeSkillChangedFilePublic(
        old_path=changed_file.old_path,
        new_path=changed_file.new_path,
        file_path=changed_file.file_path,
        change_type=changed_file.change_type,
        added_lines=changed_file.added_lines,
        deleted_lines=changed_file.deleted_lines,
        hunks=[
            CodeSkillDiffHunkPublic(
                old_start=hunk.old_start,
                old_count=hunk.old_count,
                new_start=hunk.new_start,
                new_count=hunk.new_count,
                added_lines=hunk.added_lines,
                deleted_lines=hunk.deleted_lines,
                context_lines=hunk.context_lines,
            )
            for hunk in changed_file.hunks
        ],
    )


def locate_changed_symbols_for_knowledge_base(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    request: CodeSkillLocateChangedSymbolsRequest,
) -> CodeSkillLocateChangedSymbolsResponse:

    changed_files = parse_git_diff(request.diff_text)

    public_changed_files = [
        build_changed_file_public(changed_file) for changed_file in changed_files
    ]

    documents = session.exec(
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .order_by(col(Document.original_filename))
    ).all()

    changed_symbols: list[CodeSkillChangedSymbolPublic] = []
    unresolved_files: list[str] = []

    for changed_file in changed_files:
        matching_documents = [
            document
            for document in documents
            if repo_paths_match(
                document_path=document.original_filename,
                changed_path=changed_file.file_path,
            )
        ]

        if not matching_documents:
            unresolved_files.append(changed_file.file_path)
            continue

        file_symbol_count_before = len(changed_symbols)

        for document in matching_documents:
            chunks = session.exec(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document.id)
                .order_by(col(DocumentChunk.chunk_index))
            ).all()

            for chunk in chunks:
                metadata = extract_code_chunk_metadata(chunk.content)

                symbol_name = metadata.get("symbol_name")
                symbol_type = metadata.get("symbol_type")
                line_range = metadata.get("line_range")
                metadata_file_path = (
                    metadata.get("file_path") or document.original_filename
                )

                if not symbol_name or symbol_name == "-":
                    continue

                if not symbol_type or symbol_type == "-":
                    continue

                symbol_line_range = parse_line_range(line_range)

                if symbol_line_range is None:
                    continue

                symbol_start, symbol_end = symbol_line_range

                for hunk in changed_file.hunks:
                    hunk_start, hunk_end = get_hunk_new_line_range(hunk)

                    overlap = calculate_range_overlap(
                        first_start=symbol_start,
                        first_end=symbol_end,
                        second_start=hunk_start,
                        second_end=hunk_end,
                    )

                    if overlap is None:
                        continue

                    overlap_start, overlap_end, overlap_line_count = overlap

                    changed_symbols.append(
                        CodeSkillChangedSymbolPublic(
                            document_id=document.id,
                            chunk_id=chunk.id,
                            chunk_index=chunk.chunk_index,
                            document_filename=document.original_filename,
                            file_path=metadata_file_path,
                            symbol_name=symbol_name,
                            symbol_type=symbol_type,
                            line_range=line_range,
                            symbol_start_line=symbol_start,
                            symbol_end_line=symbol_end,
                            changed_hunk_new_start=hunk_start,
                            changed_hunk_new_end=hunk_end,
                            overlap_start_line=overlap_start,
                            overlap_end_line=overlap_end,
                            overlap_line_count=overlap_line_count,
                            confidence=calculate_symbol_confidence(
                                overlap_line_count=overlap_line_count,
                                hunk_start=hunk_start,
                                hunk_end=hunk_end,
                                symbol_start=symbol_start,
                                symbol_end=symbol_end,
                            ),
                            reason=build_changed_symbol_reason(
                                symbol_name=symbol_name,
                                symbol_type=symbol_type,
                                symbol_start=symbol_start,
                                symbol_end=symbol_end,
                                hunk_start=hunk_start,
                                hunk_end=hunk_end,
                            ),
                        )
                    )

        if (
            request.include_file_level_fallback
            and len(changed_symbols) == file_symbol_count_before
        ):
            for document in matching_documents:
                for hunk in changed_file.hunks:
                    fallback = build_file_level_fallback_symbol(
                        file_path=changed_file.file_path,
                        hunk=hunk,
                    )

                    changed_symbols.append(
                        CodeSkillChangedSymbolPublic(
                            document_id=document.id,
                            chunk_id=None,
                            chunk_index=None,
                            document_filename=document.original_filename,
                            file_path=changed_file.file_path,
                            symbol_name=fallback["symbol_name"],
                            symbol_type=fallback["symbol_type"],
                            line_range=fallback["line_range"],
                            symbol_start_line=fallback["symbol_start_line"],
                            symbol_end_line=fallback["symbol_end_line"],
                            changed_hunk_new_start=fallback["changed_hunk_new_start"],
                            changed_hunk_new_end=fallback["changed_hunk_new_end"],
                            overlap_start_line=fallback["overlap_start_line"],
                            overlap_end_line=fallback["overlap_end_line"],
                            overlap_line_count=fallback["overlap_line_count"],
                            confidence=fallback["confidence"],
                            reason=fallback["reason"],
                        )
                    )

    changed_symbols.sort(
        key=lambda item: (
            -item.confidence,
            item.file_path,
            item.symbol_start_line or 0,
            item.symbol_name,
        )
    )

    return CodeSkillLocateChangedSymbolsResponse(
        changed_files=public_changed_files,
        changed_symbols=changed_symbols,
        unresolved_files=unresolved_files,
        total_files=len(public_changed_files),
        total_symbols=len(changed_symbols),
        total_unresolved_files=len(unresolved_files),
    )


def build_impacted_file_summaries(
    *,
    references: list[CodeSkillImpactReferencePublic],
) -> list[CodeSkillImpactedFilePublic]:
    file_map: dict[str, dict[str, Any]] = {}

    for reference in references:
        file_path = reference.file_path

        if file_path not in file_map:
            file_map[file_path] = {
                "file_path": file_path,
                "document_filename": reference.document_filename,
                "reference_count": 0,
                "impacted_symbol_names": set(),
                "max_confidence": 0,
            }

        item = file_map[file_path]
        item["reference_count"] += reference.occurrence_count
        item["max_confidence"] = max(item["max_confidence"], reference.confidence)

        if reference.containing_symbol_name:
            item["impacted_symbol_names"].add(reference.containing_symbol_name)

    summaries: list[CodeSkillImpactedFilePublic] = []

    for item in file_map.values():
        impacted_symbol_names = sorted(item["impacted_symbol_names"])

        summaries.append(
            CodeSkillImpactedFilePublic(
                file_path=item["file_path"],
                document_filename=item["document_filename"],
                reference_count=item["reference_count"],
                impacted_symbol_names=impacted_symbol_names,
                confidence=item["max_confidence"],
                reason=(
                    f"该文件中发现 {item['reference_count']} 处相关引用，"
                    f"涉及 {len(impacted_symbol_names)} 个代码符号"
                ),
            )
        )

    summaries.sort(
        key=lambda item: (
            -item.confidence,
            -item.reference_count,
            item.file_path,
        )
    )

    return summaries


def find_impacts_for_knowledge_base(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    request: CodeSkillFindImpactsRequest,
) -> CodeSkillFindImpactsResponse:
    max_references_per_symbol = max(
        1,
        min(request.max_references_per_symbol, 100),
    )

    documents = session.exec(
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .order_by(col(Document.original_filename))
    ).all()

    symbol_impacts: list[CodeSkillSymbolImpactPublic] = []
    all_references: list[CodeSkillImpactReferencePublic] = []

    for changed_symbol in request.changed_symbols:
        references: list[CodeSkillImpactReferencePublic] = []

        for document in documents:
            chunks = session.exec(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document.id)
                .order_by(col(DocumentChunk.chunk_index))
            ).all()

            for chunk in chunks:
                metadata = extract_code_chunk_metadata(chunk.content)

                if (
                    not request.include_definition_chunk
                    and is_definition_chunk_for_symbol(
                        metadata=metadata,
                        chunk_id=str(chunk.id),
                        changed_symbol_name=changed_symbol.symbol_name,
                        changed_symbol_file_path=changed_symbol.file_path,
                        changed_symbol_chunk_id=(
                            str(changed_symbol.chunk_id)
                            if changed_symbol.chunk_id
                            else None
                        ),
                    )
                ):
                    continue

                occurrence_count = count_symbol_occurrences(
                    content=chunk.content,
                    symbol_name=changed_symbol.symbol_name,
                )

                if occurrence_count <= 0:
                    continue

                metadata_file_path = (
                    metadata.get("file_path") or document.original_filename
                )

                containing_symbol_name = metadata.get("symbol_name")
                containing_symbol_type = metadata.get("symbol_type")
                containing_line_range = metadata.get("line_range")

                same_file = repo_paths_match(
                    document_path=metadata_file_path,
                    changed_path=changed_symbol.file_path,
                )

                confidence = calculate_reference_confidence(
                    occurrence_count=occurrence_count,
                    same_file=same_file,
                    containing_symbol_name=containing_symbol_name,
                )

                reference = CodeSkillImpactReferencePublic(
                    document_id=document.id,
                    chunk_id=chunk.id,
                    chunk_index=chunk.chunk_index,
                    document_filename=document.original_filename,
                    file_path=metadata_file_path,
                    changed_symbol_name=changed_symbol.symbol_name,
                    changed_symbol_type=changed_symbol.symbol_type,
                    containing_symbol_name=containing_symbol_name,
                    containing_symbol_type=containing_symbol_type,
                    containing_line_range=containing_line_range,
                    occurrence_count=occurrence_count,
                    preview=build_reference_preview(
                        content=chunk.content,
                        symbol_name=changed_symbol.symbol_name,
                    ),
                    confidence=confidence,
                    reason=build_impact_reference_reason(
                        changed_symbol_name=changed_symbol.symbol_name,
                        occurrence_count=occurrence_count,
                        containing_symbol_name=containing_symbol_name,
                        file_path=metadata_file_path,
                    ),
                )

                references.append(reference)

        references.sort(
            key=lambda item: (
                -item.confidence,
                -item.occurrence_count,
                item.file_path,
                item.chunk_index,
            )
        )

        references = references[:max_references_per_symbol]

        impacted_files = build_impacted_file_summaries(
            references=references,
        )

        all_references.extend(references)

        symbol_impacts.append(
            CodeSkillSymbolImpactPublic(
                changed_symbol=changed_symbol,
                references=references,
                impacted_files=impacted_files,
                total_references=len(references),
                total_impacted_files=len(impacted_files),
            )
        )

    impacted_files_summary = build_impacted_file_summaries(
        references=all_references,
    )

    return CodeSkillFindImpactsResponse(
        symbol_impacts=symbol_impacts,
        impacted_files_summary=impacted_files_summary,
        total_symbols=len(request.changed_symbols),
        total_references=len(all_references),
        total_impacted_files=len(impacted_files_summary),
    )


def recommend_tests_for_knowledge_base(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    request: CodeSkillRecommendTestsRequest,
) -> CodeSkillRecommendTestsResponse:
    max_test_files = max(
        1,
        min(request.max_test_files, 100),
    )

    min_confidence = max(
        0.0,
        min(request.min_confidence, 1.0),
    )

    changed_file_paths = deduplicate_strings(
        [
            *request.changed_files,
            *[symbol.file_path for symbol in request.changed_symbols],
        ]
    )

    impacted_file_paths = deduplicate_strings(
        [impacted_file.file_path for impacted_file in request.impacted_files]
    )

    symbol_names = deduplicate_strings(
        [
            *[
                symbol.symbol_name
                for symbol in request.changed_symbols
                if symbol.symbol_name
            ],
            *[
                symbol_name
                for impacted_file in request.impacted_files
                for symbol_name in impacted_file.impacted_symbol_names
            ],
        ]
    )

    if not changed_file_paths and not impacted_file_paths and not symbol_names:
        raise HTTPException(
            status_code=400,
            detail=(
                "At least one changed file, changed symbol, "
                "or impacted file is required"
            ),
        )

    documents = session.exec(
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .order_by(col(Document.original_filename))
    ).all()

    recommended_tests: list[CodeSkillRecommendedTestPublic] = []
    total_test_candidates = 0

    for document in documents:
        chunks = session.exec(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(col(DocumentChunk.chunk_index))
        ).all()

        if not chunks:
            continue

        chunk_contents = [chunk.content for chunk in chunks]

        test_file_path = resolve_code_file_path(
            document_filename=document.original_filename,
            chunk_contents=chunk_contents,
        )

        if not (
            is_test_file_path(test_file_path)
            or is_test_file_path(document.original_filename)
        ):
            continue

        total_test_candidates += 1

        best_path_match_score = 0.0
        related_changed_files: list[str] = []
        related_impacted_files: list[str] = []
        matched_reasons: list[str] = []

        for changed_file_path in changed_file_paths:
            score, reasons = calculate_test_path_match(
                test_file_path=test_file_path,
                source_file_path=changed_file_path,
            )

            if score < 0.2:
                continue

            best_path_match_score = max(
                best_path_match_score,
                score,
            )

            related_changed_files.append(changed_file_path)

            matched_reasons.extend(
                [f"与变更文件 {changed_file_path} 相关：{reason}" for reason in reasons]
            )

        for impacted_file_path in impacted_file_paths:
            score, reasons = calculate_test_path_match(
                test_file_path=test_file_path,
                source_file_path=impacted_file_path,
            )

            if score < 0.2:
                continue

            best_path_match_score = max(
                best_path_match_score,
                score,
            )

            related_impacted_files.append(impacted_file_path)

            matched_reasons.extend(
                [
                    f"与受影响文件 {impacted_file_path} 相关：{reason}"
                    for reason in reasons
                ]
            )

        symbol_occurrence_map: dict[str, int] = {}

        for chunk_content in chunk_contents:
            current_occurrences = find_symbol_occurrences_in_content(
                content=chunk_content,
                symbol_names=symbol_names,
            )

            for symbol_name, count in current_occurrences.items():
                symbol_occurrence_map[symbol_name] = (
                    symbol_occurrence_map.get(symbol_name, 0) + count
                )

        related_symbols = sorted(symbol_occurrence_map.keys())
        symbol_match_count = sum(symbol_occurrence_map.values())

        if related_symbols:
            symbol_description = "、".join(
                f"{symbol_name}({symbol_occurrence_map[symbol_name]}次)"
                for symbol_name in related_symbols
            )

            matched_reasons.append(f"测试代码中直接出现相关符号：{symbol_description}")

        confidence = calculate_test_recommendation_confidence(
            path_match_score=best_path_match_score,
            symbol_match_count=symbol_match_count,
            matched_symbol_count=len(related_symbols),
            related_file_count=(
                len(related_changed_files) + len(related_impacted_files)
            ),
        )

        if confidence < min_confidence:
            continue

        recommended_tests.append(
            CodeSkillRecommendedTestPublic(
                document_id=document.id,
                document_filename=document.original_filename,
                test_file_path=test_file_path,
                confidence=confidence,
                path_match_score=best_path_match_score,
                symbol_match_count=symbol_match_count,
                related_changed_files=deduplicate_strings(related_changed_files),
                related_impacted_files=deduplicate_strings(related_impacted_files),
                related_symbols=related_symbols,
                matched_reasons=deduplicate_strings(matched_reasons),
                preview=build_test_candidate_preview(
                    chunk_contents=chunk_contents,
                    matched_symbols=related_symbols,
                ),
            )
        )

    recommended_tests.sort(
        key=lambda item: (
            -item.confidence,
            -item.symbol_match_count,
            -item.path_match_score,
            item.test_file_path,
        )
    )

    recommended_tests = recommended_tests[:max_test_files]

    covered_changed_files = {
        file_path
        for recommended_test in recommended_tests
        for file_path in recommended_test.related_changed_files
    }

    covered_symbols = {
        symbol_name
        for recommended_test in recommended_tests
        for symbol_name in recommended_test.related_symbols
    }

    uncovered_changed_files = [
        file_path
        for file_path in changed_file_paths
        if file_path not in covered_changed_files
    ]

    uncovered_symbols = [
        symbol_name
        for symbol_name in symbol_names
        if symbol_name not in covered_symbols
    ]

    test_gap_notes = build_test_gap_notes(
        recommended_test_count=len(recommended_tests),
        uncovered_changed_files=uncovered_changed_files,
        uncovered_symbols=uncovered_symbols,
    )

    return CodeSkillRecommendTestsResponse(
        recommended_tests=recommended_tests,
        test_gap_notes=test_gap_notes,
        uncovered_changed_files=uncovered_changed_files,
        uncovered_symbols=uncovered_symbols,
        total_test_candidates=total_test_candidates,
        total_recommended_tests=len(recommended_tests),
        limitations=[
            (
                "当前版本根据文件路径、文件名和符号出现情况进行"
                "启发式推荐，不等同于代码覆盖率证明。"
            ),
            ("动态调用、反射、依赖注入和运行时路由关系可能无法通过静态文本匹配识别。"),
            ("接口只推荐测试文件，不会自动执行测试。"),
        ],
    )


def build_review_evidence_for_knowledge_base(
    *,
    session: Session,
    knowledge_base_id: uuid.UUID,
    request: CodeSkillBuildReviewEvidenceRequest,
) -> CodeSkillReviewEvidenceResponse:
    diff_text = request.diff_text.strip()

    if not diff_text:
        raise ValueError("diff_text cannot be empty")

    pipeline_start_time = perf_counter()

    evidence_trace: list[CodeSkillEvidenceTraceStepPublic] = []

    parse_start_time = perf_counter()

    parsed_changed_files = parse_git_diff(diff_text)

    if not parsed_changed_files:
        raise ValueError("No changed files could be parsed from diff_text")

    changed_files = [
        build_changed_file_public(changed_file) for changed_file in parsed_changed_files
    ]

    total_added_lines = sum(
        changed_file.added_lines or 0 for changed_file in changed_files
    )

    total_deleted_lines = sum(
        changed_file.deleted_lines or 0 for changed_file in changed_files
    )

    evidence_trace.append(
        CodeSkillEvidenceTraceStepPublic(
            step="parse_diff",
            status="success",
            duration_ms=elapsed_milliseconds(parse_start_time),
            summary=(
                f"解析出 {len(changed_files)} 个变更文件，"
                f"新增 {total_added_lines} 行，"
                f"删除 {total_deleted_lines} 行"
            ),
        )
    )

    locate_start_time = perf_counter()

    locate_result = locate_changed_symbols_for_knowledge_base(
        session=session,
        knowledge_base_id=knowledge_base_id,
        request=CodeSkillLocateChangedSymbolsRequest(
            diff_text=diff_text,
            include_file_level_fallback=(request.include_file_level_fallback),
        ),
    )

    evidence_trace.append(
        CodeSkillEvidenceTraceStepPublic(
            step="locate_changed_symbols",
            status="success",
            duration_ms=elapsed_milliseconds(locate_start_time),
            summary=(
                f"定位到 {locate_result.total_symbols or 0} "
                "条变更符号记录，"
                f"{locate_result.total_unresolved_files or 0} "
                "个文件未能定位"
            ),
        )
    )

    changed_symbol_inputs = [
        CodeSkillChangedSymbolInput(
            document_id=symbol.document_id,
            chunk_id=symbol.chunk_id,
            file_path=symbol.file_path,
            symbol_name=symbol.symbol_name,
            symbol_type=symbol.symbol_type,
            line_range=symbol.line_range,
        )
        for symbol in (locate_result.changed_symbols or [])
    ]

    impact_start_time = perf_counter()

    impact_result = find_impacts_for_knowledge_base(
        session=session,
        knowledge_base_id=knowledge_base_id,
        request=CodeSkillFindImpactsRequest(
            changed_symbols=(changed_symbol_inputs),
            max_references_per_symbol=(request.max_references_per_symbol),
            include_definition_chunk=(request.include_definition_chunk),
        ),
    )

    evidence_trace.append(
        CodeSkillEvidenceTraceStepPublic(
            step="find_impacts",
            status="success",
            duration_ms=elapsed_milliseconds(impact_start_time),
            summary=(
                f"找到 {impact_result.total_references or 0} "
                "个引用位置，"
                f"汇总出 {impact_result.total_impacted_files or 0} "
                "个可能受影响文件"
            ),
        )
    )

    impacted_file_inputs = [
        CodeSkillImpactedFileInput(
            file_path=impacted_file.file_path,
            reference_count=(impacted_file.reference_count or 0),
            impacted_symbol_names=(impacted_file.impacted_symbol_names or []),
        )
        for impacted_file in (impact_result.impacted_files_summary or [])
    ]

    test_start_time = perf_counter()

    test_result = recommend_tests_for_knowledge_base(
        session=session,
        knowledge_base_id=knowledge_base_id,
        request=CodeSkillRecommendTestsRequest(
            changed_files=[changed_file.file_path for changed_file in changed_files],
            changed_symbols=(changed_symbol_inputs),
            impacted_files=(impacted_file_inputs),
            max_test_files=(request.max_test_files),
            min_confidence=(request.min_test_confidence),
        ),
    )

    evidence_trace.append(
        CodeSkillEvidenceTraceStepPublic(
            step="recommend_tests",
            status="success",
            duration_ms=elapsed_milliseconds(test_start_time),
            summary=(
                f"扫描到 "
                f"{test_result.total_test_candidates or 0} "
                "个测试候选文件，推荐 "
                f"{test_result.total_recommended_tests or 0} "
                "个测试文件"
            ),
        )
    )

    risk_start_time = perf_counter()

    risk_signals = build_review_risk_signals(
        changed_files=changed_files,
        changed_symbols=(locate_result.changed_symbols or []),
        unresolved_files=(locate_result.unresolved_files or []),
        impacted_files=(impact_result.impacted_files_summary or []),
        recommended_tests=(test_result.recommended_tests or []),
        uncovered_changed_files=(test_result.uncovered_changed_files or []),
        uncovered_symbols=(test_result.uncovered_symbols or []),
    )

    overall_risk_level = calculate_overall_risk_level(risk_signals)

    review_checklist = build_review_checklist(
        changed_files=changed_files,
        changed_symbols=(locate_result.changed_symbols or []),
        impacted_files=(impact_result.impacted_files_summary or []),
        recommended_tests=(test_result.recommended_tests or []),
        risk_signals=risk_signals,
    )

    evidence_trace.append(
        CodeSkillEvidenceTraceStepPublic(
            step="build_risk_and_checklist",
            status="success",
            duration_ms=elapsed_milliseconds(risk_start_time),
            summary=(
                f"生成 {len(risk_signals)} 条风险信号和 "
                f"{len(review_checklist)} 条 Review 检查项，"
                f"总体风险等级为 {overall_risk_level}"
            ),
        )
    )

    change_summary = CodeSkillChangeSummaryPublic(
        total_changed_files=len(changed_files),
        total_added_lines=(total_added_lines),
        total_deleted_lines=(total_deleted_lines),
        total_changed_symbols=(locate_result.total_symbols or 0),
        total_unresolved_files=(locate_result.total_unresolved_files or 0),
        total_references=(impact_result.total_references or 0),
        total_impacted_files=(impact_result.total_impacted_files or 0),
        total_test_candidates=(test_result.total_test_candidates or 0),
        total_recommended_tests=(test_result.total_recommended_tests or 0),
        total_risk_signals=len(risk_signals),
        risk_level=overall_risk_level,
    )

    evidence_trace.append(
        CodeSkillEvidenceTraceStepPublic(
            step="complete_pipeline",
            status="success",
            duration_ms=elapsed_milliseconds(pipeline_start_time),
            summary=("RepoGuard Review Evidence 证据包生成完成"),
        )
    )

    limitations = deduplicate_strings(
        [
            *build_review_limitations(),
            *(test_result.limitations or []),
        ]
    )

    return CodeSkillReviewEvidenceResponse(
        change_summary=change_summary,
        changed_files=changed_files,
        changed_symbols=(locate_result.changed_symbols or []),
        unresolved_files=(locate_result.unresolved_files or []),
        symbol_impacts=(impact_result.symbol_impacts or []),
        impacted_files_summary=(impact_result.impacted_files_summary or []),
        recommended_tests=(test_result.recommended_tests or []),
        test_gap_notes=(test_result.test_gap_notes or []),
        uncovered_changed_files=(test_result.uncovered_changed_files or []),
        uncovered_symbols=(test_result.uncovered_symbols or []),
        risk_signals=risk_signals,
        review_checklist=review_checklist,
        evidence_trace=evidence_trace,
        limitations=limitations,
    )
