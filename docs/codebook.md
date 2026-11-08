# Codebook: statement stance and themes

> **SYNTHETIC DATA.** The statements coded here are invented (see `docs/data-dictionary.md`).

This codebook defines the codes that `src/analysis/code_text.py` applies to each statement in
`statements.csv`. Coding is rule-based: keyword and phrase patterns only, with no LLM calls and no learned
weights. Every coded value records the rule ID that produced it, so each decision can be traced to a
row in the rule table below.

**How the rules were built (ANL-03).** Rules were written and tuned on the **dev half** only. Under the public
split, statements from even-numbered institutions are dev. Every rule cites an example that occurs
verbatim in a dev statement, and the examples below are all dev text. The held-out half is used once, after the
rules are frozen, to report how well they generalize.

## Unit of coding
A statement is split into sentences at `.`, `!` or `?` followed by whitespace. Each code is decided over all
of the statement's sentences.

## Stance (−2 … +2): the department's official position on generative AI

| Code | Meaning | Include | Exclude | Dev example |
|---|---|---|---|---|
| −2 | Prohibited | AI use on coursework is banned, prohibited, not permitted, or earns no credit | Restrictions that leave room for instructor-approved use (→ −1) | "The department prohibits the use of generative AI tools on any graded work." |
| −1 | Cautious / limited | Caution, concerns, "avoid", limited or restricted use, not allowed *by default* | Outright bans (→ −2); course-by-course deference with no lean (→ 0) | "The faculty view AI assistants with caution and restrict them in most courses." |
| 0 | Instructor decides / no position | Each instructor or syllabus sets the rule; policies vary or differ; neither endorsed nor banned | Any clear lean toward allowing (→ +1) or restricting (→ −1) | "Each instructor sets the policy on generative AI tools for their own course." |
| +1 | Permitted with conditions | Welcome, allowed, may use, supports thoughtful/responsible use, *not prohibited* | Use that is required or central to the curriculum (→ +2) | "Students are welcome to use AI assistants in many courses, provided they follow the course guidelines." |
| +2 | Embraced / integrated | AI is embraced, required, integrated throughout the curriculum, or something students must master | Permission alone (→ +1) | "Working with AI tools is a required part of our programming courses." |

**Decision procedure.** Stance rules are tried **in table order**, and the first rule that matches any sentence decides.
Negation phrases come first, so their cue words cannot be misread: "not prohibited" is +1 before "prohibit" is
−2, and "neither endorses nor bans" is 0 before "ban" is −2. If no rule matches, the stance is **0** (`S0-default`).
Sentences that mention AI without taking a position (e.g. "Generative AI tools are changing quickly…") match no
stance rule.

## Themes (true/false): what the statement talks about

| Code | Include | Exclude | Dev example |
|---|---|---|---|
| `mentions_integrity` | Academic integrity, honor code, originality, misrepresenting AI output, dishonesty, student conduct, plagiarism | "Integrity" in a technical sense, e.g. "protect data integrity when submitting files" | "Undisclosed use of AI tools will be handled under the honor code." |
| `mentions_collaboration` | AI as a collaborator, teammate or partner; teamwork; group projects; co-designing; working or deciding together | "in collaboration with the campus library" (an institutional partnership, not collaborative work); "Internship partners" (a careers mention) | "AI tools can act as a teammate in group projects, alongside human partners." |
| `mentions_careers` | Employers, industry, careers, internships, jobs | — | "Employers increasingly expect graduates to work effectively with AI-assisted development tools." |

A statement can carry any combination of themes, including integrity and collaboration together.

## Rule table
Generated from `code_text.rules_markdown()`. A test keeps this block identical to the code.

