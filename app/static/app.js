/* ══════════════════════════════════════════════
   🎨 CARTOON SVG AVATARS & ICONS
   ══════════════════════════════════════════════ */

/* หุ่นยนต์น้อยน่ารัก — ผู้ช่วยสอน */
const SVG_ROBOT = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="22" height="22" aria-hidden="true" style="vertical-align:middle;margin-right:5px;flex-shrink:0">
  <!-- เสาอากาศ -->
  <line x1="14" y1="1.5" x2="14" y2="5.5" stroke="#93c5fd" stroke-width="2" stroke-linecap="round"/>
  <circle cx="14" cy="1.2" r="1.8" fill="#60a5fa"/>
  <!-- หัว -->
  <rect x="4" y="5.5" width="20" height="14" rx="5" fill="#dbeafe" stroke="#93c5fd" stroke-width="1.5"/>
  <!-- ตา -->
  <circle cx="10" cy="12" r="2.6" fill="#3b82f6"/>
  <circle cx="18" cy="12" r="2.6" fill="#3b82f6"/>
  <circle cx="10.9" cy="11.1" r="1" fill="white"/>
  <circle cx="18.9" cy="11.1" r="1" fill="white"/>
  <!-- ปาก -->
  <path d="M10 15.5 Q14 18.5 18 15.5" stroke="#60a5fa" stroke-width="1.8" stroke-linecap="round" fill="none"/>
  <!-- หู -->
  <rect x="1" y="9" width="3" height="5.5" rx="1.5" fill="#bfdbfe"/>
  <rect x="24" y="9" width="3" height="5.5" rx="1.5" fill="#bfdbfe"/>
</svg>`;

/* นักเรียนน่ารัก ใส่หมวกวิทยา */
const SVG_STUDENT = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 28" width="22" height="22" aria-hidden="true" style="vertical-align:middle;margin-right:5px;flex-shrink:0">
  <!-- หน้า -->
  <circle cx="14" cy="16" r="8" fill="#fde68a"/>
  <!-- ผม -->
  <path d="M6 13.5 Q6 7 14 7 Q22 7 22 13.5" fill="#92400e"/>
  <!-- หมวกวิทยา แผง -->
  <polygon points="14,5 23,9.5 14,14 5,9.5" fill="#1d4ed8"/>
  <!-- เชือกหมวก -->
  <line x1="23" y1="9.5" x2="24.5" y2="13.5" stroke="#1d4ed8" stroke-width="1.5" stroke-linecap="round"/>
  <circle cx="24.5" cy="14.3" r="1.4" fill="#fbbf24"/>
  <!-- ตา -->
  <ellipse cx="10.5" cy="16" rx="1.4" ry="1.7" fill="#1e293b"/>
  <ellipse cx="17.5" cy="16" rx="1.4" ry="1.7" fill="#1e293b"/>
  <circle cx="11.1" cy="15.2" r="0.5" fill="white"/>
  <circle cx="18.1" cy="15.2" r="0.5" fill="white"/>
  <!-- แก้มแดง -->
  <ellipse cx="8.5" cy="18" rx="1.8" ry="1" fill="#fca5a5" opacity="0.7"/>
  <ellipse cx="19.5" cy="18" rx="1.8" ry="1" fill="#fca5a5" opacity="0.7"/>
  <!-- ยิ้ม -->
  <path d="M10.5 19.5 Q14 22.5 17.5 19.5" stroke="#d97706" stroke-width="1.5" stroke-linecap="round" fill="none"/>
</svg>`;

