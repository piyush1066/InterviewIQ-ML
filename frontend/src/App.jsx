
import { useEffect, useRef, useState } from "react";
import {
  FileText,
  MessageSquareText,
  Sparkles,
  LoaderCircle,
  Upload,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  CheckCircle2,
  ClipboardList,
  BriefcaseBusiness,
  Download,
} from "lucide-react";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8011";

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error(`Cannot reach the local backend at ${API_BASE_URL}. Start it on port 8011 or set VITE_API_BASE_URL.`);
  }
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      response.status === 404
        ? `Backend route ${path} was not found at ${API_BASE_URL}. Check VITE_API_BASE_URL and restart the frontend.`
        :
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg).join("; ")
        : "Request failed. Check your inputs and backend."
    );
  }

  return data;
}

export default function App() {
  const [activeTab, setActiveTab] = useState("resume");
  const [file, setFile] = useState(null);
  const [resumeData, setResumeData] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [evaluations, setEvaluations] = useState({});
  const [jobDescription, setJobDescription] = useState("");
  const [matchResult, setMatchResult] = useState(null);
  const [questionCount, setQuestionCount] = useState(10);
  const [manualQuestion, setManualQuestion] = useState("");
  const [manualAnswer, setManualAnswer] = useState("");
  const [referenceAnswer, setReferenceAnswer] = useState("");
  const [manualResult, setManualResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [serviceStatus, setServiceStatus] = useState("checking");
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    let active = true;
    apiRequest("/health")
      .then(() => active && setServiceStatus("online"))
      .catch(() => active && setServiceStatus("offline"));
    return () => { active = false; };
  }, []);

  const currentQuestion = questions[currentIndex];
  const completedCount = Object.keys(evaluations).length;
  const submittedCount = Object.values(answers).filter((answer) => answer.trim()).length;
  const averageScore = completedCount
    ? (
        Object.values(evaluations).reduce(
          (total, item) => total + item.score,
          0
        ) / completedCount
      ).toFixed(1)
    : "0.0";
  const averageSignal = (name) => completedCount
    ? Object.values(evaluations).reduce((total, item) => total + (item.signals?.[name] || 0), 0) / completedCount
    : 0;
  const strongAreas = completedCount ? [
    averageSignal("question_term_coverage") >= 0.35 && "Your answers often include relevant terms from the questions.",
    averageSignal("word_count_normalized") >= 0.25 && "Your responses usually include enough detail to explain your approach.",
    averageSignal("has_example_signal") >= 0.5 && "You regularly support explanations with examples.",
    averageSignal("has_reasoning_signal") >= 0.5 && "You often explain your reasoning or cause and effect.",
  ].filter(Boolean) : [];
  const improvementAreas = completedCount ? [
    averageSignal("question_term_coverage") < 0.35 && "Start with a direct answer and name the concepts the question asks about.",
    averageSignal("word_count_normalized") < 0.25 && "Add a short explanation of your approach and a specific example where useful.",
    questions.some((question) => question.reference_answer) && averageSignal("reference_similarity") < 0.2 && "Review answers with low reference-text overlap against trusted technical sources; overlap does not prove correctness.",
    !questions.some((question) => question.reference_answer) && "Generated questions have no reference answers; verify technical details with trusted documentation.",
  ].filter(Boolean) : [];
  function changeTab(tab) {
    setActiveTab(tab);
    setError("");
  }

  async function processResume(selectedFile) {
    if (!selectedFile) {
      setError("Choose a PDF resume or use the fictional sample.");
      return;
    }
    if (!selectedFile.name.toLowerCase().endsWith(".pdf")) {
      setError("This file is not a PDF. Choose a .pdf resume.");
      return;
    }
    if (selectedFile.size > 5 * 1024 * 1024) {
      setError("This PDF exceeds the 5 MB upload limit.");
      return;
    }
    if (selectedFile.size === 0) {
      setError("This PDF is empty. Choose another file.");
      return;
    }

    setFile(selectedFile);
    setLoading(true);
    setError("");
    setResumeData(null);
    setQuestions([]);
    setAnswers({});
    setEvaluations({});
    setMatchResult(null);
    setCurrentIndex(0);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const data = await apiRequest("/resume/upload", {
        method: "POST",
        body: formData,
      });

      setResumeData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function uploadResume(event) {
    event.preventDefault();
    return processResume(file);
  }

  async function useSampleResume() {
    setError("");
    try {
      const response = await fetch("/sample-resume.pdf");
      if (!response.ok) throw new Error("The bundled sample PDF is missing from frontend/public.");
      const sample = new File([await response.blob()], "InterviewIQ-fictional-sample-resume.pdf", { type: "application/pdf" });
      await processResume(sample);
    } catch (err) {
      setError(err.message || "Could not load the bundled sample PDF.");
    }
  }

  function removeResume() {
    setFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setResumeData(null);
    setQuestions([]);
    setAnswers({});
    setEvaluations({});
    setMatchResult(null);
    setError("");
  }

  async function generateInterview() {
    if (!resumeData?.resume_text) {
      setError("Upload your resume before generating questions.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await apiRequest("/interview/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_text: resumeData.resume_text,
          number_of_questions: Number(questionCount),
        }),
      });

      setQuestions(data.questions || []);
      setCurrentIndex(0);
      setAnswers({});
      setEvaluations({});
      setActiveTab("interview");

      if (!data.questions?.length) {
        setError("No questions could be generated from this resume.");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function evaluateCurrentAnswer() {
    if (!currentQuestion) return;

    const candidateAnswer = (answers[currentQuestion.id] || "").trim();

    if (!candidateAnswer) {
      setError("Write your answer before submitting it.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await apiRequest("/answer/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: currentQuestion.question,
          topic: currentQuestion.topic || "",
          candidate_answer: candidateAnswer,
          reference_answer: currentQuestion.reference_answer || "",
        }),
      });

      setEvaluations((previous) => ({
        ...previous,
        [currentQuestion.id]: data,
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function evaluateManualAnswer(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setManualResult(null);

    try {
      const data = await apiRequest("/answer/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: manualQuestion,
          candidate_answer: manualAnswer,
          reference_answer: referenceAnswer,
        }),
      });

      setManualResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function matchResume(event) {
    event.preventDefault();

    if (!resumeData?.resume_text) {
      setError("Upload your resume before matching it to a role.");
      return;
    }

    setLoading(true);
    setError("");
    setMatchResult(null);

    try {
      const data = await apiRequest("/resume/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_text: resumeData.resume_text,
          job_description: jobDescription,
        }),
      });

      setMatchResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function resetInterview() {
    setQuestions([]);
    setAnswers({});
    setEvaluations({});
    setCurrentIndex(0);
    setError("");
    setActiveTab("resume");
  }

  function exportReport() {
    const report = {
      generated_questions: questions.length,
      submitted_answers: submittedCount,
      evaluated_answers: completedCount,
      average_score: averageScore,
      strong_areas: strongAreas,
      improvement_areas: improvementAreas,
      results: questions.map((question) => ({
        id: question.id,
        category: question.category,
        topic: question.topic,
        question: question.question,
        answer: answers[question.id] || "",
        evaluation: evaluations[question.id] || null,
      })),
      limitations: "Experimental local text-based evaluation. Does not establish technical correctness or hiring suitability.",
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "interviewiq-report.json";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Sparkles size={21} />
          </div>
          <div>
            <strong>InterviewIQ</strong>
            <span>ML WORKSPACE</span>
          </div>
        </div>

        <p className="nav-label">WORKSPACE</p>

        <button
          className={`nav-item ${activeTab === "resume" ? "active" : ""}`}
          onClick={() => changeTab("resume")}
        >
          <FileText size={18} /> Resume Studio
        </button>

        <button
          className={`nav-item ${activeTab === "interview" ? "active" : ""}`}
          onClick={() => changeTab("interview")}
          disabled={!questions.length}
        >
          <ClipboardList size={18} /> Mock Interview
        </button>

        <button
          className={`nav-item ${activeTab === "answer" ? "active" : ""}`}
          onClick={() => changeTab("answer")}
        >
          <MessageSquareText size={18} /> Answer Evaluator
        </button>
        <button className={`nav-item ${activeTab === "match" ? "active" : ""}`} onClick={() => changeTab("match")} disabled={!resumeData}>
          <BriefcaseBusiness size={18} /> Resume Match
        </button>
        <button
          className={`nav-item ${activeTab === "report" ? "active" : ""}`}
          onClick={() => changeTab("report")}
          disabled={!questions.length}
        >
          <CheckCircle2 size={18} /> Final feedback
        </button>

        <div className="sidebar-footer">
          <span className={`status-dot ${serviceStatus}`} /> ML service {serviceStatus}
          <small>Resume and answers stay local</small>
        </div>
      </aside>

      <section className="main-content">
        <header className="topbar">
          <div>
            <span className="eyebrow">YOUR CAREER, BETTER PREPARED</span>
            <h1>Interview intelligence</h1>
          </div>
          <div className="api-status">
            <span className={`status-dot ${serviceStatus}`} /> ML service {serviceStatus}
          </div>
        </header>

        <section className="intro">
          <div>
            <span className="eyebrow">OFFLINE INTERVIEW PRACTICE</span>
            <h2>
              {activeTab === "resume"
                ? "Start with your resume."
                : activeTab === "interview"
                  ? "Your mock interview."
                  : activeTab === "match" ? "Explore your role match." : activeTab === "report" ? "Your interview results." : "Practice with purpose."}
            </h2>
            <p>
              {activeTab === "resume"
                ? "Upload a PDF, discover your skills, and build a personalized interview."
                : activeTab === "interview"
                  ? "Answer one question at a time and review your evaluation."
                  : activeTab === "match" ? "Compare your resume with a target job description using local text analysis." : activeTab === "report" ? "Review your scores and practical feedback from this session." : "Submit an answer to receive an experimental ML score and feedback."}
            </p>
          </div>
          <div className="intro-icon">
            <Sparkles size={30} />
          </div>
        </section>

        {error && (
          <div className="error-box">
            <strong>Something went wrong</strong>
            <p>{error}</p>
          </div>
        )}

        {activeTab === "resume" && (
          <div className="workspace-grid">
            <form className="panel form-panel" onSubmit={uploadResume}>
              <div className="panel-heading">
                <div>
                  <span className="step-number">01</span>
                  <h3>Upload your resume</h3>
                </div>
                <span className="required-label">PDF · MAX 5 MB</span>
              </div>

              <div className={`upload-zone ${dragActive ? "drag-active" : ""}`}
                onDragOver={(event) => { event.preventDefault(); setDragActive(true); }}
                onDragLeave={() => setDragActive(false)}
                onDrop={(event) => {
                  event.preventDefault(); setDragActive(false);
                  const dropped = event.dataTransfer.files?.[0];
                  if (dropped) { setFile(dropped); setResumeData(null); setQuestions([]); setAnswers({}); setEvaluations({}); setMatchResult(null); setCurrentIndex(0); setError(""); }
                }}>
                <label htmlFor="resumeFile">Choose PDF</label>
                <input
                  id="resumeFile"
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  onChange={(event) => {
                    const chosen = event.target.files?.[0] || null;
                    setFile(chosen); setResumeData(null); setQuestions([]); setAnswers({}); setEvaluations({}); setMatchResult(null); setCurrentIndex(0); setError("");
                  }}
                />
                <p>or drag a PDF here from any folder · maximum 5 MB</p>
              </div>

              {file && <div className="selected-file"><span><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(1)} KB · {resumeData ? "Uploaded and analyzed" : "Ready to upload"}</small></span><button type="button" className="text-button" onClick={removeResume}>Remove</button></div>}

              <button
                className="submit-button"
                type="submit"
                disabled={loading}
              >
                {loading ? (
                  <LoaderCircle className="spin" size={18} />
                ) : (
                  <Upload size={18} />
                )}
                {loading ? "Processing..." : "Analyze PDF resume"}
              </button>

              <button className="secondary-button" type="button" onClick={useSampleResume} disabled={loading}>
                {loading ? <LoaderCircle className="spin" size={17} /> : <FileText size={17} />}
                Use fictional sample PDF
              </button>

              <p className="privacy-note">
                Your resume is processed by the local backend.
              </p>

              {resumeData && (
                <div className="results">
                  <p>
                    <CheckCircle2 size={16} /> Resume processed successfully
                  </p>
                  <strong>{resumeData.filename}</strong>
                  <p>
                    {resumeData.resume_text?.length || 0} characters extracted
                  </p>
                  <details className="resume-preview">
                    <summary>Preview extracted text</summary>
                    <pre>{resumeData.resume_text}</pre>
                  </details>
                </div>
              )}

              <div className="divider-space" />

              <div className="panel-heading">
                <div>
                  <span className="step-number">02</span>
                  <h3>Build your interview</h3>
                </div>
              </div>

              <label htmlFor="questionCount">Number of questions</label>
              <select
                id="questionCount"
                value={questionCount}
                onChange={(event) => setQuestionCount(event.target.value)}
              >
                {[5, 10, 15, 20, 30].map((count) => (
                  <option key={count} value={count}>
                    {count} questions
                  </option>
                ))}
              </select>

              <button
                className="submit-button"
                type="button"
                onClick={generateInterview}
                disabled={loading || !resumeData}
              >
                {loading ? (
                  <LoaderCircle className="spin" size={18} />
                ) : (
                  <Sparkles size={18} />
                )}
                Generate interview questions
              </button>
            </form>

            <section className="panel result-panel">
              <div className="panel-heading">
                <div>
                  <span className="step-number">03</span>
                  <h3>Resume insights</h3>
                </div>
              </div>

              {!resumeData && (
                <div className="empty-state">
                  <div className="empty-icon">
                    <FileText size={26} />
                  </div>
                  <h3>Your profile starts here</h3>
                  <p>
                    Upload a text-based PDF to extract your skills, education,
                    projects, and experience.
                  </p>
                </div>
              )}

              {resumeData && (
                <div className="results">
                  <span className="result-label">DETECTED SKILLS</span>
                  <div className="keyword-list">
                    {resumeData.details?.skills?.length ? (
                      resumeData.details.skills.map((skill) => (
                        <span key={skill}>{skill}</span>
                      ))
                    ) : (
                      <span>No known skills detected</span>
                    )}
                  </div>

                  {[
                    ["Summary", resumeData.details?.summary],
                    ["Education", resumeData.details?.education],
                    ["Projects", resumeData.details?.projects],
                    ["Experience", resumeData.details?.experience],
                    ["Certifications", resumeData.details?.certifications],
                  ].map(([heading, items]) => (
                    <div key={heading} className="detail-section">
                      <strong>{heading}</strong>
                      {items?.length ? (
                        <ul className="feedback-list">
                          {items.map((item, index) => (
                            <li key={`${heading}-${index}`}>{item}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="privacy-note">
                          No separate {heading.toLowerCase()} section detected.
                        </p>
                      )}
                    </div>
                  ))}

                  <details>
                    <summary>Match resume to a job description</summary>
                    <form onSubmit={matchResume}>
                      <label htmlFor="jobDescription">
                        Job description
                      </label>
                      <textarea
                        id="jobDescription"
                        value={jobDescription}
                        onChange={(event) =>
                          setJobDescription(event.target.value)
                        }
                        placeholder="Paste the target job description..."
                        required
                      />
                      <button
                        className="submit-button"
                        type="submit"
                        disabled={loading}
                      >
                        Analyze role match
                      </button>
                    </form>

                    {matchResult && (
                      <div className="results">
                        <strong>Match analysis</strong>
                        <pre>{JSON.stringify(matchResult, null, 2)}</pre>
                      </div>
                    )}
                  </details>
                </div>
              )}
            </section>
          </div>
        )}

        {activeTab === "interview" && (
          <div className="workspace-grid">
            <section className="panel form-panel">
              <div className="panel-heading">
                <div>
                  <span className="step-number">
                    {String(currentIndex + 1).padStart(2, "0")}
                  </span>
                  <h3>Your question</h3>
                </div>
                <span className="required-label">
                  {questions.length
                    ? `${currentIndex + 1} OF ${questions.length}`
                    : "NO QUESTIONS"}
                </span>
              </div>

              {!currentQuestion && (
                <div className="empty-state">
                  <h3>No active interview</h3>
                  <p>Upload your resume and generate questions first.</p>
                  <button
                    className="submit-button"
                    onClick={() => changeTab("resume")}
                  >
                    Go to resume studio
                  </button>
                </div>
              )}

              {currentQuestion && (
                <>
                  <div className="result-label">
                    {currentQuestion.category?.replaceAll("_", " ")}
                  </div>
                  <h2>{currentQuestion.question}</h2>
                  <p className="privacy-note">
                    Topic: {currentQuestion.topic || "General"}
                  </p>

                  <label htmlFor="candidateAnswer">Your answer</label>
                  <textarea
                    id="candidateAnswer"
                    value={answers[currentQuestion.id] || ""}
                    onChange={(event) =>
                      {
                        setAnswers((previous) => ({ ...previous, [currentQuestion.id]: event.target.value }));
                        setEvaluations((previous) => {
                          const updated = { ...previous };
                          delete updated[currentQuestion.id];
                          return updated;
                        });
                      }
                    }
                    placeholder="Explain your approach, key concepts, and examples..."
                    rows={8}
                  />

                  <button
                    className="submit-button"
                    onClick={evaluateCurrentAnswer}
                    disabled={loading}
                  >
                    {loading ? (
                      <LoaderCircle className="spin" size={18} />
                    ) : (
                      <Sparkles size={18} />
                    )}
                    {loading
                      ? "Evaluating..."
                      : evaluations[currentQuestion.id]
                        ? "Evaluate again"
                        : "Submit and evaluate"}
                  </button>

                  {evaluations[currentQuestion.id] && (
                    <div className="results">
                      <span className="result-label">YOUR SCORE</span>
                      <div className="score-display">
                        {evaluations[currentQuestion.id].score}
                        <span>/10</span>
                      </div>
                      {evaluations[currentQuestion.id].strengths?.length > 0 && (
                        <>
                          <strong>What went well</strong>
                          <ul className="feedback-list">
                            {evaluations[currentQuestion.id].strengths.map((item) => <li key={item}>{item}</li>)}
                          </ul>
                        </>
                      )}
                      <strong>Feedback</strong>
                      <ul className="feedback-list">
                        {evaluations[currentQuestion.id].feedback?.map(
                          (item, index) => (
                            <li key={index}>{item}</li>
                          )
                        )}
                      </ul>
                      <p className="privacy-note">
                        {evaluations[currentQuestion.id].caveat}
                      </p>
                      <p className="method-note">Scoring method: {evaluations[currentQuestion.id].scoring_method || evaluations[currentQuestion.id].model_version || "not reported by backend"}</p>
                    </div>
                  )}

                  <div className="question-navigation">
                    <button
                      type="button"
                      className="nav-item"
                      disabled={currentIndex === 0}
                      onClick={() =>
                        setCurrentIndex((index) => index - 1)
                      }
                    >
                      <ChevronLeft size={18} /> Previous
                    </button>

                    <button
                      type="button"
                      className="nav-item"
                      disabled={currentIndex === questions.length - 1}
                      onClick={() =>
                        setCurrentIndex((index) => index + 1)
                      }
                    >
                      Next <ChevronRight size={18} />
                    </button>
                  </div>
                </>
              )}
            </section>

            <section className="panel result-panel">
              <div className="panel-heading">
                <div>
                  <span className="step-number">02</span>
                  <h3>Interview progress</h3>
                </div>
              </div>

              <div className="results">
                <span className="result-label">COMPLETED ANSWERS</span>
                <div className="score-display">
                  {completedCount}
                  <span>/{questions.length}</span>
                </div>

                <div className="progress-track">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${
                        questions.length
                          ? (completedCount / questions.length) * 100
                          : 0
                      }%`,
                    }}
                  />
                </div>

                <p>Average score: {averageScore}/10</p>

                <div className="question-list">
                  {questions.map((item, index) => (
                      <button type="button" key={item.id} className={`question-item ${currentIndex === index ? "selected" : ""}`} onClick={() => setCurrentIndex(index)}>
                        <span>{evaluations[item.id] ? <CheckCircle2 size={17} /> : answers[item.id]?.trim() ? <MessageSquareText size={17} /> : <ClipboardList size={17} />}
                          Question {index + 1} · {evaluations[item.id] ? "Evaluated" : answers[item.id]?.trim() ? "Answered" : "Pending"}
                        </span>
                        <strong>{evaluations[item.id] ? `${evaluations[item.id].score}/10` : "—"}</strong>
                      </button>
                  ))}
                </div>

                {questions.length > 0 &&
                  completedCount === questions.length && (
                    <div className="detail-section">
                      <h3>Interview complete</h3>
                      <p>
                        Final average: {averageScore}/10 across{" "}
                        {completedCount} evaluated answers.
                      </p>
                      <button
                        className="submit-button"
                        onClick={() => changeTab("report")}
                      >
                        View final report
                      </button>
                    </div>
                  )}

                <button
                  type="button"
                  className="nav-item"
                  onClick={resetInterview}
                >
                  <RotateCcw size={17} /> Reset interview
                </button>
              </div>
            </section>
          </div>
        )}

        {activeTab === "match" && (
          <div className="workspace-grid">
            <form className="panel form-panel" onSubmit={matchResume}>
              <div className="panel-heading"><div><span className="step-number">01</span><h3>Resume to role match</h3></div></div>
              {!resumeData && <p>Upload a resume first to compare it with a role.</p>}
              <label htmlFor="matchJobDescription">Job description</label>
              <textarea id="matchJobDescription" value={jobDescription} onChange={(event) => setJobDescription(event.target.value)} placeholder="Paste the target job description..." required />
              <button className="submit-button" type="submit" disabled={loading || !resumeData}>
                {loading ? <LoaderCircle className="spin" size={18} /> : <BriefcaseBusiness size={18} />}
                {loading ? "Comparing..." : "Analyze role match"}
              </button>
            </form>
            <section className="panel result-panel">
              <div className="panel-heading"><div><span className="step-number">02</span><h3>Match analysis</h3></div></div>
              {!matchResult ? <div className="empty-state"><div className="empty-icon"><BriefcaseBusiness size={26} /></div><h3>Compare your resume with a role</h3><p>Local TF-IDF similarity and keyword overlap provide a text alignment signal, not hiring probability.</p></div> : <div className="results">
                <span className="result-label">TF-IDF TEXT SIMILARITY</span><div className="score-display">{matchResult.match_score}<span>/100</span></div>
                <p>Job-description keyword coverage: <strong>{matchResult.keyword_coverage}%</strong></p>
                <p>{matchResult.explanation}</p>
                <h3>Matching keywords</h3><div className="keyword-list">{matchResult.matched_terms?.length ? matchResult.matched_terms.map((term) => <span key={term}>{term}</span>) : <p>No matching keywords detected.</p>}</div>
                <h3>Potential gaps</h3><div className="keyword-list">{matchResult.missing_terms?.length ? matchResult.missing_terms.map((term) => <span className="missing-term" key={term}>{term}</span>) : <p>No missing terms detected.</p>}</div>
                <ul className="feedback-list">{matchResult.recommendations?.map((tip) => <li key={tip}>{tip}</li>)}</ul>
              </div>}
            </section>
          </div>
        )}

        {activeTab === "answer" && (
          <div className="workspace-grid">
            <form
              className="panel form-panel"
              onSubmit={evaluateManualAnswer}
            >
              <div className="panel-heading">
                <div>
                  <span className="step-number">01</span>
                  <h3>Answer evaluator</h3>
                </div>
              </div>

              <label htmlFor="manualQuestion">Interview question</label>
              <textarea
                id="manualQuestion"
                value={manualQuestion}
                onChange={(event) => setManualQuestion(event.target.value)}
                placeholder="Enter an interview question..."
                required
              />

              <label htmlFor="manualAnswer">Your answer</label>
              <textarea
                id="manualAnswer"
                value={manualAnswer}
                onChange={(event) => setManualAnswer(event.target.value)}
                placeholder="Write your answer..."
                required
              />

              <label htmlFor="referenceAnswer">
                Reference answer <span className="optional">(optional)</span>
              </label>
              <textarea
                id="referenceAnswer"
                value={referenceAnswer}
                onChange={(event) =>
                  setReferenceAnswer(event.target.value)
                }
                placeholder="Add key concepts or an ideal answer..."
              />

              <button
                className="submit-button"
                type="submit"
                disabled={loading}
              >
                {loading ? (
                  <LoaderCircle className="spin" size={18} />
                ) : (
                  <Sparkles size={18} />
                )}
                {loading ? "Evaluating..." : "Evaluate answer"}
              </button>
            </form>

            <section className="panel result-panel">
              <div className="panel-heading">
                <div>
                  <span className="step-number">02</span>
                  <h3>Evaluation results</h3>
                </div>
              </div>

              {!manualResult && (
                <div className="empty-state">
                  <div className="empty-icon">
                    <Sparkles size={26} />
                  </div>
                  <h3>Your feedback appears here</h3>
                  <p>Submit an answer to see its score and evaluation signals.</p>
                </div>
              )}

              {manualResult && (
                <div className="results">
                  <span className="result-label">PREDICTED SCORE</span>
                  <div className="score-display">
                    {manualResult.score}
                    <span>/10</span>
                  </div>

                  <p className="method-note">Scoring method: {manualResult.scoring_method || manualResult.model_version || "not reported by backend"}</p>
                  {manualResult.strengths?.length > 0 && <><strong>What went well</strong><ul className="feedback-list">{manualResult.strengths.map((item) => <li key={item}>{item}</li>)}</ul></>}

                  <strong>Feedback</strong>
                  <ul className="feedback-list">
                    {manualResult.feedback?.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>

                  <p className="privacy-note">{manualResult.caveat}</p>

                  <details>
                    <summary>Evaluation signals</summary>
                    <pre>
                      {JSON.stringify(manualResult.signals, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </section>
          </div>
        )}

        {activeTab === "report" && (
          <section className="panel result-panel">
            <div className="panel-heading">
              <div>
                <span className="step-number">03</span>
                <h3>Final interview report</h3>
              </div>
            </div>

            <div className="results">
              <span className="result-label">OVERALL AVERAGE</span>
              <div className="score-display">
                {completedCount ? averageScore : "—"}
                <span>/10</span>
              </div>

              <p>
                Generated {questions.length} questions. Submitted {submittedCount} answers and evaluated {completedCount}.
                Scores are experimental ML estimates, not a definitive
                measure of technical correctness.
              </p>

              {completedCount > 0 && (
                <div className="detail-section">
                  <h3>Strong areas</h3>
                  {strongAreas.length ? <ul className="feedback-list">{strongAreas.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No consistent strengths were identified by these signals yet.</p>}
                  <h3>Practice next</h3>
                  {improvementAreas.length ? <ul className="feedback-list">{improvementAreas.map((item) => <li key={item}>{item}</li>)}</ul> : <p>No major gaps were flagged by these limited text signals.</p>}
                  <strong>Question scores</strong>
                  <div className="score-breakdown">
                    {questions.map((item, index) => (
                      <div className="score-row" key={item.id}>
                        <span>Q{index + 1} · {item.topic || item.category}</span>
                        <div className="progress-track"><div className="progress-fill" style={{ width: `${(evaluations[item.id]?.score || 0) * 10}%` }} /></div>
                        <strong>{evaluations[item.id] ? `${evaluations[item.id].score}/10` : "—"}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {questions.map((item, index) => (
                <div className="detail-section" key={item.id}>
                  <strong>
                    {index + 1}. {item.question}
                  </strong>
                  <p>
                    Score:{" "}
                    {evaluations[item.id]
                      ? `${evaluations[item.id].score}/10`
                      : "Not evaluated"}
                  </p>
                  {answers[item.id] && <p className="report-answer"><strong>Your answer:</strong> {answers[item.id]}</p>}
                  {evaluations[item.id]?.strengths?.length > 0 && <p><strong>Strengths:</strong> {evaluations[item.id].strengths.join(" ")}</p>}
                  <ul className="feedback-list">
                    {evaluations[item.id]?.feedback?.map((feedback, i) => (
                      <li key={i}>{feedback}</li>
                    ))}
                  </ul>
                </div>
              ))}

              <button
                className="submit-button"
                onClick={() => window.print()}
              >
                Print / Save report as PDF
              </button>
              <button className="secondary-button" onClick={exportReport} disabled={!questions.length}>
                <Download size={17} /> Export report as JSON
              </button>

              <button
                className="nav-item"
                onClick={() => changeTab("interview")}
              >
                Return to interview
              </button>
            </div>
          </section>
        )}

        <footer className="page-footer">
          INTERVIEWIQ ML · LOCAL PROCESSING · EXPERIMENTAL EVALUATION
        </footer>
      </section>
    </main>
  );
}