<!-- rules:start -->
| Order | Rule | Code | Value | Pattern (case-insensitive) | Dev example |
|---|---|---|---|---|---|
| 1 | `S+1-not-prohibited` | stance | 1 | `\bnot prohibited\b` | "AI use is not prohibited" |
| 2 | `S-1-not-by-default` | stance | -1 | `\bnot permitted by default\b` | "are not permitted by default" |
| 3 | `S0-no-single-rule` | stance | 0 | `\bnot adopted a single\b` | "has not adopted a single rule on AI tools" |
| 4 | `S0-neither-nor` | stance | 0 | `\bneither endorses nor bans\b` | "neither endorses nor bans generative AI" |
| 5 | `S-2-prohibit` | stance | -2 | `\bprohibit(s\|ed)?\b` | "The department prohibits the use of generative AI tools" |
| 6 | `S-2-not-permitted` | stance | -2 | `\bnot permitted\b` | "is not permitted in computer science courses" |
| 7 | `S-2-may-not-use` | stance | -2 | `\bmay not use\b` | "Students may not use generative AI systems" |
| 8 | `S-2-ban` | stance | -2 | `\bban\w*` | "AI assistants are banned from all programming assignments" |
| 9 | `S-2-no-credit` | stance | -2 | `\bno credit\b` | "will receive no credit" |
| 10 | `S-1-caution` | stance | -1 | `\bcaution\b` | "The department urges caution with generative AI" |
| 11 | `S-1-concerns` | stance | -1 | `\bserious concerns\b` | "Generative AI tools raise serious concerns" |
| 12 | `S-1-not-allowed-unless` | stance | -1 | `\bnot allowed unless\b` | "they are not allowed unless told otherwise" |
| 13 | `S-1-avoid` | stance | -1 | `\bavoid\b` | "Students should generally avoid AI tools" |
| 14 | `S-1-limited` | stance | -1 | `\blimited (use\|to)\b` | "Limited use of AI for looking up concepts" |
| 15 | `S-1-restrict` | stance | -1 | `\brestrict\w*` | "restrict them in most courses" |
| 16 | `S0-each-instructor` | stance | 0 | `\beach instructor\b` | "Each instructor sets the policy" |
| 17 | `S0-vary` | stance | 0 | `\bvary by course\b` | "vary by course and are described in each syllabus" |
| 18 | `S0-left-to-faculty` | stance | 0 | `\bleft to individual\b` | "a decision left to individual faculty members" |
| 19 | `S0-differ` | stance | 0 | `\bdiffer\b` | "rules on AI assistance differ between classes" |
| 20 | `S+1-thoughtful` | stance | 1 | `\bsupports? thoughtful\b` | "The department supports thoughtful use" |
| 21 | `S+1-welcome` | stance | 1 | `\bwelcome to use\b` | "Students are welcome to use AI assistants" |
| 22 | `S+1-support-learning` | stance | 1 | `\bsupport learning\b` | "Generative AI can support learning" |
| 23 | `S+1-adopting` | stance | 1 | `\badopting\b` | "the faculty are adopting it in a growing number of courses" |
| 24 | `S+1-may-use` | stance | 1 | `\bmay use\b` | "students may use AI tools for some tasks" |
| 25 | `S+1-responsible` | stance | 1 | `\bresponsible use\b` | "Responsible use of AI assistants is allowed" |
| 26 | `S+2-embrace` | stance | 2 | `\bembrace\w*` | "The department embraces generative AI" |
| 27 | `S+2-curriculum` | stance | 2 | `\bthroughout the curriculum\b` | "integrating AI coding assistants throughout the curriculum" |
| 28 | `S+2-transforming` | stance | 2 | `\btransforming\b` | "Generative AI is transforming software development" |
| 29 | `S+2-required` | stance | 2 | `\brequired part\b` | "is a required part of our programming courses" |
| any | `I-academic-integrity` | mentions_integrity | 1 | `\bacademic integrity\b` | "a violation of the academic integrity policy" |
| any | `I-honor-code` | mentions_integrity | 1 | `\bhonor code\b` | "will be handled under the honor code" |
| any | `I-originality` | mentions_integrity | 1 | `\boriginality\b` | "responsible for the originality of their work" |
| any | `I-misrepresent` | mentions_integrity | 1 | `\bmisrepresent\w*` | "must not misrepresent AI output as their own" |
| any | `I-dishonesty` | mentions_integrity | 1 | `\bdishonest\w*` | "counts as academic dishonesty" |
| any | `I-conduct` | mentions_integrity | 1 | `\bstudent conduct\b` | "referred to the office of student conduct" |
| any | `I-plagiarism` | mentions_integrity | 1 | `\bplagiari\w*` | "Plagiarism rules apply to text and code" |
| any | `C-collaborators` | mentions_collaboration | 1 | `\bcollaborators?\b` | "treat AI tools as collaborators" |
| any | `C-teamwork` | mentions_collaboration | 1 | `\bteamwork\b` | "how AI assistants can support teamwork" |
| any | `C-collab-problem` | mentions_collaboration | 1 | `\bcollaborative problem` | "collaborative problem-solving exercises" |
| any | `C-teammate` | mentions_collaboration | 1 | `\bteammates?\b` | "AI tools can act as a teammate" |
| any | `C-partners` | mentions_collaboration | 1 | `(?<!internship )\bpartners?\b` | "alongside human partners" |
| any | `C-group-work` | mentions_collaboration | 1 | `\bgroup (projects?\|assignments?)\b` | "Group assignments may ask teams" |
| any | `C-co-design` | mentions_collaboration | 1 | `\bco-design\w*` | "co-designing course activities" |
| any | `C-together` | mentions_collaboration | 1 | `\b(working\|decide) together\b` | "Faculty and students are working together" |
| any | `K-employers` | mentions_careers | 1 | `\bemployers?\b` | "Employers increasingly expect graduates" |
| any | `K-industry` | mentions_careers | 1 | `\bindustry\b` | "an industry reshaped by AI" |
| any | `K-careers` | mentions_careers | 1 | `\bcareers?\b` | "an important skill for careers in software" |
| any | `K-internship` | mentions_careers | 1 | `\binternships?\b` | "Internship partners report" |
| any | `K-job` | mentions_careers | 1 | `\bjobs?\b` | "Graduates will enter a job market" |
| last | `S0-default` | stance | 0 | (no stance rule matched) | — |
<!-- rules:end -->

## Known limits
- The rules match words and phrases. A paraphrase that uses none of the dev cue words falls through: stance defaults to 0, and the theme stays false.
- A negation that isn't in the rule list can flip a cue's meaning. For example, any word starting with "ban" codes −2.
- The rule author also wrote the data generator, so they had seen the held-out phrasings. Two safeguards limit this:
  - every rule must cite dev text
  - a test rejects any 4-word sequence that appears only in held-out-reserved phrasings

  These stop direct copying, but not every subtle influence. Read the held-out score with that in mind.
