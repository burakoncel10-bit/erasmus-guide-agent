Erasmus Guide — A Modular Agent Skill for Exam Preparation

A custom Claude Code Agent Skill that acts as a one-on-one tutor for the Erasmus English proficiency exam. It plans study weeks, scores essays against a fixed rubric, generates exam-format practice material, and tracks progress across an eight-month preparation timeline.

I built this for my own exam preparation and I am its primary user. It is under active development.

Note on language: The skill files are written in Turkish because the target user is a Turkish university student — explanations land better in the student's native language, while all study material (vocabulary, sentence patterns, corrections) stays in English. This bilingual split is a deliberate design choice, described below.

The problem

Generic language-model tutoring fails on a specific exam for three reasons:

It doesn't know the format. The Erasmus exam scores Reading 25, Listening 25, and Writing 50. Writing is half the grade, but a general-purpose assistant spreads attention evenly across all four skills.
Its feedback isn't comparable. Ask the same model to grade two essays a week apart and you get two differently-shaped responses. There is no way to tell whether you improved.
It is too agreeable. Language models tend to soften criticism. For exam preparation, softened feedback is worse than no feedback.

This skill is an attempt to solve all three through structure rather than through longer prompts.

Architecture
SKILL.md                        # orchestrator: modes, triggers, routing rules
references/
├── essay-turleri.md            # essay types and their structures
├── essay-topic-bankasi.md      # categorised topic bank for rotation
├── akademik-kelime.md          # B1 → B2 vocabulary upgrade lists
├── kalip-cumleler.md           # academic sentence patterns
├── feedback-rubrigi.md         # 50-point scoring rubric
├── calisma-plani.md            # weekly plan templates per phase
└── ilerleme-takibi.md          # progress template and analysis guide

Progressive context loading. The orchestrator does not load all seven reference files on every invocation. Each mode declares which files it needs, and only those are read. Essay feedback loads the rubric and vocabulary lists; planning loads the schedule templates. This keeps the working context small and the responses focused — loading everything would push the model toward generic, averaged-out answers.

Operating modes

The orchestrator routes to one of six modes based on the user's message. Each has explicit triggers and a fixed output contract.

Mode	Triggered by	Loads
Planning	"weekly plan", "what should I study"	calisma-plani.md
Essay feedback	a submitted essay	feedback-rubrigi.md, akademik-kelime.md, kalip-cumleler.md
Exercise generation	"give me a reading test", "essay topic"	essay-topic-bankasi.md
Instruction	"teach me vocabulary", "how do I write X"	essay-turleri.md, akademik-kelime.md
Progress tracking	"I finished last week's tasks"	ilerleme-takibi.md
Weakness analysis	"how am I doing", "what's my weak area"	—
Design decisions worth explaining
Rubric-driven scoring instead of free-form feedback

Essays are scored on five criteria at ten points each — task achievement, coherence, lexical resource, grammar, mechanics — with banded descriptors for every score range. The output format is locked: a score table, then seven fixed sections in a fixed order.

The point is not the rubric itself but comparability. Because the shape never changes, the student can put two feedback reports side by side and see exactly which criterion moved.

Constrained generation for reading practice

Reading exercises are not freely generated. The skill must produce exactly ten paragraphs of five to seven sentences, followed by exactly ten gap-fill sentences — one per paragraph, in order. The critical rule: the answer must be a word that appears in the source paragraph. No multiple choice, and every answer key entry cites its paragraph.

Without these constraints the model produces plausible-looking questions whose answers do not exist in the text. Format constraints are what turn generation into practice material.

Deliberate refusal to generate listening content

The skill is explicitly instructed not to produce listening transcripts. Synthetic transcripts would train the student on clean, model-generated prose rather than real speech with accents, hesitation, and pace. Instead the mode returns graded source recommendations (BBC 6-Minute English, TED-Ed, and similar) plus listening strategy.

This is the decision I would most want to defend in a conversation: knowing what an agent should refuse to do is part of designing it.

Behavioural guardrails against sycophancy

Several rules exist purely to counteract the model's tendency to please:

Never end an essay review on praise if problems remain.
Produce no fewer than five and no more than ten sentence-level corrections — fewer means the review was superficial, more overwhelms the student.
Never induce guilt about missed work; reduce the plan instead.
No empty encouragement. Concrete tasks instead of motivational language.
Phase-aware planning

The preparation timeline is split into three phases with different intensities: an intensive setup month, a three-month low-load maintenance period during full-time work, and a final intensive phase before the exam. Plan generation reads the current date, determines the phase, and refuses to produce a heavy schedule during the maintenance period — an unrealistic plan is abandoned, and an abandoned plan is worse than a light one.

Batched calibration

First-time setup asks nine questions about level, weak areas, study capacity, and target score — delivered as four grouped batches in a single message rather than nine conversational turns, and never repeated afterwards.

Current limitations
No persistent state. Progress tracking depends on the student reporting what they did. The skill cannot verify it or remember across sessions without being told.
Self-reported scoring. Rubric scores are the model's estimate, not a calibrated grade. They are useful as a relative signal over time, not as an absolute prediction of exam results.
Single-user calibration. The student profile is hard-coded to my own starting level (B1, target B2 academic). Generalising this would require extracting the profile into its own configuration.
Untested reading difficulty. There is no mechanism verifying that generated passages actually sit at B1–B2 level.
Next steps
Extract the student profile into a separate configuration file so the skill works for any user.
Add a structured progress log so trend analysis runs on recorded data rather than recall.
Validate generated reading passages against a readability measure.
Built with

Claude Code · Agent Skills · Markdown

Built and maintained by Burak Öncel — Management Information Systems student, Istinye University.
