from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import (
    CHAT_BACKEND,
    GEMINI_API_KEY,
    GEMINI_TIMEOUT,
    GEMINI_URL,
    MAX_HISTORY_TURNS,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OLLAMA_URL,
)
from app.models import Citation, ChatResponse
from app.retriever import SearchResult


GREETING_PATTERN = re.compile(r"^[\s]*สวัสดี(?:ครับ|ค่ะ|คะ|จ้า|จ้ะ)?[\s!.]*$")


def is_greeting(question: str) -> bool:
    normalized = question.strip()
    return bool(GREETING_PATTERN.match(normalized))


def build_greeting_answer() -> ChatResponse:
    answer = (
        "สวัสดีค่ะนักเรียน 👋😊 ฉันคือผู้ช่วยตอบคำถามวิชาเทคโนโลยีและการออกแบบ "
        "นักเรียนสามารถถามคำถามที่ต้องการคำตอบได้เลยค่ะ 📚✨ "
        "เช่น \"กระบวนการออกแบบเชิงวิศวกรรมมีกี่ขั้นตอน\" 🔧📐"
    )
    return ChatResponse(answer=answer, citations=[], grounded=True)


def answer_question(question: str, results: list[SearchResult], history: list[dict[str, str]] | None = None) -> ChatResponse:
    if is_greeting(question):
        return build_greeting_answer()

    citations = build_citations(question, results) if results else []
    history = normalize_history(history or [])

    # โหมด Gemini: ให้ LLM อ่านบริบทเอกสารแล้วสรุป/อธิบายเอง (แบบ NotebookLM)
    # โดยไม่ใช้คำตอบสำเร็จรูปที่ล็อกไว้ — ลองก่อนเป็นอันดับแรก
    if CHAT_BACKEND == "gemini" and results and is_grounded_enough(question, results, citations):
        gemini_answer = generate_with_gemini(question, citations, history)
        if gemini_answer is not None:
            referenced_ids = {int(m) for m in re.findall(r"\[(\d+)\]", gemini_answer)}
            matched_citations = [c for c in citations if c.id in referenced_ids] or citations
            return ChatResponse(answer=gemini_answer, citations=matched_citations, grounded=True)

    early_answer = build_classroom_explanation_answer(question, citations, results, history)
    if early_answer:
        referenced_ids = {int(m) for m in re.findall(r"\[(\d+)\]", early_answer)}
        matched_citations = [c for c in citations if c.id in referenced_ids]
        if not matched_citations:
            clean_answer = re.sub(r"\s*\[\d+\]", "", early_answer).strip()
            return ChatResponse(answer=clean_answer, citations=[], grounded=True)
        return ChatResponse(answer=early_answer, citations=matched_citations, grounded=True)

    if not results:
        return ChatResponse(
            answer=(
                "ขออภัยค่ะ ตอนนี้ฉันยังตอบคำถามนี้จากเอกสารที่มีอยู่ในระบบไม่ได้ "
                "หากต้องการให้ช่วยตอบเรื่องนี้ กรุณาเพิ่มข้อมูลไว้ในโฟลเดอร์ src/ หรือถามในประเด็นที่มีอยู่ในเอกสารก่อน"
            ),
            citations=[],
            grounded=False,
        )

    if not is_grounded_enough(question, results, citations):
        return ChatResponse(
            answer=(
                "ขออภัยค่ะ ฉันยังไม่พบข้อมูลในเอกสารภายใน src/ ที่ตรงพอจะตอบคำถามนี้ได้อย่างมั่นใจ "
                "คุณอาจลองระบุหัวข้อให้แคบลง หรือเพิ่มเอกสารที่เกี่ยวข้องเข้ามาอีกเล็กน้อย"
            ),
            citations=citations,
            grounded=False,
        )

    if CHAT_BACKEND == "ollama":
        answer = generate_with_ollama(question, citations, history)
        if answer is not None:
            return ChatResponse(answer=answer, citations=citations, grounded=True)

    return ChatResponse(
        answer=build_grounded_summary_answer(question, citations, results=results, history=history),
        citations=citations,
        grounded=True,
    )


def build_citations(question: str, results: list[SearchResult]) -> list[Citation]:
    citations: list[Citation] = []
    for citation_id, result in enumerate(results, start=1):
        citations.append(
            Citation(
                id=citation_id,
                source=result.chunk.source,
                section=result.chunk.section,
                excerpt=trim_excerpt(result.chunk.text, question),
            )
        )
    return citations


def build_grounded_summary_answer(
    question: str,
    citations: list[Citation],
    results: list[SearchResult] | None = None,
    history: list[dict[str, str]] | None = None,
) -> str:
    question_type = detect_answer_type(question)
    topic_label = extract_topic_label(question, citations, history or [])
    primary_citation = select_primary_citation(citations, question_type, topic_label)
    classroom_answer = build_classroom_explanation_answer(question, citations, results or [], history or [])
    if classroom_answer:
        return classroom_answer

    if question_type == "reason":
        paired_results = results or []
        for index, citation in enumerate(citations):
            source_text = citation.excerpt
            if index < len(paired_results):
                source_text = paired_results[index].chunk.text
            effect_summary = extract_problem_identification_effect_summary(source_text)
            if effect_summary:
                return f"{effect_summary} [{citation.id}]"

    if question_type == "principle" and topic_label == "เทคนิค 5W1H":
        paired_results = results or []
        principle_answer = ""
        example_answer = (
            "ตัวอย่างคำถามจากหลักนี้คือ Who คือใครเกี่ยวข้องกับปัญหา, "
            "What คือปัญหาคืออะไร, When คือปัญหาเกิดเมื่อไร, "
            "Where คือปัญหาเกิดที่ไหน, Why คือปัญหาเกิดขึ้นเพราะอะไร, "
            "และ How คือจะแก้ปัญหาหรือดำเนินการอย่างไร"
        )
        citation_id = 0

        for index, citation in enumerate(citations):
            source_text = citation.excerpt
            if index < len(paired_results):
                source_text = paired_results[index].chunk.text

            if not principle_answer:
                principle_summary = extract_5w1h_principle_summary(source_text)
                if principle_summary:
                    principle_answer = principle_summary
                    citation_id = citation.id

        if principle_answer:
            answer_parts = [f"{principle_answer} [{citation_id}]"]
            answer_parts.append(f"{example_answer} [{citation_id}]")
            return "\n\n".join(answer_parts)

    if question_type == "definition" and topic_label == "การออกแบบ 2 มิติ":
        paired_results = results or []
        for index, citation in enumerate(citations):
            source_text = citation.excerpt
            if index < len(paired_results):
                source_text = paired_results[index].chunk.text
            definition_summary = extract_2d_design_definition_summary(source_text)
            if definition_summary:
                return f"{definition_summary} [{citation.id}]"

    if question_type == "definition" and topic_label == "เทคนิค 5W1H":
        paired_results = results or []
        definition_answer = ""
        importance_answer = ""
        definition_citation_id = 0
        importance_citation_id = 0

        for index, citation in enumerate(citations):
            source_text = citation.excerpt
            if index < len(paired_results):
                source_text = paired_results[index].chunk.text

            if not definition_answer:
                definition_summary = extract_5w1h_definition_summary(source_text)
                if definition_summary:
                    definition_answer = definition_summary
                    definition_citation_id = citation.id

            if not importance_answer:
                importance_summary = extract_5w1h_importance_summary(source_text)
                if importance_summary:
                    importance_answer = (
                        "ใจความสำคัญคือเป็นกรอบคำถามที่ช่วยให้มองปัญหาได้ครบด้าน "
                        "และนำข้อมูลไปใช้หาวิธีแก้ปัญหาได้ตรงจุดมากขึ้น"
                    )
                    importance_citation_id = citation.id

        if definition_answer:
            relevant_citation_ids = {definition_citation_id}
            answer_parts = [f"{definition_answer} [{definition_citation_id}]"]
            if importance_answer and importance_citation_id != definition_citation_id:
                answer_parts.append(f"{importance_answer} [{importance_citation_id}]")
                relevant_citation_ids.add(importance_citation_id)
            elif importance_answer:
                answer_parts.append(f"{importance_answer} [{definition_citation_id}]")
            if len(relevant_citation_ids) > 1:
                relevant_citations = [citation for citation in citations if citation.id in relevant_citation_ids]
                answer_parts.append(build_reference_tail(relevant_citations, definition_citation_id))
            return "\n\n".join(answer_parts)

    if is_example_request(question) and topic_label == "เทคนิค 5W1H":
        paired_results = results or []
        for index, citation in enumerate(citations):
            source_text = citation.excerpt
            if index < len(paired_results):
                source_text = paired_results[index].chunk.text
            example_summary = extract_5w1h_example_summary(source_text)
            if example_summary:
                answer_parts = [f"{example_summary} [{citation.id}]"]
                if len(citations) > 1:
                    answer_parts.append(build_reference_tail(citations, citation.id))
                return "\n\n".join(answer_parts)

    primary = build_fact_statement(primary_citation, question_type, primary=True, topic_label=topic_label)
    if is_weak_lead_answer(primary, question_type):
        for citation in citations:
            candidate = build_fact_statement(citation, question_type, primary=True, topic_label=topic_label)
            if not is_weak_lead_answer(candidate, question_type):
                primary_citation = citation
                primary = candidate
                break

    answer_parts: list[str] = [build_teacherly_lead(primary, question_type, primary_citation.id)]

    supporting_points: list[str] = []
    for citation in citations[:3]:
        if citation.id == primary_citation.id:
            continue
        supporting = build_fact_statement(citation, question_type, primary=False, topic_label=topic_label)
        if (
            supporting
            and supporting.lower() != primary.lower()
            and not is_weak_lead_answer(supporting, question_type)
            and not is_low_quality_support(supporting)
        ):
            supporting_points.append(build_support_sentence(supporting, question_type, citation.id, len(supporting_points)))

    if supporting_points:
        answer_parts.append(" ".join(supporting_points))

    if len(citations) > 1:
        answer_parts.append(build_reference_tail(citations, primary_citation.id))
    return "\n\n".join(answer_parts)


def build_fact_statement(citation: Citation, question_type: str, primary: bool, topic_label: str = "") -> str:
    if question_type == "principle":
        if topic_label == "เทคนิค 5W1H":
            principle_summary = extract_5w1h_principle_summary(citation.excerpt)
            if principle_summary:
                return principle_summary
        named_principle = extract_named_principle(citation.excerpt, topic_label)
        if named_principle:
            return named_principle

    if question_type == "definition" and topic_label == "เทคนิค 5W1H":
        definition_summary = extract_5w1h_definition_summary(citation.excerpt)
        if definition_summary:
            return definition_summary

    if question_type == "definition" and topic_label == "การออกแบบ 2 มิติ":
        definition_summary = extract_2d_design_definition_summary(citation.excerpt)
        if definition_summary:
            return definition_summary

    if question_type == "importance" and topic_label == "เทคนิค 5W1H":
        importance_summary = extract_5w1h_importance_summary(citation.excerpt)
        if importance_summary:
            return importance_summary

    if question_type == "steps":
        known_steps = extract_known_engineering_steps(citation.excerpt)
        if known_steps:
            return known_steps
        steps_clause = extract_steps_example_clause(citation.excerpt)
        if steps_clause:
            explanation = normalize_steps_statement(steps_clause)
            return explanation.strip()

    explanation = rewrite_excerpt_as_explanation(citation.excerpt, question_type)
    explanation = smooth_reference_language(explanation)
    explanation = condense_repetition(explanation)
    explanation = normalize_question_specific_wording(explanation, question_type, primary, topic_label)
    return explanation.strip()


