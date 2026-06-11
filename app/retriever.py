from __future__ import annotations

import pickle
import re
from collections import Counter
from dataclasses import dataclass

from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.config import INDEX_PATH, MAX_HISTORY_TURNS, MIN_RELEVANCE_SCORE, TOP_K
from app.documents import DocumentChunk, build_source_manifest


@dataclass
class SearchResult:
    chunk: DocumentChunk
    score: float


@dataclass
class SearchIndex:
    vectorizers: dict[str, TfidfVectorizer]
    matrix: object
    chunks: list[DocumentChunk]
    manifest: dict[str, str]


def save_index(index: SearchIndex) -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_PATH.open("wb") as file:
        pickle.dump(index, file)


def load_index() -> SearchIndex | None:
    if not INDEX_PATH.exists():
        return None
    with INDEX_PATH.open("rb") as file:
        index = pickle.load(file)

    if not isinstance(index, SearchIndex):
        return None
    if not hasattr(index, "manifest") or not hasattr(index, "vectorizers"):
        return None
    if index.manifest != build_source_manifest():
        return None
    return index


def build_index(chunks: list[DocumentChunk]) -> SearchIndex:
    texts = [chunk.text for chunk in chunks]

    char_vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True)
    word_vectorizer = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), lowercase=True, token_pattern=r"(?u)\b\w+\b")

    char_matrix = char_vectorizer.fit_transform(texts)
    word_matrix = word_vectorizer.fit_transform(texts)
    matrix = hstack([char_matrix, word_matrix]).tocsr()
    return SearchIndex(
        vectorizers={"char": char_vectorizer, "word": word_vectorizer},
        matrix=matrix,
        chunks=chunks,
        manifest=build_source_manifest(),
    )


def search(
    index: SearchIndex,
    question: str,
    top_k: int = TOP_K,
    history: list[dict[str, str]] | None = None,
) -> list[SearchResult]:
    expanded_question = expand_question_for_search(build_contextual_query(question, history or []))
    char_query = index.vectorizers["char"].transform([expanded_question])
    word_query = index.vectorizers["word"].transform([expanded_question])
    query_vector = hstack([char_query, word_query]).tocsr()
    similarities = cosine_similarity(query_vector, index.matrix).flatten()
    question_type = detect_question_type(question)
    ranked = rerank_indices(index, question, similarities)
    question_terms = important_terms(expanded_question)

    results: list[SearchResult] = []
    for chunk_index in ranked:
        chunk = index.chunks[chunk_index]
        score = float(similarities[chunk_index])
        bonus = chunk_priority_bonus(chunk.text, question_type)
        overlap = overlap_score(question_terms, chunk.text)
        min_score = MIN_RELEVANCE_SCORE if bonus <= 0 else max(0.04, MIN_RELEVANCE_SCORE - min(0.04, bonus / 2))
        if question_terms and overlap <= 0.0 and score < 0.2:
            continue
        if score < min_score:
            continue
        results.append(SearchResult(chunk=chunk, score=score + overlap))
        if len(results) >= top_k:
            break
    return results


def summarize_sources(index: SearchIndex) -> list[tuple[str, int]]:
    counts = Counter(chunk.source for chunk in index.chunks)
    return sorted(counts.items())


def rerank_indices(index: SearchIndex, question: str, similarities: object) -> list[int]:
    question_type = detect_question_type(question)
    question_terms = important_terms(expand_question_for_search(question))
    scored_indices: list[tuple[float, int]] = []

    for chunk_index, base_score in enumerate(similarities):
        chunk_text = index.chunks[chunk_index].text
        boosted_score = float(base_score) + chunk_priority_bonus(chunk_text, question_type) + overlap_score(question_terms, chunk_text)
        scored_indices.append((boosted_score, chunk_index))

    scored_indices.sort(key=lambda item: item[0], reverse=True)
    return [chunk_index for _, chunk_index in scored_indices]