/* จรวดน่ารัก — ปุ่มส่งคำถาม */
const SVG_ROCKET = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" style="vertical-align:middle;margin-right:5px;flex-shrink:0">
  <!-- ลำตัว -->
  <path d="M10 1.5 C13.5 3 15.5 7.5 15.5 12.5 L10 15.5 L4.5 12.5 C4.5 7.5 6.5 3 10 1.5 Z" fill="rgba(255,255,255,0.95)"/>
  <!-- หน้าต่าง -->
  <circle cx="10" cy="9" r="2.3" fill="#bfdbfe" stroke="rgba(255,255,255,0.9)" stroke-width="0.8"/>
  <!-- เปลวไฟ -->
  <path d="M7.5 13.5 Q6 16.5 4.5 18.5 Q7.5 16.5 10 17 Q12.5 16.5 15.5 18.5 Q14 16.5 12.5 13.5" fill="#fbbf24" opacity="0.95"/>
  <!-- ครีบ -->
  <path d="M4.5 12.5 L2 16 L5.5 13.5 Z" fill="rgba(255,255,255,0.85)"/>
  <path d="M15.5 12.5 L18 16 L14.5 13.5 Z" fill="rgba(255,255,255,0.85)"/>
  <!-- ดาว -->
  <circle cx="16" cy="4" r="0.8" fill="rgba(255,255,255,0.8)"/>
  <circle cx="4.5" cy="6" r="0.6" fill="rgba(255,255,255,0.7)"/>
</svg>`;

/* ดินสอน่ารัก — label ช่องพิมพ์ */
const SVG_PENCIL = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" style="vertical-align:middle;margin-right:4px;flex-shrink:0">
  <!-- ลบยาง -->
  <rect x="2.5" y="1.5" width="3" height="2.5" rx="0.8" fill="#fca5a5" stroke="#f87171" stroke-width="0.6" transform="rotate(-45 4 2.8)"/>
  <!-- ตัวดินสอ -->
  <rect x="3" y="3" width="10" height="3.5" rx="1" fill="#fbbf24" stroke="#f59e0b" stroke-width="0.7" transform="rotate(-45 8 4.75)"/>
  <!-- ปลาย -->
  <path d="M11.5 11.5 L13.8 9.2 L14.8 10.2 L12.5 12.5 Z" fill="#fde68a" stroke="#f59e0b" stroke-width="0.5"/>
  <!-- ไส้ -->
  <path d="M13.1 9.9 L14.1 10.9 L14.6 14.6 Z" fill="#1e293b"/>
</svg>`;

/* หนังสือน่ารัก — subtitle */
const SVG_BOOK = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18" width="16" height="16" aria-hidden="true" style="vertical-align:middle;margin-right:3px;flex-shrink:0">
  <!-- ปกหลัง -->
  <rect x="2" y="2" width="14" height="14" rx="2.5" fill="#93c5fd"/>
  <!-- กระดาษ -->
  <rect x="3.5" y="3" width="11" height="12" rx="1.5" fill="#eff6ff"/>
  <!-- สันหนังสือ -->
  <rect x="2" y="2" width="3" height="14" rx="1.5" fill="#3b82f6"/>
  <!-- เส้นข้อความ -->
  <line x1="7" y1="6.5" x2="13" y2="6.5" stroke="#bfdbfe" stroke-width="1.2" stroke-linecap="round"/>
  <line x1="7" y1="9" x2="13" y2="9" stroke="#bfdbfe" stroke-width="1.2" stroke-linecap="round"/>
  <line x1="7" y1="11.5" x2="11" y2="11.5" stroke="#bfdbfe" stroke-width="1.2" stroke-linecap="round"/>
  <!-- ดาวตกแต่ง -->
  <circle cx="14.5" cy="3.5" r="0.7" fill="#fbbf24"/>
</svg>`;

/* หมวกวิทยา — subtitle */
const SVG_CAP = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18" width="16" height="16" aria-hidden="true" style="vertical-align:middle;margin-left:3px;flex-shrink:0">
  <!-- แผงหมวก -->
  <polygon points="9,4 17,8 9,12 1,8" fill="#1d4ed8"/>
  <!-- เชือก -->
  <line x1="17" y1="8" x2="18" y2="12" stroke="#1d4ed8" stroke-width="1.5" stroke-linecap="round"/>
  <circle cx="18" cy="12.8" r="1.5" fill="#fbbf24"/>
  <!-- ขาตั้ง -->
  <path d="M4 9.5 L4 14 Q9 16.5 14 14 L14 9.5" fill="none" stroke="#1d4ed8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

/* ประกายแสง — title */
const SVG_SPARKLE = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18" width="18" height="18" aria-hidden="true" style="vertical-align:middle;margin-right:5px;flex-shrink:0">
  <path d="M9 1 L10.2 7.2 L16 9 L10.2 10.8 L9 17 L7.8 10.8 L2 9 L7.8 7.2 Z" fill="#fbbf24"/>
  <circle cx="15" cy="3" r="1" fill="#fbbf24" opacity="0.7"/>
  <circle cx="3" cy="14" r="0.7" fill="#60a5fa" opacity="0.8"/>
</svg>`;