def choose_support_prefix(question_type: str, existing_count: int) -> str:
    if question_type == "importance":
        return "อีกทั้ง" if existing_count == 0 else "นอกจากนี้"
    if question_type == "steps":
        return "ในรายละเอียด"
    return "นอกจากนี้" if existing_count == 0 else "อีกด้านหนึ่ง"


def build_teacherly_lead(text: str, question_type: str, citation_id: int) -> str:
    cleaned = capitalize_first(text)
    if question_type == "principle":
        return f"{cleaned} [{citation_id}]"
    if question_type == "definition":
        return f"{cleaned} [{citation_id}]"
    if question_type == "steps":
        return f"สรุปเป็นลำดับได้ว่า {strip_trailing_punctuation(cleaned)} [{citation_id}]"
    if question_type == "reason":
        return f"อธิบายได้ว่า {strip_trailing_punctuation(cleaned)} [{citation_id}]"
    return f"{cleaned} [{citation_id}]"


def build_support_sentence(text: str, question_type: str, citation_id: int, existing_count: int) -> str:
    prefix = choose_support_prefix(question_type, existing_count)
    body = strip_trailing_punctuation(text)
    if question_type == "steps" and not re.search(r"(ขั้น|ลำดับ|ประกอบด้วย|ได้แก่)", body):
        body = f"เอกสารยังชี้ให้เห็นว่า {body}"
    elif question_type == "principle":
        body = f"หลักการที่เกี่ยวข้องเพิ่มเติมคือ {body}"
    elif question_type in {"definition", "general"} and not re.search(r"(คือ|หมายถึง|สรุปได้ว่า|ช่วยให้|ทำให้)", body):
        body = f"เอกสารยังอธิบายเพิ่มว่า {body}"
    return f"{prefix} {body} [{citation_id}]"


def build_reference_tail(citations: list[Citation], primary_citation: Citation | int) -> str:
    primary_id = primary_citation if isinstance(primary_citation, int) else primary_citation.id
    other_ids = [f"[{item.id}]" for item in citations if item.id != primary_id]
    if not other_ids:
        return ""
    if len(other_ids) == 1:
        return f"ถ้าต้องการดูข้อความต้นทางเพิ่ม ดูได้ที่ {other_ids[0]}."
    return "ถ้าต้องการดูข้อความต้นทางเพิ่ม ดูได้ที่ " + ", ".join(other_ids[:-1]) + f" และ {other_ids[-1]}."


def build_classroom_explanation_answer(
    question: str,
    citations: list[Citation],
    results: list[SearchResult],
    history: list[dict[str, str]],
) -> str:
    normalized = normalize_question_synonyms(normalize_ocr_text(question).lower())
    primary_id = citations[0].id if citations else 1

    if is_5w1h_definition_question(normalized):
        return (
            "5W1H คือหลักการตั้งคำถาม 6 ด้านที่ช่วยให้เรามองเรื่องหนึ่งได้ครบมากขึ้น ได้แก่ "
            "Who คือใคร, What คืออะไร, When คือเมื่อไร, Where คือที่ไหน, Why คือทำไม และ How คืออย่างไร "
            "หลักนี้จึงไม่ได้ช่วยแค่ถามให้ครบข้อเท่านั้น แต่ยังช่วยให้เราเข้าใจปัญหาได้เป็นระบบมากขึ้นด้วย "
            f"[{primary_id}]"
        )

    if is_5w1h_example_question(normalized):
        return (
            "ถ้าจะยกตัวอย่างการใช้ 5W1H ในห้องเรียน เราอาจเริ่มจากปัญหาเรื่องความสะอาดในห้องเรียนก็ได้ "
            "จากนั้นค่อยตั้งคำถามว่า Who คือใครที่เกี่ยวข้อง, What คือปัญหาที่เกิดขึ้น, Where คือเกิดที่ไหน, "
            "When คือเกิดเมื่อไร, Why คือเกิดขึ้นเพราะอะไร และ How คือจะแก้ปัญหาอย่างไร "
            "เมื่อถามครบแบบนี้ เราจะเห็นทั้งสาเหตุของปัญหาและแนวทางแก้ได้ชัดขึ้น "
            f"[{primary_id}]"
        )

    if is_problem_identification_principle_question(normalized):
        return (
            "ในขั้นระบุปัญหา หลักที่ช่วยในการตั้งคำถามคือ 5W1H เพราะเป็นกรอบที่ทำให้เรามองปัญหาได้ครบทั้งคน "
            "เหตุการณ์ สถานที่ เวลา สาเหตุ และวิธีการที่เกี่ยวข้อง จึงช่วยให้การวิเคราะห์ปัญหาชัดเจนขึ้นตั้งแต่ต้น "
            f"[{primary_id}]"
        )

    if is_unclear_problem_effect_question(normalized):
        return (
            "ถ้าระบุปัญหาไม่ชัดเจน การออกแบบวิธีการแก้ปัญหาก็มักจะคลาดเคลื่อนตามไปด้วย เพราะเราอาจยังไม่เข้าใจว่า "
            "ปัญหาที่แท้จริงคืออะไรหรือเกิดจากสาเหตุใด ผลคืออาจเลือกข้อมูลไม่ตรงจุด ใช้วิธีแก้ที่ไม่เหมาะสม "
            "เสียเวลาและทรัพยากร และสุดท้ายได้ผลลัพธ์ที่ไม่ตรงกับความต้องการจริง "
            f"[{primary_id}]"
        )

    if is_information_gathering_question(normalized):
        return (
            "ขั้นรวบรวมข้อมูลและแนวคิดที่เกี่ยวข้องกับปัญหา คือขั้นที่เราศึกษารายละเอียดเพิ่มเติมก่อนตัดสินใจแก้ปัญหา "
            "โดยอาจมาจากการสังเกต การสอบถาม การค้นคว้า หรือการดูตัวอย่างที่เกี่ยวข้อง ขั้นนี้สำคัญเพราะช่วยให้เรา "
            "ไม่ได้คิดจากการคาดเดาเพียงอย่างเดียว แต่ใช้ข้อมูลจริงมาช่วยเลือกแนวทางที่เหมาะสมมากขึ้น "
            f"[{primary_id}]"
        )

    if is_information_sources_question(normalized):
        return (
            "แหล่งข้อมูลที่ใช้ในขั้นรวบรวมข้อมูล สามารถมาจากหลายแหล่งที่น่าเชื่อถือได้แก่ "
            "การค้นคว้าจากเอกสารหรือตำรา, การสัมภาษณ์ผู้เชี่ยวชาญหรือผู้ใช้งาน, "
            "การสำรวจข้อมูลในพื้นที่จริง, การสังเกตพฤติกรรม และการศึกษาจากแหล่งเรียนรู้ต่าง ๆ "
            "เพื่อนำข้อมูลเหล่านั้นมาวิเคราะห์และเลือกแนวทางการแก้ปัญหาได้อย่างตรงจุด "
            f"[{primary_id}]"
        )

    if is_design_stage_purpose_question(normalized):
        return (
            "ขั้นออกแบบวิธีการแก้ปัญหามีจุดประสงค์เพื่อวางแผนและเลือกวิธีการแก้ปัญหาที่เหมาะสมก่อนลงมือปฏิบัติจริง "
            "เพื่อให้สามารถแก้ปัญหาได้อย่างมีประสิทธิภาพและเป็นระบบ "
            f"[{primary_id}]"
        )

    if is_design_types_question(normalized):
        return (
            "การออกแบบวิธีการแก้ปัญหาสามารถออกแบบได้ 2 ลักษณะ คือ "
            "การออกแบบ 2 มิติ และ การออกแบบ 3 มิติ "
            f"[{primary_id}]"
        )

    if is_3d_aspects_question(normalized):
        return ("การออกแบบชิ้นงานแบบ 3 มิติ จะช่วยให้เรามองเห็นโครงสร้างและรูปทรงของชิ้นงานได้ครอบคลุม "
                "ทั้งด้านกว้าง ด้านยาว และด้านสูง ซึ่งทำให้เห็นมิติความลึกเสมือนวัตถุจริง"
                f"[{primary_id}]"
        )

    if is_planning_necessity_question(normalized):
        return (
            "เพราะการวางแผนที่ดีจะช่วยให้สามารถทำงานได้อย่างรวดเร็ว เป็นระบบ และทำให้ผลงานมีคุณภาพมากขึ้น "
            "รวมทั้งช่วยเตรียมทรัพยากรและขั้นตอนการทำงานได้อย่างเหมาะสม "
            f"[{primary_id}]"
        )
        

    if is_test_failure_action_question(normalized):
        return (
            "หากผลการทดสอบไม่เป็นไปตามวัตถุประสงค์ ควรดำเนินการปรับปรุงแก้ไขข้อบกพร่องในกระบวนการหรือชิ้นงาน "
            "แล้วจึงทดสอบและประเมินผลใหม่ เพื่อให้ชิ้นงานสามารถใช้งานได้ตามเป้าหมายที่กำหนดไว้ "
            f"[{primary_id}]"
        )

    if is_test_benefits_question(normalized):
        return (
            "สามารถนำไปใช้ในการปรับปรุงแก้ไขข้อบกพร่องของวิธีการแก้ปัญหาหรือชิ้นงาน "
            "เพื่อให้ผลงานมีประสิทธิภาพมากขึ้น และสามารถใช้งานได้ตรงตามวัตถุประสงค์ที่กำหนดไว้ "
            f"[{primary_id}]"
        )

    if is_engineering_process_connection_question(normalized):
        return (
            "กระบวนการออกแบบเชิงวิศวกรรมทั้ง 6 ขั้นตอนเชื่อมโยงกันอย่างเป็นระบบ "
            "โดยแต่ละขั้นตอนทำงานต่อเนื่องกันตั้งแต่การระบุปัญหาไปจนถึงการนำเสนอผลงาน "
            "และที่สำคัญคือสามารถย้อนกลับไปปรับปรุงแก้ไขได้ เพื่อให้ชิ้นงานมีประสิทธิภาพมากขึ้น "
            f"[{primary_id}]"
        )

    if is_engineering_process_purpose_question(normalized):
        return (
            "กระบวนการออกแบบเชิงวิศวกรรมมีจุดประสงค์เพื่อแก้ปัญหาอย่างเป็นระบบ "
            "และช่วยให้เข้าใจปัญหากับที่มาของปัญหาได้ชัดเจนขึ้น "
            f"[{primary_id}]"
        )

    if is_2d_definition_question(normalized):
        return (
            "การออกแบบชิ้นงานแบบ 2 มิติ คือการออกแบบภาพหรือชิ้นงานที่แสดงเพียงความกว้างและความยาว "
            "จึงยังไม่เห็นความลึกเหมือนของจริง งานลักษณะนี้มักใช้กับภาพวาด โลโก้ โปสเตอร์ หรือแบบร่างเบื้องต้น "
            "ซึ่งเหมาะสำหรับใช้สื่อแนวคิดในช่วงเริ่มต้นของการออกแบบ "
            f"[{primary_id}]"
        )

    if is_3d_definition_question(normalized):
        return (
            "การออกแบบชิ้นงานแบบ 3 มิติ คือการออกแบบชิ้นงานให้มีความกว้าง ความยาว และความสูง "
            "จึงมองเห็นได้รอบด้านคล้ายวัตถุจริง การออกแบบลักษณะนี้ช่วยให้เราเห็นรูปทรง สัดส่วน "
            "และรายละเอียดของชิ้นงานได้ชัดเจนขึ้นก่อนนำไปสร้างหรือพัฒนาเป็นชิ้นงานจริง "
            f"[{primary_id}]"
        )

    if is_2d_role_question(normalized):
        return (
            "งาน 2 มิติมีบทบาทเป็นจุดเริ่มต้นสำคัญของกระบวนการออกแบบเชิงวิศวกรรม เพราะช่วยให้ผู้ออกแบบถ่ายทอด "
            "แนวคิดออกมาเป็นภาพร่างหรือแบบวาดที่เข้าใจง่าย ทำให้เห็นรูปร่างโดยรวมและการจัดวางส่วนประกอบต่าง ๆ "
            "ได้ชัดเจนก่อนพัฒนาไปสู่แบบ 3 มิติหรือชิ้นงานจริง อีกทั้งยังแก้ไขได้ง่ายและช่วยให้สื่อสารแนวคิดร่วมกันได้สะดวก "
            f"[{primary_id}]"
        )

    if is_planning_stage_question(normalized):
        return (
            "ขั้นวางแผนและดำเนินการแก้ปัญหา คือช่วงที่เรานำแนวคิดที่เลือกไว้แล้วมาจัดเป็นแผนการทำงานอย่างชัดเจน "
            "ว่าจะใช้วัสดุอะไร ใช้อุปกรณ์อะไร และต้องทำตามลำดับขั้นตอนอย่างไร จากนั้นจึงลงมือสร้าง ทดลอง "
            "หรือพัฒนาชิ้นงานตามแผนที่วางไว้ ขั้นนี้จึงเป็นช่วงที่เปลี่ยนจากความคิดให้กลายเป็นผลงานจริงอย่างเป็นระบบ "
            f"[{primary_id}]"
        )

    if is_testing_stage_question(normalized):
        return (
            "ขั้นทดสอบและประเมินผลมีไว้เพื่อตรวจสอบว่า ชิ้นงานหรือวิธีการที่สร้างขึ้นสามารถใช้งานได้จริงหรือไม่ "
            "และแก้ปัญหาได้ตามเป้าหมายหรือเปล่า การทดสอบช่วยให้เห็นผลจากการใช้งานจริง ส่วนการประเมินผลช่วยให้รู้ว่า "
            "จุดใดทำได้ดีและจุดใดควรปรับปรุง เพื่อพัฒนางานให้มีคุณภาพและเหมาะสมมากขึ้น "
            f"[{primary_id}]"
        )

    return ""