def detect_question_type(question: str) -> str:
    normalized = question.strip().lower()
    if re.search(r"(สำคัญอย่างไร|สำคัญยังไง|มีความสำคัญอย่างไร|importance|why important)", normalized):
        return "importance"
    if re.search(r"(จุดมุ่งหมาย.*อะไร|มีจุดมุ่งหมาย.*อะไร|มีไว้เพื่ออะไร|วัตถุประสงค์.*อะไร|เป้าหมาย.*อะไร|เพื่ออะไร)", normalized):
        return "purpose"
    if re.search(r"(กี่ขั้นตอน|มีขั้นตอนอะไรบ้าง|อะไรบ้าง|ขั้นตอน.*อะไรบ้าง)", normalized):
        return "steps"
    if re.search(
        r"(คืออะไร|คือ|หมายถึงอะไร|หมายถึง|มีความหมายว่าอะไร|ความหมายว่าอะไร|สื่อถึงอะไร|สื่อความว่าอย่างไร|อธิบาย|นิยาม|definition|what is|ใจความว่าอย่างไร|มีใจความว่าอย่างไร)",
        normalized,
    ):
        return "definition"
    if re.search(r"(ส่งผล.*อย่างไร|มีผล.*อย่างไร|ผลกระทบ.*อย่างไร|มีผลเสีย.*อย่างไร|จะเกิดอะไรขึ้น|หาก.*ไม่ชัดเจน)", normalized):
        return "reason"
    if re.search(r"(อย่างไร|ยังไง|ทำงานอย่างไร|ทำงานยังไง|how|process|ขั้นตอน)", normalized):
        return "process"
    if re.search(r"(ทำไม|เพราะอะไร|เหตุใด|why|reason|สาเหตุ)", normalized):
        return "reason"
    return "general"


def chunk_priority_bonus(text: str, question_type: str) -> float:
    lowered = text.lower()
    bonus = 0.0

    if re.search(r"(นักเรียนวิเคราะห์ตัวอย่าง|ใบกิจกรรม|แบบฝึกหัด|จงตอบคำถาม|แผนภาพที่|คำศัพท์|ตัวอย่างคำตอบ)", lowered):
        bonus -= 0.12
    if re.search(r"(แนวข้อสอบ|o-net|pisa|ความหมายของ what คืออะไร|1\.\s*กระบวนการออกแบบเชิงวิศวกรรมมีความสำคัญ)", lowered):
        bonus -= 0.22

    if question_type == "definition":
        if re.search(r"(คือ|หมายถึง|ได้แก่|นิยาม)", lowered):
            bonus += 0.08
        if re.search(r"(มีบทบาท|หน้าที่|ช่วยให้|กระบวนการ)", lowered):
            bonus += 0.02
        if re.search(r"(5w1h|who\s*-|what\s*-|when\s*-|where\s*-|why\s*-|how\s*-)", lowered):
            bonus += 0.16
        if len(re.findall(r"(who|what|when|where|why|how)\s*(?:-|:|คือ)", lowered)) >= 3:
            bonus += 0.28
        if re.search(r"(ความหมายของ what คืออะไร|แนวข้อสอบ|o-net|pisa)", lowered):
            bonus -= 0.14
    elif question_type == "importance":
        if re.search(r"(ช่วยให้|ทำให้|มีความสำคัญ|สำคัญ|เข้าใจปัญหา|วิเคราะห์ปัญหา|กำหนดปัญหา)", lowered):
            bonus += 0.12
        if re.search(r"(5w1h|problem identification|ระบุปัญหา)", lowered):
            bonus += 0.03
        if re.search(r"(เทคนิค 5w1h นี้จะช่วยให้|ช่วยให้เข้าใจปัญหา|ที่มาของปัญหา|ตรงกับความต้องการอย่างแท้จริง)", lowered):
            bonus += 0.22
        if re.search(r"(ออกแบบวิธีการแก้ปัญหา|ซอฟต์แวร์|3 มิติ|3มิติ|แบบจำลอง|modeling|graphicdesign|animation)", lowered):
            bonus += 0.1
        if re.search(r"(นักเรียนแบ่งกลุ่มตามความเหมาะสม|portfolio|แฟ้มสะสมผลงาน|นักเรียนร่วมกันตอบคำถามดังนี้)", lowered):
            bonus -= 0.14
    elif question_type == "steps":
        if re.search(r"(ขั้นตอน|ได้แก่|ประกอบด้วย|มี\s*\d+\s*ขั้นตอน)", lowered):
            bonus += 0.12
        if re.search(r"(กระบวนการออกแบบเชิงวิศวกรรม|engineering design process)", lowered):
            bonus += 0.03
        if re.search(r"(มีขั้นตอนการดำเนินงานกี่ขั้นตอน|ตัวอย่างคำตอบมีี?\s*\d+\s*ขั้|ตัวอย่างคำตอบมี\s*\d+\s*ขั้นตอน)", lowered):
            bonus += 0.32
        if re.search(r"(ขั้นระบุปัญหา.*ขั้นรวบรวม.*ขั้นออกแบบ.*ขั้นวางแผน.*ขั้นทดสอบ.*ขั้นนำเสนอ)", lowered):
            bonus += 0.4
        if re.search(r"(ว\s*\d+\.\d+|ม\.\d+/\d+)", lowered):
            bonus -= 0.12
    elif question_type == "purpose":
        if re.search(r"(กระบวนการออกแบบเชิงวิศวกรรม|engineering design process)", lowered):
            bonus += 0.12
        if re.search(r"(เป็นการดำเนินการแก้ปัญหาอย่างเป็นระบบ|แก้ปัญหาอย่างเป็นระบบ|ช่วยให้เข้าใจปัญหา|พัฒนาวิธีการแก้ปัญหา|ตอบสนองความต้องการ)", lowered):
            bonus += 0.2
        if re.search(r"(สมรรถนะสำคัญของผู้เรียน|บูรณาการทักษะศตวรรษที่ 21|photoeditingchallenge|livefacebook)", lowered):
            bonus -= 0.28
    elif question_type == "process":
        if re.search(r"(ขั้นตอน|กระบวนการ|เริ่ม|ต่อมา|จากนั้น|ทำให้)", lowered):
            bonus += 0.08
    elif question_type == "reason":
        if re.search(r"(เพราะ|เนื่องจาก|สาเหตุ|ส่งผลให้|จึง)", lowered):
            bonus += 0.08
        if re.search(r"(หากเราละเลยขั้นตอนของการระบุปัญหา|ยังไม่เข้าใจตัวปัญหา|ที่มาของปัญหา|หลงประเด็น|เสียเวลา|ทรัพยากร|ไม่ตรงกับความต้องการ)", lowered):
            bonus += 0.24
        if re.search(r"(แนวข้อสอบ|o-net|pisa|ตัวชี้วัด|applyingandconstructingtheknowledge)", lowered):
            bonus -= 0.2
    elif question_type == "principle":
        if re.search(r"(5w1h|who\s*-|what\s*-|when\s*-|where\s*-|why\s*-|how\s*-|ตั้งคำถาม|ระบุปัญหา)", lowered):
            bonus += 0.2
        if re.search(r"(ช่วยให้เข้าใจปัญหา|ที่มาของปัญหา|วิเคราะห์ปัญหา)", lowered):
            bonus += 0.08
        if re.search(r"(หลักการจัดภาพโปสเตอร์|infographic|นิตยสารการออกแบบ|photoeditingchallenge|graphicdesign)", lowered):
            bonus -= 0.28

    return bonus