/* เช็ค — alert */
const SVG_CHECK = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18" width="16" height="16" aria-hidden="true" style="vertical-align:middle;margin-right:4px;flex-shrink:0">
  <circle cx="9" cy="9" r="8" fill="rgba(255,255,255,0.3)" stroke="rgba(255,255,255,0.7)" stroke-width="1.2"/>
  <path d="M5 9.5 L7.5 12 L13 6.5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>`;

/* ══════════════════════════════════════════════
   REFS
   ══════════════════════════════════════════════ */
const messages      = document.getElementById("messages");
const chatForm      = document.getElementById("chat-form");
const questionInput = document.getElementById("question");
const healthNode    = document.getElementById("health");
const documentsNode = document.getElementById("documents");
const docCountNode  = document.getElementById("doc-count");
const submitButton  = document.querySelector(".composer-actions button");

const history = [];
const DEFAULT_ERROR_MESSAGE = "ขออภัย ขณะนี้ระบบยังประมวลผลคำขอไม่สำเร็จ กรุณาลองใหม่อีกครั้ง";

/* ── typing indicator ───────────────────────────── */
function showTyping() {
  const wrap = document.createElement("article");
  wrap.className = "message assistant";
  wrap.id = "typing-indicator-wrap";

  const role = document.createElement("div");
  role.className = "message-role";
  role.innerHTML = `${SVG_ROBOT} ผู้ช่วยสอน`;

  const indicator = document.createElement("div");
  indicator.className = "typing-indicator";
  indicator.innerHTML = `<span class="typing-text">กำลังหาคำตอบ</span><span class="typing-dots"><span></span><span></span><span></span></span>`;

  wrap.append(role, indicator);
  messages.appendChild(wrap);
  messages.scrollTo({ top: messages.scrollHeight, behavior: "smooth" });
}

function hideTyping() {
  const el = document.getElementById("typing-indicator-wrap");
  if (el) el.remove();
}

/* ── append a message bubble ────────────────────── */
function appendMessage(role, text, citations = [], options = {}) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  if (options.tone) article.classList.add(options.tone);

  /* role label */
  const roleNode = document.createElement("div");
  roleNode.className = "message-role";

  if (role === "user") {
    roleNode.innerHTML = `${SVG_STUDENT} นักเรียน`;
  } else {
    roleNode.innerHTML = `${SVG_ROBOT} ผู้ช่วยสอน`;
    if (options.statusLabel) {
      const badge = document.createElement("span");
      badge.className = `message-badge ${options.grounded ? "grounded" : "ungrounded"}`;
      badge.textContent = options.grounded ? "✅ ตอบจากเอกสาร" : "⚠️ ข้อมูลไม่เพียงพอ";
      roleNode.appendChild(document.createTextNode(" "));
      roleNode.appendChild(badge);
    }
  }

  /* bubble */
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");

  article.append(roleNode, bubble);

  /* citations */
  if (citations.length) {
    const citationsNode = document.createElement("div");
    citationsNode.className = "citations";

    const label = document.createElement("div");
    label.className = "citations-label";
    label.textContent = "📎 แหล่งอ้างอิง";
    citationsNode.appendChild(label);

    for (const citation of citations) {
      const item = document.createElement("div");
      item.className = "citation";

      const badge = document.createElement("span");
      badge.className = "cite-badge";
      badge.textContent = `[${citation.id}]`;

      const meta = document.createElement("span");
      meta.className = "cite-meta";
      meta.textContent = `📄 ${citation.source}  •  ${citation.section}`;

      const excerpt = document.createElement("p");
      excerpt.className = "cite-excerpt";
      excerpt.textContent = citation.excerpt;

      item.append(badge, meta, excerpt);
      citationsNode.appendChild(item);
    }

    article.appendChild(citationsNode);
  }

  messages.appendChild(article);
  messages.scrollTo({ top: messages.scrollHeight, behavior: "smooth" });
}