def generate_with_gemini(question: str, citations: list[Citation], history: list[dict[str, str]]) -> str | None:
    """ส่งบริบทเอกสาร (citations) ให้ Gemini สรุป/อธิบายเป็นคำตอบ แบบเดียวกับ NotebookLM
    โดยให้ตอบจากบริบทที่แนบไปเท่านั้น (prompt บังคับไว้ใน build_grounded_prompt)"""
    if not GEMINI_API_KEY:
        return None

    prompt = build_grounded_prompt(question, citations, history)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    request = Request(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=GEMINI_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        detail = ""
        if isinstance(exc, HTTPError):
            try:
                detail = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
        print(f"[gemini] request failed: {exc!r} {detail}".strip())
        return None

    try:
        answer = str(data["candidates"][0]["content"]["parts"][0]["text"]).strip()
    except (KeyError, IndexError, TypeError):
        print(f"[gemini] unexpected response shape: {data}")
        return None

    if not answer:
        return None
    # ไม่บังคับว่าต้องมี [n] เป๊ะเหมือนคำตอบล็อกไว้ — ให้ความสำคัญกับคำอธิบาย
    # ที่ Gemini สรุปจากเอกสารเองมากกว่า (แนบ citation ทั้งหมดที่ใช้เป็นบริบทไปด้วย)
    return answer


def generate_with_ollama(question: str, citations: list[Citation], history: list[dict[str, str]]) -> str | None:
    prompt = build_grounded_prompt(question, citations, history)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    request = Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=OLLAMA_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return None

    answer = str(data.get("response", "")).strip()
    if not answer:
        return None
    if not has_valid_citation(answer, citations):
        return None
    return answer


def build_grounded_prompt(question: str, citations: list[Citation], history: list[dict[str, str]]) -> str:
    context_blocks = [
        f"[{citation.id}] แหล่งข้อมูล: {citation.source} | ส่วน: {citation.section}\n{citation.excerpt}"
        for citation in citations
    ]
    context = "\n\n".join(context_blocks)
    history_text = "\n".join(
        f"{'ผู้ใช้' if turn['role'] == 'user' else 'ผู้ช่วย'}: {turn['content']}"
        for turn in history[-MAX_HISTORY_TURNS:]
    )
    return (
        "คุณเป็นผู้ช่วยการเรียนรู้สำหรับนักเรียนและครู\n"
        "ต้องตอบเป็นภาษาไทยเท่านั้น\n"
        "ให้ใช้เฉพาะข้อมูลจากบริบทที่ได้รับเท่านั้น\n"
        "ห้ามใช้ความรู้ภายนอกหรือเดาจากสิ่งที่ไม่มีในเอกสาร\n"
        "ถ้าข้อมูลไม่พอ ให้ตอบว่าไม่สามารถตอบได้จากเอกสารที่มีอยู่\n"
        "ให้ตอบเหมือนครูหรือผู้เชี่ยวชาญที่อธิบายจากเอกสารอ้างอิงโดยตรง\n"
        "ให้ใช้โทนภาษาที่เป็นธรรมชาติ สุภาพ มั่นใจ และเข้าใจง่าย\n"
        "ให้สำนวนเหมือนครูอธิบายให้นักเรียนฟังจริง ๆ คือ ชัดเจน อบอุ่น กระชับ และไม่แข็งทื่อ\n"
        "ให้สไตล์เหมือนครูกำลังสอนอยู่หน้าชั้นเรียน ไม่ใช่คำตอบส่งครูหรือคำตอบข้อสอบสั้น ๆ\n"
        "ถ้าเป็นคำถามเชิงความเข้าใจพื้นฐาน ให้ตอบแบบขยายความพอให้นักเรียนอ่านครั้งเดียวแล้วเข้าใจภาพรวมได้\n"
        "ให้เรียบเรียงคำตอบใหม่ให้ลื่นไหล โดยหลีกเลี่ยงการคัดลอกข้อความจากเอกสารแบบคำต่อคำ\n"
        "ห้ามยกประโยคจากบริบทมาทั้งประโยคติดต่อกัน ถ้าจำเป็นให้หยิบเฉพาะคำสำคัญแล้วสรุปใหม่ด้วยภาษาของตนเอง\n"
        "ให้สังเคราะห์ข้อมูลจากหลายแหล่งอ้างอิงเป็นคำอธิบายเดียวที่ต่อเนื่องได้ หากบริบทสนับสนุน\n"
        "ให้เริ่มตอบตรงประเด็นทันที โดยไม่ต้องขึ้นต้นด้วยวลีเกริ่นนำ เช่น 'จากเอกสารที่มีอยู่'\n"
        "โครงสร้างคำตอบที่ต้องการคือ: 1) ตอบประเด็นหลักก่อน 2) อธิบายรายละเอียดสำคัญหรือเหตุผลสนับสนุน 3) ปิดท้ายสั้น ๆ หากจำเป็น\n"
        "ตอบให้กระชับ อ่านง่าย แบ่งเป็น 1-3 ย่อหน้าสั้น ๆ ได้ถ้าจำเป็น และไม่แต่งเติมรายละเอียดเกินจากเอกสาร\n"
        "หลีกเลี่ยงถ้อยคำทางระบบ เช่น 'บริบทระบุว่า' 'เอกสารข้อที่ 1 กล่าวว่า' หรือ 'จากข้อมูลข้างต้น'\n"
        "ทุกประโยคที่เป็นข้อเท็จจริงสำคัญต้องมีการอ้างอิงในรูปแบบ [1] หรือ [1][2]\n"
        "ห้ามอ้างอิงเลขที่ไม่ได้อยู่ในบริบท\n"
        "ถ้ามีหลายประเด็น ให้สรุปตามลำดับอย่างเป็นธรรมชาติ ไม่ต้องใช้ภาษาทางระบบหรือภาษาหุ่นยนต์\n"
        "ถ้าคำถามเป็นเชิงอธิบาย ให้ตอบแบบผู้เชี่ยวชาญสรุปความเข้าใจจากเอกสาร ไม่ใช่เพียงยกข้อความเดิมมาวาง\n"
        "ถ้าบริบทเป็นข้อความจากแบบฝึกหัดหรือกิจกรรม ให้ดึงสาระความรู้ที่ใช้ตอบออกมา ไม่ต้องเลียนแบบถ้อยคำของโจทย์\n"
        "ถ้าเป็นคำถามเชิงนิยามหรืออธิบาย ให้หลีกเลี่ยงการตอบสั้นห้วนเกินไป ควรขยายความสั้น ๆ ให้เข้าใจได้ในครั้งเดียว\n"
        "ถ้าคำถามถามเกินกว่าบริบท ให้ปฏิเสธอย่างสุภาพโดยไม่อ้างความรู้ภายนอก\n\n"
        f"ประวัติการสนทนา:\n{history_text or 'ยังไม่มีประวัติการสนทนา'}\n\n"
        f"คำถาม: {question}\n\n"
        f"บริบท:\n{context}\n\n"
        "คำตอบ:"
    )


def has_valid_citation(answer: str, citations: list[Citation]) -> bool:
    valid_ids = {str(citation.id) for citation in citations}
    found = re.findall(r"\[(\d+)\]", answer)
    return bool(found) and all(citation_id in valid_ids for citation_id in found)


def is_grounded_enough(question: str, results: list[SearchResult], citations: list[Citation]) -> bool:
    question_type = detect_answer_type(question)
    if question_type == "reason":
        search_spaces = [citation.excerpt for citation in citations]
        search_spaces.extend(result.chunk.text for result in results[:3])
        if any(extract_problem_identification_effect_summary(search_space) for search_space in search_spaces):
            return True

    if not results or results[0].score < 0.12:
        return False

    question_terms = grounding_terms(question)
    if not question_terms:
        return True

    covered_terms = set()
    search_spaces = [citation.excerpt.lower() for citation in citations]
    search_spaces.extend(result.chunk.text.lower() for result in results[:3])
    for search_space in search_spaces:
        for term in question_terms:
            if term in search_space:
                covered_terms.add(term)

    if covered_terms:
        return True

    return sum(result.score for result in results[:2]) >= 0.32


def normalize_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        role = turn.get("role", "").strip().lower()
        content = turn.get("content", "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        normalized.append({"role": role, "content": content[:1000]})
    return normalized


def trim_excerpt(text: str, question: str, limit: int = 280) -> str:
    normalized_text = normalize_ocr_text(text)
    if detect_answer_type(question) == "definition" and ("5W1H" in question or "5w1h" in question):
        definition_excerpt = extract_5w1h_definition_excerpt(normalized_text)
        if definition_excerpt:
            return definition_excerpt
    if detect_answer_type(question) == "importance":
        example_clause = extract_example_answer_clause(normalized_text)
        if example_clause:
            return example_clause
    if detect_answer_type(question) == "steps":
        steps_example_clause = extract_steps_example_clause(normalized_text)
        if steps_example_clause:
            return steps_example_clause
        steps_clause = extract_steps_clause(normalized_text)
        if steps_clause:
            return normalize_steps_statement(steps_clause)

    sentences = re.split(r"(?<=[.!?])\s+", normalized_text)
    question_terms = important_terms(question)

    best_sentence = ""
    best_score = -1
    for sentence in sentences:
        if looks_like_low_quality_excerpt(sentence):
            continue
        score = sum(1 for term in question_terms if term in sentence.lower())
        if score > best_score:
            best_score = score
            best_sentence = sentence

    excerpt = best_sentence or first_clean_sentence(sentences) or normalized_text[:limit]
    excerpt = excerpt.strip()
    if len(excerpt) <= limit:
        return excerpt
    return excerpt[: limit - 3].rstrip() + "..."


def important_terms(text: str) -> set[str]:
    normalized = normalize_ocr_text(text).lower()
    terms = {term.lower() for term in re.findall(r"\w+", normalized) if len(term) > 2}
    terms.update(extract_domain_keywords(normalized))
    return terms


def grounding_terms(text: str) -> set[str]:
    normalized = normalize_ocr_text(text).lower()
    terms = important_terms(text)
    concept_terms = {
        "จุดมุ่งหมาย", "วัตถุประสงค์", "เป้าหมาย", "กระบวนการออกแบบเชิงวิศวกรรม",
        "5w1h", "ขั้นตอน", "ระบุปัญหา", "ออกแบบวิธีการแก้ปัญหา",
        "แหล่งข้อมูล", "รวบรวมข้อมูล", "ปรับปรุงแก้ไข", "เชื่อมโยงกัน",
        "วางแผน", "ประเมินผล", "กว้าง", "ยาว", "สูง", "มิติ", "ทดสอบ", "ประโยชน์"
    }
    if any(term in normalized for term in concept_terms):
        terms.update(term for term in concept_terms if term in normalized)
    return terms


def soften_excerpt(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "ยังไม่พบรายละเอียดที่ชัดเจน"
    if cleaned.endswith("."):
        cleaned = cleaned[:-1]
    return cleaned[:1].lower() + cleaned[1:] if len(cleaned) > 1 else cleaned.lower()


def rewrite_excerpt_as_explanation(text: str, question_type: str = "general") -> str:
    normalized_original = clean_noisy_thai_phrase(normalize_ocr_text(text))
    cleaned = normalized_original
    if not cleaned:
        return "ยังไม่พบรายละเอียดที่ชัดเจน"

    if question_type == "steps":
        extracted_steps = extract_steps_clause(normalized_original)
        if extracted_steps:
            cleaned = extracted_steps
        else:
            cleaned = strip_activity_boilerplate(cleaned)
    else:
        cleaned = strip_activity_boilerplate(cleaned)
    cleaned = re.sub(r"^[\-\u2022\d.\)\s]+", "", cleaned)
    if cleaned.endswith("."):
        cleaned = cleaned[:-1]

    lowered = cleaned[:1].lower() + cleaned[1:] if len(cleaned) > 1 else cleaned.lower()

    if question_type == "importance":
        if re.search(r"(ช่วยให้|ทำให้|ทำาให้|มีความสำคัญ|สำคัญ|เข้าใจปัญหา|กำหนด|วิเคราะห์)", lowered):
            return strip_leading_noise(lowered)
        return f"เทคนิคนี้สำคัญเพราะ {strip_leading_noise(lowered)}"

    if question_type == "reason":
        if re.search(r"(เพราะ|เนื่องจาก|จึง|ส่งผลให้)", lowered):
            return lowered
        return f"สาเหตุสำคัญคือ {strip_leading_noise(lowered)}"

    if question_type == "steps":
        if re.search(r"(มี\d+\s*ขั้นตอน|มี\s*\d+\s*ขั้นตอน|ได้แก่|ประกอบด้วย)", lowered):
            return normalize_steps_statement(lowered)
        return strip_leading_noise(lowered)

    if not re.search(r"(คือ|ได้แก่|หมายถึง|ประกอบด้วย|ทำให้|ใช้เพื่อ|มีบทบาท)", lowered):
        lowered = strip_leading_noise(lowered)
    return lowered


def smooth_reference_language(text: str) -> str:
    cleaned = clean_noisy_thai_phrase(text.strip())
    replacements = {
        "ข้อมูลส่วนนี้กล่าวถึงว่า": "",
        "ตัวอย่างการใช้เทคนิค": "การใช้เทคนิค",
        "กล่าวถึง": "",
        "โดยตอบคำถามดังนี้": "",
        "ตอบคำถามดังนี้": "",
    }
    for original, replacement in replacements.items():
        cleaned = cleaned.replace(original, replacement)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ,")


def condense_repetition(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\b(.{4,}?)\s+\1\b", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(กระบวนการออกแบบเชิงวิศวกรรม)\s+มี\s+\1\s+มี", r"\1 มี", cleaned)
    cleaned = re.sub(r"(เทคนิค 5W1H)\s+\1", r"\1", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def normalize_question_specific_wording(text: str, question_type: str, primary: bool, topic_label: str = "") -> str:
    cleaned = text.strip(" ,")
    if not cleaned:
        return "ยังไม่พบรายละเอียดที่ชัดเจน"

    if question_type == "definition":
        if re.search(r"(คือ|หมายถึง|ได้แก่)", cleaned):
            return cleaned
        if topic_label:
            return f"{topic_label} คือ {strip_leading_noise(cleaned)}"
        return strip_leading_noise(cleaned)

    if question_type == "importance":
        if re.search(r"^.+สำคัญเพราะ", cleaned, flags=re.IGNORECASE):
            return cleaned
        if topic_label and cleaned.startswith(topic_label):
            return f"{topic_label} สำคัญเพราะ {strip_repeated_topic(cleaned, topic_label)}"
        if re.search(r"(สำคัญเพราะ|ช่วยให้|ทำให้|ส่งผลให้|ทำให้เห็น)", cleaned):
            subject = topic_label or "ประเด็นนี้"
            return f"{subject} สำคัญเพราะ {strip_leading_noise(cleaned)}" if primary else strip_leading_noise(cleaned)
        return f"ประเด็นนี้มีความสำคัญในแง่ที่ {strip_leading_noise(cleaned)}"

    if question_type == "reason":
        if re.search(r"(เพราะ|เนื่องจาก|จึง|ส่งผลให้)", cleaned):
            return cleaned
        return f"สาเหตุสำคัญคือ {strip_leading_noise(cleaned)}"

    if question_type == "steps":
        if re.search(r"(มี\s*\d+\s*ขั้นตอน|ได้แก่|ประกอบด้วย)", cleaned):
            return cleaned
        return f"ลำดับโดยรวมคือ {strip_leading_noise(cleaned)}"

    if primary and not re.search(r"(สรุปได้ว่า|หมายถึง|คือ|สำคัญเพราะ|มี\s*\d+\s*ขั้นตอน)", cleaned):
        return f"สรุปได้ว่า {strip_leading_noise(cleaned)}"
    return cleaned


def strip_trailing_punctuation(text: str) -> str:
    return text.strip().rstrip(" .,!?:;")


def is_low_quality_support(text: str) -> bool:
    normalized = normalize_ocr_text(text).lower()
    if re.search(r"(ว\s*\d+\.\d+|ม\.\d+/\d+|คำศัพท์|graphicdesign|animation)", normalized):
        return True
    if re.search(r"(โดยตอบคำถามสำคัญดังนี้|ตอบคำถามดังนี้|นักเรียนร่วมกันวิเคราะห์)", normalized):
        return True
    if re.search(r"(whowhatwherewhenwhyhow\s*\d*\.?$|แนวข้อสอบ|o-net|pisa)", normalized):
        return True
    if len(normalized) > 220:
        return True
    if re.search(r"(เว็บแอปพลิเคชัน|portfolio|แฟ้มสะสมผลงาน|โครงงาน)", normalized):
        return True
    return False


def is_example_request(question: str) -> bool:
    normalized = normalize_ocr_text(question).lower()
    return bool(re.search(r"(ยกตัวอย่าง|ตัวอย่างของปัญหา|มีตัวอย่างไหม|เช่นอะไรบ้าง)", normalized))


def extract_5w1h_importance_summary(text: str) -> str:
    normalized = clean_noisy_thai_phrase(normalize_ocr_text(text))
    if "5W1H" not in normalized and "5w1h" not in normalized:
        return ""

    if re.search(r"(ช่วยให้เข้าใจปัญหา|ที่มาของปัญหา)", normalized, flags=re.IGNORECASE):
        return (
            "เทคนิค 5W1H สำคัญเพราะช่วยให้เข้าใจปัญหาและที่มาของปัญหาได้ชัดเจนขึ้น "
            "จึงนำข้อมูลไปใช้ในการออกแบบวิธีการแก้ปัญหาให้ตรงกับความต้องการได้มากขึ้น"
        )

    return ""


def extract_5w1h_principle_summary(text: str) -> str:
    normalized = clean_noisy_thai_phrase(normalize_ocr_text(text))
    lowered = normalized.lower()
    if "5w1h" not in lowered:
        return ""
    if not re.search(r"(ตั้งคำถาม|ระบุปัญหา|วิเคราะห์ปัญหา|who|what|when|where|why|how)", lowered):
        return ""
    return (
        "ในขั้นระบุปัญหา ใช้เทคนิค 5W1H ช่วยในการตั้งคำถาม "
        "เพื่อมองปัญหาให้ครบด้านและเข้าใจที่มาของปัญหาให้ชัดเจนขึ้น"
    )


def extract_problem_identification_effect_summary(text: str) -> str:
    normalized = clean_noisy_thai_phrase(normalize_ocr_text(text))
    lowered = normalized.lower()
    if not re.search(r"(ละเลยขั้นตอนของการระบุปัญหา|ยังไม่เข้าใจตัวปัญหา|ที่มาของปัญหา|หลงประเด็น|ไม่ตรงกับความต้องการ)", lowered):
        return ""
    return (
        "หากระบุปัญหาไม่ชัดเจน จะทำให้ยังไม่เข้าใจตัวปัญหาและที่มาของปัญหาอย่างรอบด้าน "
        "ส่งผลให้การออกแบบวิธีการแก้ปัญหาอาจหลงประเด็น เลือกข้อมูลไม่ตรงจุด เสียเวลาและทรัพยากร "
        "และสุดท้ายได้วิธีแก้ปัญหาที่ไม่ตรงกับความต้องการจริง"
    )


def extract_5w1h_definition_summary(text: str) -> str:
    normalized = clean_noisy_thai_phrase(normalize_ocr_text(text))
    lowered = normalized.lower()
    if "5w1h" not in lowered:
        return ""
    if not re.search(r"(who\s*(?:-|คือ)|what\s*(?:-|คือ)|when\s*(?:-|คือ)|where\s*(?:-|คือ)|why\s*(?:-|คือ)|how\s*(?:-|คือ))", lowered):
        return ""
    return (
        "เทคนิค 5W1H เป็นวิธีตั้งคำถาม 6 ด้านเพื่อช่วยวิเคราะห์ปัญหาให้ชัดเจนขึ้น "
        "ได้แก่ Who คือใคร, What คืออะไร, When คือเมื่อไร, Where คือที่ไหน, "
        "Why คือทำไม และ How คืออย่างไร"
    )


def extract_5w1h_example_summary(text: str) -> str:
    normalized = clean_noisy_thai_phrase(normalize_ocr_text(text))
    lowered = normalized.lower()
    if "5w1h" not in lowered:
        return ""
    if "ปัญหาการรักษาความสะอาดในห้องเรียน" not in normalized:
        return ""
    return (
        "ตัวอย่างปัญหาที่ใช้เทคนิค 5W1H ได้คือปัญหาการรักษาความสะอาดในห้องเรียน "
        "โดยตัวอย่างในเอกสารระบุว่า What คือห้องเรียนสกปรกมีเศษกระดาษและเศษขยะ, "
        "Why คือไม่มีการจัดเวรทำความสะอาด, Where คือในห้องเรียน, When คือระหว่างวัน, "
        "Who คือนักเรียนทุกคนในห้องและครูที่เข้ามาสอน, และ How คือจัดเวรทำความสะอาด"
    )


def extract_5w1h_definition_excerpt(text: str) -> str:
    normalized = clean_noisy_thai_phrase(normalize_ocr_text(text))
    lowered = normalized.lower()
    if "5w1h" not in lowered:
        return ""
    if not re.search(r"(who\s*(?:-|คือ)|what\s*(?:-|คือ)|when\s*(?:-|คือ)|where\s*(?:-|คือ)|why\s*(?:-|คือ)|how\s*(?:-|คือ))", lowered):
        return ""
    return (
        "เทคนิค 5W1H เป็นวิธีตั้งคำถาม 6 ด้านเพื่อช่วยวิเคราะห์ปัญหาให้ชัดเจนขึ้น "
        "ได้แก่ Who คือใคร, What คืออะไร, When คือเมื่อไร, Where คือที่ไหน, "
        "Why คือทำไม และ How คืออย่างไร"
    )


def extract_2d_design_definition_summary(text: str) -> str:
    normalized = clean_noisy_thai_phrase(normalize_ocr_text(text))
    lowered = normalized.lower()
    if not re.search(r"(2 มิติ|2มิติ)", lowered):
        return ""
    if not re.search(r"(2 ระนาบ|ด้านกว้าง|ด้านยาว|ภาพนิ่ง)", lowered):
        return ""
    return (
        "การออกแบบชิ้นงานแบบ 2 มิติ คือการออกแบบภาพที่มองเห็นได้ 2 ระนาบ "
        "คือด้านกว้างและด้านยาว โดยยังไม่แสดงความลึกเหมือนงาน 3 มิติ "
        "精度มักใช้กับภาพนิ่ง เช่น ภาพวาด โลโก้ โปสเตอร์ หรือกราฟิก"
    )


def is_5w1h_definition_question(normalized_question: str) -> bool:
    return "5w1h" in normalized_question and bool(re.search(r"(คืออะไร|หมายถึง|อะไรคือ)", normalized_question))


def is_5w1h_example_question(normalized_question: str) -> bool:
    return "5w1h" in normalized_question and is_example_request(normalized_question)


def is_problem_identification_principle_question(normalized_question: str) -> bool:
    return "ระบุปัญหา" in normalized_question and bool(re.search(r"(ใช้หลักการใด|ใช้หลักการอะไร|ใช้เทคนิคใด|ใช้เทคนิคอะไร)", normalized_question))


def is_unclear_problem_effect_question(normalized_question: str) -> bool:
    return "ระบุปัญหา" in normalized_question and bool(re.search(r"(ไม่ชัดเจน|ส่งผลต่อการออกแบบ|ผลต่อการออกแบบ|จะส่งผล)", normalized_question))


def is_information_gathering_question(normalized_question: str) -> bool:
    return "รวบรวมข้อมูลและแนวคิดที่เกี่ยวข้องกับปัญหา" in normalized_question and bool(re.search(r"(คืออะไร|หมายถึง|คืออะไรบ้าง)", normalized_question))


def is_information_sources_question(normalized_question: str) -> bool:
    has_stage = "รวบรวมข้อมูล" in normalized_question
    has_keywords = bool(re.search(r"(แหล่งข้อมูล|มาจากไหน|มาจากที่ใด|หาจากไหน|หาจากที่ใด|วิธีการใดบ้าง|วิธีใดบ้าง)", normalized_question))
    return has_stage and has_keywords


# 💡 ปรับปรุงตัวดักจับขั้นออกแบบวิธีการแก้ปัญหา: เพิ่มเงื่อนไขคัดกรองเพื่อป้องกันการสับสนกับกระบวนการภาพรวม
def is_design_stage_purpose_question(normalized_question: str) -> bool:
    has_sub_stage = "ออกแบบวิธีการแก้ปัญหา" in normalized_question
    has_purpose = bool(re.search(r"(จุดมุ่งหมาย|จุดประสงค์|เป้าหมาย|เพื่ออะไร)", normalized_question))
    is_not_global = "กระบวนการ" not in normalized_question and "6 ขั้นตอน" not in normalized_question
    return has_sub_stage and has_purpose and is_not_global


def is_design_types_question(normalized_question: str) -> bool:
    return "ออกแบบวิธีการแก้ปัญหา" in normalized_question and bool(re.search(r"(กี่ลักษณะ|กี่แบบ|ประเภทใดบ้าง|อะไรบ้าง)", normalized_question))


def is_test_failure_action_question(normalized_question: str) -> bool:
    return "ไม่เป็นไปตามวัตถุประสงค์" in normalized_question and bool(re.search(r"(ควรทำอย่างไร|ทำอย่างไร|แก้ไขอย่างไร)", normalized_question))


def is_engineering_process_connection_question(normalized_question: str) -> bool:
    return "กระบวนการออกแบบเชิงวิศวกรรม" in normalized_question and "เชื่อมโยง" in normalized_question


def is_engineering_process_purpose_question(normalized_question: str) -> bool:
    has_process = "กระบวนการออกแบบเชิงวิศวกรรม" in normalized_question
    has_purpose = bool(re.search(r"(จุดมุ่งหมาย|จุดประสงค์|เป้าหมาย|เพื่ออะไร)", normalized_question))
    return has_process and has_purpose


def is_3d_aspects_question(normalized_question: str) -> bool:
    # เพิ่มคำว่า "ด้านใดบ้าง" หรือ "กว้าง ยาว สูง" เพื่อให้ครอบคลุมการถามถึงมิติของชิ้นงาน
    has_3d = "3 มิติ" in normalized_question or "3มิติ" in normalized_question
    has_aspects = bool(re.search(r"(ด้านใดบ้าง|ด้านไหนบ้าง|ส่วนประกอบใด|มิติใดบ้าง|กว้างยาวสูง)", normalized_question))
    return has_3d and has_aspects


def is_planning_necessity_question(normalized_question: str) -> bool:
    # เปลี่ยนจากการบังคับคำว่า "ลงมือสร้าง" เป็นการเช็คแค่เรื่อง "วางแผน" 
    # และเพิ่มคำถามเชิง "เหตุผล" หรือ "ความสำคัญ"
    has_planning = "วางแผน" in normalized_question
    has_reason = bool(re.search(r"(เหตุใด|ทำไม|เพราะอะไร|ความสำคัญ|จำเป็น|ต้องวางแผน)", normalized_question))
    
    # กันสับสน: ถ้าถามถึง "ขั้นวางแผน" (ขั้นที่ 4) ให้ข้ามไปใช้ฟังก์ชันอื่น
    is_not_stage_4 = "วางแผนและดำเนินการแก้ปัญหา" not in normalized_question
    
    return has_planning and has_reason and is_not_stage_4


# 💡 ปรับปรุง: เพิ่มเงื่อนไขให้ครอบคลุม "ประโยชน์" และ "นำไปใช้"
def is_test_benefits_question(normalized_question: str) -> bool:
    has_test = "ทดสอบ" in normalized_question and "ประเมินผล" in normalized_question
    # ครอบคลุมทั้ง "ใช้ประโยชน์อย่างไร", "นำไปใช้ประโยชน์", "มีประโยชน์อะไร"
    has_benefits = bool(re.search(r"(ประโยชน์อย่างไร|ใช้ประโยชน์อย่างไร|นำไปใช้ประโยชน์|มีประโยชน์)", normalized_question))
    return has_test and has_benefits


def is_2d_definition_question(normalized_question: str) -> bool:
    return bool(re.search(r"(2 มิติ|2มิติ)", normalized_question)) and bool(re.search(r"(คืออะไร|หมายถึง|อะไรคือ)", normalized_question))


def is_3d_definition_question(normalized_question: str) -> bool:
    return bool(re.search(r"(3 มิติ|3มิติ)", normalized_question)) and bool(re.search(r"(คืออะไร|หมายถึง|อะไรคือ)", normalized_question))


def is_2d_role_question(normalized_question: str) -> bool:
    return bool(re.search(r"(2 มิติ|2มิติ)", normalized_question)) and "มีบทบาท" in normalized_question


def is_planning_stage_question(normalized_question: str) -> bool:
    return "วางแผนและดำเนินการแก้ปัญหา" in normalized_question and bool(re.search(r"(ทำอะไรบ้าง|คืออะไร|ทำหน้าที่อะไร)", normalized_question)) and "ทำไม" not in normalized_question and "เหตุใด" not in normalized_question


def is_testing_stage_question(normalized_question: str) -> bool:
    return bool(re.search(r"(ทดสอบและประเมินผล|ทดสอบ ประเมินผล)", normalized_question)) and bool(re.search(r"(มีไว้เพื่ออะไร|เพื่ออะไร|ทำหน้าที่อะไร)", normalized_question)) and "ประโยชน์" not in normalized_question


def extract_topic_label(question: str, citations: list[Citation], history: list[dict[str, str]]) -> str:
    normalized = normalize_ocr_text(question)
    if "ขั้นออกแบบวิธีการแก้ปัญหา" in normalized:
        if "3 มิติ" in normalized or "3มิติ" in normalized:
            return "ขั้นออกแบบวิธีการแก้ปัญหาโดยใช้ซอฟต์แวร์ออกแบบ 3 มิติ"
        return "ขั้นออกแบบวิธีการแก้ปัญหา"
    if "2 มิติ" in normalized or "2มิติ" in normalized:
        return "การออกแบบ 2 มิติ"
    if "5W1H" in normalized or "5w1h" in normalized:
        return "เทคนิค 5W1H"
    for citation in citations:
        excerpt = normalize_ocr_text(citation.excerpt)
        if "5W1H" in excerpt or "5w1h" in excerpt:
            return "เทคนิค 5W1H"
        if "2 มิติ" in excerpt or "2มิติ" in excerpt:
            return "การออกแบบ 2 มิติ"
        if "กระบวนการออกแบบเชิงวิศวกรรม" in excerpt:
            return "กระบวนการออกแบบเชิงวิศวกรรม"
    return infer_topic_from_history(history)


def infer_topic_from_history(history: list[dict[str, str]]) -> str:
    for turn in reversed(history[-MAX_HISTORY_TURNS:]):
        content = normalize_ocr_text(turn.get("content", ""))
        if "5W1H" in content or "5w1h" in content:
            return "เทคนิค 5W1H"
        if "2 มิติ" in content or "2มิติ" in content:
            return "การออกแบบ 2 มิติ"
        if "ขั้นออกแบบวิธีการแก้ปัญหา" in content and ("3 มิติ" in content or "3มิติ" in content):
            return "ขั้นออกแบบวิธีการแก้ปัญหาโดยใช้ซอฟต์แวร์ออกแบบ 3 มิติ"
        if "กระบวนการออกแบบเชิงวิศวกรรม" in content:
            return "กระบวนการออกแบบเชิงวิศวกรรม"
    return ""


def strip_repeated_topic(text: str, topic_label: str) -> str:
    cleaned = text.strip()
    pattern = r"^" + re.escape(topic_label) + r"\s*"
    return re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip(" ,")


def extract_example_answer_clause(text: str) -> str:
    normalized = clean_noisy_thai_phrase(text.replace("ตััวอย่่างคำตัอบ", "ตัวอย่างคำตอบ"))
    match = re.search(r"ตัวอย่างคำตอบ(.*?)(?:\)|7\.|นักเรียนร่วมกันสรุป|$)", normalized, flags=re.IGNORECASE)
    if not match:
        return ""
    clause = match.group(1)
    clause = re.sub(r"^[\s(:\-]+", "", clause)
    clause = re.sub(r"[′]+", "", clause)
    clause = re.sub(r"เพื่ือ|เพื่ือนำไปัสู่|เพื่ือสือสาร", lambda m: {"เพื่ือ": "เพื่อ", "เพื่ือนำไปัสู่": "เพื่อนำไปสู่", "เพื่ือสือสาร": "เพื่อสื่อสาร"}[m.group(0)], clause)
    clause = re.sub(r"\s+", " ", clause).strip(" ,)")
    if len(clause) < 30:
        return ""
    return clause


def extract_steps_example_clause(text: str) -> str:
    normalized = clean_noisy_thai_phrase(text.replace("ตััวอย่่างคำตัอบ", "ตัวอย่างคำตอบ"))
    match = re.search(
        r"ตัวอย่างคำตอบ\s*(มี\s*\d+\s*ขั้นตอน.*?)(?:\)|•|2\.|นักเรียน|$)",
        normalized,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    clause = match.group(1)
    clause = clean_noisy_thai_phrase(clause)
    clause = clause.replace("ขั้", "ขั้น")
    clause = clause.replace("ตัอน", "ตอน")
    clause = clause.replace("ด้ำเนิน", "ดำเนิน")
    clause = clause.replace("วิธีีก่าร", "วิธีการ")
    clause = clause.replace("ก่าร", "การ")
    clause = clause.replace("แก่้ไขั้", "แก้ไข")
    clause = clause.replace("ชิ้ินงาน", "ชิ้นงาน")
    clause = re.sub(r"\s+", " ", clause).strip(" ,)")
    if "มี 6 ขั้นตอน" in clause and "ได้แก่" in clause:
        return clause
    return ""


def extract_known_engineering_steps(text: str) -> str:
    normalized = clean_noisy_thai_phrase(normalize_ocr_text(text)).lower()
    if "กระบวนการออกแบบเชิงวิศวกรรม" not in normalized:
        return ""
    if not re.search(r"(มีขั้นตอนการดำเนินงานกี่ขั้นตอน|ขั้นระบุปัญหา|ขั้นออกแบบวิธีการแก้ปัญหา)", normalized):
        return ""
    return (
        "มี 6 ขั้นตอน ได้แก่ ขั้นระบุปัญหา ขั้นรวบรวมข้อมูลและแนวคิดที่เกี่ยวข้องกับปัญหา "
        "ขั้นออกแบบวิธีการแก้ปัญหา ขั้นวางแผนและดำเนินการแก้ปัญหา "
        "ขั้นทดสอบ ประเมินผล และปรับปรุงแก้ไขวิธีการแก้ปัญหาหรือชิ้นงาน "
        "และขั้นนำเสนอวิธีการแก้ปัญหา ผลการแก้ปัญหาหรือชิ้นงาน"
    )


def clean_noisy_thai_phrase(text: str) -> str:
    cleaned = text
    replacements = {
        "ความี": "ความ",
        "เปั็น": "เป็น",
        "ขั้อง": "ของ",
        "คิวิาม": "ความ",
        "ชิ้่วย่": "ช่วย",
        "ที่ำ": "ทำ",
        "สิงที่ี": "สิ่งที่",
        "มีอง": "มอง",
        "ย่าก่": "ยาก",
        "ได้้ง่าย่": "ได้ง่าย",
        "เพื่ือ": "เพื่อ",
        "สือสาร": "สื่อสาร",
        "อืน": "อื่น",
        "เขั้้าใจ": "เข้าใจ",
        "หมีาย่": "หมาย",
        "ใชิ้้": "ใช้",
        "แนวที่าง": "แนวทาง",
        "เพื่ือนำไปัสู่": "เพื่อนำไปสู่",
        "ปัฏิิบัตัิงาน": "ปฏิบัติงาน",
        "ตั่อไปั": "ต่อไป",
        "ซอฟ้ต์แวร์": "ซอฟต์แวร์",
        "ทำางาน": "ทำงาน",
        "ดำาเนิน": "ดำเนิน",
        "สำาคัญ": "สำคัญ",
        "ขั้ั": "ขั้น",
        "ขั้น": "ขั้น",
        "ขั้ึน": "ขึ้น",
        "ตั้นแบบ": "ต้นแบบ",
        "ก่าร": "การ",
        "แก่้ปัญหา": "แก้ปัญหา",
        "แก่้ปััญหา": "แก้ปัญหา",
        "ระบุปััญหา": "ระบุปัญหา",
        "ข้้อมูล": "ข้อมูล",
        "อย่่าง": "อย่าง",
        "ด้้วย่": "ด้วย",
        "เป่็น": "เป็น",
        "ตัรง": "ตรง",
        "วิเครูาะห์": "วิเคราะห์",
        "รูวบรูวมู": "รวบรวม",
        "ไมู่มูากพอ": "ไม่มากพอ",
        "จ่ะทำให้": "จะทำให้",
        "ด้ำเนินการู": "ดำเนินการ",
        "ผูู้้ใช้้": "ผู้ใช้",
        "รูถย่นตั์": "รถยนต์",
        "ครูัง": "ครั้ง",
        "หรูือ": "หรือ",
        "ข้ณะ": "ขณะ",
    }
    for original, replacement in replacements.items():
        cleaned = cleaned.replace(original, replacement)
    cleaned = re.sub(r"[′]+", "", cleaned)
    cleaned = re.sub(r"([ัิ-ฺ็-๎])\1+", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def capitalize_first(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    return cleaned[:1].upper() + cleaned[1:]


def select_primary_citation(citations: list[Citation], question_type: str, topic_label: str = "") -> Citation:
    if topic_label == "ขั้นออกแบบวิธีการแก้ปัญหาโดยใช้ซอฟต์แวร์ออกแบบ 3 มิติ":
        for citation in citations:
            normalized_excerpt = clean_noisy_thai_phrase(normalize_ocr_text(citation.excerpt)).lower()
            if re.search(r"(3 มิติ|3มิติ|ต้นแบบ|สื่อสาร|มองเห็น)", normalized_excerpt):
                return citation

    if question_type == "principle" and topic_label == "เทคนิค 5W1H":
        for citation in citations:
            normalized_excerpt = clean_noisy_thai_phrase(normalize_ocr_text(citation.excerpt)).lower()
            if re.search(r"(หลักการจัดภาพโปสเตอร์|infographic|นิตยสารการออกแบบ|photoeditingchallenge|graphicdesign)", normalized_excerpt):
                continue
            if re.search(r"(5w1h|who|what|when|where|why|how|ตั้งคำถาม|ระบุปัญหา)", normalized_excerpt):
                return citation

    if question_type == "definition":
        if topic_label == "เทคนิค 5W1H":
            for citation in citations:
                normalized_excerpt = clean_noisy_thai_phrase(normalize_ocr_text(citation.excerpt)).lower()
                if re.search(r"(แนวข้อสอบ|o-net|pisa|ความหมายของ what คืออะไร)", normalized_excerpt):
                    continue
                if len(re.findall(r"(who|what|when|where|why|how)\s*(?:-|:|คือ)", normalized_excerpt)) >= 3:
                    return citation
        for citation in citations:
            normalized_excerpt = clean_noisy_thai_phrase(normalize_ocr_text(citation.excerpt)).lower()
            if re.search(r"(who\s*(?:-|คือ)|what\s*(?:-|คือ)|when\s*(?:-|คือ)|where\s*(?:-|คือ)|why\s*(?:-|คือ)|how\s*(?:-|คือ))", normalized_excerpt):
                return citation

    if question_type == "importance":
        for citation in citations:
            normalized_excerpt = clean_noisy_thai_phrase(normalize_ocr_text(citation.excerpt)).lower()
            if re.search(r"(ช่วยให้เข้าใจปัญหา|ที่มาของปัญหา|นำข้อมูล.*ออกแบบวิธีการแก้ปัญหา|ตรงกับความต้องการอย่างแท้จริง)", normalized_excerpt):
                return citation

    if question_type == "steps":
        for citation in citations:
            normalized_excerpt = clean_noisy_thai_phrase(normalize_ocr_text(citation.excerpt)).lower()
            if re.search(r"(ตัวอย่างคำตอบ|มีขั้นตอนการดำเนินงานกี่ขั้นตอน)", normalized_excerpt) and re.search(
                r"(มี\s*\d+\s*ขั้นตอน|ขั้นระบุปัญหา|ขั้นรวบรวมข้อมูล|ขั้นออกแบบวิธีการแก้ปัญหา)",
                normalized_excerpt,
            ):
                return citation

    if question_type == "purpose":
        for citation in citations:
            normalized_excerpt = clean_noisy_thai_phrase(normalize_ocr_text(citation.excerpt)).lower()
            if re.search(r"(กระบวนการออกแบบเชิงวิศวกรรม)", normalized_excerpt) and re.search(
                r"(เป็นการดำเนินการแก้ปัญหาอย่างเป็นระบบ|แก้ปัญหาอย่างเป็นระบบ|ช่วยให้เข้าใจปัญหา|ตอบสนองความต้องการ|พากระบวนการพัฒนาวิธีการแก้ปัญหา)",
                normalized_excerpt,
            ):
                return citation

    best = citations[0]
    best_score = citation_answer_score(best, question_type)
    for citation in citations[1:]:
        score = citation_answer_score(citation, question_type)
        if score > best_score:
            best = citation
            best_score = score
    return best


def detect_answer_type(question: str) -> str:
    normalized = question.strip().lower()
    
    # 1. กลุ่มความสำคัญ (เน้น ทำไมต้อง..., ความสำคัญคืออะไร, เหตุใดถึง...)
    if re.search(r"(สำคัญอย่างไร|สำคัญยังไง|มีความสำคัญอย่างไร|importance|why important|ทำไม|เหตุใด|เพราะอะไร)", normalized):
        return "importance"
        
    # 2. กลุ่มหลักการ/เทคนิค
    if re.search(r"(ใช้หลักการใด|ใช้หลักการอะไร|ใช้เทคนิคใด|ใช้เทคนิคอะไร|ใช้วิธีใด|ใช้วิธีอะไร|หลักการใดช่วย|เทคนิคใดช่วย)", normalized):
        return "principle"
        
    # 3. กลุ่มวัตถุประสงค์ (เน้น เพื่ออะไร, จุดมุ่งหมายคืออะไร)
    if re.search(r"(จุดมุ่งหมาย.*อะไร|มีจุดมุ่งหมาย.*อะไร|มีไว้เพื่ออะไร|วัตถุประสงค์.*อะไร|เป้าหมาย.*อะไร|เพื่ออะไร)", normalized):
        return "purpose"
        
    # 4. กลุ่มรายการ/ขั้นตอน (เน้น กี่ขั้นตอน, ด้านใดบ้าง, กี่ลักษณะ)
    if re.search(r"(กี่ขั้นตอน|มีขั้นตอนอะไรบ้าง|อะไรบ้าง|ขั้นตอน.*อะไรบ้าง|มาจากไหน|มาจากที่ใด|หาจากไหน|แหล่งข้อมูล|กี่ลักษณะ|เชื่อมโยงกัน|ด้านใดบ้าง)", normalized):
        return "steps"
        
    # 5. กลุ่มผลลัพธ์และการแก้ไข (เน้น ส่งผลอย่างไร, ควรทำอย่างไร, ปรับปรุงอย่างไร, ประโยชน์อย่างไร)
    if re.search(r"(ส่งผล.*อย่างไร|มีผล.*อย่างไร|ผลกระทบ.*อย่างไร|มีผลเสีย.*อย่างไร|จะเกิดอะไรขึ้น|หาก.*ไม่ชัดเจน|ควรทำอย่างไร|ทำอย่างไร|แก้ไขอย่างไร|ประโยชน์อย่างไร)", normalized):
        return "reason"
        
    # 6. กลุ่มนิยาม
    if re.search(
        r"(คืออะไร|อธิบาย|หมายถึง|หมายถึงอะไร|มีความหมายว่าอะไร|ความหมายว่าอะไร|สื่อถึงอะไร|สื่อความว่าอย่างไร|ใจความว่าอย่างไร|มีใจความว่าอย่างไร)",
        normalized,
    ):
        return "definition"
        
    return "general"


def normalize_ocr_text(text: str) -> str:
    cleaned = " ".join(text.split()).strip()
    cleaned = cleaned.replace("\ufffd", "")
    cleaned = re.sub(r"(?<=[ก-๙])\s+(?=[ก-๙])", "", cleaned)
    cleaned = re.sub(r"(?<=[A-Za-z])\s+(?=[A-Za-z])", "", cleaned)
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    cleaned = re.sub(r"[•▪■◆]+", " ", cleaned)
    cleaned = re.sub(r"([ัิ-ฺ็-๎])\1+", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def normalize_question_synonyms(text: str) -> str:
    """แปลงคำพ้องความหมายและการสะกดแบบอื่นให้ตรงกับคำในหนังสือ"""
    t = text
    t = t.replace("สามมิติ", "3 มิติ").replace("สองมิติ", "2 มิติ")
    t = t.replace("สาม มิติ", "3 มิติ").replace("สอง มิติ", "2 มิติ")
    t = t.replace("3มิติ", "3 มิติ").replace("2มิติ", "2 มิติ")
    t = re.sub(r"กระบวนการออกแบบวิศวกรรม(?!เชิง)", "กระบวนการออกแบบเชิงวิศวกรรม", t)
    t = re.sub(r"การออกแบบวิศวกรรม(?!เชิง)", "กระบวนการออกแบบเชิงวิศวกรรม", t)
    t = re.sub(r"(?<!เชิง)ออกแบบเชิงวิศวกรรม", "กระบวนการออกแบบเชิงวิศวกรรม", t)
    t = re.sub(r"\bขั้นระบุ\b", "ขั้นระบุปัญหา", t)
    t = re.sub(r"\bขั้นรวบรวม\b", "ขั้นรวบรวมข้อมูล", t)
    t = re.sub(r"\bขั้นออกแบบ\b", "ขั้นออกแบบวิธีการแก้ปัญหา", t)
    t = re.sub(r"\bขั้นวางแผน\b", "ขั้นวางแผนและดำเนินการแก้ปัญหา", t)
    t = re.sub(r"\bขั้นทดสอบ\b", "ขั้นทดสอบและประเมินผล", t)
    t = re.sub(r"\bขั้นนำเสนอ\b", "ขั้นนำเสนอวิธีการแก้ปัญหา", t)
    return t


def looks_like_low_quality_excerpt(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized or len(normalized) < 25:
        return True
    if normalized.count("\ufffd") > 0:
        return True
    if re.search(r"(คำศัพท์|animation|graphicdesign|แอนิเมชัน|กราฟิกดีไซน์)", normalized):
        return True
    if re.search(r"(ว\s*\d+\.\d+|ม\.\d+/\d+)", normalized):
        return True
    if re.search(r"^[\s\d.]+$|^[ก-๙a-zA-Z]{1,10}\s*\d*\.?\s*$", normalized):
        return True
    return False


def first_clean_sentence(sentences: list[str]) -> str:
    for sentence in sentences:
        if not looks_like_low_quality_excerpt(sentence):
            return sentence.strip()
    return ""


def extract_named_principle(text: str, topic_label: str = "") -> str:
    normalized = clean_noisy_thai_phrase(normalize_ocr_text(text))
    lowered = normalized.lower()

    if "5w1h" in lowered:
        if "ตั้งคำถาม" in normalized or "ระบุปัญหา" in normalized or topic_label == "เทคนิค 5W1H":
            return "ใช้เทคนิค 5W1H ในการตั้งคำถาม"

    if re.search(r"(engineering design process|กระบวนการออกแบบเชิงวิศวกรรม)", lowered):
        return "ใช้กระบวนการออกแบบเชิงวิศวกรรม"

    match = re.search(r"(เทคนิค\s*[A-Za-z0-9\-]+)", normalized, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()

    match = re.search(r"(หลักการ[^\s,.;:]+)", normalized)
    if match:
        return match.group(1).strip()

    return ""


def extract_engineering_purpose_summary(text: str, topic_label: str = "") -> str:
    normalized = clean_noisy_thai_phrase(normalize_ocr_text(text))
    lowered = normalized.lower()

    if "กระบวนการออกแบบเชิงวิศวกรรม" not in lowered:
        return ""

    if re.search(r"(เป็นการดำเนินการแก้ปัญหาอย่างเป็นระบบ|แก้ปัญหาอย่างเป็นระบบ)", lowered):
        summary = "กระบวนการออกแบบเชิงวิศวกรรมมีจุดประสงค์เพื่อแก้ปัญหาอย่างเป็นระบบ"
        if re.search(r"(help to understand|ช่วยให้เข้าใจปัญหา|ที่มาของปัญหา)", lowered):
            summary += " และช่วยให้เข้าใจปัญหากับที่มาของปัญหาได้ชัดเจนขึ้น"
        return summary

    if re.search(r"(ตอบสนองความต้องการ|พัฒนาวิธีการแก้ปัญหา|สร้างชิ้นงาน)", lowered):
        return "กระบวนการออกแบบเชิงวิศวกรรมมีจุดประสงค์เพื่อพัฒนาวิธีการแก้ปัญหาหรือชิ้นงานให้ตอบสนองความต้องการ"

    return ""


def extract_domain_keywords(text: str) -> set[str]:
    lowered = text.lower()
    keyword_map = {
        # 💡 ปรับปรุงคีย์เวิร์ดเพื่อให้โมเดลแยกความต่างระหว่างภาพรวมระบบและขั้นย่อยที่ 3
        "กระบวนการออกแบบเชิงวิศวกรรม": ["กระบวนการออกแบบเชิงวิศวกรรม", "engineering design", "เชื่อมโยง", "ภาพรวม"],
        "5w1h": ["5w1h"],
        "จุดมุ่งหมาย": ["จุดมุ่งหมาย", "วัตถุประสงค์", "เป้าหมาย", "เพื่ออะไร", "มีไว้เพื่อ"],
        "ขั้นตอน": ["ขั้นตอน", "กี่ขั้นตอน", "อะไรบ้าง"],
        "ระบุปัญหา": ["ระบุปัญหา"],
        "ออกแบบวิธีการแก้ปัญหา": ["ออกแบบวิธีการแก้ปัญหา", "กี่ลักษณะ", "3 มิติ", "ด้านใดบ้าง"],
        "รวบรวมข้อมูล": ["รวบรวมข้อมูล", "แหล่งข้อมูล", "มาจากไหน", "มาจากที่ใด"],
        "วางแผนและสร้าง": ["วางแผน", "ลงมือสร้าง", "สร้างชิ้นงาน"],
        "ปรับปรุงแก้ไข": ["ไม่เป็นไปตามวัตถุประสงค์", "ปรับปรุงแก้ไข", "ควรทำอย่างไร", "ประโยชน์อย่างไร"],
    }

    keywords: set[str] = set()
    for keyword, markers in keyword_map.items():
        if any(marker in lowered for marker in markers):
            keywords.add(keyword)
    return keywords


def strip_leading_noise(text: str) -> str:
    cleaned = re.sub(r"^(ข้อมูลส่วนนี้กล่าวถึงว่า|นักเรียนวิเคราะห์ตัวอย่างการใช้เทคนิค\s*5w1h|แผนภาพที่\s*\S+)\s*", "", text, flags=re.IGNORECASE)
    return cleaned.strip(" ,")


def normalize_importance_statement(text: str) -> str:
    cleaned = strip_leading_noise(text)
    cleaned = re.sub(r"^เทคนิค\s*5w1h\s*(นี้)?", "เทคนิค 5W1H", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"เทคนิค 5W1Hจะ", "เทคนิค 5W1H จะ", cleaned)
    if re.search(r"(ช่วยให้|ทำให้|เข้าใจปัญหา|กำหนดปัญหา|วิเคราะห์ปัญหา)", cleaned):
        return f"เทคนิค 5W1H สำคัญเพราะ{ensure_reason_clause(cleaned)}"
    return f"เทคนิค 5W1H สำคัญเพราะ {cleaned}"


def normalize_steps_statement(text: str) -> str:
    cleaned = strip_leading_noise(text)
    cleaned = re.sub(r"สนทนาตอบคำถามดังนี้", "", cleaned)
    cleaned = re.sub(r"ตอบคำถามดังนี้", "", cleaned)
    cleaned = re.sub(r"^(กระบวนการออกแบบเชิงวิศวกรรม)\s*(แล้ว|โดย|มีี|มี)\s*", r"\1 มี ", cleaned)
    cleaned = re.sub(r"^(กระบวนการออกแบบเชิงวิศวกรรม)\s*มี\s*กระบวนการออกแบบเชิงวิศวกรรมมี", r"\1 มี", cleaned)
    cleaned = re.sub(r"มีี", "มี", cleaned)
    cleaned = re.sub(r"ขั้ั.\s*น", "ขั้น", cleaned)
    cleaned = re.sub(r"ตััวอย่่างคำตัอบ", "", cleaned)
    cleaned = re.sub(r"ได้แก่ขั้น", "ได้แก่ ขั้น", cleaned)
    cleaned = re.sub(r"(?<!ได้แก่\s)(ขั้นระบุปัญหา)", r" \1", cleaned)
    cleaned = re.sub(r"(ขั้นระบุปัญหา)(ขั้นรวบรวม)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(ขั้นรวบรวมข้อมูลและแนวคิดที่เกี่ยวข้องกับปัญหา)(ขั้นออกแบบ)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(ขั้นออกแบบวิธีการแก้ปัญหา)(ขั้นวางแผน)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(ขั้นวางแผนและดำเนินการแก้ปัญหา)(ขั้นทดสอบ)", r"\1 \2", cleaned)
    cleaned = re.sub(r"(ชิ้นงาน)(และขั้นนำเสนอ)", r"\1 \2", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ,")


def ensure_reason_clause(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("ช่วยให้") or cleaned.startswith("ทำให้") or cleaned.startswith("เข้าใจ") or cleaned.startswith("กำหนด"):
        return f" {cleaned}"
    return f" {cleaned}"


def citation_answer_score(citation: Citation, question_type: str) -> int:
    text = clean_noisy_thai_phrase(normalize_ocr_text(citation.excerpt)).lower()
    score = 0

    if len(text) < 20:
        score -= 5
    if len(text) > 220:
        score -= 2
    if re.fullmatch(r"(ใน|ขั้น|ระบุปัญหา|ในขั้นระบุปัญหา|การใช้เทคนิค\s*5w1h|ตัวอย่างการใช้เทคนิค\s*5w1h)+", text):
        score -= 8
    if len(text) < 40 and not re.search(r"(ช่วยให้|ทำให้|คือ|หมายถึง|เพราะ|วิเคราะห์|เข้าใจ|กำหนด)", text):
        score -= 6
    if re.search(r"(นักเรียนวิเคราะห์ตัวอย่าง|ใบกิจกรรม|แบบฝึกหัด|แผนภาพที่)", text):
        score -= 4
    if re.search(r"(แนวข้อสอบ|o-net|pisa|ความหมายของ what คืออะไร)", text):
        score -= 8
    if re.search(r"(ว\s*\d+\.\d+|ม\.\d+/\d+|คำศัพท์|graphicdesign|animation)", text):
        score -= 5
    if re.search(r"(สมรรถนะสำคัญของผู้เรียน|บูรณาการทักษะศตวรรษที่ 21|photoeditingchallenge|livefacebook)", text):
        score -= 10

    if question_type == "importance":
        if re.search(r"(ช่วยให้|ทำให้|เข้าใจปัญหา|ที่มาของปัญหา|วิเคราะห์|กำหนดแนวทาง|ชัดเจน)", text):
            score += 6
        if re.search(r"(สำคัญ|มีความสำคัญ)", text):
            score += 3
        if re.search(r"(3 มิติ|3มิติ|ต้นแบบ|สื่อสาร|มองเห็น)", text):
            score += 4
        if text.startswith("ช่วย") or text.startswith("ทำให้"):
            score += 5
        if re.search(r"(ว\s*\d+\.\d+|ม\.\d+/\d+|3\.)", text):
            score -= 6
    elif question_type == "definition":
        if re.search(r"(คือ|หมายถึง|ได้แก่)", text):
            score += 5
        if len(re.findall(r"(who|what|when|where|why|how)\s*(?:-|:|คือ)", text)) >= 3:
            score += 12
    elif question_type == "principle":
        if re.search(r"(5w1h|ตั้งคำถาม|ระบุปัญหา)", text):
            score += 10
        if re.search(r"(who|what|when|where|why|how)", text):
            score += 8
        if re.search(r"(ช่วยให้เข้าใจปัญหา|ที่มาของปัญหา|วิเคราะห์ปัญหา)", text):
            score += 6
        if re.search(r"(หลักการจัดภาพโปสเตอร์|infographic|นิตยสารการออกแบบ|photoeditingchallenge|graphicdesign)", text):
            score -= 14
    elif question_type == "reason":
        if re.search(r"(เพราะ|เนื่องจาก|จึง|ส่งผลให้)", text):
            score += 5
        if re.search(r"(ยังไม่เข้าใจตัวปัญหา|ที่มาของปัญหา|หลงประเด็น|เสียเวลา|ทรัพยากร|ไม่ตรงกับความต้องการ)", text):
            score += 12
        if re.search(r"(ตัวชี้วัด|แนวข้อสอบ|o-net|pisa|applyingandconstructingtheknowledge)", text):
            score -= 12
    elif question_type == "steps":
        if re.search(r"(มี\s*\d+\s*ขั้นตอน|ได้แก่|ประกอบด้วย)", text):
            score += 8
        if re.search(r"(ขั้นระบุปัญหา|ขั้นรวบรวมข้อมูล|ขั้นออกแบบวิธีการแก้ปัญหา|ขั้นวางแผน|ขั้นทดสอบ|ขั้นนำเสนอ)", text):
            score += 8
        if re.search(r"(ว\s*\d+\.\d+|ม\.\d+/\d+)", text):
            score -= 6
        if re.search(r"(ตัวอย่างคำตอบ|มีขั้นตอนการดำเนินงานกี่ขั้นตอน)", text):
            score += 6
    elif question_type == "purpose":
        if re.search(r"(กระบวนการออกแบบเชิงวิศวกรรม|engineering design process)", text):
            score += 6
        if re.search(r"(เป็นการดำเนินการแก้ปัญหาอย่างเป็นระบบ|แก้ปัญหาอย่างเป็นระบบ)", text):
            score += 10
        if re.search(r"(ช่วยให้เข้าใจปัญหา|ที่มาของปัญหา|ตอบสนองความต้องการ|พัฒนาวิธีการแก้ปัญหา|ชิ้นงาน)", text):
            score += 6
        if re.search(r"(สมรรถนะสำคัญของผู้เรียน|เป้าหมายสมรรถนะ|บูรณาการทักษะศตวรรษที่ 21)", text):
            score -= 12

    return score


def is_weak_lead_answer(text: str, question_type: str) -> bool:
    normalized = normalize_ocr_text(text).lower()
    if len(normalized) < 25:
        return True
    if re.search(r"(นักเรียนสืบค้นข้อมูล|นักเรียนร่วมกัน|สนทนาตอบคำถามดังนี้|ตอบคำถามดังนี้|จงตอบคำถาม|ตัวอย่างคำตอบ)", normalized):
        return True
    if question_type == "importance":
        if re.fullmatch(r"(เทคนิค 5w1h สำคัญเพราะ\s*)?(ในขั้นระบุปัญหา|การใช้เทคนิค 5w1h|ตัวอย่างการใช้เทคนิค 5w1h)", normalized):
            return True
        if not re.search(r"(ช่วยให้|ทำให้|เข้าใจ|วิเคราะห์|กำหนด|ชัดเจน|ที่มาของปัญหา)", normalized):
            return True
    if question_type == "purpose":
        if not re.search(r"(จุดประสงค์|จุดมุ่งหมาย|เพื่อ|แก้ปัญหาอย่างเป็นระบบ|ตอบสนองความต้องการ|ชิ้นงาน|เข้าใจปัญหา)", normalized):
            return True
    if question_type == "steps":
        if not re.search(r"(ขั้นตอน|ได้แก่|ประกอบด้วย|มี\s*\d+\s*ขั้นตอน)", normalized):
            return True
    return False


def strip_activity_boilerplate(text: str) -> str:
    cleaned = text
    # ตัดส่วน prefix กิจกรรม แล้วเอาเนื้อหาหลัง "ดังนี้" หรือ "ดังนี้ " แทน
    match = re.search(r"ดังนี้\s*(.+)", cleaned, flags=re.DOTALL)
    if match:
        candidate = match.group(1).strip()
        if len(candidate) > 30:
            cleaned = candidate
            return cleaned.strip(" ,")
    cleaned = re.sub(
        r"^(นักเรียนสืบค้นข้อมูลเกี่ยวกับ|นักเรียนร่วมกันแสดงความคิดเห็นเกี่ยวกับ|นักเรียนร่วมกันวิเคราะห์และแสดงความคิดเห็นเกี่ยวกับ|นักเรียนร่วมกันวิเคราะห์เกี่ยวกับ)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"แล้วสนทนาตอบคำถามดังนี้.*?$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"โดยตอบคำถามดังนี้.*?$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"ตอบคำถามดังนี้.*?$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"•.*?$", "", cleaned)
    return cleaned.strip(" ,")


def extract_steps_clause(text: str) -> str:
    match = re.search(
        r"(กระบวนการออกแบบเชิงวิศวกรรม.*?มี\s*\d+\s*ขั้นตอน.*?ได้แก่.*)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    match = re.search(r"(มี\s*\d+\s*ขั้นตอน[^.]*?ได้แก่[^.]+)", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return ""