def important_terms(text: str) -> set[str]:
    normalized = normalize_question_text(text)
    stop_words = {
        "อะไร",
        "อย่างไร",
        "ยังไง",
        "คือ",
        "ที่",
        "การ",
        "ของ",
        "และ",
        "โดย",
        "ใช้",
        "มี",
        "ความ",
        "สำคัญ",
        "ขั้น",
    }
    terms = {term for term in re.findall(r"[\wก-๙]+", normalized) if len(term) > 1}
    keywords = {term for term in terms if term not in stop_words}
    keywords.update(extract_domain_keywords(normalized))
    return keywords


def normalize_question_text(text: str) -> str:
    cleaned = text.lower()

    # ── ตัวเลขภาษาไทย → ตัวเลข ──────────────────────────
    cleaned = cleaned.replace("สาม", "3").replace("สอง", "2").replace("หนึ่ง", "1")
    cleaned = cleaned.replace("หก", "6").replace("ห้า", "5").replace("สี่", "4")

    # ── รูปแบบที่พิมพ์ติดกัน ─────────────────────────────
    cleaned = cleaned.replace("3มิติ", "3 มิติ")
    cleaned = cleaned.replace("2มิติ", "2 มิติ")

    # ── Synonym ภาษาไทยที่หมายความเดียวกัน ──────────────
    synonyms = {
        # มิติ
        "ชิ้นงานสามมิติ":          "ชิ้นงาน 3 มิติ",
        "ชิ้นงานสองมิติ":          "ชิ้นงาน 2 มิติ",
        "งานสามมิติ":              "งาน 3 มิติ",
        "งานสองมิติ":              "งาน 2 มิติ",
        "แบบสามมิติ":              "แบบ 3 มิติ",
        "แบบสองมิติ":              "แบบ 2 มิติ",
        "3มิติ":                   "3 มิติ",
        "2มิติ":                   "2 มิติ",
        # กระบวนการออกแบบ
        "กระบวนการออกแบบวิศวกรรม": "กระบวนการออกแบบเชิงวิศวกรรม",
        "วิธีออกแบบวิศวกรรม":      "กระบวนการออกแบบเชิงวิศวกรรม",
        "การออกแบบวิศวกรรม":       "กระบวนการออกแบบเชิงวิศวกรรม",
        "ออกแบบเชิงวิศวกรรม":      "กระบวนการออกแบบเชิงวิศวกรรม",
        # 5W1H
        "5 w 1 h":  "5w1h",
        "5w 1h":    "5w1h",
        "ไฟว์ดับเบิ้ลยูวันเอช": "5w1h",
        # ขั้นตอน
        "ขั้นตอนวิศวกรรม":         "กระบวนการออกแบบเชิงวิศวกรรม",
        "ขั้นตอนการออกแบบ":        "กระบวนการออกแบบเชิงวิศวกรรม ขั้นตอน",
        "ขั้นตอนแก้ปัญหา":         "ขั้นตอนการแก้ปัญหา กระบวนการออกแบบเชิงวิศวกรรม",
        "ขั้นระบุ":                 "ขั้นระบุปัญหา",
        "ขั้นรวบรวม":              "ขั้นรวบรวมข้อมูล",
        "ขั้นออกแบบ":              "ขั้นออกแบบวิธีการแก้ปัญหา",
        "ขั้นวางแผน":              "ขั้นวางแผนและดำเนินการแก้ปัญหา",
        "ขั้นทดสอบ":               "ขั้นทดสอบและประเมินผล",
        "ขั้นนำเสนอ":              "ขั้นนำเสนอวิธีการแก้ปัญหา",
        # การวางแผน
        "ก่อนสร้าง":               "ก่อนลงมือสร้างชิ้นงาน",
        "ก่อนทำ":                  "ก่อนลงมือสร้างชิ้นงาน วางแผน",
        # ระบบเทคโนโลยี
        "ระบบควบคุม":              "ระบบควบคุมการทำงานของเทคโนโลยี",
        "วงปิด":                   "ระบบควบคุมแบบวงปิด",
        "วงเปิด":                  "ระบบควบคุมแบบวงเปิด",
    }
    for wrong, correct in synonyms.items():
        cleaned = cleaned.replace(wrong, correct)

    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def build_contextual_query(question: str, history: list[dict[str, str]]) -> str:
    normalized_question = normalize_question_text(question)
    if not needs_history_context(normalized_question):
        return question

    prior_turns: list[str] = []
    for turn in reversed(history[-MAX_HISTORY_TURNS:]):
        content = turn.get("content", "").strip()
        if not content:
            continue
        if normalize_question_text(content) == normalized_question:
            continue
        salient = extract_salient_history_context(content)
        if not salient:
            continue
        prior_turns.append(salient)
        if len(prior_turns) >= 3:
            break

    if not prior_turns:
        return question

    context = " ".join(reversed(prior_turns))
    return f"{context} {question}".strip()


