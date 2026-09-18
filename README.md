# Erasmus Guide

A study agent for the Erasmus English proficiency exam. It scores essays against
a fixed 50-point rubric, produces weekly study plans sized to how much time the
student actually has, generates practice material in the exam's format, and
keeps a record so progress is something the system knows rather than something
the student has to remember.

I built it for my own exam preparation and I am its primary user.

> The interface and the knowledge base are in Turkish, because the student using
> it is Turkish and explanations land better in a first language. All study
> material — vocabulary, corrections, practice text — stays in English. That
> split is deliberate.

---

## It started as a Claude Code skill

The first version was a set of Markdown files driving a
[Claude Code](https://claude.com/claude-code) skill: an orchestrator that told
the model which reference file to read for which kind of request. That original
file is still here as `ORIGINAL-SKILL.md`, unchanged.

It worked, but three things were only promises:

| In the skill version | In this version |
| --- | --- |
| The orchestrator *asked* the model to load only relevant files | A lookup table in `agent.py` decides, and the UI reports how much was loaded |
| The rubric *asked* for a fixed report format | Scoring returns a JSON schema; the format cannot drift |
| Progress tracking *asked* the student to re-state what they had done | Every scored essay is written to SQLite and analysed from there |

Rewriting it as an application is what turned those from instructions into
properties.

---

## Essay scoring

Paste an essay, get five criteria at ten points each — task achievement,
coherence, lexical resource, grammar, mechanics — each with a one-line
justification, plus a single focus for the next attempt.

![Essay scoring with the rubric breakdown](screnshoot%201.png)

The output is a schema, not prose. Two reviews a month apart have the same
shape, so the student can put them side by side and see which criterion moved.
Comparability was the whole point of writing a rubric; a fixed data structure is
what actually delivers it.

Below the scores come the sentence-level corrections. The prompt fixes the count
between five and ten: fewer reads as a superficial review, more overwhelms the
student and nothing gets fixed.

![Sentence corrections with reasoning](screenshoot%202.png)

Each correction shows the original, the revision, and why — in Turkish, with the
English left in English. Strengths are listed separately and never used to
soften the criticism above them.

---

## Practice generation

Three kinds of practice, each with its own constraints.

![Exercise generation tab](screenshoot%203.png)

Reading exercises are locked to the exam format: ten paragraphs of five to seven
sentences, at B1–B2 level.

![Ten generated reading passages](screenshoot%204.png)

Then exactly ten gap-fill items, one per paragraph in order, where **the answer
must be a word that appears in its source paragraph** — and the answer key cites
which paragraph each came from.

![Gap-fill exercise and answer key](screenshoot%205.png)

That constraint is the whole difference between practice material and
plausible-looking filler. Without it the model writes questions whose answers
are nowhere in the text.

The listening mode deliberately refuses to generate transcripts. Synthetic
transcripts would train the student on clean model prose rather than real speech
with accents, hesitation and pace, so it returns graded real sources and
listening strategy instead. Knowing what an agent should decline to do is part
of designing one.

---

## Study plans

The agent computes which preparation phase today falls into and sizes the week
accordingly. During the low-intensity phase it refuses to produce a heavy
schedule: an unrealistic plan gets abandoned, and an abandoned plan is worse
than a light one.

![Weekly study plan generated for the current phase](screenshoot%206.png)

The plan is not generated from the date alone. It reads the stored essay history
first — in the run above it noticed scores of 26, 45 and 29, called out the
inconsistency, and built the week around writing regularity rather than adding
new material. That is the state layer doing something the skill version could
not: it needs a record, not a recollection.

---

## Progress

![Progress tab with score history and per-criterion averages](screenshoot%207.png)

Scores over time, per-criterion averages, and the three weakest areas surfaced
in the sidebar. Academic vocabulary at 5.3/10 and grammar at 6.0/10 is not
something the student would have worked out by re-reading three separate
feedback reports.

---

## Selective context loading

Each mode declares the reference files it needs:

```python
MODE_CONTEXT = {
    "feedback": ["feedback-rubrigi.md", "akademik-kelime.md", "kalip-cumleler.md"],
    "plan":     ["calisma-plani.md"],
    "exercise": ["essay-topic-bankasi.md", "essay-turleri.md"],
    "progress": ["ilerleme-takibi.md"],
}
```

Essay scoring loads 15,764 of the knowledge base's 45,034 characters — about a
third. The footer of the running app prints this figure, visible in the
screenshots above, so the claim is checkable rather than asserted. Loading
everything would push the model toward generic, averaged-out answers; the files
were split for this reason and this table is where the split is enforced.

---

## Running it

Python 3.10+ and a free Google AI Studio key
(<https://aistudio.google.com>, no credit card).

```bash
git clone https://github.com/burakoncel10-bit/erasmus-guide-agent.git
cd erasmus-guide-agent
pip install -r requirements.txt
```

Set the key:

```bash
# Windows PowerShell — then open a NEW terminal
setx GEMINI_API_KEY "your-key"

# macOS / Linux
export GEMINI_API_KEY="your-key"
```

Start it:

```bash
streamlit run app.py
```

It opens at `http://localhost:8501`. To try essay scoring without writing three
hundred words, use the **Örnek essay yükle** button — it loads a deliberately
B1-level essay with typical mistakes in it. That essay scores 29/50, roughly
where a human marker would put it.

On Windows, if `python` and `pip` are not on your PATH, use `py -m pip install`
and `py -m streamlit run app.py`. There is also an optional key field in the
sidebar if you would rather not set an environment variable.

```
app.py             Streamlit interface, four tabs
agent.py           context loading, prompts, scoring schema, generation
store.py           SQLite persistence and progress analysis
knowledge/         the reference modules the agent loads from
ORIGINAL-SKILL.md  the Claude Code skill this grew out of
```

---

## Limitations

- **Scores are an estimate, not a grade.** Useful as a relative signal over
  time, not as a prediction of what an examiner would award.
- **No evaluation set.** The text-to-SQL project in my other repository is
  measured against reference answers; this one is not, because essay quality has
  no single correct output to compare against. Scoring consistency — how far the
  same essay's score moves across repeated runs — is measurable, and is the next
  thing I want to check.
- **Single-user calibration.** Student profile, exam date and phase boundaries
  are hard-coded to my own preparation. Generalising means extracting them into
  configuration.
- **Local storage.** `progress.db` sits next to the code. If the app were
  hosted, that file would reset on every restart.
- **Free-tier model availability.** The app surfaces API errors rather than
  retrying, so a busy model shows an error instead of a result.

---

## Note on AI assistance

I used Claude Code for setup, debugging and boilerplate. The knowledge base, the
rubric, the mode design and the decisions about what the agent should refuse to
do are mine — they came out of preparing for this exam, which is also why I am
the one using the tool.

---

Built by Burak Öncel — Management Information Systems, Istinye University.