/* ── escape HTML ─────────────────────────────────── */
function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ── health / status ─────────────────────────────── */
async function loadHealth() {
  try {
    const response = await fetch("/health");
    const data = await response.json();
    const modeLabel = data.backend === "ollama" ? "โหมด AI (Ollama)" : "โหมดอ้างอิงเอกสาร";
    if (healthNode) healthNode.textContent = `${modeLabel} • พร้อมใช้งาน`;
  } catch {
    if (healthNode) healthNode.textContent = "ไม่สามารถเชื่อมต่อได้";
    const dot = document.querySelector(".chat-status-dot");
    if (dot) dot.style.background = "#f87171";
  }
}

/* ── documents list ──────────────────────────────── */
async function loadDocuments() {
  try {
    const response = await fetch("/documents");
    const data = await response.json();
    if (documentsNode) documentsNode.innerHTML = "";

    if (!data.length) {
      if (docCountNode) docCountNode.textContent = "ยังไม่มีเอกสาร";
      return;
    }

    // แสดงสรุปใน header
    const totalChunks = data.reduce((sum, d) => sum + d.chunks, 0);
    if (docCountNode) docCountNode.textContent = `${data.length} เอกสาร • ${totalChunks} ส่วน`;

    // เก็บข้อมูลใน hidden list
    for (const doc of data) {
      if (!documentsNode) continue;
      const item = document.createElement("li");
      item.textContent = `${doc.source} • ${doc.chunks} ส่วน`;
      documentsNode.appendChild(item);
    }
  } catch {
    if (docCountNode) docCountNode.textContent = "โหลดไม่สำเร็จ";
  }
}

/* ── quick chip handler ─────────────────────────── */
document.querySelectorAll(".chip[data-q]").forEach(chip => {
  chip.addEventListener("click", () => {
    questionInput.value = chip.dataset.q;
    questionInput.focus();
    document.querySelector(".chat-shell").scrollIntoView({ behavior: "smooth" });
  });
});

/* ── submit handler ──────────────────────────────── */
chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  if (question.length < 3) {
    appendMessage("user", question);
    questionInput.value = "";
    appendMessage("assistant", "กรุณาพิมพ์คำถามให้ยาวขึ้นอีกนิด (อย่างน้อย 3 ตัวอักษร) นะคะ", [], {
      grounded: false,
      statusLabel: true,
      tone: "system-note",
    });
    return;
  }

  appendMessage("user", question);
  history.push({ role: "user", content: question });
  questionInput.value = "";
  questionInput.disabled = true;
  submitButton.disabled = true;

  showTyping();
  const typingStart = Date.now();
  const MIN_TYPING_MS = 1000;

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
    });

    const data = await response.json();
    if (!response.ok) {
      let detailMsg = "คำขอล้มเหลว";
      if (typeof data.detail === "string") {
        detailMsg = data.detail;
      } else if (Array.isArray(data.detail)) {
        detailMsg = data.detail.map(d => d.msg || JSON.stringify(d)).join(", ");
      } else if (data.detail) {
        detailMsg = JSON.stringify(data.detail);
      }
      throw new Error(detailMsg);
    }

    const elapsed = Date.now() - typingStart;
    if (elapsed < MIN_TYPING_MS) {
      await new Promise(resolve => setTimeout(resolve, MIN_TYPING_MS - elapsed));
    }

    hideTyping();
    appendMessage("assistant", data.answer, data.citations || [], {
      grounded: Boolean(data.grounded),
      statusLabel: true,
    });
    history.push({ role: "assistant", content: data.answer });

  } catch (error) {
    const elapsed = Date.now() - typingStart;
    if (elapsed < MIN_TYPING_MS) {
      await new Promise(resolve => setTimeout(resolve, MIN_TYPING_MS - elapsed));
    }
    hideTyping();
    const detail = error?.message || DEFAULT_ERROR_MESSAGE;
    appendMessage("assistant", `ขออภัย ระบบพบปัญหา: ${detail}`, [], {
      grounded: false,
      statusLabel: true,
      tone: "system-note",
    });
  } finally {
    questionInput.disabled = false;
    submitButton.disabled = false;
    questionInput.focus();
  }
});

loadHealth();
loadDocuments();