def needs_history_context(question: str) -> bool:
    return bool(
        re.search(
            r"(แนวทางนี้|วิธีนี้|เรื่องนี้|ข้อนี้|แบบนี้|อันนี้|อย่างนี้|ตัวนี้|สิ่งนี้|ยกตัวอย่าง|ตัวอย่างของปัญหา)",
            question,
        )
    )


def extract_salient_history_context(text: str) -> str:
    normalized = normalize_question_text(text)
    topics: list[str] = []

    if "5w1h" in normalized:
        topics.extend(
            [
                "เทคนิค 5W1H",
                "Who คือใคร",
                "What คืออะไร",
                "When คือเมื่อไร",
                "Where คือที่ไหน",
                "Why คือทำไม",
                "How คืออย่างไร",
            ]
        )
    if "กระบวนการออกแบบเชิงวิศวกรรม" in normalized:
        topics.append("กระบวนการออกแบบเชิงวิศวกรรม")
    if "ขั้นออกแบบวิธีการแก้ปัญหา" in normalized:
        topics.append("ขั้นออกแบบวิธีการแก้ปัญหา")
    if "3 มิติ" in normalized or "3มิติ" in normalized:
        topics.append("ซอฟต์แวร์ออกแบบ 3 มิติ")
    if "ตัวอย่างปัญหา" in normalized or "ยกตัวอย่าง" in normalized:
        topics.append("ตัวอย่างปัญหา")

    if topics:
        return " ".join(dict.fromkeys(topics))

    words = [word for word in re.findall(r"[\wก-๙]+", normalized) if len(word) > 2]
    return " ".join(words[:10])


