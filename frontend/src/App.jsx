import { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";

const API_BASE =
  import.meta.env.VITE_API_BASE || "http://localhost:8000";
; // change if your backend URL is different

function App() {
  const [view, setView] = useState("landing"); // "landing" | "chat"
  const [file, setFile] = useState(null);
  const [uploadedFileName, setUploadedFileName] = useState("");
  const [fileId, setFileId] = useState("");
  const [chat, setChat] = useState([]); // { role: "user" | "assistant", text: string }[]
  const [input, setInput] = useState("");
  const [loadingUpload, setLoadingUpload] = useState(false);
  const [loadingReply, setLoadingReply] = useState(false);
  const [error, setError] = useState("");

  // theme: "dark" | "light"
  const [theme, setTheme] = useState("dark");

  // structured analysis from backend
  const [analysis, setAnalysis] = useState(null);

  const messagesEndRef = useRef(null);

  // Auto-scroll chat to TOP
// Auto-scroll chat to BOTTOM (inside messages area only)
useEffect(() => {
  const el = document.querySelector(".messages-scroll");
  if (el) {
    el.scrollTop = el.scrollHeight;   // ⬅️ go to bottom
  }
}, [chat]);

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0];
    if (!selected) return;
    if (selected.type !== "application/pdf") {
      setError("Please upload a PDF resume.");
      return;
    }
    setError("");
    setFile(selected);
    setUploadedFileName(selected.name);
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoadingUpload(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await axios.post(`${API_BASE}/upload_resume`, formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      // backend returns: file_id, greeting, analysis
      const { file_id, greeting, analysis: rawAnalysis } = res.data || {};

      if (!file_id) {
        setError("Upload succeeded but no file_id returned. Check backend.");
        setLoadingUpload(false);
        return;
      }

      setFileId(file_id);

      // first assistant message
      const firstMessage =
        greeting ||
        "I’ve analyzed your resume – ask me anything about STAR stories, interviews, or projects.";

      setChat([
        {
          role: "assistant",
          text: firstMessage,
        },
      ]);

      // normalize analysis so frontend is safe if some fields are missing
      const normalizedAnalysis = rawAnalysis
        ? {
            overallScore: rawAnalysis.overall_score ?? null,
            scoreLabel: rawAnalysis.score_label || "",
            topSkills: rawAnalysis.top_skills || [],
            roleFit: rawAnalysis.role_fit || [],
            experienceLevel: rawAnalysis.experience_level || "",
            yearsExperience: rawAnalysis.years_experience ?? null,
            projectCount: rawAnalysis.project_count ?? null,
            companiesCount: rawAnalysis.companies_count ?? null,
            gaps: rawAnalysis.gaps || [],
            quickWins: rawAnalysis.quick_wins || [],
          }
        : null;

      setAnalysis(normalizedAnalysis);

      // move to chat view after successful upload
      setView("chat");
    } catch (err) {
      console.error(err);
      setError("Upload failed. Make sure backend is running on 127.0.0.1:8000.");
    } finally {
      setLoadingUpload(false);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || !fileId || loadingReply) return;

    const userText = input.trim();
    setInput("");
    setError("");

    setChat((prev) => [...prev, { role: "user", text: userText }]);
    setLoadingReply(true);

    try {
      const res = await axios.post(`${API_BASE}/chat`, {
        user_message: userText,
        file_id: fileId,
      });

      const { response } = res.data;

      setChat((prev) => [
        ...prev,
        { role: "assistant", text: response || "No response received from coach." },
      ]);
    } catch (err) {
      console.error(err);
      setError("Something went wrong while getting a reply. Check backend logs.");
      setChat((prev) => [
        ...prev,
        {
          role: "assistant",
          text: "I had trouble reaching the server. Please try again.",
        },
      ]);
    } finally {
      setLoadingReply(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ---------- LANDING VIEW ----------

  if (view === "landing") {
    return (
      <div className={`app app-landing ${theme}`}>
        <div className="landing-card fade-in-up">
          <div className="landing-badge">RAG · Resume Insights & Interview Coach</div>

          <h1 className="landing-title">
            <span className="landing-title-main">RAG</span>
            <span className="landing-title-sub">narok</span>
          </h1>

          <p className="landing-subtitle">
            Reforge your resume into insights and unforgettable stories.
          </p>

          <p className="landing-explainer">
          Upload your resume as a PDF and get insights plus a personal interview coach trained only on your experience and projects.
          </p>

          <div className="landing-upload-area">
            <label className="file-input">
              <input
                type="file"
                accept="application/pdf"
                onChange={handleFileChange}
              />
              <span>{file ? file.name : "Upload your resume (PDF)"}</span>
            </label>

            <button
              className="primary-btn"
              onClick={handleUpload}
              disabled={loadingUpload || !file}
            >
              {loadingUpload ? "Analyzing…" : "Analyze resume"}
            </button>
          </div>

          

          {error && <div className="error-text">{error}</div>}

          <p className="made-by">
            made by <span style={{ textTransform: "none" }}>Rishabh Parakh</span>
          </p>
        </div>
      </div>
    );
  }

  // Helper: safe analysis access
  const a = analysis || {};

  // sort and take top 3 roles by score
  const topRoleFit =
    Array.isArray(a.roleFit)
      ? [...a.roleFit]
          .sort((r1, r2) => (r2.score ?? 0) - (r1.score ?? 0))
          .slice(0, 3)
      : [];

  //--------------------------------------------------------------------------------------------------------
  // CHAT VIEW
  return (
    <div className={`app app-chat ${theme}`}>
      <header className="chat-header">
        <div className="chat-header-left">
          <div className="logo-circle">R</div>
          <div>
            <div className="header-title">Resume Coach</div>
            <div className="header-subtitle">
              Personalized interview prep from your own resume.
            </div>
          </div>
        </div>

        <div className="chat-header-right">
          {/* Theme toggle switch with sun / moon */}
          <div className="theme-toggle">
            <label className="switch">
              <input
                type="checkbox"
                checked={theme === "light"}
                onChange={() =>
                  setTheme((prev) => (prev === "dark" ? "light" : "dark"))
                }
              />
              <span className="slider" />
            </label>
          </div>

          <button
            className="ghost-btn header-back-btn"
            onClick={() => {
              setView("landing");
              setChat([]);
              setFileId("");
              setFile(null);
              setUploadedFileName("");
              setAnalysis(null);
              setError("");
            }}
          >
            ← Upload another resume
          </button>
        </div>
      </header>

      <main className="chat-main">
        <div className="chat-layout">
          {/* Left: Chat */}
          <section className="messages-area">
            <div className="messages-scroll">
              {chat.map((m, idx) => (
                <div
                  key={idx}
                  className={`message-bubble ${
                    m.role === "user" ? "message-user" : "message-assistant"
                  }`}
                >
                  <div className="message-role">
                    {m.role === "user" ? "You" : "Coach"}
                  </div>
                  <div className="message-text">
  <ReactMarkdown rehypePlugins={[rehypeRaw]}>
    {m.text}
  </ReactMarkdown>
</div>

                </div>
              ))}
              {loadingReply && (
                <div className="message-bubble message-assistant typing-bubble">
                  <div className="message-role">Coach</div>
                  <div className="typing-dots">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </section>

          {/* Right: Analysis Sidebar */}
          <aside className="chat-sidebar">
            {/* --- CARD 1: PROFILE SCORE --- */}
            <div className="sidebar-card">
              <div className="sidebar-label">Profile Score</div>

              <div className="score-row">
                <div className="score-circle">
                  <span className="score-main">
                    {a.overallScore != null ? a.overallScore : "--"}
                  </span>
                  <span className="score-out-of">/ 100</span>
                </div>

                <div className="score-details">
                  <div className="score-label">
                    {a.scoreLabel || "Upload a resume to see your score."}
                  </div>

                  {a.overallScore != null && (
                    <div className="score-bar">
                      <div
                        className="score-bar-fill"
                        style={{ width: `${Math.min(a.overallScore, 100)}%` }}
                      />
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* --- CARD 2: TOP 3 BEST FIT ROLES --- */}
            <div className="sidebar-card">
              <div className="sidebar-label">Top Best-Fit Roles</div>

              {topRoleFit && topRoleFit.length > 0 ? (
                <div className="rolefit-block">
                  {topRoleFit.slice(0, 3).map((r) => {
                    const val =
                      typeof r.score === "number"
                        ? Math.round(Math.min(Math.max(r.score, 0), 1) * 100)
                        : null;

                    return (
                      <div className="mini-bar-row" key={r.role}>
                        <span className="mini-bar-label">{r.role}</span>
                        <div className="mini-bar-track">
                          <div
                            className="mini-bar-fill"
                            style={{ width: val != null ? `${val}%` : "0%" }}
                          />
                        </div>
                        <span className="mini-bar-value">
                          {val != null ? `${val}%` : "--"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state">
                  Upload a resume to see best-fit roles.
                </div>
              )}
            </div>

            {/* Top strengths (skills chips only) */}
            <div className="sidebar-card">
              <div className="sidebar-label">Top Skills</div>
              <div className="skills-wrap">
                {Array.isArray(a.topSkills) && a.topSkills.length > 0 ? (
                  a.topSkills.slice(0, 8).map((skill) => (
                    <span className="skill-pill" key={skill}>
                      {skill}
                    </span>
                  ))
                ) : (
                  <span className="skill-pill skill-pill-muted">
                    Upload a resume to see skills.
                  </span>
                )}
              </div>
            </div>

            {/* Gaps & risks */}
            <div className="sidebar-card">
              <div className="sidebar-label">Gaps & risks</div>
              {Array.isArray(a.gaps) && a.gaps.length > 0 ? (
                <ul className="sidebar-list">
                  {a.gaps.slice(0, 4).map((gap, idx) => (
                    <li key={idx}>{gap}</li>
                  ))}
                </ul>
              ) : (
                <p className="sidebar-body">
                  I’ll highlight missing metrics, weak stories, or noisy sections
                  once I analyze a resume.
                </p>
              )}
            </div>

            {/* Quick wins */}
            {Array.isArray(a.quickWins) && a.quickWins.length > 0 && (
              <div className="sidebar-card">
                <div className="sidebar-label">Quick Fixes</div>
                <ul className="sidebar-list">
                  {a.quickWins.slice(0, 4).map((q, idx) => (
                    <li key={idx}>{q}</li>
                  ))}
                </ul>
              </div>
            )}
          </aside>
        </div>

        {/* Input bar */}
        <footer className="chat-input-bar">
          <textarea
            className="chat-textarea"
            placeholder={
              fileId
                ? "Ask about STAR stories, project explanations, or mock interview questions…"
                : "Upload a resume on the landing page first."
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={!fileId || loadingReply}
          />
          <button
            className="primary-btn send-btn"
            onClick={sendMessage}
            disabled={!fileId || !input.trim() || loadingReply}
          >
            {loadingReply ? "Thinking…" : "Send"}
          </button>
        </footer>

        {error && <div className="error-banner">{error}</div>}
      </main>
    </div>
  );
}

export default App;
