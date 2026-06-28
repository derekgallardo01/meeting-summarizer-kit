# Diagrams

GitHub renders Mermaid natively. These render on the README and here.

## End-to-end pipeline

```mermaid
flowchart LR
    F[Transcript file<br/>.txt / .vtt / .srt / .json] --> P["transcript.parse_file()"]
    P --> D{detect_format}
    D --> T["Transcript<br/>(speaker-attributed segments)"]
    T --> S["Summarizer.summarize()"]
    S --> B{Backend?}
    B -- "template (default)" --> ST["_summarize_template()"]
    B -. "claude" .-> CL["Claude messages.create()"]
    ST --> SUM[Summary]
    ST --> DEC[Decisions]
    ST --> AC["extract_action_items()"]
    ST --> OQ[Open questions]
    AC --> AI[Action items<br/>owner + description + due]
    SUM --> R[Recap]
    DEC --> R
    AI --> R
    OQ --> R
    CL --> R
    R --> MD["recap.to_markdown()"]
```

## The 4-section recap

```mermaid
flowchart TB
    T[Transcript] --> S{Section}
    S --> SUM["Summary<br/>first 2 substantive sentences"]
    S --> DEC["Decisions<br/>(sentences containing decision verbs:<br/>agreed, decided, approved, ...)"]
    S --> AI["Action items<br/>(via extract_action_items - separate module)"]
    S --> OQ["Open questions<br/>(?-ended sentences without substantive next response)"]
```

## Action-item extraction (the first-person trick)

```mermaid
flowchart TB
    sentence[Sentence from segment]
    sentence --> FP{First-person<br/>pattern matches?}
    FP -- "yes (e.g., I'll draft...)" --> FP_OWNER["owner = segment.speaker<br/>(NOT the literal 'I')"]
    FP -- no --> TP{Third-person<br/>pattern matches?}
    TP -- "yes (e.g., Bob will...)" --> TP_OWNER["owner = matched name"]
    TP -- no --> RQ{Request pattern?}
    RQ -- "yes (e.g., Carol, please...)" --> RQ_OWNER["owner = addressed name"]
    RQ -- no --> SKIP[Not an action item]
    FP_OWNER --> V{Assignment verb<br/>in description?}
    TP_OWNER --> V
    RQ_OWNER --> V
    V -- no --> SKIP
    V -- yes --> AI[ActionItem<br/>owner + description + due]
```

## Format auto-detection

```mermaid
flowchart TB
    C[First 500 chars of content]
    C --> W{Starts with 'WEBVTT'?}
    W -- yes --> VTT[vtt]
    W -- no --> J{Starts with '{' or '['<br/>AND parses as JSON<br/>with 'segments' or 'transcript' key?}
    J -- yes --> OJ[otter_json]
    J -- no --> S{Starts with digit<br/>followed by timestamp?}
    S -- yes --> SRT[srt]
    S -- no --> TXT[text]
```

## Stub vs LLM summarizer

```mermaid
flowchart TB
    subgraph Template["template backend (default)"]
        direction TB
        T1[Transcript]
        T2["_extract_summary - first 2 substantive sentences"]
        T3["_extract_decisions - decision-verb sentences"]
        T4["extract_action_items - regex extractor"]
        T5["_extract_open_questions - heuristic"]
        T1 --> T2
        T1 --> T3
        T1 --> T4
        T1 --> T5
        T2 --> TR[Recap]
        T3 --> TR
        T4 --> TR
        T5 --> TR
    end

    subgraph Claude["claude backend (when wired)"]
        direction TB
        C1[Transcript.full_text]
        C2["client.messages.create(<br/>system=prompts.SUMMARIZER,<br/>messages=[transcript])"]
        C3["json.loads(response.content)"]
        C4[Build Recap from parsed JSON]
        C1 --> C2 --> C3 --> C4
    end

    Template -. "same Recap shape" .- Claude
```

## Eval suite (two independent gates)

```mermaid
sequenceDiagram
    participant CI
    participant E as evals/run.py
    participant T as Transcript
    participant S as Summarizer
    participant X as Extractor

    CI->>E: python evals/run.py
    Note over E: Suite 1: Recap quality
    loop each recap-quality case
        E->>T: parse_file(fixture)
        E->>S: summarize(transcript)
        E->>E: check rendered markdown<br/>contains required phrases
    end
    Note over E: Suite 2: Action items
    loop each action-item case
        E->>T: parse_file(fixture)
        E->>X: extract_action_items(transcript)
        loop each expected_item
            E->>E: any extracted with matching<br/>owner + description substring?
        end
    end
    E-->>CI: exit 0 iff both suites green
```

## Repo shape

```mermaid
flowchart TB
    R[meeting-summarizer-kit]
    R --> SRC[src/meeting_summarizer/]
    SRC --> S1[transcript.py — 4-format parser]
    SRC --> S2[extractor.py — action item patterns]
    SRC --> S3[summarizer.py — 4-section recap + LLM seam]
    SRC --> S4[cli.py — summarize/demo/list-formats]
    R --> FX[fixtures/]
    FX --> F1[01-product-sync.txt — plain text]
    FX --> F2[02-zoom-recording.vtt — VTT]
    FX --> F3[03-customer-call.srt — SRT]
    FX --> F4[04-otter-transcript.json — Otter JSON]
    R --> T[tests/]
    T --> T1[test_transcript.py]
    T --> T2[test_extractor.py]
    T --> T3[test_summarizer.py]
    R --> EV[evals/]
    EV --> EQ[recap-quality.json + action-items.json]
    EV --> ER[run.py — both suites]
    R --> DOCS[docs/]
    R --> CI[.github/workflows/ci.yml]
    R --> DK[Dockerfile]
```