def expand_question_for_search(question: str) -> str:
    normalized = normalize_question_text(question)
    additions: list[str] = []
    question_type = detect_question_type(question)

    if question_type == "definition" and ("5w1h" in normalized):
        additions.extend(
            [
                "เทคนิค 5W1H",
                "Who คือใคร",
                "What คืออะไร",
                "When คือเมื่อไร",
                "Where คือที่ไหน",
                "Why คือทำไม",
                "How คืออย่างไร",
            ]
        )

    if question_type == "steps":
        additions.extend(["ขั้นตอน", "ได้แก่", "ประกอบด้วย"])
        if "กระบวนการออกแบบเชิงวิศวกรรม" in normalized:
            additions.extend(
                [
                    "กระบวนการออกแบบเชิงวิศวกรรม มี 6 ขั้นตอน",
                    "ขั้นระบุปัญหา",
                    "ขั้นรวบรวมข้อมูลและแนวคิดที่เกี่ยวข้องกับปัญหา",
                    "ขั้นออกแบบวิธีการแก้ปัญหา",
                    "ขั้นวางแผนและดำเนินการแก้ปัญหา",
                    "ขั้นทดสอบ ประเมินผล และปรับปรุงแก้ไขวิธีการแก้ปัญหาหรือชิ้นงาน",
                    "ขั้นนำเสนอวิธีการแก้ปัญหา ผลการแก้ปัญหาหรือชิ้นงาน",
                ]
            )

    if question_type == "purpose":
        additions.extend(["จุดมุ่งหมาย", "วัตถุประสงค์", "เป้าหมาย", "ช่วยให้", "เพื่อ"])
        if "กระบวนการออกแบบเชิงวิศวกรรม" in normalized:
            additions.extend(
                [
                    "กระบวนการออกแบบเชิงวิศวกรรม",
                    "แก้ปัญหาอย่างเป็นระบบ",
                    "ตอบสนองความต้องการ",
                    "พัฒนาวิธีการหรือชิ้นงาน",
                ]
            )

    if question_type == "reason":
        if re.search(r"(ทดสอบ|ประเมินผล)", normalized) and re.search(r"(ประโยชน์|นำไปใช้)", normalized):
            additions.extend([
                "ขั้นทดสอบ ประเมินผล และปรับปรุงแก้ไขวิธีการแก้ปัญหาหรือชิ้นงาน",
                "ปรับปรุงแก้ไขข้อบกพร่อง",
                "ผลการทดสอบ",
            ])
        if re.search(r"(วางแผน|ลงมือสร้าง|ชิ้นงาน)", normalized) and re.search(r"(เหตุใด|ทำไม|จำเป็น)", normalized):
            additions.extend([
                "วางแผนที่ดีจะช่วยให้ทำงานได้อย่างรวดเร็ว",
                "เตรียมทรัพยากร",
                "ขั้นวางแผนและดำเนินการแก้ปัญหา",
            ])

    return " ".join([normalized, *additions]).strip()


def overlap_score(question_terms: set[str], chunk_text: str) -> float:
    if not question_terms:
        return 0.0
    lowered = normalize_question_text(chunk_text)
    matched = 0
    for term in question_terms:
        if term in lowered:
            matched += 1
    if matched == 0:
        return -0.08
    return min(0.18, matched * 0.035)


def extract_domain_keywords(text: str) -> set[str]:
    lowered = text.lower()
    keyword_map = {
        "กระบวนการออกแบบเชิงวิศวกรรม": ["กระบวนการออกแบบเชิงวิศวกรรม", "engineering design"],
        "5w1h": ["5w1h"],
        "จุดมุ่งหมาย": ["จุดมุ่งหมาย", "วัตถุประสงค์", "เป้าหมาย", "เพื่ออะไร", "มีไว้เพื่อ"],
        "ขั้นตอน": ["ขั้นตอน", "กี่ขั้นตอน", "อะไรบ้าง"],
        "ระบุปัญหา": ["ระบุปัญหา"],
        "รวบรวมข้อมูล": ["รวบรวมข้อมูล"],
        "ออกแบบวิธีการแก้ปัญหา": ["ออกแบบวิธีการแก้ปัญหา"],
        "ทดสอบ": ["ทดสอบ", "ประเมินผล"],
        "นำเสนอ": ["นำเสนอ"],
    }

    keywords: set[str] = set()
    for keyword, markers in keyword_map.items():
        if any(marker in lowered for marker in markers):
            keywords.add(keyword)
    return keywords
