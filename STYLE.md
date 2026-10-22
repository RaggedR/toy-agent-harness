# Writing style

Rules for documents written for Robin. Derived from his own writing:
`~/git/education/python.pdf`, `~/git/education/unix_philosophy.pdf`, and the
preamble of `~/git/education/discrete-math.tex`.

## Prose

One fact per sentence. Short declarative sentences. Let the facts carry the
weight.

**Do not flag significance.** Delete "importantly", "worth noting", "worth
pausing on", "matters enormously", "the interesting part", "note that", "earns
its place". The reader decides what matters.

> Bad: This seems to contradict the trace above, and the resolution is worth
> dwelling on, because it explains why any of this is reliable.
>
> Good: Section 1.1 said the model emits only tokens. Section 1.5 showed a typed
> `tool_use` block. Both are true.

**No closing flourishes.** A section stops when the facts run out. No epigram,
no inversion, no aphorism.

> Bad: It is a comfort, not a component.
>
> Good: Anything you can do with the SDK you can do with curl.

**No em-dash asides.** Break the aside into its own sentence, or cut it.

> Bad: It is text --- or bytes, which is text with fewer manners --- at every
> stage.
>
> Good: The data is text at every stage.

**No bold pronouncements.** If a sentence needs bold to land, rewrite the
sentence.

**No performed candour.** Do not write "stated honestly", "to be fair", "the
honest answer is". State the thing.

**Mechanism first, then the name for it.** Explain what happens, then say what
it is called.

> Python figures out types at runtime, not at compile time. This is called
> dynamic typing.

**Spell out an acronym on first use**, with the abbreviation in brackets after
it. "Institute of Electrical and Electronics Engineers (IEEE) 754".

**Second person is fine.** "You send a JSON document." Avoid rhetorical second
person: "you can see that", "notice how", "as you would expect".

## Structure

Bottom-up. Nothing is used before it has been explained. If section 4 needs a
term, define it in section 1 or 2, not in a forward reference.

Do not name a thing before the reader needs it. The subject of a document can
stay unmentioned for several pages if its prerequisites come first.

Short paragraphs. One to four sentences.

Code immediately after the claim it demonstrates. Show output as a trailing
comment.

```python
type(42)        # <class 'int'>
0.1 + 0.2       # 0.30000000000000004
```

Tables for enumerable facts. Prose for anything with a reason attached.

Lists are for parallel facts. If the items are not parallel, use prose.

## LaTeX preamble

```latex
\documentclass[11pt]{article}          % book for anything with parts
\usepackage[a4paper,margin=2.5cm]{geometry}
\usepackage{amsmath,amssymb}
\usepackage{enumitem}
\usepackage{booktabs}
\usepackage{listings}
\usepackage{xcolor}
\usepackage[colorlinks=true,linkcolor=blue]{hyperref}

\lstset{basicstyle=\ttfamily\small,breaklines=true,frame=single,
  keywordstyle=\bfseries,commentstyle=\itshape\color{gray},
  showstringspaces=false}

\setlist[itemize]{itemsep=1pt,topsep=2pt,parsep=0pt}
\setlist[enumerate]{itemsep=3pt,topsep=3pt}

\title{\textbf{Title}\\
\large Subtitle}
\author{}
\date{2026}
```

Notes on the above:

- `frame=single` on listings, no background fill.
- `linkcolor=blue`. Not a custom colour.
- `\author{}` is empty. `\date` is the year.
- Margins are 2.5cm.
- Lists are tight.

Two additions worth carrying:

```latex
\setlength{\emergencystretch}{3em}   % long inline code overflows margins otherwise
\newenvironment{keep}{\noindent\begin{minipage}{\linewidth}}{\end{minipage}}
```

`keep` wraps a code block so `listings` cannot split it across a page break.

## Compiling

Use `tectonic file.tex`. Not pdflatex, xelatex, or lualatex. Open the result
with `open -a Skim file.pdf`.

Unicode box-drawing characters (`┌ │ └ ←`) have no glyphs in Latin Modern. Use
ASCII (`+- | <-`) in listings, or the characters silently disappear.

## Checklist

Before compiling, search the source for these and delete what you find:

- `worth noting`, `worth pausing`, `importantly`, `matters enormously`,
  `interesting`, `note that`, `earns its place`
- `---` used as an aside rather than a dash between clauses
- `\textbf{}` in body prose
- `honestly`, `to be fair`
- Any sentence that restates the previous sentence for emphasis
- Any section whose last sentence could be deleted without losing a fact

## Replies in chat

The rules above apply to replies too, plus these.

An edit gets a one-line confirmation. Nothing else.

Do not quote the user's own text back at them. They wrote it.

Do not explain how you interpreted the instruction. The result shows it.

Do not offer to revert. If they want it back they will say so.

Do not add observations they did not ask for.

Do not summarise what you just did across several sections. Do not restate the
structure of a document after changing one line of it.

Tool output already shows the work. The reply should add only what the user
cannot see.
